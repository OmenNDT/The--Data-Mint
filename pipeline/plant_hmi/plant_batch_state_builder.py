"""Read-only state assembly for the batch control API (phase 6A): live batch rows,
permissive inputs and checkpoint summary. Split out of `plant_batch_control_routes.py`
purely to keep that file under the 200-line guideline; both change together.
"""

import logging
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

from . import plant_batch_compose as compose
from . import plant_batch_config_whitelist as whitelist
from . import plant_batch_process_ops as ops
from . import plant_batch_run_dirs as run_dirs
from . import plant_gpu_lease as gpu_lease
from . import plant_host_readers as host
from . import plant_production_readers as production
from . import plant_slow_probes as probes
from .plant_alarm_rules import THRESHOLDS

logger = logging.getLogger(__name__)

SWAP_SAMPLE_INTERVAL_S = 5.0

# Own meter, independent of the snapshot builder's, sampled by a background thread (M5):
# `SwapRateMeter.rate()` only measures the delta since its OWN last call, so reading it
# just once per GET (possibly hours apart on an idle panel) would average away a real
# thrash spike. A steady 5s heartbeat keeps the reading meaningful between GETs too.
_swap_meter = host.SwapRateMeter()


def _swap_sampler_loop() -> None:
    while True:
        try:
            _swap_meter.rate()
        except Exception:
            logger.exception("batch control swap sampler tick failed")
        time.sleep(SWAP_SAMPLE_INTERVAL_S)


def start_swap_sampler() -> None:
    """Idempotent-enough for our purposes: the route module calls this once at
    import time; a second call would start a second harmless sampler thread, so
    tests that re-import the module in one process are still safe."""
    threading.Thread(target=_swap_sampler_loop, daemon=True, name="bc-swap-sampler").start()


def live_batches() -> List[Dict]:
    procs = host.find_batch_processes()
    out = []
    for p in procs:
        unit = ops.find_unit_for_pid(p["pid"])
        config_name = None
        if p.get("config_path"):
            for row in whitelist.list_configs():
                if row["path"] == p["config_path"]:
                    config_name = row["name"]
                    break
        out.append({"pid": p["pid"], "unit": unit, "config_name": config_name,
                    "config_path": p.get("config_path"), "pilot": p.get("pilot", False),
                    "start_ts": p["start_ts"]})
    return out


def checkpoint_info(config_path) -> Optional[Dict]:
    """Checkpoint summary for the selected config (M6), only when one exists AND
    is not already complete: lets the UI default `resume` on and warn plainly
    when the operator starts fresh over it instead."""
    if not config_path:
        return None
    # runs live in their own folders now: look at the newest unfinished run of this config
    run = run_dirs.latest_unfinished_run(_config_name(config_path))
    if run is None:
        return None
    return {"current_index": run["current_index"], "total": run["total"], "run_dir": str(run["run_dir"])}


def _config_name(config_path) -> str:
    """Whitelist name (`x.yaml` or `_generated/x.yaml`) of a resolved config path."""
    p = Path(config_path)
    return f"_generated/{p.name}" if p.parent.name == "_generated" else p.name


def permissive_state(config_path) -> Dict:
    config_cfg = production.load_batch_config(str(config_path)) if config_path else {}
    config_valid = bool(production.section(config_cfg, "paths").get("output_base_dir")) if config_cfg else False
    comfy_cfg = production.section(config_cfg, "comfyui") if config_cfg else \
        production.section(production.load_batch_config(None), "comfyui")
    comfy_host = str(comfy_cfg.get("host") or "127.0.0.1")
    try:
        comfy_port = int(comfy_cfg.get("port") or 8188)
    except (TypeError, ValueError):
        comfy_port = 8188
    comfy_ok = probes.comfyui(comfy_host, comfy_port).get("ok")
    mem = host.read_meminfo()
    mem_avail_pct = mem.get("mem_avail_pct")
    mem_low = (mem_avail_pct < THRESHOLDS["mem_low_pct"]) if mem_avail_pct is not None else None
    swap_rate = _swap_meter.rate()
    swap_thrash = (swap_rate > THRESHOLDS["swap_thrash_pages_s"]) if swap_rate is not None else None
    main_silo = False
    if config_path:
        for row in whitelist.list_configs():
            if row["path"] == str(config_path):
                main_silo = row["main_silo"]
                break
    lora_missing = compose.missing_for_config(config_cfg) if config_cfg else []
    return {
        "live_batch_count": len(host.find_batch_processes()),
        "comfy_ok": comfy_ok,
        "training_pids": ops.find_training_processes(),
        "mem_low": mem_low,
        "swap_thrash": swap_thrash,
        "config_valid": config_valid,
        "main_silo": main_silo,
        "lora_missing": lora_missing,
        "gpu_lease": gpu_lease.current(),
    }
