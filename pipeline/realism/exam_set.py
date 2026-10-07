"""Bộ đề thi cố định cho vòng độ thật: mỗi vòng sinh lại ĐÚNG các ca này (nền, seed, loại) để so sánh
công bằng giữa các vòng (không lẫn nhiễu do nền/seed đổi ngẫu nhiên mỗi lần).

    python3 -m realism.exam_set                      # tạo realism/state/exam-set.json (một lần)

build_exam_set: tất định theo seed — chạy lại cho cùng kết quả (không phá bộ đề thi đã có nếu seed/tham số
giữ nguyên). load_exam_set: đọc bộ đề thi. subset: n ca đầu mỗi loại, dùng khi vòng lặp chỉ cần n ≤ 40 ca
(ít hơn bộ đầy đủ) hoặc chỉ nhắm một số loại.
"""
import json
import time
from pathlib import Path

import numpy as np

from .evaluate import PAIRS

STATE = Path(__file__).resolve().parent / "state"
EXAM_SET_PATH = STATE / "exam-set.json"
DEFAULT_SEED = 20261002
DEFAULT_PER_TYPE = 40

# 6 loại sinh có cặp đối chiếu RIAWELC thật trong evaluate.PAIRS (thứ tự cố định để tất định).
SYNTH_TYPES = sorted({k for _, k in PAIRS})


def _list_backgrounds(backgrounds_dir):
    d = Path(backgrounds_dir)
    files = sorted(list(d.glob("*.png")) + list(d.glob("*.jpg")))
    if not files:
        raise RuntimeError(f"Không tìm thấy ảnh nền trong {d}")
    return files


def build_exam_set(backgrounds_dir, types=None, per_type=DEFAULT_PER_TYPE, seed=DEFAULT_SEED):
    """Tạo bộ đề thi tất định: per_type ca cho mỗi loại trong types (mặc định 6 loại có cặp RIAWELC).
    Ghi realism/state/exam-set.json rồi trả về dict đó. Cùng backgrounds_dir/types/per_type/seed → cùng kết quả."""
    types = sorted(types) if types else list(SYNTH_TYPES)
    backgrounds = _list_backgrounds(backgrounds_dir)
    rng = np.random.default_rng(seed)

    cases = []
    for defect_type in types:                                # thứ tự loại cố định (sorted) cho tất định
        for i in range(per_type):
            case = {
                "case_id": f"{defect_type}-{i:03d}",
                "defect_type": defect_type,
                "seed": int(rng.integers(0, 2**32 - 1)),
                "background_image": str(backgrounds[int(rng.integers(0, len(backgrounds)))]),
            }
            cases.append(case)

    exam = {
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        "seed": seed,
        "per_type": per_type,
        "types": types,
        "backgrounds_dir": str(backgrounds_dir),
        "cases": cases,
    }
    STATE.mkdir(parents=True, exist_ok=True)
    tmp = EXAM_SET_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(exam, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(EXAM_SET_PATH)
    return exam


def load_exam_set(path=None):
    """Đọc bộ đề thi đã tạo. Chưa có → lỗi rõ ràng (gọi build_exam_set trước)."""
    p = Path(path) if path else EXAM_SET_PATH
    if not p.exists():
        raise FileNotFoundError(f"Chưa có bộ đề thi ở {p}: chạy build_exam_set(...) trước")
    return json.loads(p.read_text(encoding="utf-8"))


def subset(types, n, exam=None):
    """n ca đầu mỗi loại trong types (giữ thứ tự case_id gốc trong bộ đề thi, tức thứ tự sinh ban đầu).
    n có thể nhỏ hơn per_type của bộ đề thi (không được lớn hơn, bộ đề thi không đủ ca)."""
    exam = exam or load_exam_set()
    by_type = {}
    for c in exam["cases"]:
        by_type.setdefault(c["defect_type"], []).append(c)

    out = []
    for t in types:
        pool = by_type.get(t, [])
        if n > len(pool):
            raise ValueError(f"Bộ đề thi chỉ có {len(pool)} ca cho loại {t}, không đủ {n}")
        out.extend(pool[:n])
    return out


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--backgrounds-dir", required=True)
    ap.add_argument("--per-type", type=int, default=DEFAULT_PER_TYPE)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--types", default=",".join(SYNTH_TYPES))
    a = ap.parse_args()
    exam = build_exam_set(a.backgrounds_dir, a.types.split(","), a.per_type, a.seed)
    print(f"Đã tạo {len(exam['cases'])} ca ({a.per_type}/loại × {len(exam['types'])} loại) → {EXAM_SET_PATH}")


if __name__ == "__main__":
    main()
