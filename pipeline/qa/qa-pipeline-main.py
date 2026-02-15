#!/usr/bin/env python3
"""
QA Pipeline Main Entry Point

Runs automated quality assurance checks on synthetic dataset:
1. SSIM background preservation check
2. Annotation validation (COCO + YOLO)
3. Defect distribution verification
4. Visual spot-check gallery generation
5. Generate comprehensive QA report
"""

import argparse
import json
import sys
import time
from pathlib import Path
from collections import defaultdict
from importlib import import_module

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import directly from modules to avoid circular import
ssim_module = import_module('qa.ssim-background-checker')
annotation_module = import_module('qa.annotation-validator')
spot_check_module = import_module('qa.visual-spot-check-grid')

check_ssim_background = ssim_module.check_ssim_background
batch_check_ssim = ssim_module.batch_check_ssim
validate_annotations = annotation_module.validate_annotations
create_spot_check_grid = spot_check_module.create_spot_check_grid


def check_defect_distribution(synthetic_dir: Path, expected_distribution: dict) -> dict:
    """
    Verify defect type distribution matches configuration.

    Args:
        synthetic_dir: Directory containing synthetic output
        expected_distribution: Dict mapping defect_type to expected ratio

    Returns:
        Distribution analysis with deviations
    """
    counts = defaultdict(int)
    total = 0

    # Count images by defect type
    for defect_dir in synthetic_dir.iterdir():
        if not defect_dir.is_dir():
            continue

        defect_type = defect_dir.name
        n_images = len([f for f in defect_dir.glob("*.png") if "_mask" not in f.name])
        counts[defect_type] = n_images
        total += n_images

    # Calculate actual vs expected
    actual_dist = {k: v / total for k, v in counts.items()} if total > 0 else {}

    deviations = {}
    max_deviation = 0.0

    for defect_type, expected_ratio in expected_distribution.items():
        actual_ratio = actual_dist.get(defect_type, 0.0)
        deviation_pct = abs(actual_ratio - expected_ratio) * 100
        deviations[defect_type] = {
            "expected": expected_ratio,
            "actual": actual_ratio,
            "deviation_pct": deviation_pct,
            "count": counts[defect_type]
        }
        max_deviation = max(max_deviation, deviation_pct)

    return {
        "total_images": total,
        "deviations": deviations,
        "max_deviation_pct": max_deviation,
        "passes": max_deviation <= 2.0  # 2% tolerance
    }


def run_qa_pipeline(
    synthetic_dir: Path,
    dataset_dir: Path,
    output_dir: Path,
    ssim_sample_size: int = 500,
    ssim_target: float = 0.90,
    spot_check_pct: float = 2.0,
    expected_distribution: dict = None
):
    """
    Run complete QA pipeline.

    Args:
        synthetic_dir: Directory with raw synthetic output
        dataset_dir: Directory with processed dataset (COCO/YOLO)
        output_dir: Directory to save QA reports
        ssim_sample_size: Number of images to check for SSIM
        ssim_target: Target SSIM threshold
        spot_check_pct: Percentage for spot-check sampling
        expected_distribution: Expected defect type distribution
    """
    start_time = time.time()

    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("QUALITY ASSURANCE PIPELINE - The Data Mint")
    print("=" * 80)

    qa_results = {}

    # Check 1: SSIM Background Preservation
    print("\n[1/4] Checking SSIM background preservation...")
    backgrounds_dir = Path("/mnt/e/The Data Mint/kohya-ss/training_data/reg/1_xray_clean")

    ssim_results = batch_check_ssim(
        synthetic_dir,
        backgrounds_dir,
        sample_size=ssim_sample_size,
        target_ssim=ssim_target
    )
    qa_results["ssim"] = ssim_results

    print(f"  Mean SSIM: {ssim_results['mean_ssim']:.3f} (target: {ssim_target})")
    print(f"  Pass rate: {ssim_results['pass_rate']*100:.1f}%")

    # Check 2: Annotation Validation
    print("\n[2/4] Validating annotations...")
    annotation_results = validate_annotations(dataset_dir)
    qa_results["annotations"] = annotation_results

    for format_type, results in annotation_results.items():
        if isinstance(results, dict) and "valid" in results:
            status = "✓ PASS" if results["valid"] else "✗ FAIL"
            print(f"  {format_type.upper()}: {status}")
            if results.get("error_count", 0) > 0:
                print(f"    Errors: {results['error_count']}")

    # Check 3: Defect Distribution
    print("\n[3/4] Verifying defect distribution...")
    if expected_distribution is None:
        expected_distribution = {
            "crack": 0.25,
            "porosity": 0.25,
            "inclusion": 0.20,
            "lack_of_fusion": 0.15,
            "undercut": 0.15
        }

    dist_results = check_defect_distribution(synthetic_dir, expected_distribution)
    qa_results["distribution"] = dist_results

    print(f"  Total images: {dist_results['total_images']}")
    print(f"  Max deviation: {dist_results['max_deviation_pct']:.2f}%")
    print(f"  Status: {'✓ PASS' if dist_results['passes'] else '✗ FAIL'}")

    # Check 4: Visual Spot Check
    print("\n[4/4] Generating visual spot-check gallery...")
    spot_check_path = output_dir / "spot-check-gallery.html"
    n_sampled = create_spot_check_grid(
        synthetic_dir,
        spot_check_path,
        sample_pct=spot_check_pct
    )

    # Generate QA Report
    print("\n[5/5] Generating QA report...")
    elapsed = time.time() - start_time

    report_md = generate_qa_report(qa_results, elapsed, spot_check_path)

    report_path = output_dir / "qa-report.md"
    with open(report_path, 'w') as f:
        f.write(report_md)

    # Save JSON results
    json_path = output_dir / "qa-results.json"
    with open(json_path, 'w') as f:
        json.dump(qa_results, f, indent=2)

    print(f"\n✓ QA report saved: {report_path}")
    print(f"✓ QA results JSON: {json_path}")
    print(f"✓ Spot-check gallery: {spot_check_path}")

    # Print summary
    print("\n" + "=" * 80)
    print("QA PIPELINE SUMMARY")
    print("=" * 80)
    print(f"SSIM:         {'✓ PASS' if ssim_results['pass_rate'] > 0.90 else '✗ FAIL'} ({ssim_results['pass_rate']*100:.1f}%)")
    print(f"Annotations:  {'✓ PASS' if all(r.get('valid', False) for r in annotation_results.values() if isinstance(r, dict) and 'valid' in r) else '✗ FAIL'}")
    print(f"Distribution: {'✓ PASS' if dist_results['passes'] else '✗ FAIL'}")
    print(f"Processing time: {elapsed:.1f}s")
    print("=" * 80)


