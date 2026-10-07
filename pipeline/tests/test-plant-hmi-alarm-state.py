"""Unit tests for Plant HMI phase 6B: alarm ack/shelve store (`plant_alarm_state.py`),
the per-tick decision/persist engine (`plant_alarm_annotate.py`) and the HTTP routes
(`plant_alarm_state_routes.py`): H1 CSRF guard, C2 lock race, H5 point-keyed shelve,
M2 unknown-key validation, M3 write-avoidance, Low ack-all-skip/expiry-journal.

Run: .venv/bin/python tests/test-plant-hmi-alarm-state.py
"""

import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from plant_hmi import plant_alarm_annotate as annotate  # noqa: E402
from plant_hmi import plant_alarm_state as state  # noqa: E402
from plant_hmi import plant_alarm_state_routes as routes  # noqa: E402

NOW = 1_000_000.0


def _cond(code="COMFY_DOWN", tag="U-902", severity="HI", pid=None, since=NOW, message="down"):
    return {"code": code, "tag": tag, "severity": severity, "pid": pid, "since": since, "message": message}


class AlarmStateDirMixin:
    """Points every module-level store/lock path at a fresh temp dir (rule R6 in tests)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        self.patches = [
            mock.patch.object(state, "ALARM_STATE_DIR", d),
            mock.patch.object(state, "STORE_PATH", d / "alarm-state.json"),
            mock.patch.object(state, "LOCK_PATH", d / "alarm-state.lock"),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()


class StoreTest(AlarmStateDirMixin, unittest.TestCase):
    def test_missing_and_corrupt_store_fall_back_to_empty(self):
        empty = {"acks": {}, "shelves": {}, "last_seen": {}, "active_points": {}}
        self.assertEqual(state.read_store(), empty)
        state.STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        state.STORE_PATH.write_text("{not json", encoding="utf-8")
        self.assertEqual(state.read_store(), empty)

    def test_ack_unknown_key_rejected(self):
        with self.assertRaises(state.UnknownAlarmKey):
            state.ack("no-such-key", "127.0.0.1", "", now=NOW)

    def test_ack_known_occurrence_persists_and_is_reflected_in_annotate(self):
        annotate.annotate_from_store([_cond()], NOW)  # seeds last_seen for the occurrence
        key = state.occurrence_key("COMFY_DOWN", "U-902", None, NOW)
        state.ack(key, "127.0.0.1", "nháy máy", now=NOW + 1)
        result = annotate.annotate_from_store([_cond()], NOW + 2)
        self.assertTrue(result["alarms"][0]["acked"])
        self.assertEqual(result["alarms"][0]["acked_at"], NOW + 1)

    def test_shelve_unknown_point_rejected(self):
        with self.assertRaises(state.UnknownAlarmKey):
            state.shelve("GPU_HOT|U-901|None", 15, "who", "chưa có báo động", now=NOW)

    def test_shelve_rejects_bad_minutes_and_missing_reason(self):
        annotate.annotate_from_store([_cond(code="GPU_HOT", tag="U-901")], NOW)
        pkey = state.point_key("GPU_HOT", "U-901", None)
        with self.assertRaises(ValueError):
            state.shelve(pkey, 99, "who", "vì nóng quá", now=NOW)
        with self.assertRaises(ValueError):
            state.shelve(pkey, 15, "who", "   ", now=NOW)

    def test_unshelve_unknown_rejected(self):
        with self.assertRaises(state.UnknownAlarmKey):
            state.unshelve("GPU_HOT|U-901|None")


class AnnotateTest(AlarmStateDirMixin, unittest.TestCase):
    def test_shelve_survives_clear_and_reraise_point_keyed(self):
        """H5: a chattering point stays shelved across its own clear/re-raise cycles
        (each cycle gets a new occurrence `since`, but the shelve key never includes it)."""
        annotate.annotate_from_store([_cond(code="GPU_HOT", tag="U-901", since=NOW)], NOW)
        pkey = state.point_key("GPU_HOT", "U-901", None)
        state.shelve(pkey, 60, "127.0.0.1", "chờ bảo trì", now=NOW)
        r1 = annotate.annotate_from_store([_cond(code="GPU_HOT", tag="U-901", since=NOW)], NOW + 5)
        self.assertEqual(r1["alarms"], [])
        self.assertEqual(len(r1["shelved"]), 1)
        # condition clears then re-raises (new `since`) while still inside the shelve window
        r2 = annotate.annotate_from_store([_cond(code="GPU_HOT", tag="U-901", since=NOW + 50)], NOW + 60)
        self.assertEqual(r2["alarms"], [])
        self.assertEqual(len(r2["shelved"]), 1)
        self.assertEqual(r2["cleared_unacked"], [])  # H5: never demands an ack while shelved

    def test_shelve_auto_expires_and_journals_unshelved_by_expiry(self):
        annotate.annotate_from_store([_cond(code="GPU_HOT", tag="U-901")], NOW)
        pkey = state.point_key("GPU_HOT", "U-901", None)
        state.shelve(pkey, 15, "127.0.0.1", "chờ bảo trì", now=NOW)
        with mock.patch("plant_hmi.plant_alarm_annotate.historian.insert_alarm_journal") as journal:
            result = annotate.annotate_from_store(
                [_cond(code="GPU_HOT", tag="U-901")], NOW + 15 * 60 + 1)
        self.assertEqual(len(result["alarms"]), 1)  # window elapsed: back to unshelved
        self.assertEqual(result["shelved"], [])
        self.assertEqual(journal.call_args.args[5], "unshelved")
        self.assertIn("expiry", journal.call_args.args[6])

    def test_cleared_unacked_remembers_then_forgets_after_24h(self):
        r1 = annotate.annotate_from_store([_cond()], NOW)
        self.assertEqual(len(r1["alarms"]), 1)
        self.assertEqual(r1["cleared_unacked"], [])
        r2 = annotate.annotate_from_store([], NOW + 5)
        self.assertEqual(len(r2["cleared_unacked"]), 1)
        self.assertEqual(r2["cleared_unacked"][0]["code"], "COMFY_DOWN")
        r3 = annotate.annotate_from_store([], NOW + 5 + 3600 * 23)
        self.assertEqual(len(r3["cleared_unacked"]), 1)
        r4 = annotate.annotate_from_store([], NOW + 5 + 3600 * 25)
        self.assertEqual(r4["cleared_unacked"], [])

    def test_acking_a_cleared_unacked_alarm_removes_it(self):
        annotate.annotate_from_store([_cond()], NOW)
        annotate.annotate_from_store([], NOW + 5)
        key = state.occurrence_key("COMFY_DOWN", "U-902", None, NOW)
        state.ack(key, "127.0.0.1", "", now=NOW + 6)
        result = annotate.annotate_from_store([], NOW + 7)
        self.assertEqual(result["cleared_unacked"], [])

    def test_reraise_after_ack_is_a_new_unacked_occurrence(self):
        annotate.annotate_from_store([_cond(since=NOW)], NOW)
        key1 = state.occurrence_key("COMFY_DOWN", "U-902", None, NOW)
        state.ack(key1, "127.0.0.1", "", now=NOW + 1)
        r1 = annotate.annotate_from_store([_cond(since=NOW)], NOW + 2)
        self.assertTrue(r1["alarms"][0]["acked"])
        r2 = annotate.annotate_from_store([_cond(since=NOW + 100)], NOW + 101)
        self.assertFalse(r2["alarms"][0]["acked"])
        self.assertNotEqual(r2["alarms"][0]["key"], key1)

    def test_ack_all_acks_known_keys_and_skips_already_acked(self):
        annotate.annotate_from_store([_cond(), _cond(code="GPU_HOT", tag="U-901")], NOW)
        k1 = state.occurrence_key("COMFY_DOWN", "U-902", None, NOW)
        k2 = state.occurrence_key("GPU_HOT", "U-901", None, NOW)
        state.ack(k1, "127.0.0.1", "đã biết", now=NOW + 1)
        acked = state.ack_all([k1, k2, "unknown|key|None|0"], "127.0.0.1", "ca trực", now=NOW + 2)
        self.assertEqual(acked, [k2])  # k1 already acked (skipped), unknown key skipped
        self.assertEqual(state.read_store()["acks"][k1]["acked_at"], NOW + 1)  # untouched

    def test_no_disk_write_while_the_active_set_is_unchanged(self):
        """M3: a steady-state poll (same alarm still active, tick to tick) must not
        rewrite the store - only a genuine set change (new/cleared/acked/shelved) does."""
        annotate.annotate_from_store([_cond()], NOW)  # first tick: new key -> one write
        with mock.patch.object(state, "write_store") as write_mock:
            for i in range(1, 5):
                annotate.annotate_from_store([_cond()], NOW + i)
            write_mock.assert_not_called()

    def test_concurrent_ack_survives_overlapping_annotate_ticks(self):
        """C2 regression: annotate_from_store and ack() share one lock, so a poll can
        never rewrite the store from a copy that predates a concurrent ack."""
        annotate.annotate_from_store([_cond()], NOW)
        key = state.occurrence_key("COMFY_DOWN", "U-902", None, NOW)
        stop = threading.Event()

        def poll_loop():
            t = NOW
            while not stop.is_set():
                t += 0.001
                annotate.annotate_from_store([_cond()], t)

        poller = threading.Thread(target=poll_loop)
        poller.start()
        try:
            for _ in range(20):  # ack racing against many overlapping poll writes
                state.ack(key, "127.0.0.1", "", now=NOW + 1)
        finally:
            stop.set()
            poller.join(timeout=5)
        self.assertIn(key, state.read_store()["acks"])


class RoutesTest(AlarmStateDirMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        app = FastAPI()
        app.include_router(routes.router, prefix="/plant-hmi")
        self.client = TestClient(app)
        self.journal_calls = []
        self.journal_patch = mock.patch(
            "plant_hmi.plant_alarm_state_routes.historian.insert_alarm_journal",
            side_effect=lambda *a: self.journal_calls.append(a))
        self.journal_patch.start()

    def tearDown(self):
        self.journal_patch.stop()
        super().tearDown()

    def _headers(self):
        return {"X-Plant-HMI": "1"}

    def test_ack_requires_csrf_header(self):
        res = self.client.post("/plant-hmi/api/alarms/ack", json={"key": "x|y|None|1"})
        self.assertEqual(res.status_code, 403)

    def test_ack_unknown_key_returns_404(self):
        res = self.client.post("/plant-hmi/api/alarms/ack", json={"key": "no|such|key|0"},
                                headers=self._headers())
        self.assertEqual(res.status_code, 404)

    def test_ack_then_state_reflects_it_and_journals(self):
        annotate.annotate_from_store([_cond()], NOW)
        key = state.occurrence_key("COMFY_DOWN", "U-902", None, NOW)
        res = self.client.post("/plant-hmi/api/alarms/ack", json={"key": key, "reason": "đã biết"},
                                headers=self._headers())
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["key"], key)
        self.assertIn(key, self.client.get("/plant-hmi/api/alarms/state").json()["acks"])
        self.assertEqual(self.journal_calls[-1][5], "acked")

    def test_shelve_bad_minutes_returns_422(self):
        annotate.annotate_from_store([_cond(code="GPU_HOT", tag="U-901")], NOW)
        pkey = state.point_key("GPU_HOT", "U-901", None)
        res = self.client.post("/plant-hmi/api/alarms/shelve",
                                json={"key": pkey, "minutes": 30, "reason": "bảo trì"},
                                headers=self._headers())
        self.assertEqual(res.status_code, 422)

    def test_shelve_unknown_point_returns_404(self):
        res = self.client.post("/plant-hmi/api/alarms/shelve",
                                json={"key": "NOPE|X|None", "minutes": 15, "reason": "r"},
                                headers=self._headers())
        self.assertEqual(res.status_code, 404)

    def test_shelve_then_unshelve_round_trip(self):
        annotate.annotate_from_store([_cond(code="GPU_HOT", tag="U-901")], NOW)
        pkey = state.point_key("GPU_HOT", "U-901", None)
        res = self.client.post("/plant-hmi/api/alarms/shelve",
                                json={"key": pkey, "minutes": 60, "reason": "bảo trì định kỳ"},
                                headers=self._headers())
        self.assertEqual(res.status_code, 200)
        self.assertIn(pkey, self.client.get("/plant-hmi/api/alarms/state").json()["shelves"])
        res = self.client.post("/plant-hmi/api/alarms/unshelve", json={"key": pkey}, headers=self._headers())
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["unshelved"])
        self.assertNotIn(pkey, self.client.get("/plant-hmi/api/alarms/state").json()["shelves"])
        self.assertEqual([c[5] for c in self.journal_calls], ["shelved", "unshelved"])

    def test_unshelve_unknown_returns_404(self):
        res = self.client.post("/plant-hmi/api/alarms/unshelve", json={"key": "NOPE|X|None"},
                                headers=self._headers())
        self.assertEqual(res.status_code, 404)

    def test_ack_all_acks_every_known_key(self):
        annotate.annotate_from_store([_cond(), _cond(code="GPU_HOT", tag="U-901")], NOW)
        keys = [state.occurrence_key("COMFY_DOWN", "U-902", None, NOW),
                state.occurrence_key("GPU_HOT", "U-901", None, NOW)]
        res = self.client.post("/plant-hmi/api/alarms/ack-all", json={"keys": keys, "reason": "ca trực"},
                                headers=self._headers())
        self.assertEqual(res.status_code, 200)
        self.assertEqual(set(res.json()["acked"]), set(keys))
        self.assertEqual(set(self.client.get("/plant-hmi/api/alarms/state").json()["acks"]), set(keys))


if __name__ == "__main__":
    unittest.main()
