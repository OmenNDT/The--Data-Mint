"""Bootstrap theo ca (ghép cặp theo case_id) cho vòng độ thật: dùng result.json của realism.evaluate.run
khi vòng sinh trên bộ đề thi cố định (realism/exam_set.py) — mỗi hàng result["cases"] có case_id khớp
giữa các vòng vì cùng nền + cùng seed.

B=1000 lần mẫu lại có hoàn lại THEO CA (không theo điểm ảnh): một lần mẫu lại chọn lại cả hàng sáu tiêu chí
của ca đó, giữ tương quan giữa các tiêu chí trong cùng ca. Ảnh thật (RIAWELC) không có case_id khớp ảnh sinh
nên GIỮ CỐ ĐỊNH (không mẫu lại) — chỉ bên sinh được mẫu lại, như C2ST đã làm trong evaluate.c2st (seed để tạo lại).

API cho bước 3 (cổng nghiệm thu):
    bootstrap_targets(result, B=1000, seed=0) -> [{pair, crit, stat, label, measured, n, ci_low, ci_high}, ...]
        CI 95% của giá trị đo (med/auc/ratio/lt45/iqr_lo/hit) cho từng mục tiêu issues.py trên MỘT vòng.
    bootstrap_criteria(result, B=1000, seed=0) -> {pair: {n, crit: {k: {median, ci_low, ci_high, auc, auc_ci_*}},
        c2st: {value, ci_low, ci_high}}}
        CI 95% trung vị + AUC từng tiêu chí và C2ST cho từng cặp loại trên MỘT vòng.
    compare_paired(prev, new, B=1000, seed=0) -> {label: {pair, crit, stat, prev, new, delta, n_common,
        ci_low, ci_high, significant}}
        So hai vòng trên ca CHUNG (case_id có ở cả hai): delta tính trên ca chung (cùng tập với CI); significant = khoảng tin cậy
        95% của delta không chứa 0. Bước 3 cộng "significant và delta cùng dấu mong muốn" thành nhận/loại vòng.
"""
import numpy as np
import pandas as pd

from . import issues
from .evaluate import PAIRS
from .features import CRITERIA, REF_DIR
from .stats import auc, c2st

_PAIR_RC = {f"{rc}↔{kind}": rc for rc, kind in PAIRS}


def _real_rows():
    df = pd.read_csv(REF_DIR / "riawelc-six-criteria.csv")
    return df[df.vung_sodom > 0]


def _cases_by_pair(result, used_only=True):
    """{pair: [ca]}. used_only: chỉ ca dùng được (có sáu tiêu chí); result cũ không có cờ "used" coi như dùng được
    (trước đây cases chỉ chứa ca dùng được). Tỉ lệ chạm lỗi cần used_only=False để đúng mẫu số."""
    out = {}
    for c in (result or {}).get("cases", []):
        if used_only and not c.get("used", True):
            continue
        out.setdefault(c["pair"], []).append(c)
    return out


def _aggregate(stat, vals, real_arr=None, real_med=None):
    """Một thống kê từ một mẫu (đã mẫu lại hay chưa) các giá trị thô của một tiêu chí/hit."""
    vals = np.asarray(vals, float)
    if stat == "med":
        return float(np.median(vals))
    if stat == "hit":
        return float(np.mean(vals))
    if stat == "iqr_lo":
        return float(np.percentile(vals, 25))
    if stat == "lt45":
        return float(np.mean(vals < 45))
    if stat == "ratio":
        return float(np.median(vals) / real_med) if real_med else None
    if stat == "auc":
        return auc(vals, real_arr) if real_arr is not None else None
    raise ValueError(f"thống kê không rõ: {stat}")


def _real_arr_and_med(pair, crit, real_df):
    rc = _PAIR_RC.get(pair)
    if not rc:
        return None, None
    rdf = real_df[real_df.cls == rc]
    if not len(rdf) or crit not in rdf:
        return None, None
    arr = rdf[crit].values
    return arr, float(np.median(arr))


def _target_case_values(result, t):
    """case_id -> giá trị thô (tiêu chí hoặc hit) cho một mục tiêu issues.py, trong một vòng."""
    hit = t["stat"] == "hit"
    col = "hit" if hit else t["crit"]
    return {c["case_id"]: c[col] for c in _cases_by_pair(result, used_only=not hit).get(t["pair"], []) if col in c}


def _measured(result, t, vals, real_arr, real_med):
    """Giá trị đo của một mục tiêu: dùng result["pairs"] (tính trên TOÀN BỘ ảnh, kể cả ảnh không có case_id)
    nếu có; không có (vd result chỉ còn "cases", test đơn vị) thì tính thẳng từ các ca có case_id."""
    v = issues.value_of(result, t)
    if v is not None:
        return v
    if not len(vals):
        return None
    try:
        return _aggregate(t["stat"], vals, real_arr, real_med)
    except ValueError:
        return None


