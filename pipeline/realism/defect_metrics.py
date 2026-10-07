"""Thước đo độ thật đa chỉ số trên đặc trưng hình dạng khuyết tật (16 đặc trưng, pha 1 bước 3 của plan
261006-defect-metrics-w0003-reference). Hàm thuần, không đọc/ghi đĩa, không phụ thuộc sklearn/torch
(venv pipeline không có). Nhận real, syn là mảng numpy (n, d); hàng có NaN bị loại trước khi đo.

C2ST dùng lại realism.stats.c2st (hồi quy logistic bậc hai, kiểm chéo 5 phần), lấy trung vị nhiều hạt
giống như evaluate._c2st_median vì một lần chia ngẫu nhiên có thể lệch xa giá trị điển hình.
KID và density/coverage nằm ở defect_metrics_density.py (phần nặng tính khoảng cách/nhân) để file này
dưới 200 dòng.

W0003 ít mẫu (3-43/lớp, xem rủi ro trong plan): các hàm dưới đây tự trả None khi mẫu quá nhỏ để đo đạc
không im lặng sai, không cố ép ra một số không có nghĩa.
"""
import numpy as np

from .defect_metrics_density import density_coverage, kid  # re-export cho nơi gọi compare()
from .stats import auc, c2st, ks

MIN_C2ST_N = 10   # khớp ngưỡng trong realism.stats.c2st


def _drop_nan_rows(arr):
    arr = np.asarray(arr, float)
    if arr.ndim == 1:
        return arr[np.isfinite(arr)]
    return arr[np.all(np.isfinite(arr), axis=1)]


def standardize(real, syn):
    """Chuẩn hoá z-score theo trung bình/lệch chuẩn của REAL (tham chiếu chính, xem plan mục 6/10).
    Lệch chuẩn quá nhỏ (đặc trưng gần hằng số) được giữ sàn 1e-8 để tránh chia 0."""
    real, syn = _drop_nan_rows(real), _drop_nan_rows(syn)
    mu, sigma = real.mean(axis=0), real.std(axis=0)
    sigma = np.where(sigma < 1e-8, 1.0, sigma)
    return (real - mu) / sigma, (syn - mu) / sigma


def rank_normal(real, syn):
    """Đổi từng đặc trưng sang điểm chuẩn theo THỨ HẠNG trên tập gộp real+syn (hạng trung bình khi trùng).
    Dùng cho KID và density/coverage thay z-score: lớp W0003 chỉ 16 tới 43 mẫu, vài đặc trưng gần hằng số trong
    ảnh thật, z-score theo real biến một ảnh sinh hơi khác thành ngoại lai cực lớn và nhân bậc ba khuếch đại
    lên (KID 1e6 ở không thấu, thấy 6/10). Biến đổi hạng bền với ngoại lai, không đổi khi đặc trưng bị biến
    đổi đơn điệu, và chung cho cả hai nhóm nên không thiên vị bên nào."""
    from scipy.stats import norm, rankdata
    real, syn = _drop_nan_rows(real), _drop_nan_rows(syn)
    pooled = np.vstack([real, syn])
    z = np.column_stack([norm.ppf((rankdata(pooled[:, j]) - 0.5) / len(pooled)) for j in range(pooled.shape[1])])
    return z[: len(real)], z[len(real):]


def c2st_median(real, syn, seeds=5):
    """Trung vị C2ST qua nhiều hạt giống chia kiểm chéo; None nếu một trong hai nhóm dưới ngưỡng tối thiểu."""
    real, syn = _drop_nan_rows(real), _drop_nan_rows(syn)
    if len(real) < MIN_C2ST_N or len(syn) < MIN_C2ST_N:
        return None
    vals = [v for v in (c2st(real, syn, seed=s) for s in range(seeds)) if v is not None]
    return float(np.median(vals)) if vals else None


def per_feature(real, syn, names):
    """AUC + KS + trung vị từng đặc trưng, sắp theo |AUC - 0,5| giảm dần (đặc trưng lệch nhiều nhất lên đầu)."""
    real, syn = np.asarray(real, float), np.asarray(syn, float)
    out = []
    for i, name in enumerate(names):
        rv = real[:, i][np.isfinite(real[:, i])]
        sv = syn[:, i][np.isfinite(syn[:, i])]
        a = auc(sv, rv) if len(sv) and len(rv) else None
        out.append({
            "name": name,
            "auc": a,
            "real_med": float(np.median(rv)) if len(rv) else None,
            "syn_med": float(np.median(sv)) if len(sv) else None,
            "ks": ks(sv, rv) if len(sv) and len(rv) else None,
        })
    out.sort(key=lambda d: -abs((d["auc"] if d["auc"] is not None else 0.5) - 0.5))
    return out


