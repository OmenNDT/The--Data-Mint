"""Historian sampler: daemon thread that ticks the plant snapshot into SQLite.

Every `PLANT_HISTORIAN_INTERVAL_S` (default 10s): build_snapshot() -> extract tag
values -> insert one row per known tag; diff alarm keys vs previous tick, journal
raised/cleared (key shape from `AlarmOnDelay.key`: "CODE|TAG|pid"). Hourly prune.
Loop never dies: every step wrapped so one bad tick never stops future ticks.
"""

import logging
import os
import threading
import time
from typing import Dict, Optional

from . import plant_historian_store as store
from .plant_alarm_rules import AlarmOnDelay
from .plant_snapshot_builder import build_snapshot, seed_alarm_on_delay

logger = logging.getLogger(__name__)

DEFAULT_INTERVAL_S = 10
PRUNE_INTERVAL_S = 3600

# Tag catalogue: source of truth for `GET tags`/what the sampler stores (label=vi name).
TAG_CATALOGUE = [
    {"tag": "tk102_pending", "label": "Hàng đợi job", "unit": "job", "equipment": "TK-102"},
    {"tag": "tk801_produced", "label": "Ảnh đã sinh", "unit": "ảnh", "equipment": "TK-801"},
    {"tag": "xi601_batches", "label": "Số batch đang chạy", "unit": "batch", "equipment": "XI-601"},
    {"tag": "si601_img_h", "label": "Tốc độ sinh ảnh", "unit": "ảnh/giờ", "equipment": "SI-601"},
    {"tag": "ki201_s", "label": "Thời gian sinh mask", "unit": "s", "equipment": "KI-201"},
    {"tag": "ki601_s", "label": "Thời gian bơm inpaint", "unit": "s", "equipment": "KI-601"},
    {"tag": "ki401_s", "label": "Thời gian hậu xử lý", "unit": "s", "equipment": "KI-401"},
    {"tag": "d901_failed", "label": "Job lỗi", "unit": "job", "equipment": "D-901"},
    {"tag": "jobs_ok_1m", "label": "Job xong (1 phút)", "unit": "job", "equipment": "D-901"},
    {"tag": "job_errors_15m", "label": "Lỗi job (15 phút)", "unit": "lần", "equipment": "D-901"},
    {"tag": "gpu_temp_c", "label": "Nhiệt độ GPU", "unit": "°C", "equipment": "U-901"},
    {"tag": "gpu_util_pct", "label": "GPU sử dụng", "unit": "%", "equipment": "U-901"},
    {"tag": "gpu_vram_used_gib", "label": "VRAM đã dùng", "unit": "GiB", "equipment": "U-901"},
    {"tag": "comfy_up", "label": "ComfyUI hoạt động", "unit": "0/1", "equipment": "U-902"},
    {"tag": "comfy_queue", "label": "Hàng đợi ComfyUI", "unit": "job", "equipment": "U-902"},
    {"tag": "ram_avail_pct", "label": "RAM còn trống", "unit": "%", "equipment": "U-903"},
    {"tag": "swap_pages_s", "label": "Swap", "unit": "trang/s", "equipment": "U-903"},
    {"tag": "load_pct", "label": "Tải hệ thống", "unit": "%", "equipment": "U-903"},
]
TAG_NAMES = {t["tag"] for t in TAG_CATALOGUE}

_state_lock = threading.Lock()
_started = False
_previous_alarms: Dict[str, dict] = {}  # key -> alarm as last seen (cleared rows reuse it)
_last_prune = 0.0


def _num(x) -> Optional[float]:
    """Best-effort float; None stays None (unknown, never coerced to 0)."""
    try:
        return None if x is None else float(x)
    except (TypeError, ValueError):
        return None


