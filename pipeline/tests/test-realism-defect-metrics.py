"""Kiểm thước đo độ thật đa chỉ số (pha 1 bước 3, plan 261006-defect-metrics-w0003-reference):
phân bố giống nhau -> KID~0/C2ST~0,5/density~1/coverage cao; lệch trung bình -> KID>0, CI không chứa 0,
C2ST cao, coverage giảm; mode collapse (mọi syn trùng một điểm thật) -> density có thể cao nhưng
coverage rất thấp, tính chất mấu chốt của density/coverage mà C2ST một mình không thấy được.
"""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from realism import defect_metrics as dm  # noqa: E402
from realism.defect_metrics_density import kid  # noqa: E402

D = 4   # số chiều đặc trưng giả lập cho mọi test


def _gauss(n, mean, seed, d=D):
    return np.random.default_rng(seed).normal(mean, 1.0, size=(n, d))


class Standardize(unittest.TestCase):
    def test_zscore_theo_real_va_bo_hang_nan(self):
        real = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, np.nan]])
        syn = np.array([[2.0, 3.0], [np.nan, 1.0]])
        r, s = dm.standardize(real, syn)
        self.assertEqual(r.shape, (2, 2))     # hàng NaN của real bị loại
        self.assertEqual(s.shape, (1, 2))     # hàng NaN của syn bị loại
        np.testing.assert_allclose(r.mean(axis=0), 0.0, atol=1e-8)


class C2stMedian(unittest.TestCase):
    def test_phan_bo_giong_nhau_gan_0_5(self):
        real, syn = _gauss(200, 0, 1), _gauss(200, 0, 2)
        v = dm.c2st_median(real, syn, seeds=3)
        self.assertIsNotNone(v)
        self.assertAlmostEqual(v, 0.5, delta=0.1)

    def test_lech_trung_binh_cho_c2st_cao(self):
        real, syn = _gauss(200, 0, 1), _gauss(200, 3, 2)
        v = dm.c2st_median(real, syn, seeds=3)
        self.assertGreater(v, 0.8)

    def test_mau_qua_nho_tra_none(self):
        real, syn = _gauss(5, 0, 1), _gauss(5, 0, 2)
        self.assertIsNone(dm.c2st_median(real, syn))


class Kid(unittest.TestCase):
    def test_phan_bo_giong_nhau_kid_gan_0(self):
        # Nhân đa thức bậc 3 có đuôi lệch phải khá nặng (phương sai KID cao với mẫu đơn lẻ), nên chọn
        # n lớn, d nhỏ để CI ổn định; seed cố định đã kiểm tra chứa 0.
        real, syn = _gauss(200, 0, 1, d=2), _gauss(200, 0, 101, d=2)
        std_r, std_s = dm.standardize(real, syn)
        r = kid(std_r, std_s, B=200, seed=0)
        self.assertIsNotNone(r)
        self.assertLessEqual(r["ci_low"], 0.0)
        self.assertLessEqual(r["ci_high"], 0.6)

    def test_lech_trung_binh_kid_duong_ci_khong_chua_0(self):
        real, syn = _gauss(100, 0, 1), _gauss(100, 4, 2)
        std_r, std_s = dm.standardize(real, syn)
        r = kid(std_r, std_s, B=100, seed=0)
        self.assertGreater(r["value"], 0.0)
        self.assertGreater(r["ci_low"], 0.0)

    def test_mau_duoi_nguong_tra_none(self):
        self.assertIsNone(kid(_gauss(3, 0, 1), _gauss(3, 0, 2)))

    def test_ci_bao_quanh_diem_uoc_luong_truong_hop_dien_hinh(self):
        # Subsampling không hoàn lại (bước 2 plan): điểm ước luợng gốc phải nằm trong CI ở trường hợp điển
        # hình (mẫu đủ lớn, lệch vừa phải), khác bootstrap có hoàn lại cũ có thể đẩy CI lệch khỏi điểm gốc.
        real, syn = _gauss(150, 0, 1, d=2), _gauss(150, 0.3, 2, d=2)
        std_r, std_s = dm.standardize(real, syn)
        r = kid(std_r, std_s, B=300, seed=7)
        self.assertLessEqual(r["ci_low"], r["value"])
        self.assertGreaterEqual(r["ci_high"], r["value"])

    def test_khong_chech_trung_binh_qua_nhieu_lan_rut_null_gan_0(self):
        # Rút nhiều cặp null (hai mẫu con của CÙNG một real) phải cho KID trung bình quay quanh 0,
        # đúng tính chất không chệch của ước lượng MMD²; không yêu cầu từng lần bằng 0.
        real = _gauss(400, 0, 0)
        vals = []
        for i in range(30):
            rng = np.random.default_rng(100 + i)
            a = real[rng.choice(400, 60, replace=False)]
            b = real[rng.choice(400, 60, replace=False)]
            std_a, std_b = dm.standardize(a, b)
            vals.append(kid(std_a, std_b, B=20, seed=i)["value"])
        self.assertAlmostEqual(float(np.mean(vals)), 0.0, delta=0.05)


