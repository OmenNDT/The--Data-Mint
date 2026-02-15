"""
Mask Prefetch Worker Pool

Pre-generates binary masks using CPU ProcessPoolExecutor ahead of GPU queue.
Keeps a buffer of ready masks to prevent GPU starvation.
"""

import sys
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
from typing import Dict, Optional
from PIL import Image
import tempfile

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def _generate_mask_worker(defect_type: str, seed: int, resolution: int) -> str:
    """
    Worker function for parallel mask generation.
    Runs in separate process, returns temp file path.

    Args:
        defect_type: One of: crack, porosity, inclusion, lack_of_fusion, undercut
        seed: Random seed for reproducibility
        resolution: Mask size (width and height)

    Returns:
        Path to temporary mask file
    """
    # Lazy import to avoid NumPy version issues at module load time
    from mask_generator import (
        CrackMaskGenerator,
        PorosityMaskGenerator,
        LackOfFusionMaskGenerator,
        SlagInclusionMaskGenerator,
        UndercutMaskGenerator
    )

    # Map defect types to generator classes
    generators = {
        "crack": CrackMaskGenerator,
        "porosity": PorosityMaskGenerator,
        "inclusion": SlagInclusionMaskGenerator,
        "lack_of_fusion": LackOfFusionMaskGenerator,
        "undercut": UndercutMaskGenerator
    }

    if defect_type not in generators:
        raise ValueError(f"Unknown defect type: {defect_type}")

    # Generate mask
    generator = generators[defect_type](
        height=resolution,
        width=resolution,
        seed=seed
    )
    binary_mask, feathered_mask = generator.generate()

    # Save feathered mask to temp file (used for inpainting)
    temp_file = tempfile.NamedTemporaryFile(
        suffix=".png",
        delete=False,
        dir=tempfile.gettempdir()
    )
    temp_path = temp_file.name
    temp_file.close()

    # Convert to PIL and save
    mask_image = Image.fromarray(feathered_mask, mode="L")
    mask_image.save(temp_path, format="PNG")

    return temp_path


class MaskPrefetcher:
    """Pre-generates masks using CPU worker pool."""

    def __init__(self, config: Dict):
        """
        Initialize mask prefetcher.

        Args:
            config: Batch configuration dict
        """
        self.config = config
        self.resolution = config["generation"]["resolution"]
        self.worker_count = config["performance"]["mask_prefetch_workers"]

        # Create process pool
        self.executor = ProcessPoolExecutor(max_workers=self.worker_count)

        # Buffer for prefetched masks
        self.buffer = []
        self.max_buffer_size = config["performance"]["mask_prefetch_count"]

        # Track futures
        self.pending_futures = []

    def submit_prefetch(self, defect_type: str, seed: int):
        """
        Submit mask generation task to worker pool.

        Args:
            defect_type: Defect type
            seed: Random seed
        """
        future = self.executor.submit(
            _generate_mask_worker,
            defect_type,
            seed,
            self.resolution
        )

        self.pending_futures.append({
            "future": future,
            "defect_type": defect_type,
            "seed": seed
        })

    def get_next_mask(self) -> Optional[str]:
        """
        Get next completed mask from buffer.
        Blocks until a mask is ready if buffer is empty.

        Returns:
            Path to mask file or None if no pending futures
        """
        # Wait for at least one future to complete
        if not self.pending_futures:
            return None

        # Get first completed future
        pending = self.pending_futures.pop(0)
        future = pending["future"]

        # Wait for completion (blocks)
        mask_path = future.result()

        return mask_path

    def prefill_buffer(self, jobs: list):
        """
        Pre-fill buffer with initial batch of masks.

        Args:
            jobs: List of job dicts to prefetch
        """
        prefill_count = min(self.max_buffer_size, len(jobs))

        print(f"Pre-filling mask buffer with {prefill_count} masks...")

        for i in range(prefill_count):
            job = jobs[i]
            self.submit_prefetch(job["defect_type"], job["seed"])

        print(f"Submitted {prefill_count} mask generation tasks")

    def shutdown(self):
        """Shutdown worker pool and cleanup."""
        self.executor.shutdown(wait=True)

    def get_buffer_status(self) -> Dict:
        """
        Get buffer status.

        Returns:
            Dict with pending count
        """
        return {
            "pending_count": len(self.pending_futures)
        }
