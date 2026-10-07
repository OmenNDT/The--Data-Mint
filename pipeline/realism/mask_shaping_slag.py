"""Tạo hình lại mask xỉ theo núm (pha 2 thước mới): phóng to, kéo dài theo trục hàn (ngang), làm méo biên.

Xỉ thật (W0003) so blob mặc định (nhiễu Gauss ngưỡng, gần tròn): diện tích nhỏ hơn thật khoảng 8 lần, độ đặc
(solidity) cao hơn thật (0,93 so 0,68, biên trơn hơn), xương dài chuẩn hoá ngắn hơn thật nhiều (0,12 so 1,09,
tức hình thiếu nhánh/độ dẹt). Trục dài của vùng xỉ thật gần như nằm ngang (đặc trưng vung_huong ~ 86-90°,
quy ước regionprops: góc đo từ trục đứng nên giá trị gần 90° nghĩa là trục dài gần trục hàn ngang).

Ba núm độc lập, mỗi núm ở mặc định (1, 1, 0) giữ hành vi cũ (hành vi cũ = không đổi hình, trả nguyên mask):
- slag_scale: phóng diện tích vùng lên (lần). Áp hệ số giãn đẳng hướng s = sqrt(slag_scale) quanh tâm từng vùng.
- slag_elongation: tỉ lệ trục dài/ngắn, kéo theo phương ngang (trục hàn) cộng lệch góc nhỏ ngẫu nhiên (xem
  AXIS_JITTER_DEG) để không phải mọi vùng xỉ đều chính xác 0°, giống phân bố 86-90° đo trên W0003.
- slag_irregularity_px: biên độ dời điểm mượt (trường Gauss lọc mượt) làm biên gồ ghề, giảm độ đặc và tăng
  xương dài chuẩn hoá (thêm nhánh/khúc khuỷu), giống biên không trơn của xỉ thật.

Xử lý từng vùng liên thông riêng (ndi.label) để nhiều hạt xỉ trong một mask không bị trộn lẫn khi giãn.
"""
import numpy as np
from scipy import ndimage as ndi

from .mask_shaping import _affine, _stretch, _warp

# Lệch góc nhỏ quanh phương ngang (trục hàn) khi kéo dài; không phải núm riêng vì biên độ cố định nhỏ, chỉ để
# tránh mọi vùng xỉ giãn đúng 0° tuyệt đối (W0003 đo được 86-90°, không phải đúng 90° mọi mẫu).
AXIS_JITTER_DEG = 8.0
PAD_MARGIN = 12  # lề thêm ngoài mức giãn tính toán, tránh cắt mất biên mượt sau warp


def shape(m, rng, knobs):
    """m: mask nhị phân (bool). Trả mask mới cùng cỡ. Núm ở mặc định phải trả đúng m (hành vi cũ)."""
    scale = knobs["slag_scale"]
    ratio = knobs["slag_elongation"]
    irr = knobs["slag_irregularity_px"]
    if scale <= 1.0 and ratio <= 1.0 and irr <= 0:
        return m
    lab, n = ndi.label(m)
    if n == 0:
        return m
    s = np.sqrt(max(scale, 1.0))
    r = max(ratio, 1.0)
    out = np.zeros_like(m)
    for i, sl in enumerate(ndi.find_objects(lab), start=1):
        h = sl[0].stop - sl[0].start
        w = sl[1].stop - sl[1].start
        axis_deg = rng.normal(0.0, AXIS_JITTER_DEG)
        M = s * _stretch(r, axis_deg)
        grow = s * np.sqrt(r)                              # trị kỳ dị lớn nhất của M (trục giãn mạnh nhất)
        pad = int(np.ceil(max(h, w) * max(grow - 1.0, 0.0) / 2)) + PAD_MARGIN
        y0, x0 = max(sl[0].start - pad, 0), max(sl[1].start - pad, 0)
        y1, x1 = min(sl[0].stop + pad, m.shape[0]), min(sl[1].stop + pad, m.shape[1])
        sub = lab[y0:y1, x0:x1] == i
        if not sub.any():
            continue
        sub = _affine(sub, ndi.center_of_mass(sub), M)
        if irr > 0 and sub.any():
            dy, dx = (ndi.gaussian_filter(rng.standard_normal(sub.shape), 2.5) for _ in range(2))
            denom = max(float(np.abs(np.r_[dy.ravel(), dx.ravel()]).max()), 1e-6)
            sub = _warp(sub, dy * (irr / denom), dx * (irr / denom))
        out[y0:y1, x0:x1] |= sub
    return out
