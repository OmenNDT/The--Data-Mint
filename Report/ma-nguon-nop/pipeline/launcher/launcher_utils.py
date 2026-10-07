"""Launcher utilities - Path validation and config helpers."""

import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


def resolve_pipeline_path(relative: str) -> Path:
    """Resolve a path relative to pipeline root.

    Args:
        relative: Relative path (e.g., "batch_manager/batch-production-main.py")

    Returns:
        Absolute Path object
    """
    pipeline_root = Path(__file__).parent.parent
    return pipeline_root / relative


def validate_dataset_path(path: str) -> tuple[bool, Optional[str]]:
    """Validate dataset folder path.

    Args:
        path: Dataset folder path to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not path:
        return False, "Dataset path is empty"

    dataset_path = Path(path)

    # Try to resolve if relative
    if not dataset_path.is_absolute():
        dataset_path = resolve_pipeline_path(path)

    if not dataset_path.exists():
        return False, f"Dataset folder not found: {path}"

    if not dataset_path.is_dir():
        return False, f"Path is not a directory: {path}"

    return True, None


def check_disk_space(path: str, required_gb: float = 10.0) -> tuple[bool, Optional[str]]:
    """Check if sufficient disk space is available.

    Args:
        path: Path to check (directory or file)
        required_gb: Required space in GB

    Returns:
        Tuple of (has_space, error_message)
    """
    import shutil

    try:
        path_obj = Path(path)
        if not path_obj.is_absolute():
            path_obj = resolve_pipeline_path(path)

        # Get disk usage for the drive
        if path_obj.exists():
            stat = shutil.disk_usage(path_obj)
            free_gb = stat.free / (1024 ** 3)

            if free_gb < required_gb:
                return False, f"Low disk space: {free_gb:.1f}GB free, need {required_gb:.1f}GB"

            return True, None
        else:
            # Check parent directory
            parent = path_obj.parent
            if parent.exists():
                stat = shutil.disk_usage(parent)
                free_gb = stat.free / (1024 ** 3)
                if free_gb < required_gb:
                    return False, f"Low disk space: {free_gb:.1f}GB free, need {required_gb:.1f}GB"
                return True, None

            return True, None  # Can't check, assume OK

    except Exception as e:
        logger.warning(f"Could not check disk space: {e}")
        return True, None  # Assume OK if can't check


def check_gpu_available() -> tuple[bool, Optional[str]]:
    """Check if CUDA GPU is available.

    Returns:
        Tuple of (has_gpu, error_message)
    """
    try:
        import subprocess
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            gpu_name = result.stdout.strip().split('\n')[0]
            logger.info(f"GPU detected: {gpu_name}")
            return True, gpu_name
        else:
            return False, "No CUDA GPU detected"
    except FileNotFoundError:
        return False, "nvidia-smi not found - NVIDIA driver may not be installed"
    except Exception as e:
        logger.warning(f"GPU check failed: {e}")
        return False, f"GPU check failed: {str(e)}"


def check_comfyui_connection(host: str = "localhost", port: int = 8188) -> tuple[bool, Optional[str]]:
    """Check if ComfyUI API is accessible.

    Args:
        host: ComfyUI host
        port: ComfyUI port

    Returns:
        Tuple of (is_connected, error_message)
    """
    import urllib.request
    import json

    try:
        url = f"http://{host}:{port}/system_stats"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read())
            logger.info(f"ComfyUI connected: {data.get('devices', [{}])[0].get('name', 'unknown')}")
            return True, None
    except urllib.error.URLError:
        return False, f"ComfyUI not detected at {host}:{port}. Please start ComfyUI first."
    except Exception as e:
        return False, f"ComfyUI connection error: {str(e)}"


def get_checkpoint_info(checkpoint_dir: str = "checkpoints") -> Optional[Dict[str, Any]]:
    """Check for existing checkpoint and return info.

    Args:
        checkpoint_dir: Path to checkpoint directory

    Returns:
        Dict with checkpoint info or None if no checkpoint found
    """
    checkpoint_path = resolve_pipeline_path(checkpoint_dir)

    if not checkpoint_path.exists():
        return None

    # Look for checkpoint files
    checkpoint_files = list(checkpoint_path.glob("*.json"))

    if not checkpoint_files:
        return None

    # Get most recent checkpoint
    latest = max(checkpoint_files, key=lambda p: p.stat().st_mtime)

    try:
        import json
        with open(latest, 'r') as f:
            data = json.load(f)

        return {
            "file": str(latest),
            "images_generated": data.get("images_generated", 0),
            "last_updated": data.get("last_updated", ""),
            "defect_type": data.get("defect_type", "unknown")
        }
    except Exception as e:
        logger.warning(f"Could not read checkpoint: {e}")
        return None
