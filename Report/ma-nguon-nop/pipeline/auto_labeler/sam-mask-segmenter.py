"""SAM mask generation from YOLO bounding boxes.

Uses Segment Anything Model (SAM) to produce precise binary masks
from bounding box prompts provided by the YOLO detector.
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
SegmentedDetection = _dataclass_mod.SegmentedDetection
ImageAutoLabelResult = _dataclass_mod.ImageAutoLabelResult

logger = logging.getLogger(__name__)


def load_sam_model(
    checkpoint_path: str,
    model_type: str = "vit_b",
    device: str = "cuda:0",
):
    """Load SAM model from checkpoint.

    Args:
        checkpoint_path: Path to SAM .pth weights
        model_type: One of vit_b, vit_l, vit_h
        device: Torch device string

    Returns:
        Tuple of (sam_model, SamPredictor)
    """
    try:
        from segment_anything import sam_model_registry, SamPredictor
    except ImportError:
        raise ImportError(
            "segment-anything not installed. "
            "Install with: pip install segment-anything"
        )

    if not Path(checkpoint_path).exists():
        raise FileNotFoundError(f"SAM checkpoint not found: {checkpoint_path}")

    valid_types = ("vit_b", "vit_l", "vit_h")
    if model_type not in valid_types:
        raise ValueError(f"sam_model_type must be one of {valid_types}")

    sam = sam_model_registry[model_type](checkpoint=checkpoint_path)
    sam.to(device=device)
    predictor = SamPredictor(sam)

    logger.info(f"Loaded SAM {model_type} from {checkpoint_path} on {device}")
    return sam, predictor


def _segment_single_bbox(
    predictor,
    bbox_xyxy: List[float],
) -> Optional[np.ndarray]:
    """Generate mask for one bounding box using the already-set image.

    Args:
        predictor: SamPredictor with image already set
        bbox_xyxy: [x1, y1, x2, y2] absolute pixels

    Returns:
        Binary mask (H, W) uint8 with values 0/255, or None on failure
    """
    import torch

    box_np = np.array(bbox_xyxy, dtype=np.float32)
    box_torch = torch.tensor(box_np, device=predictor.device).unsqueeze(0)

    masks, scores, _ = predictor.predict_torch(
        point_coords=None,
        point_labels=None,
        boxes=box_torch,
        multimask_output=False,
    )

    # masks shape: (1, 1, H, W) — take best mask
    mask = masks[0, 0].cpu().numpy().astype(np.uint8) * 255
    return mask


def generate_masks_for_image(
    predictor,
    image_path: str,
    detections: List[DetectionResult],
) -> ImageAutoLabelResult:
    """Generate SAM masks for all detections in one image.

    Args:
        predictor: SamPredictor instance
        image_path: Path to source image
        detections: YOLO detections for this image

    Returns:
        ImageAutoLabelResult with segmented detections
    """
    image_path = Path(image_path)
    image_bgr = cv2.imread(str(image_path))

    if image_bgr is None:
        return ImageAutoLabelResult(
            image_path=image_path,
            image_width=0,
            image_height=0,
            error=f"Failed to read image: {image_path}",
        )

    h, w = image_bgr.shape[:2]
    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)

    # Set image once for all boxes
    predictor.set_image(image_rgb)

    segmented = []
    for det in detections:
        try:
            mask = _segment_single_bbox(predictor, det.bbox_xyxy)
            if mask is not None:
                area = int(np.sum(mask > 0))
                segmented.append(SegmentedDetection(
                    detection=det,
                    mask=mask,
                    mask_area=area,
                ))
        except Exception as e:
            logger.warning(
                f"SAM failed for bbox {det.bbox_xyxy} in {image_path}: {e}"
            )

    return ImageAutoLabelResult(
        image_path=image_path,
        image_width=w,
        image_height=h,
        detections=segmented,
    )


def generate_masks_from_bboxes(
    predictor,
    detection_map: dict,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> List[ImageAutoLabelResult]:
    """Generate SAM masks for all images in a detection map.

    Args:
        predictor: SamPredictor instance
        detection_map: Dict[image_path, List[DetectionResult]]
        progress_callback: Optional (current, total) callback

    Returns:
        List of ImageAutoLabelResult
    """
    results = []
    total = len(detection_map)

    for idx, (img_path, detections) in enumerate(detection_map.items()):
        if not detections:
            # No detections — still record the image
            img = cv2.imread(str(img_path))
            h, w = (img.shape[:2]) if img is not None else (0, 0)
            results.append(ImageAutoLabelResult(
                image_path=Path(img_path),
                image_width=w,
                image_height=h,
            ))
        else:
            result = generate_masks_for_image(predictor, img_path, detections)
            results.append(result)

        if progress_callback:
            progress_callback(idx + 1, total)

    total_masks = sum(r.num_detections for r in results)
    logger.info(f"SAM complete: {total_masks} masks for {total} images")
    return results
