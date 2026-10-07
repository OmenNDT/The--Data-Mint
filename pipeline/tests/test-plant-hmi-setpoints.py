"""Unit tests for Plant HMI phase 5: setpoint resolve/store/audit, collector config
records (M4: head-scan, pid-liveness prune), the reverse-control routes (H1 CSRF,
M3 clear, L7 poll-before-read), and the emitter's periodic re-emit.

Run: .venv/bin/python tests/test-plant-hmi-setpoints.py
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from plant_hmi import plant_setpoints as sp  # noqa: E402
from plant_hmi import plant_setpoint_store as store  # noqa: E402
from plant_hmi import plant_setpoint_routes as routes  # noqa: E402
from plant_hmi import plant_telemetry_emitter as tel  # noqa: E402
from plant_hmi.plant_telemetry_collector import TelemetryCollector  # noqa: E402

NOW = 1_000_000.0


class SetpointDirMixin:
    """Points every module-level store/audit/lock path at a fresh temp dir."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        self.patches = [
            mock.patch.object(store, "SETPOINTS_DIR", d),
            mock.patch.object(store, "STORE_PATH", d / "setpoints.json"),
            mock.patch.object(store, "AUDIT_PATH", d / "setpoints-audit.jsonl"),
            mock.patch.object(store, "LOCK_PATH", d / "setpoints.lock"),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()


class ResolveTest(SetpointDirMixin, unittest.TestCase):
    def test_env_beats_store_beats_recipe(self):
        self.assertEqual(sp.resolve("sampler_steps", 20, environ={}), (20, "recipe"))
        sp.set_setpoint("sampler_steps", 22, "127.0.0.1", "test")
        self.assertEqual(sp.resolve("sampler_steps", 20, environ={}), (22, "setpoint"))
        env = {"PLANT_SP_SAMPLER_STEPS": "18"}
        self.assertEqual(sp.resolve("sampler_steps", 20, environ=env), (18, "env"))

    def test_bad_env_value_falls_through_to_store_then_recipe(self):
        sp.set_setpoint("sampler_steps", 22, "127.0.0.1", "test")
        self.assertEqual(sp.resolve("sampler_steps", 20, environ={"PLANT_SP_SAMPLER_STEPS": "not-a-number"}), (22, "setpoint"))
        self.assertEqual(sp.resolve("sampler_steps", 20, environ={"PLANT_SP_SAMPLER_STEPS": "999"}), (22, "setpoint"))  # out of range

    def test_corrupt_store_falls_through_to_recipe(self):
        store.SETPOINTS_DIR.mkdir(parents=True, exist_ok=True)
        store.STORE_PATH.write_text("{not json", encoding="utf-8")
        self.assertEqual(sp.resolve("sampler_steps", 20, environ={}), (20, "recipe"))
        self.assertEqual(sp.read_store(), {})

    def test_store_value_out_of_range_or_wrong_type_falls_through(self):
        store.SETPOINTS_DIR.mkdir(parents=True, exist_ok=True)
        store.STORE_PATH.write_text(json.dumps({"sampler_steps": {"value": 999}}), encoding="utf-8")
        self.assertEqual(sp.resolve("sampler_steps", 20, environ={}), (20, "recipe"))
        store.STORE_PATH.write_text(json.dumps({"sampler_steps": {"value": 25.5}}), encoding="utf-8")
        self.assertEqual(sp.resolve("sampler_steps", 20, environ={}), (20, "recipe"))
        store.STORE_PATH.write_text(json.dumps({"sampler_steps": {"value": True}}), encoding="utf-8")
        self.assertEqual(sp.resolve("sampler_steps", 20, environ={}), (20, "recipe"))

    def test_unknown_key_returns_recipe_and_never_raises(self):
        self.assertEqual(sp.resolve("no_such_knob", 33, environ={}), (33, "recipe"))

    def test_missing_or_invalid_recipe_falls_back_to_registry_default(self):
        # rule L4: a missing/None/out-of-range recipe value must never resolve to None
        self.assertEqual(sp.resolve("sampler_steps", None, environ={}), (25, "recipe"))
        self.assertEqual(sp.resolve("sampler_steps", 999, environ={}), (25, "recipe"))
        self.assertEqual(sp.resolve("sampler_steps", "not-an-int", environ={}), (25, "recipe"))


