"""Móc vòng độ thật vào bộ sinh: giữ phần sửa trong tệp sản xuất ở mức một dòng gọi mỗi chỗ.

- shape_generated_mask: gọi trong mask_prefetch_worker_pool._generate_mask_worker ngay sau generator.generate().
  Chặn mặt nạ trống (sinh lại với hạt giống khác, tối đa 5 lần: trước đây 28 ảnh rỗ khí và 3 ảnh lẫn xỉ ra mặt nạ trống
  nên thành mảnh nền sạch mang nhãn lỗi; chạy cả khi núm ở mặc định), rồi tạo hình lại theo núm của đúng loại đó
  (realism/mask_shaping.py). Loại nào núm của nó còn mặc định thì giữ nguyên mặt nạ gốc lẫn mặt nạ làm mềm mép.
- darken_image: gọi trong apply_dark_defect_convention thay cho "ảnh × (1 − mặt nạ làm mờ σ 2 × S)".
Mọi lỗi ở đây bị nuốt và trả về giá trị cũ: vòng độ thật không bao giờ được làm hỏng đợt sản xuất.
"""
import logging

import numpy as np

from .knobs import DEFAULTS, values
from .mask_shaping import PORE_TYPES, shape_mask
from .post_darkening import darken, strength_map

logger = logging.getLogger(__name__)
MAX_EMPTY_RETRIES = 5
TYPE_KNOBS = {"crack": ("crack_transverse_share", "crack_widen_px"),
              "lack_of_penetration": ("lop_tilt_max_deg", "lop_wave_amp_px", "lop_gap_max", "lop_length_scale"),
              "linear_porosity": ("linear_pore_aspect_min", "linear_pore_aspect_max", "pore_axis_jitter_deg",
                                  "linear_pore_irregularity_px"),
              "slag_inclusion": ("slag_scale", "slag_elongation", "slag_irregularity_px"),
              "elongated_cavity": ("ecav_tilt_max_deg",),
              "lack_of_fusion": ("lof_length_scale", "lof_width_scale", "lof_gap_max", "lof_band_width_scale"),
              **{t: ("pore_aspect_min", "pore_aspect_max", "pore_axis_jitter_deg", "pore_irregularity_px")
                 for t in PORE_TYPES - {"linear_porosity"}}}
# Bán kính làm mềm mép mỗi bộ sinh gốc tự dùng (mask_generator/*-mask-generator.py); làm mềm lại đúng bán kính đó.
FEATHER_RADIUS = {"crack": 1, "porosity": 2, "clustered_porosity": 2, "linear_porosity": 2, "lack_of_penetration": 40,
                  "slag_inclusion": 5, "elongated_cavity": 12, "lack_of_fusion": 2}   # 3 loại sau: nhánh kiểm lại


def _knobs():
    try:
        return values()
    except Exception:
        return dict(DEFAULTS)


# Khoảng bề rộng dải GỐC của bộ sinh không ngấu (mask_generator/lack-of-fusion-mask-generator.py,
# LackOfFusionMaskGenerator.band_width_range mặc định). Núm lof_band_width_scale co khoảng này TẠI SINH (trước
# fillPoly + feather), khác _thin hậu kỳ của mask_shaping_lof.py (affine siết quanh tâm toàn khối, đã thử và làm
# hỏng khả năng phát hiện vì méo dải nghiêng). 1.0: trả {} (giữ đúng band_width_range gốc, hành vi cũ nguyên văn).
LOF_BASE_BAND_WIDTH_RANGE = (5, 12)


def lof_generation_kwargs():
    """kwargs bổ sung truyền vào LackOfFusionMaskGenerator(...) theo núm lof_band_width_scale.
    {} nếu núm ở mặc định hoặc đọc núm lỗi (không bao giờ ném lỗi, vòng độ thật không làm hỏng sản xuất)."""
    try:
        scale = _knobs()["lof_band_width_scale"]
        if scale == DEFAULTS["lof_band_width_scale"]:
            return {}
        lo, hi = LOF_BASE_BAND_WIDTH_RANGE
        new_lo = max(1, int(round(lo * scale)))
        new_hi = max(new_lo + 1, int(round(hi * scale)))
        return {"band_width_range": (new_lo, new_hi)}
    except Exception:
        logger.exception("lof_generation_kwargs lỗi, giữ band_width_range gốc")
        return {}


def shape_generated_mask(defect_type, seed, binary_mask, feathered_mask, regenerate, weld_center_y=None):
    """regenerate(seed) → (binary, feathered) của cùng bộ sinh gốc. Trả về (binary, feathered) đã chặn rỗng, tạo hình."""
    try:
        tries = 0
        while not (binary_mask > 127).any() and tries < MAX_EMPTY_RETRIES:
            tries += 1
            binary_mask, feathered_mask = regenerate(int(seed) + 7919 * tries)
        if tries:
            logger.info("mặt nạ %s trống, sinh lại %d lần (seed %s)", defect_type, tries, seed)
        k = _knobs()
        own = TYPE_KNOBS.get(defect_type, ())
        if not own or all(k[n] == DEFAULTS[n] for n in own):
            return binary_mask, feathered_mask                # núm của loại này ở mặc định: đúng hành vi cũ
        shaped = shape_mask(defect_type, binary_mask, seed, k, weld_center_y)
        if shaped is binary_mask:
            return binary_mask, feathered_mask
        from mask_generator import feather_mask
        return shaped, feather_mask(shaped, blur_radius=FEATHER_RADIUS.get(defect_type, 5))
    except Exception:
        logger.exception("realism mask shaping lỗi, giữ mặt nạ gốc")
        return binary_mask, feathered_mask


def darken_image(img, bg, mask_arr, base_strength, key, defect_type=None):
    """Ảnh sau bước làm tối lòng lỗi (post_darkening.darken); núm mặc định cho đúng cách cũ.
    bg: nền gốc, None nếu đợt sinh không có đường dẫn nền (khi đó cũng dùng cách cũ)."""
    try:
        return darken(img, bg, mask_arr, base_strength, _knobs(), key, defect_type)
    except Exception:
        logger.exception("realism darkening lỗi, dùng cách làm tối cũ")
        return old_darken(img, mask_arr, base_strength)


def old_darken(img, mask_arr, base_strength):
    """Cách làm tối cũ, nguyên văn: dùng khi module độ thật lỗi hoặc không nạp được."""
    import cv2
    m = cv2.GaussianBlur(mask_arr.astype(np.float32), (0, 0), sigmaX=2.0) / 255.0
    return img * (1.0 - (m / m.max() if m.max() > 0 else m) * base_strength)


def darken_strength(mask_arr, base_strength, key):
    """Bản đồ hệ số làm tối theo núm hiện tại (dùng trong phép thử)."""
    return strength_map(mask_arr, base_strength, _knobs(), key)
