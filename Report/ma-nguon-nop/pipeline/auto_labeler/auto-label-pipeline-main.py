"""Auto-label pipeline orchestrator and CLI entry point.

Chains YOLO detection -> SAM segmentation -> mask export -> annotation build.
Reuses existing post_processing converters for COCO/YOLO output.
"""

import argparse
import logging
import os
import sys
import time
from pathlib import Path
from typing import Callable, List, Optional

import cv2
import numpy as np
import yaml
from importlib import import_module

# Internal imports via importlib (hyphenated filenames)
_dataclass_mod = import_module(
    ".detection-result-dataclass", package="auto_labeler"
)
AutoLabelConfig = _dataclass_mod.AutoLabelConfig
AutoLabelResult = _dataclass_mod.AutoLabelResult
ImageAutoLabelResult = _dataclass_mod.ImageAutoLabelResult

_detector_mod = import_module(
    ".yolo-defect-detector", package="auto_labeler"
)
load_yolo_model = _detector_mod.load_yolo_model
detect_defects_batch = _detector_mod.detect_defects_batch

_segmenter_mod = import_module(
    ".sam-mask-segmenter", package="auto_labeler"
)
load_sam_model = _segmenter_mod.load_sam_model
generate_masks_from_bboxes = _segmenter_mod.generate_masks_from_bboxes

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif"}


def collect_images(input_dir: str) -> List[str]:
    """Collect all image files from a directory (non-recursive).

    Args:
        input_dir: Path to folder containing images

    Returns:
        Sorted list of absolute image paths
    """
    folder = Path(input_dir)
    if not folder.is_dir():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    paths = [
        str(p) for p in sorted(folder.iterdir())
        if p.suffix.lower() in IMAGE_EXTENSIONS and p.is_file()
    ]
    logger.info(f"Found {len(paths)} images in {input_dir}")
    return paths


def save_masks(
    image_results: List[ImageAutoLabelResult],
    output_dir: Path,
) -> List[dict]:
    """Save binary masks as PNG and build image-mask pair list.

    Follows the project naming convention: mask saved next to image reference.

    Args:
        image_results: Pipeline results with masks
        output_dir: Directory to save mask PNGs

    Returns:
        List of dicts compatible with build_coco_dataset / build_yolo_dataset
    """
    masks_dir = output_dir / "masks"
    masks_dir.mkdir(parents=True, exist_ok=True)

    pairs = []
    for img_result in image_results:
        for det_idx, seg in enumerate(img_result.detections):
            stem = img_result.image_path.stem
            mask_name = f"{stem}_det{det_idx:02d}.png"
            mask_path = masks_dir / mask_name
            cv2.imwrite(str(mask_path), seg.mask)

            pairs.append({
                "image_path": str(img_result.image_path),
                "mask_path": str(mask_path),
                "defect_type": seg.detection.class_name,
            })

    logger.info(f"Saved {len(pairs)} masks to {masks_dir}")
    return pairs


def build_annotations(
    pairs: List[dict],
    output_dir: Path,
    output_coco: bool = True,
    output_yolo: bool = True,
):
    """Build COCO and/or YOLO annotations from image-mask pairs.

    Reuses existing post_processing builders.

    Args:
        pairs: List of {image_path, mask_path, defect_type} dicts
        output_dir: Root output directory
        output_coco: Whether to build COCO JSON
        output_yolo: Whether to build YOLO dataset
    """
    if not pairs:
        logger.warning("No pairs to annotate")
        return

    if output_coco:
        try:
            coco_mod = import_module(
                ".coco-dataset-builder", package="post_processing"
            )
            coco_dir = output_dir / "annotations"
            coco_mod.build_coco_dataset(pairs, "auto_labeled", coco_dir)
            logger.info(f"COCO annotations saved to {coco_dir}")
        except Exception as e:
            logger.error(f"COCO build failed: {e}")

    if output_yolo:
        try:
            yolo_mod = import_module(
                ".yolo-dataset-builder", package="post_processing"
            )
            yolo_dir = output_dir / "yolo"
            yolo_mod.build_yolo_dataset(pairs, "auto_labeled", yolo_dir)
            yolo_mod.create_yolo_data_yaml(yolo_dir, "auto_labeled_defects")
            logger.info(f"YOLO dataset saved to {yolo_dir}")
        except Exception as e:
            logger.error(f"YOLO build failed: {e}")


