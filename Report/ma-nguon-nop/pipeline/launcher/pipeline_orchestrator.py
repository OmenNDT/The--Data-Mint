"""Pipeline Orchestrator - Main orchestrator for all 9 pipeline phases."""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Callable, List, Dict, Any

from .phase_runner import PhaseRunner, PhaseResult
from .launcher_utils import resolve_pipeline_path, get_checkpoint_info

logger = logging.getLogger(__name__)


# Phase definitions with script paths and Vietnamese names
PHASE_DEFINITIONS = {
    1: {
        "name": "Thiết lập Pipeline",
        "script": "pipeline-setup-main.py",
        "description": "Thiết lập môi trường và cấu hình",
    },
    2: {
        "name": "Tiền xử lý Dữ liệu",
        "script": "data-preprocessing-main.py", 
        "description": "Tiền xử lý dữ liệu đầu vào",
    },
    3: {
        "name": "Huấn luyện LoRA",
        "script": "lora-training-main.py",
        "description": "Huấn luyện mô hình LoRA",
    },
    4: {
        "name": "Thiết kế Workflow",
        "script": "workflow-design-main.py",
        "description": "Thiết kế workflow cho ComfyUI",
    },
    5: {
        "name": "Tạo Mask",
        "script": "mask-generator-main.py",
        "description": "Tạo mask cho các khuyết tật",
    },
    6: {
        "name": "Tạo Ảnh",
        "script": "batch_manager/batch-production-main.py",
        "description": "Tạo ảnh tổng hợp (ComfyUI + ControlNet Inpaint)",
    },
    7: {
        "name": "Hậu xử lý",
        "script": "post_processing/post-processing-main.py",
        "description": "Chia train/val/test và chuyển đổi định dạng",
    },
    8: {
        "name": "Kiểm tra Chất lượng",
        "script": "qa/qa-pipeline-main.py",
        "description": "Kiểm tra chất lượng ảnh và annotation",
    },
    9: {
        "name": "Đánh giá",
        "script": "validation/validation-main.py",
        "description": "Đánh giá mô hình với dữ liệu thực",
    },
}


@dataclass
class PipelineConfig:
    """Configuration for pipeline execution."""
    # Dataset
    dataset_path: str = ""
    
    # Generation params (Phase 6)
    total_images: int = 500
    pilot_mode: bool = False
    
    # Post-processing (Phase 7)
    train_ratio: float = 0.70
    val_ratio: float = 0.20
    test_ratio: float = 0.10
    
    # QA (Phase 8)
    ssim_sample_size: int = 100
    
    # Validation (Phase 9)
    real_yolo_dir: str = ""
    synth_yolo_dir: str = ""
    model_size: str = "n"
    epochs: int = 100
    batch_size: int = 16
    ratios: List[float] = field(default_factory=lambda: [0.0, 0.5, 1.0])
    
    # Output
    output_dir: str = "output"
    
    # Paths
    config_path: str = "config/batch-config.yaml"


@dataclass
class PipelineResult:
    """Result of full pipeline execution."""
    success: bool
    phase_results: List[PhaseResult] = field(default_factory=list)
    total_duration_seconds: float = 0.0
    error_message: Optional[str] = None


