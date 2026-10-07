"""Tham chiếu W0003 thật cho 16 đặc trưng khuyết tật: hiệu chỉnh ngưỡng kernel trên nền sạch W0003 rồi tính
đặc trưng trên từng ô khuyết tật thật (×1, không phóng).

    python -m realism.reference_w0003

Ghi hai tệp vào realism/reference/:
  w0003-kernel-calibration.json : ngưỡng 3 kernel tách vùng (dom_16, dai_8, ngang_8), hiệu chỉnh trên ô nền sạch
                                   W0003 theo ĐÚNG luật v2-kernel (xem feature_bank_kernel.calibrate): tìm ngưỡng
                                   chung sao cho ND_ALARM = 15,5% ô nền sạch có vùng (báo nhầm, như RIAWELC).
  w0003-defect-features.csv     : 16 đặc trưng (defect_features16.defect_features) cho mọi ô khuyết tật thật trong
                                   dataset/4.Welds_W0003_Clear_Defects_278/<lớp>/, cỡ gốc 278×278, không cắt không phóng.

Vì sao nền sạch cắt ô 278×278 (không dùng 512×512 gốc): ngưỡng kernel phải hiệu chỉnh trên cùng cỡ ô sẽ đo đặc
trưng (viền cắt mép của kernel_maps phụ thuộc σ chứ không phụ thuộc cỡ ảnh, nhưng phân vị diện tích min_area=25
so với tổng ô thì có phụ thuộc cỡ) — khớp đúng cách v2-kernel hiệu chỉnh trên mảnh RIAWELC 227×227 rồi đo trên
chính cỡ đó.
"""
import argparse
import json
import os
import zlib
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image
from scipy import ndimage as ndi
from skimage.morphology import area_opening

from .defect_features16 import DEFECT_FEATURES, MASK_KERNELS, defect_features, kernel_maps

WORKERS = min(32, os.cpu_count() or 4)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
W0003_DEFECT_DIR = PROJECT_ROOT / "dataset/4.Welds_W0003_Clear_Defects_278"
W0003_CLEAN_DIR = PROJECT_ROOT / "dataset/processed/patches_512_Confimed/clean"
REF_DIR = Path(__file__).resolve().parent / "reference"
CALIBRATION_PATH = REF_DIR / "w0003-kernel-calibration.json"
FEATURES_CSV_PATH = REF_DIR / "w0003-defect-features.csv"

ND_ALARM = 0.155       # tỉ lệ báo nhầm mục tiêu trên ô nền sạch, giống feature_bank_kernel.ND_ALARM (RIAWELC)
TILE_SIZE = 278         # cỡ ô khuyết tật W0003 gốc
CROPS_PER_PATCH = 2     # số ô 278×278 cắt ngẫu nhiên từ mỗi mảnh nền sạch 512×512
CROP_SEED = 42

# Ánh xạ loại khuyết tật bộ sinh (defect_type dùng trong mask_generator / batch-config.yaml) → thư mục lớp W0003.
# None nghĩa là chưa có mẫu thật W0003 cho loại này (lack_of_side_wall_fusion, undercut): không dùng được làm
# tham chiếu W0003, phải dựa vào RIAWELC phụ (xem evaluate.py PAIRS) hoặc đánh giá định tính.
W0003_CLASS = {
    "crack": "Crack",
    "porosity": "Gas_Pore",
    "lack_of_fusion": "Lack_of_Fusion",
    "lack_of_penetration": "Lack_Of_Penetration",
    "slag_inclusion": "Slag_inclusions",
    "linear_porosity": "Linear_Porosity",
    "elongated_cavity": "Elongated_Cavity",
    "clustered_porosity": "Clustered_localized_porosity",
    "metallic_inclusion": "Metallic_Inclusion",
    "linear_slag_inclusion": "Linear_slag_inclusion",   # 0 mẫu trong W0003 hiện có, cột vẫn khai để tường minh
    "lack_of_side_wall_fusion": None,
    "undercut": None,
}


def _clean_crops(clean_dir=W0003_CLEAN_DIR, size=TILE_SIZE, crops_per_patch=CROPS_PER_PATCH, seed=CROP_SEED):
    """Cắt ngẫu nhiên (seed cố định, tái lập được) nhiều ô cỡ `size` từ mỗi mảnh nền sạch 512×512 thật của W0003.
    Vị trí đồng đều trong phạm vi hợp lệ (không tràn mép). Trả về (danh sách mảng ảnh, số mảnh nguồn)."""
    rng = np.random.default_rng(seed)
    paths = sorted(Path(clean_dir).glob("*.png"))
    crops = []
    for p in paths:
        img = np.asarray(Image.open(p).convert("L"), dtype=np.float32)
        h, w = img.shape
        for _ in range(crops_per_patch):
            y0 = int(rng.integers(0, h - size + 1))
            x0 = int(rng.integers(0, w - size + 1))
            crops.append(img[y0:y0 + size, x0:x0 + size])
    return crops, len(paths)


