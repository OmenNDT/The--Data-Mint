"""Độ sâu làm tối riêng cho nứt (7/10): chỉ crack đọc crack_post_depth_*; mặc định 0 giữ đúng ảnh cũ; loại khác không
đổi; sinh lại từng phần chỉ chạm nứt. Không thấu được chuyển sang chỉ tham khảo (thước v3 còn 6 ảnh thật có vùng).
Run: .venv/bin/python3 tests/test-realism-crack-darken-depth.py
"""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from realism import defect_eval, knobs, loop_partial  # noqa: E402
from realism.post_darkening import darken, effective_knobs  # noqa: E402

BASE = {**knobs.DEFAULTS, "post_depth_min": 0.37, "post_depth_max": 0.57, "post_modulation": 0.6}


def _case(seed=0):
    rng = np.random.default_rng(seed)
    bg = (120 + rng.normal(0, 5, (64, 64))).astype(np.float32)
    img = bg.copy(); mask = np.zeros((64, 64), np.uint8); mask[30:33, 8:56] = 255
    img[mask > 0] += 50
    return img, bg, mask


class CrackDepth(unittest.TestCase):
    def test_default_zero_keeps_common_depth(self):
        img, bg, m = _case()
        np.testing.assert_array_equal(darken(img, bg, m, 0.92, BASE, "crack-1", "crack"),
                                      darken(img, bg, m, 0.92, BASE, "crack-1", None))

    def test_crack_uses_own_depth(self):
        img, bg, m = _case()
        k = {**BASE, "crack_post_depth_min": 0.7, "crack_post_depth_max": 0.9}
        self.assertEqual(effective_knobs(k, "crack")["post_depth_min"], 0.7)
        self.assertFalse(np.array_equal(darken(img, bg, m, 0.92, k, "crack-1", "crack"),
                                        darken(img, bg, m, 0.92, BASE, "crack-1", "crack")))

    def test_other_types_unchanged(self):
        img, bg, m = _case()
        k = {**BASE, "crack_post_depth_min": 0.7, "crack_post_depth_max": 0.9}
        for t in ("porosity", "lack_of_fusion", "lack_of_penetration", "slag_inclusion"):
            np.testing.assert_array_equal(darken(img, bg, m, 0.92, k, "x-1", t), darken(img, bg, m, 0.92, BASE, "x-1", t))

    def test_partial_regen_maps_to_crack_only(self):
        types = ["crack", "porosity", "lack_of_fusion", "lack_of_penetration"]
        cand = {**knobs.DEFAULTS, "crack_post_depth_min": 0.7, "crack_post_depth_max": 0.9}
        self.assertEqual(loop_partial.affected_types(cand, dict(knobs.DEFAULTS), types), ["crack"])

    def test_lop_is_reference_only(self):
        self.assertIn("lack_of_penetration", defect_eval.REFERENCE_ONLY_TYPES)
        self.assertIn("metallic_inclusion", defect_eval.REFERENCE_ONLY_TYPES)


if __name__ == "__main__":
    unittest.main()
