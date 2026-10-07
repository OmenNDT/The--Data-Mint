"""Auto-label synthetic crack images using YOLOv8 + SAM.

Pipeline:
1. Train a quick YOLOv8 detector on the original crack dataset
2. Detect cracks in synthetic images
3. Use SAM to generate precise masks from bounding boxes
4. Export COCO + YOLO annotations
"""

import json
import logging
import os
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path("/home/sontn/Projects/The Data Mint")
SYNTH_DIR = PROJECT_ROOT / "output/synthetic/crack"
OUTPUT_DIR = PROJECT_ROOT / "output/auto-labeled/crack"
SAM_CHECKPOINT = PROJECT_ROOT / "models/sam/sam_vit_b_01ec64.pth"
YOLO_MODEL_PATH = PROJECT_ROOT / "models/yolo/crack_detector.pt"

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}


def prepare_yolo_training_data():
    """Prepare YOLO training data from original crack patches.

    Creates a minimal YOLO dataset from the processed crack images
    using simple thresholding to detect dark crack regions.
    """
    src_dir = PROJECT_ROOT / "dataset/processed/patches_512_Confimed/crack"
    yolo_dir = PROJECT_ROOT / "output/yolo_train_crack"
    images_dir = yolo_dir / "images/train"
    labels_dir = yolo_dir / "labels/train"

    images_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)

    crack_images = sorted(src_dir.glob("crack_*.png"))
    logger.info(f"Preparing YOLO data from {len(crack_images)} crack images")

    for img_path in crack_images:
        img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue

        # Copy image
        dst_img = images_dir / img_path.name
        cv2.imwrite(str(dst_img), cv2.imread(str(img_path)))

        # Auto-generate bbox using intensity analysis
        # Cracks appear as darker lines in X-ray images
        blurred = cv2.GaussianBlur(img, (5, 5), 0)
        mean_val = np.mean(blurred)

        # Threshold to find dark regions (potential cracks)
        thresh_val = max(mean_val * 0.7, 30)
        _, binary = cv2.threshold(blurred, thresh_val, 255, cv2.THRESH_BINARY_INV)

        # Morphological operations to clean up
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        h, w = img.shape
        labels = []

        # Find significant contours (potential cracks)
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < 100:  # Skip tiny noise
                continue

            x, y, bw, bh = cv2.boundingRect(cnt)

            # YOLO format: class cx cy w h (normalized)
            cx = (x + bw / 2) / w
            cy = (y + bh / 2) / h
            nw = bw / w
            nh = bh / h

            # Filter: crack-like aspect ratio (elongated)
            aspect = max(bw, bh) / (min(bw, bh) + 1e-6)
            if aspect > 1.5 or area > 500:
                labels.append(f"0 {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}")

        # Write label file
        label_path = labels_dir / img_path.with_suffix(".txt").name
        with open(label_path, "w") as f:
            f.write("\n".join(labels) if labels else "")

    # Create data.yaml
    data_yaml = yolo_dir / "data.yaml"
    with open(data_yaml, "w") as f:
        f.write(f"train: {images_dir}\n")
        f.write(f"val: {images_dir}\n")
        f.write("nc: 1\n")
        f.write("names: ['crack']\n")

    logger.info(f"YOLO training data prepared: {len(crack_images)} images")
    return str(data_yaml)


def train_yolo_detector(data_yaml: str):
    """Train a quick YOLOv8n detector for crack detection."""
    from ultralytics import YOLO

    YOLO_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)

    model = YOLO("yolov8n.pt")  # Start from pretrained nano
    logger.info("Training YOLOv8n crack detector (10 epochs)...")

    results = model.train(
        data=data_yaml,
        epochs=10,
        imgsz=512,
        batch=8,
        device=0,
        project=str(PROJECT_ROOT / "output/yolo_runs"),
        name="crack_detector",
        exist_ok=True,
        verbose=False,
    )

    # Save best model
    best_path = Path(results.save_dir) / "weights/best.pt"
    if best_path.exists():
        import shutil
        shutil.copy(best_path, YOLO_MODEL_PATH)
        logger.info(f"YOLO model saved to {YOLO_MODEL_PATH}")
    else:
        # Use last if best not available
        last_path = Path(results.save_dir) / "weights/last.pt"
        if last_path.exists():
            import shutil
            shutil.copy(last_path, YOLO_MODEL_PATH)
            logger.info(f"YOLO model (last) saved to {YOLO_MODEL_PATH}")

    return str(YOLO_MODEL_PATH)


