"""Hai lỗi thống kê ghép cặp tìm thấy khi chạy pilot độ nhạy (2/10):
1. delta = new − prev trên hai tập ca khác nhau, có lúc nằm ngoài chính CI của nó → nay delta tính trên ca chung.
2. cases chỉ chứa ca chạm lỗi nên tỉ lệ chạm lỗi bootstrap luôn 1, CI (0; 0) → nay cases có cả ca không chạm lỗi.
"""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from realism import evaluate, paired_stats  # noqa: E402
from realism.features import CRITERIA  # noqa: E402

PAIR = "CR↔crack"


def _case(cid, hit=True, used=True, **crit):
    c = {"case_id": cid, "pair": PAIR, "kind": "crack", "hit": hit, "used": used}
    if used:
        c.update({k: crit.get(k, 0.5) for k in CRITERIA})
    return c


def _result(cases):
    return {"pairs": [], "cases": cases}   # không có pairs → _measured tính từ cases


def _label(stat, crit=None):
    from realism import issues
    return next(t["label"] for i in issues.ISSUES for t in i["targets"]
                if t["pair"] == PAIR and t["stat"] == stat and (crit is None or t["crit"] == crit))


class DeltaOnCommonCases(unittest.TestCase):
    def test_delta_inside_ci_when_case_sets_differ(self):
        rng = np.random.default_rng(1)
        base_vals = rng.uniform(0.4, 0.6, 20)
        prev = [_case(f"c{i}", vung_dac=v) for i, v in enumerate(base_vals)]
        # biến thể: cùng ca tăng 0,1; thêm 6 ca chỉ có ở biến thể với giá trị rất thấp (kéo trung vị toàn bộ xuống)
        new = [_case(f"c{i}", vung_dac=v + 0.1) for i, v in enumerate(base_vals)]
        new += [_case(f"x{i}", vung_dac=0.0) for i in range(6)]
        e = paired_stats.compare_paired(_result(prev), _result(new), B=300)[_label("med", "vung_dac")]
        self.assertAlmostEqual(e["delta"], 0.1, places=6)
        self.assertLessEqual(e["ci_low"], e["delta"])
        self.assertGreaterEqual(e["ci_high"], e["delta"])
        self.assertTrue(e["significant"])
        self.assertLess(e["delta_full"], e["delta"])        # new − prev trên toàn bộ ảnh lệch hẳn delta ghép cặp

    def test_old_results_without_used_flag_still_work(self):
        prev = [{k: v for k, v in _case(f"c{i}", vung_dac=0.5).items() if k != "used"} for i in range(8)]
        new = [{k: v for k, v in _case(f"c{i}", vung_dac=0.6).items() if k != "used"} for i in range(8)]
        e = paired_stats.compare_paired(_result(prev), _result(new), B=100)[_label("med", "vung_dac")]
        self.assertAlmostEqual(e["delta"], 0.1, places=6)


class HitRateBootstrap(unittest.TestCase):
    def test_hit_rate_counts_unhit_cases(self):
        prev = [_case(f"c{i}") for i in range(20)]
        new = [_case(f"c{i}", hit=i >= 6, used=i >= 6) for i in range(20)]    # 6/20 ca mất chạm lỗi
        e = paired_stats.compare_paired(_result(prev), _result(new), B=300)[_label("hit")]
        self.assertEqual(e["n_common"], 20)
        self.assertAlmostEqual(e["delta"], -0.3, places=6)
        self.assertLess(e["ci_low"], e["ci_high"])                            # không còn CI (0; 0)
        self.assertTrue(e["significant"])

    def test_unused_cases_excluded_from_criteria_and_gate(self):
        r = _result([_case("a"), _case("b", hit=False, used=False)])
        self.assertEqual([c["case_id"] for c in paired_stats._cases_by_pair(r)[PAIR]], ["a"])
        self.assertEqual(len(paired_stats._cases_by_pair(r, used_only=False)[PAIR]), 2)


class EvaluateCompareCases(unittest.TestCase):
    def test_compare_emits_unhit_cases_with_used_flag(self):
        import pandas as pd
        row = {k: 0.5 for k in CRITERIA}
        rows = [{"kind": "crack", "case_id": "a", "empty_mask": False, "has_region": True, "hit": True, **row},
                {"kind": "crack", "case_id": "b", "empty_mask": False, "has_region": True, "hit": False, **row},
                {"kind": "crack", "case_id": "c", "empty_mask": True, "has_region": False, "hit": False, **row}]
        real = pd.DataFrame([{"cls": "CR", **{k: 0.5 + 0.01 * i for k in CRITERIA}} for i in range(10)])
        _, cases = evaluate.compare(rows, real)
        by = {c["case_id"]: c for c in cases}
        self.assertEqual(set(by), {"a", "b"})                                 # mặt nạ trống vẫn bị loại như cũ
        self.assertTrue(by["a"]["used"]) and self.assertIn("vung_dac", by["a"])
        self.assertFalse(by["b"]["used"])
        self.assertNotIn("vung_dac", by["b"])


if __name__ == "__main__":
    unittest.main()
