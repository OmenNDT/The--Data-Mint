"""Tests cho mục "Độ nhạy núm" (bước 4, plan 261002-1430): chiều "helps" suy từ op/value của
issues.py, tính "đã cũ" so với núm sản xuất, tuyến GET/POST (CSRF, 422, 409 khi bận, systemd-run
spawn dạng list không phải chuỗi shell), và phần mở rộng của /api/stop (plant_realism_routes.py)
cho một lượt đo đang chạy. Không bao giờ gọi `systemd-run`/`systemctl` thật (subprocess.run mock
ở biên test) và không bao giờ ghi vào `realism/state/runs/` thật (RUNS_DIR trỏ vào thư mục tạm).

Run: .venv/bin/python tests/test-plant-hmi-realism-sensitivity.py
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from plant_hmi import plant_realism_job_status as job_status  # noqa: E402
from plant_hmi import plant_realism_routes as realism_routes  # noqa: E402
from plant_hmi import plant_realism_sensitivity_routes as routes  # noqa: E402
from realism import runlog  # noqa: E402


class HelpsDirectionTests(unittest.TestCase):
    """_helps: chiều "có giúp" suy từ op/value của issues.py và prev/new đo được."""

    def test_ge_target_helps_when_delta_positive(self):
        self.assertTrue(routes._helps({"prev": 0.3, "new": 0.4, "delta": 0.1}, ">=", 0.7))
        self.assertFalse(routes._helps({"prev": 0.3, "new": 0.2, "delta": -0.1}, ">=", 0.7))

    def test_le_target_helps_when_delta_negative(self):
        self.assertTrue(routes._helps({"prev": 2.0, "new": 1.5, "delta": -0.5}, "<=", 1.5))
        self.assertFalse(routes._helps({"prev": 2.0, "new": 2.5, "delta": 0.5}, "<=", 1.5))

    def test_between_outside_moving_toward_interval_helps(self):
        spec = ("between", [0.72, 0.90])
        self.assertTrue(routes._helps({"prev": 0.60, "new": 0.70, "delta": 0.10}, *spec))
        self.assertFalse(routes._helps({"prev": 0.60, "new": 0.55, "delta": -0.05}, *spec))

    def test_between_inside_leaving_interval_hurts(self):
        spec = ("between", [0.35, 0.65])
        self.assertTrue(routes._helps({"prev": 0.50, "new": 0.55, "delta": 0.05}, *spec))
        self.assertFalse(routes._helps({"prev": 0.50, "new": 0.70, "delta": 0.20}, *spec))

    def test_missing_prev_or_new_is_none(self):
        self.assertIsNone(routes._helps({"prev": None, "new": 0.4, "delta": None}, ">=", 0.7))
        self.assertIsNone(routes._helps({"prev": 0.3, "new": None, "delta": None}, "<=", 1.5))

    def test_with_helps_attaches_without_mutating_original(self):
        sens = {"effects": {"v1": {"targets": {
            "Tỉ lệ vết nứt đứng ≥ 25% (thật 42%)": {"prev": 0.1, "new": 0.3, "delta": 0.2}}}}}
        out = routes._with_helps(sens)
        self.assertTrue(out["effects"]["v1"]["targets"]["Tỉ lệ vết nứt đứng ≥ 25% (thật 42%)"]["helps"])
        self.assertNotIn("helps", sens["effects"]["v1"]["targets"]["Tỉ lệ vết nứt đứng ≥ 25% (thật 42%)"])

    def test_with_helps_none_passthrough(self):
        self.assertIsNone(routes._with_helps(None))


class StaleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        from realism import knobs
        self.patches = [mock.patch.object(knobs, "STATE_DIR", Path(self.tmp.name))]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def test_no_latest_is_never_stale(self):
        self.assertFalse(routes._is_stale(None))

    def test_matching_base_knobs_not_stale(self):
        from realism import knobs
        base = knobs.values(knobs.resolve("production", use_env=False))
        self.assertFalse(routes._is_stale({"base_knobs": base}))

    def test_changed_production_knob_is_stale(self):
        from realism import knobs
        base = knobs.values(knobs.resolve("production", use_env=False))
        knobs.write_many({"crack_widen_px": 1.5}, "test", "r", store="production")
        self.assertTrue(routes._is_stale({"base_knobs": base}))


class SensJobTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for target in (runlog, routes, job_status):
            p = mock.patch.object(target, "RUNS_DIR", Path(self.tmp.name))
            p.start()
            self.addCleanup(p.stop)

    def test_idle_when_no_sens_runs(self):
        self.assertEqual(routes.sens_job(), {"state": "idle"})

    def test_ignores_loop_runs(self):
        (Path(self.tmp.name) / "loop-20261002-000000").mkdir()
        self.assertEqual(routes.sens_job(), {"state": "idle"})

    @mock.patch("plant_hmi.plant_realism_sensitivity_routes.is_unit_active", return_value=True)
    def test_running_before_any_event_uses_unit_active(self, _mock):
        (Path(self.tmp.name) / "sens-20261002-000000").mkdir()
        j = routes.sens_job()
        self.assertEqual(j["state"], "running")

    def test_done_from_events(self):
        rl = runlog.RunLog("sens-20261002-000000")
        rl.emit("config", pilot=True, n_per_type=20)
        rl.emit("variant", id="post_depth+", index=1, total=19)
        rl.emit("done")
        j = routes.sens_job()
        self.assertEqual(j["state"], "done")
        self.assertTrue(j["pilot"])
        self.assertEqual(j["variant"], "post_depth+")


class RouteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for target in (runlog, routes, job_status):
            p = mock.patch.object(target, "RUNS_DIR", Path(self.tmp.name))
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch.object(routes, "SENS_LATEST_PATH", Path(self.tmp.name) / "sensitivity.json")
        p.start()
        self.addCleanup(p.stop)
        p = mock.patch("plant_hmi.plant_realism_sensitivity_routes.gpu_lease.current", return_value=None)
        p.start()
        self.addCleanup(p.stop)
        p = mock.patch("plant_hmi.plant_realism_job_status.batch_running", return_value=False)
        p.start()
        self.addCleanup(p.stop)
        app = FastAPI()
        app.include_router(routes.router, prefix="/plant-hmi")
        self.c = TestClient(app)
        self.h = {"X-Plant-HMI": "1"}

    def test_get_sensitivity_empty_state(self):
        res = self.c.get("/plant-hmi/realism/api/sensitivity")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertIsNone(body["latest"])
        self.assertIsNone(body["latest_pilot"])
        self.assertFalse(body["stale"])
        self.assertEqual(body["job"]["state"], "idle")
        self.assertIn("post_depth", body["groups"])
        self.assertIsInstance(body["variants_planned"], list)
        self.assertTrue(len(body["variants_planned"]) > 0)

    def test_get_sensitivity_reads_latest_and_marks_stale(self):
        from realism import knobs
        with mock.patch.object(knobs, "STATE_DIR", Path(self.tmp.name)):
            routes.SENS_LATEST_PATH.write_text(json.dumps({
                "run_id": "sens-x", "base_knobs": {"crack_widen_px": 999.0}, "variants": [], "effects": {},
            }), encoding="utf-8")
            res = self.c.get("/plant-hmi/realism/api/sensitivity")
            self.assertEqual(res.status_code, 200)
            self.assertTrue(res.json()["stale"])

    def test_get_sensitivity_exposes_latest_pilot_from_newest_run(self):
        rid = "sens-20261002-010101"
        (Path(self.tmp.name) / rid).mkdir()
        (Path(self.tmp.name) / rid / "sensitivity.json").write_text(json.dumps({
            "run_id": rid, "pilot": True, "base_knobs": {}, "variants": [], "effects": {},
        }), encoding="utf-8")
        res = self.c.get("/plant-hmi/realism/api/sensitivity")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["latest_pilot"]["run_id"], rid)

    def test_start_requires_csrf_header(self):
        res = self.c.post("/plant-hmi/realism/api/sensitivity/start", json={"pilot": True})
        self.assertEqual(res.status_code, 403)

    def test_start_rejects_out_of_range_n(self):
        res = self.c.post("/plant-hmi/realism/api/sensitivity/start", json={"n_per_type": 1}, headers=self.h)
        self.assertEqual(res.status_code, 422)
        res = self.c.post("/plant-hmi/realism/api/sensitivity/start", json={"n_per_type": 999}, headers=self.h)
        self.assertEqual(res.status_code, 422)

    @mock.patch("plant_hmi.plant_realism_sensitivity_routes.subprocess.run")
    def test_start_spawns_via_systemd_run_as_list(self, mock_run):
        mock_run.return_value = mock.Mock(returncode=0, stdout="", stderr="")
        res = self.c.post("/plant-hmi/realism/api/sensitivity/start",
                          json={"pilot": True, "n_per_type": 10}, headers=self.h)
        self.assertEqual(res.status_code, 200)
        rid = res.json()["run_id"]
        self.assertTrue(rid.startswith("sens-"))
        self.assertEqual(res.json()["unit"], "tdm-realism-" + rid)
        argv = mock_run.call_args[0][0]
        self.assertIsInstance(argv, list)
        self.assertEqual(argv[0], "systemd-run")
        self.assertIn(f"--unit=tdm-realism-{rid}", argv)
        self.assertIn("--service-type=exec", argv)
        self.assertIn("--collect", argv)
        self.assertIn("--expand-environment=no", argv)
        self.assertIn("realism.sensitivity_screen", argv)
        self.assertIn("--pilot", argv)
        self.assertIn("--n-per-type", argv)
        self.assertIn("10", argv)
        self.assertTrue((Path(self.tmp.name) / rid).is_dir())

    @mock.patch("plant_hmi.plant_realism_sensitivity_routes.subprocess.run")
    def test_start_omits_pilot_flag_when_full_run(self, mock_run):
        mock_run.return_value = mock.Mock(returncode=0, stdout="", stderr="")
        res = self.c.post("/plant-hmi/realism/api/sensitivity/start",
                          json={"pilot": False, "n_per_type": 20}, headers=self.h)
        self.assertEqual(res.status_code, 200)
        argv = mock_run.call_args[0][0]
        self.assertNotIn("--pilot", argv)

    @mock.patch("plant_hmi.plant_realism_sensitivity_routes.subprocess.run")
    def test_start_returns_500_when_systemd_run_fails(self, mock_run):
        mock_run.return_value = mock.Mock(returncode=1, stdout="", stderr="unit tên xấu")
        res = self.c.post("/plant-hmi/realism/api/sensitivity/start", json={}, headers=self.h)
        self.assertEqual(res.status_code, 500)

    @mock.patch("plant_hmi.plant_realism_sensitivity_routes.job_status.job", return_value={"state": "running"})
    def test_start_refused_when_loop_running(self, _mock):
        res = self.c.post("/plant-hmi/realism/api/sensitivity/start", json={}, headers=self.h)
        self.assertEqual(res.status_code, 409)

    def test_start_refused_when_another_sensitivity_run_is_running(self):
        rid = "sens-20261002-020202"
        rl = runlog.RunLog(rid)
        rl.emit("config", pilot=False, n_per_type=20)
        with mock.patch("plant_hmi.plant_realism_sensitivity_routes.job_status.alive", return_value=True):
            res = self.c.post("/plant-hmi/realism/api/sensitivity/start", json={}, headers=self.h)
        self.assertEqual(res.status_code, 409)

    @mock.patch("plant_hmi.plant_realism_job_status.batch_running", return_value=True)
    def test_start_refused_when_batch_running(self, _mock):
        res = self.c.post("/plant-hmi/realism/api/sensitivity/start", json={}, headers=self.h)
        self.assertEqual(res.status_code, 409)

    def test_start_refused_when_gpu_lease_held(self):
        with mock.patch("plant_hmi.plant_realism_sensitivity_routes.gpu_lease.current",
                        return_value={"owner": "realism-loop:loop-9"}):
            res = self.c.post("/plant-hmi/realism/api/sensitivity/start", json={}, headers=self.h)
        self.assertEqual(res.status_code, 409)
        self.assertIn("realism-loop:loop-9", res.json()["detail"])


class StopExtensionTests(unittest.TestCase):
    """plant_realism_routes.stop() phải dừng được cả lượt đo độ nhạy (không chỉ vòng lặp): cùng
    stop.flag, cùng kiểu leo thang systemctl sau STOP_GRACE_S giây."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for target in (runlog, routes, job_status, realism_routes):
            p = mock.patch.object(target, "RUNS_DIR", Path(self.tmp.name))
            p.start()
            self.addCleanup(p.stop)
        app = FastAPI()
        app.include_router(realism_routes.router, prefix="/plant-hmi")
        self.c = TestClient(app)
        self.h = {"X-Plant-HMI": "1"}

    @mock.patch("plant_hmi.plant_realism_routes.job_status.job", return_value={"state": "idle"})
    @mock.patch("plant_hmi.plant_realism_routes.sens_job", return_value={"state": "running", "run_id": "sens-fake"})
    @mock.patch("plant_hmi.plant_realism_routes.subprocess.run")
    def test_stop_touches_flag_then_escalates_for_sensitivity_run(self, mock_run, mock_sens, mock_job):
        from realism import loop
        mock_run.return_value = mock.Mock(returncode=0, stdout="", stderr="")
        loop.STATE.mkdir(parents=True, exist_ok=True)
        loop.STOP.unlink(missing_ok=True)
        try:
            res1 = self.c.post("/plant-hmi/realism/api/stop", headers=self.h)
            self.assertEqual(res1.status_code, 200)
            self.assertTrue(res1.json()["stopping"])
            mock_run.assert_not_called()
            with mock.patch("plant_hmi.plant_realism_routes.time.time",
                            return_value=loop.STOP.stat().st_mtime + 60):
                res2 = self.c.post("/plant-hmi/realism/api/stop", headers=self.h)
            self.assertEqual(res2.status_code, 200)
            self.assertEqual(res2.json()["escalated_unit"], "tdm-realism-sens-fake")
            mock_run.assert_called_once()
            self.assertEqual(mock_run.call_args[0][0][:3], ["systemctl", "--user", "stop"])
        finally:
            loop.STOP.unlink(missing_ok=True)

    @mock.patch("plant_hmi.plant_realism_routes.job_status.job", return_value={"state": "idle", "child_pid": None})
    @mock.patch("plant_hmi.plant_realism_routes.sens_job", return_value={"state": "idle"})
    def test_stop_409_when_nothing_running(self, _mock_sens, _mock_job):
        res = self.c.post("/plant-hmi/realism/api/stop", headers=self.h)
        self.assertEqual(res.status_code, 409)


if __name__ == "__main__":
    unittest.main(verbosity=2)
