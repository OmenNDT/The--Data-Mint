"""Mức "hoàn hảo" (thật so thật) cho mỗi loại khuyết tật có tham chiếu W0003, tính sẵn và lưu cache vì
null_reference (chia đôi ảnh thật nhiều lần, bootstrap) chậm hơn nhiều so với một lượt đo thường.

    python -m realism.reference_w0003_null

Đọc w0003-defect-features.csv (đã có từ `python -m realism.reference_w0003`), ghi w0003-null.json:
mỗi loại khuyết tật bộ sinh có >= 4 ô thật tách được vùng (has_region) có null_reference (C2ST/KID/
density/coverage, mục median/p5/p95, xem defect_metrics.null_reference); loại dưới 4 ô ghi null: None
kèm n_real để nơi gọi biết vì sao thiếu, không phải lỗi.
"""
import json
from pathlib import Path

import pandas as pd

from . import defect_metrics as dm
from .defect_features16 import DEFECT_FEATURES
from .reference_w0003 import RULER_V1, RULER_V2, RULER_V3, RULERS, REF_DIR, W0003_CLASS

NULL_PATH = REF_DIR / "w0003-null.json"
NULL_PATH_V2 = REF_DIR / "w0003-null-v2.json"          # thước v2 (bước 2, plan 261006), KHÔNG đè NULL_PATH
NULL_PATH_V3 = REF_DIR / "w0003-null-v3.json"          # thước v3 (follow-up 7/10), KHÔNG đè NULL_PATH/NULL_PATH_V2
NULL_PATHS = {RULER_V1: NULL_PATH, RULER_V2: NULL_PATH_V2, RULER_V3: NULL_PATH_V3}
MIN_ROWS = 4   # dưới mức này chia đôi còn lại 2 mẫu/nửa, null_reference không có nghĩa thống kê
REPS = 50
SEED = 0


def build(reps=REPS, seed=SEED, ruler=RULER_V1):
    """Trả dict {defect_type: {"null": ... | None, "n_real": n}} cho mọi loại có ánh xạ W0003, đọc tệp đặc
    trưng của `ruler` (xem reference_w0003.RULERS). ruler mặc định RULER_V1 giữ đúng hành vi hiện hành."""
    features_csv = RULERS[ruler]["features_csv"]
    if not features_csv.exists():
        raise FileNotFoundError(f"chưa có {features_csv}, chạy `python -m realism.reference_w0003 --ruler {ruler}` trước")
    df = pd.read_csv(features_csv)
    out = {}
    for defect_type in sorted(dt for dt, cls in W0003_CLASS.items() if cls is not None):
        rows = df[(df.defect_type == defect_type) & (df.has_region > 0)]
        feats = rows[DEFECT_FEATURES].dropna().to_numpy(float)
        if len(feats) < MIN_ROWS:
            out[defect_type] = {"null": None, "n_real": len(feats)}
            continue
        out[defect_type] = {"null": dm.null_reference(feats, reps=reps, seed=seed), "n_real": len(feats)}
    return out


def load_null(defect_type, ruler=RULER_V1):
    """Mức "hoàn hảo" đã tính sẵn cho `defect_type` của `ruler`, hoặc None nếu chưa chạy build() hay loại đó
    không có trong cache (chưa có ánh xạ W0003, hoặc dưới MIN_ROWS mẫu thật). ruler mặc định RULER_V1 giữ
    đúng hành vi hiện hành (nơi gọi không truyền ruler đọc đúng NULL_PATH như trước)."""
    path = NULL_PATHS.get(ruler, NULL_PATH)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    # Trả THẲNG khối null_reference ({"c2st": {...}, "kid": ...}); cache lưu lồng {"null": ..., "n_real": n}, bản
    # đầu trả cả khối ngoài nên nơi đọc c2st.median ra None, cột "hoàn hảo" toàn dấu gạch (thấy 6/10).
    return (data.get(defect_type) or {}).get("null")


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ruler", choices=sorted(RULERS), default=RULER_V1)
    a = ap.parse_args()
    REF_DIR.mkdir(parents=True, exist_ok=True)
    out = build(ruler=a.ruler)
    NULL_PATHS[a.ruler].write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for defect_type, entry in out.items():
        n = entry["n_real"]
        if entry["null"] is None:
            print(f"  {defect_type:24s} n_real={n:3d}  bỏ qua (dưới {MIN_ROWS} mẫu)")
        else:
            c2 = entry["null"]["c2st"]
            print(f"  {defect_type:24s} n_real={n:3d}  C2ST hoàn hảo={c2['median']:.3f}" if c2 else
                  f"  {defect_type:24s} n_real={n:3d}  C2ST hoàn hảo=— (n_syn dưới ngưỡng)")


if __name__ == "__main__":
    main()
