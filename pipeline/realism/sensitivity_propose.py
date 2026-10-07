"""Bước 4 (pha 3): đề xuất núm theo ma trận độ nhạy đã đo (`realism/sensitivity_screen`), thay cho luật tay
(`issues._rule`) khi còn hợp lệ.

propose(result, current, sens) -> (núm mới, lý do, mode). mode:
    "data"  — sens có, núm sản xuất hiện tại khớp điểm gốc của lần đo (base_knobs) → dùng ma trận.
    "stale" — sens có nhưng núm đã lệch điểm gốc → về luật tay (issues.propose), ghi rõ lý do.
    "none"  — chưa đo độ nhạy lần nào → về luật tay.

Thuật toán mode "data", cho từng mục tiêu TRƯỢT (issues.evaluate):
    1. Vấn đề còn ở mặc định VÀ chưa núm nào của nó có trong ma trận → giữ luật cũ: nhảy thẳng giá trị sửa, bỏ qua
       các mục tiêu của vấn đề đó ở bước sau (như issues.propose).
    2. Mục tiêu còn lại: cần = khoảng thiếu để đạt (có biên 5%, xem `_need`). Ứng viên = biến thể có hiệu ứng CÓ
       Ý NGHĨA (CI loại trừ 0) và cùng chiều với cần. λ = cần/hiệu ứng, kẹp [0,5; 2,0]. Dự báo tuyến tính cộng dồn
       mọi mục tiêu đã biết: đo + Σ λ·Δ(mục tiêu). Bỏ ứng viên nếu dự báo biến một mục tiêu ĐANG ĐẠT thành trượt.
       Xếp hạng ứng viên còn lại theo tỉ lệ cần được đáp ứng (giảm dần), rồi |λ| nhỏ hơn. Mỗi nhóm biến thể và mỗi
       núm chỉ dùng một lần trong cả đề xuất.
    3. Không có ứng viên nào → ghi lý do "chưa có núm đẩy được" hoặc "mọi núm đẩy được đều làm hỏng <mục tiêu khác>".

Mọi núm mới đều qua kẹp sổ đăng ký (REGISTRY), làm tròn INT_KNOBS, và giữ cận dưới ≤ cận trên cho hai cặp núm
(post_depth, pore_aspect) bằng cách đổi chỗ — như knobs.resolve().

predict(result, sens, moves) tách riêng để test/UI xem dự báo của một tổ hợp bước λ mà không gọi lại propose.
"""
import json
from pathlib import Path

from . import issues
from .knobs import INT_KNOBS, REGISTRY

SENS_PATH = Path(__file__).resolve().parent / "state" / "sensitivity.json"
_SWAP_PAIRS = (("post_depth_min", "post_depth_max"), ("pore_aspect_min", "pore_aspect_max"),
               ("linear_pore_aspect_min", "linear_pore_aspect_max"))
LAMBDA_MIN, LAMBDA_MAX = 0.5, 2.0


def read_sensitivity(path=None):
    """sensitivity.json đã nạp, hoặc None nếu vắng/hỏng (không có ma trận → mode luật tay)."""
    try:
        d = json.loads((path or SENS_PATH).read_text(encoding="utf-8"))
        return d if isinstance(d, dict) and d.get("variants") else None
    except (OSError, ValueError):
        return None


def _clamp_knob(name, v):
    lo, hi = REGISTRY[name][2], REGISTRY[name][3]
    v = min(max(v, lo), hi)
    return int(round(v)) if name in INT_KNOBS else round(v, 4)


def _finalize(knobs_dict):
    out = {k: (_clamp_knob(k, v) if k in REGISTRY else v) for k, v in knobs_dict.items()}
    for a, b in _SWAP_PAIRS:
        if a in out and b in out and out[a] > out[b]:
            out[a], out[b] = out[b], out[a]
    return out


def _base_matches_current(sens, current):
    base = sens.get("base_knobs") or {}
    return all(abs(base.get(k, REGISTRY[k][4]) - current.get(k, REGISTRY[k][4])) < 1e-6 for k in REGISTRY)


def _margin(t):
    if t["op"] == "between":
        lo, hi = t["value"]
        return 0.05 * (hi - lo)
    return 0.05 * abs(t["value"])


def _gap(v, t):
    """Khoảng cách từ giá trị v tới vùng đạt (0 khi đã đạt): thước đo "tệ thêm" cho mục tiêu đang trượt."""
    if t["op"] == ">=":
        return max(0.0, t["value"] - v)
    if t["op"] == "<=":
        return max(0.0, v - t["value"])
    lo, hi = t["value"]
    return max(0.0, lo - v, v - hi)


