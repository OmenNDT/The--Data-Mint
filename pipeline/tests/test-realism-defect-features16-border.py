"""Kiểm loại đường mép hàn trước khi chọn vùng lớn nhất (bước 2, plan 261006-defect-metrics-w0003-reference):
defect_features16._is_border_line, _shape(exclude_border=...), defect_features(exclude_border=, return_region=).

Run: .venv/bin/python tests/test-realism-defect-features16-border.py
"""
import sys
import unittest
from pathlib import Path

import numpy as np
from skimage.measure import label, regionprops

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from realism.defect_features16 import _is_border_line, _shape, defect_features  # noqa: E402


def _border_line_mask(shape=(278, 278)):
    """Đường dài chạm trái/phải, trải >85% rộng ảnh, aspect cao — mẫu "đường mép hàn"."""
    m = np.zeros(shape, bool)
    m[130:134, :] = True
    return m


def _compact_blob_mask(shape=(278, 278)):
    """Đốm tròn nhỏ không chạm biên, TÁCH RỜI khỏi đường mép hàn (hàng 130:134) — mẫu "lỗi thật"."""
    m = np.zeros(shape, bool)
    m[40:60, 120:140] = True
    return m


class IsBorderLine(unittest.TestCase):
    def test_long_horizontal_line_touching_both_sides_is_border_line(self):
        m = _border_line_mask()
        p = regionprops(label(m))[0]
        self.assertTrue(_is_border_line(p, m.shape))

    def test_compact_central_blob_is_not_border_line(self):
        m = _compact_blob_mask()
        p = regionprops(label(m))[0]
        self.assertFalse(_is_border_line(p, m.shape))

    def test_short_line_touching_one_side_but_not_spanning_is_not_border_line(self):
        m = np.zeros((278, 278), bool)
        m[130:134, 0:60] = True   # chạm trái nhưng chỉ trải ~22% rộng ảnh, dưới BORDER_SPAN_MIN
        p = regionprops(label(m))[0]
        self.assertFalse(_is_border_line(p, m.shape))

    def test_compact_blob_touching_border_but_low_aspect_is_not_border_line(self):
        m = np.zeros((278, 278), bool)
        m[0:40, 0:40] = True   # chạm góc nhưng gần vuông (aspect thấp), không phải đường dài
        p = regionprops(label(m))[0]
        self.assertFalse(_is_border_line(p, m.shape))


class ShapeExcludeBorder(unittest.TestCase):
    """_shape phải chọn đúng đốm thật khi loại đường mép hàn, và giữ đúng hành vi cũ khi exclude_border=False."""

    def setUp(self):
        self.line, self.blob = _border_line_mask(), _compact_blob_mask()
        self.m = self.line | self.blob   # đường mép hàn to hơn đốm thật -> ưu tiên chọn nếu không lọc
        self.diff = np.zeros(self.m.shape, np.float32)
        self.mag = np.zeros(self.m.shape, np.float32)
        self.noise = 1.0

    def test_default_picks_largest_region_ignoring_border(self):
        feats, region = _shape(self.m, self.diff, self.mag, self.noise)
        self.assertAlmostEqual(feats["vung_lon"], self.line.sum() / self.m.size, places=6)
        self.assertTrue(np.array_equal(region, self.line))

    def test_exclude_border_picks_the_compact_defect_instead(self):
        feats, region = _shape(self.m, self.diff, self.mag, self.noise, exclude_border=True)
        self.assertAlmostEqual(feats["vung_lon"], self.blob.sum() / self.m.size, places=6)
        self.assertTrue(np.array_equal(region, self.blob))
        self.assertEqual(feats["vung_sodom"], 1)   # đường mép hàn bị loại khỏi cả số đếm đốm

    def test_exclude_border_with_only_border_line_present_has_no_region(self):
        feats, region = _shape(self.line, self.diff, self.mag, self.noise, exclude_border=True)
        self.assertEqual(feats["vung_sodom"], 0)
        self.assertEqual(feats["vung_lon"], 0.0)
        self.assertIsNone(region)


class DefectFeaturesReturnRegion(unittest.TestCase):
    def test_return_region_false_keeps_old_two_value_unpack_contract(self):
        rng = np.random.default_rng(2)
        img = rng.normal(180, 10, (227, 227)).astype(np.float32)
        thr = {"dom_16": 0.9, "dai_8": 2.24, "ngang_8": 2.32}
        f = defect_features(img, thr)
        self.assertIsInstance(f, dict)

    def test_return_region_true_yields_tuple_with_mask_or_none(self):
        rng = np.random.default_rng(3)
        img = rng.normal(180, 10, (227, 227)).astype(np.float32)
        img[90:140, 90:140] -= 60
        thr = {"dom_16": 0.9, "dai_8": 2.24, "ngang_8": 2.32}
        f, region = defect_features(img, thr, return_region=True)
        self.assertIsInstance(f, dict)
        if f["vung_sodom"] > 0:
            self.assertIsInstance(region, np.ndarray)
            self.assertEqual(region.dtype, bool)
        else:
            self.assertIsNone(region)

    def test_exclude_border_false_default_matches_unfiltered_behaviour(self):
        """exclude_border mặc định False: kết quả PHẢI khớp byte-for-byte hành vi trước khi thêm tham số này
        (ruler v1 đang chạy sản xuất không được đổi, xem hard constraint)."""
        rng = np.random.default_rng(4)
        img = rng.normal(180, 10, (227, 227)).astype(np.float32)
        img[30:60, 190:220] -= 60   # vùng tối gần biên phải
        thr = {"dom_16": 0.9, "dai_8": 2.24, "ngang_8": 2.32}
        f_default = defect_features(img, thr)
        f_explicit = defect_features(img, thr, exclude_border=False)
        self.assertEqual(f_default, f_explicit)


if __name__ == "__main__":
    unittest.main()
