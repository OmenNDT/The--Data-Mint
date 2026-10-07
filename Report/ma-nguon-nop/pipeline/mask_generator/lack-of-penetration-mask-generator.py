"""
Lack of Penetration (LoP) defect mask generator.

LoP morphology: thin, nearly-continuous narrow band at the weld ROOT (centerline).
  - 2-4px thick, nearly horizontal (±1.5px waviness max)
  - Sits at the weld CENTERLINE — NOT offset like LoF
  - More continuous, minimal gaps

Distinct from crack:
  - Crack: zigzag random walk, hairline, can branch
  - LoP: straight thin line dead-center, near-zero waviness
"""

import numpy as np
import cv2
from typing import Tuple
from importlib import import_module
from scipy.ndimage import uniform_filter1d  # noqa: F401 (kept for future waviness)

base_module = import_module('.base-defect-mask-generator', package='mask_generator')
feathering_module = import_module('.feathering-utility', package='mask_generator')

DefectMaskGenerator = base_module.DefectMaskGenerator
feather_mask = feathering_module.feather_mask


class LackOfPenetrationMaskGenerator(DefectMaskGenerator):
    """
    Generator for lack of penetration defect masks.

    Draws a thin, nearly-continuous line at the weld ROOT (centerline).
    Key differences from crack:
      - AT CENTERLINE (not offset like LoF)
      - Minimal waviness ±1.5px (crack uses random walk ±20° per segment)
      - More continuous (very short gaps 0-3px)
      - Slightly filled (2-4px) vs crack's 1-2px hairline
    """

    def __init__(
        self,
        height: int = 512,
        width: int = 512,
        seed: int = None,
        length_pct_range: Tuple[float, float] = (0.35, 0.70),
        thickness_range: Tuple[int, int] = (2, 4),
        **kwargs
    ):
        super().__init__(height, width, seed, **kwargs)
        self.length_pct_range = length_pct_range
        self.thickness_range = thickness_range

    def generate(self) -> Tuple[np.ndarray, np.ndarray]:
        """Generate LoP mask: thin straight band at weld root (centerline)."""
        mask = self._create_blank_mask()

        length_pct = self.rng.uniform(*self.length_pct_range)
        line_length = int(self.width * length_pct)
        start_x = int(self.rng.integers(15, max(16, self.width - line_length - 15)))

        # LoP at weld centerline — only tiny root offset (0-4% of height)
        root_offset = int(self.height * self.rng.uniform(0.0, 0.04))
        base_y = int(np.clip(self.weld_center_y + root_offset, 10, self.height - 10))

        # Perfectly straight — no waviness (LOP = root gap, mechanical straight line)
        y_offsets = np.zeros(line_length)

        thickness = int(self.rng.integers(*self.thickness_range))

        # Nearly-continuous: long segments (30-80px), tiny gaps (0-3px)
        i = 0
        while i < line_length:
            seg_len = int(self.rng.integers(30, 80))
            gap_len = int(self.rng.integers(0, 4))
            seg_end = min(i + seg_len, line_length)
            if seg_end > i + 2:
                pts = []
                for j in range(i, seg_end):
                    x = start_x + j
                    y = int(np.clip(base_y + y_offsets[j], 3, self.height - 3))
                    pts.append([x, y])
                pts_arr = np.array(pts, dtype=np.int32).reshape((-1, 1, 2))
                cv2.polylines(mask, [pts_arr], isClosed=False, color=255, thickness=thickness)
            i += seg_len + gap_len

        # Maximum feathering → LOP appears as very soft, diffuse linear shadow
        feathered = feather_mask(mask, blur_radius=40)
        return mask, feathered
