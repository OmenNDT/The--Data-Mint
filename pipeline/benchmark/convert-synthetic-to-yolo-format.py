"""
Convert synthetic images + binary masks to YOLO bounding box format.

For each synthetic image, finds its corresponding mask and computes
the YOLO-format bounding box label.

Usage:
    python3 pipeline/benchmark/convert-synthetic-to-yolo-format.py \
        --input-dir output/benchmark/medxray \
        --output-dir output/benchmark/validation/datasets/medxray
"""

import logging
import argparse
import shutil
from pathlib import Path

import cv2

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DEFECT_CLASS_MAP = {
    "crack": 0,
    "porosity": 1,
    "inclusion": 2,
    "lack_of_fusion": 3,
    "undercut": 4,
}


def mask_to_yolo_bbox(mask_path: str, class_id: int) -> str:
    """Convert binary mask to YOLO bbox format.

    Returns YOLO label string: "class_id cx cy w h" (normalized 0-1),
    or empty string if no contour found.
    """
    mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)
    if mask is None:
        return ""

    h, w = mask.shape
    _, binary = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        return ""

    # Get bounding rect of largest contour
    largest = max(contours, key=cv2.contourArea)
    if cv2.contourArea(largest) < 1:
        return ""

    x, y, bw, bh = cv2.boundingRect(largest)
    if bw < 1 or bh < 1:
        return ""

    # Normalize to [0, 1] and clamp
    cx = max(0.0, min(1.0, (x + bw / 2) / w))
    cy = max(0.0, min(1.0, (y + bh / 2) / h))
    nw = max(0.0, min(1.0, bw / w))
    nh = max(0.0, min(1.0, bh / h))

    return f"{class_id} {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}"


def convert_model_dataset(
    input_dir: Path, output_dir: Path, mask_dir: Path | None = None
):
    """Convert a model's synthetic output to YOLO dataset format.

    Args:
        input_dir: Directory with defect subdirs containing generated images
        output_dir: YOLO dataset output directory
        mask_dir: Optional separate mask directory (defaults to input_dir/*/masks/)
    """
    images_out = output_dir / "images" / "train"
    labels_out = output_dir / "labels" / "train"
    images_out.mkdir(parents=True, exist_ok=True)
    labels_out.mkdir(parents=True, exist_ok=True)

    total = 0
    skipped = 0

    for defect, class_id in DEFECT_CLASS_MAP.items():
        defect_dir = input_dir / defect
        if not defect_dir.exists():
            logger.warning(f"Missing defect dir: {defect_dir}")
            continue

        for img_path in sorted(defect_dir.glob("*.png")):
            # Skip mask files
            if "mask" in img_path.stem.lower():
                continue

            # Find corresponding mask
            mask_path = None
            if mask_dir:
                mask_path = mask_dir / defect / f"{img_path.stem}_mask.png"
            else:
                # Check common mask locations
                for candidate in [
                    defect_dir / "masks" / f"{img_path.stem}_mask.png",
                    defect_dir / f"{img_path.stem}_mask.png",
                    defect_dir / "masks" / img_path.name,
                ]:
                    if candidate.exists():
                        mask_path = candidate
                        break

            if mask_path is None or not mask_path.exists():
                skipped += 1
                continue

            # Convert mask to YOLO label
            label = mask_to_yolo_bbox(str(mask_path), class_id)
            if not label:
                skipped += 1
                continue

            # Copy image and write label
            dst_img = images_out / img_path.name
            dst_label = labels_out / f"{img_path.stem}.txt"

            shutil.copy2(img_path, dst_img)
            dst_label.write_text(label + "\n")
            total += 1

    logger.info(f"Converted {total} images, skipped {skipped}")
    return total


def write_data_yaml(output_dir: Path, val_images_dir: Path | None = None):
    """Write YOLO data.yaml config."""
    data = {
        "path": str(output_dir),
        "train": "images/train",
        "nc": 5,
        "names": list(DEFECT_CLASS_MAP.keys()),
    }
    if val_images_dir:
        data["val"] = str(val_images_dir)

    yaml_path = output_dir / "data.yaml"
    import yaml
    with open(yaml_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False)
    logger.info(f"Wrote: {yaml_path}")


def main():
    parser = argparse.ArgumentParser(description="Convert synthetic to YOLO format")
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--mask-dir", type=Path, default=None)
    parser.add_argument("--val-dir", type=Path, default=None, help="Real validation images dir")
    args = parser.parse_args()

    total = convert_model_dataset(args.input_dir, args.output_dir, args.mask_dir)
    write_data_yaml(args.output_dir, args.val_dir)
    logger.info(f"Done: {total} images converted to YOLO format")


if __name__ == "__main__":
    main()
