"""Độ sâu làm tối riêng cho rỗ khí (6/10): chỉ porosity/rỗ khí cụm/rỗ khí chuỗi đọc pore_post_depth_*; mặc định 0 giữ
đúng ảnh cũ (dùng độ sâu chung); loại khác không đổi dù núm rỗ khí đặt bất kỳ.
Run: .venv/bin/python3 tests/test-realism-pore-darken-depth.py
"""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from realism import knobs, loop_partial  # noqa: E402
from realism.post_darkening import darken, effective_knobs  # noqa: E402

BASE = {**knobs.DEFAULTS, "post_depth_min": 0.5, "post_depth_max": 0.7, "post_modulation": 0.6}


def _case(seed=0):
    rng = np.random.default_rng(seed)
    bg = (120 + rng.normal(0, 5, (64, 64))).astype(np.float32)
    img = bg.copy(); mask = np.zeros((64, 64), np.uint8); mask[20:40, 20:44] = 255
    img[mask > 0] += 50
    return img, bg, mask


class PoreDepth(unittest.TestCase):
    def test_default_zero_keeps_common_depth(self):
        img, bg, m = _case()
        a = darken(img, bg, m, 0.92, BASE, "porosity-1", "porosity")
        b = darken(img, bg, m, 0.92, BASE, "porosity-1", None)
        np.testing.assert_array_equal(a, b)

    def test_pore_types_use_own_depth(self):
        img, bg, m = _case()
        k = {**BASE, "pore_post_depth_min": 0.8, "pore_post_depth_max": 1.0}
        for t in ("porosity", "clustered_porosity", "linear_porosity"):
            self.assertEqual(effective_knobs(k, t)["post_depth_min"], 0.8)
            self.assertFalse(np.array_equal(darken(img, bg, m, 0.92, k, "x-1", t), darken(img, bg, m, 0.92, BASE, "x-1", t)))

    def test_other_types_unchanged(self):
        img, bg, m = _case()
        k = {**BASE, "pore_post_depth_min": 0.8, "pore_post_depth_max": 1.0}
        for t in ("crack", "lack_of_fusion", "lack_of_penetration", "slag_inclusion"):
            np.testing.assert_array_equal(darken(img, bg, m, 0.92, k, "x-1", t), darken(img, bg, m, 0.92, BASE, "x-1", t))

    def test_partial_regen_maps_pore_depth_to_pore_types_only(self):
        types = ["crack", "porosity", "lack_of_fusion", "linear_porosity"]
        cand = {**knobs.DEFAULTS, "pore_post_depth_min": 0.8, "pore_post_depth_max": 1.0}
        self.assertEqual(loop_partial.affected_types(cand, dict(knobs.DEFAULTS), types), ["porosity", "linear_porosity"])


if __name__ == "__main__":
    unittest.main()
