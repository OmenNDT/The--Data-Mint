"""Vấn đề 1: làm tối lòng lỗi không đều và mép nhoè hơn, dùng trong apply_dark_defect_convention.

Trước đây: hệ số S cố định nhân đều khắp mặt nạ đã làm mờ σ 2, nên mép sinh sắc đều như cắt dán (độ dốc tại biên gấp
2 tới 3 lần RIAWELC, độ dao động dọc biên thấp). Nay: S × độ sâu ngẫu nhiên trong [post_depth_min, post_depth_max]
× trường thay đổi trơn (0 là đều, post_modulation), mép làm mờ σ post_edge_blur_sigma. Núm ở mặc định cho đúng S cũ, σ 2.

Khi núm khác mặc định và có nền gốc, độ tối tính THEO NỀN: ảnh = nền × (1 − độ sâu) + hạt chi tiết SD vẽ trong lỗi.
Lý do (thấy ở vòng thử đầu): LoRA hay vẽ lỗi SÁNG; cách cũ nhân thẳng lên ảnh SD với S khoảng 0,92 nên ép được về tối,
nhưng hạ độ sâu theo cách nhân thì lỗi sáng lộ ra. Tính theo nền thì lỗi luôn tối hơn nền, đúng quy ước phim X-quang.
"""
import zlib

import cv2
import numpy as np
from scipy import ndimage as ndi


def smooth_field(shape, rng, sigma):
    """Trường nhiễu trơn xếp hạng về [0, 1]: độ tương phản không phụ thuộc σ."""
    f = ndi.gaussian_filter(rng.standard_normal(shape), sigma)
    r = np.argsort(np.argsort(f.ravel())).reshape(shape)
    return r / max(r.size - 1, 1)


def strength_map(mask_arr, base_strength, knobs, key):
    """Bản đồ hệ số làm tối từng điểm (0 ngoài lỗi, ≤ base_strength trong lỗi).
    mask_arr: mặt nạ chú thích 0..255; key: chuỗi tất định (tên ảnh) để chạy lại ra đúng ảnh cũ."""
    rng = np.random.default_rng(zlib.crc32(str(key).encode()))
    blur = float(knobs.get("post_edge_blur_sigma", 2.0))
    m = cv2.GaussianBlur(mask_arr.astype(np.float32), (0, 0), sigmaX=blur) / 255.0   # cùng hàm với mã cũ
    if m.max() > 0:
        m = m / m.max()                                        # lõi bằng 1, như mã cũ
    depth = rng.uniform(knobs.get("post_depth_min", 1.0), knobs.get("post_depth_max", 1.0))
    mod = float(knobs.get("post_modulation", 0.0))
    field = 1.0 if mod <= 0 else (1 - mod) + mod * smooth_field(m.shape, rng, knobs.get("post_modulation_sigma", 6.0))
    return m * base_strength * depth * field


DETAIL_GAIN = 0.6                                              # giữ bao nhiêu phần hạt chi tiết SD vẽ trong lòng lỗi
DEFAULTS = {"post_depth_min": 1.0, "post_depth_max": 1.0, "post_modulation": 0.0, "post_edge_blur_sigma": 2.0}


def effective_knobs(knobs, defect_type):
    """Thứ tự ưu tiên độ sâu làm tối: riêng theo dạng rỗ khí (clustered_post_depth_*,
    linear_post_depth_*) > riêng rỗ khí nói chung (pore_post_depth_*) > độ sâu chung
    (post_depth_*). Mỗi mức chỉ áp dụng khi CẢ cận dưới và cận trên đều > 0, nếu không rơi
    xuống mức dưới."""
    from .mask_shaping import PORE_TYPES
    per_type = {
        "clustered_porosity": ("clustered_post_depth_min", "clustered_post_depth_max"),
        "linear_porosity": ("linear_post_depth_min", "linear_post_depth_max"),
        # Vòng sau (7/10): xỉ và rỗ khí kéo dài hình dạng đã tốt lên nhưng còn quá nhạt.
        "slag_inclusion": ("slag_post_depth_min", "slag_post_depth_max"),
        "elongated_cavity": ("ecav_post_depth_min", "ecav_post_depth_max"),
    }
    if defect_type == "linear_porosity" and knobs.get("linear_post_modulation", -1.0) >= 0:
        # Độ thay đổi độ sâu riêng cho rỗ khí chuỗi (-1 là dùng chung): tắt nó giúp chuỗi rõ (nhánh A, 6/10).
        knobs = {**knobs, "post_modulation": knobs["linear_post_modulation"]}
    if defect_type in per_type:
        k_lo, k_hi = per_type[defect_type]
        lo, hi = knobs.get(k_lo, 0.0), knobs.get(k_hi, 0.0)
        if lo > 0 and hi > 0:
            return {**knobs, "post_depth_min": lo, "post_depth_max": hi}
    lo, hi = knobs.get("pore_post_depth_min", 0.0), knobs.get("pore_post_depth_max", 0.0)
    if defect_type in PORE_TYPES and lo > 0 and hi > 0:
        return {**knobs, "post_depth_min": lo, "post_depth_max": hi}
    return knobs


def darken(img, bg, mask_arr, base_strength, knobs, key, defect_type=None):
    """Ảnh sau bước làm tối. Núm mặc định hoặc không có nền: đúng cách cũ img × (1 − S·mặt nạ mờ)."""
    knobs = effective_knobs(knobs, defect_type)
    s = strength_map(mask_arr, base_strength, knobs, key)
    if bg is None or all(knobs.get(k, d) == d for k, d in DEFAULTS.items()):
        return img * (1.0 - s)
    m = s / max(float(s.max()), 1e-6)
    detail = img - cv2.GaussianBlur(img, (0, 0), sigmaX=1.5)
    return bg * (1.0 - s) + DETAIL_GAIN * detail * m
