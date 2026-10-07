"""
Linear Slag Inclusion defect mask generator.

Morphology: 3-6 slag blobs arranged in a horizontal row along the weld axis.
Distinct from SlagInclusionMaskGenerator (single blob) — here blobs align
in a line, simulating slag trapped along a linear welding pass boundary.
Scale: 1px ≈ 0.1mm → diameter 20-100px covers 2-10mm per blob.
"""

import numpy as np
from typing import Tuple
from scipy.ndimage import gaussian_filter
from importlib import import_module

base_module = import_module('.base-defect-mask-generator', package='mask_generator')
feathering_module = import_module('.feathering-utility', package='mask_generator')

DefectMaskGenerator = base_module.DefectMaskGenerator
feather_mask = feathering_module.feather_mask


class LinearSlagInclusionMaskGenerator(DefectMaskGenerator):
    """
    Generator for linear slag inclusion defect masks.

    Morphology: 3-6 slag blobs arranged in a horizontal row along the weld axis.
    Distinct from SlagInclusionMaskGenerator (single blob) — here blobs align
    in a line, simulating slag trapped along a linear welding pass boundary.
    """

    def __init__(
        self,
        height: int = 512,
        width: int = 512,
        seed: int = None,
        count_range: Tuple[int, int] = (3, 6),
        diameter_range: Tuple[int, int] = (20, 100),
        vertical_scatter: float = 5.0,
        length_pct_range: Tuple[float, float] = (0.25, 0.65),
        gaussian_sigma: float = 2.0,
        threshold: float = 0.4,
        **kwargs
    ):
        """
        Args:
            count_range: Number of slag blobs in the linear chain (3-6)
            diameter_range: Blob diameter range in pixels (20-100px = 2-10mm)
            vertical_scatter: Max vertical jitter around center line (pixels)
            length_pct_range: Length of the slag chain as fraction of image width
        """
        super().__init__(height, width, seed, **kwargs)
        self.count_range = count_range
        self.diameter_range = diameter_range
        self.vertical_scatter = vertical_scatter
        self.length_pct_range = length_pct_range
        self.gaussian_sigma = gaussian_sigma
        self.threshold = threshold

    def _create_blob(self, diameter: int) -> np.ndarray:
        """Create irregular slag blob using Gaussian noise threshold."""
        noise = self.rng.normal(0, 1, (diameter, diameter))
        smoothed = gaussian_filter(noise, sigma=self.gaussian_sigma)
        smoothed = (smoothed - smoothed.min()) / (smoothed.max() - smoothed.min() + 1e-8)
        y, x = np.ogrid[:diameter, :diameter]
        center = diameter / 2
        distance = np.sqrt((x - center) ** 2 + (y - center) ** 2)
        falloff = np.clip(1 - distance / center, 0, 1)
        combined = smoothed * falloff
        return np.where(combined > self.threshold, 255, 0).astype(np.uint8)

    def generate(self) -> Tuple[np.ndarray, np.ndarray]:
        """Generate linear slag inclusion mask — horizontal row of slag blobs."""
        mask = self._create_blank_mask()

        num_blobs = int(self.rng.integers(self.count_range[0], self.count_range[1] + 1))

        # Chain spans a horizontal segment within weld zone
        length_pct = self.rng.uniform(self.length_pct_range[0], self.length_pct_range[1])
        chain_length = int(self.width * length_pct)
        start_x = int(self.rng.integers(20, max(21, self.width - chain_length - 20)))
        center_y = int(self.weld_center_y + self.rng.integers(-25, 25))

        spacing = chain_length / max(num_blobs - 1, 1)

        for i in range(num_blobs):
            diameter = int(self.rng.integers(self.diameter_range[0], self.diameter_range[1] + 1))
            half_d = diameter // 2

            blob_x = int(np.clip(
                start_x + i * spacing + self.rng.uniform(-spacing * 0.2, spacing * 0.2),
                half_d, self.width - half_d
            ))
            blob_y = int(np.clip(
                center_y + self.rng.uniform(-self.vertical_scatter, self.vertical_scatter),
                half_d, self.height - half_d
            ))

            blob = self._create_blob(diameter)

            y_start = max(0, blob_y - half_d)
            y_end = min(self.height, blob_y + half_d)
            x_start = max(0, blob_x - half_d)
            x_end = min(self.width, blob_x + half_d)

            if y_end <= y_start or x_end <= x_start:
                continue

            blob_y_start = half_d - (blob_y - y_start)
            blob_x_start = half_d - (blob_x - x_start)
            blob_y_end = blob_y_start + (y_end - y_start)
            blob_x_end = blob_x_start + (x_end - x_start)

            mask[y_start:y_end, x_start:x_end] = np.maximum(
                mask[y_start:y_end, x_start:x_end],
                blob[blob_y_start:blob_y_end, blob_x_start:blob_x_end]
            )

        feathered = feather_mask(mask, blur_radius=4)
        return mask, feathered