def detection_rate(has_region_bool_array):
    """Tỉ lệ ảnh tách được vùng (has_region True). None nếu mảng rỗng."""
    arr = np.asarray(has_region_bool_array, bool)
    return float(arr.mean()) if len(arr) else None


def compare(real_df, syn_df, names):
    """Gộp mọi thước đo cho một loại khuyết tật. real_df, syn_df cần cột `has_region` (bool) + các cột
    trong `names`. Tỉ lệ tách vùng (detection_rate) tính trên TOÀN BỘ df; các thước đo hình dạng (C2ST,
    KID, density/coverage, per_feature) chỉ tính trên hàng có has_region=True và không NaN, vì hàng
    không tách được vùng không có đặc trưng hình dạng hợp lệ."""
    real_shape = _drop_nan_rows(real_df.loc[real_df["has_region"], names].to_numpy(float))
    syn_shape = _drop_nan_rows(syn_df.loc[syn_df["has_region"], names].to_numpy(float))
    std_real, std_syn = rank_normal(real_shape, syn_shape) if len(real_shape) and len(syn_shape) else (real_shape, syn_shape)
    return {
        "n_real": len(real_shape), "n_syn": len(syn_shape),
        "detection_rate_real": detection_rate(real_df["has_region"].to_numpy(bool)),
        "detection_rate_syn": detection_rate(syn_df["has_region"].to_numpy(bool)),
        "c2st": c2st_median(real_shape, syn_shape),
        "kid": kid(std_real, std_syn) if len(std_real) and len(std_syn) else None,
        "density_coverage": density_coverage(std_real, std_syn) if len(std_real) and len(std_syn) else {"density": None, "coverage": None},
        "per_feature": per_feature(real_shape, syn_shape, names) if len(real_shape) and len(syn_shape) else [],
    }


def _summarize(values):
    if not values:
        return None
    arr = np.asarray(values, float)
    return {"median": float(np.median(arr)), "p5": float(np.percentile(arr, 5)), "p95": float(np.percentile(arr, 95))}


def null_reference(real, n_syn=None, reps=50, seed=0):
    """Mức kỳ vọng của C2ST/KID/density/coverage khi ảnh sinh KHÔNG phân biệt được với ảnh thật, ước lượng bằng
    chia đôi ngẫu nhiên ảnh thật thành hai nhóm TÁCH RỜI: nửa A làm tham chiếu, nửa B đóng vai "sinh".
    Hai nhóm phải tách rời: so mẫu con với chính tập chứa nó (bản cũ) làm cùng một điểm nằm ở cả hai lớp, C2ST ra
    0,1 tới 0,2 thay vì quanh 0,5 (lỗi thấy 6/10). n_syn giữ trong chữ ký cho tương thích, không dùng: nhóm "sinh"
    là nửa còn lại, không lấy mẫu lặp (lặp điểm cũng làm C2ST lệch). Tham chiếu chỉ còn nửa số mẫu nên mức này hơi
    rộng hơn thực tế, nghiêng về thận trọng."""
    real = _drop_nan_rows(real)
    n = len(real)
    if n < 4:
        return {"c2st": None, "kid": None, "density": None, "coverage": None}
    rng = np.random.default_rng(seed)
    c2sts, kid_vals, dens, cov = [], [], [], []
    for i in range(reps):
        perm = rng.permutation(n)
        a, b = real[perm[: n // 2]], real[perm[n // 2:]]
        c = c2st_median(a, b, seeds=3)
        if c is not None:
            c2sts.append(c)
        za, zb = rank_normal(a, b)
        k = kid(za, zb, B=50, seed=seed * 10_000 + i)
        if k is not None:
            kid_vals.append(k["value"])
        dc = density_coverage(za, zb, k=5)
        if dc["density"] is not None:
            dens.append(dc["density"])
            cov.append(dc["coverage"])
    return {"c2st": _summarize(c2sts), "kid": _summarize(kid_vals),
            "density": _summarize(dens), "coverage": _summarize(cov), "method": "chia đôi ảnh thật, hai nửa tách rời"}
