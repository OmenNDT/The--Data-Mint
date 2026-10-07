"""Shared dataclasses for the auto-label pipeline.

Defines detection results, segmented detections, and pipeline configuration.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import numpy as np


@dataclass
class DetectionResult:
    """Single YOLO detection bounding box."""

    bbox_xyxy: List[float]  # [x1, y1, x2, y2] absolute pixels
    confidence: float
    class_id: int
    class_name: str


@dataclass
class SegmentedDetection:
    """Detection with SAM-generated binary mask."""

    detection: DetectionResult
    mask: np.ndarray  # (H, W) binary uint8, 0 or 255
    mask_area: int = 0


@dataclass
class ImageAutoLabelResult:
    """All detections + masks for a single image."""

    image_path: Path
    image_width: int
    image_height: int
    detections: List[SegmentedDetection] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def num_detections(self) -> int:
        return len(self.detections)


@dataclass
class AutoLabelResult:
    """Full pipeline result across all images."""

    image_results: List[ImageAutoLabelResult] = field(default_factory=list)
    total_images: int = 0
    total_detections: int = 0
    output_dir: Optional[Path] = None
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None and self.total_images > 0


@dataclass
class AutoLabelConfig:
    """Configuration for the auto-label pipeline."""

    # Input
    input_dir: str = ""

    # Model weights
    yolo_weights: str = ""
    sam_checkpoint: str = ""
    sam_model_type: str = "vit_b"  # vit_b | vit_l | vit_h

    # Detection
    confidence_threshold: float = 0.5
    max_detections_per_image: int = 20

    # Processing
    batch_size: int = 8
    device: str = "cuda:0"

    # Output
    save_masks: bool = True
    output_coco: bool = True
    output_yolo: bool = True
    output_dir: str = "output/auto-labeled"
