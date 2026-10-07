"""Bước 5 (plan 261003): một vòng chỉ sinh lại các loại lỗi mà núm vừa đổi chạm tới; loại khác dùng lại số đo của
bản tốt nhất.

An toàn vì: loại dùng lại có mọi núm liên quan giữ nguyên, cùng ca đề thi (seed + nền), SD tất định và bước làm tối
khoá ngẫu nhiên theo ca (loại + seed, sửa 2/10) → sinh lại sẽ ra đúng ảnh cũ. Dùng lại số đo chỉ bỏ bớt GPU, không
đổi kết quả cổng nghiệm thu ở các loại đó.
"""
import json
from pathlib import Path

from . import loop_gate
from .evaluate import DEFECT_METRICS_RULER
from .generator_hooks import TYPE_KNOBS
from .knobs import REGISTRY
from .loop_common import history
from .runlog import read_json


def changed_knobs(cand, best):
    return sorted(k for k in REGISTRY if cand.get(k, REGISTRY[k][4]) != best.get(k, REGISTRY[k][4]))


# Núm làm tối riêng theo nhóm loại (không nằm trong TYPE_KNOBS vì TYPE_KNOBS quyết định có tạo hình lại mask không).
DARKEN_TYPE_KNOBS = {"pore_post_depth_min": {"porosity", "clustered_porosity", "linear_porosity"},
                     "pore_post_depth_max": {"porosity", "clustered_porosity", "linear_porosity"},
                     "clustered_post_depth_min": {"clustered_porosity"}, "clustered_post_depth_max": {"clustered_porosity"},
                     "linear_post_depth_min": {"linear_porosity"}, "linear_post_depth_max": {"linear_porosity"},
                     "linear_post_modulation": {"linear_porosity"},
                     "slag_post_depth_min": {"slag_inclusion"}, "slag_post_depth_max": {"slag_inclusion"},
                     "ecav_post_depth_min": {"elongated_cavity"}, "ecav_post_depth_max": {"elongated_cavity"},
                     "lop_post_depth_min": {"lack_of_penetration"}, "lop_post_depth_max": {"lack_of_penetration"},
                     "crack_post_depth_min": {"crack"}, "crack_post_depth_max": {"crack"}}


def affected_types(cand, best, selected):
    """Loại trong `selected` bị núm đổi chạm tới: núm riêng (TYPE_KNOBS) → chỉ loại sở hữu; núm chung → mọi loại."""
    hit = set()
    for k in changed_knobs(cand, best):
        owners = DARKEN_TYPE_KNOBS.get(k) or {t for t, ks in TYPE_KNOBS.items() if k in ks}
        hit |= (owners & set(selected)) if owners else set(selected)
    return [t for t in selected if t in hit]


