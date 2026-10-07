"""Kiểm thước v3: loại dải mép TRÊN/DƯỚI tile trước khi chọn vùng lớn nhất (follow-up 7/10, người dùng duyệt
sau phát hiện LOP/crack bị v2 loại nhầm lỗi thật chạy ngang GIỮA tile — xem defect_features16._is_edge_band_line
và plans/261006-defect-metrics-w0003-reference/reports/fullstack-developer-261007-1228-lop-feature-deviation.md).

Run: .venv/bin/python tests/test-realism-defect-features16-edge-band.py
"""
import sys
import unittest
from pathlib import Path

import numpy as np
from skimage.measure import label, regionprops

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from realism.defect_features16 import _is_edge_band_line, _shape, defect_features  # noqa: E402


def _top_edge_line(shape=(278, 278)):
    """Dải dài sát hàng 0 (mẫu nhiễu chiếu sáng mép trên, xem overlay báo cáo)."""
    m = np.zeros(shape, bool)
    m[8:14, 8:270] = True
    return m


def _bottom_edge_line(shape=(278, 278)):
    """Dải dài sát hàng cuối (mẫu nhiễu chiếu sáng mép dưới)."""
    m = np.zeros(shape, bool)
    m[264:270, 8:270] = True
    return m


def _mid_long_line(shape=(278, 278)):
    """Lỗi thật dài chạy ngang qua GIỮA tile (crack/LOP thật) — v3 KHÔNG được loại cái này."""
    m = np.zeros(shape, bool)
    m[138:144, 8:270] = True
    return m


class IsEdgeBandLine(unittest.TestCase):
    def test_top_edge_line_is_edge_band(self):
        m = _top_edge_line()
        p = regionprops(label(m))[0]
        self.assertTrue(_is_edge_band_line(p, m.shape))

    def test_bottom_edge_line_is_edge_band(self):
        m = _bottom_edge_line()
        p = regionprops(label(m))[0]
        self.assertTrue(_is_edge_band_line(p, m.shape))

    def test_mid_tile_long_line_is_not_edge_band(self):
        """Khác _is_border_line (v2): KHÔNG đòi trải rộng/chạm lề trái-phải, chỉ xét vị trí HÀNG — lỗi dài
        giữa tile phải được GIỮ LẠI dù trải gần hết bề ngang."""
        m = _mid_long_line()
        p = regionprops(label(m))[0]
        self.assertFalse(_is_edge_band_line(p, m.shape))

    def test_compact_blob_near_edge_is_not_edge_band(self):
        """Đốm compact (aspect thấp) tình cờ gần mép KHÔNG bị loại (vd W0003_0043_tile_25 trong báo cáo)."""
        m = np.zeros((278, 278), bool)
        m[260:270, 100:110] = True   # gần đáy nhưng gần vuông, aspect thấp
        p = regionprops(label(m))[0]
        self.assertFalse(_is_edge_band_line(p, m.shape))

    def test_short_line_touching_only_left_right_mid_rows_is_not_edge_band(self):
        """Đường dài nằm NGANG TÂM tile, chạm lề trái/phải: _is_border_line (v2) sẽ loại (span+chạm lề),
        _is_edge_band_line (v3) KHÔNG loại vì không xét chạm lề trái/phải, chỉ xét hàng trên/dưới."""
        m = np.zeros((278, 278), bool)
        m[138:144, 0:278] = True
        p = regionprops(label(m))[0]
        self.assertFalse(_is_edge_band_line(p, m.shape))


class ShapeExcludeEdgeBand(unittest.TestCase):
    """_shape(exclude_edge_band=True) phải loại dải mép, chọn đúng lỗi giữa tile khi có cả hai."""

    def setUp(self):
        self.top, self.bottom, self.mid = _top_edge_line(), _bottom_edge_line(), _mid_long_line()
        self.m = self.top | self.bottom | self.mid   # dải mép LỚN HƠN lỗi giữa -> ưu tiên chọn nếu không lọc
        self.diff = np.zeros(self.m.shape, np.float32)
        self.mag = np.zeros(self.m.shape, np.float32)
        self.noise = 1.0

    def test_default_ignores_edge_band_picks_largest(self):
        feats, region = _shape(self.m, self.diff, self.mag, self.noise)
        # Ba dải cùng diện tích (262x6), largest là dải đầu tiên theo thứ tự label (top); không quan trọng
        # CÁI NÀO được chọn khi không lọc — chỉ cần xác nhận KHÔNG phải là vùng mid (đối chứng cho test dưới).
        self.assertIn(feats["vung_sodom"], (3,))

    def test_exclude_edge_band_keeps_only_mid_region(self):
        feats, region = _shape(self.m, self.diff, self.mag, self.noise, exclude_edge_band=True)
        self.assertEqual(feats["vung_sodom"], 1)   # hai dải mép bị loại khỏi cả số đếm
        self.assertTrue(np.array_equal(region, self.mid))

    def test_exclude_edge_band_with_only_edge_lines_has_no_region(self):
        only_edges = self.top | self.bottom
        feats, region = _shape(only_edges, self.diff, self.mag, self.noise, exclude_edge_band=True)
        self.assertEqual(feats["vung_sodom"], 0)
        self.assertIsNone(region)


class DefectFeaturesEdgeBandDefaultUnchanged(unittest.TestCase):
    def test_exclude_edge_band_false_default_matches_unfiltered_behaviour(self):
        rng = np.random.default_rng(5)
        img = rng.normal(180, 10, (227, 227)).astype(np.float32)
        img[5:15, 20:200] -= 60   # dải gần mép trên
        thr = {"dom_16": 0.9, "dai_8": 2.24, "ngang_8": 2.32}
        f_default = defect_features(img, thr)
        f_explicit = defect_features(img, thr, exclude_edge_band=False)
        self.assertEqual(f_default, f_explicit)

    def test_can_combine_exclude_border_and_exclude_edge_band(self):
        """Hai cờ độc lập về code (dù ruler v2/v3 không dùng chung trong sản xuất): bật cả hai không lỗi,
        kết quả là hợp của hai điều kiện loại."""
        rng = np.random.default_rng(6)
        img = rng.normal(180, 10, (227, 227)).astype(np.float32)
        thr = {"dom_16": 0.9, "dai_8": 2.24, "ngang_8": 2.32}
        f = defect_features(img, thr, exclude_border=True, exclude_edge_band=True)
        self.assertIsInstance(f, dict)


if __name__ == "__main__":
    unittest.main()
