"""Progress Tracker - Parse real-time stdout for structured progress data."""

import re
import logging
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class ProgressUpdate:
    """Progress update from parsing a log line."""
    phase_id: int
    phase_progress: float  # 0.0 - 1.0
    overall_progress: float
    message: str
    level: str  # info, warning, error
    eta_seconds: Optional[int]
    gpu_temp: Optional[float]
    images_generated: Optional[int]
    epoch_current: Optional[int]
    epoch_total: Optional[int]


# Regex patterns for different phase outputs
PATTERNS = {
    # Phase 6: Generation checkpoint
    "checkpoint": re.compile(r"\[CHECKPOINT\] Generated (\d+) images"),
    "checkpoint_elapsed": re.compile(r"elapsed: ([\d.]+)s"),
    
    # Phase 6: Thermal monitoring
    "thermal": re.compile(r"GPU temp: ([\d.]+)"),
    "thermal_pause": re.compile(r"Pausing.*temp: ([\d.]+)"),
    "thermal_resume": re.compile(r"Resuming.*temp: ([\d.]+)"),
    
    # Phase 7: Post-processing
    "postprocess_progress": re.compile(r"Processing (\w+).*\((\d+)/(\d+)\)"),
    
    # Phase 8: QA
    "ssim_progress": re.compile(r"SSIM check: (\d+)/(\d+)"),
    "qa_complete": re.compile(r"QA complete.*SSIM: ([\d.]+)"),
    
    # Phase 9: Validation (Ultralytics format)
    "epoch": re.compile(r"Epoch\s+(\d+)/(\d+)"),
    "map": re.compile(r"mAP@0\.5:\s*([\d.]+)"),
    "map_full": re.compile(r"mAP@0\.5:0\.95:\s*([\d.]+)"),
    
    # Common
    "error": re.compile(r"\[(ERROR|CRITICAL)\]"),
    "warning": re.compile(r"\[WARNING\]"),
    "info": re.compile(r"\[INFO\]"),
}


# Phase weight distribution
PHASE_WEIGHTS = {
    1: 0.05,   # Setup
    2: 0.05,   # Preprocessing
    3: 0.15,   # LoRA training
    4: 0.02,   # Workflow design
    5: 0.03,   # Mask generation
    6: 0.50,   # Generation (main phase)
    7: 0.02,   # Post-processing
    8: 0.03,   # QA
    9: 0.15,   # Validation
}