class DensityCoverage(unittest.TestCase):
    def test_phan_bo_giong_nhau_density_coverage_cao(self):
        real, syn = _gauss(100, 0, 1), _gauss(100, 0, 2)
        std_r, std_s = dm.standardize(real, syn)
        r = dm.density_coverage(std_r, std_s, k=5)
        self.assertGreater(r["density"], 0.5)
        self.assertGreater(r["coverage"], 0.7)

    def test_lech_trung_binh_coverage_giam(self):
        real, syn = _gauss(100, 0, 1), _gauss(100, 6, 2)
        std_r, std_s = dm.standardize(real, syn)
        r = dm.density_coverage(std_r, std_s, k=5)
        self.assertLess(r["coverage"], 0.2)

    def test_mode_collapse_density_cao_coverage_rat_thap(self):
        # Mọi điểm sinh trùng đúng MỘT điểm thật: mỗi lần "trúng" cộng dồn density của đúng một điểm
        # thật đó, nhưng chỉ một điểm thật được "phủ" -> coverage gần 1/n_real, density có thể vẫn cao.
        real = _gauss(50, 0, 1)
        syn = np.tile(real[0], (50, 1))
        std_r, std_s = dm.standardize(real, syn)
        r = dm.density_coverage(std_r, std_s, k=5)
        self.assertGreaterEqual(r["density"], 0.9)        # mọi syn trùng 1 điểm -> luôn "trúng" bán cầu đó
        self.assertLessEqual(r["coverage"], 0.1)          # nhưng chỉ phủ được vài lân cận của điểm đó
        self.assertLess(r["coverage"], r["density"] - 0.5)  # tách biệt rõ hai thước đo, đúng tính chất mode collapse

    def test_k_bi_cat_khi_real_qua_it_mau(self):
        real, syn = _gauss(5, 0, 1), _gauss(5, 0, 2)
        r = dm.density_coverage(real, syn, k=20)   # k=20 > n_real-1, phải tự cắt, không lỗi
        self.assertIsNotNone(r["density"])


class PerFeature(unittest.TestCase):
    def test_sap_theo_lech_auc_giam_dan(self):
        real = np.column_stack([_gauss(80, 0, 1)[:, 0], _gauss(80, 0, 2)[:, 0]])
        syn = np.column_stack([_gauss(80, 0, 3)[:, 0], _gauss(80, 5, 4)[:, 0]])
        out = dm.per_feature(real, syn, ["giong_nhau", "lech_manh"])
        self.assertEqual(out[0]["name"], "lech_manh")
        self.assertGreater(abs(out[0]["auc"] - 0.5), abs(out[1]["auc"] - 0.5))


class DetectionRate(unittest.TestCase):
    def test_ti_le_dung(self):
        self.assertAlmostEqual(dm.detection_rate([True, True, False, True]), 0.75)

    def test_mang_rong_tra_none(self):
        self.assertIsNone(dm.detection_rate([]))


