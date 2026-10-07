"""Cổng nghiệm thu (bước 3): so vòng mới với vòng TỐT NHẤT đã có (không phải vòng ngay trước) trên ca chung
(case_id), quyết định nhận/giữ nguyên/loại núm thử; giữ realism/state/best.json; gọi tuning_memory khi loại.

Điểm vòng = (số mục tiêu issues.py đạt, C2ST trung bình các cặp đang nhắm) — so theo thứ tự đó (n_pass trước).
Ghép cặp chỉ áp dụng giữa hai vòng đều có result["cases"] (dùng bộ đề thi cố định, bước 2); vòng không có "cases"
(bộ ngẫu nhiên cũ) không so được — vòng có "cases" ĐẦU TIÊN tự thành mốc "bản tốt nhất" (ghi "mốc mới: bộ đề thi").

Nhận (accepted): không mục tiêu "phải giữ" nào bị trượt, VÀ điểm tốt hơn rõ (n_pass tăng, hoặc C2ST giảm rõ theo CI).
Loại (rejected): một mục tiêu "phải giữ" (đang đạt ở bản tốt nhất) bị trượt, HOẶC điểm tệ hơn rõ. Núm thử lùi về
đúng núm của bản tốt nhất; tuning_memory ghi hướng đã thử cho các núm vừa đổi.
Giữ nguyên (neutral): không khác rõ bản tốt nhất, núm thử GIỮ (không lùi) — vòng sau đề xuất tiếp từ đây.
"""
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from . import issues, knobs, paired_stats, tuning_memory
from .features import CRITERIA, REF_DIR
from .runlog import read_json
from .stats import c2st

STATE = Path(__file__).resolve().parent / "state"
BEST_PATH = STATE / "best.json"
GATE_B = 200          # bootstrap trong vòng lặp/HMI (nhanh, interactive); báo cáo cuối gọi lại với B=1000