class ProgressTracker:
    """Tracks progress from pipeline subprocess output."""

    def __init__(
        self,
        total_phases: int = 9,
        config: Optional[Dict[str, Any]] = None
    ):
        """Initialize ProgressTracker.

        Args:
            total_phases: Total number of phases
            config: Configuration dict for total_images, epochs, etc.
        """
        self.total_phases = total_phases
        self.config = config or {}

        # State
        self.current_phase = 0
        self.start_time = datetime.now()
        self.image_count = 0
        self.total_images = self.config.get("total_images", 1000)
        self.epoch_count = 0
        self.total_epochs = self.config.get("epochs", 100)
        self.throughput_samples: List[float] = []

        # Completed phases
        self.completed_phases: List[int] = []

        # Errors/warnings
        self.errors: List[str] = []
        self.warnings: List[str] = []

        # GPU
        self.gpu_temps: List[float] = []

    def reset(self) -> None:
        """Reset progress tracker state."""
        self.current_phase = 0
        self.start_time = datetime.now()
        self.image_count = 0
        self.epoch_count = 0
        self.throughput_samples.clear()
        self.completed_phases.clear()
        self.errors.clear()
        self.warnings.clear()
        self.gpu_temps.clear()

    def set_current_phase(self, phase_id: int) -> None:
        """Set the current phase.

        Args:
            phase_id: Phase number (1-9)
        """
        if phase_id != self.current_phase and phase_id not in self.completed_phases:
            if self.current_phase > 0:
                self.completed_phases.append(self.current_phase)
            self.current_phase = phase_id

    def parse_line(self, line: str) -> Optional[ProgressUpdate]:
        """Parse a log line and extract progress info.

        Args:
            line: Raw log line

        Returns:
            ProgressUpdate if line contains progress info, None otherwise
        """
        level = "info"

        # Check for errors/warnings first
        if PATTERNS["error"].search(line):
            level = "error"
            self.errors.append(line)
        elif PATTERNS["warning"].search(line):
            level = "warning"
            self.warnings.append(line)

        # Phase 6: Generation
        match = PATTERNS["checkpoint"].search(line)
        if match:
            self.image_count = int(match.group(1))
            self._record_throughput()

            progress = self.image_count / self.total_images if self.total_images > 0 else 0

            return ProgressUpdate(
                phase_id=self.current_phase,
                phase_progress=progress,
                overall_progress=self._calculate_overall_progress(progress),
                message=line.strip(),
                level=level,
                eta_seconds=self._calculate_eta(progress),
                gpu_temp=self.gpu_temps[-1] if self.gpu_temps else None,
                images_generated=self.image_count,
                epoch_current=None,
                epoch_total=None
            )

        # Phase 6: Thermal
        match = PATTERNS["thermal"].search(line)
        if match:
            temp = float(match.group(1))
            self.gpu_temps.append(temp)

            return ProgressUpdate(
                phase_id=self.current_phase,
                phase_progress=self._get_phase_progress(),
                overall_progress=self._calculate_overall_progress(),
                message=line.strip(),
                level=level,
                eta_seconds=self._calculate_eta(),
                gpu_temp=temp,
                images_generated=self.image_count,
                epoch_current=None,
                epoch_total=None
            )

        # Phase 9: Epoch
        match = PATTERNS["epoch"].search(line)
        if match:
            self.epoch_count = int(match.group(1))
            self.total_epochs = int(match.group(2))

            progress = self.epoch_count / self.total_epochs if self.total_epochs > 0 else 0

            return ProgressUpdate(
                phase_id=self.current_phase,
                phase_progress=progress,
                overall_progress=self._calculate_overall_progress(progress),
                message=line.strip(),
                level=level,
                eta_seconds=self._calculate_eta_epoch(),
                gpu_temp=self.gpu_temps[-1] if self.gpu_temps else None,
                images_generated=None,
                epoch_current=self.epoch_count,
                epoch_total=self.total_epochs
            )

        # Phase 8: SSIM progress
        match = PATTERNS["ssim_progress"].search(line)
        if match:
            current = int(match.group(1))
            total = int(match.group(2))
            progress = current / total if total > 0 else 0

            return ProgressUpdate(
                phase_id=self.current_phase,
                phase_progress=progress,
                overall_progress=self._calculate_overall_progress(progress),
                message=line.strip(),
                level=level,
                eta_seconds=None,
                gpu_temp=self.gpu_temps[-1] if self.gpu_temps else None,
                images_generated=None,
                epoch_current=None,
                epoch_total=None
            )

        # Phase 7: Post-processing
        match = PATTERNS["postprocess_progress"].search(line)
        if match:
            current = int(match.group(2))
            total = int(match.group(3))
            progress = current / total if total > 0 else 0

            return ProgressUpdate(
                phase_id=self.current_phase,
                phase_progress=progress,
                overall_progress=self._calculate_overall_progress(progress),
                message=line.strip(),
                level=level,
                eta_seconds=None,
                gpu_temp=self.gpu_temps[-1] if self.gpu_temps else None,
                images_generated=None,
                epoch_current=None,
                epoch_total=None
            )

        # No progress info in this line
        return None

    def _record_throughput(self) -> None:
        """Record a throughput sample."""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        if elapsed > 0 and self.image_count > 0:
            throughput = self.image_count / (elapsed / 3600)  # images per hour
            self.throughput_samples.append(throughput)

            # Keep last 10 samples
            if len(self.throughput_samples) > 10:
                self.throughput_samples = self.throughput_samples[-10:]

    def _get_average_throughput(self) -> float:
        """Get average throughput from samples."""
        if not self.throughput_samples:
            return 1000  # Default estimate
        return sum(self.throughput_samples) / len(self.throughput_samples)

    def _calculate_eta(self, phase_progress: float = None) -> Optional[int]:
        """Calculate ETA in seconds.

        Args:
            phase_progress: Current phase progress (0-1)

        Returns:
            ETA in seconds or None
        """
        if phase_progress is None:
            phase_progress = self._get_phase_progress()

        if phase_progress <= 0:
            return None

        elapsed = (datetime.now() - self.start_time).total_seconds()
        remaining = (elapsed / phase_progress) * (1 - phase_progress)

        return int(remaining)

    def _calculate_eta_epoch(self) -> Optional[int]:
        """Calculate ETA for epoch-based phases (validation)."""
        if self.epoch_count <= 0:
            return None

        elapsed = (datetime.now() - self.start_time).total_seconds()
        time_per_epoch = elapsed / self.epoch_count
        remaining_epochs = self.total_epochs - self.epoch_count

        return int(time_per_epoch * remaining_epochs)

    def _get_phase_progress(self) -> float:
        """Get progress within current phase."""
        if self.current_phase == 6:
            return self.image_count / self.total_images if self.total_images > 0 else 0
        elif self.current_phase == 9:
            return self.epoch_count / self.total_epochs if self.total_epochs > 0 else 0
        else:
            return 0

    def _calculate_overall_progress(self, phase_progress: float = None) -> float:
        """Calculate overall pipeline progress.

        Args:
            phase_progress: Current phase progress (0-1)

        Returns:
            Overall progress (0-1)
        """
        if phase_progress is None:
            phase_progress = self._get_phase_progress()

        # Sum completed phases
        total = 0.0
        for phase in self.completed_phases:
            total += PHASE_WEIGHTS.get(phase, 0)

        # Add current phase progress
        current_weight = PHASE_WEIGHTS.get(self.current_phase, 0)
        total += current_weight * phase_progress

        return min(1.0, max(0.0, total))

    def get_overall_progress(self) -> float:
        """Get overall pipeline progress.

        Returns:
            Progress as 0.0-1.0
        """
        return self._calculate_overall_progress()

    def get_eta_seconds(self) -> Optional[int]:
        """Get overall ETA in seconds.

        Returns:
            ETA in seconds or None
        """
        if self.current_phase == 6:
            return self._calculate_eta()
        elif self.current_phase == 9:
            return self._calculate_eta_epoch()
        else:
            return None

    def get_current_phase_info(self) -> Dict[str, Any]:
        """Get info about current phase.

        Returns:
            Dict with phase info
        """
        phase_progress = self._get_phase_progress()

        return {
            "phase_id": self.current_phase,
            "phase_weight": PHASE_WEIGHTS.get(self.current_phase, 0),
            "phase_progress": phase_progress,
            "overall_progress": self._calculate_overall_progress(phase_progress),
            "images_generated": self.image_count,
            "total_images": self.total_images,
            "epoch_current": self.epoch_count,
            "epoch_total": self.total_epochs,
            "gpu_temp": self.gpu_temps[-1] if self.gpu_temps else None,
            "eta_seconds": self.get_eta_seconds(),
        }
