"""Tạo hình lại mask xỉ (realism/mask_shaping_slag.py): núm ở mặc định giữ nguyên mask, mỗi núm có hiệu ứng
riêng (phóng diện tích, kéo dài, làm méo biên), xử lý đúng khi mask có nhiều vùng tách biệt hoặc sát biên ảnh.
Run: .venv/bin/python3 tests/test-realism-shaping-slag.py
"""
import sys
import unittest
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi
from scipy.spatial import ConvexHull

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from realism import knobs  # noqa: E402
from realism.mask_shaping_slag import shape  # noqa: E402

BASE = dict(knobs.DEFAULTS)


def _circle(shape_hw=(160, 160), center=(80, 80), r=18):
    m = np.zeros(shape_hw, bool)
    yy, xx = np.ogrid[:shape_hw[0], :shape_hw[1]]
    m[(yy - center[0]) ** 2 + (xx - center[1]) ** 2 <= r * r] = True
    return m


def _solidity(mask):
    ys, xs = np.nonzero(mask)
    hull = ConvexHull(np.c_[xs, ys])
    return mask.sum() / hull.volume


class SlagShapeDefault(unittest.TestCase):
    def test_default_knobs_return_mask_unchanged(self):
        m = _circle()
        out = shape(m, np.random.default_rng(1), BASE)
        self.assertTrue(np.array_equal(out, m))

    def test_empty_mask_returns_unchanged(self):
        m = np.zeros((64, 64), bool)
        out = shape(m, np.random.default_rng(1), {**BASE, "slag_scale": 8})
        self.assertTrue(np.array_equal(out, m))


class SlagShapeScale(unittest.TestCase):
    def test_scale_grows_area_by_requested_factor(self):
        m = _circle()
        k = {**BASE, "slag_scale": 8.0}
        out = shape(m, np.random.default_rng(2), k)
        ratio = out.sum() / m.sum()
        self.assertGreater(ratio, 6.5)
        self.assertLess(ratio, 9.5)

    def test_scale_at_default_one_has_no_area_effect_alone(self):
        m = _circle()
        k = {**BASE, "slag_scale": 1.0, "slag_elongation": 1.0, "slag_irregularity_px": 0.0}
        out = shape(m, np.random.default_rng(2), k)
        self.assertTrue(np.array_equal(out, m))


class SlagShapeElongation(unittest.TestCase):
    def test_elongation_stretches_bbox_and_preserves_area(self):
        m = _circle()
        k = {**BASE, "slag_elongation": 4.0}
        out = shape(m, np.random.default_rng(3), k)
        ys, xs = np.nonzero(out)
        w, h = xs.max() - xs.min(), ys.max() - ys.min()
        self.assertGreater(w, h * 1.8)                     # dẹt rõ theo phương ngang (trục hàn)
        ratio = out.sum() / m.sum()
        self.assertAlmostEqual(ratio, 1.0, delta=0.15)      # kéo dài gần giữ nguyên diện tích


class SlagShapeIrregularity(unittest.TestCase):
    def test_irregularity_reduces_solidity_monotonically(self):
        m = _circle()
        k0 = {**BASE, "slag_scale": 6.0, "slag_elongation": 3.0, "slag_irregularity_px": 0.0}
        k1 = {**BASE, "slag_scale": 6.0, "slag_elongation": 3.0, "slag_irregularity_px": 8.0}
        sol0 = _solidity(shape(m, np.random.default_rng(10), k0))
        sol1 = _solidity(shape(m, np.random.default_rng(10), k1))
        self.assertLess(sol1, sol0)


class SlagShapeMultiRegion(unittest.TestCase):
    def test_two_separate_blobs_stay_centered_independently(self):
        m = np.zeros((160, 300), bool)
        m |= _circle((160, 300), (50, 60), 10)
        m |= _circle((160, 300), (110, 220), 10)
        k = {**BASE, "slag_scale": 3.0, "slag_elongation": 2.0, "slag_irregularity_px": 2.0}
        out = shape(m, np.random.default_rng(7), k)
        lab, n = ndi.label(out)
        self.assertEqual(n, 2)
        coms = ndi.center_of_mass(out, lab, range(1, n + 1))
        coms = sorted(coms, key=lambda c: c[1])
        self.assertAlmostEqual(coms[0][0], 50, delta=3)
        self.assertAlmostEqual(coms[0][1], 60, delta=3)
        self.assertAlmostEqual(coms[1][0], 110, delta=3)
        self.assertAlmostEqual(coms[1][1], 220, delta=3)

    def test_blob_near_image_edge_does_not_crash(self):
        m = _circle((100, 100), (5, 5), 8)
        k = {**BASE, "slag_scale": 10.0, "slag_elongation": 5.0, "slag_irregularity_px": 6.0}
        out = shape(m, np.random.default_rng(8), k)
        self.assertEqual(out.shape, m.shape)
        self.assertTrue(out.any())


class SlagShapeOutputContract(unittest.TestCase):
    def test_output_shape_and_dtype(self):
        m = _circle()
        k = {**BASE, "slag_scale": 5.0, "slag_elongation": 2.0, "slag_irregularity_px": 3.0}
        out = shape(m, np.random.default_rng(4), k)
        self.assertEqual(out.shape, m.shape)
        self.assertEqual(out.dtype, bool)


if __name__ == "__main__":
    unittest.main()
