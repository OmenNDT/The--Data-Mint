"""Pure alarm logic for the Plant HMI (ISA-18.2 style): rules + on-delay debounce.

`derive_alarms(state, thresholds)` has no I/O and takes `now` from the state, so it
is unit-tested with fixed inputs. Each alarm names the discrepancy an operator must
act on; unknown readings (None) never raise an alarm.
"""

import threading
from typing import Dict, List, Optional, Set

THRESHOLDS = {
    "wedged_s": 600,          # batch alive, no new image for 10 min
    "job_errors_15m": 3,      # retries + failed jobs in 15 min
    "comfy_stalled_s": 120,   # ComfyUI executing our prompt without any progress message
                              # (cold load of checkpoint + LoRA + VAE decode can take > 60 s)
    "gpu_hot_c": 85,          # matches thermal.max_temp_celsius in batch-config
    "mem_low_pct": 10,        # MemAvailable below 10 %
    "swap_thrash_pages_s": 1000,
}

ON_DELAY_S = {
    "COMFY_DOWN": 15,
    "STALE_CHECKPOINT": 60,
    "GPU_HOT": 30,
    "SWAP_THRASH": 10,
    "PUMP_WEDGED": 0,         # the wedged window already is the delay
    "MEM_LOW": 0,
    "COMFY_HOST_NOT_LOCAL": 0,
    "THERMAL_HOLD": 0,
    "JOB_ERRORS": 0,
    "COMFY_STALLED": 0,       # the stalled window already is the delay
}


def _alarm(code: str, tag: str, severity: str, message: str, pid: Optional[int] = None) -> Dict:
    return {"code": code, "tag": tag, "severity": severity, "message": message, "pid": pid}


def derive_alarms(state: Dict, th: Dict = THRESHOLDS) -> List[Dict]:
    """Conditions present right now (before on-delay).

    state keys: now, batches[{pid, start_ts, newest_image_ts}], comfy{ok,url},
    gpu{temp_c}, host{mem_avail_pct, swap_pages_s}, idle_checkpoint{exists,
    current_index, total_jobs}.
    """
    now = state["now"]
    batches = state.get("batches") or []
    out: List[Dict] = []

    comfy = state.get("comfy") or {}
    flows = state.get("flows") or {}
    if comfy.get("ok") is False:
        severity = "HI" if batches else "LO"
        procs = comfy.get("procs")
        if procs:  # process alive, HTTP silent: listening elsewhere or hung
            p = procs[0]
            why = (f"ComfyUI đang chạy (pid {p['pid']}, nghe {p['listen']}:{p['port']}) "
                   f"nhưng không trả lời tại {comfy.get('url', '')}")
        elif procs is not None:
            why = f"ComfyUI chưa chạy trên máy này ({comfy.get('url', '')})"
        else:
            why = f"ComfyUI {comfy.get('url', '')} không phản hồi"
        out.append(_alarm("COMFY_DOWN", "U-902", severity,
                          why + (", batch đang chạy" if batches else "")))
    if comfy.get("host_local") is False:
        out.append(_alarm("COMFY_HOST_NOT_LOCAL", "U-902", "LO",
                          f"Config trỏ ComfyUI tới {comfy.get('host')}, không phải địa chỉ của máy này "
                          "(ComfyUI chạy chung máy): đặt comfyui.host = 127.0.0.1"))

    prog = state.get("comfy_progress") or {}
    last = prog.get("last_event_ts")
    if prog.get("connected") and prog.get("phase") == "executing" and last and now - last > th["comfy_stalled_s"]:
        node = prog.get("node_title") or prog.get("node_class") or prog.get("node") or "?"
        # loading models / before the first sampler step is slow but usually not stuck: LO
        loading = not prog.get("step_seen") or "load" in str(prog.get("node_class") or "").lower()
        out.append(_alarm("COMFY_STALLED", "P-601", "LO" if loading else "HI",
                          f"ComfyUI {int(now - last)} s không báo tiến độ ở node {node}: xem log tdm-comfyui "
                          "và GPU; kẹt tiếp thì huỷ prompt trong ComfyUI"))
    if flows.get("thermal_hold"):
        out.append(_alarm("THERMAL_HOLD", "U-901", "LO", "Batch tạm dừng chờ GPU nguội"))
    jobs = flows.get("jobs") or {}
    bad = jobs.get("retry_15m", 0) + jobs.get("failed_15m", 0)
    if flows.get("has_telemetry") and bad >= th["job_errors_15m"]:
        out.append(_alarm("JOB_ERRORS", "D-901", "HI" if jobs.get("failed_15m") else "LO",
                          f"{jobs.get('retry_15m', 0)} lần thử lại, {jobs.get('failed_15m', 0)} job hỏng trong 15 phút"))

    for b in batches:
        if b.get("silo_known") is False or flows.get("thermal_hold"):
            continue  # unreadable output dir, or a deliberate cooling pause: not a wedge
        # a cooling pause is not a wedge: count idle time from the end of the last hold
        last_output = max(b.get("newest_image_ts") or 0, b["start_ts"],
                          flows.get("last_thermal_exit_ts") or 0)
        idle_s = now - last_output
        if idle_s > th["wedged_s"]:
            out.append(_alarm("PUMP_WEDGED", "P-601", "HI",
                              f"Batch pid {b['pid']} không ra ảnh mới trong {int(idle_s // 60)} phút",
                              pid=b["pid"]))

    ckpt = state.get("idle_checkpoint") or {}
    if not batches and ckpt.get("exists"):
        idx, total = ckpt.get("current_index"), ckpt.get("total_jobs")
        if isinstance(idx, int) and isinstance(total, int) and idx < total:
            out.append(_alarm("STALE_CHECKPOINT", "TK-102", "LO",
                              f"Checkpoint dừng ở {idx}/{total} job, không có tiến trình batch nào"))

    temp = (state.get("gpu") or {}).get("temp_c")
    if temp is not None and temp >= th["gpu_hot_c"]:
        out.append(_alarm("GPU_HOT", "U-901", "HI", f"GPU cục bộ {temp:.0f}°C"))

    host = state.get("host") or {}
    avail = host.get("mem_avail_pct")
    if avail is not None and avail < th["mem_low_pct"]:
        out.append(_alarm("MEM_LOW", "U-903", "HI", f"RAM còn trống {avail:.1f}%"))
    swap = host.get("swap_pages_s")
    if swap is not None and swap > th["swap_thrash_pages_s"]:
        out.append(_alarm("SWAP_THRASH", "U-903", "HI", f"Swap {swap:.0f} trang/s"))

    return out


