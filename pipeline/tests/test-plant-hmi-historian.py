"""Unit tests for Plant HMI phase 3: historian store, sampler extraction, history API.

Run: .venv/bin/python tests/test-plant-hmi-historian.py
"""

import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from plant_hmi import plant_historian_sampler as sampler  # noqa: E402
from plant_hmi import plant_historian_store as store  # noqa: E402
from plant_hmi import plant_history_routes as routes  # noqa: E402

NOW = 1_000_000.0


def _fresh_store(tmp_dir: Path):
    """Patches so `store` writes into a throwaway dir with its own thread-local conn."""
    return [mock.patch.object(store, "HISTORIAN_DIR", tmp_dir),
            mock.patch.object(store, "DB_PATH", tmp_dir / "h.sqlite"),
            mock.patch.object(store, "_local", threading.local()),
            mock.patch.object(store, "_logged_kinds", {})]


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patches = _fresh_store(Path(self.tmp.name))
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def test_bucketed_query_and_step_clamp(self):
        for i in range(10):
            store.insert_sample(NOW + i, "gpu_temp_c", 50 + i)
        result = store.query_samples(["gpu_temp_c"], NOW, NOW + 9, step=5)
        self.assertEqual(result["step"], 5)
        self.assertEqual(len(result["series"]["gpu_temp_c"]), 2)  # [0,5) and [5,10) buckets
        auto = store._auto_step(NOW, NOW + 100_000)
        self.assertLessEqual(100_000 / auto, store.MAX_POINTS)
        narrower = store.query_samples(["gpu_temp_c"], NOW, NOW + 100_000, step=1)["step"]
        self.assertGreaterEqual(narrower, auto)  # M6: never below the auto minimum
        wider = store.query_samples(["gpu_temp_c"], NOW, NOW + 10, step=3600)["step"]
        self.assertEqual(wider, 3600)  # widening beyond auto stays as requested

    def test_none_and_non_finite_values_never_stored_or_returned(self):
        store.insert_samples(NOW, {"comfy_up": None, "gpu_temp_c": 60.0})
        store.insert_sample(NOW + 1, "gpu_temp_c", float("nan"))
        store.insert_samples(NOW + 2, {"gpu_temp_c": float("inf")})
        conn = store.get_conn()  # a row that slipped past insert-time filtering (L4 defence in depth)
        conn.execute("INSERT INTO samples (ts, tag, value) VALUES (?, ?, ?)", (NOW, "gpu_temp_c", float("nan")))
        conn.commit()
        result = store.query_samples(["comfy_up", "gpu_temp_c"], NOW - 1, NOW + 3, step=10)
        self.assertEqual(result["series"]["comfy_up"], [])
        self.assertEqual(len(result["series"]["gpu_temp_c"]), 1)  # only the finite 60.0 sample

    def test_alarm_journal_and_latest_states(self):
        store.insert_alarm_journal(NOW, "COMFY_DOWN", "U-902", "HI", None, "raised", "down")
        store.insert_alarm_journal(NOW, "GPU_HOT", "U-901", "HI", None, "raised", "hot")
        store.insert_alarm_journal(NOW + 5, "COMFY_DOWN", "U-902", "HI", None, "cleared", "down")
        rows = store.query_alarms(NOW - 1, NOW + 10, limit=10)
        self.assertEqual([r["state"] for r in rows], ["cleared", "raised", "raised"])  # newest first
        self.assertEqual(set(store.latest_alarm_states()), {"GPU_HOT|U-901|None"})  # only still-raised
        # operator rows after the raise must not hide a still-active alarm (phase 6 review H1)
        store.insert_alarm_journal(NOW + 6, "GPU_HOT", "U-901", None, None, "acked", "seen")
        store.insert_alarm_journal(NOW + 7, "GPU_HOT", "U-901", None, None, "shelved", "maint")
        self.assertEqual(set(store.latest_alarm_states()), {"GPU_HOT|U-901|None"})

    def test_prune_removes_only_old_rows(self):
        store.insert_sample(NOW - store.RETENTION_S - 10, "gpu_temp_c", 1.0)
        store.insert_sample(NOW, "gpu_temp_c", 2.0)
        store.prune_old(now=NOW)
        rows = store.query_samples(["gpu_temp_c"], 0, NOW + 1, step=1)["series"]["gpu_temp_c"]
        self.assertEqual([v for _, v in rows], [2.0])

    def test_writes_never_raise_when_db_unwritable(self):
        with mock.patch.object(store, "HISTORIAN_DIR", Path("/proc/forbidden/historian")), \
             mock.patch.object(store, "_local", threading.local()):
            store.insert_sample(NOW, "gpu_temp_c", 1.0)  # must not raise
            store.insert_alarm_journal(NOW, "X", "Y", "HI", None, "raised", "m")
            store.prune_old(now=NOW)

    def test_log_once_rearms_after_window_and_counts_suppressed(self):
        calls = []
        with mock.patch.object(store.logger, "exception", side_effect=lambda *a, **k: calls.append(a)), \
             mock.patch.object(store, "time") as mock_time:
            mock_time.time.return_value = NOW
            store._log_once("kind_x", ValueError("boom"))
            store._log_once("kind_x", ValueError("boom again"))  # muted, counted
            mock_time.time.return_value = NOW + store.LOG_ONCE_WINDOW_S + 1
            store._log_once("kind_x", ValueError("boom third"))  # re-armed
        self.assertEqual(len(calls), 2)
        self.assertIn("1 lỗi", calls[1][2])  # re-armed log mentions the suppressed count

    def test_schema_on_every_new_connection_and_ts_index(self):
        conn = store._connect()  # a brand new connection, not the cached thread-local one
        try:
            conn.execute("SELECT 1 FROM samples LIMIT 1")
            conn.execute("SELECT 1 FROM alarm_journal LIMIT 1")
            names = [r[1] for r in conn.execute("PRAGMA index_list(samples)").fetchall()]
            self.assertIn("ix_samples_ts", names)
        finally:
            conn.close()