def _need(t, v=None):
    """Lượng phải đổi giá trị v (mặc định giá trị đo) để đạt mục tiêu (có biên 5%), âm nghĩa là phải GIẢM."""
    m, v = _margin(t), (t["measured"] if v is None else v)
    if t["op"] == ">=":
        return t["value"] + m - v
    if t["op"] == "<=":
        return t["value"] - m - v
    lo, hi = t["value"]
    return (lo + m - v) if v < lo else (hi - m - v)


def _pre_rule(ev, current, sens=None):
    """Vấn đề còn ở mặc định → giữ luật cũ (issues.propose): nhảy thẳng giá trị sửa đề xuất, bỏ qua mục tiêu của
    vấn đề đó ở bước đo độ nhạy. Trả (núm đổi, lý do, {núm đã đụng}, {id vấn đề đã xử lý})."""
    new, why, touched, handled = {}, [], set(), set()
    for iss in ev:
        failing = [t for t in iss["targets"] if t["pass"] is False]
        if not failing or not iss["knobs"]:
            continue
        # Núm đã có trong ma trận độ nhạy → để dữ liệu quyết (lần đo đủ 2/10: làm dày nứt và 3 núm dải không thấu
        # không giúp mục tiêu nào có ý nghĩa, còn làm C2ST tệ thêm; nhảy thẳng giá trị sửa sẽ đặt cả chúng).
        measured = {k for v in (sens or {}).get("variants", []) for k in v.get("changed", {})}
        if set(iss["knobs"]) & measured:
            continue
        if all(current[k] == REGISTRY[k][4] for k in iss["knobs"]):
            new.update({k: REGISTRY[k][5] for k in iss["knobs"]})
            touched |= set(iss["knobs"])
            handled.add(iss["id"])
            why.append(f"Vấn đề {iss['id']}: núm còn ở mặc định, đặt giá trị sửa đề xuất")
    return new, why, touched, handled


def predict(result, sens, moves, significant_only=False):
    """{nhãn mục tiêu: giá trị dự báo} sau khi áp `moves` ([(biến thể, λ), ...]) lên kết quả đo hiện tại.
    Dự báo tuyến tính cộng dồn: đo + Σ λ·Δ (Δ thiếu ở biến thể đó cho mục tiêu này → coi như 0)."""
    ev = issues.evaluate(result)
    effects = sens.get("effects", {})
    out = {}
    for iss in ev:
        for t in iss["targets"]:
            if t["measured"] is None:
                continue
            pred = t["measured"]
            for variant, lam in moves:
                eff = (effects.get(variant["id"], {}).get("targets", {}) or {}).get(t["label"])
                if significant_only and not (eff or {}).get("significant"):
                    continue
                pred += lam * ((eff or {}).get("delta") or 0)
            out[t["label"]] = pred
    return out


def _candidates(t, need, sens, used_groups, touched):
    effects = sens.get("effects", {})
    out = []
    for variant in sens.get("variants", []):
        if variant["group"] in used_groups or set(variant.get("changed", {})) & touched:
            continue
        eff = (effects.get(variant["id"], {}).get("targets", {}) or {}).get(t["label"])
        delta = (eff or {}).get("delta") if eff and eff.get("significant") else None
        if not delta or (need > 0) != (delta > 0):
            continue
        lam = min(LAMBDA_MAX, max(LAMBDA_MIN, need / delta))
        frac = min(1.0, (lam * delta) / need) if need else 0.0
        out.append((variant, lam, frac))
    out.sort(key=lambda c: (-c[2], abs(c[1])))
    return out


def _harm(ev, t, before, after, before_sig, after_sig):
    """Nhãn mục tiêu bị bước này làm hại, hoặc None. Hại = (a) mục tiêu đang ĐẠT bị dự báo thành trượt; (b) mục tiêu
    đang TRƯỢT bị đẩy xa vùng đạt hơn (vd làm tối nông khi tỉ lệ chạm lỗi đang thấp, như chốt của luật tay,
    review H3); (c) chính mục tiêu t không gần vùng đạt hơn (mục tiêu "between" bị sàn λ đẩy vượt sang phía bên
    kia, review M1). before/after: dự báo trước và sau bước này."""
    for iss in ev:
        for u in iss["targets"]:
            lab = u["label"]
            if lab not in after or u["pass"] is None:
                continue
            if u["pass"] is True and not issues.passes(after[lab], u):
                return lab
            # (b) chỉ tính hiệu ứng CÓ Ý NGHĨA: hiệu ứng nhỏ trong nhiễu (CI chứa 0) không được chặn bước có ích
            # (đo đủ 2/10: −0,04 và −0,02 không ý nghĩa ở dao động biên không thấu từng chặn mọi núm cho rỗ khí).
            if u["pass"] is False and u is not t and lab in after_sig and \
                    _gap(after_sig[lab], u) > _gap(before_sig.get(lab, u["measured"]), u) + 1e-9:
                return lab
    if _gap(after[t["label"]], t) >= _gap(before.get(t["label"], t["measured"]), t):
        return t["label"]
    return None


