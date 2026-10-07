"""
Weld Region of Interest (ROI) constraint utilities.

Defines the weld zone as a horizontal band where defects can appear.
Prevents defects from appearing in base metal regions.
"""

import numpy as np


def create_weld_roi_mask(
    height: int = 512,
    width: int = 512,
    center_offset: int = 0,
    zone_height_pct: float = 0.4
) -> np.ndarray:
    """
    Create binary mask defining weld zone ROI.

    Args:
        height: Image height
        width: Image width
        center_offset: Vertical offset from image center (positive = down)
        zone_height_pct: Weld zone height as fraction of image height

    Returns:
        Binary mask (255 in weld zone, 0 elsewhere)
    """
    mask = np.zeros((height, width), dtype=np.uint8)

    # Calculate weld zone boundaries
    center_y = height // 2 + center_offset
    zone_height = int(height * zone_height_pct)
    half_zone = zone_height // 2

    y_start = max(0, center_y - half_zone)
    y_end = min(height, center_y + half_zone)

    # Fill weld zone
    mask[y_start:y_end, :] = 255

    return mask


def apply_weld_roi(mask: np.ndarray, roi_mask: np.ndarray) -> np.ndarray:
    """
    Apply weld ROI constraint to defect mask.

    Args:
        mask: Defect mask to constrain
        roi_mask: Weld ROI mask from create_weld_roi_mask()

    Returns:
        Constrained mask (defect pixels only in weld zone)
    """
    return np.bitwise_and(mask, roi_mask)