class Compare(unittest.TestCase):
    def test_gop_day_du_truong_va_loai_hang_khong_vung(self):
        import pandas as pd
        names = ["f1", "f2"]
        real_df = pd.DataFrame({
            "f1": list(_gauss(40, 0, 1)[:, 0]) + [np.nan, 0.0],
            "f2": list(_gauss(40, 0, 2)[:, 0]) + [0.0, np.nan],
            "has_region": [True] * 40 + [True, False],
        })
        syn_df = pd.DataFrame({
            "f1": list(_gauss(40, 0, 3)[:, 0]) + [0.0],
            "f2": list(_gauss(40, 0, 4)[:, 0]) + [0.0],
            "has_region": [True] * 40 + [False],
        })
        r = dm.compare(real_df, syn_df, names)
        self.assertEqual(r["n_real"], 40)   # hàng has_region=False và hàng NaN đều bị loại
        self.assertEqual(r["n_syn"], 40)
        self.assertIsNotNone(r["c2st"])
        self.assertAlmostEqual(r["detection_rate_real"], 41 / 42, places=3)
        self.assertEqual(len(r["per_feature"]), 2)


class NullReference(unittest.TestCase):
    def test_khoang_hop_ly_va_dinh(self):
        # n_syn=12 (>= MIN_C2ST_N=10) để c2st_median không None; vẫn đủ nhỏ để thấy coverage < 1.
        real = _gauss(60, 0, 1)
        out = dm.null_reference(real, n_syn=12, reps=15, seed=0)
        self.assertIsNotNone(out["c2st"])
        self.assertIsNotNone(out["coverage"])
        # Mẫu con 12 điểm trong 60 điểm thật: coverage trung vị nên dưới 1 (không phủ hết 60 bán cầu
        # thật bằng chỉ 12 điểm), đúng cảnh báo rủi ro trong plan về mẫu nhỏ W0003.
        self.assertLess(out["coverage"]["median"], 1.0)

    def test_mau_7_diem_khong_vo_c2st_tra_none_chu_khong_crash(self):
        # Lớp W0003 nhỏ nhất (vd 7 mẫu) dưới MIN_C2ST_N=10: c2st_median trả None thay vì crash;
        # kid/density/coverage vẫn tính được vì không có ngưỡng tối thiểu 10 như C2ST.
        # Mức "hoàn hảo" chia đôi ảnh thật thành hai nửa tách rời: 14 mẫu thật → hai nửa 7, dưới MIN_C2ST_N.
        real = _gauss(14, 0, 1)
        out = dm.null_reference(real, n_syn=7, reps=10, seed=0)
        self.assertIsNone(out["c2st"])
        self.assertIsNotNone(out["coverage"])

    def test_mau_qua_it_tra_none(self):
        out = dm.null_reference(np.zeros((1, D)), n_syn=1, reps=5)
        self.assertIsNone(out["c2st"])

    def test_dinh_voi_cung_hat_giong(self):
        real = _gauss(60, 0, 1)
        a = dm.null_reference(real, n_syn=12, reps=10, seed=42)
        b = dm.null_reference(real, n_syn=12, reps=10, seed=42)
        self.assertEqual(a["c2st"]["median"], b["c2st"]["median"])
        self.assertEqual(a["coverage"]["median"], b["coverage"]["median"])


class NullReferenceDisjoint(unittest.TestCase):
    """Hai nửa ảnh thật tách rời: C2ST quanh 0,5 (bản cũ so mẫu con với chính tập chứa nó ra 0,1 tới 0,2)."""
    def test_c2st_quanh_0_5(self):
        out = dm.null_reference(_gauss(200, 0, 1), reps=20, seed=1)
        self.assertTrue(0.4 < out["c2st"]["median"] < 0.6, out["c2st"])
        self.assertLess(abs(out["kid"]["median"]), 0.05)


class RankNormalRobust(unittest.TestCase):
    """Ngoại lai cực lớn và đặc trưng gần hằng số trong ảnh thật không làm KID bùng nổ (lỗi 6/10)."""
    def test_kid_khong_bung_no_voi_ngoai_lai(self):
        real = _gauss(16, 0, 1); real[:, 0] = 1.0                      # đặc trưng 0 hằng số trong ảnh thật
        syn = _gauss(100, 0, 2); syn[:5, 0] = 50.0                     # vài ảnh sinh lệch xa
        zr, zs = dm.rank_normal(real, syn)
        self.assertLess(abs(kid(zr, zs, B=50)["value"]), 5.0)
        self.assertTrue(np.isfinite(zr).all() and np.isfinite(zs).all())


if __name__ == "__main__":
    unittest.main()
