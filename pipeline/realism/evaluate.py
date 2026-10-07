"""Đánh giá một bộ ảnh sinh so với RIAWELC thật theo sáu tiêu chí.

    python3 -m realism.evaluate --source output/realism-loop/iter-01 --run-id eval-01 [--scale x2] [--workers 32]

Mỗi ảnh sinh: cắt 227 × 227 quanh tâm mặt nạ (phóng ×2 trước nếu --scale x2, vì lỗi W0003 nhỏ khoảng một nửa theo điểm
ảnh so với RIAWELC), tách vùng bằng mặt nạ kernel v2, đo sáu tiêu chí trên vùng lớn nhất; chỉ giữ ảnh có vùng đó chạm
mặt nạ thật (không thì đang đo nền). Ảnh mặt nạ trống bị loại và đếm riêng.
Ra realism/state/runs/<run_id>/result.json; tiến độ từng ảnh ghi events.jsonl cùng thư mục (vòng lặp và HMI đọc).
"""
import argparse
import json
import os
import re
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image
from scipy import ndimage as ndi

from .defect_eval import evaluate_defects
from .features import CRITERIA, REF_DIR, six_criteria
from .knobs import read_pv
from .reference_w0003 import RULER_SCHEME_ID
from .runlog import RunLog
from .stats import auc, c2st, ks

# Định danh sơ đồ chọn thước hiện hành (follow-up 7/10: thước THEO LOẠI, xem reference_w0003.ruler_for);
# ghi vào defect_metrics["ruler"] mỗi lần đo để loop_gate_v2/loop_partial so được bản tốt nhất cũ đo bằng
# sơ đồ nào — khác đi thì coi là "mốc mới: thước mới" (đặt cổng lại) và sinh lại TẤT CẢ loại (không mang số
# đo cũ). KHÔNG đổi tên biến DEFECT_METRICS_RULER (nơi gọi cũ còn tham chiếu), chỉ đổi GIÁ TRỊ theo sơ đồ mới.
DEFECT_METRICS_RULER = RULER_SCHEME_ID

PAIRS = [("CR", "crack"), ("PO", "porosity"), ("LP", "lack_of_penetration"),
         ("PO", "clustered_porosity"), ("PO", "linear_porosity"), ("LP", "lack_of_fusion")]
S = 227
# Tên tệp ảnh ra của batch scheduler: "<defect_type>_<job_id:06d>.png" (batch-job-scheduler.py).
_JOB_ID_RE = re.compile(r"_(\d{6})\.png$")


def _job_id_of(path):
    m = _JOB_ID_RE.search(Path(path).name)
    return int(m.group(1)) if m else None


def load_case_map(source):
    """case_id theo job_id (chỉ số trong fixed_jobs của vòng này), đọc từ <source>/fixed-jobs.json mà
    realism.loop._gen_config ghi kèm ảnh ra. Rỗng nếu vòng không dùng bộ đề thi cố định (vd output/synthetic cũ):
    khi đó không ghép được cặp giữa các vòng, nhưng phép đo vẫn chạy bình thường."""
    p = Path(source) / "fixed-jobs.json"
    if not p.exists():
        return {}
    cases = json.loads(p.read_text(encoding="utf-8"))
    return {i: c["case_id"] for i, c in enumerate(cases)}


