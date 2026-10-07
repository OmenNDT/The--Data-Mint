"""Tạo hình lại mask không ngấu (lof_length_scale, lof_width_scale, lof_gap_max, nhánh D pha 2 thước mới).
Kiểm: núm mặc định trả nguyên mask, rút ngắn giảm nhịp cột, thu mỏng giảm diện tích giữ nhịp cột, cắt khoảng đứt
làm tăng số vùng tách rời (vung_sodom), và toàn bộ hàm shape() quyết định (seed giống nhau cho kết quả giống nhau).
Run: .venv/bin/python3 tests/test-realism-shaping-lof.py
"""
import sys
import unittest
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from realism import knobs  # noqa: E402
from realism.mask_shaping import shape_mask  # noqa: E402
from realism import mask_shaping_lof as lof  # noqa: E402

BASE = dict(knobs.DEFAULTS)


def _band(width=256, height=128, x0=40, x1=216, y0=60, y1=70):
    """Dải không ngấu nằm ngang, liền khối, mô phỏng mask bộ sinh gốc (fillPoly)."""
    m = np.zeros((height, width), bool)
    m[y0:y1, x0:x1] = True
    return m


def _span(m):
    cols = np.nonzero(m.any(0))[0]
    return int(cols.max() - cols.min() + 1) if cols.size else 0


class LofShapeDefaults(unittest.TestCase):
    def test_default_knobs_return_same_mask(self):
        m = _band()
        out = lof.shape(m, np.random.default_rng(1), BASE)
        np.testing.assert_array_equal(out, m)

    def test_shape_mask_dispatch_default_is_noop(self):
        m = _band()
        mask_u8 = (m * 255).astype(np.uint8)
        out = shape_mask("lack_of_fusion", mask_u8, 1, BASE)
        np.testing.assert_array_equal(out, mask_u8)

    def test_empty_mask_stays_empty(self):
        m = np.zeros((128, 256), bool)
        k = {**BASE, "lof_length_scale": 0.5, "lof_width_scale": 0.5, "lof_gap_max": 3}
        out = lof.shape(m, np.random.default_rng(1), k)
        self.assertFalse(out.any())


class LofShorten(unittest.TestCase):
    def test_length_scale_shrinks_column_span(self):
        m = _band()
        before = _span(m)
        k = {**BASE, "lof_length_scale": 0.5}
        out = lof.shape(m, np.random.default_rng(3), k)
        after = _span(out)
        self.assertLess(after, before)
        self.assertAlmostEqual(after / before, 0.5, delta=0.05)

    def test_length_scale_one_is_noop(self):
        m = _band()
        out = lof._shorten(m, np.random.default_rng(2), 1.0)
        np.testing.assert_array_equal(out, m)


class LofThin(unittest.TestCase):
    def test_width_scale_reduces_area_keeps_span(self):
        m = _band()
        before_area = m.sum()
        before_span = _span(m)
        out = lof._thin(m, 0.5)
        self.assertLess(out.sum(), before_area)
        self.assertEqual(_span(out), before_span)

    def test_width_scale_one_is_noop(self):
        m = _band()
        out = lof._thin(m, 1.0)
        np.testing.assert_array_equal(out, m)


class LofGap(unittest.TestCase):
    def test_gap_max_increases_region_count(self):
        m = _band()
        k = {**BASE, "lof_gap_max": 3}
        out = lof.shape(m, np.random.default_rng(5), k)
        _, n_before = ndi.label(m)
        _, n_after = ndi.label(out)
        self.assertEqual(n_before, 1)
        self.assertGreaterEqual(n_after, 2)

    def test_gap_max_zero_is_noop(self):
        m = _band()
        out = lof._gap(m, np.random.default_rng(4), 0)
        np.testing.assert_array_equal(out, m)

    def test_short_band_skips_gap(self):
        m = _band(x0=100, x1=140)                        # nhịp cột < MIN_COLS_FOR_GAP
        out = lof._gap(m, np.random.default_rng(4), 3)
        np.testing.assert_array_equal(out, m)


class LofDeterminism(unittest.TestCase):
    def test_same_seed_same_result(self):
        m = _band()
        k = {**BASE, "lof_length_scale": 0.6, "lof_width_scale": 0.6, "lof_gap_max": 2}
        a = lof.shape(m, np.random.default_rng(42), k)
        b = lof.shape(m, np.random.default_rng(42), k)
        np.testing.assert_array_equal(a, b)

    def test_shape_mask_seed_reproducible(self):
        mask_u8 = (_band() * 255).astype(np.uint8)
        k = {**BASE, "lof_length_scale": 0.6, "lof_width_scale": 0.6, "lof_gap_max": 2}
        a = shape_mask("lack_of_fusion", mask_u8, 123, k)
        b = shape_mask("lack_of_fusion", mask_u8, 123, k)
        np.testing.assert_array_equal(a, b)


if __name__ == "__main__":
    unittest.main()
