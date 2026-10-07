"""Operator tools behind two HMI buttons: where the output of each run is, and ComfyUI on/off.

- Runs: the per-run folders `output/synthetic/<YYYY-MM-DD_HHMMSS>_<config>/` made by HMI starts
  (plant_batch_run_dirs), newest first, with their image count. "Open" asks the desktop
  (`gio open`, the backend runs in the user's session with DISPLAY/DBus) to show the folder;
  only folders from that listing can be opened.
- ComfyUI: the `tdm-comfyui` systemd user unit, started with ComfyUI's own venv on
  127.0.0.1:8188 (same command as the port registry). Stopping is refused while a batch
  runs: the batch would burn its retries and fail every remaining job.
"""

import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from . import plant_host_readers as host
from .plant_batch_run_dirs import RUNS_ROOT
from .plant_production_readers import PIPELINE_DIR

COMFY_UNIT = "tdm-comfyui"
COMFY_DIR = PIPELINE_DIR.parent / "comfyui"
COMFY_PYTHON = COMFY_DIR / ".venv" / "bin" / "python"
COMFY_ARGS = ["main.py", "--listen", "127.0.0.1", "--port", "8188"]
RUN_NAME_PREFIX = "20"           # run folders start with the year: 2026-10-02_091530_<config>
IMAGE_SUFFIX = ".png"


def _count_images(run_dir: Path) -> int:
    total = 0
    for sub in run_dir.iterdir():
        if sub.is_dir() and sub.name not in ("checkpoints", "logs"):
            total += sum(1 for f in sub.iterdir()
                         if f.name.endswith(IMAGE_SUFFIX) and not f.name.endswith("_mask.png"))
    return total


def list_runs(limit: int = 8) -> List[Dict]:
    """Newest HMI run folders: name, absolute path, image count, last change."""
    try:
        dirs = [d for d in RUNS_ROOT.iterdir() if d.is_dir() and d.name.startswith(RUN_NAME_PREFIX)]
    except OSError:
        return []
    dirs.sort(key=lambda d: d.stat().st_mtime, reverse=True)
    out = []
    for d in dirs[:limit]:
        try:
            out.append({"name": d.name, "path": str(d), "images": _count_images(d),
                        "modified": d.stat().st_mtime})
        except OSError:
            continue
    return out


def resolve_run(name: str) -> Optional[Path]:
    """A run folder by name, only if it is a direct child of the silo (no traversal)."""
    if not name or "/" in name or "\0" in name or name in (".", ".."):
        return None
    path = (RUNS_ROOT / name).resolve()
    return path if path.parent == RUNS_ROOT and path.is_dir() else None


def open_folder(path: Path) -> Optional[str]:
    """Show the folder on this machine's desktop; returns an error text or None."""
    try:
        subprocess.Popen(["gio", "open", str(path)], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
        return None
    except OSError as exc:
        return f"không mở được cửa sổ thư mục: {exc}"


def _unit_active() -> bool:
    res = subprocess.run(["systemctl", "--user", "is-active", COMFY_UNIT],
                         capture_output=True, text=True, timeout=5)
    return res.stdout.strip() in ("active", "activating")


def comfy_state(http_ok: Optional[bool]) -> Dict:
    """Unit state + HTTP probe (the probe is shared with the snapshot: no extra load)."""
    try:
        active = _unit_active()
    except (OSError, subprocess.SubprocessError):
        active = None
    return {"unit": COMFY_UNIT, "unit_active": active, "http_ok": http_ok,
            "batch_running": bool(host.find_batch_processes())}


def comfy_start() -> Optional[str]:
    """Start ComfyUI as a transient user unit; returns an error text or None."""
    if _unit_active():
        return None  # already on: idempotent
    if not COMFY_PYTHON.exists():
        return f"không thấy venv của ComfyUI: {COMFY_PYTHON}"
    subprocess.run(["systemctl", "--user", "reset-failed", COMFY_UNIT],
                   capture_output=True, timeout=5)
    res = subprocess.run(
        ["systemd-run", "--user", f"--unit={COMFY_UNIT}", f"--working-directory={COMFY_DIR}",
         "--collect", str(COMFY_PYTHON), *COMFY_ARGS],
        capture_output=True, text=True, timeout=15)
    return None if res.returncode == 0 else (res.stderr.strip() or "systemd-run lỗi")[:300]


def comfy_stop() -> Optional[str]:
    """Stop ComfyUI; refused while a batch runs (it needs ComfyUI for every job)."""
    if host.find_batch_processes():
        return "đang có batch chạy: dừng batch trước rồi mới tắt ComfyUI"
    res = subprocess.run(["systemctl", "--user", "stop", COMFY_UNIT],
                         capture_output=True, text=True, timeout=60)
    return None if res.returncode == 0 else (res.stderr.strip() or "systemctl stop lỗi")[:300]

