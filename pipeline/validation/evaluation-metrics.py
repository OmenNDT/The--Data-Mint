#!/usr/bin/env python3
"""
Evaluation Metrics

Evaluates trained YOLO models on held-out test set.
Computes mAP, precision, recall, and per-class metrics.
"""

from pathlib import Path
from typing import Dict, List
import json


def evaluate_model(
    weights_path: Path,
    test_data_yaml: Path,
    experiment_name: str,
    device: int = 0
) -> Dict:
    """
    Evaluate YOLO model on test set.

    Args:
        weights_path: Path to trained model weights (best.pt)
        test_data_yaml: Path to test data YAML configuration
        experiment_name: Name of experiment
        device: GPU device ID

    Returns:
        Evaluation metrics dict
    """
    try:
        from ultralytics import YOLO
    except ImportError:
        raise ImportError(
            "ultralytics package not installed. "
            "Install with: pip install ultralytics"
        )

    print(f"Evaluating {experiment_name}...")

    # Load model
    model = YOLO(str(weights_path))

    # Run validation on test set
    metrics = model.val(
        data=str(test_data_yaml),
        split="test",
        device=device,
        plots=True,
        save_json=True
    )

    # Extract metrics
    results = {
        "experiment_name": experiment_name,
        "mAP50": float(metrics.box.map50),
        "mAP50_95": float(metrics.box.map),
        "precision": float(metrics.box.mp),
        "recall": float(metrics.box.mr),
        "per_class_map50": [float(x) for x in metrics.box.maps],
        "fitness": float(metrics.fitness)
    }

    print(f"  mAP@50: {results['mAP50']:.3f}")
    print(f"  mAP@50-95: {results['mAP50_95']:.3f}")
    print(f"  Precision: {results['precision']:.3f}")
    print(f"  Recall: {results['recall']:.3f}")

    return results


def compare_experiments(experiment_results: List[Dict]) -> Dict:
    """
    Compare multiple experiment results and identify best configuration.

    Args:
        experiment_results: List of evaluation results dicts

    Returns:
        Comparison analysis with best config
    """
    if not experiment_results:
        return {}

    # Sort by mAP@50
    sorted_results = sorted(
        experiment_results,
        key=lambda x: x.get("mAP50", 0),
        reverse=True
    )

    best = sorted_results[0]
    baseline = next((r for r in sorted_results if "real-only" in r["experiment_name"]), None)

    comparison = {
        "best_experiment": best["experiment_name"],
        "best_mAP50": best["mAP50"],
        "baseline_mAP50": baseline["mAP50"] if baseline else None,
        "improvement": best["mAP50"] - baseline["mAP50"] if baseline else None,
        "improvement_pct": ((best["mAP50"] - baseline["mAP50"]) / baseline["mAP50"] * 100) if baseline and baseline["mAP50"] > 0 else None,
        "all_results": sorted_results
    }

    return comparison


def generate_comparison_table(experiment_results: List[Dict]) -> str:
    """
    Generate markdown table comparing experiment results.

    Args:
        experiment_results: List of evaluation results

    Returns:
        Markdown table string
    """
    table = """
| Experiment | mAP@50 | mAP@50-95 | Precision | Recall | Fitness |
|------------|--------|-----------|-----------|--------|---------|
"""

    for result in experiment_results:
        name = result.get("experiment_name", "Unknown")
        map50 = result.get("mAP50", 0)
        map50_95 = result.get("mAP50_95", 0)
        precision = result.get("precision", 0)
        recall = result.get("recall", 0)
        fitness = result.get("fitness", 0)

        table += f"| {name} | {map50:.3f} | {map50_95:.3f} | {precision:.3f} | {recall:.3f} | {fitness:.3f} |\n"

    return table


def generate_per_class_table(experiment_results: List[Dict]) -> str:
    """
    Generate per-class mAP comparison table.

    Args:
        experiment_results: List of evaluation results

    Returns:
        Markdown table string
    """
    class_names = ["crack", "porosity", "inclusion", "lack_of_fusion", "undercut"]

    table = """
| Experiment | Crack | Porosity | Inclusion | LoF | Undercut | Mean |
|------------|-------|----------|-----------|-----|----------|------|
"""

    for result in experiment_results:
        name = result.get("experiment_name", "Unknown")
        per_class = result.get("per_class_map50", [0] * 5)

        # Pad to 5 classes if needed
        while len(per_class) < 5:
            per_class.append(0)

        mean_map = sum(per_class) / len(per_class) if per_class else 0

        table += f"| {name} | {per_class[0]:.3f} | {per_class[1]:.3f} | {per_class[2]:.3f} | {per_class[3]:.3f} | {per_class[4]:.3f} | {mean_map:.3f} |\n"

    return table


def analyze_per_class_improvement(
    baseline_result: Dict,
    experiment_results: List[Dict]
) -> Dict:
    """
    Analyze which defect types benefit most from synthetic data.

    Args:
        baseline_result: Real-only baseline results
        experiment_results: Results with synthetic data

    Returns:
        Per-class improvement analysis
    """
    class_names = ["crack", "porosity", "inclusion", "lack_of_fusion", "undercut"]

    baseline_per_class = baseline_result.get("per_class_map50", [0] * 5)

    improvements = {name: [] for name in class_names}

    for result in experiment_results:
        if "real-only" in result["experiment_name"]:
            continue

        per_class = result.get("per_class_map50", [0] * 5)

        for i, class_name in enumerate(class_names):
            improvement = per_class[i] - baseline_per_class[i]
            improvements[class_name].append({
                "experiment": result["experiment_name"],
                "improvement": improvement
            })

    # Find best improvement for each class
    best_improvements = {}
    for class_name, data in improvements.items():
        if data:
            best = max(data, key=lambda x: x["improvement"])
            best_improvements[class_name] = best

    return best_improvements
