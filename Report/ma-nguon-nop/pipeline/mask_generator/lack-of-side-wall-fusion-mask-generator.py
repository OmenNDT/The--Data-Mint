"""
Lack of Side Wall Fusion (LOSWF) defect mask generator.

LOSWF morphology: an elongated, near-straight dark band running ALONG the
groove SIDE WALL (the bevelled face of the weld preparation). It is the
incomplete fusion between the deposited weld metal and the base-metal side wall.

Distinguishing features vs the related LoF / LoP defects:
  - LoP  : thin line dead-CENTER at the weld root, no tilt.
  - LoF  : short filled band 13-20% off-center, mild tilt (±20px).
  - LOSWF: band placed FURTHER off-center (18-28%, on the groove wall) and
           TILTED MORE STEEPLY to follow the bevel angle of the side wall.
           It is also LONGER and more CONTINUOUS/straight than LoF — it hugs
           the fusion line of the wall for most of its run.

Visually in RT: a long, slightly slanted dark stripe hugging one side of the
weld bead, with one sharp edge (the unbonded wall face) and one softer edge.
"""

import numpy as np
import cv2
from typing import Tuple
from importlib import import_module
from scipy.ndimage import uniform_filter1d

base_module = import_module('.base-defect-mask-generator', package='mask_generator')
feathering_module = import_module('.feathering-utility', package='mask_generator')

DefectMaskGenerator = base_module.DefectMaskGenerator
feather_mask = feathering_module.feather_mask


class LackOfSideWallFusionMaskGenerator(DefectMaskGenerator):
    """
    Generator for lack of side wall fusion (LOSWF) masks.

    Draws a long, near-straight filled band along the groove side wall:
      - Placed 18-28% off the weld centerline (on the bevel face)
      - Steeper tilt than LoF to follow the side-wall bevel angle
      - Longer and more continuous than LoF
      - One sharp edge (unbonded wall face), one slightly wavy edge
    """

    def __init__(
        self,
        height: int = 512,
        width: int = 512,
        seed: int = None,
        length_pct_range: Tuple[float, float] = (0.45, 0.80),
        band_width_range: Tuple[int, int] = (3, 8),
        tilt_range: Tuple[float, float] = (25.0, 60.0),
        wall_offset_range: Tuple[float, float] = (0.18, 0.28),
        **kwargs
    ):
        """
        Args:
            length_pct_range: Defect length as fraction of image width (longer than LoF).
            band_width_range: Band thickness in px (3-8px — narrower/sharper than LoF).
            tilt_range: (min, max) absolute y-displacement over full length in px —
                        steeper than LoF to follow the side-wall bevel.
            wall_offset_range: Off-center placement on the groove wall, as fraction
                               of height from the weld center (further out than LoF).
        """
        super().__init__(height, width, seed, **kwargs)
        self.length_pct_range = length_pct_range
        self.band_width_range = band_width_range
        self.tilt_range = tilt_range
        self.wall_offset_range = wall_offset_range

    def generate(self) -> Tuple[np.ndarray, np.ndarray]:
        """Generate LOSWF mask: long slanted band along the groove side wall."""
        mask = self._create_blank_mask()

        # Placement on the groove wall (further off-center than LoF)
        side = 1 if self.rng.random() < 0.5 else -1
        wall_offset = int(self.height * self.rng.uniform(*self.wall_offset_range))
        center_y = int(np.clip(
            self.weld_center_y + side * wall_offset, 20, self.height - 20
        ))

        # Length and start position (longer run than LoF)
        length_pct = self.rng.uniform(*self.length_pct_range)
        length = int(self.width * length_pct)
        x_start = int(self.rng.integers(15, max(16, self.width - length - 15)))
        x_end = x_start + length

        # Band width (3-8px — thin, sharp wall face)
        band_w = int(self.rng.integers(*self.band_width_range))

        # Steep tilt following the bevel angle; sign points toward the weld center
        tilt_mag = self.rng.uniform(*self.tilt_range)
        # Tilt the wall face so its deep end drifts toward the weld centerline
        tilt_dy = -side * tilt_mag

        n_pts = 48
        xs = np.linspace(x_start, x_end, n_pts)

        # Wall (fusion) face: straight, sharp — the unbonded bevel face in RT
        wall_ys = np.linspace(center_y, center_y + tilt_dy, n_pts)
        wn = self.rng.standard_normal(n_pts)
        wn_smooth = uniform_filter1d(wn, size=10)
        wall_ys += (wn_smooth / (wn_smooth.std() + 1e-8)) * 0.8  # ±0.8px sharp

        # Open face: parallel to wall face + mild roughness (diffuse weld-metal side)
        noise = self.rng.standard_normal(n_pts)
        noise_smooth = uniform_filter1d(noise, size=6)
        noise_scaled = (noise_smooth / (noise_smooth.std() + 1e-8)) * 1.5
        open_ys = wall_ys + side * band_w + noise_scaled

        # Clamp both edges
        wall_ys = np.clip(wall_ys, 3, self.height - 3)
        open_ys = np.clip(open_ys, 3, self.height - 3)

        # Closed polygon: wall face forward → open face backward
        wall_pts = [(int(xs[i]), int(wall_ys[i])) for i in range(n_pts)]
        open_pts = [(int(xs[i]), int(open_ys[i])) for i in range(n_pts - 1, -1, -1)]
        polygon = np.array(wall_pts + open_pts, dtype=np.int32)
        cv2.fillPoly(mask, [polygon], 255)

        # Light feather — keep the sharp wall edge visible (2px blur)
        feathered = feather_mask(mask, blur_radius=2)
        return mask, feathered
