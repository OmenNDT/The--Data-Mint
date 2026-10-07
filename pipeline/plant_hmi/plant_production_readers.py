"""Production-state readers: batch configs, image silo counts, checkpoints.

Levels come from real sources only: PNG files on disk (images actually produced)
and the checkpoint JSON (failed jobs, resume position). Directory scans are cached
for a few seconds so several browser tabs polling at once cost one scan.
"""

import json
import os
import threading
import time
from pathlib import Path
from typing import Dict, Optional

import yaml

PIPELINE_DIR = Path(__file__).resolve().parent.parent  # anchor to code dir (rule R6)
BASE_CONFIG_PATH = PIPELINE_DIR / "config" / "batch-config.yaml"
IMAGE_EXTS = (".png", ".jpg", ".jpeg")

MAX_CONFIG_BYTES = 1 << 20        # a batch YAML is a few KB
MAX_CHECKPOINT_BYTES = 300 << 20  # ~100k jobs; beyond that report unknown

_cache: Dict[tuple, tuple] = {}  # key -> (expires_at, value)
_cache_lock = threading.Lock()
_key_locks: Dict[tuple, threading.Lock] = {}


def _cached(key: tuple, ttl: float, fn):
    """TTL cache shared by all request threads, single-flight per key:
    concurrent callers wait for one computation instead of stampeding the disk."""
    with _cache_lock:
        hit = _cache.get(key)
        if hit and hit[0] > time.time():
            return hit[1]
        key_lock = _key_locks.setdefault(key, threading.Lock())
    with key_lock:
        with _cache_lock:
            hit = _cache.get(key)
            if hit and hit[0] > time.time():
                return hit[1]
        value = fn()
        with _cache_lock:
            _cache[key] = (time.time() + ttl, value)
        return value


def section(cfg: Dict, name: str) -> Dict:
    """cfg[name] as a dict, tolerating empty (`paths:`) or wrong-typed YAML sections."""
    value = cfg.get(name) if isinstance(cfg, dict) else None
    return value if isinstance(value, dict) else {}


def load_batch_config(path: Optional[str]) -> Dict:
    """Load a batch YAML config; empty dict when missing or unreadable."""
    target = Path(path) if path else BASE_CONFIG_PATH

    def _load():
        try:
            # is_file + size cap: argv of any same-user process picks this path
            if not target.is_file() or target.stat().st_size > MAX_CONFIG_BYTES:
                return {}
            data = yaml.safe_load(target.read_text())
            return data if isinstance(data, dict) else {}
        except (OSError, yaml.YAMLError, UnicodeDecodeError):
            return {}

    return _cached(("config", str(target)), 10.0, _load)


def run_target(config: Dict, pilot: bool) -> Optional[int]:
    """Planned image count of a run (pilot = one image per active defect)."""
    gen = section(config, "generation")
    if pilot:
        active = [k for k, v in (gen.get("defect_distribution") or {}).items() if v]
        return max(len(active), 1)
    total = gen.get("total_images")
    return int(total) if isinstance(total, (int, float)) else None


def _is_image(name: str) -> bool:
    return name.lower().endswith(IMAGE_EXTS) and not name.endswith("_mask.png")


def scan_silo(output_dir: Optional[str], since_ts: float = 0.0) -> Dict:
    """Count produced images under output_dir (flat, <defect>/ or <run>/<defect>/).

    Returns total, per-defect counts, images newer than `since_ts` (this run),
    images in the last 10 minutes (rate) and the newest image mtime.
    """
    if not output_dir:
        return {"exists": False}

    def _scan():
        root = Path(output_dir)
        if not root.is_dir():
            return {"exists": False, "path": output_dir}
        now = time.time()
        stats = {"exists": True, "path": output_dir, "total": 0, "since": 0,
                 "last_10m": 0, "newest_ts": None, "by_defect": {}}

        def visit(directory: Path, bucket: str, depth: int = 0):
            # depth 0: silo root; 1: <defect>/ (old layout) or <run>/ (HMI per-run folder);
            # 2: <run>/<defect>/. Images are bucketed by the folder that holds them.
            try:
                with os.scandir(directory) as it:
                    for entry in it:
                        if entry.is_dir(follow_symlinks=False) and depth < 2 and entry.name not in (
                                "checkpoints", "logs"):
                            visit(Path(entry.path), entry.name, depth + 1)
                        elif entry.is_file() and _is_image(entry.name):
                            mtime = entry.stat().st_mtime
                            stats["total"] += 1
                            key = bucket or "(root)"
                            stats["by_defect"][key] = stats["by_defect"].get(key, 0) + 1
                            if mtime >= since_ts:
                                stats["since"] += 1
                            if mtime >= now - 600:
                                stats["last_10m"] += 1
                            if stats["newest_ts"] is None or mtime > stats["newest_ts"]:
                                stats["newest_ts"] = mtime
            except OSError:
                pass

        visit(root, "")
        return stats

    return _cached(("silo", output_dir, round(since_ts)), 4.0, _scan)


def count_backgrounds(backgrounds_dir: Optional[str]) -> Optional[int]:
    """Number of clean background patches available (TK-101 level)."""
    if not backgrounds_dir:
        return None

    def _count():
        try:
            with os.scandir(backgrounds_dir) as it:
                return sum(1 for e in it if e.is_file() and _is_image(e.name))
        except OSError:
            return None

    return _cached(("bg", backgrounds_dir), 60.0, _count)


def read_checkpoint(checkpoint_dir: Optional[str]) -> Dict:
    """Summary of batch_state.json: resume index, planned jobs, failed jobs."""
    if not checkpoint_dir:
        return {"exists": False}
    path = Path(checkpoint_dir) / "batch_state.json"
    try:
        st = path.stat()
    except OSError:
        return {"exists": False, "path": str(path)}
    if st.st_size > MAX_CHECKPOINT_BYTES:
        return {"exists": False, "path": str(path), "error": "checkpoint quá lớn"}

    def _read():
        try:
            state = json.loads(path.read_text())
        except (OSError, ValueError):
            return {"exists": False, "path": str(path)}
        if not isinstance(state, dict):
            return {"exists": False, "path": str(path)}
        jobs = state.get("jobs") if isinstance(state.get("jobs"), list) else []
        return {
            "exists": True,
            "path": str(path),
            "current_index": state.get("current_index"),
            "completed_count": state.get("completed_count"),
            "total_jobs": len(jobs),
            "failed": len(state["failed_jobs"]) if isinstance(state.get("failed_jobs"), list) else None,
            "saved_ts": state.get("checkpoint_time"),
        }

    return _cached(("ckpt", str(path), st.st_mtime_ns, st.st_size), 3600.0, _read)