class ExtractTagValuesTest(unittest.TestCase):
    def test_extract_values_none_skipped_and_job_errors_needs_telemetry(self):
        snap = {"instruments": {"LT-102": 5, "LT-801": None}, "equipment": {"D-901": {"level": 2}},
                "flows": {"has_telemetry": True, "jobs": {"ok_1m": 3, "retry_15m": 1, "failed_15m": 0}},
                "utilities": {"comfy": {"ok": True, "queue_running": 1, "queue_pending": 2},
                              "gpu": {"temp_c": 70, "vram_used_mib": 2048}, "host": {}}}
        values = sampler.extract_tag_values(snap)
        self.assertEqual(values["tk102_pending"], 5.0)
        self.assertIsNone(values["tk801_produced"])
        self.assertEqual(values["comfy_up"], 1.0)
        self.assertEqual(values["comfy_queue"], 3.0)
        self.assertEqual(values["gpu_vram_used_gib"], 2.0)
        self.assertEqual(values["d901_failed"], 2.0)
        self.assertEqual(values["job_errors_15m"], 1.0)

        unknown = {"flows": {"has_telemetry": False, "jobs": {"retry_15m": 5, "failed_15m": 5}},
                   "utilities": {"comfy": {}, "gpu": {}, "host": {}}}
        self.assertIsNone(sampler.extract_tag_values(unknown)["job_errors_15m"])  # L7

    def test_comfy_up_is_boolean_never_defaulted(self):
        down = {"utilities": {"comfy": {"ok": False}, "gpu": {}, "host": {}}}
        unk = {"utilities": {"comfy": {"ok": None}, "gpu": {}, "host": {}}}
        self.assertEqual(sampler.extract_tag_values(down)["comfy_up"], 0.0)
        self.assertIsNone(sampler.extract_tag_values(unk)["comfy_up"])


