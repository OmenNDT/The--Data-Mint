"""Kiểm thước mới (bước 3-4, plan 261006-defect-metrics-w0003-reference): defect_eval.evaluate_defects
trên một thư mục nhỏ ghép từ vài ô W0003 thật (không cần GPU), và evaluate.run không vỡ luồng cũ khi
thước mới lỗi.

Run: .venv/bin/python tests/test-realism-defect-eval.py
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from realism import defect_eval as de  # noqa: E402
from realism import evaluate, runlog  # noqa: E402
from realism.reference_w0003 import CALIBRATION_PATH, W0003_DEFECT_DIR  # noqa: E402


def _fake_mask(size):
    """Mặt nạ hình vuông giữa ảnh, đủ để center_of_mass và defect_features chạy được."""
    m = np.zeros(size[::-1], dtype=np.uint8)
    h, w = m.shape
    m[h // 2 - 20: h // 2 + 20, w // 2 - 20: w // 2 + 20] = 255
    return m


class EvaluateDefects(unittest.TestCase):
    """Dựng thư mục giả từ vài ô Crack thật của W0003 (ảnh thật, mặt nạ giả) + một loại không có
    tham chiếu (undercut), kiểm defect_eval.evaluate_defects trả đúng lược đồ."""

    def setUp(self):
        if not CALIBRATION_PATH.exists():
            self.skipTest("chưa hiệu chỉnh ngưỡng W0003, chạy `python -m realism.reference_w0003` trước")
        tiles = sorted((W0003_DEFECT_DIR / "Crack").glob("*.png"))[:4]
        if len(tiles) < 4:
            self.skipTest("thiếu ô Crack thật W0003 trên máy")
        self.tmp = Path(tempfile.mkdtemp(prefix="tdm-defect-eval-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

        crack_dir = self.tmp / "crack"
        crack_dir.mkdir()
        for i, t in enumerate(tiles):
            img = Image.open(t).convert("L")
            img.save(crack_dir / f"crack_{i:06d}.png")
            Image.fromarray(_fake_mask(img.size)).save(crack_dir / f"crack_{i:06d}_mask.png")

        undercut_dir = self.tmp / "undercut"   # loại chưa có mẫu W0003 (W0003_CLASS["undercut"] is None)
        undercut_dir.mkdir()
        img = Image.open(tiles[0]).convert("L")
        img.save(undercut_dir / "undercut_000000.png")
        Image.fromarray(_fake_mask(img.size)).save(undercut_dir / "undercut_000000_mask.png")

        other_dir = self.tmp / "khong_phai_loi"   # thư mục lạ, không trong W0003_CLASS: phải bị bỏ qua
        other_dir.mkdir()

    def test_loai_co_tham_chieu_du_cac_khoa(self):
        out = de.evaluate_defects(self.tmp, workers=2)
        self.assertIn("crack", out)
        self.assertNotIn("khong_phai_loi", out)
        e = out["crack"]
        self.assertEqual(e["reference"], "Crack")
        for key in ("n_real", "n_syn", "detection_rate_real", "detection_rate_syn", "c2st", "c2st_reason",
                    "kid", "density_coverage", "top_features", "null", "small_reference"):
            self.assertIn(key, e)
        self.assertIsNone(e["c2st"])            # chỉ 4 ảnh sinh, dưới MIN_C2ST_ROWS=10
        self.assertIsNotNone(e["c2st_reason"])
        self.assertEqual(e["n_syn"], 4)

    def test_loai_khong_co_tham_chieu_w0003(self):
        out = de.evaluate_defects(self.tmp, workers=2)
        self.assertIn("undercut", out)
        e = out["undercut"]
        self.assertIsNone(e["reference"])
        self.assertEqual(e["n_syn"], 1)
        self.assertIn("detection_rate_syn", e)
        self.assertNotIn("c2st", e)


class EvaluateRunDefectMetricsErrorHandling(unittest.TestCase):
    """evaluate.run không được vỡ luồng cũ (sáu tiêu chí RIAWELC) khi evaluate_defects lỗi: trường
    defect_metrics phải mang error, pairs/cases vẫn ghi như cũ."""

    def test_loi_thuoc_moi_khong_lam_vo_ket_qua_cu(self):
        tmp = Path(tempfile.mkdtemp(prefix="tdm-defect-eval-run-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        state_dir = tmp / "runs"
        with mock.patch.object(runlog, "RUNS_DIR", state_dir), \
             mock.patch("realism.evaluate.evaluate_defects", side_effect=RuntimeError("giả lỗi thước mới")):
            result = evaluate.run(tmp / "nguon-rong", "test-defect-metrics-error", workers=2)
        self.assertEqual(result["pairs"], [])     # nguồn rỗng: luồng cũ vẫn chạy xong, không vỡ
        self.assertIn("defect_metrics", result)
        self.assertEqual(result["defect_metrics"]["types"], {})
        self.assertIn("giả lỗi thước mới", result["defect_metrics"]["error"])
        self.assertTrue((state_dir / "test-defect-metrics-error" / "result.json").exists())  # ghi trong tmp, không đụng realism/state thật


if __name__ == "__main__":
    unittest.main()
