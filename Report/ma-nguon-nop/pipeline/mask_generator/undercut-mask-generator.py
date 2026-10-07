"""
Undercut defect mask generator.

Undercut = a groove melted INTO the base metal at the weld TOE (where the bead
edge meets the parent plate), not refilled. In RT it reads as a DARK, LONG,
CONTINUOUS, thin indication that HUGS the bead toe and follows its gentle curve.
May appear on one OR both toes (top/bottom of the bead).

See docs/defect-morphology-undercut.md for the full morphology reference.

Key traits (vs the older straight-line version):
  - Sits right AT the bead toe (edge of the weld zone), not an arbitrary offset.
  - LONG and CONTINUOUS (no gaps) — runs most of the frame.
  - Gently CURVED along the toe (low-frequency wave), not a rigid straight line
    and not zigzag like a crack.
  - Thin but with a smoothly VARYING width (groove deeper in spots).
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


class UndercutMaskGenerator(DefectMaskGenerator):
    """Generator for undercut defect masks (groove along the weld toe)."""

    def __init__(
        self,
        height: int = 512,
        width: int = 512,
        seed: int = None,
        length_pct_range: Tuple[float, float] = (0.45, 0.85),
        width_range: Tuple[int, int] = (2, 6),
        toe_offset_pct_range: Tuple[float, float] = (0.12, 0.18),
        both_toes_prob: float = 0.25,
        **kwargs
    ):
        """
        Args:
            length_pct_range: Groove length as fraction of image width (long, continuous).
            width_range: Groove half-width in px (thin, varies smoothly along length).
            toe_offset_pct_range: Distance of the toe from weld center, as fraction
                                  of height (the bead toe sits near the weld-zone edge).
            both_toes_prob: Probability the undercut appears on BOTH toes at once.
        """
        super().__init__(height, width, seed, **kwargs)
        self.length_pct_range = length_pct_range
        self.width_range = width_range
        self.toe_offset_pct_range = toe_offset_pct_range
        self.both_toes_prob = both_toes_prob

    def _draw_one_toe(self, mask: np.ndarray, side: int) -> None:
        """Draw a single undercut groove hugging one bead toe (side = +1/-1)."""
        # Toe line: near the edge of the weld zone, offset from center by `side`
        toe_offset = int(self.height * self.rng.uniform(*self.toe_offset_pct_range))
        base_y = int(np.clip(self.weld_center_y + side * toe_offset, 8, self.height - 8))

        # Long, continuous run
        length = int(self.width * self.rng.uniform(*self.length_pct_range))
        x_start = int(self.rng.integers(0, max(1, self.width - length)))
        x_end = x_start + length

        n_pts = 80
        xs = np.linspace(x_start, x_end, n_pts)

        # Gentle low-frequency curve along the toe (smoothed noise, ±3-6px)
        wave = self.rng.standard_normal(n_pts)
        wave = uniform_filter1d(wave, size=20)  # heavy smoothing -> low frequency
        wave = (wave / (wave.std() + 1e-8)) * self.rng.uniform(3.0, 6.0)
        ys = np.clip(base_y + wave, 3, self.height - 3)

        # Smoothly varying half-width along the groove (deeper/shallower spots)
        w_noise = self.rng.standard_normal(n_pts)
        w_noise = uniform_filter1d(w_noise, size=15)
        w_norm = (w_noise - w_noise.min()) / (np.ptp(w_noise) + 1e-8)  # 0..1
        w_lo, w_hi = self.width_range
        half_w = w_lo + w_norm * (w_hi - w_lo)

        # Build a filled ribbon: top edge (toward bead) + bottom edge (toward base)
        # The bead-side edge is sharper; the base-side edge slightly rougher.
        bead_edge = [(int(xs[i]), int(ys[i] - side * half_w[i] * 0.4)) for i in range(n_pts)]
        base_edge = [
            (int(xs[i]), int(ys[i] + side * half_w[i]))
            for i in range(n_pts - 1, -1, -1)
        ]
        polygon = np.array(bead_edge + base_edge, dtype=np.int32)
        cv2.fillPoly(mask, [polygon], 255)

    def generate(self) -> Tuple[np.ndarray, np.ndarray]:
        """Generate undercut mask: continuous groove(s) hugging the weld toe."""
        mask = self._create_blank_mask()

        # One toe by default; occasionally both toes (top + bottom)
        if self.rng.random() < self.both_toes_prob:
            self._draw_one_toe(mask, side=+1)
            self._draw_one_toe(mask, side=-1)
        else:
            side = 1 if self.rng.random() < 0.5 else -1
            self._draw_one_toe(mask, side=side)

        # Light feather — keep the groove edge visible (2-3px)
        feathered = feather_mask(mask, blur_radius=3)
        return mask, feathered
