"""
Base class for all defect mask generators.

Defines common interface and shared utilities for generating
procedural binary masks for weld defect types.
"""

import numpy as np
from abc import ABC, abstractmethod
from typing import Tuple


class DefectMaskGenerator(ABC):
    """Abstract base class for defect-specific mask generators."""

    def __init__(self, height: int = 512, width: int = 512, seed: int = None, weld_center_y: int = None, **kwargs):
        """
        Initialize mask generator.

        Args:
            height: Output mask height in pixels
            width: Output mask width in pixels
            seed: Random seed for reproducibility
            weld_center_y: Y-coordinate of weld bead center (auto-detected from background).
                           Falls back to height//2 if not provided.
            **kwargs: Additional defect-specific parameters
        """
        self.height = height
        self.width = width
        self.rng = np.random.default_rng(seed)
        # Clamp weld_center_y to safe margin so mask generators never create zero-row slices
        margin = max(10, height // 8)
        raw_y = weld_center_y if weld_center_y is not None else height // 2
        self.weld_center_y = int(np.clip(raw_y, margin, height - margin))
        self.params = kwargs

    @abstractmethod
    def generate(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Generate defect mask.

        Returns:
            Tuple of (binary_mask, feathered_mask):
                - binary_mask: Sharp binary mask (0 or 255), uint8, for annotation
                - feathered_mask: Gaussian-blurred mask (0-255), uint8, for inpainting
        """
        raise NotImplementedError("Subclasses must implement generate()")

    def _create_blank_mask(self) -> np.ndarray:
        """Create blank mask canvas."""
        return np.zeros((self.height, self.width), dtype=np.uint8)

    def _binarize_mask(self, mask: np.ndarray, threshold: int = 127) -> np.ndarray:
        """Convert grayscale mask to binary (0 or 255)."""
        binary = np.where(mask > threshold, 255, 0).astype(np.uint8)
        return binary
