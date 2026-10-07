"""Tạo hình lại mặt nạ lỗi cho giống RIAWELC, chạy ngay sau bộ sinh mặt nạ gốc và trước khi SD vẽ (vấn đề 2, 3, 4).

- Nứt: một tỉ lệ vết nứt xoay thành vết đứng (90° ± 20° quanh tâm), thu ngắn cho gọn trong dải mối hàn (40% chiều cao);
  làm dày ngẫu nhiên tới crack_widen_px điểm ảnh.
- Rỗ khí (đơn, cụm, chuỗi): từng lỗ kéo thuôn giữ diện tích, tỉ lệ trục trong [pore_aspect_min, pore_aspect_max], trục
  gần phương ngang ± pore_axis_jitter_deg; mép gồ ghề bằng dời điểm trơn biên độ pore_irregularity_px.
- Không thấu: nghiêng tới lop_tilt_max_deg, lượn biên độ lop_wave_amp_px, cắt tới lop_gap_max khoảng đứt 10 tới 35 điểm.
Núm ở mặc định (hành vi cũ) thì trả nguyên mặt nạ. Kết quả rỗng thì cũng trả nguyên mặt nạ gốc.
"""
import numpy as np
from scipy import ndimage as ndi

PORE_TYPES = {"porosity", "clustered_porosity", "linear_porosity"}
MAX_SPAN = 0.4


def _rot(deg):
    t = np.radians(deg)
    return np.array([[np.cos(t), -np.sin(t)], [np.sin(t), np.cos(t)]])


def _affine(a, center, M):
    """Kết quả tại p lấy từ a tại center + M⁻¹ (p − center); láng giềng gần nhất (mặt nạ nhị phân)."""
    inv = np.linalg.inv(M)
    c = np.asarray(center, float)
    return ndi.affine_transform(a.astype(float), inv, offset=c - inv @ c, order=1, mode="constant") > 0.5


def _warp(a, dy, dx):
    yy, xx = np.mgrid[:a.shape[0], :a.shape[1]].astype(np.float32)
    return ndi.map_coordinates(a.astype(float), [yy - dy, xx - dx], order=1, mode="constant") > 0.5


def _crack(m, rng, k, weld_y):
    if k["crack_transverse_share"] > 0 and rng.random() < k["crack_transverse_share"]:
        c = ndi.center_of_mass(m)
        M = _rot(90 + rng.uniform(-20, 20))
        rows = np.nonzero(_affine(m, c, M).any(1))[0]
        span = rows.max() - rows.min() + 1 if rows.size else 0
        if span > MAX_SPAN * m.shape[0]:                     # thu ngắn theo chiều dọc (chiều dài vết), giữ bề dày
            M = np.diag([MAX_SPAN * m.shape[0] / span, 1.0]) @ M
        m = _affine(m, c, M)
        if weld_y is not None and m.any():                  # vết nứt đứng cắt ngang mối hàn: dời tâm về đường tâm hàn
            rows = np.nonzero(m.any(1))[0]
            dy = weld_y + rng.normal(0, 0.03 * m.shape[0]) - ndi.center_of_mass(m)[0]
            dy = np.clip(dy, 4 - rows.min(), m.shape[0] - 5 - rows.max())   # cả vết nứt nằm trong khung
            m = ndi.shift(m.astype(float), (dy, 0), order=0) > 0.5
    w = int(rng.integers(0, int(k["crack_widen_px"]) + 1)) if k["crack_widen_px"] >= 1 else 0
    return ndi.binary_dilation(m, iterations=w) if w else m


def _stretch(ratio, axis_deg):
    t = np.radians(axis_deg)
    u = np.array([np.sin(t), np.cos(t)])                  # (hàng, cột); axis_deg đo từ phương ngang
    s = np.sqrt(ratio)
    return np.outer(u, u) * (s - 1 / s) + np.eye(2) / s


