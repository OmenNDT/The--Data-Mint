"""Thước đo độ thật MỚI cho một bộ ảnh sinh: 16 đặc trưng khuyết tật, tham chiếu W0003 thật (×1),
bốn độ đo (C2ST, KID, density/coverage, tỉ lệ tách vùng), kèm mức "hoàn hảo" (thật so thật).

    python -m realism.defect_eval <source_dir> [--workers 16]

`source_dir` có cấu trúc <loại khuyết tật>/<ảnh>.png + <ảnh>_mask.png (như output bộ sinh / realism.evaluate).
Mỗi loại thư mục con có mặt sẽ được đo; loại không có mẫu W0003 tham chiếu (W0003_CLASS=None, xem
reference_w0003.py) chỉ báo tỉ lệ tách vùng của ảnh sinh, không có cột so sánh.
"""
import argparse
import json
import os
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

from . import defect_metrics as dm
from .defect_features16 import DEFECT_FEATURES, defect_features
from .defect_metrics_density import density_coverage, kid
from .reference_w0003 import (CALIBRATION_PATH, RULERS, W0003_CLASS, crop_synthetic_grid, load_reference, ruler_for)
from .reference_w0003_null import load_null

WORKERS = min(16, os.cpu_count() or 4)
MIN_C2ST_ROWS = 10        # khớp realism.defect_metrics.MIN_C2ST_N
SMALL_REFERENCE_ROWS = 15  # dưới mức này gắn cờ "tham chiếu ít mẫu", xem rủi ro trong plan
TOP_FEATURES = 6
ON_TARGET_THRESHOLD = 0.3  # tỉ lệ vùng đo trùng mặt nạ lỗi thật tối thiểu để tính là "đúng đối tượng" (bước 1 plan 261006)
# Loại chỉ tham khảo, KHÔNG dùng để chặn cổng (bước 3 plan 261006): lẫn kim loại sáng hơn nền (bộ dò tìm vùng
# tối nên không đo được, xem riawelc-prompt-templates/plan) và W0003 chỉ có 3 ảnh thật (dưới MIN_C2ST_ROWS/
# MIN_ROWS null). Trước đây chỉ bị bỏ qua NGẦM vì n_real quá nhỏ; giờ đánh dấu rõ để issues_v2/loop_gate_v2
# (sửa riêng, xem hard constraint — vòng cổng đang chạy) không vô tình gộp detection_gap của loại này vào all_pass.
# Không thấu: thước v3 chỉ còn 6/19 ảnh thật có vùng (< 10), người dùng duyệt 7/10 chỉ tham khảo, chỉnh theo mắt.
REFERENCE_ONLY_TYPES = {"metallic_inclusion", "lack_of_penetration"}


def _load_thr():
    return json.loads(CALIBRATION_PATH.read_text(encoding="utf-8"))["thr"]


def _feature_row(args):
    """Worker cho Pool: (đường dẫn ảnh, ngưỡng thr, exclude_border, exclude_edge_band) -> dict 16 đặc trưng +
    has_region + on_target_overlap (tỉ lệ vùng đo trùng mặt nạ lỗi thật, bước 1 plan 261006), hoặc None nếu
    đọc lỗi (ảnh ghi dở, thiếu mặt nạ) hay mặt nạ trống. Top-level để pickle được qua Pool."""
    path, thr, exclude_border, exclude_edge_band = args
    try:
        img = np.asarray(Image.open(path).convert("L"), dtype=np.float32)
        mask = np.asarray(Image.open(str(path).replace(".png", "_mask.png")).convert("L")) > 127
        if not mask.any():
            return None
        name = Path(path).name
        crop = crop_synthetic_grid(img, mask, name)
        # Cắt mặt nạ CÙNG khung: crop_synthetic_grid lấy tâm + độ lệch ngẫu nhiên từ `mask` và `name` (seed), nên
        # gọi lại với mask làm "ảnh" vẫn ra đúng khung đã cắt img ở trên (không cần lộ y0/x0 ra khỏi hàm).
        mask_crop = crop_synthetic_grid(mask.astype(np.uint8), mask, name) > 0
        feats, region = defect_features(crop, thr, exclude_border=exclude_border,
                                         exclude_edge_band=exclude_edge_band, return_region=True)
        overlap = float((region & mask_crop).sum() / region.sum()) if region is not None and region.sum() > 0 else 0.0
        return {"file": name, "on_target_overlap": overlap, **feats}
    except (OSError, ValueError):
        return None


