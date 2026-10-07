"""Persistence primitives for the setpoint store (phase 5): atomic JSON file, append-only
audit log, and the lock that serialises a read-modify-write cycle. Split out of
`plant_setpoints.py` (which owns the registry/validation/resolve logic) purely to keep
each file small; both are part of the same feature and change together.

Paths anchored to this file's directory (rule R6): safe regardless of the caller's cwd
(Gradio launcher, CLI, systemd-run, tests).
"""

import fcntl
import json
import logging
import os
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)

SETPOINTS_DIR = Path(__file__).resolve().parent / "setpoints"  # code-anchored (rule R6)
STORE_PATH = SETPOINTS_DIR / "setpoints.json"
AUDIT_PATH = SETPOINTS_DIR / "setpoints-audit.jsonl"
LOCK_PATH = SETPOINTS_DIR / "setpoints.lock"

# One process-wide lock: fcntl.flock only serialises across processes, not threads
# of the same process, so both are needed for a safe read-modify-write cycle.
_thread_lock = threading.Lock()


def read_store() -> Dict:
    """Whole setpoint store, `{}` when missing, corrupt or wrong-shaped."""
    try:
        data = json.loads(STORE_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def read_audit(limit: int = 50) -> List[Dict]:
    """Newest-first audit entries, tolerant of corrupt/partial lines."""
    try:
        lines = AUDIT_PATH.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out: List[Dict] = []
    for raw in reversed(lines):
        try:
            ev = json.loads(raw)
        except ValueError:
            continue
        if isinstance(ev, dict):
            out.append(ev)
        if len(out) >= limit:
            break
    return out


@contextmanager
def locked_store():
    """Cross-process file lock (`fcntl.flock`) plus a same-process thread lock: a
    safe read-modify-write cycle for the store, held for the whole of one PUT/DELETE."""
    SETPOINTS_DIR.mkdir(parents=True, exist_ok=True)
    with _thread_lock:
        lock_fd = os.open(LOCK_PATH, os.O_CREAT | os.O_RDWR, 0o644)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)


def write_store_and_audit(store: Dict, audit_event: Dict) -> None:
    """Atomic store write (tmp + fsync + os.replace), then an append-only audit line.

    Rule L3: the store write is the actual state change and must propagate any
    error; a failure to append the audit line afterwards must NOT undo or fail the
    request (the store already reflects the new value) — it is logged instead.
    """
    tmp_path = STORE_PATH.with_suffix(".json.tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(store, ensure_ascii=False, indent=2))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, STORE_PATH)

    try:
        audit_line = json.dumps(audit_event, ensure_ascii=False) + "\n"
        audit_fd = os.open(AUDIT_PATH, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        try:
            os.write(audit_fd, audit_line.encode("utf-8"))
        finally:
            os.close(audit_fd)
    except OSError:
        logger.exception("plant setpoint audit append failed (store already updated): %s", audit_event)
