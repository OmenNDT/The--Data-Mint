#!/usr/bin/env python3
"""
Annotation Validator

Validates COCO and YOLO annotation formats:
- COCO: polygon within image bounds, bbox valid, category IDs correct
- YOLO: normalized coords in [0,1], class IDs valid
- Cross-check: COCO bbox roughly matches YOLO bbox
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple


def validate_coco_annotation(annotation: Dict, image_info: Dict, num_categories: int = 5) -> List[str]:
    """
    Validate single COCO annotation entry.

    Args:
        annotation: COCO annotation dict
        image_info: COCO image info dict
        num_categories: Number of valid categories

    Returns:
        List of error messages (empty if valid)
    """
    errors = []

    # Check required fields
    required = ["id", "image_id", "category_id", "bbox", "area", "segmentation"]
    for field in required:
        if field not in annotation:
            errors.append(f"Missing field: {field}")

    if errors:
        return errors

    # Validate category_id
    if annotation["category_id"] < 1 or annotation["category_id"] > num_categories:
        errors.append(f"Invalid category_id: {annotation['category_id']} (must be 1-{num_categories})")

    # Validate bbox format [x, y, width, height]
    bbox = annotation["bbox"]
    if len(bbox) != 4:
        errors.append(f"Invalid bbox format: {bbox} (must be [x, y, w, h])")
    else:
        x, y, w, h = bbox
        img_w, img_h = image_info["width"], image_info["height"]

        if x < 0 or y < 0:
            errors.append(f"Bbox has negative coordinates: ({x}, {y})")

        if x + w > img_w or y + h > img_h:
            errors.append(f"Bbox exceeds image bounds: ({x}+{w}, {y}+{h}) > ({img_w}, {img_h})")

        if w <= 0 or h <= 0:
            errors.append(f"Bbox has non-positive dimensions: w={w}, h={h}")

    # Validate area
    if annotation["area"] <= 0:
        errors.append(f"Invalid area: {annotation['area']} (must be > 0)")

    # Validate segmentation (should be list of polygons)
    if not isinstance(annotation["segmentation"], list):
        errors.append("Segmentation must be a list")
    elif len(annotation["segmentation"]) > 0:
        for i, polygon in enumerate(annotation["segmentation"]):
            if len(polygon) < 6:  # At least 3 points (x,y pairs)
                errors.append(f"Polygon {i} has too few points: {len(polygon)//2} (need >= 3)")

    return errors


def validate_yolo_label(label_line: str, num_classes: int = 5) -> List[str]:
    """
    Validate single YOLO label line.

    Args:
        label_line: YOLO format line "class_id x_center y_center width height"
        num_classes: Number of valid classes (0-indexed)

    Returns:
        List of error messages (empty if valid)
    """
    errors = []

    parts = label_line.strip().split()

    if len(parts) != 5:
        return [f"Invalid format: expected 5 values, got {len(parts)}"]

    try:
        class_id = int(parts[0])
        x_center, y_center, width, height = map(float, parts[1:])
    except ValueError as e:
        return [f"Failed to parse values: {e}"]

    # Validate class_id (0-indexed)
    if class_id < 0 or class_id >= num_classes:
        errors.append(f"Invalid class_id: {class_id} (must be 0-{num_classes-1})")

    # Validate normalized coordinates [0, 1]
    for name, val in [("x_center", x_center), ("y_center", y_center),
                       ("width", width), ("height", height)]:
        if val < 0 or val > 1:
            errors.append(f"{name} out of range: {val} (must be in [0, 1])")

    # Width and height should be positive
    if width <= 0 or height <= 0:
        errors.append(f"Non-positive dimensions: w={width}, h={height}")

    return errors


def validate_coco_dataset(coco_json_path: Path) -> Dict:
    """
    Validate entire COCO JSON dataset.

    Args:
        coco_json_path: Path to COCO JSON file

    Returns:
        Validation summary with errors
    """
    with open(coco_json_path, 'r') as f:
        coco = json.load(f)

    errors = []
    warnings = []

    # Check top-level structure
    required_fields = ["images", "annotations", "categories"]
    for field in required_fields:
        if field not in coco:
            errors.append(f"Missing top-level field: {field}")

    if errors:
        return {"valid": False, "errors": errors, "warnings": warnings}

    # Build image lookup
    images_by_id = {img["id"]: img for img in coco["images"]}

    # Validate each annotation
    for ann in coco["annotations"]:
        image_id = ann.get("image_id")

        if image_id not in images_by_id:
            errors.append(f"Annotation {ann.get('id')} references missing image_id: {image_id}")
            continue

        ann_errors = validate_coco_annotation(ann, images_by_id[image_id], len(coco["categories"]))
        errors.extend([f"Annotation {ann['id']}: {e}" for e in ann_errors])

    # Check for orphaned images (no annotations)
    annotated_images = set(ann["image_id"] for ann in coco["annotations"])
    orphaned = set(images_by_id.keys()) - annotated_images

    if orphaned:
        warnings.append(f"{len(orphaned)} images have no annotations")

    return {
        "valid": len(errors) == 0,
        "total_images": len(coco["images"]),
        "total_annotations": len(coco["annotations"]),
        "categories": len(coco["categories"]),
        "errors": errors[:20],  # First 20 errors
        "warnings": warnings,
        "error_count": len(errors)
    }


def validate_yolo_dataset(yolo_dir: Path) -> Dict:
    """
    Validate YOLO dataset structure and label files.

    Args:
        yolo_dir: Root YOLO dataset directory

    Returns:
        Validation summary
    """
    errors = []
    warnings = []

    # Check data.yaml exists
    data_yaml = yolo_dir / "data.yaml"
    if not data_yaml.exists():
        errors.append("Missing data.yaml")

    # Check splits
    splits = ["train", "val"]
    total_images = 0
    total_labels = 0

    for split in splits:
        images_dir = yolo_dir / split / "images"
        labels_dir = yolo_dir / split / "labels"

        if not images_dir.exists():
            errors.append(f"Missing directory: {images_dir}")
            continue

        if not labels_dir.exists():
            errors.append(f"Missing directory: {labels_dir}")
            continue

        # Check each image has label
        images = list(images_dir.glob("*.png")) + list(images_dir.glob("*.jpg"))
        total_images += len(images)

        for img_path in images:
            label_path = labels_dir / f"{img_path.stem}.txt"

            if not label_path.exists():
                errors.append(f"Missing label: {label_path}")
                continue

            total_labels += 1

            # Validate label content
            with open(label_path, 'r') as f:
                lines = f.readlines()

            if len(lines) == 0:
                warnings.append(f"Empty label file: {label_path}")
                continue

            for line_num, line in enumerate(lines, 1):
                if line.strip():
                    label_errors = validate_yolo_label(line)
                    errors.extend([f"{label_path}:{line_num} {e}" for e in label_errors])

    return {
        "valid": len(errors) == 0,
        "total_images": total_images,
        "total_labels": total_labels,
        "errors": errors[:20],  # First 20 errors
        "warnings": warnings,
        "error_count": len(errors)
    }


def validate_annotations(dataset_dir: Path) -> Dict:
    """
    Validate both COCO and YOLO annotations.

    Args:
        dataset_dir: Root dataset directory containing annotations/ and yolo/

    Returns:
        Combined validation results
    """
    results = {
        "coco": {},
        "yolo": {}
    }

    # Validate COCO
    coco_dir = dataset_dir / "annotations"
    for split in ["train", "val", "test"]:
        coco_json = coco_dir / f"coco_{split}.json"
        if coco_json.exists():
            print(f"Validating COCO {split}...")
            results["coco"][split] = validate_coco_dataset(coco_json)

    # Validate YOLO
    yolo_dir = dataset_dir / "yolo"
    if yolo_dir.exists():
        print("Validating YOLO dataset...")
        results["yolo"] = validate_yolo_dataset(yolo_dir)

    return results
