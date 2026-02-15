#!/usr/bin/env python3
"""
Downstream Validation Main Entry Point

Validates synthetic dataset quality by training YOLOv8 detectors:
1. Prepare real test set (held-out, never used in training)
2. Create experiment datasets with different synthetic ratios
3. Train YOLOv8 on each configuration
4. Evaluate all models on real test set
5. Compare results and generate validation report
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import List, Dict
from importlib import import_module

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import directly from modules to avoid circular import
trainer_module = import_module('validation.yolo-trainer')
metrics_module = import_module('validation.evaluation-metrics')

train_yolo = trainer_module.train_yolo
create_mixed_dataset_yaml = trainer_module.create_mixed_dataset_yaml
evaluate_model = metrics_module.evaluate_model
compare_experiments = metrics_module.compare_experiments
generate_comparison_table = metrics_module.generate_comparison_table
generate_per_class_table = metrics_module.generate_per_class_table
analyze_per_class_improvement = metrics_module.analyze_per_class_improvement


def run_validation(
    real_yolo_dir: Path,
    synth_yolo_dir: Path,
    output_dir: Path,
    model_size: str = "n",
    epochs: int = 100,
    batch_size: int = 16,
    synthetic_ratios: List[float] = None,
    skip_training: bool = False
):
    """
    Run complete downstream validation pipeline.

    Args:
        real_yolo_dir: Path to real dataset in YOLO format
        synth_yolo_dir: Path to synthetic dataset in YOLO format
        output_dir: Output directory for experiments
        model_size: YOLOv8 model size (n, s, m, l, x)
        epochs: Training epochs
        batch_size: Batch size
        synthetic_ratios: List of synthetic ratios to test
        skip_training: Skip training and only evaluate existing models
    """
    start_time = time.time()

    output_dir.mkdir(parents=True, exist_ok=True)
    datasets_dir = output_dir / "datasets"
    results_dir = output_dir / "results"
    datasets_dir.mkdir(exist_ok=True)
    results_dir.mkdir(exist_ok=True)

    print("=" * 80)
    print("DOWNSTREAM VALIDATION PIPELINE - The Data Mint")
    print("=" * 80)

    if synthetic_ratios is None:
        synthetic_ratios = [0.0, 0.10, 0.20, 0.30, 0.50, 1.0]

    experiments = []

    # Define experiments
    for ratio in synthetic_ratios:
        if ratio == 0.0:
            exp_name = "real-only"
        elif ratio == 1.0:
            exp_name = "synth-only"
        else:
            exp_name = f"real-synth-{int(ratio*100)}"

        experiments.append({
            "name": exp_name,
            "synth_ratio": ratio
        })

    print(f"\nConfigured {len(experiments)} experiments:")
    for exp in experiments:
        print(f"  - {exp['name']}: {exp['synth_ratio']*100:.0f}% synthetic")

    # Step 1: Create mixed datasets
    if not skip_training:
        print(f"\n[1/3] Creating mixed datasets...")
        for exp in experiments:
            print(f"\nPreparing {exp['name']}...")
            data_yaml = create_mixed_dataset_yaml(
                real_yolo_dir=real_yolo_dir,
                synth_yolo_dir=synth_yolo_dir,
                synth_ratio=exp["synth_ratio"],
                output_dir=datasets_dir,
                experiment_name=exp["name"],
                seed=42
            )
            exp["data_yaml"] = data_yaml
    else:
        print("\n[1/3] Skipping dataset creation (--skip-training)")
        for exp in experiments:
            exp["data_yaml"] = datasets_dir / exp["name"] / "data.yaml"

    # Step 2: Train models
    training_results = []

    if not skip_training:
        print(f"\n[2/3] Training YOLOv8{model_size} models...")
        print(f"  Epochs: {epochs}, Batch: {batch_size}")
        print(f"  This will take approximately {len(experiments) * epochs / 50} - {len(experiments) * epochs / 30} minutes")

        for i, exp in enumerate(experiments, 1):
            print(f"\n{'='*60}")
            print(f"Training {i}/{len(experiments)}: {exp['name']}")
            print(f"{'='*60}")

            train_result = train_yolo(
                data_yaml_path=exp["data_yaml"],
                experiment_name=exp["name"],
                output_dir=results_dir,
                model_size=model_size,
                epochs=epochs,
                batch_size=batch_size,
                device=0
            )

            training_results.append(train_result)
            exp["weights_path"] = train_result["weights_path"]
    else:
        print("\n[2/3] Skipping training (--skip-training)")
        for exp in experiments:
            exp["weights_path"] = results_dir / exp["name"] / "weights" / "best.pt"

    # Step 3: Evaluate all models on real test set
    print(f"\n[3/3] Evaluating models on held-out real test set...")

    # Use real dataset's test split as ground truth
    test_data_yaml = real_yolo_dir / "data.yaml"

    if not test_data_yaml.exists():
        print(f"⚠️  Warning: Test data.yaml not found at {test_data_yaml}")
        print("    Using synthetic dataset for evaluation (not ideal)")
        test_data_yaml = synth_yolo_dir / "data.yaml"

    evaluation_results = []

    for exp in experiments:
        weights_path = Path(exp["weights_path"])

        if not weights_path.exists():
            print(f"⚠️  Warning: Weights not found for {exp['name']}, skipping evaluation")
            continue

        eval_result = evaluate_model(
            weights_path=weights_path,
            test_data_yaml=test_data_yaml,
            experiment_name=exp["name"],
            device=0
        )

        evaluation_results.append(eval_result)

    # Step 4: Generate validation report
    print("\n[4/4] Generating validation report...")

    comparison = compare_experiments(evaluation_results)

    report = generate_validation_report(
        evaluation_results,
        comparison,
        experiments,
        time.time() - start_time
    )

    report_path = output_dir / "validation-report.md"
    with open(report_path, 'w') as f:
        f.write(report)

    # Save JSON results
    json_path = output_dir / "validation-results.json"
    with open(json_path, 'w') as f:
        json.dump({
            "experiments": experiments,
            "evaluation_results": evaluation_results,
            "comparison": comparison
        }, f, indent=2, default=str)

    print(f"\n✓ Validation report: {report_path}")
    print(f"✓ Results JSON: {json_path}")

    # Print summary
    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)

    if comparison:
        print(f"Best Configuration: {comparison['best_experiment']}")
        print(f"  mAP@50: {comparison['best_mAP50']:.3f}")

        if comparison['improvement'] is not None:
            print(f"  Improvement over real-only: +{comparison['improvement']:.3f} ({comparison['improvement_pct']:.1f}%)")

    print(f"\nProcessing Time: {time.time() - start_time:.1f}s")
    print("=" * 80)


def generate_validation_report(
    evaluation_results: List[Dict],
    comparison: Dict,
    experiments: List[Dict],
    elapsed: float
) -> str:
    """Generate markdown validation report."""

    report = f"""# Downstream Validation Report
