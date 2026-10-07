"""Unit tests for Plant HMI phase 2: emitter, collector, flow metrics, telemetry alarms.

Run: .venv/bin/python tests/test-plant-hmi-telemetry.py
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from plant_hmi import plant_telemetry_emitter as tel  # noqa: E402
from plant_hmi.plant_alarm_rules import derive_alarms, unknown_codes  # noqa: E402
from plant_hmi.plant_comfyui_readers import is_local_address  # noqa: E402
from plant_hmi.plant_flow_metrics import compute_flows  # noqa: E402
from plant_hmi.plant_telemetry_collector import TelemetryCollector  # noqa: E402

NOW = 1_000_000.0


class EmitterTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patches = [mock.patch.object(tel, "TELEMETRY_DIR", Path(self.tmp.name)),
                        mock.patch.object(tel, "_fd", None), mock.patch.object(tel, "_enabled", False)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        if tel._fd is not None:
            os.close(tel._fd)
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def lines(self):
        files = list(Path(self.tmp.name).glob("batch-*.jsonl"))
        return [json.loads(x) for f in files for x in f.read_text().splitlines()]

    def test_result_and_exception_pass_through(self):
        tel.enable("b1")
        tel.set_job(7, "crack")
        self.assertEqual(tel.instrument(lambda x: x * 2, "P-601", "infer")(21), 42)

        def boom():
            raise KeyboardInterrupt  # BaseException must pass through too
        with self.assertRaises(KeyboardInterrupt):
            tel.instrument(boom, "P-601", "infer")()
        recs = self.lines()
        self.assertEqual([r["kind"] for r in recs], ["enter", "exit", "enter", "exit"])
        self.assertEqual(recs[1]["ok"], True)
        self.assertEqual((recs[3]["ok"], recs[3]["err"]), (False, "KeyboardInterrupt"))
        self.assertEqual((recs[0]["job"], recs[0]["defect"], recs[0]["batch"]), (7, "crack", "b1"))
        self.assertTrue(recs[0]["run"].startswith(f"batch-{os.getpid()}-"))

    def test_disabled_process_writes_nothing_and_kill_switch_returns_original(self):
        fn = tel.instrument(lambda: 1, "R-201", "mask")
        self.assertEqual(fn(), 1)
        self.assertEqual(self.lines(), [])
        with mock.patch.dict(os.environ, {"PLANT_TELEMETRY": "0"}):
            original = len
            self.assertIs(tel.instrument(original, "R-201", "mask"), original)
            self.assertFalse(tel.enable("b"))

    def test_unwritable_dir_never_fails_the_job(self):
        with mock.patch.object(tel, "TELEMETRY_DIR", Path("/proc/forbidden/telemetry")):
            tel.enable("b")
            self.assertEqual(tel.instrument(lambda: "ok", "P-601", "infer")(), "ok")
            tel.job_outcome("ok")


class CollectorTest(unittest.TestCase):
    def test_partial_lines_corrupt_lines_and_truncation(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "batch-5-100.jsonl"
            rec = {"ts": NOW, "pid": 5, "run": "batch-5-100", "kind": "job", "outcome": "ok", "job": 1}
            full, half = json.dumps(rec), json.dumps({**rec, "job": 2})
            f.write_text(full + "\n{corrupt\n" + json.dumps({**rec, "kind": "config"}) + "\n" + half[:10])
            c = TelemetryCollector(Path(d))
            with mock.patch("plant_hmi.plant_telemetry_collector.time.time", return_value=NOW):
                c.poll()
                self.assertEqual(len(c.events()), 1)          # config dropped, partial held
                with open(f, "a") as fh:
                    fh.write(half[10:] + "\n")
                c._last_poll = 0
                c.poll()
                self.assertEqual([e["job"] for e in c.events()], [1, 2])
                self.assertEqual(c.run_for(5, NOW - 1)["ok"], 2)
                self.assertIsNone(c.run_for(5, NOW + 100))     # recycled pid: not this run
                f.write_text(full + "\n")                      # truncated / rewritten
                c._last_poll = 0
                c.poll()
                self.assertEqual(len(c.events()), 3)


    def test_events_since_orders_and_flags_truncation(self):
        c = TelemetryCollector(Path("/nonexistent"))
        for ts in (NOW + 3, NOW + 1, NOW + 2):  # interleaved files: not ts-ordered
            c._buffer.append({"ts": ts, "pid": 1, "kind": "job"})
        got = c.events_since(NOW, limit=2)
        self.assertEqual([e["ts"] for e in got["events"]], [NOW + 2, NOW + 3])
        self.assertTrue(got["truncated"])
        self.assertEqual(got["cursor"], NOW + 3)
        self.assertEqual(c.events_since(NOW + 3)["cursor"], NOW + 3)

    def test_idle_file_skipped_on_first_sight_and_tail_marks_partial(self):
        with tempfile.TemporaryDirectory() as d:
            old = Path(d) / "batch-1-1.jsonl"
            old.write_text(json.dumps({"ts": 1.0, "pid": 1, "run": "r1", "kind": "job", "outcome": "ok"}) + "\n")
            os.utime(old, (1, 1))
            c = TelemetryCollector(Path(d))
            c.poll()
            self.assertEqual(c.runs, {})
            big = Path(d) / "batch-2-2.jsonl"
            rec = json.dumps({"ts": __import__("time").time(), "pid": 2, "run": "r2", "kind": "job",
                              "outcome": "failed"})
            with mock.patch("plant_hmi.plant_telemetry_collector.FIRST_READ_TAIL", len(rec) * 2 + 1):
                big.write_text((rec + "\n") * 5)
                c._last_poll = 0
                c.poll()
            self.assertTrue(c.runs["r2"]["partial"])
            self.assertLess(c.runs["r2"]["failed"], 5)


def ev(kind, call, ts, pid=5, tag="P-601", **kw):
    return {"kind": kind, "call": call, "ts": ts, "pid": pid, "tag": tag, **kw}


class FlowMetricsTest(unittest.TestCase):
    def test_running_excludes_dead_and_recycled_pids(self):
        events = [ev("enter", "a", NOW - 5, call_kind="infer"),
                  ev("enter", "b", NOW - 5, pid=9, call_kind="infer"),        # dead pid
                  ev("enter", "c", NOW - 500, pid=6, call_kind="infer")]      # before pid 6 started
        flows = compute_flows(events, {5: NOW - 100, 6: NOW - 50}, NOW)
        self.assertEqual([r["call"] for r in flows["running"]], ["a"])
        self.assertEqual(flows["stages"]["P-601"]["running"], 1)

    def test_p50_errors_and_jobs(self):
        events = [ev("exit", "a", NOW - 10, ok=True, dur_ms=4000, call_kind="infer"),
                  ev("exit", "b", NOW - 20, ok=True, dur_ms=6000, call_kind="infer"),
                  ev("exit", "c", NOW - 30, ok=False, err="Timeout", call_kind="infer"),
                  {"kind": "job", "ts": NOW - 30, "pid": 5, "outcome": "ok"},
                  {"kind": "job", "ts": NOW - 300, "pid": 5, "outcome": "retry"},
                  {"kind": "job", "ts": NOW - 2000, "pid": 5, "outcome": "failed"}]
        flows = compute_flows(events, {5: NOW - 5000}, NOW)
        self.assertEqual(flows["stages"]["P-601"]["p50_ms"]["infer"], 5000)
        self.assertEqual(flows["stages"]["P-601"]["errors_5m"], 1)
        self.assertEqual(flows["jobs"], {"ok_1m": 1, "ok_10m": 1, "retry_15m": 1, "failed_15m": 0})
        self.assertTrue(flows["has_telemetry"])


def state(**kw):
    base = {"now": NOW, "batches": [], "comfy": {"ok": True}, "gpu": {"temp_c": 50},
            "host": {"mem_avail_pct": 40, "swap_pages_s": 0}, "idle_checkpoint": {}, "flows": {}}
    base.update(kw)
    return base


class FlowOwnershipTest(unittest.TestCase):
    def test_dead_run_errors_do_not_count_for_the_next_run(self):
        events = [{"kind": "job", "ts": NOW - 60, "pid": 9, "outcome": "failed"},       # killed run
                  ev("exit", "x", NOW - 60, pid=9, ok=False, err="Timeout", call_kind="infer")]
        flows = compute_flows(events, {5: NOW - 30}, NOW)
        self.assertEqual(flows["jobs"]["failed_15m"], 0)
        self.assertEqual(flows["stages"], {})

    def test_wedged_counts_from_end_of_thermal_hold(self):
        events = [ev("enter", "h", NOW - 1500, tag="U-901", call_kind="thermal_hold"),
                  ev("exit", "h", NOW - 30, tag="U-901", call_kind="thermal_hold", ok=True, dur_ms=1)]
        flows = compute_flows(events, {5: NOW - 3000}, NOW)
        self.assertEqual(flows["last_thermal_exit_ts"], NOW - 30)
        b = [{"pid": 5, "start_ts": NOW - 3000, "newest_image_ts": NOW - 1600}]
        self.assertEqual(derive_alarms(state(batches=b, flows=flows)), [])


class TelemetryAlarmTest(unittest.TestCase):
    def test_comfy_down_names_the_cause(self):
        down = derive_alarms(state(comfy={"ok": False, "url": "u", "procs": []}))
        self.assertIn("chưa chạy", down[0]["message"])
        alive = derive_alarms(state(comfy={"ok": False, "url": "u",
                                           "procs": [{"pid": 3, "listen": "10.0.0.1", "port": "8188"}]}))
        self.assertIn("pid 3", alive[0]["message"])

    def test_config_host_not_local(self):
        codes = [a["code"] for a in derive_alarms(state(comfy={"ok": True, "host": "10.1.2.3",
                                                               "host_local": False}))]
        self.assertEqual(codes, ["COMFY_HOST_NOT_LOCAL"])
        self.assertIn("COMFY_HOST_NOT_LOCAL", unknown_codes(state(comfy={"ok": True})))

    def test_thermal_hold_suppresses_wedged(self):
        b = [{"pid": 7, "start_ts": NOW - 7200, "newest_image_ts": None}]
        flows = {"thermal_hold": True, "has_telemetry": True, "jobs": {}}
        self.assertEqual([a["code"] for a in derive_alarms(state(batches=b, flows=flows))], ["THERMAL_HOLD"])

    def test_job_errors_needs_telemetry_and_rate(self):
        flows = {"has_telemetry": True, "jobs": {"retry_15m": 2, "failed_15m": 1}}
        alarms = derive_alarms(state(flows=flows))
        self.assertEqual([(a["code"], a["severity"]) for a in alarms], [("JOB_ERRORS", "HI")])
        self.assertEqual(derive_alarms(state(flows={**flows, "has_telemetry": False})), [])

    def test_comfy_stalled_only_when_connected_and_executing(self):
        prog = {"connected": True, "phase": "executing", "last_event_ts": NOW - 150, "node_title": "KSampler",
                "node_class": "KSampler", "step_seen": True}
        self.assertEqual([(a["code"], a["severity"]) for a in derive_alarms(state(comfy_progress=prog))],
                         [("COMFY_STALLED", "HI")])
        loading = {**prog, "node_class": "LoraLoader", "step_seen": False}
        self.assertEqual([a["severity"] for a in derive_alarms(state(comfy_progress=loading))], ["LO"])
        self.assertEqual(derive_alarms(state(comfy_progress={**prog, "last_event_ts": NOW - 90})), [])
        self.assertEqual(derive_alarms(state(comfy_progress={**prog, "phase": "busy_foreign"})), [])
        self.assertEqual(derive_alarms(state(comfy_progress={**prog, "last_event_ts": NOW - 5})), [])
        self.assertEqual(derive_alarms(state(comfy_progress={**prog, "phase": "idle"})), [])
        self.assertIn("COMFY_STALLED", unknown_codes(state(comfy_progress={"connected": False})))

    def test_is_local_address(self):
        self.assertTrue(is_local_address("127.0.0.1"))
        self.assertTrue(is_local_address("localhost"))
        self.assertFalse(is_local_address("192.0.2.123"))   # TEST-NET-1, never assigned
        self.assertIsNone(is_local_address("some-hostname"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
