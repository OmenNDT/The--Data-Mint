"""5 vấn đề độ thật: phát hiện, việc cần làm, núm vặn, mục tiêu đo được (theo RIAWELC), luật tự vặn cho vòng lặp.

Mục tiêu đọc từ result.json của realism.evaluate. Thống kê: med (trung vị sinh), auc, lt45 (tỉ lệ vùng đứng), ratio
(trung vị sinh / trung vị thật), iqr_lo (phân vị 25% phía sinh). Luật tự vặn: mỗi mục tiêu trượt đẩy núm liên quan một
bước về phía mục tiêu, kẹp trong giới hạn sổ đăng ký; núm còn ở mặc định thì nhảy thẳng tới giá trị sửa đề xuất.
"""
from .knobs import REGISTRY

MAIN = ("CR↔crack", "PO↔porosity", "LP↔lack_of_penetration", "LP↔lack_of_fusion")  # LF: lớp LP của RIAWELC


def _t(pair, crit, stat, op, value, label):
    return {"pair": pair, "crit": crit, "stat": stat, "op": op, "value": value, "label": label}


ISSUES = [
    {"id": 1, "title": "Mép quá gắt và quá đều", "types": ["crack", "porosity", "lack_of_penetration", "lack_of_fusion"],
     "finding": "Độ dốc tại biên gấp 2 tới 3 lần RIAWELC ở cả 6 cặp; độ dao động dọc biên thấp: mép sắc đều như cắt dán, "
                "do hậu xử lý nhân một hệ số làm tối đều khắp mặt nạ.",
     "action": "Hạ độ sâu làm tối, cho độ sâu thay đổi dọc lỗi, nhoè mép hơn (apply_dark_defect_convention).",
     "knobs": ["post_depth_min", "post_depth_max", "post_modulation", "post_edge_blur_sigma", "controlnet_strength"],
     "targets": [_t(p, "bien_doc", "ratio", "<=", 1.5, f"{p}: độ dốc tại biên ≤ 1,5 lần thật") for p in MAIN]
     + [_t(p, "bien_daodong", "auc", ">=", 0.35, f"{p}: dao động dọc biên, AUC ≥ 0,35") for p in MAIN]
     + [_t(p, "_hit", "hit", ">=", 0.70, f"{p}: tỉ lệ vùng chạm lỗi ≥ 0,7 (lỗi còn thấy được)") for p in MAIN]},
    {"id": 2, "title": "Nứt chỉ nằm một hướng", "types": ["crack"],
     "finding": "RIAWELC có 42% vết nứt đứng, ảnh sinh 0,7% (bộ sinh chỉ cho lệch ±15° quanh phương ngang); nứt sinh mảnh "
                "và thưa: độ đặc 0,54 so với 0,72, độ đầy hộp bao 0,27 so với 0,47.",
     "action": "Xoay một tỉ lệ vết nứt thành vết đứng gọn trong dải mối hàn, làm dày vệt nứt (realism/mask_shaping.py).",
     "knobs": ["crack_transverse_share", "crack_widen_px"],
     "targets": [_t("CR↔crack", "vung_huong", "lt45", ">=", 0.25, "Tỉ lệ vết nứt đứng ≥ 25% (thật 42%)"),
                 _t("CR↔crack", "vung_dac", "med", ">=", 0.65, "Độ đặc ≥ 0,65 (thật 0,72)"),
                 _t("CR↔crack", "vung_dayhop", "med", ">=", 0.40, "Độ đầy hộp bao ≥ 0,40 (thật 0,47)")]},
    {"id": 3, "title": "Rỗ khí quá tròn và quá đặc", "types": ["porosity"],
     "finding": "Độ lệch tâm 0,62 so với 0,82, độ đặc 0,97 so với 0,91: lỗ khí sinh gần như elip hoàn hảo, lỗ thật hơi "
                "thuôn và mép không đều.",
     "action": "Kéo thuôn từng lỗ giữ diện tích, trục gần phương ngang, làm mép gồ ghề (realism/mask_shaping.py).",
     "knobs": ["pore_aspect_min", "pore_aspect_max", "pore_axis_jitter_deg", "pore_irregularity_px"],
     "targets": [_t("PO↔porosity", "vung_lechtam", "med", "between", [0.72, 0.90], "Độ lệch tâm 0,72 tới 0,90 (thật 0,82)"),
                 _t("PO↔porosity", "vung_dac", "auc", "<=", 0.65, "Độ đặc, AUC ≤ 0,65")]},
    {"id": 4, "title": "Không thấu là dải thẳng tắp", "types": ["lack_of_penetration"],
     "finding": "Góc sinh 89,8° tới 90,0°, thật 86° tới 89,5°; độ đầy hộp bao 0,89 so với 0,63, độ đặc 0,93 so với 0,79: "
                "dải thật lượn và đứt đoạn.",
     "action": "Nghiêng dải, cho dải lượn, cắt khoảng đứt (realism/mask_shaping.py).",
     "knobs": ["lop_tilt_max_deg", "lop_wave_amp_px", "lop_gap_max"],
     "targets": [_t("LP↔lack_of_penetration", "vung_huong", "iqr_lo", "<=", 89.0, "Phân vị 25% của góc ≤ 89° (thật 86°)"),
                 _t("LP↔lack_of_penetration", "vung_dayhop", "med", "between", [0.50, 0.72], "Độ đầy hộp bao 0,50 tới 0,72 (thật 0,63)"),
                 _t("LP↔lack_of_penetration", "vung_dac", "med", "<=", 0.85, "Độ đặc ≤ 0,85 (thật 0,79)")]},
    {"id": 5, "title": "Giữ nguyên chỗ đã giống thật", "types": [],
     "finding": "Độ lệch tâm của nứt và góc nghiêng của rỗ khí đã giống RIAWELC (AUC gần 0,5).",
     "action": "Không sửa; chốt hồi quy sau mỗi vòng, nhất là sau khi xoay nứt (2) và kéo thuôn lỗ khí (3).",
     "knobs": [],
     "targets": [_t("CR↔crack", "vung_lechtam", "auc", "between", [0.35, 0.65], "Nứt: độ lệch tâm, AUC 0,35 tới 0,65"),
                 _t("PO↔porosity", "vung_huong", "auc", "between", [0.35, 0.65], "Rỗ khí: góc nghiêng, AUC 0,35 tới 0,65")]},
]


