"""Kiểm thước v3 (edge-band) nối dây theo loại (follow-up 7/10): reference_w0003.ruler_for trả v3 cho
crack/lack_of_penetration, defect_eval.evaluate_defects(ruler=None) dùng ĐÚNG v3 cho hai loại này và v2 cho
loại khác, RULERS["...v3"] trỏ tệp riêng (không đụng v1/v2).

Run: .venv/bin/python tests/test-realism-ruler-v3-edge-band.py
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from realism import defect_eval as de  # noqa: E402
from realism.reference_w0003 import (  # noqa: E402
    CALIBRATION_PATH, RULER_V2, RULER_V3, RULERS, ruler_for, W0003_DEFECT_DIR,
)


class RulerForPerType(unittest.TestCase):
    def test_crack_and_lop_use_v3(self):
        self.assertEqual(ruler_for("crack"), RULER_V3)
        self.assertEqual(ruler_for("lack_of_penetration"), RULER_V3)

    def test_other_types_still_use_v2(self):
        for t in ("porosity", "lack_of_fusion", "slag_inclusion", "elongated_cavity", "metallic_inclusion"):
            self.assertEqual(ruler_for(t), RULER_V2)

    def test_v3_registered_with_own_files_not_overwriting_v1_v2(self):
        self.assertIn(RULER_V3, RULERS)
        cfg = RULERS[RULER_V3]
        self.assertTrue(cfg["exclude_edge_band"])
        self.assertFalse(cfg["exclude_border"])
        v1_csv, v2_csv = RULERS["w0003-16dac-trung-v1"]["features_csv"], RULERS[RULER_V2]["features_csv"]
        self.assertNotEqual(cfg["features_csv"], v1_csv)
        self.assertNotEqual(cfg["features_csv"], v2_csv)


def _fake_mask(size):
    m = np.zeros(size[::-1], dtype=np.uint8)
    h, w = m.shape
    m[h // 2 - 20: h // 2 + 20, w // 2 - 20: w // 2 + 20] = 255
    return m


class EvaluateDefectsUsesV3ForCrackAndLop(unittest.TestCase):
    """evaluate_defects(ruler=None) (mặc định sản xuất) phải gắn ruler v3 cho crack, v2 cho porosity, trong
    CÙNG một đợt đo (xác nhận thước THEO LOẠI, không ép một thước chung)."""

    def setUp(self):
        v3_csv = RULERS[RULER_V3]["features_csv"]
        if not CALIBRATION_PATH.exists() or not v3_csv.exists():
            self.skipTest(f"chưa build tham chiếu v3, chạy `python -m realism.reference_w0003 --ruler {RULER_V3}` trước")
        crack_tiles = sorted((W0003_DEFECT_DIR / "Crack").glob("*.png"))[:4]
        if len(crack_tiles) < 4:
            self.skipTest("thiếu ô Crack thật W0003 trên máy")
        self.tmp = Path(tempfile.mkdtemp(prefix="tdm-ruler-v3-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        crack_dir = self.tmp / "crack"
        crack_dir.mkdir()
        for i, t in enumerate(crack_tiles):
            img = Image.open(t).convert("L")
            img.save(crack_dir / f"crack_{i:06d}.png")
            Image.fromarray(_fake_mask(img.size)).save(crack_dir / f"crack_{i:06d}_mask.png")
        porosity_tiles = sorted((W0003_DEFECT_DIR / "Gas_Pore").glob("*.png"))[:4]
        if len(porosity_tiles) < 4:
            self.skipTest("thiếu ô Gas_Pore thật W0003 trên máy")
        porosity_dir = self.tmp / "porosity"
        porosity_dir.mkdir()
        for i, t in enumerate(porosity_tiles):
            img = Image.open(t).convert("L")
            img.save(porosity_dir / f"porosity_{i:06d}.png")
            Image.fromarray(_fake_mask(img.size)).save(porosity_dir / f"porosity_{i:06d}_mask.png")

    def test_per_type_ruler_recorded_in_result(self):
        out = de.evaluate_defects(self.tmp, workers=2)   # ruler=None -> thước THEO LOẠI
        self.assertEqual(out["crack"]["ruler"], RULER_V3)
        self.assertEqual(out["porosity"]["ruler"], RULER_V2)

    def test_explicit_ruler_override_forces_same_ruler_for_every_type(self):
        out = de.evaluate_defects(self.tmp, workers=2, ruler=RULER_V2)
        self.assertEqual(out["crack"]["ruler"], RULER_V2)
        self.assertEqual(out["porosity"]["ruler"], RULER_V2)


if __name__ == "__main__":
    unittest.main()
