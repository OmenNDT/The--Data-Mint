"""
Elongated Cavity defect mask generator.

Morphology: irregular elongated void (wormhole / piping porosity).
Real elongated cavities are NOT perfect ellipses. Key features:
  - Curved axis (quadratic bezier, not straight)
  - Irregular outline (boundary noise ±2.5px)
  - Asymmetric tapered ends (one end more pointed — tear-drop profile)
  - Width variation along length (±15% noise)
  - Aspect ratio 3:1 to 7:1

Visually distinct from perfect cv2.ellipse() output.
"""

import numpy as np
import cv2
from typing import Tuple
from importlib import import_module

base_module = import_module('.base-defect-mask-generator', package='mask_generator')
feathering_module = import_module('.feathering-utility', package='mask_generator')

DefectMaskGenerator = base_module.DefectMaskGenerator
feather_mask = feathering_module.feather_mask


class ElongatedCavityMaskGenerator(DefectMaskGenerator):
    """
    Generator for elongated cavity defect masks.

    Uses a bezier-curved axis with an asymmetric gaussian width profile
    plus boundary noise. Produces realistic wormhole shapes instead of
    perfect geometric ellipses.
    """

    def __init__(
        self,
        height: int = 512,
        width: int = 512,
        seed: int = None,
        count_range: Tuple[int, int] = (1, 2),
        length_range: Tuple[int, int] = (55, 130),
        max_width_range: Tuple[int, int] = (10, 22),
        axis_curve_px: float = 10.0,
        **kwargs
    ):
        """
        Args:
            count_range: Number of cavities per mask (1-2 is realistic)
            length_range: Total cavity length in pixels
            max_width_range: Peak width at widest point in pixels
            axis_curve_px: Max perpendicular displacement of bezier midpoint
        """
        super().__init__(height, width, seed, **kwargs)
        self.count_range = count_range
        self.length_range = length_range
        self.max_width_range = max_width_range
        self.axis_curve_px = axis_curve_px

    def _quadratic_bezier(
        self,
        p0: Tuple[float, float],
        p1: Tuple[float, float],
        p2: Tuple[float, float],
        n: int = 60,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Sample n points along quadratic bezier p0 → p1 (control) → p2."""
        t = np.linspace(0, 1, n)
        x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t ** 2 * p2[0]
        y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t ** 2 * p2[1]
        return x, y

    def _draw_one_cavity(self, mask: np.ndarray) -> None:
        """Draw one irregular elongated cavity onto mask in-place."""
        length = int(self.rng.integers(*self.length_range))
        max_w = int(self.rng.integers(*self.max_width_range))

        # Center position within weld zone
        cx = int(self.rng.integers(length // 2 + 10, self.width - length // 2 - 10))
        cy = int(np.clip(
            self.weld_center_y + self.rng.integers(-35, 35),
            max_w + 5, self.height - max_w - 5
        ))

        # Bezier control points: slight curve on axis
        x_start = cx - length // 2
        x_end = cx + length // 2
        y_end_jitter = int(self.rng.integers(-6, 6))  # slight tilt at far end
        ctrl_x = (x_start + x_end) // 2 + int(self.rng.integers(-10, 10))
        ctrl_y = cy + int(self.rng.uniform(-self.axis_curve_px, self.axis_curve_px))

        n_pts = 60
        ax, ay = self._quadratic_bezier(
            (x_start, cy),
            (ctrl_x, ctrl_y),
            (x_end, cy + y_end_jitter),
            n=n_pts,
        )

        # Asymmetric gaussian width profile — peak at 30-45% from start
        # creates a pointed "tail" at the far end (tear-drop shape)
        t = np.linspace(0, 1, n_pts)
        peak_t = self.rng.uniform(0.28, 0.45)
        sigma = self.rng.uniform(0.20, 0.30)
        width_profile = max_w * np.exp(-((t - peak_t) ** 2) / (2 * sigma ** 2))

        # ±15% width noise for organic irregularity
        width_noise = 1.0 + self.rng.uniform(-0.15, 0.15, n_pts)
        widths = np.clip(width_profile * width_noise, 0.5, max_w)

        # Upper and lower contour with ±2.5px boundary noise
        bnd_noise_u = self.rng.uniform(-2.5, 2.5, n_pts)
        bnd_noise_l = self.rng.uniform(-2.5, 2.5, n_pts)
        upper_pts = np.column_stack([ax, ay - widths / 2 + bnd_noise_u])
        lower_pts = np.column_stack([ax, ay + widths / 2 + bnd_noise_l])

        # Closed polygon: upper forward + lower backward
        contour = np.vstack([upper_pts, lower_pts[::-1]])
        contour[:, 0] = np.clip(contour[:, 0], 2, self.width - 2)
        contour[:, 1] = np.clip(contour[:, 1], 2, self.height - 2)
        cv2.fillPoly(mask, [contour.astype(np.int32)], 255)

    def generate(self) -> Tuple[np.ndarray, np.ndarray]:
        """Generate elongated cavity mask — irregular wormhole shapes."""
        mask = self._create_blank_mask()

        num_cavities = int(self.rng.integers(self.count_range[0], self.count_range[1] + 1))
        for _ in range(num_cavities):
            self._draw_one_cavity(mask)

        feathered = feather_mask(mask, blur_radius=12)
        return mask, feathered
