"""One output folder per HMI-started run, inside the main silo `output/synthetic/`.

A start never writes into an existing dataset: it copies the selected config to
`config/_generated/runs/<run>.yaml` with every path pointed at a fresh folder
`output/synthetic/<YYYY-MM-DD_HHMMSS>_<config stem>/` (images, checkpoint, logs).
A resume reuses the newest unfinished run of the same config, so the checkpoint and
images continue in place. Post-processing then takes `--synthetic-dir <that folder>`.
"""

import re
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

import yaml

from . import plant_production_readers as production

RUNS_ROOT = (production.PIPELINE_DIR.parent / "output" / "synthetic").resolve()
RUN_CONFIG_DIR = production.PIPELINE_DIR / "config" / "_generated" / "runs"
RUN_MARKER = "plant_hmi_run"   # extra top-level YAML key; the batch pipeline ignores it


def _stem(config_name: str) -> str:
    """Folder-safe short name of the selected config (e.g. `lack-of-fusion-100`)."""
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", Path(config_name).stem).strip("-.") or "config"


def new_run(config_path: Path, config_name: str, now: Optional[float] = None) -> Tuple[Path, Path]:
    """Write a run config for a fresh start; returns (run config path, run output folder)."""
    now = now or time.time()
    base = yaml.safe_load(Path(config_path).read_text()) or {}
    run_name = f"{time.strftime('%Y-%m-%d_%H%M%S', time.localtime(now))}_{_stem(config_name)}"
    run_dir = RUNS_ROOT / run_name
    paths = dict(production.section(base, "paths"))
    paths.update(output_base_dir=str(run_dir), checkpoint_dir=str(run_dir / "checkpoints"),
                 logs_dir=str(run_dir / "logs"))
    base["paths"] = paths
    base[RUN_MARKER] = {"source_config": config_name, "created": now, "run_dir": str(run_dir)}
    RUN_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    run_cfg = RUN_CONFIG_DIR / f"{run_name}.yaml"
    tmp = run_cfg.with_suffix(".tmp")
    tmp.write_text(yaml.safe_dump(base, allow_unicode=True, sort_keys=False))
    tmp.replace(run_cfg)
    return run_cfg, run_dir


def _runs_of(config_name: str):
    """Run configs created from `config_name`, newest first."""
    if not RUN_CONFIG_DIR.is_dir():
        return []
    found = []
    for path in RUN_CONFIG_DIR.glob("*.yaml"):
        cfg = production.load_batch_config(str(path))
        marker = cfg.get(RUN_MARKER) if isinstance(cfg, dict) else None
        if isinstance(marker, dict) and marker.get("source_config") == config_name:
            found.append((float(marker.get("created") or 0), path, cfg))
    return [(p, c) for _, p, c in sorted(found, key=lambda r: r[0], reverse=True)]


def latest_unfinished_run(config_name: str) -> Optional[Dict]:
    """Newest run of this config whose checkpoint is incomplete, for resume; else None."""
    for path, cfg in _runs_of(config_name):
        ckpt = production.read_checkpoint(production.section(cfg, "paths").get("checkpoint_dir"))
        idx, total = ckpt.get("current_index"), ckpt.get("total_jobs")
        if ckpt.get("exists") and isinstance(idx, int) and isinstance(total, int) and idx < total:
            return {"config_path": path, "run_dir": Path(production.section(cfg, "paths")["output_base_dir"]),
                    "current_index": idx, "total": total}
    return None
