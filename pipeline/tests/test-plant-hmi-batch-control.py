"""Unit tests for Plant HMI phase 6A: permissive logic (pure), config whitelist
(traversal/symlink-escape/control-char rejection), argv building (incl. the H3/M7/L2
systemd-run flags), the cross-process start lock (H2), stop-target + pid-reuse
validation (L4), checkpoint exposure (M6) and the start/stop/state routes.
`subprocess.run`/`os.kill` are mocked ONLY here, at the test boundary; the real code
always calls `systemd-run`/`systemctl`.

Run: .venv/bin/python tests/test-plant-hmi-batch-control.py
"""

import fcntl
import json
import os
import signal
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from plant_hmi import plant_batch_config_whitelist as whitelist  # noqa: E402
from plant_hmi import plant_batch_control_routes as routes  # noqa: E402
from plant_hmi import plant_batch_process_ops as ops  # noqa: E402
from plant_hmi import plant_batch_run_dirs as run_dirs  # noqa: E402
from plant_hmi import plant_production_readers as production  # noqa: E402
from plant_hmi import plant_batch_state_builder as state_builder  # noqa: E402
from plant_hmi.plant_batch_control import evaluate_permissives, blocking_failures  # noqa: E402


class PermissiveTests(unittest.TestCase):
    """Pure evaluate_permissives: no I/O, fixed dict in -> fixed list out."""

    FULL_OK = {"live_batch_count": 0, "comfy_ok": True, "training_pids": [],
               "mem_low": False, "swap_thrash": False, "config_valid": True, "main_silo": False}

    def test_all_ok_nothing_blocks(self):
        rows = evaluate_permissives(self.FULL_OK)
        self.assertTrue(all(r["ok"] for r in rows))
        self.assertEqual(blocking_failures(rows), [])

    def test_live_batch_blocks(self):
        rows = evaluate_permissives({**self.FULL_OK, "live_batch_count": 1})
        failures = blocking_failures(rows)
        self.assertEqual([f["code"] for f in failures], ["NO_LIVE_BATCH"])

    def test_comfy_down_blocks(self):
        rows = evaluate_permissives({**self.FULL_OK, "comfy_ok": False})
        self.assertIn("COMFY_UP", [f["code"] for f in blocking_failures(rows)])

    def test_comfy_unknown_blocks_fail_safe(self):
        rows = evaluate_permissives({**self.FULL_OK, "comfy_ok": None})
        self.assertIn("COMFY_UP", [f["code"] for f in blocking_failures(rows)])

    def test_training_pid_blocks(self):
        rows = evaluate_permissives({**self.FULL_OK, "training_pids": [4242]})
        failures = blocking_failures(rows)
        self.assertEqual([f["code"] for f in failures], ["NO_TRAINING"])
        self.assertIn("4242", next(f for f in rows if f["code"] == "NO_TRAINING")["message"])

    def test_mem_low_blocks(self):
        rows = evaluate_permissives({**self.FULL_OK, "mem_low": True})
        self.assertIn("MEM_OK", [f["code"] for f in blocking_failures(rows)])

    def test_swap_thrash_blocks(self):
        rows = evaluate_permissives({**self.FULL_OK, "swap_thrash": True})
        self.assertIn("MEM_OK", [f["code"] for f in blocking_failures(rows)])

    def test_mem_unknown_blocks_fail_safe(self):
        rows = evaluate_permissives({**self.FULL_OK, "mem_low": None, "swap_thrash": None})
        self.assertIn("MEM_OK", [f["code"] for f in blocking_failures(rows)])

    def test_config_invalid_blocks(self):
        rows = evaluate_permissives({**self.FULL_OK, "config_valid": False})
        self.assertIn("CONFIG_VALID", [f["code"] for f in blocking_failures(rows)])

    def test_run_dir_is_informational_never_blocks(self):
        rows = evaluate_permissives({**self.FULL_OK, "main_silo": True})
        run_dir = next(r for r in rows if r["code"] == "RUN_DIR")
        self.assertTrue(run_dir["ok"])
        self.assertFalse(run_dir["blocking"])
        self.assertEqual(blocking_failures(rows), [])

    def test_gpu_lease_free_does_not_block(self):
        rows = evaluate_permissives({**self.FULL_OK, "gpu_lease": None})
        self.assertNotIn("GPU_FREE", [f["code"] for f in blocking_failures(rows)])

    def test_gpu_lease_held_by_other_blocks_with_owner_in_message(self):
        held = {"owner": "realism-loop:loop-1", "purpose": "vòng lặp realism (auto)", "pid": 1, "ts": 0}
        rows = evaluate_permissives({**self.FULL_OK, "gpu_lease": held})
        failures = blocking_failures(rows)
        self.assertEqual([f["code"] for f in failures], ["GPU_FREE"])
        self.assertIn("realism-loop:loop-1", failures[0]["message"])

    def test_gpu_lease_missing_key_defaults_to_free(self):
        """Back-compat: a state dict without the key at all (older caller) must not
        suddenly block every start."""
        rows = evaluate_permissives(self.FULL_OK)
        self.assertEqual(blocking_failures(rows), [])


