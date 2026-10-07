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
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image
from skimage.morphology import area_opening

from .defect_features16 import DEFECT_FEATURES, MASK_KERNELS, defect_features, kernel_maps
from .reference_w0003_crop import crop_synthetic, crop_synthetic_grid  # noqa: F401  (re-export, xem dưới)

WORKERS = min(32, os.cpu_count() or 4)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
W0003_DEFECT_DIR = PROJECT_ROOT / "dataset/4.Welds_W0003_Clear_Defects_278"
W0003_CLEAN_DIR = PROJECT_ROOT / "dataset/processed/patches_512_Confimed/clean"
REF_DIR = Path(__file__).resolve().parent / "reference"
CALIBRATION_PATH = REF_DIR / "w0003-kernel-calibration.json"
FEATURES_CSV_PATH = REF_DIR / "w0003-defect-features.csv"

# Thước v2 (bước 2, plan 261006): loại đường mép hàn trước khi chọn vùng lớn nhất (xem defect_features16.
# _is_border_line). Ngưỡng 3 kernel KHÔNG đổi (hiệu chỉnh theo per-pixel area_opening, không phụ thuộc cách
# chọn vùng lớn nhất), nên v2/v3 DÙNG LẠI CALIBRATION_PATH; chỉ 16 đặc trưng trên ô khuyết tật đổi (vùng được
# chọn khác đi) → mỗi ruler ghi file riêng, KHÔNG đè FEATURES_CSV_PATH (ruler v1 cơ chế gốc, xem hard constraint).
RULER_V1 = "w0003-16dac-trung-v1"
RULER_V2 = "w0003-16dac-trung-v2"
# Thước v3 (follow-up 7/10, người dùng duyệt): loại DẢI MÉP TRÊN/DƯỚI tile (xem defect_features16.
# _is_edge_band_line) thay vì loại đường chạm lề trái/phải + trải rộng của v2 — dành riêng cho crack/
# lack_of_penetration (bản chất lỗi dài tự nhiên, v2 loại nhầm lỗi thật chạy ngang GIỮA tile, xem báo cáo
# fullstack-developer-261007-1228-lop-feature-deviation.md mục 0 và overlay lop-real-region-overlay-261007.png).
RULER_V3 = "w0003-16dac-trung-v3"
FEATURES_CSV_PATH_V2 = REF_DIR / "w0003-defect-features-v2.csv"
FEATURES_CSV_PATH_V3 = REF_DIR / "w0003-defect-features-v3.csv"
RULERS = {
    RULER_V1: {"exclude_border": False, "exclude_edge_band": False, "features_csv": FEATURES_CSV_PATH},
    RULER_V2: {"exclude_border": True, "exclude_edge_band": False, "features_csv": FEATURES_CSV_PATH_V2},
    RULER_V3: {"exclude_border": False, "exclude_edge_band": True, "features_csv": FEATURES_CSV_PATH_V3},
}

# Thước THEO LOẠI (follow-up 7/10, người dùng duyệt): v2 mặc định cho mọi loại; crack và lack_of_penetration
# dùng v3 (loại dải mép trên/dưới, giữ lỗi dài ở GIỮA tile — xem ghi chú RULER_V3). Đổi map này PHẢI đi kèm
# đổi RULER_SCHEME_ID để vòng lặp nhận ra bản tốt nhất cũ đo bằng sơ đồ khác (xem loop_gate_v2/loop_partial:
# so sánh defect_metrics["ruler"] == RULER_SCHEME_ID để quyết định đặt mốc mới/sinh lại tất cả).
TYPE_RULER_OVERRIDES = {"crack": RULER_V3, "lack_of_penetration": RULER_V3}
RULER_SCHEME_ID = "w0003-16dac-trung-v2-per-type-crack-lop-v3"


def ruler_for(defect_type):
    """Thước áp cho `defect_type` theo sơ đồ hiện hành: v2 (loại đường mép hàn) mặc định, trừ override."""
    return TYPE_RULER_OVERRIDES.get(defect_type, RULER_V2)

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
    """Worker cho Pool: (file_path, cls, defect_type, thr, exclude_border, exclude_edge_band) -> hàng dict.
    Top-level để pickle được."""
    f, cls, defect_type, thr, exclude_border, exclude_edge_band = args
    img = np.asarray(Image.open(f).convert("L"), dtype=np.float32)
    feats = defect_features(img, thr, exclude_border=exclude_border, exclude_edge_band=exclude_edge_band)
    return {"file": f"{cls}/{f.name}", "cls": cls, "defect_type": defect_type, **feats}


