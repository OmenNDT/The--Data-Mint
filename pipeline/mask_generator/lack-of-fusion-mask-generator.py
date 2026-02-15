"""
Lack of Fusion (LoF) defect mask generator.

Generates linear indications along weld fusion boundaries.
Morphology: parallel lines near weld edges, slight waviness.
"""

import numpy as np
import cv2
from typing import Tuple
from importlib import import_module

base_module = import_module('.base-defect-mask-generator', package='mask_generator')
feathering_module = import_module('.feathering-utility', package='mask_generator')

DefectMaskGenerator = base_module.DefectMaskGenerator
feather_mask = feathering_module.feather_mask


class LackOfFusionMaskGenerator(DefectMaskGenerator):
    """Generator for lack of fusion defect masks."""

    def __init__(
        self,
        height: int = 512,
        width: int = 512,
        seed: int = None,
        length_pct_range: Tuple[float, float] = (0.2, 0.6),
        thickness_range: Tuple[int, int] = (2, 5),
        position: str = "fusion_boundary",
        wave_amplitude: float = 3.0,
        wave_frequency: float = 0.05,
        **kwargs
    ):
        """
        Initialize lack of fusion mask generator.

        Args:
            length_pct_range: Line length as fraction of image width
            thickness_range: Line thickness in pixels
            position: "fusion_boundary" (top/bottom edge) or "center"
            wave_amplitude: Sine wave amplitude for waviness
            wave_frequency: Sine wave frequency (cycles per pixel)
        """
        super().__init__(height, width, seed, **kwargs)
        self.length_pct_range = length_pct_range
        self.thickness_range = thickness_range
        self.position = position
        self.wave_amplitude = wave_amplitude
        self.wave_frequency = wave_frequency

    def generate(self) -> Tuple[np.ndarray, np.ndarray]:
        """Generate lack of fusion mask with wavy line."""
        mask = self._create_blank_mask()

        # Random parameters
        length_pct = self.rng.uniform(self.length_pct_range[0], self.length_pct_range[1])
        line_length = int(self.width * length_pct)
        thickness = self.rng.integers(self.thickness_range[0], self.thickness_range[1] + 1)

        # Starting position
        start_x = self.rng.integers(0, self.width - line_length)

        # Y position (fusion boundary - top or bottom of weld zone)
        if self.position == "fusion_boundary":
            # Choose top or bottom edge of weld zone
            if self.rng.random() < 0.5:
                base_y = int(self.height * 0.35)  # Top boundary
            else:
                base_y = int(self.height * 0.65)  # Bottom boundary
        else:
            base_y = self.height // 2

        # Generate wavy line points
        points = []
        for i in range(line_length):
            x = start_x + i
            # Add sine wave perturbation
            y_offset = self.wave_amplitude * np.sin(2 * np.pi * self.wave_frequency * i)
            y = int(base_y + y_offset + self.rng.uniform(-2, 2))  # Add random noise
            y = np.clip(y, 0, self.height - 1)
            points.append([x, y])

        # Draw polyline
        points_array = np.array(points, dtype=np.int32).reshape((-1, 1, 2))
        cv2.polylines(mask, [points_array], isClosed=False, color=255, thickness=thickness)

        # Create feathered version
        feathered = feather_mask(mask, blur_radius=4)

        return mask, feathered
