#!/usr/bin/env python3
"""
Post-Processing Pipeline Main Entry Point

Orchestrates conversion of raw synthetic output to annotated datasets:
1. Load all synthetic images + masks + metadata
2. Split into train/val/test with stratification
3. Build COCO JSON format annotations
4. Build YOLO format dataset with labels
5. Validate both formats
6. Generate summary report
"""

import argparse
import sys
import time
from pathlib import Path
from importlib import import_module

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import directly from modules to avoid circular import
splitter = import_module('post_processing.dataset-splitter')
coco_builder = import_module('post_processing.coco-dataset-builder')
yolo_builder = import_module('post_processing.yolo-dataset-builder')

split_dataset = splitter.split_dataset
verify_split_distribution = splitter.verify_split_distribution
build_coco_dataset = coco_builder.build_coco_dataset
validate_coco_format = coco_builder.validate_coco_format
build_yolo_dataset = yolo_builder.build_yolo_dataset
create_yolo_data_yaml = yolo_builder.create_yolo_data_yaml
validate_yolo_format = yolo_builder.validate_yolo_format


def run_post_processing(
    synthetic_dir: Path,
    output_dir: Path,
    train_ratio: float = 0.70,
    val_ratio: float = 0.20,
    test_ratio: float = 0.10,
    skip_validation: bool = False
):
    """
    Run complete post-processing pipeline.

    Args:
        synthetic_dir: Path to output/synthetic directory with raw output
        output_dir: Path to output/dataset directory for processed annotations
        train_ratio: Training set fraction
        val_ratio: Validation set fraction
        test_ratio: Test set fraction
        skip_validation: Skip COCO/YOLO validation (if libraries not installed)
    """
    start_time = time.time()

    print("=" * 80)
    print("POST-PROCESSING PIPELINE - The Data Mint")
    print("=" * 80)

    # Step 1: Load and split dataset
    print("\n[1/5] Loading and splitting dataset...")
    splits = split_dataset(
        synthetic_dir,
        train_ratio=train_ratio,
        val_ratio=val_ratio,
        test_ratio=test_ratio,
        random_seed=42
    )
    verify_split_distribution(splits)

    # Step 2: Build COCO format
    print("\n[2/5] Building COCO format annotations...")
    coco_output_dir = output_dir / "annotations"
    coco_output_dir.mkdir(parents=True, exist_ok=True)

    for split_name, split_data in splits.items():
        if len(split_data) > 0:
            build_coco_dataset(split_data, split_name, coco_output_dir)

    # Step 3: Build YOLO format
    print("\n[3/5] Building YOLO format dataset...")
    yolo_output_dir = output_dir / "yolo"
    yolo_output_dir.mkdir(parents=True, exist_ok=True)

    for split_name, split_data in splits.items():
        if len(split_data) > 0:
            build_yolo_dataset(split_data, split_name, yolo_output_dir)

    create_yolo_data_yaml(yolo_output_dir)

    # Step 4: Validation
    if not skip_validation:
        print("\n[4/5] Validating dataset formats...")

        # Validate COCO
        for split_name in ["train", "val", "test"]:
            coco_json = coco_output_dir / f"coco_{split_name}.json"
            if coco_json.exists():
                validate_coco_format(coco_json)

        # Validate YOLO
        validate_yolo_format(yolo_output_dir)
    else:
        print("\n[4/5] Skipping validation (--skip-validation flag)")

    # Step 5: Generate summary report
    print("\n[5/5] Generating summary report...")
    elapsed = time.time() - start_time

    report = f"""
{'=' * 80}
POST-PROCESSING PIPELINE SUMMARY
{'=' * 80}

Input Directory:  {synthetic_dir}
Output Directory: {output_dir}

Dataset Split:
  Train: {len(splits['train'])} images ({len(splits['train'])/sum(len(s) for s in splits.values())*100:.1f}%)
  Val:   {len(splits['val'])} images ({len(splits['val'])/sum(len(s) for s in splits.values())*100:.1f}%)
  Test:  {len(splits['test'])} images ({len(splits['test'])/sum(len(s) for s in splits.values())*100:.1f}%)
  Total: {sum(len(s) for s in splits.values())} images

Output Formats:
  ✓ COCO JSON: {coco_output_dir}
  ✓ YOLO TXT:  {yolo_output_dir}

Processing Time: {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)

Next Steps:
  - Review annotations in {coco_output_dir}
  - Train YOLO model using {yolo_output_dir / 'data.yaml'}
  - Run QA pipeline to validate quality

{'=' * 80}
"""

    print(report)

    # Save report to file
    report_path = output_dir / "post-processing-report.txt"
    with open(report_path, 'w') as f:
        f.write(report)

    print(f"\n✓ Report saved to: {report_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Post-processing pipeline for synthetic X-ray defect dataset"
    )
    parser.add_argument(
        "--synthetic-dir",
        type=Path,
        default=Path("/mnt/e/The Data Mint/output/synthetic"),
        help="Directory containing raw synthetic output"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/mnt/e/The Data Mint/output/dataset"),
        help="Output directory for processed datasets"
    )
    parser.add_argument(
        "--train-ratio",
        type=float,
        default=0.70,
        help="Training set ratio (default: 0.70)"
    )
    parser.add_argument(
        "--val-ratio",
        type=float,
        default=0.20,
        help="Validation set ratio (default: 0.20)"
    )
    parser.add_argument(
        "--test-ratio",
        type=float,
        default=0.10,
        help="Test set ratio (default: 0.10)"
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip COCO/YOLO validation (useful if pycocotools not installed)"
    )

    args = parser.parse_args()

    run_post_processing(
        synthetic_dir=args.synthetic_dir,
        output_dir=args.output_dir,
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
        test_ratio=args.test_ratio,
        skip_validation=args.skip_validation
    )


if __name__ == "__main__":
    main()
