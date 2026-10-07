"""Error Handler - Pre-flight checks and error recovery for pipeline launcher."""

import logging
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from .launcher_utils import (
    check_gpu_available,
    check_comfyui_connection,
    check_disk_space,
    validate_dataset_path,
    resolve_pipeline_path
)

logger = logging.getLogger(__name__)


class ErrorHandler:
    """Handles pre-flight checks and error recovery."""

    def __init__(self):
        """Initialize ErrorHandler."""
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def reset(self) -> None:
        """Reset error state."""
        self.errors.clear()
        self.warnings.clear()

    def check_gpu_available(self) -> bool:
        """Check if GPU is available.

        Returns:
            True if GPU is available
        """
        available, msg = check_gpu_available()
        if not available:
            self.errors.append(f"GPU: {msg}")
            return False
        self.warnings.append(f"GPU: {msg}")
        return True

    def check_comfyui_connection(
        self,
        host: str = "172.21.192.1",
        port: int = 8188
    ) -> bool:
        """Check if ComfyUI is accessible.

        Args:
            host: ComfyUI host
            port: ComfyUI port

        Returns:
            True if ComfyUI is connected
        """
        connected, msg = check_comfyui_connection(host, port)
        if not connected:
            self.errors.append(f"ComfyUI: {msg}")
            return False
        self.warnings.append(f"ComfyUI: {msg}")
        return True

    def check_disk_space(
        self,
        path: str = "output",
        required_gb: float = 10.0
    ) -> bool:
        """Check disk space.

        Args:
            path: Path to check
            required_gb: Required space in GB

        Returns:
            True if sufficient space
        """
        has_space, msg = check_disk_space(path, required_gb)
        if not has_space:
            self.errors.append(f"Disk: {msg}")
            return False
        return True

    def check_dataset_path(self, path: str) -> bool:
        """Check dataset path exists.

        Args:
            path: Dataset path

        Returns:
            True if path is valid
        """
        if not path:
            self.errors.append("Dataset: Đường dẫn dataset trống")
            return False

        valid, msg = validate_dataset_path(path)
        if not valid:
            self.errors.append(f"Dataset: {msg}")
            return False
        return True

    def check_pipeline_scripts(self) -> bool:
        """Check that required pipeline scripts exist.

        Returns:
            True if all scripts exist
        """
        required_scripts = {
            6: "batch_manager/batch-production-main.py",
            7: "post_processing/post-processing-main.py",
            8: "qa/qa-pipeline-main.py",
            9: "validation/validation-main.py",
        }

        all_exist = True
        for phase, script in required_scripts.items():
            script_path = resolve_pipeline_path(script)
            if not script_path.exists():
                self.errors.append(f"Script Phase {phase}: Không tìm thấy {script}")
                all_exist = False

        return all_exist

    def check_output_dirs(self) -> bool:
        """Check that output directories are writable.

        Returns:
            True if directories are writable
        """
        output_dir = resolve_pipeline_path("output")

        try:
            output_dir.mkdir(parents=True, exist_ok=True)

            # Test write
            test_file = output_dir / ".write_test"
            test_file.write_text("test")
            test_file.unlink()

            return True
        except Exception as e:
            self.errors.append(f"Output: Không thể ghi vào thư mục output: {e}")
            return False

    def run_preflight_checks(
        self,
        config: Dict[str, Any]
    ) -> Tuple[bool, List[str], List[str]]:
        """Run all pre-flight checks.

        Args:
            config: Pipeline configuration

        Returns:
            Tuple of (all_passed, errors, warnings)
        """
        self.reset()

        # Check GPU
        self.check_gpu_available()

        # Check ComfyUI (only if running generation phase)
        phases = config.get("phases_to_run", [])
        if 6 in phases:
            self.check_comfyui_connection()

        # Check disk space
        self.check_disk_space()

        # Check dataset if provided
        dataset_path = config.get("dataset_path", "")
        if dataset_path:
            self.check_dataset_path(dataset_path)

        # Check scripts
        self.check_pipeline_scripts()

        # Check output dirs
        self.check_output_dirs()

        return (
            len(self.errors) == 0,
            self.errors.copy(),
            self.warnings.copy()
        )


def format_error_message(error: str) -> str:
    """Format error message for user display.

    Args:
        error: Error string

    Returns:
        Formatted error message
    """
    # Add emoji based on error type
    if "GPU" in error:
        return f"🖥️ {error}"
    elif "ComfyUI" in error:
        return f"🎨 {error}"
    elif "Dataset" in error:
        return f"📁 {error}"
    elif "Disk" in error:
        return f"💾 {error}"
    elif "Script" in error:
        return f"📜 {error}"
    elif "Output" in error:
        return f"📤 {error}"
    else:
        return f"❌ {error}"


def format_warning_message(warning: str) -> str:
    """Format warning message for user display.

    Args:
        warning: Warning string

    Returns:
        Formatted warning message
    """
    if "GPU" in warning:
        return f"🖥️ {warning}"
    elif "ComfyUI" in warning:
        return f"🎨 {warning}"
    else:
        return f"⚠️ {warning}"