def _pick_candidate(result, sens, ev, t, need, used_groups, touched, accepted):
    cands = _candidates(t, need, sens, used_groups, touched)
    before = predict(result, sens, accepted)
    before_sig = predict(result, sens, accepted, significant_only=True)
    broke_label = None
    for variant, lam, _frac in cands:
        pred = predict(result, sens, accepted + [(variant, lam)])
        pred_sig = predict(result, sens, accepted + [(variant, lam)], significant_only=True)
        broke = _harm(ev, t, before, pred, before_sig, pred_sig)
        if broke is None:
            return variant, lam, pred
        broke_label = broke_label or broke
    if cands and broke_label:
        return None, None, f"{t['label']}: mọi núm đẩy được đều làm hỏng {broke_label}"
    run_id = sens.get("run_id", "?")
    return None, None, f"{t['label']}: chưa có núm nào đẩy được (đo {run_id})"


def _propose_data(result, current, sens):
    ev = issues.evaluate(result)
    new, why, touched, handled = _pre_rule(ev, current, sens)
    new = {**current, **new}
    used_groups, accepted = set(), []
    for iss in ev:
        if iss["id"] in handled:
            continue
        for t in iss["targets"]:
            if t["pass"] is not False:
                continue
            # Tính từ DỰ BÁO sau các bước đã nhận, không từ giá trị đo: một biến thể hay đẩy nhiều mục tiêu cùng
            # lúc (vd nhoè mép hạ độ dốc biên cả 3 loại), không cộng thêm bước cho mục tiêu đã dự báo đạt (review H2).
            now = predict(result, sens, accepted).get(t["label"], t["measured"])
            if issues.passes(now, t):
                why.append(f"{t['label']}: dự báo đạt ({now:.3g}) nhờ bước đã chọn, không vặn thêm")
                continue
            need = _need(t, now)
            if not need:
                continue
            variant, lam, info = _pick_candidate(result, sens, ev, t, need, used_groups, touched, accepted)
            if variant is None:
                why.append(info)
                continue
            for k, (base_v, new_v) in variant["changed"].items():
                new[k] = new.get(k, current[k]) + lam * (new_v - base_v)
            used_groups.add(variant["group"])
            touched |= set(variant["changed"])
            accepted.append((variant, lam))
            predicted = info.get(t["label"]) if isinstance(info, dict) else None
            why.append(f"{t['label']}: đo {t['measured']:.3g}, dự báo {predicted:.3g} "
                       f"(λ={lam:.2f}, biến thể {variant['id']})")
    return _finalize(new), why


def propose(result, current, sens):
    # Pha 2a (plan w0003-reference): ma trận độ nhạy sens.json được đo trên THƯỚC CŨ (sáu tiêu chí); khi bản
    # tốt nhất đã ở thước mới (v2), áp ma trận cũ coi như vẫn còn đúng là sai (mục tiêu trượt/đạt của hai thước
    # không khớp nhau). Không có luật tay nào thay thế (đó là việc bước 2d: đo độ nhạy lại trên thước mới), nên
    # không đổi núm, báo rõ lý do; cũng vì vậy không gọi tới issues.propose/_pre_rule (luật thước cũ).
    from . import loop_gate
    best = loop_gate.read_best()
    if best and best.get("ruler") == "v2":
        return dict(current), ["chưa có số đo độ nhạy theo thước mới, đặt núm tay hoặc chạy đo độ nhạy (bước 2d)"], "none"
    if sens is None:
        new, why = issues.propose(result, current)
        return new, why + ["chưa có số đo độ nhạy"], "none"
    if not _base_matches_current(sens, current):
        new, why = issues.propose(result, current)
        run_id = sens.get("run_id", "?")
        return new, why + [f"độ nhạy đã cũ: núm hiện tại khác điểm gốc lần đo {run_id}"], "stale"
    new, why = _propose_data(result, current, sens)
    return new, why, "data"
