"""
Linear Porosity defect mask generator.

Morphology: pores arranged in a linear chain along the weld axis.
Distinct from clustered_porosity (random scatter) — here pores align
in a horizontal row, simulating wormhole porosity or aligned gas pockets.
"""

import numpy as np
import cv2
from scipy.ndimage import gaussian_filter
from typing import Tuple
from importlib import import_module

base_module = import_module('.base-defect-mask-generator', package='mask_generator')
feathering_module = import_module('.feathering-utility', package='mask_generator')


def _organic_pore_blob(rng, diameter: int) -> np.ndarray:
    """Create an organic (irregular) pore blob using gaussian noise threshold."""
    noise = rng.normal(0, 1, (diameter, diameter))
    from scipy.ndimage import gaussian_filter as _gf
    smoothed = _gf(noise, sigma=max(1.5, diameter * 0.25))
    smoothed = (smoothed - smoothed.min()) / (smoothed.max() - smoothed.min() + 1e-8)
    y, x = np.ogrid[:diameter, :diameter]
    c = diameter / 2
    falloff = np.clip(1 - np.sqrt((x - c) ** 2 + (y - c) ** 2) / c, 0, 1)
    return np.where(smoothed * falloff > 0.38, 255, 0).astype(np.uint8)


def _place_blob(mask, blob, cx, cy):
    """Stamp blob onto mask centered at (cx, cy)."""
    d = blob.shape[0]; h, w = mask.shape; half = d // 2
    y0, y1 = max(0, cy - half), min(h, cy + half)
    x0, x1 = max(0, cx - half), min(w, cx + half)
    by0 = half - (cy - y0); bx0 = half - (cx - x0)
    mask[y0:y1, x0:x1] = np.maximum(mask[y0:y1, x0:x1],
                                      blob[by0: by0 + (y1 - y0), bx0: bx0 + (x1 - x0)])

DefectMaskGenerator = base_module.DefectMaskGenerator
feather_mask = feathering_module.feather_mask


class LinearPorosityMaskGenerator(DefectMaskGenerator):
    """Generator for linear porosity defect masks.

    Pores are arranged in a roughly horizontal line along the weld axis,
    with slight vertical scatter to look natural. Not a random cluster.
    """

    def __init__(
        self,
        height: int = 512,
        width: int = 512,
        seed: int = None,
        count_range: Tuple[int, int] = (5, 15),
        radius_range: Tuple[int, int] = (8, 28),
        vertical_scatter: float = 4.0,
        length_pct_range: Tuple[float, float] = (0.3, 0.7),
        **kwargs
    ):
        """
        Args:
            count_range: Number of pores in the linear chain
            radius_range: Pore radius in pixels
            vertical_scatter: Max vertical jitter around center line (pixels)
            length_pct_range: Length of the pore chain as fraction of image width
        """
        super().__init__(height, width, seed, **kwargs)
        self.count_range = count_range
        self.radius_range = radius_range
        self.vertical_scatter = vertical_scatter
        self.length_pct_range = length_pct_range

    def generate(self) -> Tuple[np.ndarray, np.ndarray]:
        """Generate linear porosity mask — horizontal chain of pores."""
        mask = self._create_blank_mask()

        num_pores = self.rng.integers(self.count_range[0], self.count_range[1] + 1)

        # Linear chain spans a horizontal segment within weld zone
        length_pct = self.rng.uniform(self.length_pct_range[0], self.length_pct_range[1])
        chain_length = int(self.width * length_pct)

        # Start x, centered vertically in weld zone
        start_x = self.rng.integers(0, max(1, self.width - chain_length))
        center_y = self.weld_center_y + self.rng.integers(-30, 30)

        # Distribute pores evenly along chain with slight jitter
        spacing = chain_length / max(num_pores - 1, 1)
        for i in range(num_pores):
            x = int(start_x + i * spacing + self.rng.uniform(-spacing * 0.2, spacing * 0.2))
            y = int(center_y + self.rng.uniform(-self.vertical_scatter, self.vertical_scatter))
            x = int(np.clip(x, 0, self.width - 1))
            y = int(np.clip(y, 0, self.height - 1))
            radius = int(self.rng.integers(self.radius_range[0], self.radius_range[1] + 1))
            blob = _organic_pore_blob(self.rng, radius * 2)
            _place_blob(mask, blob, x, y)

        feathered = feather_mask(mask, blur_radius=2)
        return mask, feathered