## The Data Mint Synthetic X-ray Defect Dataset

**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}
**Processing Time:** {elapsed/60:.1f} minutes

---

## Executive Summary

"""

    if comparison:
        best_name = comparison["best_experiment"]
        best_map = comparison["best_mAP50"]
        baseline_map = comparison.get("baseline_mAP50", 0)
        improvement = comparison.get("improvement", 0)
        improvement_pct = comparison.get("improvement_pct", 0)

        if improvement and improvement > 0:
            report += f"""
**✓ VALIDATION PASSED**: Synthetic data improves performance

- **Best Configuration:** {best_name}
- **Best mAP@50:** {best_map:.3f}
- **Baseline (Real-only):** {baseline_map:.3f}
- **Improvement:** +{improvement:.3f} (+{improvement_pct:.1f}%)

**Recommendation:** Use {best_name} configuration for production dataset.
"""
        elif improvement and improvement < -0.03:
            report += f"""
**⚠️ VALIDATION FAILED**: Synthetic data degrades performance

- **Best Configuration:** {best_name}
- **Best mAP@50:** {best_map:.3f}
- **Baseline (Real-only):** {baseline_map:.3f}
- **Change:** {improvement:.3f} ({improvement_pct:.1f}%)

**Recommendation:** Review LoRA quality (Phase 3) and generation parameters before production use.
"""
        else:
            report += f"""
