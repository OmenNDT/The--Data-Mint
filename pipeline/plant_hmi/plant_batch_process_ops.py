"""Process-level operations for batch start/stop (phase 6A): the only module that
calls `systemd-run`/`systemctl`/`os.kill`. Every call uses an argv list, never
`shell=True` (rule: no shell injection from a config name or reason string).

Starting outside `tdm-backend`'s cgroup (rule R8) means restarting the launcher
service never SIGKILLs a batch this HMI started: `systemd-run --user` creates an
independent transient unit in the user's own scope.
"""

import fcntl
import os
import signal
import subprocess
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, List, Optional

from . import plant_host_readers as host
from . import plant_production_readers as production
from .plant_batch_training_scan import find_training_processes  # noqa: F401 (re-exported)

BATCH_MANAGER_DIR = production.PIPELINE_DIR / "batch_manager"
VENV_PYTHON = production.PIPELINE_DIR / ".venv" / "bin" / "python3"
START_WAIT_S = 5.0          # unit active poll window
VISIBLE_WAIT_S = 3.0        # extra window to see the pid itself in /proc (closes H2's TOCTOU)
START_POLL_INTERVAL_S = 0.3

CONTROL_DIR = Path(__file__).resolve().parent / "control"  # code-anchored (rule R6)
START_LOCK_PATH = CONTROL_DIR / "batch-start.lock"
# Serialises start attempts process-wide (threading.Lock: FastAPI's sync routes run in a
# threadpool) AND across processes (fcntl.flock: a second launcher/process on this host),
# held from the permissive re-check through to the new pid being visible (rule H2).
_start_thread_lock = threading.Lock()


@contextmanager
def start_lock():
    CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    with _start_thread_lock:
        fd = os.open(START_LOCK_PATH, os.O_CREAT | os.O_RDWR, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)


def _unit_name(now: Optional[float] = None) -> str:
    return "tdm-batch-" + time.strftime("%y%m%d-%H%M%S", time.localtime(now or time.time()))


def build_start_argv(config_path: Path, pilot: bool, resume: bool, unit: str) -> List[str]:
    """Argv for `systemd-run --user`; working directory is `pipeline/` so the
    script's own relative defaults and `sys.path.insert` keep working.

    `KillSignal=SIGINT` + `TimeoutStopSec=120` (H3): the batch only handles
    `KeyboardInterrupt` (SIGINT), not SIGTERM (systemd's own default), so a plain
    stop would kill it without running any of its interrupt handling; 120s gives
    it room to finish the image in flight before systemd escalates to SIGKILL.
    `--service-type=exec` (M7): `Type=simple` (the default) reports "active" right
    after fork, before exec, so a bad venv path or an instant crash would still
    look like success; `exec` waits for the exec() itself to succeed.
    `--collect` (M7): a failed transient unit is unloaded instead of lingering.
    `--expand-environment=no` (L2): a config path containing `$` must be passed
    through literally, never expanded as a systemd specifier/variable."""
    argv = [
        "systemd-run", "--user", f"--unit={unit}",
        f"--working-directory={BATCH_MANAGER_DIR.parent}",
        "--service-type=exec", "--collect", "--expand-environment=no",
        "-p", "KillSignal=SIGINT", "-p", "TimeoutStopSec=120",
        str(VENV_PYTHON), "batch_manager/batch-production-main.py",
        "--config", str(config_path),
    ]
    if pilot:
        argv.append("--pilot")
    if resume:
        argv.append("--resume")
    return argv


def is_unit_active(unit: str) -> Optional[bool]:
    """True/False, or None if `systemctl` itself could not answer (treated as
    unknown, never as a silent success)."""
    try:
        out = subprocess.run(["systemctl", "--user", "is-active", unit],
                              capture_output=True, text=True, timeout=4)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() == "active"