class AlarmJournalDiffTest(unittest.TestCase):
    def setUp(self):
        sampler._previous_alarms = {}
        self.calls = []
        self.patch = mock.patch.object(store, "insert_alarm_journal", side_effect=lambda *a: self.calls.append(a))
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        sampler._previous_alarms = {}

    def test_raise_at_since_then_clear_keeps_severity(self):
        alarm = {"code": "COMFY_DOWN", "tag": "U-902", "severity": "HI", "pid": None,
                 "message": "down", "since": NOW - 30}
        sampler._journal_alarm_diff([alarm], NOW)  # tick fires 30s after the condition started
        self.assertEqual((self.calls[-1][0], self.calls[-1][5]), (NOW - 30, "raised"))  # M5
        sampler._journal_alarm_diff([], NOW + 5)
        self.assertEqual((self.calls[-1][0], self.calls[-1][3], self.calls[-1][5], self.calls[-1][6]),
                        (NOW + 5, "HI", "cleared", "down"))

    def test_unknown_inputs_carry_alarm_over_instead_of_clearing(self):
        alarm = {"code": "COMFY_DOWN", "tag": "U-902", "severity": "LO", "pid": None, "message": "down"}
        sampler._journal_alarm_diff([alarm], NOW)
        sampler._journal_alarm_diff([], NOW + 10, frozenset({"COMFY_DOWN"}))  # probe unknown
        self.assertEqual([c[5] for c in self.calls], ["raised"])
        sampler._journal_alarm_diff([], NOW + 20)  # known and gone
        self.assertEqual(self.calls[-1][5], "cleared")

    def test_persisting_alarm_journals_only_once(self):
        alarm = {"code": "GPU_HOT", "tag": "U-901", "severity": "HI", "pid": None, "message": "hot", "since": NOW}
        sampler._journal_alarm_diff([alarm], NOW)
        sampler._journal_alarm_diff([alarm], NOW + 10)
        self.assertEqual(len(self.calls), 1)