**~ VALIDATION NEUTRAL**: Synthetic data has minimal impact

- **Best Configuration:** {best_name}
- **Best mAP@50:** {best_map:.3f}
- **Baseline (Real-only):** {baseline_map:.3f}

**Recommendation:** Synthetic data may be used for data augmentation but yields limited gains.
"""

    report += "\n---\n\n## Results Overview\n\n"
    report += generate_comparison_table(evaluation_results)

    report += "\n## Per-Class Performance\n\n"
    report += generate_per_class_table(evaluation_results)

    # Find baseline for per-class analysis
    baseline = next((r for r in evaluation_results if "real-only" in r["experiment_name"]), None)

    if baseline:
        report += "\n## Per-Class Improvement Analysis\n\n"
        improvements = analyze_per_class_improvement(baseline, evaluation_results)

        for class_name, best in improvements.items():
            report += f"- **{class_name}:** Best with {best['experiment']} ({best['improvement']:+.3f})\n"

    report += "\n---\n\n## Experiment Configurations\n\n"
    for exp in experiments:
        report += f"### {exp['name']}\n"
        report += f"- Synthetic Ratio: {exp['synth_ratio']*100:.0f}%\n"
        report += f"- Dataset: `{exp.get('data_yaml', 'N/A')}`\n"
        report += f"- Weights: `{exp.get('weights_path', 'N/A')}`\n\n"

    report += "\n---\n\n## Recommendations\n\n"

    if comparison and comparison.get("improvement", 0) > 0.02:
        synth_ratio = next((e["synth_ratio"] for e in experiments if e["name"] == comparison["best_experiment"]), 0)
        report += f"""
1. **Production Configuration:** Use {int(synth_ratio*100)}% synthetic data ratio
2. **Scale-Up:** Generate {int(20000 / synth_ratio)} total images (to achieve ~20K effective training samples)
3. **Next Steps:** Monitor performance on real-world test cases
"""
    else:
        report += """
1. **Improve LoRA Quality:** Retrain LoRAs with more diverse real examples (Phase 3)
2. **Tune Generation Parameters:** Adjust LoRA strength, CFG, controlnet weight (Phase 4)
3. **Collect More Real Data:** Insufficient real data may limit baseline performance
"""

    return report


def main():
    parser = argparse.ArgumentParser(
        description="Downstream validation by training YOLO on synthetic data"
    )
    parser.add_argument(
        "--real-yolo-dir",
        type=Path,
        required=True,
        help="Path to real dataset in YOLO format"
    )
    parser.add_argument(
        "--synth-yolo-dir",
        type=Path,
        default=Path("/mnt/e/The Data Mint/output/dataset/yolo"),
        help="Path to synthetic dataset in YOLO format"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/mnt/e/The Data Mint/output/validation"),
        help="Output directory for validation results"
    )
    parser.add_argument(
        "--model-size",
        type=str,
        default="n",
        choices=["n", "s", "m", "l", "x"],
        help="YOLOv8 model size (n=nano, s=small, m=medium, l=large, x=xlarge)"
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=100,
        help="Training epochs (default: 100, use 300 for final validation)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=16,
        help="Batch size (default: 16)"
    )
    parser.add_argument(
        "--ratios",
        type=float,
        nargs="+",
        default=[0.0, 0.10, 0.20, 0.30, 0.50, 1.0],
        help="Synthetic ratios to test (default: 0.0 0.10 0.20 0.30 0.50 1.0)"
    )
    parser.add_argument(
        "--skip-training",
        action="store_true",
        help="Skip training and only evaluate existing models"
    )

    args = parser.parse_args()

    run_validation(
        real_yolo_dir=args.real_yolo_dir,
        synth_yolo_dir=args.synth_yolo_dir,
        output_dir=args.output_dir,
        model_size=args.model_size,
        epochs=args.epochs,
        batch_size=args.batch_size,
        synthetic_ratios=args.ratios,
        skip_training=args.skip_training
    )


if __name__ == "__main__":
    main()
