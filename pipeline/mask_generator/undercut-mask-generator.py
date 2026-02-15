"""
Undercut defect mask generator.

Generates edge-aligned linear groove indications.
Morphology: linear depression along weld toe (edge of weld bead).
"""

import numpy as np
import cv2
from typing import Tuple
from importlib import import_module

base_module = import_module('.base-defect-mask-generator', package='mask_generator')
feathering_module = import_module('.feathering-utility', package='mask_generator')

DefectMaskGenerator = base_module.DefectMaskGenerator
feather_mask = feathering_module.feather_mask


class UndercutMaskGenerator(DefectMaskGenerator):
    """Generator for undercut defect masks."""

    def __init__(
        self,
        height: int = 512,
        width: int = 512,
        seed: int = None,
        length_pct_range: Tuple[float, float] = (0.2, 0.5),
        thickness_range: Tuple[int, int] = (2, 4),
        edge_offset_range: Tuple[int, int] = (5, 15),
        **kwargs
    ):
        """
        Initialize undercut mask generator.

        Args:
            length_pct_range: Line length as fraction of image width
            thickness_range: Line thickness in pixels
            edge_offset_range: Distance from weld edge in pixels
        """
        super().__init__(height, width, seed, **kwargs)
        self.length_pct_range = length_pct_range
        self.thickness_range = thickness_range
        self.edge_offset_range = edge_offset_range

    def generate(self) -> Tuple[np.ndarray, np.ndarray]:
        """Generate undercut mask along weld edge."""
        mask = self._create_blank_mask()

        # Random parameters
        length_pct = self.rng.uniform(self.length_pct_range[0], self.length_pct_range[1])
        line_length = int(self.width * length_pct)
        thickness = self.rng.integers(self.thickness_range[0], self.thickness_range[1] + 1)

        # Starting position
        start_x = self.rng.integers(0, self.width - line_length)

        # Y position (along weld toe - just outside weld zone)
        edge_offset = self.rng.integers(self.edge_offset_range[0], self.edge_offset_range[1])
        if self.rng.random() < 0.5:
            # Top edge of weld
            base_y = int(self.height * 0.35) - edge_offset
        else:
            # Bottom edge of weld
            base_y = int(self.height * 0.65) + edge_offset

        # Generate slightly irregular line (less wavy than LoF)
        points = []
        for i in range(line_length):
            x = start_x + i
            y = int(base_y + self.rng.uniform(-1, 1))  # Minimal variation
            y = np.clip(y, 0, self.height - 1)
            points.append([x, y])

        # Draw polyline
        points_array = np.array(points, dtype=np.int32).reshape((-1, 1, 2))
        cv2.polylines(mask, [points_array], isClosed=False, color=255, thickness=thickness)

        # Create feathered version
        feathered = feather_mask(mask, blur_radius=3)

        return mask, feathered
