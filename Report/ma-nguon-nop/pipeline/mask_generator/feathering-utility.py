"""
Mask edge feathering and dilation utility.

Applies Gaussian blur to binary mask edges for seamless inpainting blending.
Provides mask dilation for expanding thin masks before inpainting.
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


def dilate_mask_for_inpainting(
    binary_mask: np.ndarray,
    kernel_size: int = 21,
    kernel_shape: str = "ellipse",
    feather_blur_radius: int = 7,
) -> np.ndarray:
    """
    Dilate a thin binary mask and feather edges for inpainting.

    Thin masks (1-4px) give the inpainting model too little area to generate
    visible defects. This expands the mask so the model has enough room,
    then feathers edges for seamless blending.

    Args:
        binary_mask: Sharp binary mask (0 or 255), uint8
        kernel_size: Dilation kernel diameter in pixels (odd number)
        kernel_shape: "ellipse", "rect", or "cross"
        feather_blur_radius: Gaussian blur radius after dilation

    Returns:
        Dilated and feathered mask (0-255), uint8
    """
    # Build structuring element
    shapes = {
        "ellipse": cv2.MORPH_ELLIPSE,
        "rect": cv2.MORPH_RECT,
        "cross": cv2.MORPH_CROSS,
    }
    morph_shape = shapes.get(kernel_shape, cv2.MORPH_ELLIPSE)
    kernel = cv2.getStructuringElement(morph_shape, (kernel_size, kernel_size))

    # Dilate binary mask
    dilated = cv2.dilate(binary_mask, kernel, iterations=1)

    # Feather the dilated mask for smooth inpainting transition
    feathered = feather_mask(dilated, blur_radius=feather_blur_radius)

    return feathered
