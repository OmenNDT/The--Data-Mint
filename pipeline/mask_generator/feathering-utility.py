"""
Mask edge feathering utility.

Applies Gaussian blur to binary mask edges for seamless inpainting blending.
"""

import numpy as np
import cv2


def feather_mask(binary_mask: np.ndarray, blur_radius: int = 5) -> np.ndarray:
    """
    Apply Gaussian blur to mask edges for smooth blending.

    Args:
        binary_mask: Sharp binary mask (0 or 255), uint8
        blur_radius: Gaussian blur kernel radius in pixels

    Returns:
        Feathered mask with soft edges (0-255), uint8
    """
    # Convert to float for blurring
    mask_float = binary_mask.astype(np.float32) / 255.0

    # Apply Gaussian blur
    kernel_size = blur_radius * 2 + 1
    blurred = cv2.GaussianBlur(mask_float, (kernel_size, kernel_size), 0)

    # Convert back to uint8
    feathered = (blurred * 255).astype(np.uint8)

    return feathered
