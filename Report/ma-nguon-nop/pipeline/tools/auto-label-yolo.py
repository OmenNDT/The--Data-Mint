"""
Auto-label YOLO annotations for Data Mint synthetic images (img2img approach).

Strategy: img2img modifies the entire image globally but the LoRA-induced defect
has MUCH higher pixel diff than background texture noise. We isolate the defect
by finding the largest connected component above a high-percentile threshold.

Approach:
  1. Load output PNG + background PNG (path from .json metadata)
  2. Compute grayscale absolute pixel diff
  3. Threshold at max(90th percentile, 20) to filter background texture noise
  4. Morphological closing to connect nearby defect pixels
  5. Find connected components → take largest qualified component
  6. Convert to YOLO bbox

Usage:
    python3 auto-label-yolo.py [--synthetic-dir PATH] [--min-area N] [--threshold-pct N]

Output per image:
    {class}_{jobid}.txt  →  YOLO: "class_id cx cy w h" (normalized 0-1)
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage


# Class ID mapping — matches batch-config.yaml defect_distribution order
CLASS_IDS = {
    "crack": 0,
    "porosity": 1,
    "lack_of_fusion": 2,
    "lack_of_penetration": 3,
    "clustered_porosity": 4,
    "slag_inclusion": 5,
    "linear_porosity": 6,
    "elongated_cavity": 7,
    "metallic_inclusion": 8,
    "linear_slag_inclusion": 9,
    "inclusion": 10,
    "undercut": 11,
}

# Morphological closing kernel size — larger = connect more dispersed defect pixels
CLOSING_KERNEL = np.ones((7, 7), dtype=bool)


def img2img_diff_to_yolo_bbox(output_path: Path, bg_path: Path, min_area: int, threshold_pct: float):
    """
    Compute bbox from pixel diff between img2img output and background.

    Returns (cx, cy, w, h) normalized 0-1, or None if no clear defect found.
    """
    output_arr = np.array(Image.open(output_path).convert("RGB"), dtype=np.int32)
    bg_arr = np.array(Image.open(bg_path).convert("RGB"), dtype=np.int32)

    # Grayscale absolute diff — captures both dark and bright defects
    diff = np.abs(output_arr - bg_arr).mean(axis=2).astype(np.float32)

    # High-percentile threshold: ignore background texture noise
    pct_threshold = np.percentile(diff, threshold_pct)
    abs_minimum = 50  # never label sub-50 diff as defect — filters background texture noise
    threshold = max(float(pct_threshold), abs_minimum)

    binary = (diff > threshold).astype(np.uint8)

    if binary.sum() < min_area:
        return None

    # Morphological closing: connects nearby defect pixels into one region
    binary_closed = ndimage.binary_closing(binary, structure=CLOSING_KERNEL).astype(np.uint8)

    # Label connected components
    labeled, n_components = ndimage.label(binary_closed)
    if n_components == 0:
        return None

    # Find the largest component by area
    component_sizes = ndimage.sum(binary_closed, labeled, range(1, n_components + 1))
    largest_id = int(np.argmax(component_sizes)) + 1
    largest_mask = (labeled == largest_id)

    if largest_mask.sum() < min_area:
        return None

    # Also verify mean diff in this region is sufficiently high
    mean_diff_in_region = diff[largest_mask].mean()
    if mean_diff_in_region < abs_minimum:
        return None

    # Bounding box
    rows = np.any(largest_mask, axis=1)
    cols = np.any(largest_mask, axis=0)
    rmin, rmax = np.where(rows)[0][[0, -1]]
    cmin, cmax = np.where(cols)[0][[0, -1]]

    h_img, w_img = diff.shape

    cx = ((cmin + cmax) / 2) / w_img
    cy = ((rmin + rmax) / 2) / h_img
    bw = (cmax - cmin) / w_img
    bh = (rmax - rmin) / h_img

    # Clamp
    cx = max(0.0, min(1.0, cx))
    cy = max(0.0, min(1.0, cy))
    bw = max(0.001, min(1.0, bw))
    bh = max(0.001, min(1.0, bh))

    # Reject bbox that covers most of the image — likely background noise, not defect
    if bw > 0.75 or bh > 0.75:
        return None

    return (cx, cy, bw, bh)


def process_class_folder(class_dir: Path, class_id: int, min_area: int, threshold_pct: float):
    """Process all images in one class folder. Returns (labeled, skipped, no_json) counts."""
    labeled = 0
    skipped = 0
    no_json = 0

    # Output PNGs only (exclude _mask.png)
    png_files = [f for f in class_dir.glob("*.png") if "_mask." not in f.name]

    for png_path in sorted(png_files):
        txt_path = png_path.with_suffix(".txt")
        json_path = png_path.with_suffix(".json")

        if not json_path.exists():
            no_json += 1
            continue

        try:
            meta = json.loads(json_path.read_text())
            bg_path = Path(meta["background_image"])
        except (json.JSONDecodeError, KeyError):
            no_json += 1
            continue

        if not bg_path.exists():
            no_json += 1
            continue

        try:
            result = img2img_diff_to_yolo_bbox(png_path, bg_path, min_area, threshold_pct)
        except Exception:
            skipped += 1
            continue

        if result is None:
            txt_path.write_text("")  # empty label = no clear defect
            skipped += 1
            continue

        cx, cy, bw, bh = result
        txt_path.write_text(f"{class_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")
        labeled += 1

    return labeled, skipped, no_json


def main():
    parser = argparse.ArgumentParser(description="Auto-label Data Mint img2img synthetic images in YOLO format")
    parser.add_argument(
        "--synthetic-dir",
        default="/home/sontn/Projects/The Data Mint/output/synthetic",
        help="Path to output/synthetic directory"
    )
    parser.add_argument(
        "--min-area",
        type=int,
        default=300,
        help="Minimum connected component area in pixels (default: 300)"
    )
    parser.add_argument(
        "--threshold-pct",
        type=float,
        default=99.0,
        help="Percentile of diff to use as threshold (default: 99 = top 1%% of pixels)"
    )
    parser.add_argument(
        "--class",
        dest="only_class",
        default=None,
        help="Process only a specific class (e.g. crack)"
    )
    args = parser.parse_args()

    synthetic_dir = Path(args.synthetic_dir)
    if not synthetic_dir.exists():
        print(f"ERROR: synthetic dir not found: {synthetic_dir}")
        sys.exit(1)

    print(f"Auto-labeling YOLO annotations (img2img percentile diff)")
    print(f"  Synthetic dir   : {synthetic_dir}")
    print(f"  Threshold pct   : {args.threshold_pct}th percentile")
    print(f"  Min area        : {args.min_area} px")
    print()

    total_labeled = 0
    total_skipped = 0
    total_no_json = 0

    for class_name, class_id in CLASS_IDS.items():
        if args.only_class and class_name != args.only_class:
            continue

        class_dir = synthetic_dir / class_name
        if not class_dir.exists():
            continue

        labeled, skipped, no_json = process_class_folder(
            class_dir, class_id, args.min_area, args.threshold_pct
        )
        total_labeled += labeled
        total_skipped += skipped
        total_no_json += no_json

        print(f"  {class_name:30s} (id={class_id}): {labeled} labeled | {skipped} skipped | {no_json} no_json")

    print()
    print(f"Done: {total_labeled} labeled | {total_skipped} skipped | {total_no_json} no_json")


if __name__ == "__main__":
    main()