class PipelineOrchestrator:
    """Orchestrates all 9 pipeline phases sequentially."""

    def __init__(
        self,
        config: PipelineConfig,
        progress_callback: Optional[Callable[[str], None]] = None,
        phases_to_run: Optional[List[int]] = None,
        python_executable: str = "python"
    ):
        """Initialize PipelineOrchestrator.

        Args:
            config: Pipeline configuration
            progress_callback: Optional callback for progress updates
            phases_to_run: List of phase IDs to run (default: all 6-9)
            python_executable: Path to Python interpreter
        """
        self.config = config
        self.progress_callback = progress_callback
        self.phases_to_run = phases_to_run or [6, 7, 8]  # Default: skip phase 9 unless configured
        self.python_executable = python_executable

        self.phase_runner = PhaseRunner(
            python_executable=python_executable,
            pipeline_dir=resolve_pipeline_path(".")
        )

        self._current_phase: Optional[int] = None
        self._cancel_requested = False

    def _log(self, message: str) -> None:
        """Log message to callback and logger."""
        logger.info(message)
        if self.progress_callback:
            self.progress_callback(message)

    def _build_phase_args(self, phase_id: int) -> List[str]:
        """Build command-line arguments for a phase.

        Args:
            phase_id: Phase number (1-9)

        Returns:
            List of command-line arguments
        """
        args = []

        if phase_id == 6:  # Generation (ComfyUI batch)
            args.extend(["--config", self.config.config_path])
            if self.config.pilot_mode:
                args.append("--pilot")

        elif phase_id == 7:  # Post-processing
            # output_dir already points to synthetic output base (e.g. output/synthetic)
            synth_dir = self.config.output_dir
            output_dir = str(Path(self.config.output_dir).parent / "datasets")
            
            args.extend([
                "--synthetic-dir", synth_dir,
                "--output-dir", output_dir,
                "--train-ratio", str(self.config.train_ratio),
                "--val-ratio", str(self.config.val_ratio),
                "--test-ratio", str(self.config.test_ratio),
            ])

        elif phase_id == 8:  # QA
            synth_dir = self.config.output_dir
            dataset_dir = str(Path(self.config.output_dir).parent / "datasets")
            qa_output = str(Path(self.config.output_dir).parent / "qa-reports")
            
            args.extend([
                "--synthetic-dir", synth_dir,
                "--dataset-dir", dataset_dir,
                "--output-dir", qa_output,
                "--ssim-sample-size", str(self.config.ssim_sample_size),
            ])

        elif phase_id == 9:  # Validation
            if not self.config.real_yolo_dir:
                raise ValueError("Phase 9 requires --real-yolo-dir to be configured")
            
            synth_dir = f"{self.config.output_dir}/datasets"
            
            args.extend([
                "--real-yolo-dir", self.config.real_yolo_dir,
                "--synth-yolo-dir", synth_dir,
                "--output-dir", f"{self.config.output_dir}/validation",
                "--model-size", self.config.model_size,
                "--epochs", str(self.config.epochs),
                "--batch-size", str(self.config.batch_size),
            ])
            
            # Add ratio arguments
            for ratio in self.config.ratios:
                args.extend(["--ratios", str(ratio)])

        return args

    def get_status(self) -> Dict[str, Any]:
        """Get current pipeline status.

        Returns:
            Dict with status information
        """
        return {
            "current_phase": self._current_phase,
            "phases_to_run": self.phases_to_run,
            "cancel_requested": self._cancel_requested,
            "checkpoint_info": get_checkpoint_info()
        }

    def check_checkpoint(self) -> Optional[Dict[str, Any]]:
        """Check for existing checkpoint.

        Returns:
            Checkpoint info dict or None
        """
        return get_checkpoint_info()

    def cancel(self) -> None:
        """Cancel the currently running pipeline."""
        self._cancel_requested = True
        self.phase_runner.cancel()
        self._log("Pipeline cancellation requested...")

    def run_all(self) -> PipelineResult:
        """Run all configured phases sequentially.

        Returns:
            PipelineResult with all phase results
        """
        import time
        start_time = time.time()

        self._log("=" * 50)
        self._log("Starting Pipeline Orchestrator")
        self._log(f"Phases to run: {self.phases_to_run}")
        self._log("=" * 50)

        phase_results = []
        overall_success = True

        # Check checkpoint before starting
        checkpoint_info = self.check_checkpoint()
        if checkpoint_info:
            self._log(f"Found checkpoint: {checkpoint_info['images_generated']} images generated")

        for phase_id in self.phases_to_run:
            if self._cancel_requested:
                self._log("Pipeline cancelled by user")
                break

            if phase_id not in PHASE_DEFINITIONS:
                self._log(f"Unknown phase: {phase_id}")
                continue

            phase_def = PHASE_DEFINITIONS[phase_id]
            self._current_phase = phase_id

            self._log("")
            self._log(f"[Phase {phase_id}/9] {phase_def['name']}")
            self._log(f"Description: {phase_def['description']}")
            self._log("-" * 40)

            # Build script path and args
            script_path = resolve_pipeline_path(phase_def["script"])

            # Skip if script doesn't exist
            if not script_path.exists():
                self._log(f"WARNING: Script not found: {script_path}")
                self._log(f"Skipping phase {phase_id}")
                continue

            try:
                args = self._build_phase_args(phase_id)
            except ValueError as e:
                self._log(f"ERROR: {e}")
                overall_success = False
                break

            # Use per-phase python if specified, otherwise default
            phase_python = phase_def.get("python", None)

            # Run phase
            result = self.phase_runner.run(
                phase_id=phase_id,
                phase_name=phase_def["name"],
                script_path=script_path,
                args=args,
                progress_callback=self._log,
                python_override=phase_python,
            )

            phase_results.append(result)

            if not result.success:
                self._log(f"ERROR: Phase {phase_id} failed: {result.error_message}")
                overall_success = False
                break

        total_duration = time.time() - start_time

        self._log("")
        self._log("=" * 50)
        self._log(f"Pipeline {'completed' if overall_success else 'failed'}")
        self._log(f"Total duration: {total_duration:.1f}s ({total_duration/60:.1f} minutes)")
        self._log("=" * 50)

        return PipelineResult(
            success=overall_success,
            phase_results=phase_results,
            total_duration_seconds=total_duration,
            error_message=None if overall_success else "Pipeline failed - see logs"
        )

    def run_phase(self, phase_id: int) -> PhaseResult:
        """Run a single phase.

        Args:
            phase_id: Phase number to run

        Returns:
            PhaseResult for the executed phase
        """
        if phase_id not in PHASE_DEFINITIONS:
            return PhaseResult(
                phase_id=phase_id,
                phase_name="Unknown",
                success=False,
                exit_code=-1,
                duration_seconds=0.0,
                error_message=f"Unknown phase: {phase_id}"
            )

        phase_def = PHASE_DEFINITIONS[phase_id]
        script_path = resolve_pipeline_path(phase_def["script"])

        if not script_path.exists():
            return PhaseResult(
                phase_id=phase_id,
                phase_name=phase_def["name"],
                success=False,
                exit_code=-1,
                duration_seconds=0.0,
                error_message=f"Script not found: {script_path}"
            )

        args = self._build_phase_args(phase_id)

        return self.phase_runner.run(
            phase_id=phase_id,
            phase_name=phase_def["name"],
            script_path=script_path,
            args=args,
            progress_callback=self._log
        )
