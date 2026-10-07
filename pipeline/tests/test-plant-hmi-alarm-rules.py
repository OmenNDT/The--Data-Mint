"""Unit tests for Plant HMI pure logic: alarm rules, on-delay, argv parsing, run target.

Run: .venv/bin/python tests/test-plant-hmi-alarm-rules.py
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from plant_hmi.plant_alarm_rules import THRESHOLDS, AlarmOnDelay, derive_alarms, unknown_codes  # noqa: E402
from plant_hmi.plant_host_readers import _parse_batch_argv  # noqa: E402
from plant_hmi.plant_production_readers import load_batch_config, run_target, section  # noqa: E402

NOW = 1_000_000.0


def state(**kw):
    base = {"now": NOW, "batches": [], "comfy": {"ok": True, "url": "http://c:8188"},
            "gpu": {"temp_c": 50}, "host": {"mem_avail_pct": 40, "swap_pages_s": 0},
            "idle_checkpoint": {}}
    base.update(kw)
    return base


def codes(alarms):
    return sorted((a["code"], a["severity"]) for a in alarms)


class DeriveAlarmsTest(unittest.TestCase):
    def test_healthy_plant_has_no_alarm(self):
        self.assertEqual(derive_alarms(state()), [])

    def test_unknown_readings_never_alarm(self):
        s = state(comfy={"ok": None}, gpu={"ok": None}, host={})
        self.assertEqual(derive_alarms(s), [])

    def test_comfy_down_is_lo_when_idle_and_hi_with_live_batch(self):
        down = {"ok": False, "url": "http://c:8188"}
        self.assertEqual(codes(derive_alarms(state(comfy=down))), [("COMFY_DOWN", "LO")])
        live = [{"pid": 7, "start_ts": NOW - 30, "newest_image_ts": None}]
        self.assertEqual(codes(derive_alarms(state(comfy=down, batches=live))), [("COMFY_DOWN", "HI")])

    def test_pump_wedged_uses_start_time_when_no_image_yet(self):
        young = [{"pid": 7, "start_ts": NOW - 300, "newest_image_ts": NOW - 5000}]
        self.assertEqual(derive_alarms(state(batches=young)), [])
        old = [{"pid": 7, "start_ts": NOW - 700, "newest_image_ts": None}]
        self.assertEqual(codes(derive_alarms(state(batches=old))), [("PUMP_WEDGED", "HI")])

    def test_pump_wedged_clears_when_images_keep_coming(self):
        b = [{"pid": 7, "start_ts": NOW - 7200, "newest_image_ts": NOW - 20}]
        self.assertEqual(derive_alarms(state(batches=b)), [])
        b[0]["newest_image_ts"] = NOW - THRESHOLDS["wedged_s"] - 1
        self.assertEqual(codes(derive_alarms(state(batches=b))), [("PUMP_WEDGED", "HI")])

    def test_unknown_silo_never_raises_wedged(self):
        b = [{"pid": 7, "start_ts": NOW - 7200, "newest_image_ts": None, "silo_known": False}]
        self.assertEqual(derive_alarms(state(batches=b)), [])
        self.assertIn("PUMP_WEDGED", unknown_codes(state(batches=b)))

    def test_stale_checkpoint_only_without_live_batch(self):
        ckpt = {"exists": True, "current_index": 40, "total_jobs": 100}
        self.assertEqual(codes(derive_alarms(state(idle_checkpoint=ckpt))), [("STALE_CHECKPOINT", "LO")])
        done = {"exists": True, "current_index": 100, "total_jobs": 100}
        self.assertEqual(derive_alarms(state(idle_checkpoint=done)), [])

    def test_utilities(self):
        s = state(gpu={"temp_c": 86}, host={"mem_avail_pct": 5, "swap_pages_s": 5000})
        self.assertEqual(codes(derive_alarms(s)),
                         [("GPU_HOT", "HI"), ("MEM_LOW", "HI"), ("SWAP_THRASH", "HI")])


class AlarmOnDelayTest(unittest.TestCase):
    def cond(self, code="COMFY_DOWN", severity="LO"):
        return {"code": code, "tag": "U-902", "severity": severity, "message": "", "pid": None}

    def test_waits_for_delay_then_keeps_first_seen_time(self):
        od = AlarmOnDelay({"COMFY_DOWN": 15})
        self.assertEqual(od.apply([self.cond()], NOW), [])
        self.assertEqual(od.apply([self.cond()], NOW + 14), [])
        shown = od.apply([self.cond()], NOW + 15)
        self.assertEqual(len(shown), 1)
        self.assertEqual(shown[0]["since"], NOW)

    def test_cleared_condition_restarts_its_delay(self):
        od = AlarmOnDelay({"COMFY_DOWN": 15})
        od.apply([self.cond()], NOW)
        od.apply([], NOW + 10)  # cleared: forgotten
        self.assertEqual(od.apply([self.cond()], NOW + 20), [])

    def test_severity_change_does_not_reset_delay(self):
        od = AlarmOnDelay({"COMFY_DOWN": 15})
        od.apply([self.cond(severity="LO")], NOW)
        shown = od.apply([self.cond(severity="HI")], NOW + 16)
        self.assertEqual(shown[0]["severity"], "HI")
        self.assertEqual(shown[0]["since"], NOW)

    def test_unknown_reading_holds_timer_instead_of_resetting(self):
        od = AlarmOnDelay({"GPU_HOT": 30})
        hot = {"code": "GPU_HOT", "tag": "U-901", "severity": "HI", "message": "", "pid": None}
        od.apply([hot], NOW)
        od.apply([], NOW + 10, hold={"GPU_HOT"})  # probe failed this tick
        self.assertEqual(od.apply([hot], NOW + 30)[0]["since"], NOW)
        od.apply([], NOW + 40)  # known and cleared: forgotten
        self.assertEqual(od.apply([hot], NOW + 50), [])


    def test_seeded_first_seen_annunciates_at_once_after_restart(self):
        od = AlarmOnDelay({"COMFY_DOWN": 15})
        od.seed({"COMFY_DOWN|U-902|None": NOW - 100})
        shown = od.apply([{"code": "COMFY_DOWN", "tag": "U-902", "severity": "LO", "message": "", "pid": None}], NOW)
        self.assertEqual(shown[0]["since"], NOW - 100)


class ParsingTest(unittest.TestCase):
    def test_relative_config_resolves_against_process_cwd(self):
        got = _parse_batch_argv(["python", "batch_manager/batch-production-main.py",
                                 "--config", "config/x.yaml", "--pilot"], "/work/pipeline")
        self.assertEqual(got, {"config_path": "/work/pipeline/config/x.yaml", "pilot": True})

    def test_equals_form_and_absolute_path(self):
        got = _parse_batch_argv(["python", "b.py", "--config=/abs/c.yaml"], "/elsewhere")
        self.assertEqual(got, {"config_path": "/abs/c.yaml", "pilot": False})

    def test_relative_config_with_unreadable_cwd_is_unknown(self):
        got = _parse_batch_argv(["python", "b.py", "--config", "c.yaml", "--pilot"], None)
        self.assertEqual(got, {"config_path": None, "pilot": True})

    def test_malformed_config_shapes_are_tolerated(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
            f.write("- just\n- a list\n")
        try:
            self.assertEqual(load_batch_config(f.name), {})
        finally:
            Path(f.name).unlink()
        self.assertEqual(section({"paths": None}, "paths"), {})
        self.assertEqual(section({"paths": "x"}, "paths"), {})
        self.assertIsNone(run_target({"generation": None}, pilot=False))
        self.assertEqual(load_batch_config("/dev/zero"), {})  # not a regular file

    def test_run_target(self):
        cfg = {"generation": {"total_images": 500,
                              "defect_distribution": {"crack": 0.5, "porosity": 0.5, "undercut": 0}}}
        self.assertEqual(run_target(cfg, pilot=False), 500)
        self.assertEqual(run_target(cfg, pilot=True), 2)
        self.assertIsNone(run_target({}, pilot=False))


if __name__ == "__main__":
    unittest.main(verbosity=2)
