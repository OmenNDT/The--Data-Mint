"""
Metallic Inclusion defect mask generator.

Morphology: single compact dense blob — typically tungsten or copper fragments
embedded in weld metal. Denser and more compact than slag inclusions.
Scale: 1px ≈ 0.1mm → diameter 15-60px covers 1.5-6mm.

Distinct from slag inclusion:
  - Smaller, denser, more compact shape
  - Higher threshold → sharper edges (metallic = hard fragment, not soft slag)
  - Typically single inclusion per occurrence
"""

import numpy as np
from typing import Tuple
from scipy.ndimage import gaussian_filter
from importlib import import_module

base_module = import_module('.base-defect-mask-generator', package='mask_generator')
feathering_module = import_module('.feathering-utility', package='mask_generator')

DefectMaskGenerator = base_module.DefectMaskGenerator
feather_mask = feathering_module.feather_mask


class MetallicInclusionMaskGenerator(DefectMaskGenerator):
    """
    Generator for metallic inclusion defect masks.

    Single compact blob simulating a metallic fragment (tungsten, copper)
    embedded in weld metal. More compact and sharper-edged than slag.
    """

    def __init__(
        self,
        height: int = 512,
        width: int = 512,
        seed: int = None,
        diameter_range: Tuple[int, int] = (15, 60),
        gaussian_sigma: float = 1.5,
        threshold: float = 0.5,
        **kwargs
    ):
        """
        Args:
            diameter_range: Blob diameter in pixels (15-60px = 1.5-6mm at 10px/mm)
            gaussian_sigma: Lower sigma → sharper, more compact blob (metallic fragment)
            threshold: Higher threshold → smaller, denser blob vs slag's 0.4
        """
        super().__init__(height, width, seed, **kwargs)
        self.diameter_range = diameter_range
        self.gaussian_sigma = gaussian_sigma
        self.threshold = threshold

    def _create_blob(self, diameter: int) -> np.ndarray:
        """Create compact metallic inclusion blob — sharper than slag blob."""
        noise = self.rng.normal(0, 1, (diameter, diameter))
        smoothed = gaussian_filter(noise, sigma=self.gaussian_sigma)
        smoothed = (smoothed - smoothed.min()) / (smoothed.max() - smoothed.min() + 1e-8)
        y, x = np.ogrid[:diameter, :diameter]
        center = diameter / 2
        distance = np.sqrt((x - center) ** 2 + (y - center) ** 2)
        # Sharper falloff (power=1.5) → more compact blob vs slag's linear falloff
        falloff = np.clip(1 - (distance / center) ** 1.5, 0, 1)
        combined = smoothed * falloff
        return np.where(combined > self.threshold, 255, 0).astype(np.uint8)

    def generate(self) -> Tuple[np.ndarray, np.ndarray]:
        """Generate single metallic inclusion mask."""
        mask = self._create_blank_mask()

        diameter = int(self.rng.integers(self.diameter_range[0], self.diameter_range[1] + 1))
        half_d = diameter // 2

        # Place within weld zone
        blob_x = int(np.clip(
            self.rng.integers(diameter, self.width - diameter),
            half_d, self.width - half_d
        ))
        blob_y = int(np.clip(
            self.weld_center_y + self.rng.integers(-60, 60),
            half_d, self.height - half_d
        ))

        blob = self._create_blob(diameter)

        y_start = max(0, blob_y - half_d)
        y_end = min(self.height, blob_y + half_d)
        x_start = max(0, blob_x - half_d)
        x_end = min(self.width, blob_x + half_d)

        if y_end > y_start and x_end > x_start:
            blob_y_start = half_d - (blob_y - y_start)
            blob_x_start = half_d - (blob_x - x_start)
            blob_y_end = blob_y_start + (y_end - y_start)
            blob_x_end = blob_x_start + (x_end - x_start)
            mask[y_start:y_end, x_start:x_end] = np.maximum(
                mask[y_start:y_end, x_start:x_end],
                blob[blob_y_start:blob_y_end, blob_x_start:blob_x_end]
            )

        # Light feather — metallic inclusions have sharper edges than slag
        feathered = feather_mask(mask, blur_radius=3)
        return mask, feathered