def detect_and_segment(yolo_path: str):
    """Run detection + SAM segmentation on synthetic images."""
    from ultralytics import YOLO
    from segment_anything import sam_model_registry, SamPredictor

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    masks_dir = OUTPUT_DIR / "masks"
    masks_dir.mkdir(exist_ok=True)
    annotations_dir = OUTPUT_DIR / "annotations"
    annotations_dir.mkdir(exist_ok=True)

    # Load YOLO
    yolo = YOLO(yolo_path)

    # Load SAM
    logger.info(f"Loading SAM from {SAM_CHECKPOINT}")
    sam = sam_model_registry["vit_b"](checkpoint=str(SAM_CHECKPOINT))
    sam = sam.to("cuda")
    predictor = SamPredictor(sam)

    # Collect synthetic images
    synth_images = sorted([
        p for p in SYNTH_DIR.iterdir()
        if p.suffix.lower() in IMAGE_EXTENSIONS and p.name.startswith("synth_")
    ])
    logger.info(f"Processing {len(synth_images)} synthetic images")

    coco_annotations = {
        "images": [],
        "annotations": [],
        "categories": [{"id": 0, "name": "crack"}],
    }
    ann_id = 0

    for idx, img_path in enumerate(synth_images):
        img = cv2.imread(str(img_path))
        if img is None:
            continue

        h, w = img.shape[:2]

        # YOLO detection
        results = yolo(img, conf=0.25, verbose=False)
        boxes = results[0].boxes

        # Add image to COCO
        coco_annotations["images"].append({
            "id": idx,
            "file_name": img_path.name,
            "width": w,
            "height": h,
        })

        # YOLO label output
        yolo_labels = []

        if len(boxes) > 0:
            # SAM segmentation
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            predictor.set_image(img_rgb)

            for box in boxes:
                xyxy = box.xyxy[0].cpu().numpy()
                conf = float(box.conf[0])

                # SAM predict
                sam_box = np.array(xyxy)
                masks_pred, scores, _ = predictor.predict(
                    box=sam_box,
                    multimask_output=True,
                )

                # Use best mask
                best_idx = np.argmax(scores)
                mask = masks_pred[best_idx].astype(np.uint8) * 255

                # Save mask
                mask_name = f"{img_path.stem}_det{ann_id:03d}.png"
                cv2.imwrite(str(masks_dir / mask_name), mask)

                # Contour for COCO segmentation
                contours, _ = cv2.findContours(
                    mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
                )

                segmentation = []
                for cnt in contours:
                    if len(cnt) >= 3:
                        seg = cnt.flatten().tolist()
                        segmentation.append(seg)

                # Bbox in COCO format (x, y, w, h)
                x1, y1, x2, y2 = xyxy
                bbox = [float(x1), float(y1), float(x2 - x1), float(y2 - y1)]

                coco_annotations["annotations"].append({
                    "id": ann_id,
                    "image_id": idx,
                    "category_id": 0,
                    "bbox": bbox,
                    "area": float(bbox[2] * bbox[3]),
                    "segmentation": segmentation,
                    "iscrowd": 0,
                    "confidence": conf,
                })

                # YOLO format
                cx = (x1 + x2) / 2 / w
                cy = (y1 + y2) / 2 / h
                bw = (x2 - x1) / w
                bh = (y2 - y1) / h
                yolo_labels.append(f"0 {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")

                ann_id += 1

        # Write YOLO label
        label_path = annotations_dir / img_path.with_suffix(".txt").name
        with open(label_path, "w") as f:
            f.write("\n".join(yolo_labels))

        if (idx + 1) % 10 == 0 or idx == 0:
            det_count = len(boxes) if len(boxes) > 0 else 0
            logger.info(f"  [{idx + 1}/{len(synth_images)}] {img_path.name}: {det_count} detections")

    # Save COCO JSON
    coco_path = annotations_dir / "coco_annotations.json"
    with open(coco_path, "w") as f:
        json.dump(coco_annotations, f, indent=2)

    total_dets = len(coco_annotations["annotations"])
    logger.info(f"Auto-labeling complete: {total_dets} detections in {len(synth_images)} images")
    logger.info(f"COCO annotations: {coco_path}")
    logger.info(f"YOLO labels: {annotations_dir}")
    logger.info(f"Masks: {masks_dir}")

    return total_dets


def main():
    start = time.time()

    # Step 1: Prepare YOLO training data
    logger.info("=== Step 1: Prepare YOLO training data ===")
    data_yaml = prepare_yolo_training_data()

    # Step 2: Train YOLO detector
    logger.info("=== Step 2: Train YOLO crack detector ===")
    if YOLO_MODEL_PATH.exists():
        logger.info(f"Using existing model: {YOLO_MODEL_PATH}")
        yolo_path = str(YOLO_MODEL_PATH)
    else:
        yolo_path = train_yolo_detector(data_yaml)

    # Step 3: Detect + Segment
    logger.info("=== Step 3: Auto-label synthetic images ===")
    total = detect_and_segment(yolo_path)

    elapsed = time.time() - start
    logger.info(f"=== Done in {elapsed:.1f}s: {total} total detections ===")


if __name__ == "__main__":
    main()
