"""History API for the Plant HMI trend/replay UI, mounted under `/plant-hmi/api/history`.

  GET tags                           tag catalogue (label/unit/equipment, Vietnamese)
  GET samples?tags=&from=&to=&step=  bucketed averages from the historian (SQLite)
  GET alarms?from=&to=&limit=        alarm journal, newest first
  GET runs                           one row/telemetry file (run), cheap aggregates only
  GET events?run=&cursor=&limit=     paged flow events of one run, ts ascending, index cursor

`runs`/`events` read the JSONL telemetry files directly, independent of the phase-2
collector's in-memory buffer, so replay works for a run finished before this backend
started. Two caches: `_runs_cache` (small aggregates only, keyed by path/size/mtime,
dropped once its file is gone) and `_events_lru` (at most 2 runs' full sorted event
lists, bounded, single-flight by lock).
"""

import json
import logging
import math
import threading
import time
from collections import OrderedDict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from . import plant_historian_store as store
from .plant_historian_sampler import TAG_CATALOGUE, TAG_NAMES
from .plant_telemetry_emitter import TELEMETRY_DIR

logger = logging.getLogger(__name__)

FLOW_KINDS = {"enter", "exit", "job"}
DEFAULT_SAMPLES_WINDOW_S = 3600
MAX_EVENTS_LIMIT = 5000
MAX_ALARMS_LIMIT = 2000
MAX_SAMPLE_TAGS = 12
EVENTS_LRU_MAX = 2

router = APIRouter(prefix="/api/history")

_runs_cache: Dict[str, Tuple[int, float, Dict]] = {}
_runs_cache_lock = threading.Lock()
_events_lru: "OrderedDict[str, Tuple[int, float, List[Dict]]]" = OrderedDict()
_events_lock = threading.Lock()  # also serves as the single-flight lock for LRU fills


def _has_non_finite(v) -> bool:
    """True if `v` (or anything nested in it) is a NaN/Inf float (rule L4)."""
    if isinstance(v, float):
        return not math.isfinite(v)
    if isinstance(v, dict):
        return any(_has_non_finite(x) for x in v.values())
    return isinstance(v, list) and any(_has_non_finite(x) for x in v)


def _parse_flow_records(path: Path) -> List[Dict]:
    """One telemetry file -> flow records (enter/exit/job, finite fields only)."""
    records: List[Dict] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    ev = json.loads(line)
                except (ValueError, TypeError):
                    continue  # corrupt/partial/blank line: skip
                if (isinstance(ev, dict) and ev.get("kind") in FLOW_KINDS
                        and isinstance(ev.get("ts"), (int, float)) and not _has_non_finite(ev)):
                    records.append(ev)
    except OSError:
        return []
    return records


def _telemetry_files() -> List[Path]:
    try:
        return sorted(TELEMETRY_DIR.glob("batch-*.jsonl"))
    except OSError:
        return []


def _run_aggregate(path: Path) -> Optional[Dict]:
    """Cheap per-run summary for `/runs`, cached by (path, size, mtime); never keeps
    the event list (rule H5)."""
    try:
        st = path.stat()
    except OSError:
        return None
    with _runs_cache_lock:
        cached = _runs_cache.get(str(path))
    if cached and cached[0] == st.st_size and cached[1] == st.st_mtime:
        return cached[2]
    if not (records := _parse_flow_records(path)):
        return None
    outcomes = [r.get("outcome") for r in records if r.get("kind") == "job"]
    agg = {"run": path.stem, "pid": records[0].get("pid"), "batch": records[0].get("batch"),
           "first_ts": min(r["ts"] for r in records), "last_ts": max(r["ts"] for r in records),
           "jobs_ok": outcomes.count("ok"), "jobs_retry": outcomes.count("retry"),
           "jobs_failed": outcomes.count("failed"), "events": len(records)}
    with _runs_cache_lock:
        _runs_cache[str(path)] = (st.st_size, st.st_mtime, agg)
    return agg


