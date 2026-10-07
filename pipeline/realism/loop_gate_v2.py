"""Cổng nghiệm thu v2 (bước 2a plan w0003-reference, người dùng duyệt nguyên tắc 6/10): so vòng mới với bản
TỐT NHẤT trên thước 16 đặc trưng khuyết tật + tham chiếu W0003 thật, bốn độ đo (C2ST, KID, density, coverage)
VÀ tỉ lệ tách được vùng.

Nguyên tắc (người dùng duyệt): cổng dùng cả 4 độ đo; tỉ lệ tách được vùng là điều kiện CHẶN — sinh không được
thấp hơn thật quá 10 điểm % VÀ không cải thiện rõ (≥ 2 điểm %) so bản tốt nhất thì loại thẳng, dù 4 độ đo kia
tốt lên (lỗi quá mờ không dùng huấn luyện được, xem phát hiện 6/10 trong plan).

So cặp (paired): chỉ trên ca (case_id) có ở CẢ HAI vòng và có vùng tách được (has_region) ở CẢ HAI — bootstrap
B lần trên các ca chung, mỗi lần dùng CÙNG chỉ số mẫu lại cho vòng mới lẫn bản tốt nhất (ghép cặp triệt nhiễu
do khác bộ ca, như loop_gate v1 / paired_stats). Bốn độ đo quy về "phí tổn" (càng thấp càng giống thật) để
dùng chung một luật: C2ST, KID giữ nguyên; density đổi thành |density − 1|; coverage đổi dấu (coverage càng
cao càng tốt). Quyết định mỗi độ đo theo CI 95% của hiệu phí tổn (mới − tốt nhất): tốt hơn nếu CI hoàn toàn
dưới 0, tệ hơn nếu CI hoàn toàn trên 0, còn lại coi là không đổi.

Quyết định chung: loại (rejected) nếu CÓ loại bị chặn tỉ lệ tách vùng, HOẶC có độ đo tệ hơn rõ ở bất kỳ loại
nào. Nhận (accepted) nếu không bị loại VÀ có ít nhất một độ đo tốt hơn rõ ở đâu đó. Còn lại: giữ nguyên
(neutral). Loại không đủ 10 ca chung có vùng, hoặc tham chiếu W0003 dưới 10 ca thật có vùng: chỉ báo
("ignored"), không ảnh hưởng quyết định.
"""
import time

import numpy as np

from . import issues_v2
from . import knobs
from . import loop_gate as _v1
from . import reference_w0003
from . import tuning_memory
from .defect_features16 import DEFECT_FEATURES
from .loop_gate_v2_metrics import METRIC_LABEL, paired_metrics

MIN_COMMON_CASES = 10      # dưới mức này không so cặp được một loại (khớp MIN_C2ST_ROWS của defect_eval)
MIN_REAL_ROWS = 10         # tham chiếu W0003 dưới mức này không dùng làm cổng (chỉ báo, xem rủi ro trong plan)
DETECT_GAP_LIMIT = 0.10    # điều kiện CHẶN: sinh không thấp hơn thật quá 10 điểm % (người dùng duyệt 6/10)
DETECT_IMPROVE_MIN = 0.02  # chặn vẫn giữ nếu chưa cải thiện ít nhất 2 điểm % so bản tốt nhất


def _types_considered(rec_types, new_dm, best_dm):
    """Loại đủ điều kiện so cặp: có mặt ở cả hai vòng (rec_types nếu vòng chỉ nhắm một số loại), có tham chiếu
    W0003 (reference không None), KHÔNG chỉ tham khảo (reference_only, xem defect_eval.REFERENCE_ONLY_TYPES —
    hiện chỉ metallic_inclusion, bước 3 plan 261006-defect-metrics-w0003-reference; trước đây chỉ bị bỏ qua
    NGẦM qua MIN_REAL_ROWS vì n_real=3, giờ loại rõ để không phụ thuộc n_real có đổi sau này), và tham chiếu
    đủ >= MIN_REAL_ROWS ca thật có vùng ở CẢ HAI lần đo (cùng tệp w0003-defect-features.csv nên n_real lẽ ra
    bằng nhau, kiểm cả hai cho chắc)."""
    pool = set(rec_types) if rec_types else set(new_dm)
    out = []
    for t in sorted(pool & set(new_dm) & set(best_dm)):
        ne, be = new_dm.get(t) or {}, best_dm.get(t) or {}
        if ne.get("reference") is None or be.get("reference") is None:
            continue
        if ne.get("reference_only") or be.get("reference_only"):
            continue
        if (ne.get("n_real") or 0) < MIN_REAL_ROWS or (be.get("n_real") or 0) < MIN_REAL_ROWS:
            continue
        out.append(t)
    return out


