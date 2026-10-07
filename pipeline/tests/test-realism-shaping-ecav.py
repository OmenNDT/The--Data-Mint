"""Test mask_shaping_ecav.shape: núm 0 không đổi hành vi cũ; núm > 0 xoay vùng, giữ diện tích,
giữ vùng trong khung ảnh, xác định theo seed (rng).
Viết theo unittest như các test khác (venv dự án không có pytest).
Run: .venv/bin/python3 tests/test-realism-shaping-ecav.py
"""
import sys
import unittest
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from realism import mask_shaping_ecav as ecav  # noqa: E402


def _horizontal_bar(h=200, w=300, y0=95, y1=106, x0=50, x1=200):
    m = np.zeros((h, w), dtype=bool)
    m[y0:y1, x0:x1] = True
    return m


class EcavShape(unittest.TestCase):
    def test_zero_knob_returns_same_mask(self):
        m = _horizontal_bar()
        out = ecav.shape(m, np.random.default_rng(1), {"ecav_tilt_max_deg": 0.0})
        self.assertTrue(out is m or np.array_equal(out, m))

    def test_empty_mask_returns_unchanged(self):
        m = np.zeros((100, 100), dtype=bool)
        self.assertTrue(np.array_equal(ecav.shape(m, np.random.default_rng(1), {"ecav_tilt_max_deg": 45.0}), m))

    def test_missing_knob_defaults_to_zero(self):
        m = _horizontal_bar()
        self.assertTrue(np.array_equal(ecav.shape(m, np.random.default_rng(1), {}), m))

    def test_positive_knob_preserves_area_and_stays_inside_frame(self):
        for tilt_max in (15.0, 30.0, 45.0, 60.0):
            with self.subTest(tilt_max=tilt_max):
                m = _horizontal_bar()
                out = ecav.shape(m, np.random.default_rng(42), {"ecav_tilt_max_deg": tilt_max})
                # diện tích giữ nguyên trong sai số làm tròn láng giềng gần nhất của phép xoay
                self.assertLessEqual(abs(int(out.sum()) - int(m.sum())), max(2, int(0.1 * m.sum())))
                rows, cols = np.nonzero(out)
                self.assertGreaterEqual(rows.min(), ecav.FRAME_MARGIN)
                self.assertLessEqual(rows.max(), m.shape[0] - 1 - ecav.FRAME_MARGIN)
                self.assertGreaterEqual(cols.min(), ecav.FRAME_MARGIN)
                self.assertLessEqual(cols.max(), m.shape[1] - 1 - ecav.FRAME_MARGIN)

    def test_rotation_changes_orientation_on_average(self):
        """Vùng dài theo trục x xoay nhiều thì số hàng chiếm (bbox dọc) phải rộng ra."""
        m = _horizontal_bar()
        base_rows = np.nonzero(m.any(1))[0]
        base_height = base_rows.max() - base_rows.min() + 1
        rng = np.random.default_rng(7)
        heights = []
        for _ in range(30):
            rows = np.nonzero(ecav.shape(m, rng, {"ecav_tilt_max_deg": 60.0}).any(1))[0]
            heights.append(rows.max() - rows.min() + 1)
        self.assertGreater(np.mean(heights), base_height * 1.3)

    def test_deterministic_given_same_rng_state(self):
        m = _horizontal_bar()
        a = ecav.shape(m, np.random.default_rng(99), {"ecav_tilt_max_deg": 30.0})
        b = ecav.shape(m, np.random.default_rng(99), {"ecav_tilt_max_deg": 30.0})
        self.assertTrue(np.array_equal(a, b))

    def test_multiple_components_shaped_independently(self):
        m = np.zeros((200, 300), dtype=bool)
        m[20:28, 30:120] = True     # vùng 1: trên
        m[150:158, 180:260] = True  # vùng 2: dưới
        out = ecav.shape(m, np.random.default_rng(3), {"ecav_tilt_max_deg": 45.0})
        lab, n = ndi.label(out)
        self.assertEqual(n, 2)
        for area_before, obj in zip((m[20:28, 30:120].sum(), m[150:158, 180:260].sum()), range(1, 3)):
            self.assertLessEqual(abs(int((lab == obj).sum()) - int(area_before)), max(2, int(0.1 * area_before)))


if __name__ == "__main__":
    unittest.main()
