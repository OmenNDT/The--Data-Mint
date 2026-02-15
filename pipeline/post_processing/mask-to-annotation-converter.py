#!/usr/bin/env python3
"""
Mask to Annotation Converter

Converts binary mask images to polygon and bounding box annotations.
Uses OpenCV contour detection to extract segmentation polygons from masks.
"""

import cv2
import numpy as np
from typing import Dict, List, Tuple, Optional


def mask_to_polygon(mask: np.ndarray) -> List[List[float]]:
    """
    Convert binary mask to polygon segmentation(s).

    Args:
        mask: Binary mask (H, W) with values 0 or 255

    Returns:
        List of polygons, where each polygon is [x1,y1,x2,y2,...,xn,yn]
    """
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    polygons = []

    for contour in contours:
        # Need at least 3 points to form a polygon (6 values)
        if contour.size >= 6:
            seg = contour.flatten().tolist()
            polygons.append(seg)

    return polygons


def mask_to_bbox(mask: np.ndarray) -> Optional[List[int]]:
    """
    Convert binary mask to bounding box in COCO format [x, y, width, height].

    Args:
        mask: Binary mask (H, W) with values 0 or 255

    Returns:
        [x, y, width, height] or None if mask is empty
    """
    pos = np.where(mask > 0)

    if len(pos[0]) == 0:
        return None

    y_min, y_max = int(np.min(pos[0])), int(np.max(pos[0]))
    x_min, x_max = int(np.min(pos[1])), int(np.max(pos[1]))

    width = x_max - x_min + 1
    height = y_max - y_min + 1

    return [x_min, y_min, width, height]


def mask_to_yolo_bbox(mask: np.ndarray, img_width: int, img_height: int) -> Optional[List[float]]:
    """
    Convert binary mask to YOLO format bbox [x_center, y_center, width, height] normalized.

    Args:
        mask: Binary mask (H, W)
        img_width: Image width for normalization
        img_height: Image height for normalization

    Returns:
        [x_center, y_center, width, height] normalized to [0, 1] or None if empty
    """
    pos = np.where(mask > 0)

    if len(pos[0]) == 0:
        return None

    y_min, y_max = int(np.min(pos[0])), int(np.max(pos[0]))
    x_min, x_max = int(np.min(pos[1])), int(np.max(pos[1]))

    x_center = ((x_min + x_max) / 2) / img_width
    y_center = ((y_min + y_max) / 2) / img_height
    width = (x_max - x_min + 1) / img_width
    height = (y_max - y_min + 1) / img_height

    return [x_center, y_center, width, height]


def mask_to_area(mask: np.ndarray) -> int:
    """
    Calculate mask area (number of pixels > 0).

    Args:
        mask: Binary mask (H, W)

    Returns:
        Number of foreground pixels
    """
    return int(np.sum(mask > 0))


def mask_to_annotation(
    mask_path: str,
    defect_type: str,
    category_map: Dict[str, int],
    format: str = "coco"
) -> Dict:
    """
    Convert mask file to annotation dictionary.

    Args:
        mask_path: Path to binary mask PNG file
        defect_type: Defect type name (e.g., 'crack', 'porosity')
        category_map: Dict mapping defect_type to category_id
        format: 'coco' or 'yolo'

    Returns:
        Annotation dict with polygon, bbox, area (COCO) or normalized bbox (YOLO)
    """
    mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)

    if mask is None:
        raise ValueError(f"Failed to load mask: {mask_path}")

    h, w = mask.shape

    if format == "coco":
        polygons = mask_to_polygon(mask)
        bbox = mask_to_bbox(mask)
        area = mask_to_area(mask)

        return {
            "segmentation": polygons,
            "bbox": bbox if bbox else [0, 0, 0, 0],
            "area": area,
            "category_id": category_map[defect_type],
            "iscrowd": 0
        }

    elif format == "yolo":
        yolo_bbox = mask_to_yolo_bbox(mask, w, h)

        if yolo_bbox is None:
            return None

        # YOLO uses 0-indexed class IDs
        class_id = category_map[defect_type] - 1

        return {
            "class_id": class_id,
            "bbox": yolo_bbox  # [x_center, y_center, width, height] normalized
        }

    else:
        raise ValueError(f"Unknown format: {format}")