def _type_entry(t, ne, be, seed, B):
    """Một mục v2 cho loại `t`: điều kiện chặn tách vùng + (nếu đủ ca chung) bốn độ đo ghép cặp."""
    det_real = ne.get("detection_rate_real")
    det_real = det_real if det_real is not None else be.get("detection_rate_real")
    det_new, det_best = ne.get("detection_rate_syn"), be.get("detection_rate_syn")
    gap_new = (det_real - det_new) if det_real is not None and det_new is not None else None
    gap_best = (det_real - det_best) if det_real is not None and det_best is not None else None
    blocked = bool(gap_new is not None and gap_new > DETECT_GAP_LIMIT
                   and (gap_best is None or gap_new > gap_best - DETECT_IMPROVE_MIN))
    entry = {"n_real": ne.get("n_real"), "null": ne.get("null"),
             "detection": {"real": det_real, "new": det_new, "best": det_best,
                           "gap_new": gap_new, "gap_best": gap_best, "blocked": blocked}}

    new_cases = {c["case_id"]: c for c in (ne.get("cases") or []) if c.get("case_id") is not None and c.get("has_region")}
    best_cases = {c["case_id"]: c for c in (be.get("cases") or []) if c.get("case_id") is not None and c.get("has_region")}
    common = sorted(set(new_cases) & set(best_cases))
    entry["n_common"] = len(common)
    if len(common) < MIN_COMMON_CASES:
        entry["metrics"] = {}
        entry["skip_reason"] = f"chỉ {len(common)} ca chung có vùng tách được (cần >= {MIN_COMMON_CASES}), không so cặp bốn độ đo được"
        return entry, blocked
    try:
        real_df = reference_w0003.load_reference(t)
    except (ValueError, FileNotFoundError) as e:
        entry["metrics"] = {}
        entry["skip_reason"] = f"không đọc được tham chiếu W0003: {e}"
        return entry, blocked
    real = real_df.loc[real_df["has_region"].astype(bool), DEFECT_FEATURES].dropna().to_numpy(float)
    new_mat = np.array([[new_cases[c][k] for k in DEFECT_FEATURES] for c in common])
    best_mat = np.array([[best_cases[c][k] for k in DEFECT_FEATURES] for c in common])
    entry["metrics"] = paired_metrics(real, new_mat, best_mat, B, seed)
    return entry, blocked


def _mean_point_c2st(types_dm, type_list):
    """C2ST16 trung bình các loại đang xét (mục "score" của best.json / cột lịch sử, câu hỏi 7 của plan)."""
    keys = type_list or list(types_dm or {})
    vals = [types_dm[t]["c2st"] for t in keys if (types_dm or {}).get(t) and types_dm[t].get("c2st") is not None]
    return float(np.mean(vals)) if vals else None


def _fmt(v):
    return "—" if v is None else f"{v:.3f}"


