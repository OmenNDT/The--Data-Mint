"""SQLite historian: raw samples + alarm journal for the Plant HMI trend/replay UI.

Own file (never the Gradio/app DB), WAL mode. One connection per thread
(`threading.local`); schema (`CREATE ... IF NOT EXISTS`) runs on every new
connection, not behind a process flag, so a connection opened after the db file
was recreated still gets its tables. Every write swallows its own error, logged
at most once per 10 min per kind (counts what was suppressed in between).

Tables: samples(ts, tag, value) idx (tag, ts) + idx (ts) alone for prune;
alarm_journal(ts, code, tag, severity, pid, state, message). Retention 30 days,
pruned in chunks (`DELETE ... WHERE rowid IN (SELECT rowid ... LIMIT 5000)`).
"""

import logging
import math
import sqlite3
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

HISTORIAN_DIR = Path(__file__).resolve().parent / "historian"  # code-anchored, gitignored
DB_PATH = HISTORIAN_DIR / "plant-historian.sqlite"

RETENTION_S = 30 * 24 * 3600
PRUNE_CHUNK = 5000
LOG_ONCE_WINDOW_S = 600  # re-arm a muted error kind after 10 minutes
# candidate bucket widths (s): auto-step picks the smallest keeping a series <= MAX_POINTS
_STEP_CANDIDATES = (1, 5, 10, 30, 60, 300, 600, 1800, 3600, 4 * 3600, 12 * 3600, 86400)
MAX_POINTS = 500

_local = threading.local()
_log_lock = threading.Lock()
_logged_kinds: Dict[str, Dict] = {}  # kind -> {"last": ts, "suppressed": int}


def _log_once(kind: str, exc: Exception) -> None:
    now = time.time()
    with _log_lock:
        entry = _logged_kinds.get(kind)
        if entry and now - entry["last"] < LOG_ONCE_WINDOW_S:
            entry["suppressed"] += 1
            return
        suppressed = entry["suppressed"] if entry else 0
        _logged_kinds[kind] = {"last": now, "suppressed": 0}
    extra = f" ({suppressed} lỗi bị nén trong 10 phút trước đó)" if suppressed else ""
    logger.exception("plant historian %s failed%s: %s", kind, extra, exc)


def _finite(v) -> Optional[float]:
    """None stays None; a NaN/Inf float is dropped (rule L4: never persist/return one)."""
    return v if isinstance(v, (int, float)) and math.isfinite(v) else None


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS samples (ts REAL NOT NULL, tag TEXT NOT NULL, value REAL)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_samples_tag_ts ON samples (tag, ts)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_samples_ts ON samples (ts)")
    conn.execute("CREATE TABLE IF NOT EXISTS alarm_journal (ts REAL NOT NULL, code TEXT NOT NULL, "
                "tag TEXT, severity TEXT, pid INTEGER, state TEXT NOT NULL, message TEXT)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_journal_ts ON alarm_journal (ts)")
    conn.commit()


def _connect() -> sqlite3.Connection:
    HISTORIAN_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=5.0, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    _create_schema(conn)
    return conn