class SeedPreviousAlarmsTest(unittest.TestCase):
    """M4: a restart must not re-journal an alarm that is still active."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patches = _fresh_store(Path(self.tmp.name))
        for p in self.patches:
            p.start()
        sampler._previous_alarms = {}

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()
        sampler._previous_alarms = {}

    def test_seeded_alarm_skips_reraise_then_clears_once_condition_is_gone(self):
        store.insert_alarm_journal(NOW, "COMFY_DOWN", "U-902", "HI", None, "raised", "down")
        sampler._seed_previous_alarms()
        still_active = {"code": "COMFY_DOWN", "tag": "U-902", "severity": "HI", "pid": None,
                        "message": "down", "since": NOW}
        calls = []
        with mock.patch.object(store, "insert_alarm_journal", side_effect=lambda *a: calls.append(a)):
            sampler._journal_alarm_diff([still_active], NOW + 20)  # still active: no fresh raise
            self.assertEqual(calls, [])
            sampler._journal_alarm_diff([], NOW + 40)  # condition gone after restart: cleared once
        self.assertEqual([c[5] for c in calls], ["cleared"])


class HistoryRoutesTest(unittest.TestCase):
    """Query-param endpoints go through a real FastAPI app: calling handlers directly
    leaves `Query(...)` unresolved (rule: test the contract)."""

    def setUp(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "telemetry"
        self.dir.mkdir()
        routes._runs_cache.clear()
        routes._events_lru.clear()
        self.patches = [mock.patch.object(routes, "TELEMETRY_DIR", self.dir),
                       *_fresh_store(Path(self.tmp.name) / "historian")]
        for p in self.patches:
            p.start()
        app = FastAPI()
        app.include_router(routes.router)
        self.client = TestClient(app)

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()
        routes._runs_cache.clear()
        routes._events_lru.clear()

    def _write(self, name, lines):
        (self.dir / name).write_text("\n".join(lines) + "\n")

    def _page(self, run, cur, limit=2):
        return self.client.get("/api/history/events",
                               params={"run": run, "cursor": cur, "limit": limit}).json()

    def test_cursor_paging_no_duplicates_and_next_cursor_null_at_end(self):
        recs = [json.dumps({"kind": "enter", "ts": NOW + i, "pid": 5, "run": "batch-5-1"}) for i in range(5)]
        self._write("batch-5-1.jsonl", recs)
        b1 = self._page("batch-5-1", 0)
        self.assertEqual((len(b1["events"]), b1["total"], b1["next_cursor"]), (2, 5, 2))
        b2 = self._page("batch-5-1", b1["next_cursor"])
        self.assertEqual([e["ts"] for e in b2["events"]], [NOW + 2, NOW + 3])  # no repeat of 0/1
        b3 = self._page("batch-5-1", b2["next_cursor"])
        self.assertEqual((len(b3["events"]), b3["next_cursor"]), (1, None))  # nothing left: loop stops

    def test_cursor_paging_stable_with_equal_timestamps(self):
        recs = [json.dumps({"kind": "enter", "ts": NOW, "pid": 5, "run": "r", "call": i}) for i in range(4)]
        self._write("batch-5-3.jsonl", recs)
        b1 = self._page("batch-5-3", 0)
        b2 = self._page("batch-5-3", b1["next_cursor"])
        calls = [e["call"] for e in b1["events"]] + [e["call"] for e in b2["events"]]
        self.assertEqual(calls, [0, 1, 2, 3])  # stable sort: no item repeated or skipped
        self.assertIsNone(b2["next_cursor"])

    def test_corrupt_non_flow_and_non_finite_lines_are_skipped(self):
        lines = [json.dumps({"kind": "enter", "ts": NOW, "pid": 5, "run": "r"}),
                 "{not json", json.dumps({"kind": "config", "ts": NOW + 1, "pid": 5}),
                 json.dumps(["not", "a", "dict"]),
                 json.dumps({"kind": "exit", "ts": NOW + 2, "pid": 5, "dur_ms": float("nan")})]
        self._write("batch-5-2.jsonl", lines)
        body = self.client.get("/api/history/events", params={"run": "batch-5-2"}).json()
        self.assertEqual(len(body["events"]), 1)

    def test_runs_lists_aggregates_and_drops_cache_key_on_delete(self):
        lines = [json.dumps({"kind": "job", "ts": NOW, "pid": 5, "batch": "b1", "outcome": "ok"}),
                 json.dumps({"kind": "job", "ts": NOW + 1, "pid": 5, "batch": "b1", "outcome": "failed"})]
        self._write("batch-5-1.jsonl", lines)
        body = self.client.get("/api/history/runs").json()
        self.assertEqual((body[0]["run"], body[0]["jobs_ok"], body[0]["jobs_failed"]), ("batch-5-1", 1, 1))
        self.assertEqual(len(routes._runs_cache), 1)
        (self.dir / "batch-5-1.jsonl").unlink()  # rule H5: stale key dropped once its file is gone
        self.assertEqual(self.client.get("/api/history/runs").json(), [])
        self.assertEqual(len(routes._runs_cache), 0)

    def test_events_lru_evicts_oldest_run_beyond_max(self):
        for i, name in enumerate(["batch-5-1", "batch-5-2", "batch-5-3"]):
            self._write(f"{name}.jsonl", [json.dumps({"kind": "enter", "ts": NOW + i, "pid": 5, "run": name})])
            self.client.get("/api/history/events", params={"run": name})
        self.assertEqual(len(routes._events_lru), routes.EVENTS_LRU_MAX)
        self.assertNotIn("batch-5-1", routes._events_lru)  # oldest touched evicted first
        self.assertIn("batch-5-3", routes._events_lru)

    def test_path_traversal_in_run_name_is_neutralised(self):
        body = self.client.get("/api/history/events", params={"run": "../../etc/passwd"}).json()
        self.assertEqual(body["events"], [])

    def test_samples_validation_and_tag_filtering(self):
        resp = self.client.get("/api/history/samples", params={"tags": "gpu_temp_c", "from": 10, "to": 5})
        self.assertEqual(resp.status_code, 400)
        resp = self.client.get("/api/history/samples", params={"tags": "gpu_temp_c,not_a_tag,gpu_temp_c"})
        self.assertEqual((resp.status_code, set(resp.json()["series"])), (200, {"gpu_temp_c"}))  # M6
        too_many = ",".join(list(sampler.TAG_NAMES)[:routes.MAX_SAMPLE_TAGS + 1])
        self.assertEqual(self.client.get("/api/history/samples", params={"tags": too_many}).status_code, 422)

    def test_tags_endpoint_returns_catalogue(self):
        body = self.client.get("/api/history/tags").json()
        self.assertIn("gpu_temp_c", [t["tag"] for t in body])


if __name__ == "__main__":
    unittest.main(verbosity=2)
