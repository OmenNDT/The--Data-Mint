"""Realism check of one HMI run folder, started from the "Đánh giá độ thật" button.

Runs the existing evaluator of the realism loop (`python -m realism.evaluate`, six shape/edge
criteria vs RIAWELC real defects + C2ST) on `output/synthetic/<run>/` in a detached process,
so a long evaluation never blocks a request thread. Results land where the realism page reads
them (`realism/state/runs/hmi-eval-<run>-<time>/result.json`), so both pages show the same run.
Only the six defect types with a real reference are measured (others are reported as absent).
"""

import json
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Dict, Optional

from .plant_production_readers import PIPELINE_DIR

RUNS_DIR = PIPELINE_DIR / "realism" / "state" / "runs"
LOG_DIR = PIPELINE_DIR / "plant_hmi" / "control"
WORKERS = "16"
LABELS = {"vung_dac": "Độ đặc vùng", "vung_huong": "Góc nghiêng vùng", "bien_daodong": "Dao động dọc biên",
          "vung_lechtam": "Độ lệch tâm", "vung_dayhop": "Độ đầy hộp bao", "bien_doc": "Độ dốc tại biên"}

_jobs: Dict[str, tuple] = {}    # run name -> (Popen, eval run id)
_lock = threading.Lock()


def _prefix(name: str) -> str:
    return f"hmi-eval-{name}-"


def start(run_dir: Path, name: str) -> str:
    """Start (or reuse a running) evaluation of one run folder; returns the eval run id."""
    with _lock:
        job = _jobs.get(name)
        if job and job[0].poll() is None:
            return job[1]
        run_id = f"{_prefix(name)}{time.strftime('%Y%m%d-%H%M%S')}"
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_DIR / f"{run_id}.log", "wb") as log:
            proc = subprocess.Popen(
                [sys.executable, "-m", "realism.evaluate", "--source", str(run_dir),
                 "--run-id", run_id, "--workers", WORKERS],
                cwd=str(PIPELINE_DIR), stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        _jobs[name] = (proc, run_id)
        return run_id


def _verdict(auc: Optional[float]) -> str:
    """AUC 0.5 = real and synthetic indistinguishable on this criterion."""
    if auc is None:
        return "—"
    gap = abs(auc - 0.5)
    return "gần giống" if gap < 0.1 else "hơi lệch" if gap < 0.25 else "khác rõ"


def _defect_metrics_summary(result: Dict) -> Dict:
    """Thước mới (16 đặc trưng khuyết tật, tham chiếu W0003 thật): một hàng gọn mỗi loại lỗi có trong
    đợt chạy, kèm mức "hoàn hảo" (thật so thật, null) để so sánh ngay bên cạnh."""
    dm = result.get("defect_metrics") or {}
    rows = []
    for defect_type, e in (dm.get("types") or {}).items():
        if not e.get("n_syn"):
            continue
        row = {"defect_type": defect_type, "reference": e.get("reference"),
               "n_real": e.get("n_real"), "n_syn": e.get("n_syn"),
               "detection_rate_real": e.get("detection_rate_real"), "detection_rate_syn": e.get("detection_rate_syn"),
               "c2st": e.get("c2st"), "c2st_reason": e.get("c2st_reason"),
               "kid": e.get("kid"), "density_coverage": e.get("density_coverage"),
               "small_reference": e.get("small_reference", False)}
        null = e.get("null") or {}
        row["perfect"] = {"c2st": (null.get("c2st") or {}).get("median") if null else None,
                           "kid": (null.get("kid") or {}).get("median") if null else None,
                           "density": (null.get("density") or {}).get("median") if null else None,
                           "coverage": (null.get("coverage") or {}).get("median") if null else None}
        rows.append(row)
    return {"ruler": dm.get("ruler"), "error": dm.get("error"), "types": rows}


def summarize(result: Dict) -> Dict:
    """Compact view: thước mới trước (per-type: C2ST/KID/density/coverage/tách vùng + mức hoàn hảo),
    sau đó thước cũ (C2ST, images used, each criterion real vs synthetic, so RIAWELC xuyên miền)."""
    pairs = []
    for p in result.get("pairs") or []:
        if not p.get("n_syn"):
            continue  # this defect type is not in the run
        crit = [{"key": k, "label": LABELS.get(k, k), "real": v.get("real_med"), "syn": v.get("syn_med"),
                 "auc": v.get("auc"), "verdict": _verdict(v.get("auc"))} for k, v in (p.get("crit") or {}).items()]
        pairs.append({"pair": p.get("pair"), "synthetic": p.get("synthetic"), "n_syn": p.get("n_syn"),
                      "n_used": p.get("n_used"), "c2st": p.get("c2st"), "criteria": crit})
    return {"run_id": result.get("run_id"), "finished": result.get("finished"),
            "defect_metrics": _defect_metrics_summary(result), "pairs": pairs}


def _latest_result(name: str) -> Optional[Dict]:
    if not RUNS_DIR.is_dir():
        return None
    done = sorted((d for d in RUNS_DIR.glob(f"{_prefix(name)}*") if (d / "result.json").is_file()),
                  key=lambda d: d.name, reverse=True)
    if not done:
        return None
    try:
        return json.loads((done[0] / "result.json").read_text())
    except (OSError, ValueError):
        return None


def status(name: str) -> Dict:
    """none | running | done | error, with the newest finished summary when there is one."""
    with _lock:
        job = _jobs.get(name)
    if job and job[0].poll() is None:
        return {"state": "running", "run_id": job[1]}
    result = _latest_result(name)
    if job and job[0].returncode not in (0, None) and (result is None or result.get("run_id") != job[1]):
        tail = ""
        try:
            tail = (LOG_DIR / f"{job[1]}.log").read_text(errors="replace")[-400:]
        except OSError:
            pass
        return {"state": "error", "run_id": job[1], "error": tail or f"exit {job[0].returncode}"}
    if result is None:
        return {"state": "none"}
    return {"state": "done", **summarize(result)}