def unknown_codes(state: Dict) -> Set[str]:
    """Codes whose inputs are unknown this tick: their on-delay timers are held,
    not reset, so one missed reading does not restart a 30 s delay."""
    host = state.get("host") or {}
    out = set()
    if (state.get("comfy") or {}).get("ok") is None:
        out.add("COMFY_DOWN")
    if (state.get("gpu") or {}).get("temp_c") is None:
        out.add("GPU_HOT")
    if host.get("mem_avail_pct") is None:
        out.add("MEM_LOW")
    if host.get("swap_pages_s") is None:
        out.add("SWAP_THRASH")
    if any(b.get("silo_known") is False for b in state.get("batches") or []):
        out.add("PUMP_WEDGED")
    if not (state.get("comfy_progress") or {}).get("connected"):
        out.add("COMFY_STALLED")
    if (state.get("comfy") or {}).get("host_local") is None:
        out.add("COMFY_HOST_NOT_LOCAL")
    if not (state.get("flows") or {}).get("has_telemetry"):
        out.update({"JOB_ERRORS", "THERMAL_HOLD"})
    return out


class AlarmOnDelay:
    """A condition must persist its on-delay before annunciation.

    Process-wide state: the condition belongs to the plant, so every viewer sees the
    same `since`. A cleared condition is forgotten, so it restarts its delay if it
    comes back.
    """

    def __init__(self, delays: Dict[str, float] = ON_DELAY_S):
        self._delays = delays
        self._first: Dict[str, float] = {}
        self._lock = threading.Lock()

    @staticmethod
    def key(cond: Dict) -> str:
        return f"{cond['code']}|{cond['tag']}|{cond.get('pid')}"

    def seed(self, first_seen: Dict[str, float]) -> None:
        """Restore first-seen times after a restart (from the alarm journal), so an alarm
        still present re-annunciates at once with its original `since`."""
        with self._lock:
            for key, ts in first_seen.items():
                self._first.setdefault(key, ts)

    def apply(self, conditions: List[Dict], now: float, hold: Set[str] = frozenset()) -> List[Dict]:
        """`hold`: codes with unknown inputs this tick; their running timers survive."""
        keyed = {self.key(c): c for c in conditions}
        with self._lock:
            kept = {k: t for k, t in self._first.items() if k.split("|", 1)[0] in hold}
            self._first = {**kept, **{k: self._first.get(k, now) for k in keyed}}
            first = dict(self._first)
        return [{**c, "since": first[k]} for k, c in keyed.items()
                if now - first[k] >= self._delays.get(c["code"], 0)]
