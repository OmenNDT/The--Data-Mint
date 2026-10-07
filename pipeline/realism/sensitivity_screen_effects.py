"""Bước 4 (độ nhạy): ghép hiệu ứng một biến thể so với lượt gốc, trên ca chung (paired_stats.compare_paired),
lọc còn mục tiêu/cặp của các loại biến thể đó thật sự chạm tới (variant["types"]). Tách khỏi
sensitivity_screen.py để mỗi tệp dưới 200 dòng."""
from . import paired_stats

# pair (nhãn trong issues.py/evaluate.py) -> loại sinh tương ứng, dùng để lọc theo variant["types"].
TYPE_OF_PAIR = {
    "CR↔crack": "crack",
    "PO↔porosity": "porosity",
    "LP↔lack_of_penetration": "lack_of_penetration",
    "LP↔lack_of_fusion": "lack_of_fusion",
}


def _c2st_by_pair(result):
    return {p["pair"]: p.get("c2st") for p in (result or {}).get("pairs", [])}


def assemble_effects(base_result, variant_result, types, B=1000, seed=0):
    """{"targets": {nhãn mục tiêu: mục của compare_paired}, "c2st": {pair: {base, new, delta}}} chỉ cho các
    cặp/mục tiêu của loại nằm trong `types` (loại biến thể đó thật sự sinh lại hoặc tính lại)."""
    paired = paired_stats.compare_paired(base_result, variant_result, B=B, seed=seed)
    targets = {label: e for label, e in paired.items() if TYPE_OF_PAIR.get(e["pair"]) in types}

    base_c2st, var_c2st = _c2st_by_pair(base_result), _c2st_by_pair(variant_result)
    c2st = {}
    for pair, t in TYPE_OF_PAIR.items():
        if t not in types:
            continue
        b, n = base_c2st.get(pair), var_c2st.get(pair)
        if b is None and n is None:
            continue
        c2st[pair] = {"base": b, "new": n, "delta": (n - b) if (b is not None and n is not None) else None}
    return {"targets": targets, "c2st": c2st}