def gate_v2(rec, best, new_result, best_result, B=200, seed=0):
    """rec: dòng lịch sử của vòng vừa đo. best/best_result: bản tốt nhất đã có (None nếu chưa có vòng nào).
    Trả rec thêm ruler/decision/reasons/compared_to/v2/all_pass, với tác dụng phụ (ghi best.json, lùi núm thử,
    tuning_memory) như loop_gate v1.

    old_ruler (follow-up 7/10, thước THEO LOẠI): ngoài hai lý do cũ (chưa có bản tốt nhất, bản tốt nhất chưa
    có defect_metrics), còn coi là "thước cũ" khi defect_metrics["ruler"] (định danh sơ đồ chọn vùng, xem
    evaluate.DEFECT_METRICS_RULER/reference_w0003.RULER_SCHEME_ID) của bản tốt nhất KHÁC vòng hiện tại — số
    đo hai bên không còn cùng thước, so cặp vô nghĩa, nên đặt mốc mới ngay (nhánh "mốc mới: thước mới" có sẵn)."""
    rec["ruler"] = "v2"
    new_types = (new_result.get("defect_metrics") or {}).get("types") or {}
    rec["all_pass"] = issues_v2.all_pass(new_result)         # thay all_pass v1 (issues.py) khi thước là v2

    old_ruler = (best is None
                 or not ((best_result or {}).get("defect_metrics") or {}).get("types")
                 or (best_result.get("defect_metrics") or {}).get("ruler")
                 != (new_result.get("defect_metrics") or {}).get("ruler"))
    if old_ruler:
        mean_c2 = _mean_point_c2st(new_types, rec.get("types"))
        _v1._write_best({"iter": rec["iter"], "eval_run": rec["eval_run"], "knobs": rec.get("knobs"),
                         "score": {"mean_c2st16": mean_c2}, "ruler": "v2", "ts": time.time()})
        rec.update(decision="best", reasons=["mốc mới: thước mới"], compared_to=None,
                   v2={"types": {}, "ignored": [], "mean_c2st16": mean_c2})
        return rec

    best_types = (best_result.get("defect_metrics") or {}).get("types") or {}
    considered = _types_considered(rec.get("types"), new_types, best_types)
    ignored = sorted(set(new_types) - set(considered))
    if not considered:
        rec.update(decision="neutral", compared_to=best["iter"], v2={"types": {}, "ignored": ignored},
                   reasons=["không có loại lỗi nào đủ điều kiện so cặp (cần tham chiếu W0003 >= "
                            f"{MIN_REAL_ROWS} ca thật có vùng, có mặt ở cả hai vòng)"])
        return rec

    per_type, blocked_types, worse, better = {}, [], [], []
    for i, t in enumerate(considered):
        entry, blocked = _type_entry(t, new_types[t], best_types[t], seed * 97 + i, B)
        if t in (rec.get("reused_types") or []):
            # Loại dùng lại số đo bản tốt nhất (vòng chỉ sinh vài loại): khoảng cách tách vùng y hệt bản tốt nhất nên
            # luôn "chưa cải thiện"; chặn nó là loại oan cả vòng (lỗi thấy 7/10, vòng 15 chỉ đổi nứt bị chặn bởi LF/LP).
            blocked = False
            entry.setdefault("detection", {})["blocked"] = False
        per_type[t] = entry
        if blocked:
            blocked_types.append(t)
        for m, v in entry.get("metrics", {}).items():
            label = f"{t}: {METRIC_LABEL[m]} (mới {_fmt(v['new'])} so tốt nhất {_fmt(v['best'])})"
            if v["verdict"] == "worse":
                worse.append(label)
            elif v["verdict"] == "better":
                better.append(label)

    reasons = []
    for t in blocked_types:
        d = per_type[t]["detection"]
        reasons.append(f"{t}: tỉ lệ tách vùng sinh kém thật {100 * d['gap_new']:.1f} điểm % (giới hạn "
                        f"{100 * DETECT_GAP_LIMIT:.0f}), chưa cải thiện đủ so bản tốt nhất "
                        f"(trước kém {100 * (d['gap_best'] or 0):.1f} điểm %)")
    mean_c2 = _mean_point_c2st(new_types, considered)
    if blocked_types or worse:
        reasons += [f"tệ hơn rõ: {r}" for r in worse]
        decision = "rejected"
        best_knobs, rejected_knobs = _v1._plain(best.get("knobs")), _v1._plain(rec.get("knobs"))
        tuning_memory.record_rejection(best_knobs, rejected_knobs)
        knobs.write_many(best_knobs or dict(knobs.DEFAULTS), "cổng nghiệm thu",
                         "loại vòng (thước mới), về núm bản tốt nhất", store="candidate")
    elif better:
        reasons = [f"tốt hơn rõ: {r}" for r in better]
        decision = "accepted"
        _v1._write_best({"iter": rec["iter"], "eval_run": rec["eval_run"], "knobs": rec.get("knobs"),
                         "score": {"mean_c2st16": mean_c2}, "ruler": "v2", "ts": time.time()})
        tuning_memory.clear(_v1._plain(rec.get("knobs")).keys())
    else:
        reasons, decision = ["không khác rõ bản tốt nhất (thước mới)"], "neutral"

    rec.update(decision=decision, reasons=reasons, compared_to=best["iter"],
               v2={"types": per_type, "ignored": ignored, "mean_c2st16": mean_c2})
    return rec
