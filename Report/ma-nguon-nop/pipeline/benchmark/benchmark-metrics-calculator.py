"""
Benchmark metrics: FID, SSIM, Laplacian sharpness for grayscale X-ray images.
"""

import logging
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def compute_fid(real_dir: Path, synthetic_dir: Path, batch_size: int = 32) -> float:
    """Compute FID between real and synthetic image directories.

    Grayscale images are replicated to 3-channel for Inception v3.
    Returns FID score (lower = better).
    """
    import torch
    from torchmetrics.image.fid import FrechetInceptionDistance
    from PIL import Image
    from torchvision import transforms

    transform = transforms.Compose([
        transforms.Resize((299, 299)),
        transforms.ToTensor(),
    ])

    fid = FrechetInceptionDistance(feature=2048, normalize=True)

    def load_and_update(directory: Path, real: bool):
        images = sorted(directory.glob("*.png"))
        if not images:
            logger.warning(f"No images in {directory}")
            return
        batch = []
        for img_path in images:
            img = Image.open(img_path).convert("L")
            tensor = transform(img)
            # Replicate grayscale to 3-channel for Inception
            tensor = tensor.repeat(3, 1, 1)
            batch.append(tensor)
            if len(batch) >= batch_size:
                fid.update(torch.stack(batch), real=real)
                batch = []
        if batch:
            fid.update(torch.stack(batch), real=real)

    load_and_update(real_dir, real=True)
    load_and_update(synthetic_dir, real=False)

    return fid.compute().item()


def compute_ssim_distribution(
    real_dir: Path, synthetic_dir: Path, sample_pairs: int = 50
) -> dict:
    """Compute mean SSIM between random pairs of real and synthetic images.

    Returns {"mean": float, "std": float, "min": float, "max": float}
    """
    from skimage.metrics import structural_similarity as ssim

    real_images = sorted(real_dir.glob("*.png"))
    synth_images = sorted(synthetic_dir.glob("*.png"))

    if not real_images or not synth_images:
        logger.warning(f"Missing images: real={len(real_images)}, synth={len(synth_images)}")
        return {"mean": 0.0, "std": 0.0, "min": 0.0, "max": 0.0}

    scores = []
    for i in range(min(sample_pairs, len(synth_images))):
        real_img = cv2.imread(str(real_images[i % len(real_images)]), cv2.IMREAD_GRAYSCALE)
        synth_img = cv2.imread(str(synth_images[i]), cv2.IMREAD_GRAYSCALE)

        if real_img is None or synth_img is None:
            continue

        # Resize to same dimensions
        real_img = cv2.resize(real_img, (512, 512))
        synth_img = cv2.resize(synth_img, (512, 512))

        score = ssim(real_img, synth_img, data_range=255, gaussian_weights=True, sigma=1.5)
        scores.append(score)

    if not scores:
        return {"mean": 0.0, "std": 0.0, "min": 0.0, "max": 0.0}

    return {
        "mean": float(np.mean(scores)),
        "std": float(np.std(scores)),
        "min": float(np.min(scores)),
        "max": float(np.max(scores)),
    }


def compute_sharpness(image_dir: Path) -> dict:
    """Compute mean Laplacian variance (sharpness) for directory of images.

    Returns {"mean": float, "std": float}
    """
    scores = []
    for img_path in sorted(image_dir.glob("*.png")):
        img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue
        laplacian = cv2.Laplacian(img, cv2.CV_64F)
        scores.append(float(laplacian.var()))

    if not scores:
        return {"mean": 0.0, "std": 0.0}

    return {
        "mean": float(np.mean(scores)),
        "std": float(np.std(scores)),
    }
