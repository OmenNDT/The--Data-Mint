"""Tạo hình lại mask rỗ khí kéo dài (elongated_cavity) theo núm ecav_tilt_max_deg (pha 2 thước mới).

Vấn đề đo được trên thước 16 đặc trưng (so W0003 thật): bộ sinh luôn vẽ trục gần nằm ngang
(vung_huong 85,9° so thật 60,4°, AUC 0,77; vung_huong = abs(orientation) đo từ phương ĐỨNG theo
skimage regionprops, nên giá trị gần 90° là gần nằm ngang, gần 0° là gần thẳng đứng). Muốn kéo
vung_huong trung bình về ~60° cần xoay trục mỗi vùng khỏi phương ngang trung bình ~30°; núm lấy
góc xoay rút đều trong [-ecav_tilt_max_deg, ecav_tilt_max_deg] quanh tâm từng vùng nên trị tuyệt
đối trung bình = ecav_tilt_max_deg / 2 (núm 60 thì trung bình xoay 30, đúng mục tiêu).

Núm ở mặc định (0) trả nguyên mask, không đổi hành vi cũ.
"""
import numpy as np
from scipy import ndimage as ndi

from .mask_shaping import _affine, _rot

# Viền giữ trống theo đúng cách bộ sinh gốc cắt contour (mask_generator/elongated-cavity-mask-generator.py
# clip [2, H-2]/[2, W-2]): sau khi xoay, dời vùng vào lại trong viền này, không cắt mất phần lỗi.
FRAME_MARGIN = 2


def _shift_inside_frame(sub, y0, x0, H, W):
    """Dời nguyên vùng (không cắt) nếu xoay làm nó chạm viền khung ảnh gốc (H, W)."""
    rows, cols = np.nonzero(sub)
    if rows.size == 0:
        return sub
    r0, r1 = rows.min() + y0, rows.max() + y0
    c0, c1 = cols.min() + x0, cols.max() + x0
    dy = max(FRAME_MARGIN - r0, 0) or min((H - 1 - FRAME_MARGIN) - r1, 0)
    dx = max(FRAME_MARGIN - c0, 0) or min((W - 1 - FRAME_MARGIN) - c1, 0)
    if dy or dx:
        sub = ndi.shift(sub.astype(float), (dy, dx), order=0) > 0.5
    return sub


def shape(m, rng, knobs):
    """m: mask nhị phân (bool) toàn khung. knobs["ecav_tilt_max_deg"]: góc xiên tối đa (độ).
    Mỗi vùng liên thông (một lỗ rỗ khí kéo dài) xoay độc lập quanh tâm chính nó, giữ diện tích,
    góc rút ngẫu nhiên đều trong [-tilt_max, tilt_max]. Trả mask mới cùng cỡ, hoặc nguyên m nếu
    núm = 0 hoặc mask rỗng."""
    tilt_max = float(knobs.get("ecav_tilt_max_deg", 0.0))
    if tilt_max <= 0:
        return m
    H, W = m.shape
    lab, n = ndi.label(m)
    if n == 0:
        return m
    out = np.zeros_like(m)
    for i, sl in enumerate(ndi.find_objects(lab), start=1):
        size = max(sl[0].stop - sl[0].start, sl[1].stop - sl[1].start)
        pad = int(np.ceil(size * 0.75)) + 4   # đủ chỗ cho góc xoay tới 60° không bị cắt bởi biên vùng cục bộ
        y0, x0 = max(sl[0].start - pad, 0), max(sl[1].start - pad, 0)
        y1, x1 = min(sl[0].stop + pad, H), min(sl[1].stop + pad, W)
        sub = lab[y0:y1, x0:x1] == i
        angle = rng.uniform(-tilt_max, tilt_max)
        sub = _affine(sub, ndi.center_of_mass(sub), _rot(angle))
        if sub.any():
            sub = _shift_inside_frame(sub, y0, x0, H, W)
        out[y0:y1, x0:x1] |= sub
    return out
