"""Tests for the operator tool buttons (output folders, ComfyUI on/off).

Run: .venv/bin/python tests/test-plant-hmi-operator-tools.py
"""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from plant_hmi import plant_operator_tools as tools  # noqa: E402
from plant_hmi import plant_operator_tools_routes as routes  # noqa: E402
from plant_hmi import plant_run_evaluation as evaluation  # noqa: E402
import json  # noqa: E402

H = {"X-Plant-HMI": "1"}


class RunFolderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        p = mock.patch.object(tools, "RUNS_ROOT", self.root)
        p.start()
        self.addCleanup(p.stop)
        run = self.root / "2026-10-02_091530_lack-of-fusion-100" / "lack_of_fusion"
        run.mkdir(parents=True)
        for i in range(3):
            (run / f"lof_{i}.png").write_bytes(b"x")
            (run / f"lof_{i}_mask.png").write_bytes(b"x")
        (self.root / "crack").mkdir()            # old flat layout: not a run folder

    def test_list_counts_images_not_masks_and_skips_old_layout(self):
        runs = tools.list_runs()
        self.assertEqual([(r["name"], r["images"]) for r in runs],
                         [("2026-10-02_091530_lack-of-fusion-100", 3)])

    def test_resolve_run_blocks_traversal(self):
        self.assertIsNotNone(tools.resolve_run("2026-10-02_091530_lack-of-fusion-100"))
        for bad in ("..", "../etc", "a/b", "", "nope", "x\0y"):
            self.assertIsNone(tools.resolve_run(bad), bad)

    def test_open_route_guarded_and_validated(self):
        app = FastAPI()
        app.include_router(routes.router, prefix="/plant-hmi")
        client = TestClient(app)
        url = "/plant-hmi/api/control/tools/open"
        self.assertEqual(client.post(url, json={"name": "x"}).status_code, 403)          # no header
        self.assertEqual(client.post(url, json={"name": "../etc"}, headers=H).status_code, 404)
        with mock.patch.object(tools, "open_folder", return_value=None) as opener:
            res = client.post(url, json={"name": "2026-10-02_091530_lack-of-fusion-100"}, headers=H)
        self.assertEqual(res.status_code, 200)
        opener.assert_called_once()


class ComfyToggleTests(unittest.TestCase):
    def test_stop_refused_while_batch_runs(self):
        with mock.patch.object(tools.host, "find_batch_processes", return_value=[{"pid": 1}]), \
                mock.patch.object(tools.subprocess, "run") as run:
            self.assertIn("batch", tools.comfy_stop())
            run.assert_not_called()

    def test_start_is_idempotent_and_uses_comfy_venv(self):
        with mock.patch.object(tools, "_unit_active", return_value=True), \
                mock.patch.object(tools.subprocess, "run") as run:
            self.assertIsNone(tools.comfy_start())
            run.assert_not_called()
        with mock.patch.object(tools, "_unit_active", return_value=False), \
                mock.patch.object(tools.subprocess, "run") as run:
            run.return_value = mock.Mock(returncode=0, stderr="")
            self.assertIsNone(tools.comfy_start())
            argv = run.call_args_list[-1].args[0]
            self.assertEqual(argv[:3], ["systemd-run", "--user", "--unit=tdm-comfyui"])
            self.assertIn(str(tools.COMFY_PYTHON), argv)

    def test_toggle_route_409_when_batch_running(self):
        app = FastAPI()
        app.include_router(routes.router, prefix="/plant-hmi")
        with tempfile.TemporaryDirectory() as d, \
                mock.patch("plant_hmi.plant_batch_audit.AUDIT_PATH", Path(d) / "a.jsonl"), \
                mock.patch("plant_hmi.plant_batch_audit.CONTROL_DIR", Path(d)), \
                mock.patch.object(tools.host, "find_batch_processes", return_value=[{"pid": 1}]):
            res = TestClient(app).post("/plant-hmi/api/control/tools/comfyui",
                                       json={"action": "stop"}, headers=H)
        self.assertEqual(res.status_code, 409)