def _synthetic_features(defect_dir, thr, workers, case_map=None, exclude_border=False, exclude_edge_band=False):
    """case_map: {job_id: case_id} từ evaluate.load_case_map(source) (bước 2a plan w0003-reference: gắn case_id
    vào từng hàng để cổng nghiệm thu v2 ghép cặp ca giữa hai vòng). {} hoặc None (vòng không dùng bộ đề thi cố
    định, ảnh ngẫu nhiên cũ) → mọi hàng case_id=None, cột vẫn có mặt để schema nhất quán."""
    cols = ["file", "has_region", "on_target_overlap"] + DEFECT_FEATURES + ["case_id"]
    files = sorted(defect_dir.glob("*[0-9].png"))
    if not files:
        return pd.DataFrame(columns=cols)
    with Pool(workers) as pool:
        args = [(f, thr, exclude_border, exclude_edge_band) for f in files]
        rows = [r for r in pool.map(_feature_row, args, chunksize=4) if r]
    # Nhập trễ (không phải đầu tệp): evaluate.py nhập defect_eval Ở DÒNG ĐẦU TIÊN, nên nhập evaluate tại đây lúc
    # module mới nạp sẽ vòng lặp (evaluate chưa định nghĩa _job_id_of). Gọi trong thân hàm thì evaluate đã nạp xong.
    from .evaluate import _job_id_of
    for r in rows:
        r["case_id"] = case_map.get(_job_id_of(r["file"])) if case_map else None
    return pd.DataFrame(rows, columns=cols)


def _on_target(syn_df, n_syn_total):
    """Độ đo "đúng đối tượng" (bước 1 plan 261006, chỉ ảnh sinh vì real W0003 không có mặt nạ lỗi): tỉ lệ
    trung bình vùng đo trùng mặt nạ lỗi thật (trên ảnh CÓ vùng đo), và tỉ lệ ca trong TOÀN BỘ ảnh mà vùng đo
    chạm đúng lỗi (>= ON_TARGET_THRESHOLD, tính cả ảnh không tách được vùng là trượt). Chỉ báo, KHÔNG gate
    (xem docstring module)."""
    if not n_syn_total or "on_target_overlap" not in syn_df:
        return {"mean_overlap_on_region": None, "on_target_rate": None, "threshold": ON_TARGET_THRESHOLD}
    region_rows = syn_df.loc[syn_df["has_region"].astype(bool), "on_target_overlap"]
    mean_overlap = float(region_rows.mean()) if len(region_rows) else None
    on_target_rate = float((syn_df["on_target_overlap"] >= ON_TARGET_THRESHOLD).sum() / n_syn_total)
    return {"mean_overlap_on_region": mean_overlap, "on_target_rate": on_target_rate, "threshold": ON_TARGET_THRESHOLD}


def _evaluate_type(defect_type, syn_df, ruler):
    """Một mục kết quả cho `defect_type`: so ảnh sinh (syn_df) với W0003 thật nếu có ánh xạ, không thì
    chỉ báo tỉ lệ tách vùng của ảnh sinh. "cases": hàng theo từng ca (case_id, has_region, 16 đặc trưng) để
    loop_gate_v2 ghép cặp ca chung giữa hai vòng (case_id=None nếu vòng không dùng bộ đề thi cố định).
    "reference_only": loại có tham chiếu W0003 nhưng KHÔNG dùng để chặn cổng (bước 3 plan 261006, xem
    REFERENCE_ONLY_TYPES). "ruler": thước ĐÃ DÙNG cho loại này (bước follow-up 7/10: thước theo loại, xem
    reference_w0003.ruler_for) — ghi lại để biết số đo mỗi loại tính bằng sơ đồ chọn vùng nào."""
    n_syn_total = len(syn_df)
    det_syn = dm.detection_rate(syn_df["has_region"].to_numpy(bool)) if n_syn_total else None
    on_target = _on_target(syn_df, n_syn_total)
    cases = syn_df[["case_id", "has_region"] + DEFECT_FEATURES].to_dict("records") if n_syn_total else []
    if W0003_CLASS.get(defect_type) is None:
        return {"reference": None, "n_syn": n_syn_total, "detection_rate_syn": det_syn,
                "on_target": on_target, "ruler": ruler, "cases": cases}

    real_df = load_reference(defect_type, ruler=ruler)
    real_shape = real_df.loc[real_df["has_region"].astype(bool), DEFECT_FEATURES].dropna().to_numpy(float)
    syn_shape = syn_df.loc[syn_df["has_region"].astype(bool), DEFECT_FEATURES].dropna().to_numpy(float) \
        if n_syn_total else np.empty((0, len(DEFECT_FEATURES)))
    n_real, n_syn_shape = len(real_shape), len(syn_shape)

    c2st, c2st_reason = None, None
    if n_real >= MIN_C2ST_ROWS and n_syn_shape >= MIN_C2ST_ROWS:
        c2st = dm.c2st_median(real_shape, syn_shape)
    else:
        c2st_reason = f"cần >= {MIN_C2ST_ROWS} ô tách được vùng mỗi bên (thật {n_real}, sinh {n_syn_shape})"

    kid_val, dc, top_features = None, {"density": None, "coverage": None}, []
    if n_real and n_syn_shape:
        std_real, std_syn = dm.rank_normal(real_shape, syn_shape)
        kid_val = kid(std_real, std_syn)
        dc = density_coverage(std_real, std_syn)
        top_features = dm.per_feature(real_shape, syn_shape, DEFECT_FEATURES)[:TOP_FEATURES]

    return {
        "reference": W0003_CLASS[defect_type],
        "reference_only": defect_type in REFERENCE_ONLY_TYPES,
        "ruler": ruler,
        "n_real": n_real, "n_syn": n_syn_total, "n_syn_region": n_syn_shape,
        "detection_rate_real": dm.detection_rate(real_df["has_region"].to_numpy(bool)),
        "detection_rate_syn": det_syn,
        "on_target": on_target,
        "c2st": c2st, "c2st_reason": c2st_reason,
        "kid": kid_val, "density_coverage": dc,
        "top_features": top_features,
        "null": (nul := load_null(defect_type, ruler=ruler)),
        "perfect": {m: ((nul or {}).get(m) or {}).get("median") for m in ("c2st", "kid", "density", "coverage")},
        "small_reference": n_real < SMALL_REFERENCE_ROWS,
        "cases": cases,
    }


