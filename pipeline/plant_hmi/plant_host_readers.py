"""Host-level readers for the Plant HMI: live batch processes, RAM/swap, load.

Read-only. Every reader tolerates missing /proc entries (process exits mid-scan)
and returns partial data instead of raising, so one bad read never breaks the
snapshot.
"""

import os
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

BATCH_SCRIPT_MARKER = "batch-production-main.py"
_CLK_TCK = os.sysconf("SC_CLK_TCK")


def _boot_time() -> float:
    """System boot time (epoch seconds) from /proc/stat `btime`."""
    try:
        for line in Path("/proc/stat").read_text().splitlines():
            if line.startswith("btime"):
                return float(line.split()[1])
    except OSError:
        pass
    return 0.0


_BTIME = _boot_time()


def process_start_ts(pid: int) -> Optional[float]:
    """Epoch start time of a pid (field 22 of /proc/<pid>/stat), None if gone."""
    try:
        raw = Path(f"/proc/{pid}/stat").read_text()
        # comm (field 2) may contain spaces: split after the closing paren
        fields = raw[raw.rindex(")") + 2:].split()
        return _BTIME + int(fields[19]) / _CLK_TCK
    except (OSError, ValueError, IndexError):
        return None


def _parse_batch_argv(argv: List[str], cwd: Optional[str]) -> Dict:
    """Extract --config path (absolute) and pilot flag from a batch command line."""
    pilot = any(a in ("--pilot", "--pilot-mode") for a in argv)
    config_path = None
    for i, arg in enumerate(argv):
        if arg == "--config" and i + 1 < len(argv):
            config_path = argv[i + 1]
        elif arg.startswith("--config="):
            config_path = arg.split("=", 1)[1]
    if config_path and not os.path.isabs(config_path):
        # relative path needs the cwd; unreadable cwd (other user) = config unknown
        config_path = os.path.normpath(os.path.join(cwd, config_path)) if cwd else None
    return {"config_path": config_path, "pilot": pilot}


def find_batch_processes() -> List[Dict]:
    """Live batch-production processes: pid, start_ts, config_path, pilot.

    Matches the script name in argv, so Gradio Popen, CLI and systemd-run launches
    are all seen. Wrapper shells (`bash -c ...`) are skipped: only the python process
    whose argv holds the script as its own argument counts.
    """
    found = []
    for entry in os.scandir("/proc"):
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        try:
            argv = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
            argv = [a.decode(errors="replace") for a in argv if a]
            if not argv or "python" not in os.path.basename(argv[0]):
                continue
            if not any(a.endswith(BATCH_SCRIPT_MARKER) for a in argv[1:]):
                continue
        except OSError:
            continue  # exited
        try:
            cwd = os.readlink(f"/proc/{pid}/cwd")  # EACCES for other users' processes
        except OSError:
            cwd = None
        start_ts = process_start_ts(pid)
        if start_ts is None:
            continue
        found.append({"pid": pid, "start_ts": start_ts, "ppid": _ppid(pid),
                      **_parse_batch_argv(argv, cwd)})
    # forked workers (multiprocessing) inherit the parent's argv: keep only the roots
    pids = {p["pid"] for p in found}
    roots = [p for p in found if p.pop("ppid") not in pids]
    return sorted(roots, key=lambda p: p["start_ts"])


def _ppid(pid: int) -> Optional[int]:
    try:
        raw = Path(f"/proc/{pid}/stat").read_text()
        return int(raw[raw.rindex(")") + 2:].split()[1])
    except (OSError, ValueError, IndexError):
        return None


def read_meminfo() -> Dict:
    """RAM availability in percent plus absolute GiB values."""
    info = {}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, _, rest = line.partition(":")
            info[key] = int(rest.split()[0])  # kB
    except (OSError, ValueError, IndexError):
        return {}
    total = info.get("MemTotal", 0)
    avail = info.get("MemAvailable", 0)
    swap_total = info.get("SwapTotal", 0)
    swap_used = swap_total - info.get("SwapFree", 0)
    return {
        "mem_total_gib": round(total / 1048576, 1),
        "mem_avail_gib": round(avail / 1048576, 1),
        "mem_avail_pct": round(100 * avail / total, 1) if total else None,
        "swap_used_gib": round(swap_used / 1048576, 2),
    }


class SwapRateMeter:
    """Swap activity (pages in+out per second) from /proc/vmstat deltas.

    Occupancy is not thrash: a full-but-idle swap is harmless, so the alarm keys on
    the page rate between two reads.
    """

    def __init__(self):
        self._last = None  # (ts, pages)
        self._prev_rate: Optional[float] = None
        self._lock = threading.Lock()  # request threads share one meter

    @staticmethod
    def _read_pages() -> Optional[int]:
        try:
            vals = {}
            for line in Path("/proc/vmstat").read_text().splitlines():
                k, v = line.split()
                if k in ("pswpin", "pswpout"):
                    vals[k] = int(v)
            return vals.get("pswpin", 0) + vals.get("pswpout", 0)
        except (OSError, ValueError):
            return None

    def rate(self) -> Optional[float]:
        """Pages/s since the previous read; reads < 0.5 s apart reuse the last rate."""
        now, pages = time.monotonic(), self._read_pages()
        if pages is None:
            return None
        with self._lock:
            if self._last is not None and now - self._last[0] < 0.5:
                return self._prev_rate
            prev, self._last = self._last, (now, pages)
            if prev is not None:
                self._prev_rate = round((pages - prev[1]) / (now - prev[0]), 1)
            return self._prev_rate


def read_load() -> Dict:
    """1-minute load average normalised by CPU count."""
    try:
        load1 = float(Path("/proc/loadavg").read_text().split()[0])
    except (OSError, ValueError, IndexError):
        return {}
    ncpu = os.cpu_count() or 1
    return {"load1": load1, "ncpu": ncpu, "load_pct": round(100 * load1 / ncpu, 1)}
