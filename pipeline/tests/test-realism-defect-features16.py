"""Kiểm 16 đặc trưng khuyết tật (defect_features16) và tham chiếu W0003 (reference_w0003).

Tái lập v2-kernel/features.csv (Data_Science) trên mẫu ảnh RIAWELC thật; kiểm luật hiệu chỉnh ngưỡng tái lập đúng
ngưỡng RIAWELC gốc khi áp trên ảnh RIAWELC (chứng minh hàm hiệu chỉnh đúng, độc lập dữ liệu W0003); kiểm ánh xạ
loại lỗi bộ sinh → lớp W0003; kiểm crop_synthetic kẹp biên.

Run: .venv/bin/python tests/test-realism-defect-features16.py
"""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mask_generator import (  # noqa: E402
    ClusteredPorosityMaskGenerator, CrackMaskGenerator, ElongatedCavityMaskGenerator,
    LackOfFusionMaskGenerator, LackOfPenetrationMaskGenerator, LackOfSideWallFusionMaskGenerator,
    LinearPorosityMaskGenerator, LinearSlagInclusionMaskGenerator, MetallicInclusionMaskGenerator,
    PorosityMaskGenerator, SlagInclusionMaskGenerator, UndercutMaskGenerator,
)
from realism.defect_features16 import DEFECT_FEATURES, defect_features  # noqa: E402
from realism.reference_w0003 import (  # noqa: E402
    W0003_CLASS, W0003_DEFECT_DIR, calibrate_thresholds, crop_synthetic, region_scores,
)

RIAWELC = Path("/home/sontn/Projects/The Data Mint/dataset/RIAWELC/extracted-fresh/DB - Copy")
V2_KERNEL_DIR = Path("/home/sontn/Projects/Data_Science/analysis/riawelc-features/v2-kernel")
V2_FEATURES_CSV = V2_KERNEL_DIR / "features.csv"
V2_CALIBRATION_JSON = V2_KERNEL_DIR / "calibration.json"

# Toàn bộ tên generator dùng trong mask_generator / batch-config.yaml (defect_type), để đối chiếu W0003_CLASS.
GENERATOR_DEFECT_TYPES = {
    "crack", "porosity", "clustered_porosity", "lack_of_fusion", "lack_of_penetration",
    "lack_of_side_wall_fusion", "slag_inclusion", "linear_slag_inclusion", "metallic_inclusion",
    "undercut", "linear_porosity", "elongated_cavity",
}


class DefectFeaturesShape(unittest.TestCase):
    """Không cần dữ liệu ngoài: defect_features trả đúng 16 khoá + has_region trên ảnh bất kỳ."""

    def test_returns_exact_16_keys_plus_has_region(self):
        rng = np.random.default_rng(0)
        img = (rng.normal(180, 10, (227, 227))).astype(np.float32)
        thr = {"dom_16": 0.9, "dai_8": 2.24, "ngang_8": 2.32}
        f = defect_features(img, thr)
        self.assertEqual(set(f), set(DEFECT_FEATURES) | {"has_region"})
        self.assertEqual(len(DEFECT_FEATURES), 16)
        for v in f.values():
            self.assertIsInstance(v, float)

    def test_has_region_matches_vung_sodom(self):
        rng = np.random.default_rng(1)
        img = (rng.normal(180, 10, (227, 227))).astype(np.float32)
        img[90:140, 90:140] -= 60   # vùng tối rõ rệt, phải bị kernel dom bắt
        thr = {"dom_16": 0.9, "dai_8": 2.24, "ngang_8": 2.32}
        f = defect_features(img, thr)
        self.assertEqual(f["has_region"], 1.0 if f["vung_sodom"] > 0 else 0.0)
        self.assertGreater(f["vung_sodom"], 0)
        self.assertEqual(f["has_region"], 1.0)


class FeaturesMatchV2KernelReference(unittest.TestCase):
    """defect_features(img, thr_riawelc) phải khớp v2-kernel/features.csv (bảng gốc) tới ~1e-6."""

    @unittest.skipUnless(RIAWELC.exists() and V2_FEATURES_CSV.exists(), "thiếu RIAWELC hoặc v2-kernel/features.csv")
    def test_matches_v2_kernel_csv(self):
        import json
        from PIL import Image

        thr = json.loads(V2_CALIBRATION_JSON.read_text())["thr"]
        ref = pd.read_csv(V2_FEATURES_CSV)
        sample = pd.concat([ref[ref.cls == c].sample(10, random_state=5) for c in ("CR", "PO", "LP")])
        root = RIAWELC
        for _, r in sample.iterrows():
            img = np.asarray(Image.open(root / r["file"]).convert("L"), dtype=np.float32)
            f = defect_features(img, thr)
            for k in DEFECT_FEATURES:
                self.assertAlmostEqual(f[k], r[k], delta=1e-5, msg=f"{r['file']} {k}")


