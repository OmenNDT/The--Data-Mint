"""Pure flow metrics from telemetry records (no I/O; unit-tested with a fixed `now`).

`compute_flows(events, alive, now)`:
  running    calls entered but not exited, only for live processes (a dead pid leaves
             no ghost) and only records newer than that process start (pid reuse)
  stages     per tag: running count, p50 duration per call kind over 5 min (ok calls),
             errors in 5 min
  jobs       images ok in 1 / 10 min, retries and failed jobs in 15 min
  thermal    True while the batch waits for the GPU to cool (U-901 thermal_hold)
"""

from statistics import median
from typing import Dict, List


def _p50(values: List[float]):
    return round(median(values)) if values else None


def compute_flows(events: List[Dict], alive: Dict[int, float], now: float) -> Dict:
    """alive: {pid: process start epoch} of live batch processes."""
    def owned(ev):  # record belongs to a live process's current run
        start = alive.get(ev.get("pid"))
        return start is not None and ev["ts"] >= start - 2

    entered: Dict[str, Dict] = {}
    exited = set()
    durations: Dict[tuple, List[float]] = {}
    errors: Dict[str, int] = {}
    jobs = {"ok_1m": 0, "ok_10m": 0, "retry_15m": 0, "failed_15m": 0}

    last_thermal_exit = None
    for ev in events:
        if not owned(ev):
            continue  # only the live runs count (a killed run's errors must not alarm the next)
        kind = ev.get("kind")
        if kind == "enter" and ev.get("call"):
            entered[ev["call"]] = ev
        elif kind == "exit" and ev.get("call"):
            exited.add(ev["call"])
            if ev.get("call_kind") == "thermal_hold":
                last_thermal_exit = max(last_thermal_exit or 0, ev["ts"])
            if ev["ts"] >= now - 300:
                if ev.get("ok"):
                    durations.setdefault((ev.get("tag"), ev.get("call_kind")), []).append(ev.get("dur_ms") or 0)
                else:
                    errors[ev.get("tag")] = errors.get(ev.get("tag"), 0) + 1
        elif kind == "job":
            age = now - ev["ts"]
            outcome = ev.get("outcome")
            if outcome == "ok":
                jobs["ok_1m"] += age <= 60
                jobs["ok_10m"] += age <= 600
            elif outcome in ("retry", "failed") and age <= 900:
                jobs[f"{outcome}_15m"] += 1

    running = [
        {"call": c, "tag": ev.get("tag"), "call_kind": ev.get("call_kind"), "since": ev["ts"],
         "job": ev.get("job"), "defect": ev.get("defect"), "pid": ev.get("pid")}
        for c, ev in entered.items() if c not in exited
    ]

    stages: Dict[str, Dict] = {}
    for (tag, call_kind), values in durations.items():
        stages.setdefault(tag, {"running": 0, "p50_ms": {}, "errors_5m": 0})["p50_ms"][call_kind] = _p50(values)
    for tag, count in errors.items():
        stages.setdefault(tag, {"running": 0, "p50_ms": {}, "errors_5m": 0})["errors_5m"] = count
    for call in running:
        stages.setdefault(call["tag"], {"running": 0, "p50_ms": {}, "errors_5m": 0})["running"] += 1

    return {
        "running": running,
        "stages": stages,
        "jobs": jobs,
        "thermal_hold": any(c["tag"] == "U-901" and c["call_kind"] == "thermal_hold" for c in running),
        "has_telemetry": any(owned(ev) for ev in events),
        "last_thermal_exit_ts": last_thermal_exit,
    }
