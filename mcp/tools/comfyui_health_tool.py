"""ComfyUI health check tool — API status, GPU temp, queue length."""

import json
import subprocess
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError


def register(mcp, project_root: Path):
    @mcp.tool()
    def comfyui_health() -> dict:
        """Check ComfyUI API server health, GPU temperature, VRAM usage, queue status."""
        config = _load_comfyui_config(project_root)
        host = config.get("host", "10.86.201.250")
        port = config.get("port", 8188)
        base_url = f"http://{host}:{port}"

        result = {
            "api": _check_api(base_url),
            "gpu": _get_gpu_info(),
            "queue": _check_queue(base_url),
        }
        return result


def _load_comfyui_config(project_root: Path) -> dict:
    """Load ComfyUI host/port from batch-config.yaml."""
    config_path = project_root / "pipeline" / "config" / "batch-config.yaml"
    if not config_path.exists():
        return {}
    try:
        import yaml
        with open(config_path) as f:
            config = yaml.safe_load(f)
        return config.get("comfyui", {})
    except Exception:
        return {}


def _check_api(base_url: str) -> dict:
    """Check if ComfyUI API is responding."""
    try:
        req = Request(f"{base_url}/system_stats", method="GET")
        with urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            return {"status": "online", "system_stats": data}
    except URLError as e:
        return {"status": "offline", "error": str(e)}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def _get_gpu_info() -> dict:
    """Get GPU temperature and VRAM usage via nvidia-smi."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=temperature.gpu,memory.used,memory.total,utilization.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return {"status": "nvidia-smi failed", "stderr": result.stderr.strip()}

        parts = result.stdout.strip().split(", ")
        if len(parts) >= 4:
            return {
                "temp_celsius": int(parts[0]),
                "vram_used_mb": int(parts[1]),
                "vram_total_mb": int(parts[2]),
                "utilization_pct": int(parts[3]),
                "thermal_ok": int(parts[0]) < 85,
            }
        return {"status": "parse_error", "raw": result.stdout.strip()}
    except FileNotFoundError:
        return {"status": "nvidia-smi not found"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def _check_queue(base_url: str) -> dict:
    """Check ComfyUI prompt queue length."""
    try:
        req = Request(f"{base_url}/queue", method="GET")
        with urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            running = len(data.get("queue_running", []))
            pending = len(data.get("queue_pending", []))
            return {"running": running, "pending": pending}
    except Exception as e:
        return {"status": "error", "error": str(e)}
