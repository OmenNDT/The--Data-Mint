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


def _detect_weld_center_y(image_path: str, smooth_window: int = 30) -> int:
    """
    Detect weld bead center Y coordinate from background X-ray image.
    The weld metal is the brightest horizontal band in the image.

    Args:
        image_path: Path to background grayscale X-ray image
        smooth_window: Moving average window to smooth row brightness

    Returns:
        Y pixel coordinate of the brightest row (weld center)
    """
    import numpy as np
    from PIL import Image as PILImage
    img = np.array(PILImage.open(image_path).convert("L"), dtype=np.float32)
    row_means = img.mean(axis=1)
    kernel = np.ones(smooth_window) / smooth_window
    smoothed = np.convolve(row_means, kernel, mode="same")
    return int(smoothed.argmax())


def _generate_mask_worker(
    defect_type: str, seed: int, resolution: int,
    dilation_config: dict = None, background_path: str = None
) -> dict:
    """
    Worker function for parallel mask generation.
    Runs in separate process, returns paths to both annotation and inpainting masks.

    Args:
        defect_type: One of: crack, porosity, inclusion, lack_of_fusion, undercut
        seed: Random seed for reproducibility
        resolution: Mask size (width and height)
        dilation_config: Optional dict with keys: kernel_size, kernel_shape, feather_blur_radius

    Returns:
        Dict with "annotation_path" (thin original) and "inpaint_path" (dilated for inpainting)
    """
    # Lazy import to avoid NumPy version issues at module load time
    from mask_generator import (
        CrackMaskGenerator,
        PorosityMaskGenerator,
        ClusteredPorosityMaskGenerator,
        LackOfFusionMaskGenerator,
        LackOfPenetrationMaskGenerator,
        LackOfSideWallFusionMaskGenerator,
        SlagInclusionMaskGenerator,
        LinearSlagInclusionMaskGenerator,
        MetallicInclusionMaskGenerator,
        UndercutMaskGenerator,
        LinearPorosityMaskGenerator,
        ElongatedCavityMaskGenerator,
        dilate_mask_for_inpainting,
    )

    # Map defect types to generator classes
    generators = {
        "crack": CrackMaskGenerator,
        "porosity": PorosityMaskGenerator,
        "clustered_porosity": ClusteredPorosityMaskGenerator,
        "linear_porosity": LinearPorosityMaskGenerator,
        "lack_of_fusion": LackOfFusionMaskGenerator,
        "lack_of_penetration": LackOfPenetrationMaskGenerator,
        "lack_of_side_wall_fusion": LackOfSideWallFusionMaskGenerator,
        "slag_inclusion": SlagInclusionMaskGenerator,
        "linear_slag_inclusion": LinearSlagInclusionMaskGenerator,
        "metallic_inclusion": MetallicInclusionMaskGenerator,
        "elongated_cavity": ElongatedCavityMaskGenerator,
        "undercut": UndercutMaskGenerator,
        "inclusion": SlagInclusionMaskGenerator,  # legacy alias
    }

    if defect_type not in generators:
        raise ValueError(f"Unknown defect type: {defect_type}")

    # Detect weld bead center from background image for accurate mask placement
    weld_center_y = None
    if background_path:
        try:
            weld_center_y = _detect_weld_center_y(background_path)
        except Exception:
            weld_center_y = resolution // 2

    # Realism loop: băng rộng dải không ngấu điều chỉnh TẠI SINH theo núm lof_band_width_scale (mặc định: {}, không
    # đổi gì). Khác shape_generated_mask dưới đây (tạo hình lại mask ĐÃ sinh): đây sửa kwargs của bộ sinh trước khi
    # vẽ polygon, giữ mép sắc nét. Xem realism/generator_hooks.lof_generation_kwargs.
    extra_kwargs = {}
    if defect_type == "lack_of_fusion":
        try:
            from realism.generator_hooks import lof_generation_kwargs
            extra_kwargs = lof_generation_kwargs()
        except Exception:  # realism module missing or broken: giữ band_width_range gốc của bộ sinh
            extra_kwargs = {}

    # Generate mask
    generator = generators[defect_type](
        height=resolution,
        width=resolution,
        seed=seed,
        weld_center_y=weld_center_y,
        **extra_kwargs
    )
    binary_mask, feathered_mask = generator.generate()

    # Realism loop: retry empty masks, reshape per knobs (defaults = unchanged). See realism/generator_hooks.py
    try:
        from realism.generator_hooks import shape_generated_mask
        binary_mask, feathered_mask = shape_generated_mask(
            defect_type, seed, binary_mask, feathered_mask,
            regenerate=lambda s: generators[defect_type](
                height=resolution, width=resolution, seed=s, weld_center_y=weld_center_y, **extra_kwargs).generate(),
            weld_center_y=weld_center_y)
    except Exception:  # realism module missing or broken: keep the generator's own mask
        pass

    # Save original thin mask (annotation ground truth)
    annotation_file = tempfile.NamedTemporaryFile(
        suffix="_annotation.png", delete=False, dir=tempfile.gettempdir()
    )
    annotation_path = annotation_file.name
    annotation_file.close()
    Image.fromarray(binary_mask, mode="L").save(annotation_path, format="PNG")

    # Create inpainting mask: dilated if config provided, otherwise use feathered
    if dilation_config and dilation_config.get("enabled", False):
        inpaint_mask = dilate_mask_for_inpainting(
            binary_mask,
            kernel_size=dilation_config.get("kernel_size", 21),
            kernel_shape=dilation_config.get("kernel_shape", "ellipse"),
            feather_blur_radius=dilation_config.get("feather_blur_radius", 7),
        )
    else:
        inpaint_mask = feathered_mask

    inpaint_file = tempfile.NamedTemporaryFile(
        suffix="_inpaint.png", delete=False, dir=tempfile.gettempdir()
    )
    inpaint_path = inpaint_file.name
    inpaint_file.close()
    Image.fromarray(inpaint_mask, mode="L").save(inpaint_path, format="PNG")

    return {"annotation_path": annotation_path, "inpaint_path": inpaint_path}