def read_best():
    try:
        return json.loads(BEST_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write_best(rec):
    STATE.mkdir(parents=True, exist_ok=True)
    tmp = BEST_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(BEST_PATH)


def _plain(nested):
    """{tên: {"value":...}} -> {tên: giá trị}; an toàn với dict rỗng/None (khác knobs.values() hay rơi về
    kho sản xuất khi dict rỗng vì `resolved or resolve()`)."""
    return {k: v["value"] for k, v in (nested or {}).items()}


def has_cases(result):
    return bool((result or {}).get("cases"))


def _fmt(v):
    return "—" if v is None else f"{v:+.3f}"


def score(result, types=None, pair_labels=None):
    """(số mục tiêu issues.py đạt, C2ST trung bình các cặp đang nhắm — None nếu không cặp nào có C2ST).
    pair_labels: chỉ tính trên các cặp này (cổng truyền các cặp CÓ Ở CẢ HAI vòng, để vòng 4 loại không "hơn" vòng
    1 loại chỉ vì đếm được nhiều mục tiêu hơn, lỗi thấy 2/10: "đạt 14 so 3 mục tiêu")."""
    ev = issues.evaluate(result)
    # đếm theo MỤC TIÊU (không theo vấn đề): một mục tiêu chuyển sang đạt là một bước tiến dù vấn đề chưa đạt trọn
    n_pass = sum(1 for i in ev for t in i["targets"]
                 if t["pass"] is True and (pair_labels is None or t["pair"] in pair_labels))
    pairs = (result or {}).get("pairs", [])
    if types:
        pairs = [p for p in pairs if p.get("synthetic") in types]
    if pair_labels is not None:
        pairs = [p for p in pairs if p["pair"] in pair_labels]
    vals = [p["c2st"] for p in pairs if p.get("c2st") is not None]
    return n_pass, (float(np.mean(vals)) if vals else None)


def _must_keep_targets(best_result):
    """Mục tiêu đang ĐẠT ở bản tốt nhất: bộ "phải giữ" — thay vấn đề 5 cứng làm lưới chặn hồi quy, bao luôn
    các mục tiêu của vấn đề 5 (chúng cũng nằm trong issues.evaluate như mọi vấn đề khác)."""
    return [t for i in issues.evaluate(best_result) for t in i["targets"] if t["pass"] is True]


def _mean_c2st_delta(best_result, new_result, pair_labels, B=GATE_B, seed=0):
    """Bootstrap CI (theo ca, ghép cặp case_id chung mỗi cặp loại) của delta = TB(C2ST mới) − TB(C2ST tốt nhất)
    trên các cặp đang nhắm. None cả ba nếu không cặp nào có ≥5 ca chung."""
    if not pair_labels:
        return None, None, None
    rng = np.random.default_rng(seed)
    real_df = pd.read_csv(REF_DIR / "riawelc-six-criteria.csv")
    real_df = real_df[real_df.vung_sodom > 0]
    cb_all, cn_all = paired_stats._cases_by_pair(best_result), paired_stats._cases_by_pair(new_result)
    deltas_per_b, points = [], []
    for pair in pair_labels:
        cb = {c["case_id"]: c for c in cb_all.get(pair, [])}
        cn = {c["case_id"]: c for c in cn_all.get(pair, [])}
        common = sorted(set(cb) & set(cn))
        rc = paired_stats._PAIR_RC.get(pair)
        if len(common) < 5 or not rc:
            continue
        real_mat = real_df[real_df.cls == rc][list(CRITERIA)].values
        mb = np.array([[cb[c][k] for k in CRITERIA] for c in common])
        mn = np.array([[cn[c][k] for k in CRITERIA] for c in common])
        pb, pn = c2st(real_mat, mb, seed=seed), c2st(real_mat, mn, seed=seed)
        if pb is None or pn is None:
            continue
        points.append(pn - pb)
        boots = []
        for b in range(B):
            idx = rng.integers(0, len(common), len(common))
            vb, vn = c2st(real_mat, mb[idx], seed=seed * 1009 + b), c2st(real_mat, mn[idx], seed=seed * 1009 + b)
            if vb is not None and vn is not None:
                boots.append(vn - vb)
        if boots:
            deltas_per_b.append(boots)
    if not points:
        return None, None, None
    delta = float(np.mean(points))
    if not deltas_per_b:
        return delta, None, None
    minlen = min(len(d) for d in deltas_per_b)
    agg = np.mean(np.array([d[:minlen] for d in deltas_per_b]), axis=0)
    return delta, float(np.percentile(agg, 2.5)), float(np.percentile(agg, 97.5))


def gate(rec, B=GATE_B, seed=0):
    """rec: dòng lịch sử của vòng vừa đo (đã có eval_run/iter/knobs/types); trả rec thêm
    decision/reasons/compared_to, với tác dụng phụ (ghi best.json, lùi núm thử, tuning_memory) khi cần.

    Pha 2a (plan w0003-reference): vòng đo được bằng thước mới (defect_metrics.types có dữ liệu, không lỗi)
    đi qua loop_gate_v2 (bốn độ đo + điều kiện chặn tỉ lệ tách vùng); vòng cũ (chưa có defect_metrics, hoặc
    lỗi khi đo) vẫn qua cổng v1 dưới đây, để không vỡ lịch sử/test cũ."""
    new_result = read_json(rec["eval_run"], "result.json") or {}
    new_dm = new_result.get("defect_metrics") or {}
    if new_dm.get("types") and not new_dm.get("error"):
        from . import loop_gate_v2
        best = read_best()
        best_result = (read_json(best["eval_run"], "result.json") or {}) if best else None
        return loop_gate_v2.gate_v2(rec, best, new_result, best_result, B=B, seed=seed)

    best = read_best()
    types = rec.get("types")

    if best is None or not has_cases(read_json(best["eval_run"], "result.json") or {}):
        if has_cases(new_result):
            n_pass, mean_c2st = score(new_result, types)
            _write_best({"iter": rec["iter"], "eval_run": rec["eval_run"], "knobs": rec.get("knobs"),
                         "score": {"n_pass": n_pass, "mean_c2st": mean_c2st}, "ts": time.time()})
            rec.update(decision="best", reasons=["mốc mới: bộ đề thi"], compared_to=None)
        else:
            rec.update(decision="neutral", reasons=["chưa dùng bộ đề thi cố định, không so được"], compared_to=None)
        return rec

    best_result = read_json(best["eval_run"], "result.json") or {}
    must_keep = _must_keep_targets(best_result)
    ev_new = {t["label"]: t for i in issues.evaluate(new_result) for t in i["targets"]}
    broke = [t["label"] for t in must_keep if ev_new.get(t["label"], {}).get("pass") is False]

    pair_labels = sorted({p["pair"] for p in new_result.get("pairs", []) if not types or p.get("synthetic") in types}
                          & {p["pair"] for p in best_result.get("pairs", [])})
    if not pair_labels:
        rec.update(decision="neutral", reasons=["không có loại lỗi chung với bản tốt nhất, không so được"],
                   compared_to=best["iter"])
        return rec
    n_best, c2st_best = score(best_result, types, pair_labels)
    n_new, c2st_new = score(new_result, types, pair_labels)
    delta, ci_lo, ci_hi = _mean_c2st_delta(best_result, new_result, pair_labels, B=B, seed=seed)

    score_worse = (n_new < n_best) or (ci_lo is not None and ci_lo > 0)
    score_better = (not score_worse) and (n_new > n_best or (ci_hi is not None and ci_hi < 0))

    if broke or score_worse:
        reasons = [f"trượt mục tiêu đang đạt: {lbl}" for lbl in broke]
        if score_worse:
            reasons.append(f"điểm tệ hơn rõ (đạt {n_new} so {n_best} mục tiêu, ΔC2ST={_fmt(delta)})")
        best_knobs, rejected_knobs = _plain(best.get("knobs")), _plain(rec.get("knobs"))
        tuning_memory.record_rejection(best_knobs, rejected_knobs)
        knobs.write_many(best_knobs or dict(knobs.DEFAULTS), "cổng nghiệm thu", "loại vòng, về núm bản tốt nhất",
                         store="candidate")
        rec.update(decision="rejected", reasons=reasons, compared_to=best["iter"])
    elif score_better:
        _write_best({"iter": rec["iter"], "eval_run": rec["eval_run"], "knobs": rec.get("knobs"),
                     "score": {"n_pass": n_new, "mean_c2st": c2st_new}, "ts": time.time()})
        tuning_memory.clear(_plain(rec.get("knobs")).keys())
        rec.update(decision="accepted", reasons=[f"tốt hơn rõ (đạt {n_new} so {n_best} mục tiêu, ΔC2ST={_fmt(delta)})"],
                   compared_to=best["iter"])
    else:
        rec.update(decision="neutral", reasons=["không khác rõ bản tốt nhất"], compared_to=best["iter"])
    return rec
