"""Kiểm độ đo "đúng đối tượng" (bước 1) và cờ "chỉ tham khảo" (bước 3), plan 261006-defect-metrics-w0003-
reference: defect_eval._on_target, _evaluate_type(reference_only), evaluate_defects(ruler=RULER_V2).

Run: .venv/bin/python tests/test-realism-defect-eval-on-target.py
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from realism import defect_eval as de  # noqa: E402
from realism.defect_features16 import DEFECT_FEATURES  # noqa: E402
from realism.reference_w0003 import CALIBRATION_PATH, RULER_V2, RULERS, W0003_DEFECT_DIR  # noqa: E402


class OnTarget(unittest.TestCase):
    """_on_target: trung bình vùng trùng mặt nạ (chỉ ảnh có vùng) + tỉ lệ "đúng đối tượng" trên TOÀN BỘ ảnh."""

    def _df(self, rows):
        cols = ["file", "has_region", "on_target_overlap"] + DEFECT_FEATURES + ["case_id"]
        return pd.DataFrame([{**{k: 0.0 for k in DEFECT_FEATURES}, "case_id": None, **r} for r in rows],
                             columns=cols)

    def test_mixed_overlap_rows(self):
        df = self._df([
            {"file": "a", "has_region": 1.0, "on_target_overlap": 0.9},
            {"file": "b", "has_region": 1.0, "on_target_overlap": 0.1},   # có vùng nhưng lệch mục tiêu
            {"file": "c", "has_region": 0.0, "on_target_overlap": 0.0},   # không tách được vùng -> trượt
        ])
        out = de._on_target(df, len(df))
        self.assertAlmostEqual(out["mean_overlap_on_region"], 0.5, places=6)   # TB trên 2 ảnh CÓ vùng
        self.assertAlmostEqual(out["on_target_rate"], 1 / 3, places=6)         # chỉ "a" vượt ngưỡng 0.3 trên 3 ảnh
        self.assertEqual(out["threshold"], de.ON_TARGET_THRESHOLD)

    def test_empty_frame_returns_none(self):
        out = de._on_target(self._df([]), 0)
        self.assertIsNone(out["mean_overlap_on_region"])
        self.assertIsNone(out["on_target_rate"])

    def test_no_region_anywhere_gives_zero_rate_and_none_mean(self):
        df = self._df([{"file": "a", "has_region": 0.0, "on_target_overlap": 0.0}])
        out = de._on_target(df, len(df))
        self.assertEqual(out["on_target_rate"], 0.0)
        self.assertIsNone(out["mean_overlap_on_region"])   # không ảnh nào có vùng để lấy trung bình


def _fake_mask(size):
    m = np.zeros(size[::-1], dtype=np.uint8)
    h, w = m.shape
    m[h // 2 - 20: h // 2 + 20, w // 2 - 20: w // 2 + 20] = 255
    return m


class ReferenceOnlyFlag(unittest.TestCase):
    """metallic_inclusion phải mang reference_only=True (bước 3: chỉ 3 ảnh thật W0003, không chặn cổng);
    loại khác có tham chiếu (vd crack) phải là False."""

    def setUp(self):
        if not CALIBRATION_PATH.exists():
            self.skipTest("chưa hiệu chỉnh ngưỡng W0003, chạy `python -m realism.reference_w0003` trước")

    def test_metallic_inclusion_is_reference_only(self):
        tiles = sorted((W0003_DEFECT_DIR / "Metallic_Inclusion").glob("*.png"))
        if not tiles:
            self.skipTest("thiếu ô Metallic_Inclusion thật W0003 trên máy")
        tmp = Path(tempfile.mkdtemp(prefix="tdm-on-target-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        d = tmp / "metallic_inclusion"
        d.mkdir()
        for i, t in enumerate(tiles):
            img = Image.open(t).convert("L")
            img.save(d / f"metallic_inclusion_{i:06d}.png")
            Image.fromarray(_fake_mask(img.size)).save(d / f"metallic_inclusion_{i:06d}_mask.png")
        out = de.evaluate_defects(tmp, workers=2)
        self.assertTrue(out["metallic_inclusion"]["reference_only"])

    def test_crack_is_not_reference_only(self):
        tiles = sorted((W0003_DEFECT_DIR / "Crack").glob("*.png"))[:4]
        if len(tiles) < 4:
            self.skipTest("thiếu ô Crack thật W0003 trên máy")
        tmp = Path(tempfile.mkdtemp(prefix="tdm-on-target-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        d = tmp / "crack"
        d.mkdir()
        for i, t in enumerate(tiles):
            img = Image.open(t).convert("L")
            img.save(d / f"crack_{i:06d}.png")
            Image.fromarray(_fake_mask(img.size)).save(d / f"crack_{i:06d}_mask.png")
        out = de.evaluate_defects(tmp, workers=2)
        self.assertFalse(out["crack"]["reference_only"])


class RulerV2EndToEnd(unittest.TestCase):
    """evaluate_defects(ruler=RULER_V2) phải chạy được trên thư mục ĐÃ CÓ (không sinh lại ảnh) và đọc đúng
    tệp tham chiếu v2 (xem reference_w0003.RULERS), không đụng tệp v1."""

    def setUp(self):
        v2_csv = RULERS[RULER_V2]["features_csv"]
        if not CALIBRATION_PATH.exists() or not v2_csv.exists():
            self.skipTest("chưa build tham chiếu v2, chạy `python -m realism.reference_w0003 --ruler "
                           f"{RULER_V2}` trước")

    def test_ruler_v2_runs_and_tags_result(self):
        tiles = sorted((W0003_DEFECT_DIR / "Crack").glob("*.png"))[:4]
        if len(tiles) < 4:
            self.skipTest("thiếu ô Crack thật W0003 trên máy")
        tmp = Path(tempfile.mkdtemp(prefix="tdm-ruler-v2-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        d = tmp / "crack"
        d.mkdir()
        for i, t in enumerate(tiles):
            img = Image.open(t).convert("L")
            img.save(d / f"crack_{i:06d}.png")
            Image.fromarray(_fake_mask(img.size)).save(d / f"crack_{i:06d}_mask.png")
        out = de.evaluate_defects(tmp, workers=2, ruler=RULER_V2)
        self.assertIn("crack", out)
        self.assertIn("on_target", out["crack"])


if __name__ == "__main__":
    unittest.main()
