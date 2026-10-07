"""ComfyUI feedback on this host: is the process alive, and is the configured host local?

ComfyUI runs on the same machine as the batch pipeline (it drives the local RTX 3090).
The HTTP probe alone cannot tell "not started" from "started but listening on another
address" from "config points at a stale DHCP IP"; these readers give the command-vs-
feedback pieces so the alarms can name the actual fix.
"""

import ipaddress
import os
import socket
import time
from pathlib import Path
from typing import Dict, List, Optional


def _arg_value(argv: List[str], flag: str) -> Optional[str]:
    for i, arg in enumerate(argv):
        if arg == flag and i + 1 < len(argv):
            return argv[i + 1]
        if arg.startswith(flag + "="):
            return arg.split("=", 1)[1]
    return None


def find_comfyui_processes() -> List[Dict]:
    """Live `python main.py` processes started from a ComfyUI directory."""
    found = []
    for entry in os.scandir("/proc"):
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        try:
            argv = [a.decode(errors="replace")
                    for a in Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0") if a]
            if not argv or "python" not in os.path.basename(argv[0]):
                continue
            script = next((a for a in argv[1:] if a.endswith("main.py")), None)
            if script is None:
                continue
            try:
                cwd = os.readlink(f"/proc/{pid}/cwd")
            except OSError:
                cwd = ""
            where = os.path.join(cwd, script).lower()
            if "comfyui" not in where:
                continue
        except OSError:
            continue
        found.append({"pid": pid, "listen": _arg_value(argv, "--listen") or "127.0.0.1",
                      "port": _arg_value(argv, "--port") or "8188"})
    return found


_local_cache: Dict[str, tuple] = {}  # host -> (checked_at, result)
_LOCAL_TTL_S = 300


def is_local_address(host: str) -> Optional[bool]:
    """True if `host` is an address of this machine, False if not, None if unknown.

    Only IP literals and `localhost` are judged (binding to the address answers the
    question without DNS); hostnames stay unknown so a slow resolver never blocks a
    request thread. Cached: interface addresses change rarely (DHCP renewals).
    """
    hit = _local_cache.get(host)
    if hit and time.time() - hit[0] < _LOCAL_TTL_S:
        return hit[1]
    if host in ("localhost", "0.0.0.0"):
        result = True
    else:
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            return None
        if ip.is_loopback:
            result = True
        else:
            family = socket.AF_INET6 if ip.version == 6 else socket.AF_INET
            try:
                with socket.socket(family, socket.SOCK_DGRAM) as s:
                    s.bind((host, 0))  # succeeds only for an address held by this host
                result = True
            except OSError:
                result = False
    if len(_local_cache) < 64 or host in _local_cache:
        _local_cache[host] = (time.time(), result)
    return result
