"""Bước 4 (độ nhạy): danh sách nhóm núm đem đo, mỗi nhóm một bước lệch quanh điểm gốc (núm sản xuất hiện tại).

Một biến thể = điểm gốc + một nhóm lệch một bước (một phía hoặc hai phía). Mọi thứ khác giữ nguyên, ca đề thi giữ
nguyên (ghép cặp theo case_id), nên chênh lệch đo được chỉ do nhóm đó gây ra.

mode "replay": núm chỉ dùng ở bước làm tối sau khi SD vẽ xong (post_darkening.darken), tính lại bằng CPU trên ảnh
               trước-làm-tối của lượt gốc (tất định, không tốn GPU).
mode "generate": núm đổi mặt nạ hoặc ControlNet, phải sinh lại bằng GPU, chỉ cho các loại núm đó chạm tới.
Núm có cặp cận dưới/trên (độ sâu, tỉ lệ trục lỗ khí) dịch cả cặp cùng lượng để giữ nguyên độ rộng khoảng.
"""
from .knobs import INT_KNOBS, REGISTRY

ALL_TYPES = ["crack", "porosity", "lack_of_penetration", "lack_of_fusion"]

# tên nhóm → núm: bước lệch (cộng), loại bị ảnh hưởng, cách tính, có đo hai phía không
GROUPS = {
    "post_depth": {"knobs": {"post_depth_min": 0.10, "post_depth_max": 0.10}, "types": ALL_TYPES,
                   "mode": "replay", "two_sided": True},
    "post_modulation": {"knobs": {"post_modulation": 0.15}, "types": ALL_TYPES, "mode": "replay", "two_sided": True},
    "post_modulation_sigma": {"knobs": {"post_modulation_sigma": 3.0}, "types": ALL_TYPES, "mode": "replay",
                              "two_sided": True},
    "post_edge_blur_sigma": {"knobs": {"post_edge_blur_sigma": 0.75}, "types": ALL_TYPES, "mode": "replay",
                             "two_sided": True},
    "controlnet_strength": {"knobs": {"controlnet_strength": 0.10}, "types": ALL_TYPES, "mode": "generate",
                            "two_sided": True},
    "crack_transverse_share": {"knobs": {"crack_transverse_share": 0.30}, "types": ["crack"], "mode": "generate",
                               "two_sided": False},
    "crack_widen_px": {"knobs": {"crack_widen_px": 2.0}, "types": ["crack"], "mode": "generate", "two_sided": False},
    "pore_aspect": {"knobs": {"pore_aspect_min": 0.5, "pore_aspect_max": 0.5}, "types": ["porosity"],
                    "mode": "generate", "two_sided": False},
    "pore_axis_jitter_deg": {"knobs": {"pore_axis_jitter_deg": 15.0}, "types": ["porosity"], "mode": "generate",
                             "two_sided": True},
    "pore_irregularity_px": {"knobs": {"pore_irregularity_px": 1.5}, "types": ["porosity"], "mode": "generate",
                             "two_sided": False},
    "lop_tilt_max_deg": {"knobs": {"lop_tilt_max_deg": 3.0}, "types": ["lack_of_penetration"], "mode": "generate",
                         "two_sided": False},
    "lop_wave_amp_px": {"knobs": {"lop_wave_amp_px": 2.0}, "types": ["lack_of_penetration"], "mode": "generate",
                        "two_sided": False},
    "lop_gap_max": {"knobs": {"lop_gap_max": 2.0}, "types": ["lack_of_penetration"], "mode": "generate",
                    "two_sided": False},
}


def _clamp(name, v):
    lo, hi = REGISTRY[name][2], REGISTRY[name][3]
    v = min(max(v, lo), hi)
    return int(round(v)) if name in INT_KNOBS else round(v, 4)


def variant_knobs(base, group, sign):
    """Bộ núm đầy đủ của biến thể (group, sign ±1); kẹp trong giới hạn sổ đăng ký.
    Trả về None khi kẹp xong không núm nào đổi (điểm gốc nằm sát biên theo phía này)."""
    out = dict(base)
    for k, step in GROUPS[group]["knobs"].items():
        out[k] = _clamp(k, base[k] + sign * step)
    return out if any(out[k] != base[k] for k in GROUPS[group]["knobs"]) else None


def variants(base):
    """[(variant_id, group, sign, knobs)] theo thứ tự đo: replay trước (rẻ), generate sau."""
    out = []
    for mode in ("replay", "generate"):
        for g, spec in GROUPS.items():
            if spec["mode"] != mode:
                continue
            for sign in ((1, -1) if spec["two_sided"] else (1,)):
                kv = variant_knobs(base, g, sign)
                if kv is not None:
                    out.append((f"{g}{'+' if sign > 0 else '-'}", g, sign, kv))
    return out
