"""
Crack defect mask generator.

Generates jagged linear crack patterns using random walk polylines.
Morphology: thin (1-4px), branching, chaotic orientation.
"""

import numpy as np
import cv2
from typing import Tuple
from importlib import import_module

base_module = import_module('.base-defect-mask-generator', package='mask_generator')
feathering_module = import_module('.feathering-utility', package='mask_generator')

DefectMaskGenerator = base_module.DefectMaskGenerator
feather_mask = feathering_module.feather_mask


class CrackMaskGenerator(DefectMaskGenerator):
    """Generator for crack defect masks."""

    def __init__(
        self,
        height: int = 512,
        width: int = 512,
        seed: int = None,
        width_range: Tuple[int, int] = (2, 4),
        length_pct_range: Tuple[float, float] = (0.10, 0.85),
        branch_probability: float = 0.2,
        angle_variation: float = 20.0,
        **kwargs
    ):
        """
        Initialize crack mask generator.

        Args:
            width_range: Crack line thickness range in pixels
            length_pct_range: Crack length as fraction of image width
            branch_probability: Probability of secondary branch (0-1)
            angle_variation: Max angle deviation from weld axis in degrees
        """
        super().__init__(height, width, seed, **kwargs)
        self.width_range = width_range
        self.length_pct_range = length_pct_range
        self.branch_probability = branch_probability
        self.angle_variation = angle_variation

    def generate(self) -> Tuple[np.ndarray, np.ndarray]:
        """Generate crack mask using random walk polyline."""
        mask = self._create_blank_mask()

        # Random crack parameters
        crack_width = self.rng.integers(self.width_range[0], self.width_range[1] + 1)
        length_pct = self.rng.uniform(self.length_pct_range[0], self.length_pct_range[1])
        crack_length = int(self.width * length_pct)

        # Starting position (center of image with variation)
        start_x = self.rng.integers(self.width // 4, 3 * self.width // 4)
        start_y = self.weld_center_y + self.rng.integers(-50, 50)

        # Base angle (mostly horizontal, slight variation)
        base_angle = self.rng.uniform(-self.angle_variation, self.angle_variation)

        # Generate main crack path
        points = self._random_walk_polyline(
            start_x, start_y, crack_length, base_angle, num_segments=60
        )
        cv2.polylines(mask, [points], isClosed=False, color=255, thickness=crack_width)

        # Optional branch
        if self.rng.random() < self.branch_probability:
            branch_point_idx = self.rng.integers(len(points) // 4, 3 * len(points) // 4)
            branch_start = points[branch_point_idx, 0]  # Extract [x, y] from shape (N, 1, 2)
            branch_length = crack_length // 3
            branch_angle = base_angle + self.rng.uniform(-45, 45)

            branch_points = self._random_walk_polyline(
                branch_start[0], branch_start[1], branch_length, branch_angle, num_segments=25
            )
            cv2.polylines(mask, [branch_points], isClosed=False, color=255, thickness=max(1, crack_width - 1))

        feathered = feather_mask(mask, blur_radius=1)
        return mask, feathered

    def _random_walk_polyline(
        self, start_x: int, start_y: int, length: int, base_angle: float, num_segments: int
    ) -> np.ndarray:
        """
        Generate random walk polyline for crack path.

        Args:
            start_x, start_y: Starting point
            length: Total path length
            base_angle: Base direction in degrees
            num_segments: Number of line segments

        Returns:
            Array of points [[x, y], ...], shape (N, 1, 2) for cv2.polylines
        """
        points = [[start_x, start_y]]
        segment_length = length / num_segments

        current_x, current_y = start_x, start_y
        current_angle = np.radians(base_angle)

        base_angle_rad = np.radians(base_angle)
        max_deviation = np.radians(35)  # Clamp total drift ≤35° — prevents "?" shape

        for _ in range(num_segments):
            # Add random angle perturbation, but clamp total drift from base direction
            angle_noise = self.rng.uniform(-45, 45)
            new_angle = current_angle + np.radians(angle_noise)
            # Clamp: total deviation from base direction cannot exceed ±60°
            deviation = new_angle - base_angle_rad
            deviation = np.clip(deviation, -max_deviation, max_deviation)
            current_angle = base_angle_rad + deviation

            # Calculate next point
            dx = segment_length * np.cos(current_angle)
            dy = segment_length * np.sin(current_angle)

            current_x += dx
            current_y += dy

            # Clamp to image bounds
            current_x = np.clip(current_x, 0, self.width - 1)
            current_y = np.clip(current_y, 0, self.height - 1)

            points.append([int(current_x), int(current_y)])

        return np.array(points, dtype=np.int32).reshape((-1, 1, 2))