def _pores(m, rng, k, prefix="pore"):
    """prefix "pore" (rỗ khí đơn, cụm) hoặc "linear_pore" (rỗ khí chuỗi, núm riêng); độ lệch trục dùng chung."""
    lo, hi, irr = k[f"{prefix}_aspect_min"], k[f"{prefix}_aspect_max"], k[f"{prefix}_irregularity_px"]
    if hi <= 1.0 and irr <= 0:
        return m
    lab, _ = ndi.label(m)
    out = np.zeros_like(m)
    for i, sl in enumerate(ndi.find_objects(lab), start=1):
        pad = 16
        y0, x0 = max(sl[0].start - pad, 0), max(sl[1].start - pad, 0)
        y1, x1 = min(sl[0].stop + pad, m.shape[0]), min(sl[1].stop + pad, m.shape[1])
        sub = lab[y0:y1, x0:x1] == i
        if hi > 1.0:
            sub = _affine(sub, ndi.center_of_mass(sub), _stretch(rng.uniform(lo, hi), rng.normal(0, k["pore_axis_jitter_deg"])))
        if irr > 0 and sub.any():
            dy, dx = (ndi.gaussian_filter(rng.standard_normal(sub.shape), 2.5) for _ in range(2))
            s = irr / max(float(np.abs(np.r_[dy.ravel(), dx.ravel()]).max()), 1e-6)
            sub = _warp(sub, dy * s, dx * s)
        out[y0:y1, x0:x1] |= sub
    return out


def _lop(m, rng, k):
    H, W = m.shape
    if k["lop_tilt_max_deg"] > 0:
        t = rng.uniform(min(1.0, k["lop_tilt_max_deg"]), k["lop_tilt_max_deg"]) * rng.choice([-1, 1])
        m = _affine(m, ndi.center_of_mass(m), _rot(t))
    if k["lop_wave_amp_px"] > 0:
        x = np.arange(W, dtype=float)
        amp = rng.uniform(0.6, 1.0) * k["lop_wave_amp_px"]
        dy = amp * np.sin(2 * np.pi * x / rng.uniform(60, 160) + rng.uniform(0, 2 * np.pi))
        m = _warp(m, np.broadcast_to(dy, (H, W)), 0)
    cols = np.nonzero(m.any(0))[0]
    if k["lop_gap_max"] >= 1 and cols.size > 60:
        for _ in range(int(rng.integers(1, int(k["lop_gap_max"]) + 1))):
            w = rng.uniform(10, 35)
            g0 = rng.uniform(cols.min() + 15, max(cols.max() - 15 - w, cols.min() + 16))
            m[:, int(g0):int(g0 + w)] = False
    return m


EXTRA_SHAPERS = {"slag_inclusion": ".mask_shaping_slag", "elongated_cavity": ".mask_shaping_ecav",
                 "lack_of_fusion": ".mask_shaping_lof"}


def shape_mask(defect_type, mask_u8, seed, knobs, weld_center_y=None):
    """mask_u8: mặt nạ nhị phân 0/255 của bộ sinh gốc. knobs: {tên: giá trị} (xem knobs.REGISTRY).
    weld_center_y: hàng tâm mối hàn bộ sinh đã dò trên nền; vết nứt đứng được dời về đó."""
    m = mask_u8 > 127
    if not m.any():
        return mask_u8
    rng = np.random.default_rng([int(seed) & 0xFFFFFFFF, 7919])
    if defect_type == "crack":
        out = _crack(m, rng, knobs, weld_center_y)
    elif defect_type in PORE_TYPES:
        out = _pores(m, rng, knobs, "linear_pore" if defect_type == "linear_porosity" else "pore")
    elif defect_type == "lack_of_penetration":
        out = _lop(m, rng, knobs)
    elif defect_type in EXTRA_SHAPERS:
        # Mỗi loại một mô-đun riêng (pha 2 thước mới, nhiều nhánh làm song song không đụng tệp nhau).
        import importlib
        out = importlib.import_module(EXTRA_SHAPERS[defect_type], __package__).shape(m, rng, knobs)
    else:
        return mask_u8
    return (out * 255).astype(np.uint8) if out.any() else mask_u8
