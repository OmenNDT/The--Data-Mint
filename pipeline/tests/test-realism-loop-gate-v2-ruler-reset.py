"""Follow-up 7/10 (thước theo loại, người dùng duyệt): defect_metrics["ruler"] của bản tốt nhất KHÁC vòng
hiện tại -> loop_gate_v2.gate_v2 phải đặt mốc mới ("mốc mới: thước mới"), không so cặp với số đo cũ (hai
sơ đồ chọn vùng khác nhau, so cặp vô nghĩa).

Run: .venv/bin/python tests/test-realism-loop-gate-v2-ruler-reset.py
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from realism import knobs, loop_gate, tuning_memory  # noqa: E402
from realism.defect_features16 import DEFECT_FEATURES  # noqa: E402

CRACK = {"reference": "Crack", "n_real": 20, "n_syn": 12, "n_syn_region": 12,
         "detection_rate_real": 0.9, "detection_rate_syn": 0.85, "c2st": 0.5,
         "kid": {"value": 0.0}, "density_coverage": {"density": 1.0, "coverage": 1.0},
         "null": {"c2st": {"median": 0.5, "p5": 0.45, "p95": 0.6},
                   "kid": {"median": 0.0, "p5": -0.1, "p95": 0.1},
                   "density": {"median": 1.0, "p5": 0.8, "p95": 1.2},
                   "coverage": {"median": 1.0, "p5": 0.8, "p95": 1.1}},
         "perfect": {"c2st": 0.5, "kid": 0.0, "density": 1.0, "coverage": 1.0},
         "small_reference": False,
         "cases": [{"case_id": f"c{i}", "has_region": 1.0, **{k: 0.5 for k in DEFECT_FEATURES}}
                   for i in range(12)]}


class KnobDir(unittest.TestCase):
    """Khớp KnobDir của test-realism-loop-gate-v2.py: cô lập kho núm/best.json/tuning-memory vào thư mục tạm."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        self.p = [mock.patch.object(knobs, "STATE_DIR", d), mock.patch.dict(os.environ, {}, clear=False),
                  mock.patch.object(loop_gate, "BEST_PATH", d / "best.json"), mock.patch.object(loop_gate, "STATE", d),
                  mock.patch.object(tuning_memory, "PATH", d / "tuning-memory.json")]
        for p in self.p:
            p.start()
        os.environ.pop("REALISM_KNOBS", None)
        os.environ.pop(knobs.FROZEN_ENV, None)
        self.results = {}
        self.p.append(mock.patch.object(loop_gate, "read_json", side_effect=lambda rid, name: self.results.get(rid)))
        self.p[-1].start()

    def tearDown(self):
        for p in reversed(self.p):
            p.stop()
        self.tmp.cleanup()

    def _rec(self, it, run_id):
        return {"iter": it, "eval_run": run_id, "knobs": {}, "issues": {}, "c2st": {}, "all_pass": False,
                "types": ["crack"]}


class RulerChangeResetsBaseline(KnobDir):
    def test_different_ruler_on_best_is_treated_as_new_baseline(self):
        self.results["r1"] = {"defect_metrics": {"ruler": "thuoc-cu", "types": {"crack": CRACK}}}
        rec1 = loop_gate.gate(self._rec(1, "r1"))
        self.assertEqual(rec1["decision"], "best")
        self.assertEqual(loop_gate.read_best()["iter"], 1)

        self.results["r2"] = {"defect_metrics": {"ruler": "thuoc-moi", "types": {"crack": CRACK}}}
        rec2 = loop_gate.gate(self._rec(2, "r2"))
        self.assertEqual(rec2["decision"], "best")
        self.assertEqual(rec2["reasons"], ["mốc mới: thước mới"])
        self.assertIsNone(rec2["compared_to"])
        self.assertEqual(loop_gate.read_best()["iter"], 2)   # vòng 2 thay mốc, không so cặp với vòng 1

    def test_same_ruler_compares_normally_not_reset(self):
        self.results["r1"] = {"defect_metrics": {"ruler": "thuoc-x", "types": {"crack": CRACK}}}
        loop_gate.gate(self._rec(1, "r1"))
        self.results["r2"] = {"defect_metrics": {"ruler": "thuoc-x", "types": {"crack": CRACK}}}
        rec2 = loop_gate.gate(self._rec(2, "r2"))
        # Cùng thước, cùng số đo y hệt bản tốt nhất -> không có mục tiêu nào tốt/tệ hơn rõ -> neutral, KHÔNG
        # phải nhánh "mốc mới: thước mới" (chứng minh so cặp bình thường vẫn chạy khi ruler không đổi).
        self.assertNotEqual(rec2["reasons"], ["mốc mới: thước mới"])

    def test_missing_ruler_field_on_both_sides_also_compares_normally(self):
        """defect_metrics["ruler"] vắng cả hai bên (None == None): không bị coi là đổi thước."""
        self.results["r1"] = {"defect_metrics": {"types": {"crack": CRACK}}}
        loop_gate.gate(self._rec(1, "r1"))
        self.results["r2"] = {"defect_metrics": {"types": {"crack": CRACK}}}
        rec2 = loop_gate.gate(self._rec(2, "r2"))
        self.assertNotEqual(rec2["reasons"], ["mốc mới: thước mới"])


if __name__ == "__main__":
    unittest.main()
