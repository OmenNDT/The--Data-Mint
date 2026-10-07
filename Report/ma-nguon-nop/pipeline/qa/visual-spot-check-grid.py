#!/usr/bin/env python3
"""
Visual Spot Check Grid Generator

Creates HTML gallery with random sample of synthetic images for manual review.
Overlays annotations on images for visual verification.
"""

import cv2
import numpy as np
import random
from pathlib import Path
from typing import List, Dict
import base64


def overlay_mask_on_image(image: np.ndarray, mask: np.ndarray, color=(0, 255, 0), alpha=0.5) -> np.ndarray:
    """
    Overlay colored mask on grayscale image.

    Args:
        image: Grayscale image (H, W)
        mask: Binary mask (H, W)
        color: RGB color for mask overlay
        alpha: Transparency factor

    Returns:
        RGB image with mask overlay
    """
    # Convert grayscale to RGB
    if len(image.shape) == 2:
        img_rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
    else:
        img_rgb = image.copy()

    # Create colored mask
    mask_rgb = np.zeros_like(img_rgb)
    mask_rgb[mask > 0] = color

    # Blend
    overlaid = cv2.addWeighted(img_rgb, 1.0, mask_rgb, alpha, 0)

    return overlaid


def image_to_base64(image: np.ndarray) -> str:
    """
    Convert image array to base64 string for HTML embedding.

    Args:
        image: Image array

    Returns:
        Base64 encoded string
    """
    _, buffer = cv2.imencode('.png', image)
    return base64.b64encode(buffer).decode('utf-8')


def create_spot_check_grid(
    synthetic_dir: Path,
    output_path: Path,
    sample_pct: float = 2.0,
    min_samples: int = 50,
    max_samples: int = 200,
    seed: int = 42
) -> int:
    """
    Create HTML grid gallery for visual spot-check.

    Args:
        synthetic_dir: Directory containing synthetic output
        output_path: Path to save HTML file
        sample_pct: Percentage of dataset to sample
        min_samples: Minimum number of samples
        max_samples: Maximum number of samples
        seed: Random seed

    Returns:
        Number of images in gallery
    """
    random.seed(seed)

    # Collect all synthetic images
    all_items = []
    for defect_dir in synthetic_dir.iterdir():
        if not defect_dir.is_dir():
            continue

        defect_type = defect_dir.name

        for img_file in defect_dir.glob("*.png"):
            if "_mask" in img_file.name:
                continue

            base_name = img_file.stem
            mask_file = defect_dir / f"{base_name}_mask.png"

            if not mask_file.exists():
                continue

            all_items.append({
                "image": str(img_file),
                "mask": str(mask_file),
                "defect_type": defect_type,
                "basename": img_file.name
            })

    # Calculate sample size
    n_samples = max(min_samples, min(max_samples, int(len(all_items) * sample_pct / 100)))
    n_samples = min(n_samples, len(all_items))

    # Random sample
    sampled = random.sample(all_items, n_samples)

    print(f"Creating spot-check gallery: {n_samples} / {len(all_items)} images")

    # Generate HTML
    html_parts = ["""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Spot Check Gallery - The Data Mint</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f0f0f0;
        }
        h1 {
            text-align: center;
            color: #333;
        }
        .info {
            text-align: center;
            margin-bottom: 30px;
            font-size: 14px;
            color: #666;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
            max-width: 1400px;
            margin: 0 auto;
        }
        .item {
            background: white;
            border-radius: 8px;
            padding: 15px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .item img {
            width: 100%;
            border-radius: 4px;
            margin-bottom: 10px;
        }
        .label {
            font-weight: bold;
            color: #444;
            margin-bottom: 5px;
        }
        .defect-type {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: bold;
            margin-bottom: 8px;
        }
        .crack { background: #ff6b6b; color: white; }
        .porosity { background: #4ecdc4; color: white; }
        .inclusion { background: #ffe66d; color: #333; }
        .lack_of_fusion { background: #a8dadc; color: #333; }
        .undercut { background: #95e1d3; color: #333; }
        .checklist {
            font-size: 12px;
            margin-top: 10px;
            padding: 10px;
            background: #f9f9f9;
            border-radius: 4px;
        }
        .checklist label {
            display: block;
            margin: 5px 0;
            cursor: pointer;
        }
    </style>
</head>
<body>
    <h1>🔍 Spot Check Gallery</h1>
    <div class="info">
        <p>Random sample for manual quality review</p>
        <p>Total images: """ + str(n_samples) + """ / """ + str(len(all_items)) + f""" ({sample_pct}%)</p>
    </div>
    <div class="grid">
"""]

    # Process each sample
    for idx, item in enumerate(sampled):
        # Load image and mask
        img = cv2.imread(item["image"], cv2.IMREAD_GRAYSCALE)
        mask = cv2.imread(item["mask"], cv2.IMREAD_GRAYSCALE)

        if img is None or mask is None:
            continue

        # Create overlay
        overlaid = overlay_mask_on_image(img, mask, color=(0, 255, 0), alpha=0.4)

        # Convert to base64
        img_b64 = image_to_base64(overlaid)

        # Add to HTML
        html_parts.append(f"""
        <div class="item">
            <span class="defect-type {item['defect_type']}">{item['defect_type']}</span>
            <img src="data:image/png;base64,{img_b64}" alt="{item['basename']}">
            <div class="label">{item['basename']}</div>
            <div class="checklist">
                <strong>Review Checklist:</strong>
                <label><input type="checkbox"> Defect looks realistic</label>
                <label><input type="checkbox"> Correct weld zone placement</label>
                <label><input type="checkbox"> Background undistorted</label>
                <label><input type="checkbox"> No color artifacts</label>
                <label><input type="checkbox"> Annotation matches defect</label>
            </div>
        </div>
""")

    html_parts.append("""
    </div>
</body>
</html>
""")

    # Save HTML
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        f.write(''.join(html_parts))

    print(f"✓ Spot-check gallery saved: {output_path}")
    return n_samples
