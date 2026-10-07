"""Backend collector: tails the batch processes' telemetry JSONL into memory.

Incremental per file (inode + offset + partial last line), so a poll reads only new
bytes. Flow records (enter/exit/job) go to an AGE-evicted buffer (15 min), so a burst
of fast calls cannot evict a long-running `enter`. Batch-long counters (images ok,
retries, failed) live per run (file stem) outside the buffer because a run outlasts the window.
Non-flow kinds are dropped at ingest (rule R5).
"""

import json
import os
import threading
import time
from collections import deque
from pathlib import Path
from typing import Dict, List

from .plant_telemetry_emitter import TELEMETRY_DIR

FLOW_KINDS = {"enter", "exit", "job"}
CONFIG_KIND = "config"          # phase 5 setpoint feedback (rule R5: never a flow record)
CONFIG_HEAD_BYTES = 64 << 10    # rule M4: config records sit near the start of the file
BUFFER_AGE_S = 15 * 60
BUFFER_CAP = 50_000            # memory backstop only
FIRST_READ_TAIL = 5 << 20      # a big file seen for the first time: read its last 5 MB
RETENTION_S = 7 * 24 * 3600
POLL_MIN_INTERVAL_S = 1.0


def _pid_alive(pid: int) -> bool:
    """Rule M4: config records are pruned by process liveness, not by age, so a
    long-running batch keeps its PV even past any fixed retention window."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True   # alive, just owned by another user
    except OSError:
        return False
    return True


class TelemetryCollector:
    def __init__(self, directory: Path = TELEMETRY_DIR):
        self._dir = directory
        self._files: Dict[str, Dict] = {}   # path -> {ino, off, partial}
        self._buffer: deque = deque(maxlen=BUFFER_CAP)
        self.runs: Dict[str, Dict] = {}     # run id -> batch-long counters
        self._config: Dict[int, Dict[str, Dict]] = {}  # pid -> key -> latest config record
        self._lock = threading.Lock()
        self._last_poll = 0.0
        self._last_prune = 0.0

    def poll(self) -> None:
        """Read new lines from every telemetry file (throttled, one reader at a time)."""
        with self._lock:
            now = time.time()
            if now - self._last_poll < POLL_MIN_INTERVAL_S:
                return
            self._last_poll = now
            try:
                paths = sorted(self._dir.glob("batch-*.jsonl"), key=lambda p: p.stat().st_mtime)
            except OSError:
                paths = []
            for path in paths:
                self._read_file(path)
            cutoff = now - BUFFER_AGE_S
            if self._buffer and min(e["ts"] for e in self._buffer) < cutoff:
                # files interleave, so the buffer is not strictly ts-ordered: filter, not popleft
                self._buffer = deque((e for e in self._buffer if e["ts"] >= cutoff), maxlen=BUFFER_CAP)
            if now - self._last_prune > 3600:
                self._last_prune = now
                self._prune_old_files(now)

    def _read_file(self, path: Path) -> None:
        try:
            st = path.stat()
        except OSError:
            return
        state = self._files.get(str(path))
        if state is None:
            self._scan_head_for_config(path)  # rule M4: first sight, catch the head config record
        if state is None and st.st_mtime < time.time() - BUFFER_AGE_S:
            # idle file seen for the first time (backend restart): its records would be
            # evicted at once, so skip parsing; counters then fall back to the checkpoint
            self._files[str(path)] = {"ino": st.st_ino, "off": st.st_size, "partial": b""}
            return
        if state is None or state["ino"] != st.st_ino or st.st_size < state["off"]:
            start = max(0, st.st_size - FIRST_READ_TAIL) if state is None else 0
            state = {"ino": st.st_ino, "off": start, "partial": b"", "skip_first": start > 0}
            self._files[str(path)] = state
        if st.st_size == state["off"]:
            return
        try:
            with open(path, "rb") as f:
                f.seek(state["off"])
                chunk = f.read(st.st_size - state["off"])
        except OSError:
            return
        state["off"] += len(chunk)
        data = state["partial"] + chunk
        lines = data.split(b"\n")
        state["partial"] = lines.pop()  # incomplete last line waits for the next poll
        partial_run = state.pop("skip_first", False)
        if partial_run and lines:
            lines.pop(0)                   # fragment cut by the tail offset
        for raw in lines:
            try:
                ev = json.loads(raw)
                if isinstance(ev, dict):
                    self._ingest(ev, partial_run)
            except (ValueError, TypeError, KeyError, AttributeError):
                continue                   # corrupt line: skip

    def _ingest(self, ev: Dict, partial_run: bool = False) -> None:
        if ev.get("kind") == CONFIG_KIND:
            self._ingest_config(ev)
            return  # rule R5: config records never enter the flow buffer
        if ev.get("kind") not in FLOW_KINDS or not isinstance(ev.get("ts"), (int, float)):
            return
        self._buffer.append(ev)
        run = self.runs.setdefault(str(ev.get("run")), {"ok": 0, "retry": 0, "failed": 0, "pid": ev.get("pid"),
                                                       "first_ts": ev["ts"], "batch": ev.get("batch")})
        run["last_ts"] = ev["ts"]
        if partial_run:
            run["partial"] = True          # counters only cover the file tail
        if ev["kind"] == "job" and ev.get("outcome") in ("ok", "retry", "failed"):
            run[ev["outcome"]] += 1

    def _scan_head_for_config(self, path: Path) -> None:
        """Rule M4: read the first `CONFIG_HEAD_BYTES` once, independent of the
        flow offset, so a `config` record near the start of a run is never
        missed by the idle-file skip or the big-file tail-read."""
        try:
            with open(path, "rb") as f:
                head = f.read(CONFIG_HEAD_BYTES)
        except OSError:
            return
        for raw in head.split(b"\n")[:-1]:   # drop a possibly-partial last line
            try:
                ev = json.loads(raw)
            except (ValueError, TypeError):
                continue
            if isinstance(ev, dict) and ev.get("kind") == CONFIG_KIND:
                self._ingest_config(ev)

    def _ingest_config(self, ev: Dict) -> None:
        """Keep only the newest record per (pid, key), outside the flow buffer."""
        pid, key, ts = ev.get("pid"), ev.get("key"), ev.get("ts")
        if not isinstance(pid, int) or not isinstance(key, str) or not isinstance(ts, (int, float)):
            return
        per_pid = self._config.setdefault(pid, {})
        prev = per_pid.get(key)
        if prev is None or ts >= prev.get("ts", 0):
            per_pid[key] = dict(ev)

    def config_for(self, pid: int, start_ts: float) -> Dict[str, Dict]:
        """Latest config records of the LIVE process `pid`, guarding pid reuse
        (rule R2): only records with `ts >= start_ts - 2` count. `{}` when unknown."""
        with self._lock:
            per_pid = self._config.get(pid, {})
            return {k: dict(v) for k, v in per_pid.items() if v.get("ts", 0) >= start_ts - 2}

    def _prune_old_files(self, now: float) -> None:
        for path in list(self._dir.glob("batch-*.jsonl")):
            try:
                if now - path.stat().st_mtime > RETENTION_S:
                    path.unlink()
                    self._files.pop(str(path), None)
            except OSError:
                pass
        for pid in list(self._config):        # rule M4: prune by liveness, not by age
            if not _pid_alive(pid):
                self._config.pop(pid, None)

    def run_for(self, pid: int, start_ts: float):
        """Counters of the run owned by this live process (pid-reuse safe), else None."""
        with self._lock:
            mine = [r for r in self.runs.values() if r["pid"] == pid and r["first_ts"] >= start_ts - 2]
        return dict(max(mine, key=lambda r: r["first_ts"])) if mine else None

    def events(self) -> List[Dict]:
        with self._lock:
            return list(self._buffer)

    def events_since(self, since: float, limit: int = 500) -> Dict:
        """Records newer than `since`, ts-ordered. `truncated` tells the client that older
        records were dropped (it must reset its particle state); `cursor` = max ts sent."""
        with self._lock:
            newer = sorted((e for e in self._buffer if e["ts"] > since), key=lambda e: e["ts"])
        sent = newer[-limit:]
        return {"events": sent, "truncated": len(newer) > limit,
                "cursor": sent[-1]["ts"] if sent else since}


collector = TelemetryCollector()
