"""Sáu tiêu chí hình dạng và biên của vùng lỗi, tính ĐÚNG như bảng tham chiếu RIAWELC (reference/riawelc-six-criteria.csv).

Chép nguyên văn từ Data_Science/analysis/riawelc-features: suspect_mask, gradient Sobel và _shape (feature_bank.py),
kernel_maps / kernel_mask cho ba kernel tách vùng (v2-kernel/feature_bank_kernel.py). Đừng sửa các hàm này riêng lẻ: số
đo sẽ lệch bảng tham chiếu. tests/test-realism-loop.py (FeaturesMatchReference) kiểm lại trên ảnh RIAWELC thật.
Sáu tiêu chí: vung_dac (độ đặc), vung_huong (|góc| độ, 90 là nằm ngang), bien_daodong (độ dao động dọc biên),
vung_lechtam (độ lệch tâm), vung_dayhop (độ đầy hộp bao), bien_doc (độ dốc tại biên, lần độ nhiễu).
"""
import json
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi
from skimage.measure import label, regionprops

REF_DIR = Path(__file__).resolve().parent / "reference"
THR = json.loads((REF_DIR / "kernel-calibration.json").read_text(encoding="utf-8"))["thr"]
MASK_KERNELS = ("dom_16", "dai_8", "ngang_8")
CRITERIA = {"vung_dac": "độ đặc", "vung_huong": "góc nghiêng vùng", "bien_daodong": "độ dao động dọc biên",
            "vung_lechtam": "độ lệch tâm", "vung_dayhop": "độ đầy hộp bao", "bien_doc": "độ dốc tại biên"}


def suspect_mask(img):
    bg = ndi.gaussian_filter(img, 25)
    diff = ndi.gaussian_filter(bg - img, 2.0)
    sd = 1.4826 * np.median(np.abs(diff - np.median(diff))) + 1e-3
    lab = label(diff > 3 * sd)
    keep = np.zeros(lab.max() + 1, bool)
    for p in regionprops(lab, intensity_image=diff):
        keep[p.label] = p.area >= 25 and p.intensity_max > 5 * sd
    return keep[lab], diff, sd


def noise_of(img):
    g = img - ndi.gaussian_filter(img, 1.5)
    return 1.4826 * np.median(np.abs(g - np.median(g))) + 1e-3


def _hessian(img, s):
    return (ndi.gaussian_filter(img, s, order=(0, 2)), ndi.gaussian_filter(img, s, order=(2, 0)),
            ndi.gaussian_filter(img, s, order=(1, 1)))


def kernel_maps(img, names=MASK_KERNELS):
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


def kernel_mask(img, thr=THR, min_area=25):
    maps = kernel_maps(img, MASK_KERNELS)
    raw = np.zeros(img.shape, bool)
    for k in MASK_KERNELS:
        raw |= maps[k] > thr[k]
    lab = label(raw)
    keep = np.zeros(lab.max() + 1, bool)
    for p in regionprops(lab):
        keep[p.label] = p.area >= min_area
    return keep[lab]


def six_criteria(img, mask=None):
    """img: float32 0..255, mảnh 227 × 227. mask None = mặt nạ kernel v2 (như RIAWELC); truyền mặt nạ thật để đo đúng
    vùng máy đã vẽ. Trả về sáu tiêu chí trên vùng lớn nhất, has_region, và nhãn vùng lớn nhất (để kiểm chạm lỗi)."""
    s = ndi.gaussian_filter(img, 1.0)
    mag = np.hypot(ndi.sobel(s, 1), ndi.sobel(s, 0))
    _, diff, sd = suspect_mask(img)
    m = kernel_mask(img) if mask is None else mask
    lab = label(m)
    props = sorted(regionprops(lab), key=lambda p: p.area, reverse=True)
    if not props:
        return {k: 0.0 for k in CRITERIA} | {"has_region": 0.0, "largest": None}
    p = props[0]
    obj = lab == p.label
    edge = obj & ~ndi.binary_erosion(obj)
    ge = mag[edge] if edge.any() else np.array([0.0])
    return {"vung_dac": float(p.solidity), "vung_huong": float(abs(np.degrees(p.orientation))),
            "bien_daodong": float(ge.std() / max(ge.mean(), 1e-6)), "vung_lechtam": float(p.eccentricity),
            "vung_dayhop": float(p.extent), "bien_doc": float(ge.mean() / max(sd, 1e-3)), "has_region": 1.0,
            "largest": obj}
