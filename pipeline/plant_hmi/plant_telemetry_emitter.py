"""In-process telemetry emitter for the batch-production process (Plant HMI phase 2).

The batch process calls `enable(batch_id)` once; nothing else in the code base emits.
Every record is one JSON line written with a single `os.write` on an O_APPEND fd, to
`plant_hmi/telemetry/batch-<pid>-<start>.jsonl` (start time in the name: a recycled
pid never appends to an old run's file). Telemetry never breaks a job (rule R4):
every emit swallows its own errors, and a wrapped function's result or exception
passes through untouched. `PLANT_TELEMETRY=0` returns the original functions.

Records:
  {"kind": "enter"|"exit", "tag", "call_kind", "call", "job", "defect", "ok", "err", "dur_ms"}
  {"kind": "job", "job", "defect", "outcome": "ok"|"retry"|"failed", "err"}
"""

import functools
import itertools
import json
import os
import time
from pathlib import Path

TELEMETRY_DIR = Path(__file__).resolve().parent / "telemetry"  # code-anchored (rule R6)

_fd = None
_run = None
_enabled = False
_batch = None
_seq = itertools.count(1)
_job = {"job": None, "defect": None}  # current job context (the loop is sequential)
_last_config: dict = {}   # key -> last record passed to emit_config (rule M4: re-emit source)
_ok_count = 0             # successful jobs since the last re-emit (rule M4)
CONFIG_REEMIT_EVERY = 50  # re-emit so PV survives a backend restart or the 24h config prune


def enable(batch_id: str) -> bool:
    """Turn emission on for this process. Returns False when the kill switch is set."""
    global _enabled, _batch
    if os.getenv("PLANT_TELEMETRY", "1") == "0":
        return False
    _enabled, _batch = True, batch_id
    return True


def emit(record: dict) -> None:
    global _fd, _run
    if not _enabled:
        return
    try:
        if _fd is None:
            TELEMETRY_DIR.mkdir(parents=True, exist_ok=True)
            _run = f"batch-{os.getpid()}-{int(time.time())}"
            _fd = os.open(TELEMETRY_DIR / f"{_run}.jsonl",
                          os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        line = {"ts": time.time(), "pid": os.getpid(), "run": _run, "batch": _batch, **_job, **record}
        os.write(_fd, (json.dumps(line, ensure_ascii=False, default=str) + "\n").encode())
    except Exception:
        pass  # disk full, permission, odd value: never fail the batch


def emit_config(record: dict) -> None:
    """Emit one `kind=config` record (phase 5, rule R2): the value a component
    actually loaded plus its source, e.g. `{"key": "sampler_steps", "value": 25,
    "source": "setpoint"}`. Tagged SP-601 (KSampler steps). Same safety rules as
    `emit`: never raises, no-op unless `enable()` was called; config records must
    never break the job. Cached by `key` so `job_outcome()` can re-emit it
    periodically (rule M4: PV must survive a backend restart, which only tails
    the last 5 MB of a big file, and the collector's 24h config-age prune)."""
    try:
        payload = {"kind": "config", "tag": "SP-601"}
        payload.update(record)
        key = record.get("key") if isinstance(record, dict) else None
        if isinstance(key, str):
            _last_config[key] = dict(payload)
    except Exception:
        return
    emit(payload)


def set_job(job_id, defect) -> None:
    """Context stamped on every following record until the next job starts."""
    try:
        _job["job"], _job["defect"] = int(job_id), str(defect)
    except Exception:
        _job["job"], _job["defect"] = None, None


def job_outcome(outcome: str, err: BaseException = None) -> None:
    """ok = image saved; retry = attempt failed, will retry; failed = retries exhausted."""
    global _ok_count
    emit({"kind": "job", "outcome": outcome,
          "err": f"{type(err).__name__}: {err}"[:200] if err is not None else None})
    if outcome != "ok":
        return
    try:
        _ok_count += 1
        if _ok_count >= CONFIG_REEMIT_EVERY:
            _ok_count = 0
            for cached in list(_last_config.values()):
                emit(cached)
    except Exception:
        pass  # rule R4: a re-emit hiccup must never affect the job outcome itself


def instrument(fn, tag: str, call_kind: str):
    """Wrap a callable so each call emits enter/exit records under `tag`."""
    if os.getenv("PLANT_TELEMETRY", "1") == "0":
        return fn

    @functools.wraps(fn)
    def wrapped(*args, **kwargs):
        call = f"{os.getpid()}-{next(_seq)}"
        emit({"kind": "enter", "tag": tag, "call_kind": call_kind, "call": call})
        t0 = time.monotonic()
        try:
            result = fn(*args, **kwargs)
        except BaseException as exc:
            emit({"kind": "exit", "tag": tag, "call_kind": call_kind, "call": call, "ok": False,
                  "err": type(exc).__name__, "dur_ms": round((time.monotonic() - t0) * 1000)})
            raise
        emit({"kind": "exit", "tag": tag, "call_kind": call_kind, "call": call, "ok": True,
              "dur_ms": round((time.monotonic() - t0) * 1000)})
        return result

    return wrapped