def _crop(a, cy, cx):
    y0 = int(np.clip(cy - S // 2, 0, a.shape[0] - S))
    x0 = int(np.clip(cx - S // 2, 0, a.shape[1] - S))
    return a[y0:y0 + S, x0:x0 + S]


def measure(args):
    """Đo một ảnh; lỗi đọc (ảnh ghi dở khi bị dừng, thiếu mặt nạ, lệch cỡ) chỉ loại riêng ảnh đó.
    args: (path, scale) hoặc (path, scale, case_id) — case_id None nếu vòng không dùng bộ đề thi cố định."""
    t0 = time.perf_counter()
    path, scale = args[0], args[1]
    case_id = args[2] if len(args) > 2 else None
    try:
        out = _measure(path, scale)
    except Exception as e:
        out = {"kind": Path(path).parent.name, "empty_mask": False, "error": f"{type(e).__name__}: {e}"[:200]}
    out["dur"] = time.perf_counter() - t0
    out["path"] = str(path)   # stable sort key: parallel workers return rows in any order
    out["case_id"] = case_id
    return out


def _measure(path, scale):
    img = np.asarray(Image.open(path).convert("L"), dtype=np.float32)
    gt = np.asarray(Image.open(str(path).replace(".png", "_mask.png")).convert("L")) > 127
    out = {"kind": Path(path).parent.name, "empty_mask": not gt.any()}
    if not out["empty_mask"]:
        cy, cx = ndi.center_of_mass(gt)
        if scale == 2:
            n = img.shape[0] * 2
            img = np.asarray(Image.fromarray(img.astype(np.uint8)).resize((n, n), Image.BICUBIC), dtype=np.float32)
            gt = np.asarray(Image.fromarray(gt.astype(np.uint8) * 255).resize((n, n), Image.NEAREST)) > 127
            cy, cx = cy * 2, cx * 2
        c, g = _crop(img, cy, cx), _crop(gt, cy, cx)
        f = six_criteria(c)
        largest = f.pop("largest")
        f["hit"] = float(largest[ndi.binary_dilation(g, iterations=3)].any()) if largest is not None else 0.0
        out.update(f)
    return out


def _c2st_median(real, syn, seeds=5):
    """C2ST median over a few fold splits: one split of ~100 synthetic vs 3,000 real rows can
    land far from the typical value (seen on the LF-100 run: 0.877 once, 0.975 median)."""
    vals = [v for v in (c2st(real, syn, seed=s) for s in range(seeds)) if v is not None]
    return float(np.median(vals)) if vals else None


def compare(rows, real):
    """Trả (pairs, cases): pairs là thống kê gộp (trung vị, AUC, C2ST) như cũ; cases là hàng theo TỪNG ca
    (case_id, hit, used, sáu tiêu chí khi used) cho các ca đọc được VÀ có case_id (bộ đề thi cố định) — dùng để ghép cặp
    bootstrap giữa các vòng (realism/paired_stats.py), không ảnh hưởng tới pairs."""
    pairs, cases = [], []
    for rc, kind in PAIRS:
        R = real[real.cls == rc]
        mine = [r for r in rows if r["kind"] == kind]
        if not mine:
            continue
        good = [r for r in mine if not r.get("error") and not r["empty_mask"]]
        ok = [r for r in good if r["has_region"] and r["hit"]]
        pair_label = f"{rc}↔{kind}"
        e = {"riawelc": rc, "synthetic": kind, "pair": pair_label, "n_real": len(R), "n_syn": len(mine),
             "empty_masks": sum(r["empty_mask"] for r in mine), "read_errors": sum(bool(r.get("error")) for r in mine),
             "n_used": len(ok), "hit": round(float(np.mean([r["hit"] for r in good] or [0])), 3),
             "c2st": _c2st_median(R[list(CRITERIA)].values, np.array([[r[k] for k in CRITERIA] for r in ok])),
             "crit": {}}
        for k in CRITERIA:
            sv, rv = np.array([r[k] for r in ok]), R[k].values
            d = {"real_med": float(np.median(rv)), "real_iqr": [float(np.percentile(rv, q)) for q in (25, 75)]}
            if len(sv):
                d.update(syn_med=float(np.median(sv)), syn_iqr=[float(np.percentile(sv, q)) for q in (25, 75)],
                         auc=auc(sv, rv), ks=ks(sv, rv))
            if k == "vung_huong":                              # tỉ lệ vùng đứng: trục chính lệch dọc dưới 45°
                d["real_lt45"] = float((rv < 45).mean())
                d["syn_lt45"] = float((sv < 45).mean()) if len(sv) else None
            e["crit"][k] = d
        pairs.append(e)
        # Mọi ca đọc được (good) vào "cases" để bootstrap tỉ lệ chạm lỗi đúng mẫu số; chỉ ca dùng được (used:
        # có vùng và chạm lỗi) mang sáu tiêu chí. Trước đây chỉ ghi ca "ok" nên tỉ lệ chạm lỗi trong cases luôn 1.
        for r in good:
            if r.get("case_id") is not None:
                used = bool(r["has_region"] and r["hit"])
                cases.append({"case_id": r["case_id"], "pair": pair_label, "kind": kind, "hit": r["hit"],
                              "used": used, **({k: r[k] for k in CRITERIA} if used else {})})
    return pairs, cases


def run(source, run_id, scale=2, workers=32, log=None):
    """Đo cả bộ; trả về dict kết quả và ghi result.json. log: RunLog để báo tiến độ (vòng lặp truyền vào)."""
    log = log or RunLog(run_id)
    source = Path(source)
    kinds = sorted({k for _, k in PAIRS})
    files = [p for k in kinds for p in sorted((source / k).glob("*[0-9].png"))]
    log.emit("stage", stage="evaluate", state="start", total=len(files), source=str(source))
    real = pd.read_csv(REF_DIR / "riawelc-six-criteria.csv")
    real = real[real.vung_sodom > 0]
    case_map = load_case_map(source)   # job_id -> case_id (bộ đề thi cố định); {} nếu vòng không dùng
    rows = []
    with Pool(workers) as pool:
        args = [(p, scale, case_map.get(_job_id_of(p))) for p in files]
        for r in pool.imap_unordered(measure, args, chunksize=2):
            rows.append(r)
            drain = "lỗi đọc ảnh" if r.get("error") else "mặt nạ trống" if r["empty_mask"] else \
                None if r.get("hit") else "vùng không chạm lỗi"
            log.emit("item", stage="evaluate", type=r["kind"], dur=round(r["dur"], 3), drain=drain,
                     done=len(rows), total=len(files))
    rows.sort(key=lambda r: r.get("path", ""))   # deterministic input order for C2ST folds
    pairs, cases = compare(rows, real)
    result = {"run_id": run_id, "source": str(source), "scale": f"x{scale}", "finished": time.time(),
              "knobs_pv": read_pv(source), "pairs": pairs, "cases": cases}
    try:                                           # thước mới (bước 4, plan w0003-reference): không bao giờ
        result["defect_metrics"] = {"ruler": DEFECT_METRICS_RULER, "types": evaluate_defects(source)}
    except Exception as e:                          # được làm vỡ luồng cũ (cổng/lịch sử sáu tiêu chí RIAWELC)
        result["defect_metrics"] = {"ruler": DEFECT_METRICS_RULER, "types": {}, "error": f"{type(e).__name__}: {e}"[:300]}
    log.write_json("result.json", result)
    log.emit("stage", stage="evaluate", state="end")
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source", required=True)
    ap.add_argument("--run-id", default=time.strftime("eval-%Y%m%d-%H%M%S"))
    ap.add_argument("--scale", choices=["x1", "x2"], default="x2")
    ap.add_argument("--workers", type=int, default=min(32, os.cpu_count() or 4))
    a = ap.parse_args()
    r = run(a.source, a.run_id, 2 if a.scale == "x2" else 1, a.workers)
    for p in r["pairs"]:
        print(p["pair"], "dùng", p["n_used"], "/", p["n_syn"], "C2ST", p["c2st"],
              {k: (round(d.get("syn_med", float("nan")), 3), round(d["real_med"], 3)) for k, d in p["crit"].items()})


if __name__ == "__main__":
    main()
