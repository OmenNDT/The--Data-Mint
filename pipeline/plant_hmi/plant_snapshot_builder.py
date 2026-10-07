"""Builds the level-1 Plant HMI snapshot for the image-generation area.

Plant map (phase 1, read-only):
  TK-102 job queue -> R-201 mask reactor -> P-601 ComfyUI inpaint pump -> R-401 post-proc
  -> TK-801 image silo; TK-101 clean backgrounds feed P-601; D-901 failed-jobs drain.
  Utilities: U-901 local GPU, U-902 ComfyUI server, U-903 RAM/swap/load.
"""

import time
from pathlib import Path
from typing import Dict, List, Optional

from . import plant_comfyui_readers as comfy_local
from . import plant_gpu_lease as gpu_lease
from . import plant_host_readers as host
from . import plant_production_readers as prod
from . import plant_slow_probes as probes
from .plant_alarm_rules import AlarmOnDelay, derive_alarms, unknown_codes
from .plant_flow_metrics import compute_flows
from .plant_telemetry_collector import collector

_on_delay = AlarmOnDelay()
seed_alarm_on_delay = _on_delay.seed  # historian restores journal state at startup
_swap_meter = host.SwapRateMeter()


def _describe_batch(proc: Dict, now: float) -> Dict:
    """Join a live process with its config, silo scan and checkpoint."""
    # unknown config (None) must not fall back to the base config: that is another run's silo
    config = prod.load_batch_config(proc["config_path"]) if proc["config_path"] else {}
    paths = prod.section(config, "paths")
    silo = prod.scan_silo(paths.get("output_base_dir"), since_ts=proc["start_ts"] - 2)
    ckpt = prod.read_checkpoint(paths.get("checkpoint_dir"))
    target = prod.run_target(config, proc["pilot"])
    produced = silo.get("since", 0)
    uptime = now - proc["start_ts"]
    newest = silo.get("newest_ts")
    rate_run = produced / uptime * 3600 if uptime > 60 and produced else None
    eta = (target - produced) / rate_run * 3600 if rate_run and target and target > produced else None
    return {
        **proc,
        "config_name": Path(proc["config_path"]).name if proc["config_path"] else None,
        "uptime_s": round(uptime),
        "target": target,
        "produced": produced,
        "failed": _failed_jobs(proc, ckpt),
        "rate_img_h": silo.get("last_10m", 0) * 6 if silo.get("exists") else None,
        "eta_s": round(eta) if eta else None,
        # an image older than the process belongs to an earlier run
        "newest_image_ts": newest if newest and newest >= proc["start_ts"] - 2 else None,
        "output_dir": paths.get("output_base_dir"),
        "silo_known": silo.get("exists") is True,  # unreadable output dir: no wedged alarm
        "silo": silo,
        "comfyui": prod.section(config, "comfyui"),
    }


def _equipment(active: Optional[Dict], base_cfg: Dict, silo: Dict, ckpt: Dict, n_live: int) -> Dict:
    running = "running" if active else "idle"
    target = active["target"] if active else ckpt.get("total_jobs")
    done = active["produced"] if active else ckpt.get("current_index")
    pending = _pending_jobs(active, ckpt)
    failed = active["failed"] if active else ckpt.get("failed")
    bg_dir = prod.section(base_cfg, "paths").get("backgrounds_dir")
    return {
        "TK-101": {"label": "Nền X-ray sạch", "state": "idle", "level": prod.count_backgrounds(bg_dir),
                   "unit": "ảnh", "details": {"thư mục": bg_dir}},
        "TK-102": {"label": "Hàng đợi job", "state": running, "level": pending, "max": target,
                   "unit": "job", "details": {"nguồn": "tiến trình sống" if active else "checkpoint"}},
        "R-201": {"label": "Sinh mask thủ tục", "state": running,
                  "details": {"ghi chú": "chạy inline cùng P-601, chưa đo riêng (phase 2)"}},
        "P-601": {"label": "Bơm inpaint ComfyUI", "state": running, "level": n_live, "unit": "batch",
                  "details": {"pid": active["pid"] if active else None,
                              "config": active["config_name"] if active else None}},
        "R-401": {"label": "Hậu xử lý dark-convention", "state": running,
                  "details": {"ghi chú": "chạy inline cùng P-601, chưa đo riêng (phase 2)"}},
        "TK-801": {"label": "Silo ảnh tổng hợp", "state": running,
                   "level": done if active else silo.get("total"), "max": target if active else None,
                   "unit": "ảnh", "details": {"tổng trong silo": silo.get("total"),
                                               "thư mục": silo.get("path"),
                                               **{f"· {k}": v for k, v in sorted((silo.get("by_defect") or {}).items())}}},
        "D-901": {"label": "Job lỗi", "state": "idle", "level": failed, "unit": "job",
                  "details": {"nguồn": "telemetry trực tiếp, không có thì checkpoint (ghi mỗi 100 ảnh)"}},
    }