class SetSetpointTest(SetpointDirMixin, unittest.TestCase):
    def test_bool_and_float_rejected(self):
        with self.assertRaises(ValueError):
            sp.set_setpoint("sampler_steps", True, "127.0.0.1", "r")
        with self.assertRaises(ValueError):
            sp.set_setpoint("sampler_steps", 20.5, "127.0.0.1", "r")

    def test_out_of_range_rejected(self):
        with self.assertRaises(ValueError):
            sp.set_setpoint("sampler_steps", 5, "127.0.0.1", "r")
        with self.assertRaises(ValueError):
            sp.set_setpoint("sampler_steps", 999, "127.0.0.1", "r")

    def test_unknown_key_rejected(self):
        with self.assertRaises(ValueError):
            sp.set_setpoint("no_such_knob", 20, "127.0.0.1", "r")

    def test_reason_too_long_rejected(self):
        with self.assertRaises(ValueError):
            sp.set_setpoint("sampler_steps", 20, "127.0.0.1", "x" * 201)

    def test_atomic_write_and_audit_line(self):
        sp.set_setpoint("sampler_steps", 22, "127.0.0.1", "first change")
        self.assertFalse(store.STORE_PATH.with_suffix(".json.tmp").exists())  # tmp file cleaned up
        stored = sp.read_store()["sampler_steps"]
        self.assertEqual(stored["value"], 22)
        self.assertEqual(stored["updated_by"], "127.0.0.1")

        sp.set_setpoint("sampler_steps", 30, "10.0.0.5", "second change")
        audit = sp.read_audit(10)
        self.assertEqual(len(audit), 2)
        self.assertEqual(audit[0]["old"], 22)   # newest first
        self.assertEqual(audit[0]["new"], 30)
        self.assertEqual(audit[1]["old"], None)  # first change had no prior value
        self.assertEqual(audit[1]["new"], 22)

    def test_read_audit_tolerates_corrupt_lines(self):
        store.SETPOINTS_DIR.mkdir(parents=True, exist_ok=True)
        store.AUDIT_PATH.write_text('{not json\n{"ts": 1, "key": "sampler_steps", "new": 5}\n', encoding="utf-8")
        self.assertEqual(sp.read_audit(10), [{"ts": 1, "key": "sampler_steps", "new": 5}])

    def test_audit_append_failure_does_not_undo_store_write(self):
        # rule L3: store write already succeeded; a broken audit file must only be logged.
        # Only the audit file's os.open is made to fail: the lock file uses the same call.
        sp.set_setpoint("sampler_steps", 22, "127.0.0.1", "ok")
        real_open = os.open

        def flaky_open(path, *args, **kwargs):
            if str(path) == str(store.AUDIT_PATH):
                raise OSError("disk full")
            return real_open(path, *args, **kwargs)

        with mock.patch("plant_hmi.plant_setpoint_store.os.open", side_effect=flaky_open):
            sp.set_setpoint("sampler_steps", 30, "127.0.0.1", "audit will fail")  # must not raise
        self.assertEqual(sp.read_store()["sampler_steps"]["value"], 30)

    def test_clear_setpoint_removes_entry_and_audits_new_null(self):
        sp.set_setpoint("sampler_steps", 22, "127.0.0.1", "set")
        sp.clear_setpoint("sampler_steps", "127.0.0.1", "revert")
        self.assertIsNone(sp.read_store().get("sampler_steps"))
        audit = sp.read_audit(1)[0]
        self.assertEqual((audit["old"], audit["new"], audit["reason"]), (22, None, "revert"))
        # cleared: resolve() falls through to recipe again
        self.assertEqual(sp.resolve("sampler_steps", 20, environ={}), (20, "recipe"))

    def test_clear_unknown_key_rejected(self):
        with self.assertRaises(ValueError):
            sp.clear_setpoint("no_such_knob", "127.0.0.1", "r")


