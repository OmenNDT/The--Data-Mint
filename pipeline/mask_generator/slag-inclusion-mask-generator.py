"""
Slag Inclusion defect mask generator.

Generates irregular blob-shaped inclusions using Gaussian noise threshold.
Morphology: organic-looking blobs with smooth edges.
"""

import numpy as np
import cv2
from typing import Tuple
from scipy.ndimage import gaussian_filter
from importlib import import_module

base_module = import_module('.base-defect-mask-generator', package='mask_generator')
feathering_module = import_module('.feathering-utility', package='mask_generator')

DefectMaskGenerator = base_module.DefectMaskGenerator
feather_mask = feathering_module.feather_mask


class SlagInclusionMaskGenerator(DefectMaskGenerator):
    """Generator for slag inclusion defect masks."""

    def __init__(
        self,
        height: int = 512,
        width: int = 512,
        seed: int = None,
        blob_count_range: Tuple[int, int] = (1, 3),
        diameter_range: Tuple[int, int] = (10, 50),
        gaussian_sigma: float = 2.0,
        threshold: float = 0.4,
        **kwargs
    ):
        """
        Initialize slag inclusion mask generator.

        Args:
            blob_count_range: Number of inclusion blobs to generate
            diameter_range: Blob diameter range in pixels
            gaussian_sigma: Gaussian smoothing sigma for blob edges
            threshold: Threshold for binarizing noise (0-1)
        """
        super().__init__(height, width, seed, **kwargs)
        self.blob_count_range = blob_count_range
        self.diameter_range = diameter_range
        self.gaussian_sigma = gaussian_sigma
        self.threshold = threshold

    def generate(self) -> Tuple[np.ndarray, np.ndarray]:
        """Generate slag inclusion mask using Gaussian noise threshold."""
        mask = self._create_blank_mask()

        # Random parameters
        num_blobs = self.rng.integers(self.blob_count_range[0], self.blob_count_range[1] + 1)

        for _ in range(num_blobs):
            # Random blob size and position
            diameter = self.rng.integers(self.diameter_range[0], self.diameter_range[1] + 1)
            blob_x = self.rng.integers(diameter, self.width - diameter)
            blob_y = self.height // 2 + self.rng.integers(-80, 80)

            # Create blob using Gaussian noise
            blob_mask = self._create_blob(diameter)

            # Calculate placement bounds
            half_d = diameter // 2
            y_start = max(0, blob_y - half_d)
            y_end = min(self.height, blob_y + half_d)
            x_start = max(0, blob_x - half_d)
            x_end = min(self.width, blob_x + half_d)

            # Calculate blob crop region (handle boundary clipping)
            blob_y_start = max(0, half_d - blob_y)
            blob_y_end = blob_y_start + (y_end - y_start)
            blob_x_start = max(0, half_d - blob_x)
            blob_x_end = blob_x_start + (x_end - x_start)

            # Place blob on mask
            mask[y_start:y_end, x_start:x_end] = np.maximum(
                mask[y_start:y_end, x_start:x_end],
                blob_mask[blob_y_start:blob_y_end, blob_x_start:blob_x_end]
            )

        # Create feathered version
        feathered = feather_mask(mask, blur_radius=5)

        return mask, feathered

    def _create_blob(self, diameter: int) -> np.ndarray:
        """
        Create irregular blob using Gaussian noise threshold.

        Args:
            diameter: Blob diameter in pixels

        Returns:
            Binary blob mask
        """
        # Generate Gaussian noise
        noise = self.rng.normal(0, 1, (diameter, diameter))

        # Smooth with Gaussian filter for organic shape
        smoothed = gaussian_filter(noise, sigma=self.gaussian_sigma)

        # Normalize to 0-1
        smoothed = (smoothed - smoothed.min()) / (smoothed.max() - smoothed.min() + 1e-8)

        # Apply circular falloff (edges fade out)
        y, x = np.ogrid[:diameter, :diameter]
        center = diameter / 2
        distance = np.sqrt((x - center)**2 + (y - center)**2)
        falloff = np.clip(1 - distance / center, 0, 1)

        # Combine noise with falloff
        combined = smoothed * falloff

        # Threshold to binary
        blob = np.where(combined > self.threshold, 255, 0).astype(np.uint8)

        return blob