def build_snapshot() -> Dict:
    now = time.time()
    base_cfg = prod.load_batch_config(None)
    procs = host.find_batch_processes()
    collector.poll()
    flows = compute_flows(collector.events(), {p["pid"]: p["start_ts"] for p in procs}, now)
    batches: List[Dict] = [_describe_batch(p, now) for p in procs]
    active = batches[-1] if batches else None  # newest run drives the diagram

    base_paths = prod.section(base_cfg, "paths")
    silo = active["silo"] if active else prod.scan_silo(base_paths.get("output_base_dir"))
    idle_ckpt = {} if active else prod.read_checkpoint(base_paths.get("checkpoint_dir"))
    comfy_cfg = (active or {}).get("comfyui") or prod.section(base_cfg, "comfyui")
    comfy_host = str(comfy_cfg.get("host") or "127.0.0.1")
    comfy = {**probes.comfyui(comfy_host, _port(comfy_cfg.get("port"))), "host": comfy_host,
             "host_local": comfy_local.is_local_address(comfy_host),
             "procs": comfy_local.find_comfyui_processes()}
    gpu = probes.local_gpu()
    host_state = {**host.read_meminfo(), **host.read_load(), "swap_pages_s": _swap_meter.rate()}

    comfy_progress = _comfy_progress()
    alarm_state = {"now": now, "batches": batches, "comfy": comfy, "gpu": gpu, "flows": flows,
                   "comfy_progress": comfy_progress,
                   "host": host_state, "idle_checkpoint": idle_ckpt}
    unknown = unknown_codes(alarm_state)
    alarms = sorted(_on_delay.apply(derive_alarms(alarm_state), now, hold=unknown),
                    key=lambda a: (a["severity"] != "HI", a["since"]))

    for b in batches:
        b.pop("silo", None)
        b.pop("comfyui", None)
    return {
        "ts": time.time(),  # stamped at the end: clients align clocks with it
        "batches": batches,
        "equipment": _equipment(active, base_cfg, silo, idle_ckpt, len(batches)),
        "flows": flows,
        "comfy_progress": comfy_progress,
        "instruments": {
            "LT-102": _pending_jobs(active, idle_ckpt),
            "LT-801": active["produced"] if active else silo.get("total"),
            "SI-601": active["rate_img_h"] if active else None,
            "XI-601": len(batches),
            # residence time p50 (5 min) per stage; None until telemetry has samples
            "KI-201": _stage_p50(flows, "R-201", "mask"),
            "KI-601": _stage_p50(flows, "P-601", "infer"),
            "KI-401": _stage_p50(flows, "R-401", "post"),
        },
        "utilities": {"gpu": gpu, "comfy": comfy, "host": host_state},
        "gpu_lease": gpu_lease.current(),  # ai đang giữ phiếu GPU, None = rảnh (plan Bước 1, hộp U-901)
        **_alarm_views(alarms, now),
        "alarms_unknown": sorted(unknown),  # codes whose inputs are unknown this tick
    }


def _pending_jobs(active: Optional[Dict], ckpt: Dict) -> Optional[int]:
    """Pending jobs for the LT-102 bubble (same rule as the TK-102 level)."""
    if active:  # failed jobs left the queue too (they drained to D-901)
        t, d = active["target"], active["produced"] + (active["failed"] or 0)
    else:
        t, d = ckpt.get("total_jobs"), ckpt.get("current_index")
    return t - d if isinstance(t, int) and isinstance(d, int) else None


def _port(raw) -> int:
    """ComfyUI port from YAML; a blank or non-numeric value falls back to 8188."""
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 8188


def _stage_p50(flows: Dict, tag: str, call_kind: str) -> Optional[float]:
    """p50 in seconds (1 decimal) of ok calls of one kind at one stage."""
    ms = ((flows.get("stages") or {}).get(tag) or {}).get("p50_ms", {}).get(call_kind)
    return round(ms / 1000, 1) if ms is not None else None


def _failed_jobs(proc: Dict, ckpt: Dict) -> Optional[int]:
    """Failed jobs of this run: live telemetry counter first, checkpoint as fallback."""
    run = collector.run_for(proc["pid"], proc["start_ts"])
    ckpt_failed = ckpt.get("failed") if ckpt.get("exists") else None
    if run is None:
        return ckpt_failed
    if run.get("partial"):  # counters cover only the file tail read after a backend restart
        return max(run["failed"], ckpt_failed or 0)
    return run["failed"]


def _comfy_progress() -> Dict:
    """Phase 4 black-box view of P-601; empty (unknown) if the observer is unavailable."""
    try:
        from .plant_comfyui_progress_observer import current_progress
        return current_progress() or {}
    except Exception:
        return {}


def _alarm_views(alarms: List[Dict], now: float) -> Dict:
    """ISA-18.2 views (phase 6B): operator list with ack/shelve state, cleared-but-unacked and
    shelved lists. `alarms_all` keeps every active condition for the historian journal, so a
    shelved alarm is never journalled as cleared. Falls back to the raw list on any error."""
    try:
        from .plant_alarm_annotate import annotate_from_store  # locked read-compute-write (C2)
        views = annotate_from_store(alarms, now)
        return {"alarms": views["alarms"], "alarms_all": alarms,
                "alarms_cleared_unacked": views["cleared_unacked"], "alarms_shelved": views["shelved"]}
    except Exception:
        return {"alarms": alarms, "alarms_all": alarms, "alarms_cleared_unacked": [], "alarms_shelved": []}
