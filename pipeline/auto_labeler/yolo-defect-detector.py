"""YOLOv8 inference wrapper for defect detection.

Loads a trained YOLOv8 model and runs batch inference on X-ray images,
returning DetectionResult objects filtered by confidence threshold.
"""

import logging
from pathlib import Path
from typing import List, Optional, Callable

import cv2
import numpy as np
from importlib import import_module

_dataclass_mod = import_module(
    ".detection-result-dataclass", package="auto_labeler"
)
AutoLabelConfig = _dataclass_mod.AutoLabelConfig
DetectionResult = _dataclass_mod.DetectionResult

logger = logging.getLogger(__name__)


def load_yolo_model(weights_path: str, device: str = "cuda:0"):
    """Load a YOLOv8 model from weights file.

    Args:
        weights_path: Path to .pt weights file
        device: Torch device string

    Returns:
        Ultralytics YOLO model instance
    """
    try:
        from ultralytics import YOLO
    except ImportError:
        raise ImportError(
            "ultralytics not installed. Install with: pip install ultralytics"
        )

    if not Path(weights_path).exists():
        raise FileNotFoundError(f"YOLO weights not found: {weights_path}")

    model = YOLO(weights_path)
    model.to(device)
    logger.info(f"Loaded YOLO model from {weights_path} on {device}")
    logger.info(f"  Classes: {model.names}")
    return model


def detect_defects_single(
    model,
    image_path: str,
    confidence_threshold: float = 0.5,
    max_detections: int = 20,
) -> List[DetectionResult]:
    """Run YOLO inference on a single image.

    Args:
        model: Loaded YOLO model
        image_path: Path to image file
        confidence_threshold: Minimum confidence to keep
        max_detections: Maximum detections per image

    Returns:
        List of DetectionResult sorted by confidence descending
    """
    results = model(image_path, verbose=False)

    if not results or len(results) == 0:
        return []

    result = results[0]
    detections = []

    if result.boxes is None or len(result.boxes) == 0:
        return []

    boxes = result.boxes
    for i in range(len(boxes)):
        conf = float(boxes.conf[i])
        if conf < confidence_threshold:
            continue

        xyxy = boxes.xyxy[i].cpu().numpy().tolist()
        cls_id = int(boxes.cls[i])
        cls_name = model.names.get(cls_id, f"class_{cls_id}")

        detections.append(DetectionResult(
            bbox_xyxy=xyxy,
            confidence=conf,
            class_id=cls_id,
            class_name=cls_name,
        ))

    # Sort by confidence descending, limit count
    detections.sort(key=lambda d: d.confidence, reverse=True)
    return detections[:max_detections]


def detect_defects_batch(
    model,
    image_paths: List[str],
    config: AutoLabelConfig,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> dict:
    """Run YOLO inference on a batch of images.

    Args:
        model: Loaded YOLO model
        image_paths: List of image file paths
        config: Auto-label configuration
        progress_callback: Optional (current, total) callback

    Returns:
        Dict mapping image_path -> List[DetectionResult]
    """
    all_detections = {}
    total = len(image_paths)

    for idx, img_path in enumerate(image_paths):
        try:
            dets = detect_defects_single(
                model,
                img_path,
                confidence_threshold=config.confidence_threshold,
                max_detections=config.max_detections_per_image,
            )
            all_detections[img_path] = dets
        except Exception as e:
            logger.warning(f"Detection failed for {img_path}: {e}")
            all_detections[img_path] = []

        if progress_callback:
            progress_callback(idx + 1, total)

    total_dets = sum(len(d) for d in all_detections.values())
    logger.info(
        f"Detection complete: {total_dets} detections in {total} images"
    )
    return all_detections
