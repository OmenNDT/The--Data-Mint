"""KID (MMD² không chệch, nhân đa thức) và density/coverage (Naeem 2020) trên đặc trưng đã chuẩn hoá.
Tách khỏi defect_metrics.py để module chính dưới 200 dòng; đây là phần nặng tính toán khoảng cách/nhân.
"""
import numpy as np
from scipy.spatial.distance import cdist

MIN_N = 5   # dưới mức này KID không đủ ổn định (xem rủi ro CI rộng trong plan), trả None


def _poly_kernel(X, Y, d):
    """Nhân đa thức bậc 3 kiểu Bińkowski 2018: k(x, y) = (x.y / d + 1) ** 3."""
    return (X @ Y.T / d + 1.0) ** 3


def _mmd2_unbiased(X, Y):
    """MMD² không chệch: bỏ cặp (i, i) trong nội bộ mỗi nhóm, giữ đủ cặp chéo giữa hai nhóm."""
    m, n = len(X), len(Y)
    d = X.shape[1]
    kxx, kyy, kxy = _poly_kernel(X, X, d), _poly_kernel(Y, Y, d), _poly_kernel(X, Y, d)
    sum_xx = (kxx.sum() - np.trace(kxx)) / (m * (m - 1))
    sum_yy = (kyy.sum() - np.trace(kyy)) / (n * (n - 1))
    sum_xy = kxy.sum() / (m * n)
    return float(sum_xx + sum_yy - 2 * sum_xy)


def kid(real, syn, B=200, seed=0, frac=0.8):
    """MMD² không chệch giữa real và syn (đã chuẩn hoá), CI theo SUBSAMPLING KHÔNG HOÀN LẠI (`frac` phần
    mỗi nhóm, B lần), lấy khoảng 2,5-97,5%. Trước dùng bootstrap CÓ hoàn lại (lấy lại mẫu, có thể trùng
    điểm): điểm trùng kéo kxx/kyy (nhân trong nội bộ nhóm) lên cao hơn thực tế vì một điểm "giống chính
    nó" tuyệt đối, đẩy MMD² bootstrap lệch lên so với giá trị gốc, có lúc CI nằm hẳn TRÊN điểm ước lượng
    (không bao được điểm chính nó). Subsampling không hoàn lại không có điểm trùng nên không mang lệch đó,
    đổi lại mẫu con nhỏ hơn gốc nên CI hơi rộng hơn — đánh đổi hợp lý vì mục tiêu là CI đáng tin, không
    phải CI chặt nhất. Mẫu quá nhỏ (dưới MIN_N mỗi bên, hoặc mẫu con sau khi nhân `frac` dưới MIN_N) trả
    None vì dưới 5 điểm không có nghĩa thống kê."""
    real, syn = np.asarray(real, float), np.asarray(syn, float)
    if len(real) < MIN_N or len(syn) < MIN_N:
        return None
    value = _mmd2_unbiased(real, syn)
    n_r = max(MIN_N, min(len(real), int(round(len(real) * frac))))
    n_s = max(MIN_N, min(len(syn), int(round(len(syn) * frac))))
    rng = np.random.default_rng(seed)
    boot = np.empty(B)
    for i in range(B):
        r_idx = rng.choice(len(real), n_r, replace=False)
        s_idx = rng.choice(len(syn), n_s, replace=False)
        boot[i] = _mmd2_unbiased(real[r_idx], syn[s_idx])
    lo, hi = np.percentile(boot, [2.5, 97.5])
    return {"value": value, "ci_low": float(lo), "ci_high": float(hi)}


def density_coverage(real, syn, k=5):
    """Density/coverage theo Naeem 2020 (Reliable Fidelity and Diversity Metrics), khoảng cách Euclid
    trên đặc trưng đã chuẩn hoá. Bán kính k-NN tính trên real (bỏ chính điểm đó), k bị cắt về n_real - 1
    khi mẫu thật quá ít (lớp W0003 có thể chỉ 7-43 mẫu)."""
    real, syn = np.asarray(real, float), np.asarray(syn, float)
    n, m = len(real), len(syn)
    if n < 2 or m < 1:
        return {"density": None, "coverage": None}
    kk = max(1, min(k, n - 1))
    d_rr = cdist(real, real)
    np.fill_diagonal(d_rr, np.inf)
    radii = np.partition(d_rr, kk - 1, axis=1)[:, kk - 1]
    d_rs = cdist(real, syn)              # (n, m): khoảng cách mỗi điểm thật tới mỗi điểm sinh
    within = d_rs <= radii[:, None]      # Y_j có rơi vào quả cầu bán kính NND_k(X_i) quanh X_i không
    density = float(within.sum() / (kk * m))
    coverage = float(within.any(axis=1).mean())
    return {"density": density, "coverage": coverage}
