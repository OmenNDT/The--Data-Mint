"""Cổng nghiệm thu chỉ đếm mục tiêu trên các cặp loại có ở CẢ HAI vòng (lỗi thấy 2/10: vòng 4 loại "tốt hơn rõ"
vòng chỉ có lỗi không ngấu vì "đạt 14 so 3 mục tiêu").
Run: .venv/bin/python3 tests/test-realism-gate-common-pairs.py
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from realism import loop_gate  # noqa: E402


def _crit(**over):
    base = {"syn_med": 1.0, "real_med": 1.0, "auc": 0.5, "syn_iqr": [0.5, 1.5], "syn_lt45": 0.4}
    return {**base, **over}


def _pair(pair, synthetic, c2st):
    crit = {k: _crit() for k in ("bien_doc", "bien_daodong", "vung_huong", "vung_dac", "vung_dayhop", "vung_lechtam")}
    return {"pair": pair, "synthetic": synthetic, "hit": 0.9, "c2st": c2st, "crit": crit}


class ScoreOnCommonPairs(unittest.TestCase):
    def setUp(self):
        self.lf = _pair("LP↔lack_of_fusion", "lack_of_fusion", 0.7)
        self.cr = _pair("CR↔crack", "crack", 0.9)

    def test_extra_types_do_not_add_targets(self):
        only_lf, four = {"pairs": [self.lf]}, {"pairs": [self.lf, self.cr]}
        common = ["LP↔lack_of_fusion"]
        self.assertEqual(loop_gate.score(only_lf, None, common)[0], loop_gate.score(four, None, common)[0])
        self.assertGreater(loop_gate.score(four)[0], loop_gate.score(only_lf)[0])     # không lọc thì lệch như lỗi cũ

    def test_c2st_mean_restricted_to_common_pairs(self):
        four = {"pairs": [self.lf, self.cr]}
        self.assertAlmostEqual(loop_gate.score(four, None, ["LP↔lack_of_fusion"])[1], 0.7)


if __name__ == "__main__":
    unittest.main()