class WhitelistTests(unittest.TestCase):
    """Config name resolution: only pipeline/config/*.yaml and _generated/*.yaml,
    verified with a real symlink escape attempt and a real NUL byte."""

    def test_direct_config_resolves(self):
        path = whitelist.resolve_config_name("batch-config.yaml")
        self.assertIsNotNone(path)
        self.assertEqual(path.parent, whitelist.CONFIG_DIR)

    def test_generated_config_resolves(self):
        configs = whitelist.list_configs()
        generated = [c for c in configs if c["name"].startswith("_generated/")]
        if not generated:
            self.skipTest("no _generated configs present on this checkout")
        path = whitelist.resolve_config_name(generated[0]["name"])
        self.assertIsNotNone(path)

    def test_traversal_rejected(self):
        self.assertIsNone(whitelist.resolve_config_name("../../../etc/passwd"))
        self.assertIsNone(whitelist.resolve_config_name("_generated/../batch-config.yaml"))

    def test_subdirectory_rejected(self):
        self.assertIsNone(whitelist.resolve_config_name("benchmark/foo.yaml"))
        self.assertIsNone(whitelist.resolve_config_name("presets/foo.yaml"))

    def test_non_yaml_rejected(self):
        self.assertIsNone(whitelist.resolve_config_name("batch-config.yaml.bak"))
        self.assertIsNone(whitelist.resolve_config_name(""))

    def test_nonexistent_name_rejected(self):
        self.assertIsNone(whitelist.resolve_config_name("does-not-exist.yaml"))

    def test_control_char_rejected_without_exception(self):
        """L1: a NUL byte survives JSON parsing but must never reach `Path.resolve`
        as an unhandled ValueError; it is screened out up front and returns None
        the same as any other invalid name."""
        self.assertIsNone(whitelist.resolve_config_name("batch-config\x00.yaml"))
        self.assertIsNone(whitelist.resolve_config_name("batch-config\x01.yaml"))
        self.assertIsNone(whitelist.resolve_config_name("_generated/plant-hmi-pilot\x00.yaml"))

    def test_symlink_escape_rejected(self):
        with tempfile.TemporaryDirectory() as outside:
            target = Path(outside) / "secret.yaml"
            target.write_text("paths: {output_base_dir: /tmp/x}\n")
            link = whitelist.CONFIG_DIR / "zz-test-escape-link.yaml"
            try:
                link.symlink_to(target)
                self.assertIsNone(whitelist.resolve_config_name("zz-test-escape-link.yaml"))
            finally:
                link.unlink(missing_ok=True)

    def test_main_silo_flag_matches_base_config(self):
        rows = whitelist.list_configs()
        base = next(r for r in rows if r["name"] == "batch-config.yaml")
        self.assertTrue(base["main_silo"])