def value_of(result, t):
    p = next((x for x in (result or {}).get("pairs", []) if x["pair"] == t["pair"]), None)
    if t["stat"] == "hit":
        return p.get("hit") if p else None
    d = (p or {}).get("crit", {}).get(t["crit"], {})
    if "syn_med" not in d:
        return None
    return {"med": d["syn_med"], "auc": d.get("auc"), "lt45": d.get("syn_lt45"), "iqr_lo": d["syn_iqr"][0],
            "ratio": d["syn_med"] / d["real_med"] if d["real_med"] else None}[t["stat"]]


def passes(v, t):
    if v is None:
        return None
    if t["op"] == "<=":
        return v <= t["value"]
    if t["op"] == ">=":
        return v >= t["value"]
    return t["value"][0] <= v <= t["value"][1]


def evaluate(result):
    out = []
    for iss in ISSUES:
        ts = [{**t, "measured": value_of(result, t)} for t in iss["targets"]]
        for t in ts:
            t["pass"] = passes(t["measured"], t)
        known = [t["pass"] for t in ts if t["pass"] is not None]
        status = "na" if not known else "pass" if all(known) else "fail"
        out.append({k: iss[k] for k in ("id", "title", "finding", "action", "knobs", "types")} | {"targets": ts, "status": status})
    return out


def _clamp(name, v):
    lo, hi = REGISTRY[name][2], REGISTRY[name][3]
    return min(max(v, lo), hi)