def start_batch(config_path: Path, pilot: bool, resume: bool) -> Dict:
    """Launch the batch via `systemd-run --user`, poll (<=5s) until the unit is
    active, then confirm the pid itself is visible to `find_batch_processes()`
    (<=3s more). That second wait is what actually closes the H2 race: the
    caller holds `start_lock()` for the whole call, so a concurrent start's
    `NO_LIVE_BATCH` re-check (which also calls `find_batch_processes()`) is
    guaranteed to see this pid once this function returns.
    Returns {ok, unit, pid, error}; `pid` is the live batch pid once visible
    (needed by the caller to take the GPU lease, plan Bước 1), None otherwise;
    `error` set only when `ok` is False."""
    unit = _unit_name()
    started_at = time.time()
    argv = build_start_argv(config_path, pilot, resume, unit)
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"ok": False, "unit": unit, "pid": None, "error": f"systemd-run lỗi: {exc}"}
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()[:400]
        return {"ok": False, "unit": unit, "pid": None, "error": f"systemd-run thất bại: {detail or 'không rõ lỗi'}"}

    deadline = time.monotonic() + START_WAIT_S
    active = is_unit_active(unit)
    while active is not True and time.monotonic() < deadline:
        time.sleep(START_POLL_INTERVAL_S)
        active = is_unit_active(unit)
    if active is not True:
        return {"ok": False, "unit": unit, "pid": None,
                "error": "unit không chuyển sang active trong 5s, xem `systemctl --user status "
                         f"{unit}` và log tdm-backend"}

    visible_deadline = time.monotonic() + VISIBLE_WAIT_S
    config_str = str(config_path)
    while time.monotonic() < visible_deadline:
        match = next((p for p in host.find_batch_processes()
                      if p.get("config_path") == config_str and p["start_ts"] >= started_at - 2), None)
        if match is not None:
            return {"ok": True, "unit": unit, "pid": match["pid"], "error": None}
        time.sleep(START_POLL_INTERVAL_S)
    return {"ok": False, "unit": unit, "pid": None,
            "error": "unit active nhưng chưa thấy tiến trình batch trong /proc, xem `systemctl "
                     f"--user status {unit}` và log tdm-backend"}


def find_unit_for_pid(pid: int) -> Optional[str]:
    """`tdm-batch-*` unit owning this pid, read from its cgroup path (no I/O
    beyond one file read; never guesses from the pid's start time)."""
    try:
        cgroup = Path(f"/proc/{pid}/cgroup").read_text()
    except OSError:
        return None
    for segment in cgroup.replace("\n", "/").split("/"):
        if segment.startswith("tdm-batch-") and segment.endswith(".service"):
            return segment[:-len(".service")]
    return None


def stop_batch(pid: int, live_pids: List[int]) -> Dict:
    """Stop a live batch: prefer `systemctl --user stop <unit>` (unit started with
    `KillSignal=SIGINT`, see `build_start_argv`) for a systemd-run job, otherwise
    SIGINT the pid directly. Refuses any pid not already reported by
    `find_batch_processes()` (`live_pids`), so this can never signal an unrelated
    process.

    SIGINT (not SIGTERM, H3): the batch script only catches `KeyboardInterrupt`
    (raised by SIGINT); Python's default SIGTERM disposition terminates the
    interpreter immediately with no exception at all, mid-write of whatever file
    is open. SIGINT at least lets the current job finish its `except Exception`
    cleanup and reach the next loop iteration instead of dying mid-write. It does
    NOT by itself guarantee an up-to-date checkpoint: `batch-production-main.py`
    only writes one every `checkpoint_interval` images plus one "final" write
    after its main loop returns normally; `KeyboardInterrupt` raised inside that
    loop propagates past the final-checkpoint write, so progress since the last
    periodic checkpoint is still lost either way (see phase-6A report to main)."""
    if pid not in live_pids:
        return {"ok": False, "unit": None, "error": f"pid {pid} không phải batch đang sống"}
    unit = find_unit_for_pid(pid)
    if unit:
        try:
            out = subprocess.run(["systemctl", "--user", "stop", unit],
                                  capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.SubprocessError) as exc:
            return {"ok": False, "unit": unit, "error": f"systemctl stop lỗi: {exc}"}
        if out.returncode != 0:
            detail = (out.stderr or out.stdout or "").strip()[:400]
            return {"ok": False, "unit": unit, "error": f"systemctl stop thất bại: {detail or 'không rõ lỗi'}"}
        return {"ok": True, "unit": unit, "error": None}
    try:
        os.kill(pid, signal.SIGINT)  # not SIGTERM: see docstring above (H3)
    except ProcessLookupError:
        return {"ok": True, "unit": None, "error": None}  # already gone
    except OSError as exc:
        return {"ok": False, "unit": None, "error": f"kill lỗi: {exc}"}
    return {"ok": True, "unit": None, "error": None}