def build_features_csv(thr, workers=WORKERS, exclude_border=False, exclude_edge_band=False):
    """Tính 16 đặc trưng cho mọi ô khuyết tật thật W0003 (×1, nguyên ô, không cắt không phóng).
    exclude_border=True: thước v2, loại đường mép hàn trước khi chọn vùng lớn nhất. exclude_edge_band=True:
    thước v3, loại dải mép trên/dưới tile (xem defect_features16). Trả DataFrame cột: file, cls (thư mục
    W0003), defect_type (tên bộ sinh), has_region, 16 đặc trưng."""
    cls_to_defect_type = {v: k for k, v in W0003_CLASS.items() if v is not None}
    jobs = []
    for cls_dir in sorted(p for p in W0003_DEFECT_DIR.iterdir() if p.is_dir()):
        cls = cls_dir.name
        defect_type = cls_to_defect_type.get(cls)
        for f in sorted(cls_dir.glob("*.png")):
            jobs.append((f, cls, defect_type, thr, exclude_border, exclude_edge_band))
    with Pool(workers) as pool:
        rows = pool.map(_feature_row, jobs, chunksize=4)
    cols = ["file", "cls", "defect_type", "has_region"] + DEFECT_FEATURES
    return pd.DataFrame(rows, columns=cols)


def load_reference(defect_type, ruler=RULER_V1):
    """Trả DataFrame các ô W0003 thật của loại khuyết tật bộ sinh `defect_type` (đọc tệp đặc trưng đã tính sẵn
    của `ruler`, xem RULERS). Báo lỗi rõ ràng nếu chưa chạy hiệu chỉnh, hoặc loại khuyết tật chưa có mẫu W0003
    tham chiếu. ruler mặc định RULER_V1 giữ đúng hành vi hiện hành (nơi gọi không truyền ruler không đổi)."""
    if defect_type not in W0003_CLASS:
        raise ValueError(f"defect_type không rõ: {defect_type!r} (xem W0003_CLASS)")
    if W0003_CLASS[defect_type] is None:
        raise ValueError(f"{defect_type!r} chưa có mẫu W0003 thật tham chiếu (W0003_CLASS[{defect_type!r}] = None)")
    if ruler not in RULERS:
        raise ValueError(f"ruler không rõ: {ruler!r} (xem RULERS)")
    path = RULERS[ruler]["features_csv"]
    if not path.exists():
        raise FileNotFoundError(f"chưa có {path}, chạy `python -m realism.reference_w0003 --ruler {ruler}` trước")
    df = pd.read_csv(path)
    return df[df.defect_type == defect_type].reset_index(drop=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ruler", choices=sorted(RULERS), default=RULER_V1,
                     help="v1 (mặc định, đang chạy sản xuất) hoặc v2 (loại đường mép hàn, ghi tệp riêng "
                          "FEATURES_CSV_PATH_V2, KHÔNG đè tệp v1)")
    a = ap.parse_args()
    REF_DIR.mkdir(parents=True, exist_ok=True)
    cfg = RULERS[a.ruler]

    print("Hiệu chỉnh ngưỡng kernel trên nền sạch W0003...")
    # Ngưỡng dùng chung cho mọi ruler (xem ghi chú ở RULERS): luôn đọc/ghi CALIBRATION_PATH, không nhân bản theo ruler.
    calibration = build_calibration()
    CALIBRATION_PATH.write_text(json.dumps(calibration, ensure_ascii=False, indent=1), encoding="utf-8")
    thr_rounded = {k: round(v, 3) for k, v in calibration["thr"].items()}
    print(f"  ngưỡng: {thr_rounded}, phân vị chung {calibration['q']:.4f}, "
          f"đạt {calibration['achieved_nd_rate']:.3f} (mục tiêu {ND_ALARM}) trên {calibration['n_crops']} ô nền sạch")

    print(f"Tính 16 đặc trưng trên mọi ô khuyết tật thật W0003 (ruler {a.ruler})...")
    df = build_features_csv(calibration["thr"], exclude_border=cfg["exclude_border"],
                             exclude_edge_band=cfg["exclude_edge_band"])
    df.to_csv(cfg["features_csv"], index=False)

    print(f"{len(df)} ô · {len(W0003_CLASS) - sum(v is None for v in W0003_CLASS.values())} lớp có ánh xạ")
    print("Tỉ lệ có vùng (has_region) theo lớp W0003:")
    for cls, g in df.groupby("cls"):
        print(f"  {cls:32s} n={len(g):3d}  has_region={g.has_region.mean():.3f}")
    print("\nTrung vị 16 đặc trưng theo lớp (chỉ lớp có vùng):")
    with pd.option_context("display.width", 160, "display.max_columns", 20):
        print(df[df.has_region > 0].groupby("cls")[DEFECT_FEATURES].median().round(3))


if __name__ == "__main__":
    main()
