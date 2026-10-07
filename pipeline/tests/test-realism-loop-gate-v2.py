"""Cổng v2 (bước 2a plan w0003-reference): điều kiện chặn tỉ lệ tách vùng, xác định loại đủ điều kiện so
cặp, thẩm định tốt hơn/tệ hơn/không đổi trên đặc trưng tổng hợp, mốc đầu tiên khi bản tốt nhất ở thước cũ,
loại dữ liệu đi qua cổng nào (v1/v2), mục tiêu issues_v2, propose không đổi núm khi bản tốt nhất ở thước v2,
mặc định 40 ca/loại, và cú pháp JS trang Độ thật.

Run: .venv/bin/python tests/test-realism-loop-gate-v2.py
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from realism import exam_set, issues_v2, knobs, loop_gate, loop_gate_v2, sensitivity_propose, tuning_memory  # noqa: E402
from realism.defect_features16 import DEFECT_FEATURES  # noqa: E402
from realism.loop_gate_v2_metrics import paired_metrics  # noqa: E402

PIPELINE = Path(__file__).resolve().parent.parent


class KnobDir(unittest.TestCase):
    """Khớp KnobDir của test-realism-loop.py: cô lập kho núm/best.json/tuning-memory vào thư mục tạm."""

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

    def tearDown(self):
        for p in reversed(self.p):
            p.stop()
        self.tmp.cleanup()


def _dm_type(reference="Crack", n_real=20, det_real=0.9, det_syn=0.85, cases=None, null=None, c2st=0.5):
    return {"reference": reference, "n_real": n_real, "n_syn": len(cases or []), "n_syn_region": len(cases or []),
            "detection_rate_real": det_real, "detection_rate_syn": det_syn, "c2st": c2st,
            "kid": {"value": 0.0}, "density_coverage": {"density": 1.0, "coverage": 1.0},
            "null": null or {"c2st": {"median": 0.5, "p5": 0.45, "p95": 0.6},
                              "kid": {"median": 0.0, "p5": -0.1, "p95": 0.1},
                              "density": {"median": 1.0, "p5": 0.8, "p95": 1.2},
                              "coverage": {"median": 1.0, "p5": 0.8, "p95": 1.1}},
            "perfect": {"c2st": 0.5, "kid": 0.0, "density": 1.0, "coverage": 1.0},
            "small_reference": n_real < 15, "cases": cases or []}


def _cases(ids, feat_fn):
    return [{"case_id": c, "has_region": 1.0, **{k: feat_fn(i, k) for k in DEFECT_FEATURES}} for i, c in enumerate(ids)]


class DetectionBlockTest(unittest.TestCase):
    """Điều kiện chặn (người dùng duyệt 6/10): gap > 10 điểm % VÀ chưa cải thiện >= 2 điểm % so bản tốt nhất."""

    def _entry(self, gap_new, gap_best):
        det_real = 0.9
        ne = _dm_type(det_real=det_real, det_syn=det_real - gap_new, cases=[])
        be = _dm_type(det_real=det_real, det_syn=det_real - gap_best, cases=[])
        entry, blocked = loop_gate_v2._type_entry("crack", ne, be, seed=0, B=10)
        return entry, blocked

    def test_large_gap_not_improving_is_blocked(self):
        _, blocked = self._entry(0.30, 0.30)
        self.assertTrue(blocked)

    def test_large_gap_improving_enough_is_not_blocked(self):
        _, blocked = self._entry(0.30, 0.35)       # cải thiện 0,05 >= 0,02
        self.assertFalse(blocked)

    def test_small_gap_is_never_blocked(self):
        _, blocked = self._entry(0.05, 0.05)
        self.assertFalse(blocked)

    def test_few_common_cases_skips_metrics_with_reason(self):
        entry, _ = self._entry(0.0, 0.0)
        self.assertEqual(entry["metrics"], {})
        self.assertIn("ca chung", entry["skip_reason"])


class PairedMetricsVerdictTest(unittest.TestCase):
    """loop_gate_v2_metrics.paired_metrics trên đặc trưng tổng hợp: mới giống thật hơn bản tốt nhất -> tốt
    hơn rõ; ngược lại -> tệ hơn rõ; hai bên giống nhau -> không đổi."""

    def setUp(self):
        rng = np.random.default_rng(0)
        self.real = rng.normal(0.0, 1.0, (40, len(DEFECT_FEATURES)))

    def test_new_closer_to_real_is_better(self):
        rng = np.random.default_rng(1)
        new = self.real[rng.choice(40, 20, replace=False)] + rng.normal(0, 0.05, (20, len(DEFECT_FEATURES)))
        best = rng.normal(6.0, 1.0, (20, len(DEFECT_FEATURES)))     # lệch xa thật
        out = paired_metrics(self.real, new, best, B=80, seed=2)
        self.assertEqual(out["c2st"]["verdict"], "better")

    def test_new_farther_from_real_is_worse(self):
        rng = np.random.default_rng(3)
        best = self.real[rng.choice(40, 20, replace=False)] + rng.normal(0, 0.05, (20, len(DEFECT_FEATURES)))
        new = rng.normal(6.0, 1.0, (20, len(DEFECT_FEATURES)))
        out = paired_metrics(self.real, new, best, B=80, seed=4)
        self.assertEqual(out["c2st"]["verdict"], "worse")

    def test_identical_distributions_are_unchanged(self):
        rng = np.random.default_rng(5)
        idx = rng.choice(40, 20, replace=False)
        new = self.real[idx] + rng.normal(0, 0.02, (20, len(DEFECT_FEATURES)))
        best = self.real[idx] + rng.normal(0, 0.02, (20, len(DEFECT_FEATURES)))
        out = paired_metrics(self.real, new, best, B=80, seed=6)
        self.assertEqual(out["c2st"]["verdict"], "same")


class GateV2BaselineAndDispatchTest(KnobDir):
    def setUp(self):
        super().setUp()
        self.results = {}
        self.p.append(mock.patch.object(loop_gate, "read_json", side_effect=lambda rid, name: self.results.get(rid)))
        self.p[-1].start()

    def _rec(self, it, run_id, types=None):
        return {"iter": it, "eval_run": run_id, "knobs": {}, "issues": {}, "c2st": {}, "all_pass": False,
                "types": types or ["crack"]}

    def test_first_v2_round_becomes_baseline_best(self):
        ids = [f"c{i}" for i in range(3)]
        result = {"defect_metrics": {"types": {"crack": _dm_type(cases=_cases(ids, lambda i, k: 0.5))}}}
        self.results["r1"] = result
        rec = loop_gate.gate(self._rec(1, "r1"))
        self.assertEqual(rec["decision"], "best")
        self.assertEqual(rec["ruler"], "v2")
        self.assertEqual(rec["reasons"], ["mốc mới: thước mới"])
        best = loop_gate.read_best()
        self.assertEqual(best["ruler"], "v2")
        self.assertEqual(best["iter"], 1)

    def test_old_data_without_defect_metrics_uses_v1_path(self):
        self.results["old"] = {"pairs": [], "cases": []}         # không có defect_metrics: khớp dữ liệu cũ
        rec = loop_gate.gate(self._rec(1, "old"))
        self.assertNotIn("ruler", rec)
        self.assertEqual(rec["decision"], "neutral")              # v1: không "cases" -> neutral (xem GateTest v1)

    def test_error_in_defect_metrics_falls_back_to_v1(self):
        self.results["err"] = {"defect_metrics": {"types": {}, "error": "boom"}, "pairs": [], "cases": []}
        rec = loop_gate.gate(self._rec(1, "err"))
        self.assertNotIn("ruler", rec)

    def test_no_eligible_type_is_neutral(self):
        """Loại không đủ 10 ca thật tách vùng (n_real thấp): chỉ báo, cổng không nhận cũng không loại."""
        self.results["r1"] = {"defect_metrics": {"types": {"crack": _dm_type(n_real=3, cases=[])}}}
        loop_gate.gate(self._rec(1, "r1"))
        self.results["r2"] = {"defect_metrics": {"types": {"crack": _dm_type(n_real=3, cases=[])}}}
        rec = loop_gate.gate(self._rec(2, "r2"))
        self.assertEqual(rec["decision"], "neutral")
        self.assertIn("đủ điều kiện", rec["reasons"][0])


class ReusedTypeNeverBlocksTest(GateV2BaselineAndDispatchTest):
    """Loại dùng lại số đo bản tốt nhất không được chặn vòng (lỗi 7/10: vòng chỉ đổi nứt bị chặn bởi LF/LP)."""
    def test_reused_faint_type_does_not_block(self):
        ids = [f"c{i}" for i in range(12)]
        faint = _dm_type(reference="Lack_of_Fusion", det_real=0.9, det_syn=0.5, cases=_cases(ids, lambda i, k: 0.5))
        crack = _dm_type(cases=_cases(ids, lambda i, k: 0.5))
        self.results["r1"] = {"defect_metrics": {"types": {"crack": crack, "lack_of_fusion": faint}}}
        loop_gate.gate(self._rec(1, "r1", ["crack", "lack_of_fusion"]))
        self.results["r2"] = {"defect_metrics": {"types": {"crack": crack, "lack_of_fusion": faint}}}
        rec = self._rec(2, "r2", ["crack", "lack_of_fusion"]); rec["reused_types"] = ["lack_of_fusion"]
        rec = loop_gate.gate(rec)
        self.assertNotEqual(rec["decision"], "rejected", rec["reasons"])
        self.assertFalse(rec["v2"]["types"]["lack_of_fusion"]["detection"]["blocked"])


class IssuesV2Test(unittest.TestCase):
    def test_targets_pass_and_fail(self):
        entry = _dm_type(det_real=0.9, det_syn=0.85, c2st=0.5)         # gap 0,05 đạt; c2st 0,5 trong [—,0,6] đạt
        targets = issues_v2.evaluate_type(entry)
        self.assertTrue(all(t["pass"] for t in targets))

    def test_detection_gap_target_fails_over_limit(self):
        entry = _dm_type(det_real=0.9, det_syn=0.5)                    # gap 0,4 > 0,10
        targets = issues_v2.evaluate_type(entry)
        gap_t = next(t for t in targets if t["name"] == "detection_gap")
        self.assertFalse(gap_t["pass"])

    def test_no_reference_type_has_no_targets(self):
        self.assertEqual(issues_v2.evaluate_type({"reference": None}), [])

    def test_all_pass_requires_every_considered_type_to_pass(self):
        good = _dm_type(det_real=0.9, det_syn=0.85, c2st=0.5)
        bad = _dm_type(det_real=0.9, det_syn=0.5, c2st=0.5)
        self.assertTrue(issues_v2.all_pass({"defect_metrics": {"types": {"crack": good}}}))
        self.assertFalse(issues_v2.all_pass({"defect_metrics": {"types": {"crack": good, "porosity": bad}}}))
        self.assertFalse(issues_v2.all_pass({"defect_metrics": {"types": {}}}))


class ProposeUnderV2Test(KnobDir):
    def test_propose_returns_no_changes_when_best_is_v2(self):
        loop_gate._write_best({"iter": 1, "eval_run": "x", "knobs": {}, "score": {}, "ruler": "v2", "ts": 0})
        cur = {k: s[4] for k, s in knobs.REGISTRY.items()}
        new, why, mode = sensitivity_propose.propose({}, cur, sens=None)
        self.assertEqual(new, cur)
        self.assertEqual(mode, "none")
        self.assertTrue(any("thước mới" in w for w in why))

    def test_propose_falls_back_to_rules_when_best_is_v1(self):
        loop_gate._write_best({"iter": 1, "eval_run": "x", "knobs": {}, "score": {}, "ts": 0})   # không "ruler": v1
        cur = {k: s[4] for k, s in knobs.REGISTRY.items()}
        new, why, mode = sensitivity_propose.propose({}, cur, sens=None)
        self.assertEqual(mode, "none")
        self.assertFalse(any("thước mới" in w for w in why))


class DefaultNPerTypeTest(unittest.TestCase):
    """Mặc định 40 ca/loại (bước 2a): sau khi lọc has_region, 20 ca để lại quá ít hàng cho cổng v2 ghép cặp."""

    def test_exam_set_default(self):
        self.assertEqual(exam_set.DEFAULT_PER_TYPE, 40)

    def test_loop_cli_default(self):
        src = (PIPELINE / "realism" / "loop.py").read_text(encoding="utf-8")
        self.assertRegex(src, r'"--n-per-type", type=int, default=40')

    def test_route_default(self):
        src = (PIPELINE / "plant_hmi" / "plant_realism_routes.py").read_text(encoding="utf-8")
        self.assertRegex(src, r'n_per_type["\']?,\s*40\)')

    def test_html_input_default(self):
        src = (PIPELINE / "plant_hmi" / "static" / "plant-hmi-realism.html").read_text(encoding="utf-8")
        self.assertIn('id="n-per-type" type="number" min="1" max="500" value="40"', src)


class RealismJsSyntaxTest(unittest.TestCase):
    """node --check trên JS trang Độ thật mới/sửa cho cổng v2: lỗi cú pháp sẽ làm hỏng cả trang."""

    def test_node_check_passes(self):
        node = __import__("shutil").which("node")
        if not node:
            self.skipTest("không có node trên máy")
        static = PIPELINE / "plant_hmi" / "static"
        for name in ("plant-hmi-realism-v2.js", "plant-hmi-realism-issues.js", "plant-hmi-realism-app.js"):
            out = subprocess.run([node, "--check", str(static / name)], capture_output=True, text=True)
            self.assertEqual(out.returncode, 0, f"{name}: {out.stderr}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