def bootstrap_targets(result, B=1000, seed=0):
    """CI 95% bootstrap theo ca cho giá trị đo của từng mục tiêu issues.py, trên một vòng (không ghép cặp)."""
    rng = np.random.default_rng(seed)
    real_df = _real_rows()
    out = []
    for iss in issues.ISSUES:
        for t in iss["targets"]:
            case_vals = _target_case_values(result, t)
            vals = np.array(list(case_vals.values()))
            real_arr, real_med = (_real_arr_and_med(t["pair"], t["crit"], real_df)
                                   if t["stat"] in ("auc", "ratio") else (None, None))
            entry = {"pair": t["pair"], "crit": t["crit"], "stat": t["stat"], "label": t["label"],
                     "measured": _measured(result, t, vals, real_arr, real_med), "n": len(vals)}
            if len(vals) >= 5:
                boots = []
                for _ in range(B):
                    samp = vals[rng.integers(0, len(vals), len(vals))]
                    v = _aggregate(t["stat"], samp, real_arr, real_med)
                    if v is not None and np.isfinite(v):
                        boots.append(v)
                if boots:
                    entry["ci_low"] = float(np.percentile(boots, 2.5))
                    entry["ci_high"] = float(np.percentile(boots, 97.5))
            out.append(entry)
    return out


def bootstrap_criteria(result, B=1000, seed=0):
    """CI 95% bootstrap theo ca: trung vị + AUC từng tiêu chí, và C2ST, cho từng cặp loại trên một vòng."""
    rng = np.random.default_rng(seed)
    real_df = _real_rows()
    out = {}
    for pair, cs in _cases_by_pair(result).items():
        n = len(cs)
        if n < 5:
            continue
        rc = _PAIR_RC.get(pair)
        real_mat = real_df[real_df.cls == rc][list(CRITERIA)].values if rc else None
        mat = np.array([[c[k] for k in CRITERIA] for c in cs])
        crit_out = {}
        boot_meds = np.array([np.median(mat[rng.integers(0, n, n)], axis=0) for _ in range(B)])
        for j, k in enumerate(CRITERIA):
            d = {"median": float(np.median(mat[:, j])),
                 "ci_low": float(np.percentile(boot_meds[:, j], 2.5)),
                 "ci_high": float(np.percentile(boot_meds[:, j], 97.5))}
            if real_mat is not None:
                d["auc"] = auc(mat[:, j], real_mat[:, j])
            crit_out[k] = d
        pair_out = {"n": n, "crit": crit_out}
        if real_mat is not None:
            point = c2st(real_mat, mat, seed=seed)
            boots = [v for v in (c2st(real_mat, mat[rng.integers(0, n, n)], seed=seed * 1000 + b)
                                  for b in range(B)) if v is not None]
            if boots:
                pair_out["c2st"] = {"value": point, "ci_low": float(np.percentile(boots, 2.5)),
                                    "ci_high": float(np.percentile(boots, 97.5))}
        out[pair] = pair_out
    return out


def compare_paired(prev, new, B=1000, seed=0):
    """So hai vòng trên ca CHUNG, mẫu lại cùng chỉ số cho cả hai (ghép cặp: triệt nhiễu do khác bộ ca)."""
    rng = np.random.default_rng(seed)
    real_df = _real_rows()
    out = {}
    for iss in issues.ISSUES:
        for t in iss["targets"]:
            vp, vn = _target_case_values(prev, t), _target_case_values(new, t)
            common = sorted(set(vp) & set(vn))
            real_arr, real_med = (_real_arr_and_med(t["pair"], t["crit"], real_df)
                                   if t["stat"] in ("auc", "ratio") else (None, None))
            mp = _measured(prev, t, np.array(list(vp.values())), real_arr, real_med)
            mn = _measured(new, t, np.array(list(vn.values())), real_arr, real_med)
            # prev/new: giá trị đo của từng vòng trên TOÀN BỘ ảnh (đúng số mục tiêu dùng để xét đạt/trượt).
            # delta: tính trên CA CHUNG, cùng tập với bootstrap, nên luôn nằm cùng phía CI (trước đây delta = new − prev
            # trên hai tập ca khác nhau, có lúc nằm ngoài chính CI của nó). delta_full = new − prev để đối chiếu.
            entry = {"pair": t["pair"], "crit": t["crit"], "stat": t["stat"], "label": t["label"],
                     "prev": mp, "new": mn, "n_common": len(common), "delta": None,
                     "delta_full": (mn - mp) if mp is not None and mn is not None else None}
            ap, an = np.array([vp[c] for c in common]), np.array([vn[c] for c in common])
            if len(common):
                cp, cn = _aggregate(t["stat"], ap, real_arr, real_med), _aggregate(t["stat"], an, real_arr, real_med)
                if cp is not None and cn is not None:
                    entry["delta"] = cn - cp
            if len(common) >= 5 and entry["delta"] is not None:
                deltas = []
                for _ in range(B):
                    idx = rng.integers(0, len(common), len(common))   # cùng chỉ số cho cả hai vòng
                    vvp = _aggregate(t["stat"], ap[idx], real_arr, real_med)
                    vvn = _aggregate(t["stat"], an[idx], real_arr, real_med)
                    if vvp is not None and vvn is not None and np.isfinite(vvp) and np.isfinite(vvn):
                        deltas.append(vvn - vvp)
                if deltas:
                    lo, hi = float(np.percentile(deltas, 2.5)), float(np.percentile(deltas, 97.5))
                    entry.update(ci_low=lo, ci_high=hi, significant=bool(lo > 0 or hi < 0))
            out[t["label"]] = entry
    return out
