#!/usr/bin/env python3
"""
SSIM Background Checker

Validates that inpainting preserves the background outside the defect mask.
Compares original clean background with synthetic result using SSIM metric.
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Dict, Optional
from skimage.metrics import structural_similarity as ssim


def check_ssim_background(
    synthetic_image_path: str,
    background_image_path: str,
    mask_path: str,
    target_ssim: float = 0.90
) -> Dict:
    """
    Check SSIM between original background and synthetic image outside mask region.

    Args:
        synthetic_image_path: Path to generated synthetic image
        background_image_path: Path to original clean background
        mask_path: Path to binary mask (defect region)
        target_ssim: Target SSIM threshold (default 0.90)

    Returns:
        Dict with ssim_score, passes, and analysis
    """
    # Load images
    synthetic = cv2.imread(synthetic_image_path, cv2.IMREAD_GRAYSCALE)
    background = cv2.imread(background_image_path, cv2.IMREAD_GRAYSCALE)
    mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)

    if synthetic is None or background is None or mask is None:
        return {
            "ssim_score": 0.0,
            "passes": False,
            "error": "Failed to load one or more images"
        }

    # Ensure same dimensions
    if synthetic.shape != background.shape:
        background = cv2.resize(background, (synthetic.shape[1], synthetic.shape[0]))

    if mask.shape != synthetic.shape:
        mask = cv2.resize(mask, (synthetic.shape[1], synthetic.shape[0]))

    # Create inverse mask (background region only, exclude defect)
    background_mask = (mask == 0).astype(np.uint8)

    # Apply mask to both images
    synthetic_bg = cv2.bitwise_and(synthetic, synthetic, mask=background_mask)
    original_bg = cv2.bitwise_and(background, background, mask=background_mask)

    # Compute SSIM on background region only
    ssim_score = ssim(original_bg, synthetic_bg, data_range=255)

    passes = ssim_score >= target_ssim

    return {
        "ssim_score": float(ssim_score),
        "target_ssim": target_ssim,
        "passes": passes,
        "background_pixels": int(np.sum(background_mask)),
        "defect_pixels": int(np.sum(mask > 0))
    }


def batch_check_ssim(
    synthetic_dir: Path,
    backgrounds_dir: Path,
    sample_size: Optional[int] = None,
    target_ssim: float = 0.90
) -> Dict:
    """
    Run SSIM check on batch of synthetic images.

    Args:
        synthetic_dir: Directory containing synthetic output
        backgrounds_dir: Directory containing original backgrounds
        sample_size: Number of random samples to check (None = all)
        target_ssim: Target SSIM threshold

    Returns:
        Summary statistics and list of failed images
    """
    import json
    import random

    results = []
    failed_images = []

    # Collect all synthetic images
    all_images = []
    for defect_dir in synthetic_dir.iterdir():
        if not defect_dir.is_dir():
            continue

        for img_file in defect_dir.glob("*.png"):
            if "_mask" in img_file.name:
                continue

            base_name = img_file.stem
            mask_file = defect_dir / f"{base_name}_mask.png"
            metadata_file = defect_dir / f"{base_name}.json"

            if not mask_file.exists() or not metadata_file.exists():
                continue

            all_images.append({
                "image": str(img_file),
                "mask": str(mask_file),
                "metadata": str(metadata_file)
            })

    # Sample if requested
    if sample_size and sample_size < len(all_images):
        all_images = random.sample(all_images, sample_size)

    print(f"Checking SSIM for {len(all_images)} images...")

    for item in all_images:
        # Load metadata to get background path
        with open(item["metadata"], 'r') as f:
            metadata = json.load(f)

        background_path = metadata.get("background_image", "")

        if not background_path or not Path(background_path).exists():
            continue

        result = check_ssim_background(
            item["image"],
            background_path,
            item["mask"],
            target_ssim=target_ssim
        )

        result["image_path"] = item["image"]
        results.append(result)

        if not result["passes"]:
            failed_images.append(item["image"])

    # Compute statistics
    ssim_scores = [r["ssim_score"] for r in results if "ssim_score" in r]

    summary = {
        "total_checked": len(results),
        "passed": sum(1 for r in results if r.get("passes", False)),
        "failed": len(failed_images),
        "pass_rate": sum(1 for r in results if r.get("passes", False)) / len(results) if results else 0,
        "mean_ssim": float(np.mean(ssim_scores)) if ssim_scores else 0.0,
        "min_ssim": float(np.min(ssim_scores)) if ssim_scores else 0.0,
        "max_ssim": float(np.max(ssim_scores)) if ssim_scores else 0.0,
        "std_ssim": float(np.std(ssim_scores)) if ssim_scores else 0.0,
        "target_ssim": target_ssim,
        "failed_images": failed_images[:10]  # First 10 failures
    }

    return summary
