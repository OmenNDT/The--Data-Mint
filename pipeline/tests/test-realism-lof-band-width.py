"""Núm lof_band_width_scale (vòng 2 không ngấu, 7/10): co band_width_range GỐC của bộ sinh lack_of_fusion
TẠI SINH (trước fillPoly + feather), khác lof_width_scale hậu kỳ (affine siết quanh tâm toàn khối, đã thử
và làm hỏng khả năng phát hiện). Kiểm: núm mặc định trả {} (không đổi kwargs bộ sinh, mask y nguyên pixel),
núm < 1.0 co band_width_range đúng tỉ lệ, TYPE_KNOBS/DARKEN_TYPE_KNOBS nối dây đúng loại, và worker mask sinh
ra mask hẹp hơn khi núm < 1.0 với cùng seed.
Run: .venv/bin/python3 tests/test-realism-lof-band-width.py
"""
import json
import os
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mask_generator import LackOfFusionMaskGenerator  # noqa: E402
from realism import knobs  # noqa: E402
from realism.generator_hooks import LOF_BASE_BAND_WIDTH_RANGE, TYPE_KNOBS, lof_generation_kwargs  # noqa: E402
from realism.loop_partial import DARKEN_TYPE_KNOBS, affected_types  # noqa: E402


class LofGenerationKwargsDefault(unittest.TestCase):
    def setUp(self):
        os.environ.pop("REALISM_KNOBS", None)
        os.environ.pop("REALISM_KNOBS_FROZEN", None)

    def tearDown(self):
        os.environ.pop("REALISM_KNOBS", None)
        os.environ.pop("REALISM_KNOBS_FROZEN", None)

    def test_default_returns_empty_kwargs(self):
        self.assertEqual(lof_generation_kwargs(), {})

    def test_default_knob_value_is_old_band_width_range_identity(self):
        # mặc định (1.0) không đổi hành vi: sinh với và không có kwargs phải giống hệt từng điểm ảnh
        kw = lof_generation_kwargs()
        g1 = LackOfFusionMaskGenerator(height=256, width=256, seed=7, weld_center_y=128)
        g2 = LackOfFusionMaskGenerator(height=256, width=256, seed=7, weld_center_y=128, **kw)
        m1, f1 = g1.generate()
        m2, f2 = g2.generate()
        np.testing.assert_array_equal(m1, m2)
        np.testing.assert_array_equal(f1, f2)


class LofGenerationKwargsScaled(unittest.TestCase):
    def setUp(self):
        os.environ.pop("REALISM_KNOBS_FROZEN", None)

    def tearDown(self):
        os.environ.pop("REALISM_KNOBS", None)
        os.environ.pop("REALISM_KNOBS_FROZEN", None)

    def _with_scale(self, scale):
        os.environ["REALISM_KNOBS"] = json.dumps({"lof_band_width_scale": scale})
        return lof_generation_kwargs()

    def test_scale_half_narrows_band_width_range(self):
        kw = self._with_scale(0.5)
        lo, hi = LOF_BASE_BAND_WIDTH_RANGE
        self.assertEqual(kw["band_width_range"], (round(lo * 0.5), round(hi * 0.5)))

    def test_scale_narrows_mask_area_deterministically(self):
        kw_default = {}
        kw_narrow = self._with_scale(0.4)
        for seed in (1, 2, 3):
            g_def = LackOfFusionMaskGenerator(height=512, width=512, seed=seed, weld_center_y=256, **kw_default)
            g_nar = LackOfFusionMaskGenerator(height=512, width=512, seed=seed, weld_center_y=256, **kw_narrow)
            m_def, _ = g_def.generate()
            m_nar, _ = g_nar.generate()
            self.assertLess(int(m_nar.sum()), int(m_def.sum()))

    def test_bad_env_value_falls_back_to_empty_kwargs(self):
        os.environ["REALISM_KNOBS"] = "not json"
        self.assertEqual(lof_generation_kwargs(), {})

    def test_other_defect_types_unaffected_no_kwarg_path(self):
        # extra_kwargs trong worker chỉ áp cho lack_of_fusion; hàm này chỉ tính cho loại đó, không có đường gọi
        # tương đương cho loại khác nên không kiểm ở đây — chỉ đảm bảo hàm không ném lỗi khi gọi lại nhiều lần.
        for _ in range(3):
            lof_generation_kwargs()


class LofBandWidthKnobWiring(unittest.TestCase):
    def test_registered_in_type_knobs_lack_of_fusion(self):
        self.assertIn("lof_band_width_scale", TYPE_KNOBS["lack_of_fusion"])

    def test_default_in_registry_matches_old_behaviour(self):
        self.assertEqual(knobs.DEFAULTS["lof_band_width_scale"], 1.0)

    def test_not_a_darken_knob(self):
        self.assertNotIn("lof_band_width_scale", DARKEN_TYPE_KNOBS)

    def test_changing_knob_only_affects_lack_of_fusion_in_partial_regen(self):
        best = dict(knobs.DEFAULTS)
        cand = dict(knobs.DEFAULTS, lof_band_width_scale=0.5)
        selected = ["lack_of_fusion", "crack", "porosity"]
        self.assertEqual(affected_types(cand, best, selected), ["lack_of_fusion"])


if __name__ == "__main__":
    unittest.main()
