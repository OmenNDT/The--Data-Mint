"""
Porosity defect mask generator.

Generates clustered gas pore patterns using Rayleigh-distributed circles.
Morphology: multiple small circular voids scattered around cluster center.
"""

import numpy as np
import cv2
from typing import Tuple
from importlib import import_module

base_module = import_module('.base-defect-mask-generator', package='mask_generator')
feathering_module = import_module('.feathering-utility', package='mask_generator')

DefectMaskGenerator = base_module.DefectMaskGenerator
feather_mask = feathering_module.feather_mask


class PorosityMaskGenerator(DefectMaskGenerator):
    """Generator for porosity defect masks."""

    def __init__(
        self,
        height: int = 512,
        width: int = 512,
        seed: int = None,
        count_range: Tuple[int, int] = (5, 30),
        radius_range: Tuple[int, int] = (2, 8),
        rayleigh_scale: float = 30.0,
        **kwargs
    ):
        """
        Initialize porosity mask generator.

        Args:
            count_range: Number of gas pores to generate
            radius_range: Pore radius range in pixels
            rayleigh_scale: Rayleigh distribution scale for scatter distance
        """
        super().__init__(height, width, seed, **kwargs)
        self.count_range = count_range
        self.radius_range = radius_range
        self.rayleigh_scale = rayleigh_scale

    def generate(self) -> Tuple[np.ndarray, np.ndarray]:
        """Generate porosity mask with clustered circles."""
        mask = self._create_blank_mask()

        # Random parameters
        num_pores = self.rng.integers(self.count_range[0], self.count_range[1] + 1)

        # Cluster center (within central weld zone)
        cluster_x = self.rng.integers(self.width // 4, 3 * self.width // 4)
        cluster_y = self.height // 2 + self.rng.integers(-50, 50)

        # Generate pores around cluster center
        for _ in range(num_pores):
            # Rayleigh-distributed distance from cluster center
            distance = self.rng.rayleigh(self.rayleigh_scale)
            angle = self.rng.uniform(0, 2 * np.pi)

            # Pore position
            pore_x = int(cluster_x + distance * np.cos(angle))
            pore_y = int(cluster_y + distance * np.sin(angle))

            # Clamp to image bounds
            pore_x = np.clip(pore_x, 0, self.width - 1)
            pore_y = np.clip(pore_y, 0, self.height - 1)

            # Random pore radius
            radius = self.rng.integers(self.radius_range[0], self.radius_range[1] + 1)

            # Draw circle
            cv2.circle(mask, (pore_x, pore_y), radius, color=255, thickness=-1)

        # Create feathered version
        feathered = feather_mask(mask, blur_radius=4)

        return mask, feathered
