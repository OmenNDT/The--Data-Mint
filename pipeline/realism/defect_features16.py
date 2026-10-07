"""16 đặc trưng khuyết tật: họ "Hình dạng vùng nghi lỗi" (12) + họ "Biên khuyết tật" (4).

Chép nguyên văn từ Data_Science/analysis/riawelc-features: suspect_mask, gradient Sobel, _shape (feature_bank.py),
kernel_maps / kernel_mask (v2-kernel/feature_bank_kernel.py). Đừng sửa các hàm này riêng lẻ: số đo sẽ lệch bảng
tham chiếu v2-kernel/features.csv. tests/test-realism-defect-features16.py kiểm lại trên ảnh RIAWELC thật.

Khác với realism/features.py (sáu tiêu chí, ngưỡng cố định đọc từ reference/kernel-calibration.json của RIAWELC):
module này nhận ngưỡng `thr` làm tham số, để dùng được với ngưỡng hiệu chỉnh trên W0003 (realism/reference_w0003.py)
lẫn ngưỡng RIAWELC gốc, cùng một hàm.
"""
import numpy as np
from scipy import ndimage as ndi
from skimage.measure import label, regionprops
from skimage.morphology import skeletonize

# Thứ tự đúng theo feature_bank.FAMILY: họ "hinhdang" (tiền tố vung_, xuong_) rồi họ "bien" (tiền tố bien_).
DEFECT_FEATURES = [
    "vung_tile", "vung_sodom", "vung_trontb", "vung_lon", "vung_tron", "vung_lechtam", "vung_thuon",
    "vung_huong", "vung_dac", "vung_dayhop", "xuong_dai", "xuong_renhanh",
    "bien_tuongphan", "bien_doc", "bien_daodong", "bien_sau",
]

MASK_KERNELS = ("dom_16", "dai_8", "ngang_8")


def suspect_mask(img):
    """Mặt nạ vùng nghi lỗi kiểu DoG (feature_bank.suspect_mask): chỉ dùng để lấy ảnh hiệu nền `diff` và độ nhiễu
    `sd` cho họ biên; mặt nạ `m` của hàm này KHÔNG dùng, bị ghi đè bằng kernel_mask (giống extract_features_kernel.py)."""
    bg = ndi.gaussian_filter(img, 25)
    diff = ndi.gaussian_filter(bg - img, 2.0)
    sd = 1.4826 * np.median(np.abs(diff - np.median(diff))) + 1e-3
    lab = label(diff > 3 * sd)
    keep = np.zeros(lab.max() + 1, bool)
    for p in regionprops(lab, intensity_image=diff):
        keep[p.label] = p.area >= 25 and p.intensity_max > 5 * sd
    return keep[lab], diff, sd


def noise_of(img):
    """Độ nhiễu hạt của mảnh: MAD của ảnh trừ bản làm mờ Gauss σ 1,5 (dùng để chuẩn hoá bản đồ kernel)."""
    g = img - ndi.gaussian_filter(img, 1.5)
    return 1.4826 * np.median(np.abs(g - np.median(g))) + 1e-3


def _hessian(img, s):
    return (ndi.gaussian_filter(img, s, order=(0, 2)), ndi.gaussian_filter(img, s, order=(2, 0)),
            ndi.gaussian_filter(img, s, order=(1, 1)))


def kernel_maps(img, names=MASK_KERNELS):
    """Bản đồ đáp ứng / độ nhiễu cho các kernel yêu cầu, viền rộng σ đặt về 0 (cắt mép đáp ứng giả)."""
    sd, out, cache = noise_of(img), {}, {}
    for name in names:
        kind, s = name.split("_")
        s = int(s)
        ixx, iyy, ixy = cache.setdefault(s, _hessian(img, s))
        if kind in ("dom", "dai"):
            tr, det = ixx + iyy, ixx * iyy - ixy * ixy
            d = np.sqrt(np.maximum(tr * tr / 4 - det, 0))
            l1, l2 = tr / 2 + d, tr / 2 - d
            m = np.where(l2 > 0, l2, 0) if kind == "dom" else np.where(l1 > 0, l1 - np.abs(l2), 0)
        else:
            m = {"ngang": iyy, "doc": ixx, "log": ixx + iyy}[kind]
        m = s * s * m / sd
        b = min(s, 16)
        m[:b], m[-b:], m[:, :b], m[:, -b:] = 0, 0, 0, 0
        out[name] = m
    return out


