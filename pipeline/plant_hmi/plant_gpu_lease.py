"""GPU lease shared by the Plant HMI batch start and the realism improvement loop
(plan `plans/261002-1006-realism-loop-safety-paired-gate/plan.md`, Bước 1): a single
file `plant_hmi/control/gpu-lease.json`, read/written under an flock so acquire and
release are atomic across processes (the HMI's FastAPI workers and the realism loop's
own `python -m realism.loop` process never share memory).

  acquire(owner, purpose, pid) -> (ok, holder)
  release(owner) -> None
  current() -> dict | None

No TTL. A lease is valid only while its holder's pid is alive AND that pid's start
time still matches the one recorded at acquire time (pid-reuse guard, same idea as
the batch-control route's own L4 stop-target check): a dead or recycled-pid holder's
lease self-expires the moment anyone reads it, so neither side needs an explicit
heartbeat or cleanup job. `acquire` succeeds when there is no valid lease, or the
valid lease already belongs to `owner` (re-acquire from the same owner refreshes the
record instead of being refused).
"""
import fcntl
import json
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Optional, Tuple

from . import plant_host_readers as host

CONTROL_DIR = Path(__file__).resolve().parent / "control"  # code-anchored (rule R6)
LEASE_PATH = CONTROL_DIR / "gpu-lease.json"
LOCK_PATH = CONTROL_DIR / "gpu-lease.lock"
PID_REUSE_SLACK_S = 2.0  # same slack as the batch-control route's own L4 pid-reuse guard


@contextmanager
def _locked():
    CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    fd = os.open(LOCK_PATH, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _read() -> Optional[Dict]:
    try:
        return json.loads(LEASE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write(record: Optional[Dict]) -> None:
    CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    if record is None:
        LEASE_PATH.unlink(missing_ok=True)
        return
    tmp = LEASE_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, LEASE_PATH)  # atomic rename: readers never see a half-written file


def _valid(record: Optional[Dict]) -> bool:
    """True only while the recorded pid is alive AND is still the same process
    that took the lease (start-time match), never merely "some pid with this
    number happens to be alive" (pid reuse)."""
    if not record:
        return False
    live_start = host.process_start_ts(record.get("pid"))
    if live_start is None:
        return False
    return abs(live_start - record.get("start_ts", float("-inf"))) <= PID_REUSE_SLACK_S


def current() -> Optional[Dict]:
    """The active lease, or None if there is none or it is stale (dead pid or a
    reused pid). A plain unlocked read is fine here: this is for display
    (permissive evaluation, snapshot) only; `acquire` re-checks under the lock."""
    record = _read()
    return record if _valid(record) else None


def acquire(owner: str, purpose: str, pid: int) -> Tuple[bool, Optional[Dict]]:
    """Take the lease for `owner`, recording `pid`'s own start time so a dead
    owner's lease self-expires (no TTL needed). Succeeds if there is no valid
    lease, or the valid lease already belongs to `owner`. Returns (True, None)
    on success; (False, holder) with the other owner's record when refused."""
    start_ts = host.process_start_ts(pid)
    if start_ts is None:
        return False, None  # pid already gone: never claim a lease with no live proof
    with _locked():
        existing = _read()
        if _valid(existing) and existing.get("owner") != owner:
            return False, existing
        _write({"owner": owner, "purpose": purpose, "pid": pid, "start_ts": start_ts, "ts": time.time()})
        return True, None


def release(owner: str) -> None:
    """No-op if the lease is already gone or belongs to someone else: a caller
    can never drop another owner's lease, including by racing its own exit."""
    with _locked():
        existing = _read()
        if existing and existing.get("owner") == owner:
            _write(None)