def extract_tag_values(snapshot: Dict) -> Dict[str, Optional[float]]:
    """Pure: snapshot -> {tag: value|None}. None values are skipped by the caller."""
    instr = snapshot.get("instruments") or {}
    equip = snapshot.get("equipment") or {}
    utilities = snapshot.get("utilities") or {}
    comfy = utilities.get("comfy") or {}
    gpu = utilities.get("gpu") or {}
    host = utilities.get("host") or {}

    comfy_ok = comfy.get("ok")
    comfy_up = 1.0 if comfy_ok is True else (0.0 if comfy_ok is False else None)
    q_running, q_pending = comfy.get("queue_running"), comfy.get("queue_pending")
    comfy_queue = (q_running or 0) + (q_pending or 0) if q_running is not None or q_pending is not None else None
    vram_mib = gpu.get("vram_used_mib")

    flows = snapshot.get("flows") or {}
    jobs = flows.get("jobs") or {}
    # rule L7: an unknown telemetry state is unknown, not zero errors
    job_errors_15m = (_num(jobs.get("retry_15m") or 0) + _num(jobs.get("failed_15m") or 0)
                      if flows.get("has_telemetry") else None)

    return {
        "tk102_pending": _num(instr.get("LT-102")),
        "tk801_produced": _num(instr.get("LT-801")),
        "xi601_batches": _num(instr.get("XI-601")),
        "si601_img_h": _num(instr.get("SI-601")),
        "ki201_s": _num(instr.get("KI-201")),
        "ki601_s": _num(instr.get("KI-601")),
        "ki401_s": _num(instr.get("KI-401")),
        "d901_failed": _num((equip.get("D-901") or {}).get("level")),
        "jobs_ok_1m": _num(jobs.get("ok_1m")),
        "job_errors_15m": job_errors_15m,
        "gpu_temp_c": _num(gpu.get("temp_c")),
        "gpu_util_pct": _num(gpu.get("util_pct")),
        "gpu_vram_used_gib": round(vram_mib / 1024, 2) if vram_mib is not None else None,
        "comfy_up": comfy_up,
        "comfy_queue": _num(comfy_queue),
        "ram_avail_pct": _num(host.get("mem_avail_pct")),
        "swap_pages_s": _num(host.get("swap_pages_s")),
        "load_pct": _num(host.get("load_pct")),
    }


def _journal_alarm_diff(alarms: list, now: float, unknown: frozenset = frozenset()) -> None:
    """Diff current alarm keys against the previous tick; journal raised/cleared.
    Raise is journalled at `since` (on-delay start), not the tick that observed it;
    cleared repeats its active severity/message; unknown inputs carry it over."""
    global _previous_alarms
    current = {AlarmOnDelay.key(a): a for a in alarms}
    for key, a in _previous_alarms.items():
        if key not in current and a["code"] in unknown:
            current[key] = a
    for key in current.keys() - _previous_alarms.keys():
        a = current[key]
        store.insert_alarm_journal(a.get("since", now), a["code"], a.get("tag"), a.get("severity"),
                                    a.get("pid"), "raised", a.get("message"))
    for key in _previous_alarms.keys() - current.keys():
        a = _previous_alarms[key]
        store.insert_alarm_journal(now, a["code"], a.get("tag"), a.get("severity"),
                                    a.get("pid"), "cleared", a.get("message"))
    _previous_alarms = current


def _seed_previous_alarms() -> None:
    """Load still-`raised` alarms from the journal so a restart does not re-journal
    one that never actually cleared."""
    global _previous_alarms
    try:
        seeded = store.latest_alarm_states()
    except Exception:
        logger.exception("plant historian: seeding previous alarms from journal failed")
        return
    _previous_alarms = {
        key: {"code": row["code"], "tag": row["tag"], "severity": row["severity"],
              "pid": row["pid"], "message": row["message"]}
        for key, row in seeded.items()
    }
    seed_alarm_on_delay({key: row["ts"] for key, row in seeded.items()})


def _tick() -> None:
    """One sampling cycle; every failure stays local so the loop never dies."""
    now = time.time()
    try:
        snapshot = build_snapshot()
    except Exception:
        logger.exception("plant historian: build_snapshot failed, skipping this tick")
        return
    try:
        values = extract_tag_values(snapshot)
        store.insert_samples(now, {k: v for k, v in values.items() if k in TAG_NAMES})
    except Exception:
        logger.exception("plant historian: sample insert failed")
    try:
        _journal_alarm_diff(snapshot.get("alarms_all", snapshot.get("alarms")) or [], now,
                            frozenset(snapshot.get("alarms_unknown") or ()))
    except Exception:
        logger.exception("plant historian: alarm journal diff failed")

    global _last_prune
    if now - _last_prune > PRUNE_INTERVAL_S:
        _last_prune = now
        try:
            store.prune_old(now)
        except Exception:
            logger.exception("plant historian: prune failed")


def _interval_s() -> float:
    raw = os.getenv("PLANT_HISTORIAN_INTERVAL_S")
    if raw is None:
        return DEFAULT_INTERVAL_S
    try:
        v = float(raw)
        if v > 0:
            return v
    except (TypeError, ValueError):
        pass
    logger.warning("PLANT_HISTORIAN_INTERVAL_S=%r invalid, using default %ss", raw, DEFAULT_INTERVAL_S)
    return DEFAULT_INTERVAL_S


def _loop(interval: float) -> None:
    while True:
        try:
            _tick()
        except Exception:
            logger.exception("plant historian: tick raised unexpectedly")
        time.sleep(interval)


def start_sampler() -> None:
    """Idempotent: only the first call starts a thread."""
    global _started
    with _state_lock:
        if _started:
            return
        _started = True
    _seed_previous_alarms()
    interval = _interval_s()
    t = threading.Thread(target=_loop, args=(interval,), name="plant-historian-sampler", daemon=True)
    t.start()
    logger.info("Plant historian sampler started (interval=%ss)", interval)