def region_scores(img):
    """Điểm vùng của 3 kernel tách vùng trên một ảnh: mức cao nhất mà {bản đồ > t} còn một cụm liền (8 hướng)
    từ 25 điểm (area_opening). ĐÚNG luật feature_bank_kernel.region_scores, để ngưỡng hiệu chỉnh khớp mặt nạ
    dùng khi đo đặc trưng (defect_features16.kernel_mask dùng cùng luật "điểm ảnh vượt ngưỡng, gộp vùng, lọc
    diện tích" chứ không phải area_opening trực tiếp, nhưng cùng ý nghĩa: ngưỡng = mức mà vùng liền ≥25 điểm bắt đầu xuất hiện)."""
    maps = kernel_maps(img, MASK_KERNELS)
    return {n: float(area_opening(m, 25, connectivity=2).max()) for n, m in maps.items()}


def calibrate_thresholds(nd_scores):
    """nd_scores: {kernel: mảng điểm vùng trên ô nền sạch}. Tìm phân vị chung q sao cho đúng ND_ALARM tỉ lệ ô
    nền sạch vượt ngưỡng của ít nhất một kernel; trả (thr theo từng kernel, q). Nguyên văn luật
    feature_bank_kernel.calibrate (v2-kernel), áp cho W0003 thay RIAWELC."""
    ranks = np.stack([np.argsort(np.argsort(nd_scores[k])) / (len(nd_scores[k]) - 1) for k in MASK_KERNELS], 1)
    q = float(np.quantile(ranks.max(1), 1 - ND_ALARM))
    return {k: float(np.quantile(nd_scores[k], q)) for k in MASK_KERNELS}, q


def build_calibration(clean_dir=W0003_CLEAN_DIR, workers=WORKERS):
    """Chạy hiệu chỉnh đầy đủ trên nền sạch W0003 thật và trả về dict sẵn để ghi JSON."""
    crops, n_patches = _clean_crops(clean_dir)
    with Pool(workers) as pool:
        rows = pool.map(region_scores, crops, chunksize=8)
    nd_scores = {k: np.array([r[k] for r in rows]) for k in MASK_KERNELS}
    thr, q = calibrate_thresholds(nd_scores)
    # Tỉ lệ ô nền sạch thực sự có vùng với ngưỡng vừa hiệu chỉnh (kiểm lại đạt đúng ND_ALARM, sai số do rời rạc).
    achieved = float(np.mean([any(nd_scores[k][i] > thr[k] for k in MASK_KERNELS) for i in range(len(crops))]))
    return {
        "thr": thr, "q": q, "nd_alarm_target": ND_ALARM, "achieved_nd_rate": round(achieved, 4),
        "method": "feature_bank_kernel.calibrate trên ô 278x278 cắt ngẫu nhiên từ nền sạch W0003 512x512",
        "n_clean_patches": n_patches, "n_crops": len(crops), "crops_per_patch": CROPS_PER_PATCH,
        "crop_size": TILE_SIZE, "seed": CROP_SEED, "margin": "viền rộng σ, tối đa 16",
    }


def _feature_row(args):
    """Worker cho Pool: (file_path, cls, defect_type, thr) -> hàng dict. Top-level để pickle được."""
    f, cls, defect_type, thr = args
    img = np.asarray(Image.open(f).convert("L"), dtype=np.float32)
    feats = defect_features(img, thr)
    return {"file": f"{cls}/{f.name}", "cls": cls, "defect_type": defect_type, **feats}


def build_features_csv(thr, workers=WORKERS):
    """Tính 16 đặc trưng cho mọi ô khuyết tật thật W0003 (×1, nguyên ô, không cắt không phóng).
    Trả DataFrame cột: file, cls (thư mục W0003), defect_type (tên bộ sinh), has_region, 16 đặc trưng."""
    cls_to_defect_type = {v: k for k, v in W0003_CLASS.items() if v is not None}
    jobs = []
    for cls_dir in sorted(p for p in W0003_DEFECT_DIR.iterdir() if p.is_dir()):
        cls = cls_dir.name
        defect_type = cls_to_defect_type.get(cls)
        for f in sorted(cls_dir.glob("*.png")):
            jobs.append((f, cls, defect_type, thr))
    with Pool(workers) as pool:
        rows = pool.map(_feature_row, jobs, chunksize=4)
    cols = ["file", "cls", "defect_type", "has_region"] + DEFECT_FEATURES
    return pd.DataFrame(rows, columns=cols)