def get_conn() -> sqlite3.Connection:
    """One connection per thread (WAL: concurrent readers + one writer)."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = _connect()
        _local.conn = conn
    return conn


def insert_sample(ts: float, tag: str, value: float) -> None:
    if (value := _finite(value)) is None:
        return
    try:
        conn = get_conn()
        conn.execute("INSERT INTO samples (ts, tag, value) VALUES (?, ?, ?)", (ts, tag, value))
        conn.commit()
    except Exception as exc:  # disk full, locked, odd value: never crash the sampler
        _log_once("insert_sample", exc)


def insert_samples(ts: float, values: Dict[str, Optional[float]]) -> None:
    """Insert one tick of tag->value pairs; None/non-finite values are skipped."""
    rows = [(ts, tag, f) for tag, v in values.items() if (f := _finite(v)) is not None]
    if not rows:
        return
    try:
        conn = get_conn()
        conn.executemany("INSERT INTO samples (ts, tag, value) VALUES (?, ?, ?)", rows)
        conn.commit()
    except Exception as exc:
        _log_once("insert_samples", exc)


def insert_alarm_journal(ts: float, code: str, tag: Optional[str], severity: Optional[str],
                         pid: Optional[int], state: str, message: Optional[str]) -> None:
    try:
        conn = get_conn()
        conn.execute("INSERT INTO alarm_journal (ts, code, tag, severity, pid, state, message) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)", (ts, code, tag, severity, pid, state, message))
        conn.commit()
    except Exception as exc:
        _log_once("insert_alarm_journal", exc)


def latest_alarm_states() -> Dict[str, Dict]:
    """Latest raise/clear row per (code, tag, pid) key still `raised` (no later `cleared`).
    Seeds the sampler's previous-tick state after a restart. Operator rows (acked, shelved,
    unshelved) are ignored: they never change whether the condition is active."""
    try:
        conn = get_conn()
        rows = conn.execute(
            "SELECT ts, code, tag, severity, pid, state, message FROM alarm_journal "
            "WHERE state IN ('raised', 'cleared') ORDER BY ts ASC"
        ).fetchall()
    except Exception as exc:
        _log_once("latest_alarm_states", exc)
        return {}
    latest = {f"{c}|{t}|{p}": {"ts": ts, "code": c, "tag": t, "severity": s, "pid": p,
                               "state": st, "message": m} for ts, c, t, s, p, st, m in rows}
    return {k: v for k, v in latest.items() if v["state"] == "raised"}


def _auto_step(ts_from: float, ts_to: float) -> int:
    span = max(ts_to - ts_from, 1.0)
    for step in _STEP_CANDIDATES:
        if span / step <= MAX_POINTS:
            return step
    return _STEP_CANDIDATES[-1]


def query_samples(tags: Sequence[str], ts_from: float, ts_to: float,
                   step: Optional[int] = None) -> Dict:
    """`{"step": s, "series": {tag: [[ts, value], ...]}}`; `step` clamped up to the
    auto-selected minimum so a series never exceeds MAX_POINTS."""
    auto = _auto_step(ts_from, ts_to)
    step = max(step, auto) if step and step > 0 else auto
    series: Dict[str, List[List[float]]] = {}
    try:
        conn = get_conn()
        for tag in tags:
            rows = conn.execute(
                "SELECT CAST(ts / ? AS INTEGER) * ? AS bucket, AVG(value) FROM samples "
                "WHERE tag = ? AND ts >= ? AND ts <= ? GROUP BY bucket ORDER BY bucket",
                (step, step, tag, ts_from, ts_to),
            ).fetchall()
            # a pre-fix row could still hold a non-finite value: never surface one (L4)
            series[tag] = [[float(b), float(v)] for b, v in rows if v is not None and math.isfinite(v)]
    except Exception as exc:
        _log_once("query_samples", exc)
        series = {tag: [] for tag in tags}
    return {"step": step, "series": series}


def query_alarms(ts_from: float, ts_to: float, limit: int = 200) -> List[Dict]:
    """Journal entries in [ts_from, ts_to], newest first, capped at `limit`."""
    try:
        conn = get_conn()
        rows = conn.execute(
            "SELECT ts, code, tag, severity, pid, state, message FROM alarm_journal "
            "WHERE ts >= ? AND ts <= ? ORDER BY ts DESC LIMIT ?", (ts_from, ts_to, limit),
        ).fetchall()
    except Exception as exc:
        _log_once("query_alarms", exc)
        return []
    return [{"ts": r[0], "code": r[1], "tag": r[2], "severity": r[3], "pid": r[4],
             "state": r[5], "message": r[6]} for r in rows]


def prune_old(now: float = None) -> None:
    """Delete rows older than retention, in small chunks (never a long transaction).
    The `ts` index keeps each chunk's inner SELECT a range scan, not a full scan.
    Safe to call repeatedly; a partial prune just resumes next call."""
    now = time.time() if now is None else now
    cutoff = now - RETENTION_S
    try:
        conn = get_conn()
        for table, ts_col in (("samples", "ts"), ("alarm_journal", "ts")):
            while True:
                cur = conn.execute(
                    f"DELETE FROM {table} WHERE rowid IN "
                    f"(SELECT rowid FROM {table} WHERE {ts_col} < ? LIMIT ?)", (cutoff, PRUNE_CHUNK))
                conn.commit()
                if cur.rowcount < PRUNE_CHUNK:
                    break
    except Exception as exc:
        _log_once("prune_old", exc)