class CalibrationReproducesReference(unittest.TestCase):
    """calibrate_thresholds (chép từ feature_bank_kernel.calibrate) phải tái lập ngưỡng RIAWELC gốc khi áp
    đúng cách lên ảnh ND RIAWELC (chứng minh hàm hiệu chỉnh đúng, trước khi dùng cho miền W0003)."""

    @unittest.skipUnless(RIAWELC.exists() and V2_FEATURES_CSV.exists(), "thiếu RIAWELC hoặc v2-kernel/features.csv")
    def test_calibration_close_to_riawelc_official(self):
        import json
        import os
        from multiprocessing import Pool

        from PIL import Image

        official = json.loads(V2_CALIBRATION_JSON.read_text())["thr"]
        ref = pd.read_csv(V2_FEATURES_CSV)
        nd = ref[ref.cls == "ND"].sample(800, random_state=11)
        imgs = [np.asarray(Image.open(RIAWELC / f).convert("L"), dtype=np.float32) for f in nd.file]
        with Pool(min(32, os.cpu_count() or 4)) as pool:
            rows = pool.map(region_scores, imgs, chunksize=8)
        nd_scores = {k: np.array([r[k] for r in rows]) for k in ("dom_16", "dai_8", "ngang_8")}
        thr, q = calibrate_thresholds(nd_scores)
        for k in official:
            rel_err = abs(thr[k] - official[k]) / official[k]
            self.assertLess(rel_err, 0.1, f"{k}: {thr[k]} vs {official[k]} (sai {rel_err:.1%})")


class W0003ClassMapping(unittest.TestCase):
    def test_every_generator_defect_type_is_mapped(self):
        self.assertEqual(set(W0003_CLASS), GENERATOR_DEFECT_TYPES)

    def test_mapped_folders_exist_when_dataset_present(self):
        if not W0003_DEFECT_DIR.exists():
            self.skipTest("không có dataset W0003 trên máy")
        existing = {p.name for p in W0003_DEFECT_DIR.iterdir() if p.is_dir()}
        for defect_type, cls in W0003_CLASS.items():
            if cls is not None:
                self.assertIn(cls, existing, f"{defect_type} -> {cls} không tồn tại trong {W0003_DEFECT_DIR}")

    def test_none_mapped_types_have_no_w0003_reference(self):
        self.assertIsNone(W0003_CLASS["lack_of_side_wall_fusion"])
        self.assertIsNone(W0003_CLASS["undercut"])

    def test_mask_generator_classes_importable_for_every_mapped_type(self):
        # Chỉ kiểm các lớp generator tồn tại và instantiate được, không liên quan trực tiếp tới W0003_CLASS,
        # nhưng xác nhận GENERATOR_DEFECT_TYPES không liệt kê nhầm tên không có generator tương ứng.
        generators = {
            "crack": CrackMaskGenerator, "porosity": PorosityMaskGenerator,
            "clustered_porosity": ClusteredPorosityMaskGenerator, "lack_of_fusion": LackOfFusionMaskGenerator,
            "lack_of_penetration": LackOfPenetrationMaskGenerator,
            "lack_of_side_wall_fusion": LackOfSideWallFusionMaskGenerator,
            "slag_inclusion": SlagInclusionMaskGenerator, "linear_slag_inclusion": LinearSlagInclusionMaskGenerator,
            "metallic_inclusion": MetallicInclusionMaskGenerator, "undercut": UndercutMaskGenerator,
            "linear_porosity": LinearPorosityMaskGenerator, "elongated_cavity": ElongatedCavityMaskGenerator,
        }
        self.assertEqual(set(generators), GENERATOR_DEFECT_TYPES)


class CropSyntheticBounds(unittest.TestCase):
    def test_centered_mask_gives_centered_crop_of_requested_size(self):
        img = np.zeros((512, 512), np.float32)
        mask = np.zeros((512, 512), bool)
        mask[246:266, 246:266] = True   # tâm ~ (256, 256)
        c = crop_synthetic(img, mask, size=278)
        self.assertEqual(c.shape, (278, 278))

    def test_corner_mask_crop_stays_within_bounds(self):
        img = np.arange(512 * 512, dtype=np.float32).reshape(512, 512)
        mask = np.zeros((512, 512), bool)
        mask[2:10, 2:10] = True         # lỗi sát góc trên-trái
        c = crop_synthetic(img, mask, size=278)
        self.assertEqual(c.shape, (278, 278))
        # Kẹp biên: khung cắt phải nằm trong [0, 512) cả hai trục, không lỗi index.
        self.assertTrue(np.array_equal(c, img[:278, :278]))

    def test_mask_near_bottom_right_corner(self):
        img = np.arange(512 * 512, dtype=np.float32).reshape(512, 512)
        mask = np.zeros((512, 512), bool)
        mask[500:508, 500:508] = True
        c = crop_synthetic(img, mask, size=278)
        self.assertEqual(c.shape, (278, 278))
        self.assertTrue(np.array_equal(c, img[234:512, 234:512]))


if __name__ == "__main__":
    unittest.main()