def kernel_mask(img, thr, min_area=25):
    """Mặt nạ vùng nghi lỗi từ 3 kernel riêng: hợp các điểm vượt ngưỡng thr, bỏ vùng nhỏ hơn min_area.
    thr: dict {"dom_16": ..., "dai_8": ..., "ngang_8": ...} (xem reference_w0003.calibrate_thresholds)."""
    maps = kernel_maps(img, MASK_KERNELS)
    raw = np.zeros(img.shape, bool)
    for k in MASK_KERNELS:
        raw |= maps[k] > thr[k]
    lab = label(raw)
    keep = np.zeros(lab.max() + 1, bool)
    for p in regionprops(lab):
        keep[p.label] = p.area >= min_area
    return keep[lab]


# Ngưỡng loại "đường biên mép hàn" (bước 2, plan 261006): chọn từ dữ liệu, xem báo cáo subagent
# fullstack-developer-261007 — kiểm trên W0003 thật (would_lose tối thiểu, chỉ LOP/Crack/Slag mất vài ca vì
# bản chất lỗi đó CŨNG là đường dài sát biên) và trên ảnh sinh porosity/lack_of_fusion (porosity bắt đúng lỗ
# khí thay vì mép hàn, on_target +2 điểm %; LOF gần như không đổi vì lỗi đó tự nhiên dài, không trùng mẫu mép hàn).
BORDER_MARGIN = 20      # viền ảnh (điểm ảnh) coi là "chạm mép"; tính từ viền σ riêng kernel (8–16) + đệm quan sát
BORDER_ASPECT_MIN = 3.0  # tỉ lệ trục dài/ngắn tối thiểu để coi là "đường dài" (không phải đốm tròn/bầu)
BORDER_SPAN_MIN = 0.85   # khung vùng phải trải ít nhất 85% cạnh ảnh theo trục dài của nó


def _is_border_line(p, shape, margin=BORDER_MARGIN, aspect_min=BORDER_ASPECT_MIN, span_min=BORDER_SPAN_MIN):
    """True nếu vùng `p` giống một đoạn mép hàn: đường dài (aspect >= aspect_min) trải gần hết một cạnh ảnh
    (span >= span_min theo trục đó) VÀ chạm cả hai lề của trục đó. Dùng để loại trước khi chọn vùng lớn nhất
    (bước 2 plan 261006: tách biệt vùng lỗi thật khỏi đường mép hàn dài chạy ngang/dọc hết khung)."""
    minr, minc, maxr, maxc = p.bbox
    h, w = shape
    aspect = p.axis_major_length / max(p.axis_minor_length, 1)
    if aspect < aspect_min:
        return False
    width_span, height_span = (maxc - minc) / w, (maxr - minr) / h
    if width_span >= height_span:
        return width_span >= span_min and (minc <= margin or maxc >= w - margin)
    return height_span >= span_min and (minr <= margin or maxr >= h - margin)


# Ngưỡng loại "dải mép trên/dưới tile" (ruler v3, follow-up 7/10: crack/lack_of_penetration thật dài TỰ NHIÊN,
# _is_border_line (v2, đòi span>=85% VÀ chạm lề TRÁI/PHẢI) loại nhầm lỗi thật chạy ngang qua GIỮA tile — xem
# plans/261006-defect-metrics-w0003-reference/reports/fullstack-developer-261007-1228-lop-feature-deviation.md
# mục 0 + ảnh lop-real-region-overlay-261007.png: dải sáng/tối do chiếu sáng không đều nằm SÁT HÀNG 0 hoặc
# HÀNG CUỐI (cách mép 7-8px trong mẫu thật), không liên quan tới có chạm lề trái/phải hay trải bao xa theo
# chiều ngang. v3 chỉ xét VỊ TRÍ HÀNG (minr/maxr so biên trên/dưới), bỏ hẳn điều kiện span+chạm lề ngang của
# v2 — nhờ vậy giữ được lỗi dài nằm giữa tile (hàng tâm, xem báo cáo subagent fullstack-developer-261007-14xx).
EDGE_BAND_MARGIN = 20       # khớp BORDER_MARGIN: viền σ kernel (8-16) + đệm; dải nhiễu quan sát được cách mép 7-8px
EDGE_BAND_ASPECT_MIN = 3.0  # khớp BORDER_ASPECT_MIN: chỉ loại đường dài, không loại đốm compact tình cờ gần mép
                            # (vd W0003_0043_tile_25: đốm nhỏ aspect 1,4 cách mép dưới 14px — GIỮ LẠI, không phải dải mép)


def _is_edge_band_line(p, shape, margin=EDGE_BAND_MARGIN, aspect_min=EDGE_BAND_ASPECT_MIN):
    """True nếu vùng `p` là dải dài nằm trong `margin` điểm ảnh của hàng 0 hoặc hàng cuối (rìa TRÊN/DƯỚI tile):
    đường dài (aspect >= aspect_min) VÀ (minr <= margin HOẶC hàng cuối của vùng cách đáy ảnh <= margin). KHÔNG
    đòi trải rộng theo chiều ngang hay chạm lề trái/phải (khác _is_border_line) — xem ghi chú EDGE_BAND_* ở trên."""
    minr, _, maxr, _ = p.bbox
    h, _ = shape
    aspect = p.axis_major_length / max(p.axis_minor_length, 1)
    if aspect < aspect_min:
        return False
    return minr <= margin or (h - 1 - maxr) <= margin