def _sorted_events_for_run(run: str) -> List[Dict]:
    """Full ts-sorted event list of one run, from a size/mtime-bounded LRU (max
    `EVENTS_LRU_MAX` runs); the lock single-flights concurrent requests for a run."""
    path = TELEMETRY_DIR / f"{Path(run).name}.jsonl"  # Path(...).name: no traversal
    try:
        st = path.stat()
    except OSError:
        with _events_lock:
            _events_lru.pop(run, None)
        return []
    with _events_lock:
        cached = _events_lru.get(run)
        if cached and cached[0] == st.st_size and cached[1] == st.st_mtime:
            _events_lru.move_to_end(run)
            return cached[2]
        records = sorted(_parse_flow_records(path), key=lambda r: r["ts"])
        _events_lru[run] = (st.st_size, st.st_mtime, records)
        _events_lru.move_to_end(run)
        while len(_events_lru) > EVENTS_LRU_MAX:
            _events_lru.popitem(last=False)
        return records


@router.get("/tags")
def tags():
    return JSONResponse(TAG_CATALOGUE)


@router.get("/samples")
def samples(tags: str, from_: Optional[float] = Query(None, alias="from"),
            to: Optional[float] = Query(None), step: Optional[int] = Query(None, ge=1)):
    # rule M6: only known tags, de-duplicated, capped (no fan-out into many full scans)
    seen = set()
    tag_list = [t for t in (s.strip() for s in tags.split(",")) if t in TAG_NAMES and not (t in seen or seen.add(t))]
    if not tag_list:
        return JSONResponse({"error": "tags rỗng hoặc không hợp lệ"}, status_code=400)
    if len(tag_list) > MAX_SAMPLE_TAGS:
        return JSONResponse({"error": f"tối đa {MAX_SAMPLE_TAGS} tag mỗi lần"}, status_code=422)
    ts_to = to if to is not None else time.time()
    ts_from = from_ if from_ is not None else ts_to - DEFAULT_SAMPLES_WINDOW_S
    if ts_from > ts_to:
        return JSONResponse({"error": "from phải <= to"}, status_code=400)
    try:
        return JSONResponse(store.query_samples(tag_list, ts_from, ts_to, step))
    except Exception:
        logger.exception("plant history samples failed")
        return JSONResponse({"error": "samples lỗi, xem log tdm-backend"}, status_code=500)


@router.get("/alarms")
def alarms(from_: Optional[float] = Query(None, alias="from"), to: Optional[float] = Query(None),
           limit: int = Query(200, ge=1, le=MAX_ALARMS_LIMIT)):
    ts_to = to if to is not None else time.time()
    ts_from = from_ if from_ is not None else 0.0
    if ts_from > ts_to:
        return JSONResponse({"error": "from phải <= to"}, status_code=400)
    try:
        return JSONResponse(store.query_alarms(ts_from, ts_to, limit))
    except Exception:
        logger.exception("plant history alarms failed")
        return JSONResponse({"error": "alarms lỗi, xem log tdm-backend"}, status_code=500)


@router.get("/runs")
def runs():
    try:
        paths = _telemetry_files()
        existing = {str(p) for p in paths}
        out = [agg for p in paths if (agg := _run_aggregate(p)) is not None]
        with _runs_cache_lock:
            for key in list(_runs_cache):
                if key not in existing:
                    _runs_cache.pop(key, None)
        out.sort(key=lambda r: r["last_ts"], reverse=True)
        return JSONResponse(out)
    except Exception:
        logger.exception("plant history runs failed")
        return JSONResponse({"error": "runs lỗi, xem log tdm-backend"}, status_code=500)


@router.get("/events")
def events(run: str, cursor: int = Query(0, ge=0),
           limit: int = Query(MAX_EVENTS_LIMIT, ge=1, le=MAX_EVENTS_LIMIT)):
    """`cursor` is an index into the run's ts-sorted event list: paging never duplicates or loops."""
    try:
        records = _sorted_events_for_run(run)
        total = len(records)
        page = records[cursor:cursor + limit]
        next_cursor = cursor + len(page) if cursor + len(page) < total else None
        return JSONResponse({"events": page, "next_cursor": next_cursor, "total": total})
    except Exception:
        logger.exception("plant history events failed")
        return JSONResponse({"error": "events lỗi, xem log tdm-backend"}, status_code=500)
