"""Tạo hình lại mask không ngấu theo núm (pha 2 thước mới, nhánh D).

Dải không ngấu bộ sinh vẽ ra là một dải liền (fillPoly), đo bằng thước 16 đặc trưng thì to hơn thật khoảng 2,6 lần
(vung_tile 0,016 so W0003 thật 0,006), biên quá sắc (bien_tuongphan 2,5 so 1,47), và liền một khối trong khi thật
thường đứt thành 2 đoạn trở lên (vung_sodom). Ba bước theo thứ tự, núm ở mặc định (1, 1, 0) trả nguyên m:

1. Rút ngắn chiều dài dải: giữ một đoạn liên tục ngẫu nhiên theo tỉ lệ lof_length_scale (dải nằm ngang theo cột ảnh).
2. Thu mỏng bề dày: ép mask theo chiều đứng quanh tâm khối theo tỉ lệ lof_width_scale (giữ chiều dài, giảm bề dày
   trung bình, qua đó cũng hạ diện tích và độ sắc biên vì mép mỏng lại dễ mờ hơn khi làm mềm mép sau).
3. Cắt khoảng đứt: xoá các cửa sổ 10 tới 35 điểm ảnh theo chiều ngang, tối đa lof_gap_max lần (cùng cách _lop).
"""
import numpy as np
from scipy import ndimage as ndi

from .mask_shaping import _affine

GAP_WIDTH_RANGE = (10, 35)
MIN_COLS_FOR_GAP = 60


def _shorten(m, rng, scale):
    """Giữ một đoạn liên tục ngẫu nhiên theo chiều cột (chiều dài dải), tỉ lệ scale so với toàn bộ nhịp."""
    cols = np.nonzero(m.any(0))[0]
    if cols.size < 2:
        return m
    x0, x1 = int(cols.min()), int(cols.max())
    span = x1 - x0 + 1
    keep = max(int(round(span * scale)), 1)
    if keep >= span:
        return m
    start = x0 + int(rng.integers(0, span - keep + 1))
    out = np.zeros_like(m)
    out[:, start:start + keep] = m[:, start:start + keep]
    return out if out.any() else m


def _thin(m, scale):
    """Ép theo chiều đứng quanh tâm khối (giữ chiều ngang), tỉ lệ scale < 1 làm mỏng bề dày dải."""
    if scale >= 1.0 or not m.any():
        return m
    out = _affine(m, ndi.center_of_mass(m), np.diag([scale, 1.0]))
    return out if out.any() else m


def _gap(m, rng, gap_max):
    """Cắt tối đa gap_max khoảng đứt 10 tới 35 điểm ảnh theo chiều ngang (giống _lop.mask_shaping)."""
    cols = np.nonzero(m.any(0))[0]
    if gap_max < 1 or cols.size < MIN_COLS_FOR_GAP:
        return m
    out = m.copy()
    x0, x1 = int(cols.min()), int(cols.max())
    for _ in range(int(rng.integers(1, int(gap_max) + 1))):
        w = rng.uniform(*GAP_WIDTH_RANGE)
        g0 = rng.uniform(x0 + 15, max(x1 - 15 - w, x0 + 16))
        out[:, int(g0):int(g0 + w)] = False
    return out if out.any() else m


def shape(m, rng, knobs):
    """m: mask nhị phân (bool). Trả mask mới cùng cỡ. Núm ở mặc định phải trả đúng m (hành vi cũ)."""
    if not m.any():
        return m
    out = _shorten(m, rng, knobs["lof_length_scale"])
    out = _thin(out, knobs["lof_width_scale"])
    out = _gap(out, rng, knobs["lof_gap_max"])
    return out if out.any() else m
