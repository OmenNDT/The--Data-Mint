"""Rỗ khí chuỗi có núm tạo hình riêng (5/10): kéo thuôn mạnh làm lỗ chuỗi dính thành dải. Kiểm: chuỗi chỉ đọc núm
linear_pore_*, rỗ khí đơn/cụm chỉ đọc pore_*, và cùng giá trị thì mask chuỗi y hệt cách cũ (dùng chung núm).
Run: .venv/bin/python3 tests/test-realism-linear-porosity-knobs.py
"""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from realism import knobs, loop_partial  # noqa: E402
from realism.generator_hooks import TYPE_KNOBS  # noqa: E402
from realism.mask_shaping import shape_mask  # noqa: E402


def _chain():
    m = np.zeros((128, 256), np.uint8)
    for x in range(30, 230, 28):                          # chuỗi lỗ tròn bán kính 6 cách nhau 28 px
        yy, xx = np.ogrid[:128, :256]
        m[(yy - 64) ** 2 + (xx - x) ** 2 <= 36] = 255
    return m


BASE = dict(knobs.DEFAULTS)


class LinearPorosityOwnKnobs(unittest.TestCase):
    def test_linear_ignores_shared_pore_knobs(self):
        k = {**BASE, "pore_aspect_min": 2.4, "pore_aspect_max": 2.6, "pore_irregularity_px": 3.0}
        self.assertTrue(np.array_equal(shape_mask("linear_porosity", _chain(), 7, k), _chain()))
        self.assertFalse(np.array_equal(shape_mask("porosity", _chain(), 7, k), _chain()))
        self.assertFalse(np.array_equal(shape_mask("clustered_porosity", _chain(), 7, k), _chain()))

    def test_linear_reads_own_knobs(self):
        k = {**BASE, "linear_pore_aspect_min": 1.5, "linear_pore_aspect_max": 1.5}
        self.assertFalse(np.array_equal(shape_mask("linear_porosity", _chain(), 7, k), _chain()))
        self.assertTrue(np.array_equal(shape_mask("porosity", _chain(), 7, k), _chain()))

    def test_same_values_reproduce_old_shared_behaviour(self):
        """Tách núm không đổi ảnh chuỗi khi giá trị riêng = giá trị chung cũ (cùng hàm, cùng rút ngẫu nhiên)."""
        old = {**BASE, "pore_aspect_min": 1.2769, "pore_aspect_max": 1.2769}
        new = {**BASE, "linear_pore_aspect_min": 1.2769, "linear_pore_aspect_max": 1.2769}
        np.testing.assert_array_equal(shape_mask("porosity", _chain(), 11, old),
                                      shape_mask("linear_porosity", _chain(), 11, new))

    def test_type_mapping_and_affected_types(self):
        self.assertIn("linear_pore_aspect_min", TYPE_KNOBS["linear_porosity"])
        self.assertNotIn("pore_aspect_min", TYPE_KNOBS["linear_porosity"])
        types = ["porosity", "clustered_porosity", "linear_porosity", "crack"]
        self.assertEqual(loop_partial.affected_types({**BASE, "pore_aspect_min": 2.2}, BASE, types),
                         ["porosity", "clustered_porosity"])
        self.assertEqual(loop_partial.affected_types({**BASE, "linear_pore_irregularity_px": 1.0}, BASE, types),
                         ["linear_porosity"])

    def test_min_max_swap_for_linear_pair(self):
        import json, os
        from unittest import mock
        env = {"REALISM_KNOBS": json.dumps({"linear_pore_aspect_min": 2.0, "linear_pore_aspect_max": 1.5})}
        with mock.patch.dict(os.environ, env), mock.patch.object(knobs, "read_store", return_value={}):
            v = knobs.values(knobs.resolve("production"))
        self.assertEqual((v["linear_pore_aspect_min"], v["linear_pore_aspect_max"]), (1.5, 2.0))


if __name__ == "__main__":
    unittest.main()