def generate_qa_report(qa_results: dict, elapsed: float, spot_check_path: Path) -> str:
    """Generate markdown QA report."""

    report = f"""# Quality Assurance Report
## The Data Mint Synthetic X-ray Defect Dataset

**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}
**Processing Time:** {elapsed:.1f} seconds

---

## Summary

"""

    # SSIM Summary
    ssim = qa_results.get("ssim", {})
    ssim_status = "✓ PASS" if ssim.get("pass_rate", 0) > 0.90 else "✗ FAIL"
    report += f"""
### SSIM Background Preservation {ssim_status}

- **Checked:** {ssim.get('total_checked', 0)} images
- **Mean SSIM:** {ssim.get('mean_ssim', 0):.3f} (target: {ssim.get('target_ssim', 0.90)})
- **Pass Rate:** {ssim.get('pass_rate', 0)*100:.1f}%
- **Range:** {ssim.get('min_ssim', 0):.3f} - {ssim.get('max_ssim', 0):.3f}

"""

    # Annotation Summary
    report += "### Annotation Validation\n\n"
    annotations = qa_results.get("annotations", {})

    for format_type, results in annotations.items():
        if isinstance(results, dict):
            if "valid" in results:
                status = "✓ PASS" if results["valid"] else "✗ FAIL"
                report += f"**{format_type.upper()}:** {status}\n"
                report += f"- Images: {results.get('total_images', 0)}\n"
                report += f"- Annotations/Labels: {results.get('total_annotations', 0) or results.get('total_labels', 0)}\n"
                if results.get("error_count", 0) > 0:
                    report += f"- Errors: {results['error_count']}\n"
                report += "\n"

    # Distribution Summary
    dist = qa_results.get("distribution", {})
    dist_status = "✓ PASS" if dist.get("passes", False) else "✗ FAIL"
    report += f"""
### Defect Distribution {dist_status}

**Total Images:** {dist.get('total_images', 0)}
**Max Deviation:** {dist.get('max_deviation_pct', 0):.2f}% (tolerance: 2%)

| Defect Type | Expected | Actual | Count | Deviation |
|-------------|----------|--------|-------|-----------|
"""

    for defect_type, data in dist.get("deviations", {}).items():
        report += f"| {defect_type} | {data['expected']*100:.1f}% | {data['actual']*100:.1f}% | {data['count']} | {data['deviation_pct']:.2f}% |\n"

    # Spot Check
    report += f"""

### Visual Spot Check

Manual review gallery generated: [{spot_check_path.name}]({spot_check_path.name})

**Review Checklist:**
- [ ] Defects look realistic
- [ ] Correct weld zone placement
- [ ] Background undistorted
- [ ] No color artifacts
- [ ] Annotations match defects

---

## Recommendations

"""

    # Add recommendations based on results
    if ssim.get("pass_rate", 0) < 0.90:
        report += "- ⚠️ **SSIM pass rate below 90%** - Review inpainting quality, consider adjusting LoRA strength\n"

    if not dist.get("passes", False):
        report += "- ⚠️ **Distribution deviation >2%** - Adjust batch generation config to balance defect types\n"

    for format_type, results in annotations.items():
        if isinstance(results, dict) and not results.get("valid", True):
            report += f"- ⚠️ **{format_type.upper()} validation failed** - Review annotation conversion pipeline\n"

    if ssim.get("pass_rate", 0) >= 0.90 and dist.get("passes", False):
        report += "- ✓ **All automated checks passed** - Proceed with downstream validation (Phase 9)\n"

    return report


def main():
    parser = argparse.ArgumentParser(description="QA pipeline for synthetic dataset")
    parser.add_argument(
        "--synthetic-dir",
        type=Path,
        default=Path("/mnt/e/The Data Mint/output/synthetic"),
        help="Directory with raw synthetic output"
    )
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=Path("/mnt/e/The Data Mint/output/dataset"),
        help="Directory with processed dataset"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/mnt/e/The Data Mint/output/qa-reports"),
        help="Output directory for QA reports"
    )
    parser.add_argument(
        "--ssim-sample-size",
        type=int,
        default=500,
        help="Number of images to check for SSIM"
    )
    parser.add_argument(
        "--ssim-target",
        type=float,
        default=0.90,
        help="Target SSIM threshold"
    )
    parser.add_argument(
        "--spot-check-pct",
        type=float,
        default=2.0,
        help="Percentage for spot-check sampling"
    )

    args = parser.parse_args()

    run_qa_pipeline(
        synthetic_dir=args.synthetic_dir,
        dataset_dir=args.dataset_dir,
        output_dir=args.output_dir,
        ssim_sample_size=args.ssim_sample_size,
        ssim_target=args.ssim_target,
        spot_check_pct=args.spot_check_pct
    )


if __name__ == "__main__":
    main()
