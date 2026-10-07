#!/usr/bin/env python3
"""
COCO Dataset Builder

Builds COCO JSON format from synthetic images + masks + metadata.
Produces annotations/coco_train.json and annotations/coco_val.json.
"""

import json
import os
from pathlib import Path
from typing import Dict, List
import cv2
from tqdm import tqdm

# Import directly from module file to avoid circular import
from importlib import import_module
mask_to_annotation = import_module('.mask-to-annotation-converter', package='post_processing')


# Category mapping: defect_type -> category_id (1-indexed for COCO)
CATEGORY_MAP = {
    "crack": 1,
    "porosity": 2,
    "inclusion": 3,
    "lack_of_fusion": 4,
    "undercut": 5
}


def build_coco_dataset(
    image_mask_pairs: List[Dict],
    split_name: str,
    output_dir: Path
) -> Dict:
    """
    Build COCO format JSON from image-mask-metadata triplets.

    Args:
        image_mask_pairs: List of dicts with keys:
            - image_path: Path to synthetic image
            - mask_path: Path to binary mask
            - defect_type: Defect category name
            - metadata: Dict from metadata JSON
        split_name: 'train', 'val', or 'test'
        output_dir: Directory to save COCO JSON file

    Returns:
        COCO format dict
    """
    coco = {
        "images": [],
        "annotations": [],
        "categories": [
            {"id": v, "name": k, "supercategory": "defect"}
            for k, v in CATEGORY_MAP.items()
        ],
        "info": {
            "description": "The Data Mint Synthetic X-ray Defect Dataset",
            "version": "1.0",
            "year": 2026,
            "contributor": "The Data Mint Pipeline",
            "date_created": "2026-01-31"
        }
    }

    ann_id = 1

    for img_id, item in enumerate(tqdm(image_mask_pairs, desc=f"Building COCO {split_name}"), 1):
        img_path = item["image_path"]
        mask_path = item["mask_path"]
        defect_type = item["defect_type"]

        # Read image to get dimensions
        img = cv2.imread(str(img_path))
        if img is None:
            print(f"Warning: Failed to load image {img_path}, skipping")
            continue

        h, w = img.shape[:2]
        filename = os.path.basename(img_path)

        # Add image entry
        coco["images"].append({
            "id": img_id,
            "file_name": filename,
            "height": h,
            "width": w
        })

        # Convert mask to annotation
        try:
            ann = mask_to_annotation.mask_to_annotation(
                str(mask_path),
                defect_type,
                CATEGORY_MAP,
                format="coco"
            )

            # Skip if mask is empty (area == 0)
            if ann["area"] == 0:
                print(f"Warning: Empty mask for {filename}, skipping annotation")
                continue

            ann["id"] = ann_id
            ann["image_id"] = img_id
            coco["annotations"].append(ann)
            ann_id += 1

        except Exception as e:
            print(f"Error processing mask {mask_path}: {e}")
            continue

    # Save COCO JSON
    output_path = output_dir / f"coco_{split_name}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(coco, f, indent=2)

    print(f"✓ Saved COCO {split_name}: {output_path}")
    print(f"  Images: {len(coco['images'])}, Annotations: {len(coco['annotations'])}")

    return coco


def validate_coco_format(coco_json_path: Path) -> bool:
    """
    Validate COCO JSON format by attempting to load with pycocotools.

    Args:
        coco_json_path: Path to COCO JSON file

    Returns:
        True if valid, False otherwise
    """
    try:
        from pycocotools.coco import COCO

        # Redirect stdout to suppress verbose output
        import sys
        from io import StringIO
        old_stdout = sys.stdout
        sys.stdout = StringIO()

        coco = COCO(str(coco_json_path))

        sys.stdout = old_stdout

        print(f"✓ COCO validation passed: {coco_json_path}")
        print(f"  Categories: {len(coco.cats)}, Images: {len(coco.imgs)}, Annotations: {len(coco.anns)}")
        return True

    except ImportError:
        print("Warning: pycocotools not installed, skipping validation")
        return True

    except Exception as e:
        print(f"✗ COCO validation failed: {e}")
        return False
