"""Slow probes (nvidia-smi, ComfyUI HTTP) behind a non-blocking, single-flight cache.

`BackgroundProbe.get()` never waits for the probe: it returns the last value and,
when that value is stale, starts one refresh thread (never two at once). Until the
first probe completes the value is `{"ok": None}` = unknown, which never alarms.
"""

import json
import subprocess
import threading
import time
import urllib.request
from typing import Callable, Dict


class BackgroundProbe:
    def __init__(self, fn: Callable[[], Dict], ttl: float):
        self._fn = fn
        self._ttl = ttl
        self._value: Dict = {"ok": None}
        self._fetched_at = 0.0
        self._running = False
        self._started_at = 0.0
        self._lock = threading.Lock()

    def _refresh(self):
        try:
            value = dict(self._fn())
        except Exception as exc:  # a probe bug degrades its panel only
            value = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        with self._lock:
            self._value = {**value, "probed_ts": time.time()}
            self._fetched_at = time.time()
            self._running = False

    def get(self) -> Dict:
        with self._lock:
            now = time.time()
            if now - self._fetched_at > self._ttl and not self._running:
                self._running = True
                self._started_at = now
                try:
                    threading.Thread(target=self._refresh, daemon=True).start()
                except Exception:
                    self._running = False
            # A hung probe (DNS stall, trickling server) must not keep serving "ok" forever
            if self._running and now - self._started_at > max(3 * self._ttl, 20):
                return {"ok": None, "stale": True, "error": "probe không trả lời"}
            return dict(self._value)


def probe_local_gpu() -> Dict:
    """RTX 3090 on this host: temperature, utilisation, VRAM, power."""
    out = subprocess.run(
        ["nvidia-smi",
         "--query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total,power.draw",
         "--format=csv,noheader,nounits"],
        capture_output=True, text=True, timeout=4,
    )
    if out.returncode != 0 or not out.stdout.strip():
        return {"ok": False, "error": (out.stderr or "nvidia-smi failed").strip()[:200]}
    name, temp, util, used, total, power = [p.strip() for p in out.stdout.splitlines()[0].split(",")]

    def num(v):
        try:
            return float(v)
        except ValueError:
            return None

    return {"ok": True, "name": name, "temp_c": num(temp), "util_pct": num(util),
            "vram_used_mib": num(used), "vram_total_mib": num(total), "power_w": num(power)}


def _get_json(url: str, timeout: float):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def make_comfyui_probe(base_url: str) -> Callable[[], Dict]:
    """Probe for one ComfyUI server: health, queue depth, VRAM of its GPU."""

    def probe() -> Dict:
        try:
            stats = _get_json(f"{base_url}/system_stats", timeout=2.5)
        except Exception as exc:
            return {"ok": False, "url": base_url, "error": f"{type(exc).__name__}: {exc}"[:200]}
        result = {"ok": True, "url": base_url}
        devices = stats.get("devices") or []
        if devices:
            dev = devices[0]
            result.update(device=dev.get("name"),
                          vram_total_mib=round((dev.get("vram_total") or 0) / 1048576),
                          vram_free_mib=round((dev.get("vram_free") or 0) / 1048576))
        try:
            queue = _get_json(f"{base_url}/queue", timeout=2.5)
            result["queue_running"] = len(queue.get("queue_running") or [])
            result["queue_pending"] = len(queue.get("queue_pending") or [])
        except Exception:
            pass  # health is known; queue stays unknown
        return result

    return probe


_gpu_probe = BackgroundProbe(probe_local_gpu, ttl=5.0)
_comfy_probes: Dict[str, BackgroundProbe] = {}
_comfy_lock = threading.Lock()


def local_gpu() -> Dict:
    return _gpu_probe.get()


def comfyui(host: str, port: int) -> Dict:
    """Cached probe per ComfyUI endpoint (batch configs may point at different hosts)."""
    base_url = f"http://{host}:{port}"
    with _comfy_lock:
        probe = _comfy_probes.get(base_url)
        if probe is None:
            probe = _comfy_probes[base_url] = BackgroundProbe(make_comfyui_probe(base_url), ttl=5.0)
    return {"url": base_url, **probe.get()}
