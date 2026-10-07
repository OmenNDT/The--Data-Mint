"""Phần tính toán bốn độ đo ghép cặp cho cổng v2 (realism/loop_gate_v2.py): tách riêng để tệp quyết định
dưới 200 dòng, không đổi hành vi. Xem docstring loop_gate_v2.py cho ý nghĩa "phí tổn" (_cost) và cách ghép cặp.
"""
import numpy as np

from . import defect_metrics as dm
from .defect_metrics_density import MIN_N as _KID_MIN_N
from .defect_metrics_density import _mmd2_unbiased

METRICS = ("c2st", "kid", "density", "coverage")
METRIC_LABEL = {"c2st": "C2ST", "kid": "KID", "density": "Density", "coverage": "Coverage"}


def _cost(value, metric):
    """Quy một giá trị độ đo về "phí tổn" (càng thấp càng giống thật) để so chung một luật cho cả 4 độ đo."""
    if value is None:
        return None
    if metric == "density":
        return abs(value - 1.0)
    if metric == "coverage":
        return -value
    return value


def point_metrics(real, syn):
    """4 độ đo tại một điểm (không CI): C2ST trung vị 3 hạt giống (nhanh hơn seeds=5 mặc định, đủ ổn định cho
    vòng bootstrap), KID là giá trị MMD2 thô (không gọi lại CI nội bộ của defect_metrics_density.kid: vòng này
    đã tự bootstrap theo ca, lặp CI bên trong nữa sẽ lãng phí B² lần tính)."""
    c2st = dm.c2st_median(real, syn, seeds=3)
    std_real, std_syn = dm.rank_normal(real, syn)
    kid_val = _mmd2_unbiased(std_real, std_syn) if len(std_real) >= _KID_MIN_N and len(std_syn) >= _KID_MIN_N else None
    dc = dm.density_coverage(std_real, std_syn)
    return {"c2st": c2st, "kid": kid_val, "density": dc["density"], "coverage": dc["coverage"]}


def paired_metrics(real, new_mat, best_mat, B, seed):
    """{độ đo: {new, best, delta, ci_low, ci_high, verdict}} ghép cặp trên ca chung (new_mat/best_mat cùng số
    hàng, cùng thứ tự ca). delta/CI theo "phí tổn" (_cost); verdict suy từ CI của phí tổn, không phải giá trị
    thô: tốt hơn nếu CI hoàn toàn dưới 0, tệ hơn nếu hoàn toàn trên 0, còn lại không đổi."""
    n = len(new_mat)
    point_new, point_best = point_metrics(real, new_mat), point_metrics(real, best_mat)
    rng = np.random.default_rng(seed)
    boot_delta = {m: [] for m in METRICS}
    for b in range(B):
        idx = rng.integers(0, n, n)                 # CÙNG chỉ số mẫu lại cho cả hai vòng (ghép cặp)
        vn, vb = point_metrics(real, new_mat[idx]), point_metrics(real, best_mat[idx])
        for m in METRICS:
            cn, cb = _cost(vn[m], m), _cost(vb[m], m)
            if cn is not None and cb is not None:
                boot_delta[m].append(cn - cb)
    out = {}
    for m in METRICS:
        cn, cb = _cost(point_new[m], m), _cost(point_best[m], m)
        entry = {"new": point_new[m], "best": point_best[m],
                  "delta": (cn - cb) if cn is not None and cb is not None else None}
        boots = boot_delta[m]
        if boots:
            lo, hi = float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))
            entry["ci_low"], entry["ci_high"] = lo, hi
            entry["verdict"] = "better" if hi < 0 else "worse" if lo > 0 else "same"
        else:
            entry["verdict"] = "same"
        out[m] = entry
    return out