class MaskPrefetcher:
    """Pre-generates masks using CPU worker pool."""

    def __init__(self, config: Dict, mask_config: Dict = None):
        """
        Initialize mask prefetcher.

        Args:
            config: Batch configuration dict
            mask_config: Optional mask-config.yaml dict with dilation settings
        """
        self.config = config
        self.resolution = config["generation"]["resolution"]
        self.worker_count = config["performance"]["mask_prefetch_workers"]

        # Dilation config from mask-config.yaml
        self.dilation_config = None
        if mask_config and "inpaint_dilation" in mask_config:
            self.dilation_config = mask_config["inpaint_dilation"]

        # Create process pool
        self.executor = ProcessPoolExecutor(max_workers=self.worker_count)

        # Buffer for prefetched masks
        self.buffer = []
        self.max_buffer_size = config["performance"]["mask_prefetch_count"]

        # Track futures
        self.pending_futures = []

    def submit_prefetch(self, defect_type: str, seed: int, background_path: str = None):
        """
        Submit mask generation task to worker pool.

        Args:
            defect_type: Defect type
            seed: Random seed
            background_path: Path to background image for weld bead detection
        """
        future = self.executor.submit(
            _generate_mask_worker,
            defect_type,
            seed,
            self.resolution,
            self.dilation_config,
            background_path,
        )

        self.pending_futures.append({
            "future": future,
            "defect_type": defect_type,
            "seed": seed,
            "background_path": background_path,
        })

    def get_next_mask(self) -> Optional[dict]:
        """
        Get next completed mask pair from buffer.
        Blocks until a mask is ready if buffer is empty.

        Returns:
            Dict with "annotation_path" and "inpaint_path", or None
        """
        if not self.pending_futures:
            return None

        # Get first completed future
        pending = self.pending_futures.pop(0)
        future = pending["future"]

        # Wait for completion; on worker failure, regenerate synchronously
        try:
            return future.result()
        except Exception as e:
            print(f"  [warn] Mask worker failed ({e}), regenerating synchronously")
            try:
                return _generate_mask_worker(
                    pending["defect_type"],
                    pending["seed"],
                    self.resolution,
                    self.dilation_config,
                    pending.get("background_path"),
                )
            except Exception as e2:
                print(f"  [warn] Sync mask regen also failed: {e2}")
                return None

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
            bg_path = str(job["background_image"]) if job.get("background_image") else None
            self.submit_prefetch(job["defect_type"], job["seed"], background_path=bg_path)

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