class EmitterReemitTest(unittest.TestCase):
    """Rule M4: the emitter re-emits cached config records every N ok jobs, so PV
    survives a backend restart or config-record pruning without needing a new batch."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patches = [mock.patch.object(tel, "TELEMETRY_DIR", Path(self.tmp.name)),
                        mock.patch.object(tel, "_fd", None), mock.patch.object(tel, "_enabled", False),
                        mock.patch.object(tel, "_last_config", {}), mock.patch.object(tel, "_ok_count", 0)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        if tel._fd is not None:
            os.close(tel._fd)
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def records(self):
        files = list(Path(self.tmp.name).glob("batch-*.jsonl"))
        return [json.loads(x) for f in files for x in f.read_text().splitlines()]

    def test_reemits_after_n_ok_jobs_not_before(self):
        tel.enable("b1")
        tel.emit_config({"key": "sampler_steps", "value": 25, "source": "setpoint"})
        for _ in range(tel.CONFIG_REEMIT_EVERY - 1):
            tel.job_outcome("ok")
        configs = [r for r in self.records() if r.get("kind") == "config"]
        self.assertEqual(len(configs), 1)   # not yet due
        tel.job_outcome("ok")               # the Nth ok job
        configs = [r for r in self.records() if r.get("kind") == "config"]
        self.assertEqual(len(configs), 2)
        self.assertEqual(configs[-1]["value"], 25)

    def test_retry_and_failed_outcomes_do_not_count(self):
        tel.enable("b1")
        tel.emit_config({"key": "sampler_steps", "value": 25, "source": "setpoint"})
        for _ in range(tel.CONFIG_REEMIT_EVERY):
            tel.job_outcome("retry")
        configs = [r for r in self.records() if r.get("kind") == "config"]
        self.assertEqual(len(configs), 1)


class CollectorConfigTest(unittest.TestCase):
    """Config records (rule R5): outside the flow buffer, keyed by pid with pid-reuse guard."""

    def test_config_record_excluded_from_flow_buffer(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "batch-5-100.jsonl"
            rec = {"ts": NOW, "pid": 5, "run": "batch-5-100", "kind": "config",
                   "tag": "SP-601", "key": "sampler_steps", "value": 25, "source": "setpoint"}
            f.write_text(json.dumps(rec) + "\n")
            c = TelemetryCollector(Path(d))
            with mock.patch("plant_hmi.plant_telemetry_collector.time.time", return_value=NOW):
                c.poll()
            self.assertEqual(c.events(), [])
            self.assertEqual(c.config_for(5, NOW)["sampler_steps"]["value"], 25)

    def test_pid_reuse_guard_rejects_stale_record(self):
        c = TelemetryCollector(Path(tempfile.mkdtemp()))
        c._config[7] = {"sampler_steps": {"pid": 7, "key": "sampler_steps", "value": 15, "ts": NOW - 100}}
        self.assertEqual(c.config_for(7, NOW), {})              # new process start after the old record
        self.assertEqual(c.config_for(7, NOW - 100)["sampler_steps"]["value"], 15)  # same-run start: accepted

    def test_unknown_pid_returns_empty(self):
        c = TelemetryCollector(Path(tempfile.mkdtemp()))
        self.assertEqual(c.config_for(999, NOW), {})

    def test_keeps_only_newest_record_per_key(self):
        c = TelemetryCollector(Path(tempfile.mkdtemp()))
        c._ingest_config({"pid": 3, "key": "sampler_steps", "value": 10, "ts": NOW - 5})
        c._ingest_config({"pid": 3, "key": "sampler_steps", "value": 20, "ts": NOW})
        c._ingest_config({"pid": 3, "key": "sampler_steps", "value": 5, "ts": NOW - 10})  # older: ignored
        self.assertEqual(c.config_for(3, 0)["sampler_steps"]["value"], 20)

    def test_head_scan_finds_config_record_a_big_tail_read_would_skip(self):
        # rule M4: config sits at the start; a file bigger than FIRST_READ_TAIL only
        # tails its last bytes for flow records, so the head must be scanned separately.
        # Uses this test process's own pid so the liveness-based prune (also exercised
        # by the same poll(), since `_last_prune` starts at 0) does not remove it.
        pid = os.getpid()
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / f"batch-{pid}-200.jsonl"
            config_rec = {"ts": NOW - 500, "pid": pid, "kind": "config", "key": "sampler_steps",
                          "value": 18, "source": "env"}
            padding = "\n".join(json.dumps({"ts": NOW, "pid": pid, "run": "x", "kind": "job",
                                             "outcome": "ok"}) for _ in range(5)) + "\n"
            f.write_text(json.dumps(config_rec) + "\n" + padding)
            c = TelemetryCollector(Path(d))
            with mock.patch("plant_hmi.plant_telemetry_collector.FIRST_READ_TAIL", 10):
                with mock.patch("plant_hmi.plant_telemetry_collector.time.time", return_value=NOW):
                    c.poll()
            self.assertEqual(c.config_for(pid, NOW - 500)["sampler_steps"]["value"], 18)

    def test_prune_config_keeps_alive_pid_drops_dead_pid(self):
        c = TelemetryCollector(Path(tempfile.mkdtemp()))
        c._config[os.getpid()] = {"sampler_steps": {"value": 1, "ts": 0}}   # this test process: alive
        dead_pid = 999999   # astronomically unlikely to be a live pid
        c._config[dead_pid] = {"sampler_steps": {"value": 2, "ts": 0}}
        c._prune_old_files(NOW)
        self.assertIn(os.getpid(), c._config)
        self.assertNotIn(dead_pid, c._config)


class RoutesTest(SetpointDirMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.app = FastAPI()
        self.app.include_router(routes.router)
        self.client = TestClient(self.app)

    def test_list_setpoints_no_live_process_pv_null(self):
        with mock.patch.object(routes.host, "find_batch_processes", return_value=[]), \
             mock.patch.object(routes.collector, "poll"), \
             mock.patch.object(routes.production, "load_batch_config", return_value={"sampler": {"steps": 20}}):
            res = self.client.get("/api/control/setpoints")
        self.assertEqual(res.status_code, 200)
        row = res.json()[0]
        self.assertEqual(row["key"], "sampler_steps")
        self.assertEqual(row["recipe"], 20)
        self.assertIsNone(row["pv"])
        self.assertIsNone(row["pv_source"])

    def test_list_setpoints_polls_collector_before_reading_pv(self):
        # rule L7: PV must reflect a fresh read, not whatever a previous request polled
        with mock.patch.object(routes.host, "find_batch_processes", return_value=[]), \
             mock.patch.object(routes.production, "load_batch_config", return_value={}), \
             mock.patch.object(routes.collector, "poll") as poll_mock:
            self.client.get("/api/control/setpoints")
        poll_mock.assert_called_once()

    def test_list_setpoints_pv_from_live_process_config_record(self):
        live = {"pid": 42, "start_ts": NOW, "config_path": None, "pilot": False}
        with mock.patch.object(routes.host, "find_batch_processes", return_value=[live]), \
             mock.patch.object(routes.collector, "poll"), \
             mock.patch.object(routes.production, "load_batch_config", return_value={"sampler": {"steps": 20}}), \
             mock.patch.object(routes.collector, "config_for",
                                return_value={"sampler_steps": {"value": 25, "source": "setpoint"}}):
            res = self.client.get("/api/control/setpoints")
        row = res.json()[0]
        self.assertEqual(row["pv"], 25)
        self.assertEqual(row["pv_pid"], 42)
        self.assertEqual(row["pv_source"], "REMOTE")

    def test_put_without_header_is_403(self):
        res = self.client.put("/api/control/setpoints/sampler_steps", json={"value": 20, "reason": "x"})
        self.assertEqual(res.status_code, 403)
        self.assertEqual(sp.read_store(), {})

    def test_put_out_of_range_is_422(self):
        res = self.client.put("/api/control/setpoints/sampler_steps", json={"value": 999, "reason": "x"},
                               headers={"X-Plant-HMI": "1"})
        self.assertEqual(res.status_code, 422)

    def test_put_float_value_rejected_by_pydantic_strict_int(self):
        res = self.client.put("/api/control/setpoints/sampler_steps", json={"value": 20.5, "reason": "x"},
                               headers={"X-Plant-HMI": "1"})
        self.assertEqual(res.status_code, 422)

    def test_put_success_writes_store_and_audit(self):
        res = self.client.put("/api/control/setpoints/sampler_steps", json={"value": 25, "reason": "thử knob"},
                               headers={"X-Plant-HMI": "1"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["value"], 25)
        self.assertEqual(sp.read_store()["sampler_steps"]["value"], 25)

        audit_res = self.client.get("/api/control/audit?limit=5")
        self.assertEqual(audit_res.status_code, 200)
        self.assertEqual(audit_res.json()[0]["new"], 25)
        self.assertEqual(audit_res.json()[0]["reason"], "thử knob")

    def test_put_unknown_key_is_404(self):
        res = self.client.put("/api/control/setpoints/not_a_knob", json={"value": 1, "reason": "x"},
                               headers={"X-Plant-HMI": "1"})
        self.assertEqual(res.status_code, 404)

    def test_put_foreign_origin_is_403(self):
        res = self.client.put("/api/control/setpoints/sampler_steps", json={"value": 20, "reason": "x"},
                               headers={"X-Plant-HMI": "1", "Origin": "http://evil.example"})
        self.assertEqual(res.status_code, 403)
        self.assertEqual(sp.read_store(), {})

    def test_put_same_origin_is_ok(self):
        # starlette's TestClient always sends Host: testserver
        res = self.client.put("/api/control/setpoints/sampler_steps", json={"value": 20, "reason": "x"},
                               headers={"X-Plant-HMI": "1", "Origin": "http://testserver"})
        self.assertEqual(res.status_code, 200)

    def test_put_no_origin_header_is_ok(self):
        res = self.client.put("/api/control/setpoints/sampler_steps", json={"value": 20, "reason": "x"},
                               headers={"X-Plant-HMI": "1"})
        self.assertEqual(res.status_code, 200)

    def test_put_cross_site_sec_fetch_site_is_403(self):
        res = self.client.put("/api/control/setpoints/sampler_steps", json={"value": 20, "reason": "x"},
                               headers={"X-Plant-HMI": "1", "Sec-Fetch-Site": "cross-site"})
        self.assertEqual(res.status_code, 403)

    def test_delete_clears_setpoint_and_audits_new_null(self):
        self.client.put("/api/control/setpoints/sampler_steps", json={"value": 25, "reason": "set"},
                         headers={"X-Plant-HMI": "1"})
        res = self.client.request("DELETE", "/api/control/setpoints/sampler_steps", json={"reason": "về recipe"},
                                   headers={"X-Plant-HMI": "1"})
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(sp.read_store().get("sampler_steps"))
        audit = self.client.get("/api/control/audit?limit=1").json()[0]
        self.assertIsNone(audit["new"])

    def test_delete_without_header_is_403(self):
        res = self.client.request("DELETE", "/api/control/setpoints/sampler_steps", json={"reason": "x"})
        self.assertEqual(res.status_code, 403)

    def test_delete_foreign_origin_is_403(self):
        res = self.client.request("DELETE", "/api/control/setpoints/sampler_steps", json={"reason": "x"},
                                   headers={"X-Plant-HMI": "1", "Origin": "http://evil.example"})
        self.assertEqual(res.status_code, 403)


if __name__ == "__main__":
    unittest.main(verbosity=2)