def run_auto_labeling(
    config: AutoLabelConfig,
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
) -> AutoLabelResult:
    """Run the full auto-labeling pipeline.

    Steps:
        1. Collect images
        2. YOLO detection
        3. SAM segmentation
        4. Save masks
        5. Build annotations

    Args:
        config: Pipeline configuration
        progress_callback: Optional (stage, current, total) callback

    Returns:
        AutoLabelResult with all detection/segmentation data
    """
    start_time = time.time()
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    def _progress(stage, cur, total):
        if progress_callback:
            progress_callback(stage, cur, total)

    # 1. Collect images
    _progress("collect", 0, 1)
    try:
        image_paths = collect_images(config.input_dir)
    except FileNotFoundError as e:
        return AutoLabelResult(error=str(e))

    if not image_paths:
        return AutoLabelResult(error="No images found in input directory")

    _progress("collect", 1, 1)

    # 2. YOLO detection
    _progress("detect", 0, len(image_paths))
    try:
        yolo_model = load_yolo_model(config.yolo_weights, config.device)
    except Exception as e:
        return AutoLabelResult(error=f"Failed to load YOLO model: {e}")

    detection_map = detect_defects_batch(
        yolo_model,
        image_paths,
        config,
        progress_callback=lambda c, t: _progress("detect", c, t),
    )

    # 3. SAM segmentation
    _progress("segment", 0, len(image_paths))
    try:
        _, predictor = load_sam_model(
            config.sam_checkpoint, config.sam_model_type, config.device
        )
    except Exception as e:
        return AutoLabelResult(error=f"Failed to load SAM model: {e}")

    image_results = generate_masks_from_bboxes(
        predictor,
        detection_map,
        progress_callback=lambda c, t: _progress("segment", c, t),
    )

    # 4. Save masks
    _progress("save", 0, 1)
    pairs = []
    if config.save_masks:
        pairs = save_masks(image_results, output_dir)
    _progress("save", 1, 1)

    # 5. Build annotations
    _progress("annotate", 0, 1)
    build_annotations(
        pairs, output_dir,
        output_coco=config.output_coco,
        output_yolo=config.output_yolo,
    )
    _progress("annotate", 1, 1)

    total_dets = sum(r.num_detections for r in image_results)
    elapsed = time.time() - start_time
    logger.info(
        f"Auto-labeling complete: {total_dets} detections in "
        f"{len(image_paths)} images ({elapsed:.1f}s)"
    )

    return AutoLabelResult(
        image_results=image_results,
        total_images=len(image_paths),
        total_detections=total_dets,
        output_dir=output_dir,
    )


def load_config_from_yaml(yaml_path: str) -> AutoLabelConfig:
    """Load AutoLabelConfig from a YAML file.

    Args:
        yaml_path: Path to auto-label-config.yaml

    Returns:
        AutoLabelConfig instance
    """
    with open(yaml_path, "r") as f:
        data = yaml.safe_load(f)

    models = data.get("models", {})
    detection = data.get("detection", {})
    processing = data.get("processing", {})
    output = data.get("output", {})

    return AutoLabelConfig(
        yolo_weights=models.get("yolo_weights", ""),
        sam_checkpoint=models.get("sam_checkpoint", ""),
        sam_model_type=models.get("sam_model_type", "vit_b"),
        confidence_threshold=detection.get("confidence_threshold", 0.5),
        max_detections_per_image=detection.get("max_detections_per_image", 20),
        batch_size=processing.get("batch_size", 8),
        device=processing.get("device", "cuda:0"),
        save_masks=output.get("save_masks", True),
        output_coco=output.get("output_coco", True),
        output_yolo=output.get("output_yolo", True),
        output_dir=output.get("output_dir", "output/auto-labeled"),
    )


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Auto-label X-ray images with YOLO + SAM"
    )
    parser.add_argument(
        "--input-dir", required=True,
        help="Directory containing images to label",
    )
    parser.add_argument(
        "--yolo-weights", required=True,
        help="Path to YOLO .pt weights file",
    )
    parser.add_argument(
        "--sam-weights", required=True,
        help="Path to SAM .pth checkpoint",
    )
    parser.add_argument(
        "--sam-type", default="vit_b",
        choices=["vit_b", "vit_l", "vit_h"],
        help="SAM model type (default: vit_b)",
    )
    parser.add_argument(
        "--confidence", type=float, default=0.5,
        help="Detection confidence threshold (default: 0.5)",
    )
    parser.add_argument(
        "--output-dir", default="output/auto-labeled",
        help="Output directory (default: output/auto-labeled)",
    )
    parser.add_argument(
        "--device", default="cuda:0",
        help="Torch device (default: cuda:0)",
    )
    parser.add_argument(
        "--config", default=None,
        help="Path to auto-label-config.yaml (overrides other flags)",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.config:
        config = load_config_from_yaml(args.config)
        config.input_dir = args.input_dir
    else:
        config = AutoLabelConfig(
            input_dir=args.input_dir,
            yolo_weights=args.yolo_weights,
            sam_checkpoint=args.sam_weights,
            sam_model_type=args.sam_type,
            confidence_threshold=args.confidence,
            output_dir=args.output_dir,
            device=args.device,
        )

    def cli_progress(stage, current, total):
        print(f"  [{stage}] {current}/{total}", end="\r", flush=True)

    result = run_auto_labeling(config, progress_callback=cli_progress)

    if result.success:
        print(f"\nDone: {result.total_detections} detections "
              f"in {result.total_images} images")
        print(f"Output: {result.output_dir}")
    else:
        print(f"\nError: {result.error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
