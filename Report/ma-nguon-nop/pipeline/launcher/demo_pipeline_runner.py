"""Demo Pipeline Runner - Mock orchestrator for UI testing without real pipeline."""

import time
import logging
from typing import Optional, Callable, List, Dict, Any

from .pipeline_orchestrator import PipelineConfig, PipelineResult, PHASE_DEFINITIONS
from .phase_runner import PhaseResult

logger = logging.getLogger(__name__)

# Mock log lines grouped by phase with delays (seconds)
MOCK_LOG_SEQUENCE = [
    # Phase 6: Generation (~12s)
    (6, "[INFO] Pipeline started - Demo Mode", 0.5),
    (6, "[Phase 6/9] Tạo Ảnh", 0.3),
    (6, "[CHECKPOINT] Generated 100 images, elapsed: 2.0s", 2.0),
    (6, "GPU temp: 72.5", 0.5),
    (6, "[CHECKPOINT] Generated 200 images, elapsed: 4.0s", 2.0),
    (6, "[CHECKPOINT] Generated 300 images, elapsed: 6.0s", 2.0),
    (6, "[CHECKPOINT] Generated 400 images, elapsed: 8.0s", 2.0),
    (6, "[CHECKPOINT] Generated 500 images, elapsed: 10.0s", 2.0),
    (6, "GPU temp: 74.1", 0.5),
    # Phase 7: Post-processing (~3s)
    (7, "[Phase 7/9] Hậu xử lý", 0.5),
    (7, "Processing crack (1/5)", 0.5),
    (7, "Processing porosity (2/5)", 0.5),
    (7, "Processing inclusion (3/5)", 0.5),
    (7, "Processing lack_of_fusion (4/5)", 0.5),
    (7, "Processing undercut (5/5)", 0.5),
    # Phase 8: QA (~4s)
    (8, "[Phase 8/9] Kiểm tra Chất lượng", 0.5),
    (8, "SSIM check: 25/100 images", 1.0),
    (8, "SSIM check: 50/100 images", 1.0),
    (8, "SSIM check: 75/100 images", 0.5),
    (8, "SSIM check: 100/100 images", 0.5),
    (8, "QA complete. SSIM: 0.94", 0.5),
    # Phase 9: Validation (~6s)
    (9, "[Phase 9/9] Đánh giá", 0.5),
    (9, "Epoch 5/20", 1.0),
    (9, "Epoch 10/20", 1.0),
    (9, "Epoch 15/20", 1.0),
    (9, "Epoch 20/20", 1.0),
    (9, "mAP@0.5: 0.612", 0.5),
    (9, "mAP@0.5:0.95: 0.381", 0.5),
    (9, "Pipeline completed successfully!", 0.3),
]


class MockPipelineOrchestrator:
    """Mock orchestrator that simulates pipeline execution for UI testing."""

    def __init__(
        self,
        config: PipelineConfig,
        progress_callback: Optional[Callable[[str], None]] = None,
        phases_to_run: Optional[List[int]] = None,
        **kwargs,
    ):
        self.config = config
        self.progress_callback = progress_callback
        self.phases_to_run = phases_to_run or [6, 7, 8]
        self._cancel_requested = False

    def _log(self, message: str) -> None:
        logger.info(message)
        if self.progress_callback:
            self.progress_callback(message)

    def cancel(self) -> None:
        self._cancel_requested = True
        self._log("Pipeline cancellation requested...")

    def get_status(self) -> Dict[str, Any]:
        return {
            "current_phase": None,
            "phases_to_run": self.phases_to_run,
            "cancel_requested": self._cancel_requested,
            "demo_mode": True,
        }

    def run_all(self) -> PipelineResult:
        """Simulate pipeline run with fake log output (~25 seconds)."""
        start_time = time.time()
        phase_results = []

        self._log("=" * 50)
        self._log("[DEMO MODE] Starting Mock Pipeline")
        self._log(f"Phases to run: {self.phases_to_run}")
        self._log("=" * 50)

        # Filter log sequence to only include requested phases
        for phase_id, message, delay in MOCK_LOG_SEQUENCE:
            if self._cancel_requested:
                self._log("Pipeline cancelled by user")
                break

            if phase_id not in self.phases_to_run:
                continue

            time.sleep(delay)
            self._log(message)

        # Build phase results for completed phases
        for phase_id in self.phases_to_run:
            phase_def = PHASE_DEFINITIONS.get(phase_id, {})
            phase_results.append(PhaseResult(
                phase_id=phase_id,
                phase_name=phase_def.get("name", f"Phase {phase_id}"),
                success=not self._cancel_requested,
                exit_code=0,
                duration_seconds=5.0,
            ))

        total_duration = time.time() - start_time

        self._log("")
        self._log("=" * 50)
        status = "cancelled" if self._cancel_requested else "completed"
        self._log(f"[DEMO] Pipeline {status} in {total_duration:.1f}s")
        self._log("=" * 50)

        return PipelineResult(
            success=not self._cancel_requested,
            phase_results=phase_results,
            total_duration_seconds=total_duration,
            error_message="Cancelled" if self._cancel_requested else None,
        )