class ArgvTests(unittest.TestCase):
    def test_argv_is_a_list_never_a_shell_string(self):
        argv = ops.build_start_argv(Path("/x/cfg.yaml"), pilot=True, resume=True, unit="tdm-batch-test")
        self.assertIsInstance(argv, list)
        self.assertEqual(argv[0], "systemd-run")
        self.assertIn("--unit=tdm-batch-test", argv)
        self.assertIn("--pilot", argv)
        self.assertIn("--resume", argv)
        self.assertIn("--config", argv)
        self.assertIn("/x/cfg.yaml", argv)

    def test_argv_omits_flags_when_false(self):
        argv = ops.build_start_argv(Path("/x/cfg.yaml"), pilot=False, resume=False, unit="tdm-batch-test")
        self.assertNotIn("--pilot", argv)
        self.assertNotIn("--resume", argv)

    def test_argv_has_sigint_kill_signal_and_stop_timeout(self):
        """H3: the batch only handles SIGINT (KeyboardInterrupt), never systemd's
        default SIGTERM, so the unit itself must be told to send SIGINT on stop."""
        argv = ops.build_start_argv(Path("/x/cfg.yaml"), False, False, "tdm-batch-test")
        self.assertIn("KillSignal=SIGINT", argv)
        self.assertIn("TimeoutStopSec=120", argv)

    def test_argv_has_exec_type_collect_and_no_expand(self):
        """M7: Type=exec (not the default simple) so "active" means exec() really
        succeeded; --collect drops a failed transient unit instead of leaking it;
        --expand-environment=no so a `$` in a config path is never expanded."""
        argv = ops.build_start_argv(Path("/x/cfg.yaml"), False, False, "tdm-batch-test")
        self.assertIn("--service-type=exec", argv)
        self.assertIn("--collect", argv)
        self.assertIn("--expand-environment=no", argv)


class StartLockTests(unittest.TestCase):
    """H2: start_lock() is a REAL cross-process file lock, not just an in-process
    mutex, so a second OS process attempting to start a batch also blocks."""

    def test_lock_is_held_exclusively_against_a_second_flock_attempt(self):
        with ops.start_lock():
            fd = os.open(ops.START_LOCK_PATH, os.O_CREAT | os.O_RDWR, 0o644)
            try:
                with self.assertRaises(BlockingIOError):
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            finally:
                os.close(fd)

    def test_lock_releases_after_the_with_block(self):
        with ops.start_lock():
            pass
        fd = os.open(ops.START_LOCK_PATH, os.O_CREAT | os.O_RDWR, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)  # must not raise: lock was released
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


class StopTargetTests(unittest.TestCase):
    """stop_batch must refuse any pid not already reported as a live batch process,
    and must send SIGINT (never SIGTERM) when there is no systemd unit (H3)."""

    def test_refuses_pid_not_in_live_list(self):
        result = ops.stop_batch(99999, live_pids=[123, 456])
        self.assertFalse(result["ok"])
        self.assertIn("99999", result["error"])

    @mock.patch("plant_hmi.plant_batch_process_ops.find_unit_for_pid", return_value="tdm-batch-250101-000000")
    @mock.patch("plant_hmi.plant_batch_process_ops.subprocess.run")
    def test_stops_via_systemctl_for_unit_pid(self, mock_run, mock_unit):
        mock_run.return_value = mock.Mock(returncode=0, stdout="", stderr="")
        result = ops.stop_batch(123, live_pids=[123])
        self.assertTrue(result["ok"])
        self.assertEqual(result["unit"], "tdm-batch-250101-000000")
        mock_run.assert_called_once()
        self.assertEqual(mock_run.call_args[0][0][:3], ["systemctl", "--user", "stop"])

    @mock.patch("plant_hmi.plant_batch_process_ops.find_unit_for_pid", return_value=None)
    @mock.patch("plant_hmi.plant_batch_process_ops.os.kill")
    def test_sigint_for_non_unit_pid(self, mock_kill, mock_unit):
        result = ops.stop_batch(123, live_pids=[123])
        self.assertTrue(result["ok"])
        self.assertIsNone(result["unit"])
        mock_kill.assert_called_once_with(123, signal.SIGINT)