def propose(result, current):
    """Núm mới cho vòng sau và lý do. current: {tên: giá trị}. Chỉ đụng núm của vấn đề đang trượt; mỗi núm đổi tối đa
    một bước mỗi vòng, tính từ giá trị hiện tại (không cộng dồn khi nhiều mục tiêu cùng trượt)."""
    new, why, touched = dict(current), [], set()
    ev = evaluate(result)
    low_hit = [t["pair"] for i in ev for t in i["targets"] if t["stat"] == "hit" and t["pass"] is False]
    for iss in ev:
        failing = [t for t in iss["targets"] if t["pass"] is False]
        if not failing or not iss["knobs"]:
            continue
        if all(current[k] == REGISTRY[k][4] for k in iss["knobs"]):
            new.update({k: REGISTRY[k][5] for k in iss["knobs"]})
            touched |= set(iss["knobs"])
            why.append(f"Vấn đề {iss['id']}: núm còn ở mặc định, đặt giá trị sửa đề xuất")
            continue
        for t in failing:
            if t["crit"] == "bien_doc" and low_hit:
                why.append(f"Vấn đề 1: không làm tối nông thêm vì độ phát hiện đang thấp ở {', '.join(low_hit)}")
                continue
            step = _rule(t, current)
            if not step:
                continue
            fresh = {k: _clamp(k, v) for k, v in step[0].items() if k not in touched}
            if fresh:
                new.update(fresh)
                touched |= set(fresh)
                why.append(f"Vấn đề {iss['id']}: {t['label']} (đo {t['measured']:.3g}) → {step[1]}")
    return new, why


def _rule(t, k):
    """Một bước vặn cho một mục tiêu trượt: ({núm: giá trị mới}, lời giải thích). Mỗi đặc tính một núm chính để các
    luật không giằng co: độ dốc biên ← độ sâu, độ nhoè; dao động ← độ thay đổi; góc dải ← độ nghiêng; độ đầy hộp và độ
    đặc của dải ← độ lượn (đo ở mức mặt nạ: thêm khoảng đứt lại làm tăng cả hai, nên không dùng)."""
    c, v, s = t["crit"], t["measured"], t["stat"]
    if s == "hit":
        return {"post_depth_min": k["post_depth_min"] * 1.15, "post_depth_max": k["post_depth_max"] * 1.15,
                "controlnet_strength": k["controlnet_strength"] + 0.05}, \
            "làm tối sâu hơn 15%, ControlNet bám mask thêm 0,05 cho lỗi thấy được và khớp nhãn"
    if c == "bien_doc":
        return {"post_depth_min": k["post_depth_min"] * 0.85, "post_depth_max": k["post_depth_max"] * 0.85,
                "post_edge_blur_sigma": k["post_edge_blur_sigma"] + 0.5,
                "controlnet_strength": k["controlnet_strength"] - 0.05}, \
            "làm tối nông hơn 15%, nhoè mép thêm 0,5, ControlNet bớt bám mask 0,05"
    if c == "bien_daodong":
        return {"post_modulation": k["post_modulation"] + 0.1}, "tăng độ thay đổi độ sâu thêm 0,1"
    if c == "vung_huong" and s == "lt45":
        return {"crack_transverse_share": k["crack_transverse_share"] + 0.1}, "tăng tỉ lệ nứt đứng thêm 0,1"
    if c in ("vung_dac", "vung_dayhop") and t["pair"] == "CR↔crack":
        return {"crack_widen_px": k["crack_widen_px"] + 1}, "làm dày vệt nứt thêm 1 điểm ảnh"
    if c == "vung_lechtam" and t["pair"] == "PO↔porosity":
        d = 0.2 if v < t["value"][0] else -0.2
        return {"pore_aspect_min": k["pore_aspect_min"] + d, "pore_aspect_max": k["pore_aspect_max"] + d}, \
            f"{'kéo thuôn thêm' if d > 0 else 'bớt thuôn'} 0,2"
    if c == "vung_dac" and t["pair"] == "PO↔porosity":
        return {"pore_irregularity_px": k["pore_irregularity_px"] + 0.5}, "mép lỗ khí gồ ghề thêm 0,5 điểm ảnh"
    if c == "vung_huong" and s == "iqr_lo":
        return {"lop_tilt_max_deg": k["lop_tilt_max_deg"] + 1}, "cho dải nghiêng thêm 1°"
    if c in ("vung_dayhop", "vung_dac") and t["pair"] == "LP↔lack_of_penetration":
        hi = v > (t["value"][1] if t["op"] == "between" else t["value"])
        return {"lop_wave_amp_px": k["lop_wave_amp_px"] + (0.5 if hi else -0.5)}, \
            f"cho dải lượn {'thêm' if hi else 'bớt'} 0,5 điểm ảnh"
    return None
