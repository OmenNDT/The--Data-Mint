"""ISA-18.2 ack/shelve store for Plant HMI alarms (phase 6B): atomic JSON file, the
cross-process lock and the ack/shelve/unshelve mutations the HTTP routes call. The
per-tick decision engine (`annotate_from_store`) lives in `plant_alarm_annotate.py`
(same feature, split only to keep each file under 200 lines).

Store: `plant_hmi/control/alarm-state.json` (gitignored, same pattern as
`plant_setpoint_store.py`: tmp + fsync + os.replace, `fcntl.flock` + thread lock).

Two key shapes (rule H5): an **occurrence** key `f"{code}|{tag}|{pid}|{since}"` identifies
one annunciation episode (acks use this: a clear-then-re-raise gets a new `since`, hence a
new key, so an old ack never carries over - ISA-18.2 wants a fresh ack each annunciation).
A **point** key `f"{code}|{tag}|{pid}"` identifies the alarm *point* regardless of how many
times it chatters (shelves use this: shelving a chattering point must survive its clear/
re-raise cycles, otherwise shelving a nuisance alarm is useless).

Sections: acks (occurrence-keyed) {acked_at, acked_by, reason}; shelves (point-keyed)
{until, by, reason, minutes, code, tag, pid} (until <= now: expired, auto-dropped); last_seen
(occurrence-keyed, bounded 24h) {code, tag, severity, message, pid, since, last_seen_ts} -
remembers an occurrence that was active so a later tick can tell it cleared before anyone
acked it ("cleared_unacked"); a *shelved* occurrence never lands here (H5), so it can never
wrongly demand an ack while suppressed. active_points (point-keyed, ephemeral): {code, tag,
pid} for every point currently alarming, used only to validate a shelve request targets a
real current alarm (rule M2).
"""

import fcntl
import json
import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, List, Optional

ALARM_STATE_DIR = Path(__file__).resolve().parent / "control"  # code-anchored (rule R6)
STORE_PATH = ALARM_STATE_DIR / "alarm-state.json"
LOCK_PATH = ALARM_STATE_DIR / "alarm-state.lock"

ALLOWED_SHELVE_MINUTES = (15, 60, 480)
LAST_SEEN_TTL_S = 24 * 3600  # bounded memory for cleared-but-unacked tracking
MAX_KEY_LEN = 200
MAX_ACK_ALL_KEYS = 200

_thread_lock = threading.Lock()


class UnknownAlarmKey(Exception):
    """Raised when a client references a key that matches no current alarm (rule M2)."""


def occurrence_key(code: str, tag: Optional[str], pid: Optional[int], since: Optional[float]) -> str:
    return f"{code}|{tag}|{pid}|{since}"


def point_key(code: str, tag: Optional[str], pid: Optional[int]) -> str:
    return f"{code}|{tag}|{pid}"


def _empty_store() -> Dict:
    return {"acks": {}, "shelves": {}, "last_seen": {}, "active_points": {}}


def read_store() -> Dict:
    """Whole alarm-state store, falling back to empty sections on missing/corrupt/wrong-shaped data."""
    try:
        data = json.loads(STORE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return _empty_store()
    if not isinstance(data, dict):
        return _empty_store()
    out = _empty_store()
    for section in out:
        value = data.get(section)
        if isinstance(value, dict):
            out[section] = value
    return out


@contextmanager
def locked_store():
    """Cross-process file lock plus a same-process thread lock around one read-modify-write.
    Exported (no leading underscore): `plant_alarm_annotate.annotate_from_store` shares this
    exact lock so a snapshot-poll rewrite and an ack/shelve POST can never interleave (C2)."""
    ALARM_STATE_DIR.mkdir(parents=True, exist_ok=True)
    with _thread_lock:
        lock_fd = os.open(LOCK_PATH, os.O_CREAT | os.O_RDWR, 0o644)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)


def write_store(store: Dict) -> None:
    ALARM_STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp_path = STORE_PATH.with_suffix(".json.tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(store, ensure_ascii=False, indent=2))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, STORE_PATH)


def _is_known_occurrence(store: Dict, key: str) -> bool:
    return key in (store.get("last_seen") or {}) or key in (store.get("acks") or {})


def ack(key: str, who: str, reason: str, now: Optional[float] = None) -> Dict:
    """Acknowledge one alarm occurrence. Re-acking an already-acked key just refreshes it."""
    if len(key) > MAX_KEY_LEN:
        raise ValueError("khoá báo động quá dài")
    now = time.time() if now is None else now
    with locked_store():
        store = read_store()
        if not _is_known_occurrence(store, key):
            raise UnknownAlarmKey(key)
        entry = {"acked_at": now, "acked_by": who, "reason": reason}
        store["acks"][key] = entry
        store["last_seen"].pop(key, None)  # acked: no longer needs cleared-unacked tracking
        write_store(store)
        return entry


def ack_all(keys: List[str], who: str, reason: str, now: Optional[float] = None) -> List[str]:
    """Acks every known, not-yet-acked key in `keys` (rule "Low": skip already-acked);
    unknown/oversized keys are silently skipped rather than failing the whole batch."""
    if len(keys) > MAX_ACK_ALL_KEYS:
        raise ValueError(f"tối đa {MAX_ACK_ALL_KEYS} báo động mỗi lần xác nhận")
    now = time.time() if now is None else now
    acked: List[str] = []
    with locked_store():
        store = read_store()
        for key in keys:
            if len(key) > MAX_KEY_LEN or key in store["acks"] or not _is_known_occurrence(store, key):
                continue
            store["acks"][key] = {"acked_at": now, "acked_by": who, "reason": reason}
            store["last_seen"].pop(key, None)
            acked.append(key)
        if acked:
            write_store(store)
    return acked


def shelve(key: str, minutes: int, who: str, reason: str, now: Optional[float] = None) -> Dict:
    """Suppress alarm *point* `key` (rule H5: survives clear/re-raise) for `minutes`
    (only 15/60/480 allowed); a reason is required; `key` must be a currently alarming point."""
    if len(key) > MAX_KEY_LEN:
        raise ValueError("khoá báo động quá dài")
    if minutes not in ALLOWED_SHELVE_MINUTES:
        raise ValueError(f"thời gian tạm tắt không hợp lệ: {minutes} phút (chỉ 15/60/480)")
    if not reason or not reason.strip():
        raise ValueError("cần nhập lý do tạm tắt")
    now = time.time() if now is None else now
    with locked_store():
        store = read_store()
        point = (store.get("active_points") or {}).get(key)
        if point is None:
            raise UnknownAlarmKey(key)
        entry = {"until": now + minutes * 60, "by": who, "reason": reason, "minutes": minutes,
                 "code": point.get("code"), "tag": point.get("tag"), "pid": point.get("pid")}
        store["shelves"][key] = entry
        write_store(store)
        return entry


def unshelve(key: str) -> bool:
    with locked_store():
        store = read_store()
        if key not in store["shelves"]:
            raise UnknownAlarmKey(key)
        del store["shelves"][key]
        write_store(store)
        return True