class EvaluationTests(unittest.TestCase):
    RESULT = {"run_id": "hmi-eval-r-20261002-093000", "finished": 1.0, "pairs": [
        {"pair": "LP↔lack_of_fusion", "synthetic": "lack_of_fusion", "n_syn": 100, "n_used": 96, "c2st": 0.875,
         "crit": {"bien_doc": {"real_med": 3.6, "syn_med": 9.6, "auc": 0.96},
                  "vung_dac": {"real_med": 0.79, "syn_med": 0.76, "auc": 0.43}}},
        {"pair": "CR↔crack", "synthetic": "crack", "n_syn": 0, "n_used": 0, "c2st": None, "crit": {}}]}

    def test_verdict_bands(self):
        self.assertEqual([evaluation._verdict(a) for a in (0.43, 0.68, 0.96, 0.06, None)],
                         ["gần giống", "hơi lệch", "khác rõ", "khác rõ", "—"])

    def test_summary_skips_absent_types_and_labels_criteria(self):
        out = evaluation.summarize(self.RESULT)
        self.assertEqual([p["synthetic"] for p in out["pairs"]], ["lack_of_fusion"])
        crit = {c["key"]: c for c in out["pairs"][0]["criteria"]}
        self.assertEqual((crit["bien_doc"]["label"], crit["bien_doc"]["verdict"]), ("Độ dốc tại biên", "khác rõ"))

    def test_summary_includes_new_ruler_block_first(self):
        result = {**self.RESULT, "defect_metrics": {"ruler": "w0003-16dac-trung-v1", "types": {
            "crack": {"reference": "Crack", "n_real": 32, "n_syn": 50, "detection_rate_real": 0.9,
                      "detection_rate_syn": 0.8, "c2st": 0.72, "c2st_reason": None,
                      "kid": {"value": 1.1, "ci_low": 0.5, "ci_high": 1.7},
                      "density_coverage": {"density": 0.6, "coverage": 0.5}, "small_reference": False,
                      "null": {"c2st": {"median": 0.5}, "kid": {"median": 0.1},
                                "density": {"median": 0.9}, "coverage": {"median": 0.95}}},
            "undercut": {"reference": None, "n_syn": 20, "detection_rate_syn": 0.7},
            "porosity": {"reference": "Gas_Pore", "n_syn": 0},
        }}}
        out = evaluation.summarize(result)
        self.assertEqual(out["defect_metrics"]["ruler"], "w0003-16dac-trung-v1")
        types = {t["defect_type"]: t for t in out["defect_metrics"]["types"]}
        self.assertEqual(set(types), {"crack", "undercut"})  # porosity n_syn=0: loại không có trong đợt chạy
        self.assertEqual(types["crack"]["perfect"]["c2st"], 0.5)
        self.assertIsNone(types["undercut"]["reference"])

    def test_summary_old_run_without_defect_metrics_shows_empty_block(self):
        out = evaluation.summarize(self.RESULT)   # RESULT không có defect_metrics (lần chạy cũ trước bản thước mới)
        self.assertIsNone(out["defect_metrics"]["ruler"])
        self.assertEqual(out["defect_metrics"]["types"], [])

    def test_summary_passes_through_per_type_ruler_on_target_and_reference_only(self):
        """Follow-up 7/10 (thước theo loại): mỗi loại ghi "ruler" đã dùng; "on_target"/"reference_only"
        (bước 1, 3 plan 261006) cũng phải lọt qua summarize, không bị lược bỏ như lần đầu thêm (lỗi tự
        phát hiện: JS trang đọc 3 trường này từ /evaluate nhưng summarize từng lọc mất cả ba)."""
        result = {**self.RESULT, "defect_metrics": {"ruler": "w0003-16dac-trung-v2-per-type-crack-lop-v1", "types": {
            "crack": {"reference": "Crack", "ruler": "w0003-16dac-trung-v1", "n_real": 32, "n_syn": 50,
                      "detection_rate_real": 0.9, "detection_rate_syn": 0.8, "c2st": 0.72, "c2st_reason": None,
                      "kid": {"value": 1.1, "ci_low": 0.5, "ci_high": 1.7},
                      "density_coverage": {"density": 0.6, "coverage": 0.5}, "small_reference": False,
                      "reference_only": False, "on_target": {"mean_overlap_on_region": 0.7, "on_target_rate": 0.6,
                                                               "threshold": 0.3},
                      "null": {"c2st": {"median": 0.5}, "kid": {"median": 0.1},
                                "density": {"median": 0.9}, "coverage": {"median": 0.95}}},
            "metallic_inclusion": {"reference": "Metallic_Inclusion", "ruler": "w0003-16dac-trung-v2", "n_real": 3,
                                    "n_syn": 20, "detection_rate_real": 1.0, "detection_rate_syn": 0.1,
                                    "reference_only": True, "on_target": {"mean_overlap_on_region": None,
                                                                           "on_target_rate": 0.0, "threshold": 0.3},
                                    "c2st": None, "c2st_reason": "x", "kid": None, "density_coverage": {},
                                    "small_reference": True, "null": None},
        }}}
        out = evaluation.summarize(result)
        types = {t["defect_type"]: t for t in out["defect_metrics"]["types"]}
        self.assertEqual(types["crack"]["ruler"], "w0003-16dac-trung-v1")
        self.assertFalse(types["crack"]["reference_only"])
        self.assertEqual(types["crack"]["on_target"]["on_target_rate"], 0.6)
        self.assertEqual(types["metallic_inclusion"]["ruler"], "w0003-16dac-trung-v2")
        self.assertTrue(types["metallic_inclusion"]["reference_only"])
        self.assertEqual(types["metallic_inclusion"]["on_target"]["on_target_rate"], 0.0)

    def test_status_reads_newest_finished_result(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(evaluation, "RUNS_DIR", Path(d)), \
                mock.patch.dict(evaluation._jobs, clear=True):
            self.assertEqual(evaluation.status("r")["state"], "none")
            for stamp, c2st in (("20261002-090000", 0.9), ("20261002-093000", 0.875)):
                run = Path(d) / f"hmi-eval-r-{stamp}"
                run.mkdir()
                (run / "result.json").write_text(json.dumps({**self.RESULT, "run_id": run.name,
                    "pairs": [{**self.RESULT["pairs"][0], "c2st": c2st}]}))
            st = evaluation.status("r")
            self.assertEqual((st["state"], st["pairs"][0]["c2st"]), ("done", 0.875))


if __name__ == "__main__":
    unittest.main(verbosity=2)