def _cases_per_type(source):
    """{loại: số ca} từ fixed-jobs.json của thư mục ảnh bản tốt nhất; {} nếu không có (bộ ngẫu nhiên cũ)."""
    try:
        jobs = json.loads((Path(source) / "fixed-jobs.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    out = {}
    for c in jobs:
        out[c["defect_type"]] = out.get(c["defect_type"], 0) + 1
    return out


def coverage(best):
    """{loại: số ca} bản tốt nhất đã sinh trên bộ đề thi: ưu tiên "coverage" trong result đã ghép (vòng chỉ sinh vài
    loại có thư mục ảnh thiếu loại dùng lại), không có thì đọc fixed-jobs.json của thư mục ảnh nguồn."""
    result = read_json(best["eval_run"], "result.json") or {}
    if result.get("coverage"):
        return result["coverage"]
    rec = next((r for r in history() if r.get("iter") == best["iter"] and r.get("eval_run") == best["eval_run"]), None)
    return _cases_per_type((rec or {}).get("source") or result.get("source"))


def _best_ruler_outdated(best):
    """True nếu bản tốt nhất đo bằng sơ đồ thước KHÁC sơ đồ hiện hành (follow-up 7/10: thước theo loại đổi
    thì mọi số đo cũ không còn so được, xem evaluate.DEFECT_METRICS_RULER/reference_w0003.RULER_SCHEME_ID).
    best chưa từng có defect_metrics (ruler=None, bản rất cũ) KHÔNG coi là lỗi thời ở đây — giữ hành vi gốc
    (coverage theo fixed-jobs.json) cho trường hợp đó, chỉ chặn khi CÓ ruler cũ và nó khác ruler hiện hành."""
    result = read_json(best["eval_run"], "result.json") or {}
    best_ruler = (result.get("defect_metrics") or {}).get("ruler")
    return best_ruler is not None and best_ruler != DEFECT_METRICS_RULER


def plan_cycle(cand, types, n):
    """(loại cần sinh, loại dùng lại, bản tốt nhất hoặc None). Dùng lại khi: loại không bị ảnh hưởng VÀ bản tốt nhất
    đã sinh đúng n ca của loại đó trên bộ đề thi (khác n thì tập ca khác, không dùng lại được).

    Thước đổi (ruler khác, xem _best_ruler_outdated): KHÔNG dùng lại loại nào — sinh lại toàn bộ `types` của
    vòng này để đặt mốc mới sạch (follow-up 7/10, người dùng duyệt), dù núm không đổi."""
    best = loop_gate.read_best()
    if not best:
        return list(types), [], None
    if _best_ruler_outdated(best):
        return list(types), [], best
    have = coverage(best)
    best_knobs = {k: v["value"] for k, v in (best.get("knobs") or {}).items()}
    hit = set(affected_types(cand, best_knobs, types))
    gen = [t for t in types if t in hit or have.get(t) != n]
    # Loại bản tốt nhất có nhưng vòng này không chọn: mang theo nguyên số đo nếu núm đổi không chạm tới nó, để bản
    # tốt nhất mới không mất loại (vd vòng chỉ chọn rỗ khí, 40 ca). Núm chung đổi thì số đo cũ hết đúng → không mang.
    others = [t for t in have if t not in types]
    carry = [t for t in others if t not in set(affected_types(cand, best_knobs, others))]
    return gen, [t for t in types if t not in gen] + carry, best


def merge(new_result, best_result, reused_types, best_eval_run, best_coverage=None):
    """Kết quả đầy đủ của vòng: pairs + cases của loại sinh lại lấy từ new_result, loại dùng lại lấy nguyên best_result."""
    reused = set(reused_types)
    out = dict(new_result)
    out["pairs"] = ([p for p in new_result.get("pairs", []) if p.get("synthetic") not in reused]
                    + [p for p in best_result.get("pairs", []) if p.get("synthetic") in reused])
    out["cases"] = ([c for c in new_result.get("cases", []) if c.get("kind") not in reused]
                    + [c for c in best_result.get("cases", []) if c.get("kind") in reused])
    out["reused"] = {"from_eval_run": best_eval_run, "types": sorted(reused)}
    # Thước mới (defect_metrics) cũng phải ghép: thiếu bước này, kết quả vòng chỉ còn loại sinh lại, issues_v2 thấy
    # "đạt hết" và cổng v2 chỉ xét một loại (lỗi thấy 6/10, vòng 14 chỉ sinh rỗ khí ghi all_pass True).
    nd, bd = new_result.get("defect_metrics") or {}, best_result.get("defect_metrics") or {}
    if nd.get("types") is not None and not nd.get("error"):
        types = {t: v for t, v in nd["types"].items() if t not in reused}
        types.update({t: v for t, v in (bd.get("types") or {}).items() if t in reused})
        out["defect_metrics"] = {**nd, "types": types}
    cov = {t: k for t, k in (best_coverage or {}).items() if t in reused}
    cov.update(_cases_per_type(new_result.get("source")))
    out["coverage"] = cov
    return out


def merge_into_eval_run(eval_run, reused_types, best):
    """Ghi đè result.json của lượt đo vừa xong bằng bản đã ghép (trước khi qua cổng)."""
    from .runlog import RunLog
    new_result = read_json(eval_run, "result.json") or {}
    best_result = read_json(best["eval_run"], "result.json") or {}
    RunLog(eval_run).write_json("result.json", merge(new_result, best_result, reused_types, best["eval_run"],
                                                     coverage(best)))
