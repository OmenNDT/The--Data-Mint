"""Thống kê so hai nhóm cho vòng độ thật, chỉ numpy và scipy (venv pipeline không có sklearn).

auc: P(một mẫu sinh > một mẫu thật), 0,5 là không phân biệt được. ks: khoảng cách Kolmogorov-Smirnov.
c2st: bộ phân loại thật hay sinh trên sáu tiêu chí (hồi quy logistic có thêm bậc hai, chuẩn hoá, phạt L2, Newton),
AUC kiểm chéo 5 phần. Khác bản đo đầu dùng cây tăng cường, nên số C2ST có thể thấp hơn chút: so giữa các vòng, đừng so
với bản cũ.
"""
import numpy as np
from scipy import stats


def auc(syn, real):
    a, b = np.asarray(syn, float), np.asarray(real, float)
    a, b = a[np.isfinite(a)], b[np.isfinite(b)]
    if not len(a) or not len(b):
        return None
    return float(stats.mannwhitneyu(a, b).statistic / (len(a) * len(b)))


def ks(syn, real):
    return float(stats.ks_2samp(syn, real).statistic) if len(syn) and len(real) else None


def _fit_logistic(X, y, lam=1e-2, iters=30):
    w = np.zeros(X.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-np.clip(X @ w, -30, 30)))
        g = X.T @ (p - y) + lam * w
        H = (X * (p * (1 - p))[:, None]).T @ X + lam * np.eye(len(w))
        step = np.linalg.solve(H, g)
        w -= step
        if np.abs(step).max() < 1e-6:
            break
    return w


def c2st(real, syn, folds=5, seed=0, max_real=3000):
    """AUC kiểm chéo của bộ phân loại thật hay sinh. real, syn: mảng (n, 6). Lấy mẫu thật tối đa max_real cho nhanh."""
    real, syn = np.asarray(real, float), np.asarray(syn, float)
    if len(syn) < 10 or len(real) < 10:
        return None
    rng = np.random.default_rng(seed)
    if len(real) > max_real:
        real = real[rng.choice(len(real), max_real, replace=False)]
    X = np.vstack([real, syn])
    y = np.r_[np.zeros(len(real)), np.ones(len(syn))]
    X = (X - X.mean(0)) / (X.std(0) + 1e-9)
    X = np.hstack([np.ones((len(X), 1)), X, X ** 2])
    idx = rng.permutation(len(X))
    score = np.zeros(len(X))
    for f in range(folds):
        test = idx[f::folds]
        train = np.setdiff1d(idx, test)
        score[test] = X[test] @ _fit_logistic(X[train], y[train])
    return auc(score[y == 1], score[y == 0])