def _shape(m, diff, mag, noise, exclude_border=False, exclude_edge_band=False):
    """Chép nguyên văn feature_bank._shape: họ hình dạng (12) và họ biên (4) trên vùng nghi lỗi lớn nhất của `m`
    (số đốm vung_sodom tính trên toàn mặt nạ, hoặc trên phần còn lại sau khi loại đường mép hàn/dải mép rìa).
    Không sửa công thức khi cả hai cờ đều False — phải khớp v2-kernel/features.csv. Hai cờ loại trừ lẫn nhau
    về Ý NGHĨA thước (ruler v2 dùng exclude_border, ruler v3 dùng exclude_edge_band) nhưng độc lập về code,
    có thể bật cả hai nếu sau này cần (áp dụng hợp của hai điều kiện loại bỏ)."""
    lab = label(m)
    props = sorted(regionprops(lab), key=lambda p: p.area, reverse=True)
    if exclude_border:
        props = [p for p in props if not _is_border_line(p, m.shape)]
    if exclude_edge_band:
        props = [p for p in props if not _is_edge_band_line(p, m.shape)]
    circ = [4 * np.pi * p.area / max(p.perimeter, 1) ** 2 for p in props]
    sh = dict(vung_tile=m.mean(), vung_sodom=len(props), vung_trontb=np.mean(circ) if circ else 0.0)
    bd = dict(bien_tuongphan=0.0, bien_doc=0.0, bien_daodong=0.0, bien_sau=0.0)
    if props:
        p = props[0]
        sk = skeletonize(lab == p.label)
        nb = ndi.convolve(sk.astype(int), np.ones((3, 3)), mode="constant") * sk
        sh.update(vung_lon=p.area / m.size, vung_tron=circ[0], vung_lechtam=p.eccentricity,
                  vung_thuon=p.axis_major_length / max(p.axis_minor_length, 1),
                  vung_huong=abs(np.degrees(p.orientation)), vung_dac=p.solidity, vung_dayhop=p.extent,
                  xuong_dai=sk.sum() / 227.0, xuong_renhanh=int((nb >= 4).sum()))
        obj = lab == p.label
        ring = ndi.binary_dilation(obj, iterations=4) & ~obj
        edge = obj & ~ndi.binary_erosion(obj)
        ge = mag[edge] if edge.any() else np.array([0.0])
        bd = dict(bien_tuongphan=(diff[obj].mean() - diff[ring].mean()) / max(noise, 1e-3),
                  bien_doc=ge.mean() / max(noise, 1e-3), bien_daodong=ge.std() / max(ge.mean(), 1e-6),
                  bien_sau=diff[obj].max() / max(noise, 1e-3))
    else:
        sh.update(vung_lon=0.0, vung_tron=0.0, vung_lechtam=0.0, vung_thuon=1.0, vung_huong=0.0,
                  vung_dac=0.0, vung_dayhop=0.0, xuong_dai=0.0, xuong_renhanh=0)
        obj = None
    return {**sh, **bd}, obj


def defect_features(img, thr, exclude_border=False, exclude_edge_band=False, return_region=False):
    """img: mảng float32 thang 0..255. thr: ngưỡng 3 kernel (dict). exclude_border: loại đường mép hàn kiểu v2
    (xem _is_border_line). exclude_edge_band: loại dải rìa trên/dưới kiểu v3 (xem _is_edge_band_line). Cả hai
    mặc định False giữ đúng hành vi ruler v1 hiện hành. Trả về dict 16 đặc trưng + has_region (1.0 nếu
    vung_sodom > 0, tức kernel bắt được ít nhất một vùng nghi lỗi sau khi lọc). return_region=True: trả thêm
    mặt nạ bool của vùng được chọn (None nếu không có vùng), dùng cho độ đo "đúng đối tượng" (bước 1 plan
    261006) so khớp với mặt nạ lỗi thật trên ảnh sinh."""
    img = np.asarray(img, dtype=np.float32)
    _, diff, sd = suspect_mask(img)
    m = kernel_mask(img, thr)
    s = ndi.gaussian_filter(img, 1.0)
    gx, gy = ndi.sobel(s, 1), ndi.sobel(s, 0)
    mag = np.hypot(gx, gy)
    raw, region = _shape(m, diff, mag, sd, exclude_border=exclude_border, exclude_edge_band=exclude_edge_band)
    f = {k: float(v) for k, v in raw.items()}
    f["has_region"] = 1.0 if f["vung_sodom"] > 0 else 0.0
    return (f, region) if return_region else f
