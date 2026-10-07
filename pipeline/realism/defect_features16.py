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


def _shape(m, diff, mag, noise):
    """Chép nguyên văn feature_bank._shape: họ hình dạng (12) và họ biên (4) trên vùng nghi lỗi lớn nhất của `m`
    (số đốm vung_sodom tính trên toàn mặt nạ). Không sửa công thức — phải khớp v2-kernel/features.csv."""
    lab = label(m)
    props = sorted(regionprops(lab), key=lambda p: p.area, reverse=True)
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
    return {**sh, **bd}


def defect_features(img, thr):
    """img: mảng float32 thang 0..255. thr: ngưỡng 3 kernel (dict). Trả về dict 16 đặc trưng + has_region
    (1.0 nếu vung_sodom > 0, tức kernel bắt được ít nhất một vùng nghi lỗi)."""
    img = np.asarray(img, dtype=np.float32)
    _, diff, sd = suspect_mask(img)
    m = kernel_mask(img, thr)
    s = ndi.gaussian_filter(img, 1.0)
    gx, gy = ndi.sobel(s, 1), ndi.sobel(s, 0)
    mag = np.hypot(gx, gy)
    f = {k: float(v) for k, v in _shape(m, diff, mag, sd).items()}
    f["has_region"] = 1.0 if f["vung_sodom"] > 0 else 0.0
    return f
