"""Test núm Không thấu (lack_of_penetration) mới (bước 3 báo cáo fullstack-developer-261007):
- lop_length_scale (mask_shaping._lop): kéo dài mặt nạ theo chiều ngang quanh tâm, giữ bề dày; 1,0 = hành vi cũ.
- lop_post_depth_min/max (post_darkening.effective_knobs): độ sâu làm tối riêng; 0 là dùng chung post_depth_*.
Viết theo unittest như các test khác (venv dự án không có pytest).
Run: .venv/bin/python3 tests/test-realism-shaping-lop.py
"""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from realism import knobs, loop_partial  # noqa: E402
from realism.mask_shaping import _lop, shape_mask  # noqa: E402
from realism.post_darkening import darken, effective_knobs  # noqa: E402

BASE_SHAPE = {**knobs.DEFAULTS}


def _horizontal_bar(h=200, w=400, y0=96, y1=104, x0=100, x1=300):
    m = np.zeros((h, w), dtype=bool)
    m[y0:y1, x0:x1] = True
    return m


class LopLengthScale(unittest.TestCase):
    def test_default_scale_returns_same_mask(self):
        m = _horizontal_bar()
        out = _lop(m, np.random.default_rng(1), BASE_SHAPE)
        self.assertTrue(np.array_equal(out, m))

    def test_missing_knob_defaults_to_one(self):
        m = _horizontal_bar()
        out = _lop(m, np.random.default_rng(1), {"lop_tilt_max_deg": 0.0, "lop_wave_amp_px": 0.0, "lop_gap_max": 0})
        self.assertTrue(np.array_equal(out, m))

    def test_scale_above_one_extends_width_keeps_thickness(self):
        m = _horizontal_bar()
        base_cols = np.nonzero(m.any(0))[0]
        base_width = base_cols.max() - base_cols.min() + 1
        base_rows = np.nonzero(m.any(1))[0]
        base_thickness = base_rows.max() - base_rows.min() + 1
        k = {**BASE_SHAPE, "lop_length_scale": 1.3}
        out = _lop(m, np.random.default_rng(2), k)
        cols = np.nonzero(out.any(0))[0]
        rows = np.nonzero(out.any(1))[0]
        width = cols.max() - cols.min() + 1
        thickness = rows.max() - rows.min() + 1
        self.assertGreater(width, base_width * 1.15)
        self.assertLessEqual(abs(thickness - base_thickness), 2)   # bề dày không đổi quá 2 px (sai số láng giềng gần nhất)

    def test_empty_mask_returns_unchanged(self):
        m = np.zeros((100, 100), dtype=bool)
        k = {**BASE_SHAPE, "lop_length_scale": 1.5}
        self.assertTrue(np.array_equal(_lop(m, np.random.default_rng(1), k), m))

    def test_shape_mask_dispatch_triggers_on_length_scale_alone(self):
        """Núm khác đều mặc định, chỉ lop_length_scale khác 1 vẫn phải tạo hình lại (generator_hooks.TYPE_KNOBS)."""
        m = (_horizontal_bar() * 255).astype(np.uint8)
        k = {**BASE_SHAPE, "lop_length_scale": 1.3}
        out = shape_mask("lack_of_penetration", m, seed=5, knobs=k)
        self.assertFalse(np.array_equal(out, m))


class LopPostDepth(unittest.TestCase):
    BASE = {**knobs.DEFAULTS, "post_depth_min": 0.5, "post_depth_max": 0.7, "post_modulation": 0.6}

    def _case(self, seed=0):
        rng = np.random.default_rng(seed)
        bg = (120 + rng.normal(0, 5, (64, 64))).astype(np.float32)
        img = bg.copy(); mask = np.zeros((64, 64), np.uint8); mask[28:36, 10:54] = 255
        img[mask > 0] += 50
        return img, bg, mask

    def test_default_zero_keeps_common_depth(self):
        img, bg, m = self._case()
        a = darken(img, bg, m, 0.92, self.BASE, "lop-1", "lack_of_penetration")
        b = darken(img, bg, m, 0.92, self.BASE, "lop-1", None)
        np.testing.assert_array_equal(a, b)

    def test_lop_knob_overrides_depth_for_lop_only(self):
        img, bg, m = self._case()
        k = {**self.BASE, "lop_post_depth_min": 0.15, "lop_post_depth_max": 0.3}
        self.assertEqual(effective_knobs(k, "lack_of_penetration")["post_depth_min"], 0.15)
        self.assertFalse(np.array_equal(
            darken(img, bg, m, 0.92, k, "x-1", "lack_of_penetration"),
            darken(img, bg, m, 0.92, self.BASE, "x-1", "lack_of_penetration")))

    def test_other_types_unchanged(self):
        img, bg, m = self._case()
        k = {**self.BASE, "lop_post_depth_min": 0.15, "lop_post_depth_max": 0.3}
        for t in ("crack", "lack_of_fusion", "porosity", "slag_inclusion"):
            np.testing.assert_array_equal(darken(img, bg, m, 0.92, k, "x-1", t), darken(img, bg, m, 0.92, self.BASE, "x-1", t))

    def test_partial_regen_maps_lop_depth_to_lop_only(self):
        types = ["crack", "lack_of_penetration", "lack_of_fusion", "porosity"]
        cand = {**knobs.DEFAULTS, "lop_post_depth_min": 0.15, "lop_post_depth_max": 0.3}
        self.assertEqual(loop_partial.affected_types(cand, dict(knobs.DEFAULTS), types), ["lack_of_penetration"])


if __name__ == "__main__":
    unittest.main()
