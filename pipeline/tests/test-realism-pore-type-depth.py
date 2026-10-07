"""Độ sâu làm tối riêng cho rỗ khí cụm/chuỗi (nhánh A phase 2, plan 261006-defect-metrics-w0003-reference).

Kiểm effective_knobs trong realism/post_darkening.py: thứ tự ưu tiên độ sâu làm tối là
clustered_post_depth_*/linear_post_depth_* (riêng dạng) > pore_post_depth_* (riêng rỗ khí) >
post_depth_* (chung). Mỗi mức chỉ áp dụng khi CẢ cận dưới và cận trên > 0.

Run: .venv/bin/python3 tests/test-realism-pore-type-depth.py
"""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from realism import knobs  # noqa: E402
from realism.post_darkening import darken, effective_knobs  # noqa: E402

BASE = dict(knobs.DEFAULTS)


def _mask():
    m = np.zeros((64, 64), np.uint8)
    m[20:44, 20:44] = 255
    return m


class EffectiveKnobsDefaults(unittest.TestCase):
    """Mặc định (mọi độ sâu riêng = 0): effective_knobs trả về chính knobs gốc, không đổi gì,
    cho cả 3 dạng rỗ khí và loại khác."""

    def test_defaults_passthrough_for_all_pore_types(self):
        for t in ("porosity", "clustered_porosity", "linear_porosity", "crack", None):
            self.assertEqual(effective_knobs(BASE, t), BASE)

    def test_defaults_identical_pixels_for_all_pore_types(self):
        img = np.full((64, 64), 0.5, np.float32)
        mask = _mask()
        for t in ("porosity", "clustered_porosity", "linear_porosity"):
            out = darken(img, None, mask, 0.9, BASE, key="k", defect_type=t)
            expect = darken(img, None, mask, 0.9, BASE, key="k", defect_type=None)
            self.assertTrue(np.allclose(out, expect), f"defect_type={t} phải giống hành vi cũ")


class EffectiveKnobsPrecedence(unittest.TestCase):
    def test_clustered_uses_own_knob_over_pore_shared(self):
        k = {**BASE, "pore_post_depth_min": 0.8, "pore_post_depth_max": 1.0,
             "clustered_post_depth_min": 0.3, "clustered_post_depth_max": 0.5}
        eff = effective_knobs(k, "clustered_porosity")
        self.assertEqual((eff["post_depth_min"], eff["post_depth_max"]), (0.3, 0.5))

    def test_linear_uses_own_knob_over_pore_shared(self):
        k = {**BASE, "pore_post_depth_min": 0.8, "pore_post_depth_max": 1.0,
             "linear_post_depth_min": 1.0, "linear_post_depth_max": 1.0}
        eff = effective_knobs(k, "linear_porosity")
        self.assertEqual((eff["post_depth_min"], eff["post_depth_max"]), (1.0, 1.0))

    def test_clustered_falls_back_to_pore_shared_when_own_zero(self):
        k = {**BASE, "pore_post_depth_min": 0.8, "pore_post_depth_max": 1.0}
        eff = effective_knobs(k, "clustered_porosity")
        self.assertEqual((eff["post_depth_min"], eff["post_depth_max"]), (0.8, 1.0))

    def test_linear_falls_back_to_pore_shared_when_own_zero(self):
        k = {**BASE, "pore_post_depth_min": 0.8, "pore_post_depth_max": 1.0}
        eff = effective_knobs(k, "linear_porosity")
        self.assertEqual((eff["post_depth_min"], eff["post_depth_max"]), (0.8, 1.0))

    def test_plain_porosity_ignores_clustered_and_linear_knobs(self):
        k = {**BASE, "clustered_post_depth_min": 0.3, "clustered_post_depth_max": 0.5,
             "linear_post_depth_min": 1.0, "linear_post_depth_max": 1.0}
        eff = effective_knobs(k, "porosity")
        self.assertEqual((eff["post_depth_min"], eff["post_depth_max"]),
                         (BASE["post_depth_min"], BASE["post_depth_max"]))

    def test_non_pore_type_unaffected_by_any_pore_knob(self):
        k = {**BASE, "pore_post_depth_min": 0.8, "pore_post_depth_max": 1.0,
             "clustered_post_depth_min": 0.3, "clustered_post_depth_max": 0.5,
             "linear_post_depth_min": 1.0, "linear_post_depth_max": 1.0}
        for t in ("crack", "lack_of_fusion", "undercut", None):
            self.assertEqual(effective_knobs(k, t), k)

    def test_requires_both_bounds_positive_else_falls_through(self):
        k = {**BASE, "pore_post_depth_min": 0.8, "pore_post_depth_max": 1.0,
             "clustered_post_depth_min": 0.3, "clustered_post_depth_max": 0.0}   # chỉ 1 cận > 0
        eff = effective_knobs(k, "clustered_porosity")
        self.assertEqual((eff["post_depth_min"], eff["post_depth_max"]), (0.8, 1.0))


if __name__ == "__main__":
    unittest.main()