def load_reference(defect_type):
    """Trả DataFrame các ô W0003 thật của loại khuyết tật bộ sinh `defect_type` (đọc w0003-defect-features.csv
    đã tính sẵn). Báo lỗi rõ ràng nếu chưa chạy hiệu chỉnh, hoặc loại khuyết tật chưa có mẫu W0003 tham chiếu."""
    if defect_type not in W0003_CLASS:
        raise ValueError(f"defect_type không rõ: {defect_type!r} (xem W0003_CLASS)")
    if W0003_CLASS[defect_type] is None:
        raise ValueError(f"{defect_type!r} chưa có mẫu W0003 thật tham chiếu (W0003_CLASS[{defect_type!r}] = None)")
    if not FEATURES_CSV_PATH.exists():
        raise FileNotFoundError(f"chưa có {FEATURES_CSV_PATH}, chạy `python -m realism.reference_w0003` trước")
    df = pd.read_csv(FEATURES_CSV_PATH)
    return df[df.defect_type == defect_type].reset_index(drop=True)


def crop_synthetic(img, mask, size=TILE_SIZE):
    """Cắt ảnh sinh (512×512) quanh trọng tâm mặt nạ lỗi, cỡ `size`, giữ ×1 (không phóng), kẹp trong biên ảnh.
    Dùng để so ảnh sinh với ô W0003 thật cùng cỡ; LƯU Ý (xem báo cáo): ô W0003 thật KHÔNG căn giữa khuyết tật
    (ô cắt lưới cố định từ ảnh gốc lớn), còn hàm này luôn căn giữa quanh lỗi, nên vị trí lỗi trong khung lệch
    nhau có hệ thống giữa hai tập — ảnh hưởng đặc trưng nhạy vị trí biên (vd bien_*) nhiều hơn đặc trưng hình dạng."""
    img = np.asarray(img)
    h, w = img.shape[:2]
    cy, cx = ndi.center_of_mass(np.asarray(mask) > 0)
    y0 = int(np.clip(cy - size // 2, 0, max(h - size, 0)))
    x0 = int(np.clip(cx - size // 2, 0, max(w - size, 0)))
    return img[y0:y0 + size, x0:x0 + size]


def crop_synthetic_grid(img, mask, key, size=TILE_SIZE):
    """Cắt ảnh sinh (512×512) cỡ `size` quanh tâm mặt nạ lỗi NHƯNG lệch tâm một khoảng ngẫu nhiên (20..size-20
    điểm ảnh mỗi trục), seed cố định theo `key` (vd tên tệp ảnh) để tái lập được. Dùng để so ảnh sinh với ô
    W0003 thật (xem rủi ro trong plan, mục 6/10, bước 7): ô W0003 gốc là CẮT LƯỚI CỐ ĐỊNH từ ảnh lớn, khuyết tật
    không nằm giữa khung; `crop_synthetic` (căn giữa đúng tâm) lệch hệ thống so cách cắt đó, nhất là đặc trưng
    nhạy vị trí biên (bien_*). Khung lệch ngẫu nhiên nhưng vẫn LUÔN chứa tâm khuyết tật mô phỏng đúng cách W0003
    cắt theo lưới mà không biết trước lỗi nằm đâu trong ô."""
    img = np.asarray(img)
    h, w = img.shape[:2]
    cy, cx = ndi.center_of_mass(np.asarray(mask) > 0)
    rng = np.random.default_rng(zlib.crc32(str(key).encode()))
    y0 = int(np.clip(cy - rng.uniform(20, size - 20), 0, max(h - size, 0)))
    x0 = int(np.clip(cx - rng.uniform(20, size - 20), 0, max(w - size, 0)))
    return img[y0:y0 + size, x0:x0 + size]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.parse_args()
    REF_DIR.mkdir(parents=True, exist_ok=True)

    print("Hiệu chỉnh ngưỡng kernel trên nền sạch W0003...")
    calibration = build_calibration()
    CALIBRATION_PATH.write_text(json.dumps(calibration, ensure_ascii=False, indent=1), encoding="utf-8")
    thr_rounded = {k: round(v, 3) for k, v in calibration["thr"].items()}
    print(f"  ngưỡng: {thr_rounded}, phân vị chung {calibration['q']:.4f}, "
          f"đạt {calibration['achieved_nd_rate']:.3f} (mục tiêu {ND_ALARM}) trên {calibration['n_crops']} ô nền sạch")

    print("Tính 16 đặc trưng trên mọi ô khuyết tật thật W0003...")
    df = build_features_csv(calibration["thr"])
    df.to_csv(FEATURES_CSV_PATH, index=False)

    print(f"{len(df)} ô · {len(W0003_CLASS) - sum(v is None for v in W0003_CLASS.values())} lớp có ánh xạ")
    print("Tỉ lệ có vùng (has_region) theo lớp W0003:")
    for cls, g in df.groupby("cls"):
        print(f"  {cls:32s} n={len(g):3d}  has_region={g.has_region.mean():.3f}")
    print("\nTrung vị 16 đặc trưng theo lớp (chỉ lớp có vùng):")
    with pd.option_context("display.width", 160, "display.max_columns", 20):
        print(df[df.has_region > 0].groupby("cls")[DEFECT_FEATURES].median().round(3))


if __name__ == "__main__":
    main()