class CheckpointInfoTests(unittest.TestCase):
    """checkpoint_info looks at the newest unfinished RUN of the selected config (each
    HMI start writes to its own output/synthetic/<date_time>_<config>/ folder)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        for target, value in (("RUN_CONFIG_DIR", d / "runs"), ("RUNS_ROOT", d / "synthetic")):
            p = mock.patch(f"plant_hmi.plant_batch_run_dirs.{target}", value)
            p.start()
            self.addCleanup(p.stop)
        self.cfg = d / "lf.yaml"
        self.cfg.write_text("paths:\n  output_base_dir: /x\ngeneration:\n  total_images: 100\n")

    def _checkpoint(self, run_dir, idx, total):
        (run_dir / "checkpoints").mkdir(parents=True, exist_ok=True)
        (run_dir / "checkpoints" / "batch_state.json").write_text(json.dumps(
            {"current_index": idx, "completed_count": idx, "jobs": [{}] * total, "failed_jobs": []}))

    def test_new_run_gets_own_dated_folder(self):
        run_cfg, run_dir = run_dirs.new_run(self.cfg, "_generated/lf.yaml", now=1790900000)
        self.assertRegex(run_dir.name, r"^\d{4}-\d{2}-\d{2}_\d{6}_lf$")
        self.assertEqual(run_dir.parent, run_dirs.RUNS_ROOT)
        paths = yaml.safe_load(run_cfg.read_text())["paths"]
        self.assertEqual(paths["output_base_dir"], str(run_dir))
        self.assertEqual(paths["checkpoint_dir"], str(run_dir / "checkpoints"))

    def test_incomplete_run_exposed_complete_or_missing_is_none(self):
        self.assertIsNone(state_builder.checkpoint_info(None))
        _, run_dir = run_dirs.new_run(self.cfg, "lf.yaml", now=1790900000)
        self.assertIsNone(state_builder.checkpoint_info(self.cfg))          # no checkpoint yet
        self._checkpoint(run_dir, 40, 100)
        info = state_builder.checkpoint_info(self.cfg)
        self.assertEqual((info["current_index"], info["total"], info["run_dir"]), (40, 100, str(run_dir)))
        self._checkpoint(run_dir, 100, 100)
        production._cache.clear()
        self.assertIsNone(state_builder.checkpoint_info(self.cfg))          # finished run


class ResumeRouteTests(unittest.TestCase):
    """Resume without an unfinished run of that config is refused (409), never a fresh start."""

    def test_resume_without_unfinished_run_is_409(self):
        with tempfile.TemporaryDirectory() as d, \
                mock.patch("plant_hmi.plant_batch_run_dirs.RUN_CONFIG_DIR", Path(d) / "runs"), \
                mock.patch("plant_hmi.plant_batch_audit.AUDIT_PATH", Path(d) / "a.jsonl"), \
                mock.patch("plant_hmi.plant_batch_audit.CONTROL_DIR", Path(d)), \
                mock.patch("plant_hmi.plant_batch_process_ops.START_LOCK_PATH", Path(d) / "l.lock"), \
                mock.patch("plant_hmi.plant_batch_process_ops.CONTROL_DIR", Path(d)), \
                mock.patch("plant_hmi.plant_batch_state_builder.permissive_state",
                           return_value=PermissiveTests.FULL_OK), \
                mock.patch("plant_hmi.plant_batch_control_routes.ops.start_batch") as start:
            app = FastAPI()
            app.include_router(routes.router, prefix="/plant-hmi")
            res = TestClient(app).post("/plant-hmi/api/control/batch/start",
                                       json={"config": "batch-config.yaml", "resume": True, "reason": "r"},
                                       headers={"X-Plant-HMI": "1"})
            self.assertEqual(res.status_code, 409)
            start.assert_not_called()


class RouteTests(unittest.TestCase):
    """Routes via fastapi TestClient; subprocess/process-list calls mocked at the
    module boundary only (never real systemd-run). Lock + audit paths point at a
    temp dir so tests never touch the real control/ directory."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        self.patches = [
            mock.patch("plant_hmi.plant_batch_audit.CONTROL_DIR", d),
            mock.patch("plant_hmi.plant_batch_audit.AUDIT_PATH", d / "batch-audit.jsonl"),
            mock.patch("plant_hmi.plant_batch_process_ops.CONTROL_DIR", d),
            mock.patch("plant_hmi.plant_batch_process_ops.START_LOCK_PATH", d / "batch-start.lock"),
        ]
        self.patches += [mock.patch("plant_hmi.plant_batch_run_dirs.RUN_CONFIG_DIR", d / "runs"),
                         mock.patch("plant_hmi.plant_batch_run_dirs.RUNS_ROOT", d / "synthetic")]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)
        app = FastAPI()
        app.include_router(routes.router, prefix="/plant-hmi")
        self.client = TestClient(app)
        self.full_ok_state = {
            "live_batch_count": 0, "comfy_ok": True, "training_pids": [],
            "mem_low": False, "swap_thrash": False, "config_valid": True, "main_silo": False,
        }

    def test_state_requires_no_csrf_header_for_get(self):
        res = self.client.get("/plant-hmi/api/control/batch")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertIn("configs", body)
        self.assertIn("permissives", body)
        self.assertIn("live", body)
        self.assertIn("checkpoint", body)

    def test_start_without_header_is_403(self):
        res = self.client.post("/plant-hmi/api/control/batch/start",
                               json={"config": "batch-config.yaml", "reason": "x"})
        self.assertEqual(res.status_code, 403)

    def test_start_cross_origin_is_403(self):
        res = self.client.post("/plant-hmi/api/control/batch/start",
                               json={"config": "batch-config.yaml", "reason": "x"},
                               headers={"X-Plant-HMI": "1", "Origin": "http://evil.example"})
        self.assertEqual(res.status_code, 403)

    def test_start_rejects_non_whitelisted_config(self):
        res = self.client.post("/plant-hmi/api/control/batch/start",
                               json={"config": "../../../etc/passwd", "reason": "x"},
                               headers={"X-Plant-HMI": "1"})
        self.assertEqual(res.status_code, 400)
        audit = self.client.get("/plant-hmi/api/control/batch/audit?limit=1").json()
        self.assertFalse(audit[0]["accepted"])

    def test_start_rejects_control_char_config_as_400_not_500(self):
        """L1: must never surface as an unhandled 500 (embedded NUL ValueError)."""
        res = self.client.post("/plant-hmi/api/control/batch/start",
                               json={"config": "batch-config\x00.yaml", "reason": "x"},
                               headers={"X-Plant-HMI": "1"})
        self.assertEqual(res.status_code, 400)
        audit = self.client.get("/plant-hmi/api/control/batch/audit?limit=1").json()
        self.assertFalse(audit[0]["accepted"])

    @mock.patch("plant_hmi.plant_batch_state_builder.permissive_state")
    def test_start_blocked_by_permissive_returns_409_with_failures(self, mock_state):
        mock_state.return_value = {**self.full_ok_state, "comfy_ok": False}
        res = self.client.post("/plant-hmi/api/control/batch/start",
                               json={"config": "batch-config.yaml", "reason": "comfy tắt"},
                               headers={"X-Plant-HMI": "1"})
        self.assertEqual(res.status_code, 409)
        failures = res.json()["failures"]
        self.assertIn("COMFY_UP", [f["code"] for f in failures])
        audit = self.client.get("/plant-hmi/api/control/batch/audit?limit=1").json()
        self.assertFalse(audit[0]["accepted"])
        self.assertEqual(audit[0]["reason"], "comfy tắt")

    @mock.patch("plant_hmi.plant_batch_state_builder.permissive_state")
    def test_start_permissive_exception_is_audited_not_unhandled(self, mock_state):
        """L3: an exception while building permissive inputs (e.g. a /proc scan
        failure) must still be caught and audited, not surfaced as a bare 500
        with no audit trail."""
        mock_state.side_effect = RuntimeError("boom")
        res = self.client.post("/plant-hmi/api/control/batch/start",
                               json={"config": "batch-config.yaml", "reason": "x"},
                               headers={"X-Plant-HMI": "1"})
        self.assertEqual(res.status_code, 500)
        audit = self.client.get("/plant-hmi/api/control/batch/audit?limit=1").json()
        self.assertFalse(audit[0]["accepted"])

    @mock.patch("plant_hmi.plant_batch_control_routes.gpu_lease.acquire", return_value=(True, None))
    @mock.patch("plant_hmi.plant_batch_control_routes.ops.start_batch")
    @mock.patch("plant_hmi.plant_batch_state_builder.permissive_state")
    def test_start_accepted_calls_ops_and_audits(self, mock_state, mock_start, mock_lease):
        mock_state.return_value = self.full_ok_state
        mock_start.return_value = {"ok": True, "unit": "tdm-batch-250101-000000", "pid": 4242, "error": None}
        res = self.client.post("/plant-hmi/api/control/batch/start",
                               json={"config": "batch-config.yaml", "pilot": True, "reason": "test pilot"},
                               headers={"X-Plant-HMI": "1"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["unit"], "tdm-batch-250101-000000")
        mock_start.assert_called_once()
        args, _ = mock_start.call_args
        # the batch runs a per-run copy of the selected config, writing to its own folder
        self.assertEqual(args[0].parent, run_dirs.RUN_CONFIG_DIR)
        self.assertTrue(args[0].name.endswith("_batch-config.yaml"))
        run_dir = Path(res.json()["run_dir"])
        self.assertEqual(run_dir.parent, run_dirs.RUNS_ROOT)
        self.assertEqual(yaml.safe_load(args[0].read_text())["paths"]["output_base_dir"], str(run_dir))
        self.assertTrue(args[1])  # pilot=True
        audit = self.client.get("/plant-hmi/api/control/batch/audit?limit=1").json()
        self.assertTrue(audit[0]["accepted"])
        self.assertEqual(audit[0]["unit"], "tdm-batch-250101-000000")

    @mock.patch("plant_hmi.plant_batch_control_routes.ops.start_batch")
    @mock.patch("plant_hmi.plant_batch_state_builder.permissive_state")
    def test_start_failure_from_ops_returns_500_and_audits(self, mock_state, mock_start):
        mock_state.return_value = self.full_ok_state
        mock_start.return_value = {"ok": False, "unit": "tdm-batch-x", "error": "unit không active"}
        res = self.client.post("/plant-hmi/api/control/batch/start",
                               json={"config": "batch-config.yaml", "reason": "x"},
                               headers={"X-Plant-HMI": "1"})
        self.assertEqual(res.status_code, 500)
        audit = self.client.get("/plant-hmi/api/control/batch/audit?limit=1").json()
        self.assertFalse(audit[0]["accepted"])

    def test_stop_without_header_is_403(self):
        res = self.client.post("/plant-hmi/api/control/batch/stop", json={"pid": 1, "reason": "x"})
        self.assertEqual(res.status_code, 403)

    @mock.patch("plant_hmi.plant_batch_control_routes.host.find_batch_processes", return_value=[])
    def test_stop_unknown_pid_is_409_and_audited(self, mock_find):
        res = self.client.post("/plant-hmi/api/control/batch/stop",
                               json={"pid": 424242, "reason": "x"}, headers={"X-Plant-HMI": "1"})
        self.assertEqual(res.status_code, 409)
        audit = self.client.get("/plant-hmi/api/control/batch/audit?limit=1").json()
        self.assertFalse(audit[0]["accepted"])

    @mock.patch("plant_hmi.plant_batch_control_routes.ops.stop_batch")
    @mock.patch("plant_hmi.plant_batch_control_routes.host.find_batch_processes",
                return_value=[{"pid": 123, "start_ts": 1000.0, "config_path": None, "pilot": False}])
    def test_stop_accepted_calls_ops_and_audits(self, mock_find, mock_stop):
        mock_stop.return_value = {"ok": True, "unit": "tdm-batch-250101-000000", "error": None}
        res = self.client.post("/plant-hmi/api/control/batch/stop",
                               json={"pid": 123, "start_ts": 1000.0, "reason": "dừng kiểm tra"},
                               headers={"X-Plant-HMI": "1"})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["accepted"])
        audit = self.client.get("/plant-hmi/api/control/batch/audit?limit=1").json()
        self.assertTrue(audit[0]["accepted"])
        self.assertEqual(audit[0]["reason"], "dừng kiểm tra")

    @mock.patch("plant_hmi.plant_batch_control_routes.ops.stop_batch")
    @mock.patch("plant_hmi.plant_batch_control_routes.host.find_batch_processes",
                return_value=[{"pid": 123, "start_ts": 1000.0, "config_path": None, "pilot": False}])
    def test_stop_with_stale_start_ts_is_refused_pid_reuse(self, mock_find, mock_stop):
        """L4: the confirm dialog's start_ts no longer matches the live pid's
        actual start time (pid was reused by a different process); must refuse
        BEFORE calling ops.stop_batch at all."""
        res = self.client.post("/plant-hmi/api/control/batch/stop",
                               json={"pid": 123, "start_ts": 42.0, "reason": "x"},
                               headers={"X-Plant-HMI": "1"})
        self.assertEqual(res.status_code, 409)
        mock_stop.assert_not_called()
        audit = self.client.get("/plant-hmi/api/control/batch/audit?limit=1").json()
        self.assertFalse(audit[0]["accepted"])

    @mock.patch("plant_hmi.plant_batch_control_routes.ops.stop_batch")
    @mock.patch("plant_hmi.plant_batch_control_routes.host.find_batch_processes",
                return_value=[{"pid": 123, "start_ts": 1000.0, "config_path": None, "pilot": False}])
    def test_stop_without_start_ts_skips_pid_reuse_check(self, mock_find, mock_stop):
        """Back-compat: omitting start_ts (older client) still works."""
        mock_stop.return_value = {"ok": True, "unit": None, "error": None}
        res = self.client.post("/plant-hmi/api/control/batch/stop",
                               json={"pid": 123, "reason": "x"}, headers={"X-Plant-HMI": "1"})
        self.assertEqual(res.status_code, 200)
        mock_stop.assert_called_once()

    def test_reason_over_200_chars_is_422(self):
        res = self.client.post("/plant-hmi/api/control/batch/start",
                               json={"config": "batch-config.yaml", "reason": "x" * 201},
                               headers={"X-Plant-HMI": "1"})
        self.assertEqual(res.status_code, 422)


class TrainingDetectionTest(unittest.TestCase):
    """find_training_processes counts a python process running train_network.py,
    never a shell whose command line only mentions the string (e.g. pgrep -af)."""

    def test_python_script_counts_shell_mention_does_not(self):
        import subprocess
        import tempfile as tmp_mod
        from plant_hmi.plant_batch_process_ops import find_training_processes
        with tmp_mod.TemporaryDirectory() as d:
            script = Path(d) / "train_network.py"
            script.write_text("import time\ntime.sleep(30)\n")
            real = subprocess.Popen([sys.executable, str(script)])
            shell = subprocess.Popen(["bash", "-c", "sleep 30 # pgrep -af train_network"])
            try:
                import time
                time.sleep(0.3)
                found = find_training_processes()
                self.assertIn(real.pid, found)
                self.assertNotIn(shell.pid, found)
            finally:
                real.kill(); shell.kill(); real.wait(); shell.wait()


if __name__ == "__main__":
    unittest.main(verbosity=2)