def evaluate_defects(source_dir, workers=WORKERS, ruler=None):
    """Đo mọi loại khuyết tật có thư mục con trong `source_dir`.

    ruler=None (mặc định, dùng cho sản xuất/evaluate.run): THƯỚC THEO LOẠI (bước follow-up 7/10, xem
    reference_w0003.ruler_for) — mỗi loại tự chọn v1/v2/v3, KHÔNG ép chung một thước. ruler=<v1/v2/v3> (ép
    tường minh, dùng để đo lại một thư mục ảnh ĐÃ CÓ bằng MỘT thước duy nhất cho mọi loại, vd so sánh trước/
    sau khi đổi ngưỡng): xem CLI `python -m realism.defect_eval <dir> --ruler w0003-16dac-trung-v3`.
    Trả {defect_type: entry} (xem _evaluate_type, mỗi entry mang "ruler" đã dùng cho chính loại đó)."""
    source_dir = Path(source_dir)
    thr = _load_thr()
    from .evaluate import load_case_map   # nhập trễ: xem lý do trong _synthetic_features
    case_map = load_case_map(source_dir)
    out = {}
    for d in sorted(p for p in source_dir.iterdir() if p.is_dir()):
        if d.name not in W0003_CLASS:
            continue
        eff_ruler = ruler or ruler_for(d.name)
        cfg = RULERS[eff_ruler]
        syn_df = _synthetic_features(d, thr, workers, case_map, exclude_border=cfg["exclude_border"],
                                      exclude_edge_band=cfg["exclude_edge_band"])
        out[d.name] = _evaluate_type(d.name, syn_df, ruler=eff_ruler)
    return out


def _fmt(v, d=3):
    return "—" if v is None else f"{v:.{d}f}"


def _fmt_on_target(on_target):
    if not on_target or on_target.get("on_target_rate") is None:
        return "—"
    return f"{on_target['on_target_rate']:.2f} (TB vùng trùng {_fmt(on_target['mean_overlap_on_region'], 2)})"


def print_table(result):
    for defect_type, e in result.items():
        if e["reference"] is None:
            print(f"{defect_type:24s} (không có tham chiếu W0003, thước {e.get('ruler', '—')}) sinh n={e['n_syn']:4d} "
                  f"tách vùng={_fmt(e['detection_rate_syn'], 2)} đúng đối tượng={_fmt_on_target(e.get('on_target'))}")
            continue
        k = e["kid"] or {}
        warn = " [tham chiếu ít mẫu]" if e["small_reference"] else ""
        warn += " [CHỈ THAM KHẢO, không chặn cổng]" if e.get("reference_only") else ""
        print(f"{defect_type:24s} so {e['reference']:28s} (thước {e.get('ruler', '—')}){warn}\n"
              f"  n thật/sinh {e['n_real']}/{e['n_syn']} (tách vùng thật {_fmt(e['detection_rate_real'], 2)} "
              f"sinh {_fmt(e['detection_rate_syn'], 2)}, đúng đối tượng {_fmt_on_target(e.get('on_target'))})\n"
              f"  C2ST {_fmt(e['c2st'])}{' (' + e['c2st_reason'] + ')' if e['c2st_reason'] else ''} · "
              f"KID {_fmt(k.get('value'))} [{_fmt(k.get('ci_low'))}, {_fmt(k.get('ci_high'))}] · "
              f"density {_fmt(e['density_coverage']['density'])} · coverage {_fmt(e['density_coverage']['coverage'])}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("source_dir")
    ap.add_argument("--workers", type=int, default=WORKERS)
    ap.add_argument("--ruler", choices=sorted(RULERS), default=None,
                     help="bỏ trống (mặc định): thước THEO LOẠI như sản xuất (xem reference_w0003.ruler_for). "
                          "Chỉ định v1/v2: ép MỘT thước cho mọi loại — đo lại một thư mục ảnh sinh ĐÃ CÓ để so "
                          "sánh trước/sau, không cần sinh lại")
    a = ap.parse_args()
    print_table(evaluate_defects(a.source_dir, a.workers, ruler=a.ruler))


if __name__ == "__main__":
    main()
