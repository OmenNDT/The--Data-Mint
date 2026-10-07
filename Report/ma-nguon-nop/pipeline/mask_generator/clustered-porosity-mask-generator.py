"""
Clustered Porosity defect mask generator.

Morphology: many small circular gas pores tightly grouped together.
Distinct from isolated porosity: higher pore count, Rayleigh-distributed scatter
creating a visible cluster pattern.
"""

import numpy as np
from typing import Tuple
from importlib import import_module
from scipy.ndimage import gaussian_filter

base_module = import_module('.base-defect-mask-generator', package='mask_generator')
feathering_module = import_module('.feathering-utility', package='mask_generator')

DefectMaskGenerator = base_module.DefectMaskGenerator
feather_mask = feathering_module.feather_mask


def _organic_pore_blob(rng, diameter: int) -> np.ndarray:
    """Create an organic (irregular) pore blob using Gaussian noise threshold."""
    noise = rng.normal(0, 1, (diameter, diameter))
    smoothed = gaussian_filter(noise, sigma=max(1.5, diameter * 0.25))
    smoothed = (smoothed - smoothed.min()) / (smoothed.max() - smoothed.min() + 1e-8)
    y, x = np.ogrid[:diameter, :diameter]
    c = diameter / 2
    falloff = np.clip(1 - np.sqrt((x - c) ** 2 + (y - c) ** 2) / c, 0, 1)
    return np.where(smoothed * falloff > 0.38, 255, 0).astype(np.uint8)


def _place_blob(mask, blob, cx, cy):
    """Stamp a blob array onto mask centered at (cx, cy)."""
    d = blob.shape[0]
    h, w = mask.shape
    half = d // 2
    y0, y1 = max(0, cy - half), min(h, cy + half)
    x0, x1 = max(0, cx - half), min(w, cx + half)
    by0 = half - (cy - y0)
    bx0 = half - (cx - x0)
    mask[y0:y1, x0:x1] = np.maximum(
        mask[y0:y1, x0:x1],
        blob[by0: by0 + (y1 - y0), bx0: bx0 + (x1 - x0)]
    )


class ClusteredPorosityMaskGenerator(DefectMaskGenerator):
    """
    Generator for clustered porosity defect masks.

    Morphology: many small circular gas pores tightly grouped together.
    Distinct from isolated porosity: higher pore count, Rayleigh-distributed scatter
    creating a visible cluster pattern.
    """

    def __init__(
        self,
        height: int = 512,
        width: int = 512,
        seed: int = None,
        count_range: Tuple[int, int] = (8, 25),
        radius_range: Tuple[int, int] = (8, 28),
        rayleigh_scale: float = 50.0,
        **kwargs
    ):
        super().__init__(height, width, seed, **kwargs)
        self.count_range = count_range
        self.radius_range = radius_range
        self.rayleigh_scale = rayleigh_scale

    def generate(self) -> Tuple[np.ndarray, np.ndarray]:
        """Generate clustered porosity: many pores around a common center."""
        mask = self._create_blank_mask()

        num_pores = self.rng.integers(self.count_range[0], self.count_range[1] + 1)

        # Cluster center within weld zone
        cluster_x = int(self.rng.integers(self.width // 5, 4 * self.width // 5))
        weld_half = int(self.height * 0.12)
        cluster_y = int(np.clip(
            self.weld_center_y + self.rng.integers(-weld_half, weld_half),
            weld_half, self.height - weld_half
        ))

        for _ in range(num_pores):
            distance = self.rng.rayleigh(self.rayleigh_scale)
            angle = self.rng.uniform(0, 2 * np.pi)
            pore_x = int(np.clip(cluster_x + distance * np.cos(angle), 0, self.width - 1))
            pore_y = int(np.clip(cluster_y + distance * np.sin(angle), 0, self.height - 1))
            radius = int(self.rng.integers(self.radius_range[0], self.radius_range[1] + 1))
            blob = _organic_pore_blob(self.rng, radius * 2)
            _place_blob(mask, blob, pore_x, pore_y)

        feathered = feather_mask(mask, blur_radius=2)
        return mask, feathered
