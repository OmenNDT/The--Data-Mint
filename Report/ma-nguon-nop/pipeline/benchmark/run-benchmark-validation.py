"""
Benchmark YOLOv8 Validation Runner.

Trains YOLOv8 on synthetic data from top 2 models + baseline,
evaluates on real test set, compares mAP.

Usage:
    python3 pipeline/benchmark/run-benchmark-validation.py \
        --models baseline medxray realvis \
        --real-test-dir output/dataset-test/yolo \
        --output-dir output/benchmark/validation
"""

import json
import logging
import argparse
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path("/home/sontn/Projects/The Data Mint")
sys.path.insert(0, str(PROJECT_ROOT / "pipeline"))

BENCHMARK_DIR = PROJECT_ROOT / "output" / "benchmark"
DEFAULT_REAL_TEST = PROJECT_ROOT / "output" / "dataset-test" / "yolo"
DEFAULT_OUTPUT = BENCHMARK_DIR / "validation"


def train_and_evaluate(
    model_name: str,
    dataset_dir: Path,
    output_dir: Path,
    epochs: int = 100,
    batch_size: int = 16,
    patience: int = 50,
) -> dict:
    """Train YOLOv8n on synthetic data and evaluate."""
    from ultralytics import YOLO

    data_yaml = dataset_dir / "data.yaml"
    if not data_yaml.exists():
        logger.error(f"data.yaml not found: {data_yaml}")
        return {}

    run_dir = output_dir / "runs" / model_name
    run_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Training YOLOv8n for {model_name}...")
    model = YOLO("yolov8n.pt")

    results = model.train(
        data=str(data_yaml),
        epochs=epochs,
        batch=batch_size,
        patience=patience,
        imgsz=512,
        project=str(run_dir),
        name="train",
        exist_ok=True,
        seed=42,
        verbose=False,
    )

    # Get best model path
    best_path = run_dir / "train" / "weights" / "best.pt"
    if not best_path.exists():
        logger.error(f"Best model not found: {best_path}")
        return {}

    # Evaluate on validation set
    logger.info(f"Evaluating {model_name}...")
    eval_model = YOLO(str(best_path))
    metrics = eval_model.val(data=str(data_yaml), verbose=False)

    result = {
        "model": model_name,
        "best_model_path": str(best_path),
        "map50": float(metrics.box.map50),
        "map50_95": float(metrics.box.map),
        "per_class_ap50": {},
    }

    # Per-class AP if available
    if hasattr(metrics.box, "ap50") and metrics.box.ap50 is not None:
        class_names = ["crack", "porosity", "inclusion", "lack_of_fusion", "undercut"]
        for i, ap in enumerate(metrics.box.ap50):
            if i < len(class_names):
                result["per_class_ap50"][class_names[i]] = round(float(ap), 4)

    logger.info(f"  {model_name}: mAP@50={result['map50']:.4f}, mAP@50-95={result['map50_95']:.4f}")
    return result


def generate_final_report(all_results: dict, output_dir: Path):
    """Generate final benchmark comparison report."""
    report_path = output_dir / "final-benchmark-report.md"

    ranked = sorted(all_results.values(), key=lambda r: r.get("map50", 0), reverse=True)
    winner = ranked[0]["model"] if ranked else "N/A"

    lines = [
        "# Base Model Benchmark — Final Results\n",
        "## YOLOv8 Detection Performance (mAP on Real Test Set)\n",
        "| Model | mAP@50 | mAP@50-95 |",
        "|-------|--------|-----------|",
    ]
    for r in ranked:
        lines.append(f"| {r['model']} | {r.get('map50', 0):.4f} | {r.get('map50_95', 0):.4f} |")

    # Per-class breakdown
    lines.extend(["\n## Per-Class AP@50\n"])
    classes = ["crack", "porosity", "inclusion", "lack_of_fusion", "undercut"]
    header = "| Model | " + " | ".join(classes) + " |"
    sep = "|-------|" + "|".join(["--------"] * len(classes)) + "|"
    lines.extend([header, sep])
    for r in ranked:
        vals = " | ".join(f"{r.get('per_class_ap50', {}).get(c, 0):.4f}" for c in classes)
        lines.append(f"| {r['model']} | {vals} |")

    lines.extend([
        f"\n## Recommendation\n",
        f"**Winner: {winner}**",
        f"- mAP@50: {ranked[0].get('map50', 0):.4f}" if ranked else "",
        f"\n## Action Items",
        f"- [ ] Update production checkpoint to {winner}",
        f"- [ ] Retrain all 5 production LoRAs on {winner} base",
        f"- [ ] Update pipeline configs",
        f"- [ ] Run full production validation",
    ])

    report_path.write_text("\n".join(lines))
    logger.info(f"Final report: {report_path}")


def main():
    parser = argparse.ArgumentParser(description="Benchmark YOLOv8 validation")
    parser.add_argument("--models", nargs="+", required=True, help="Models to validate")
    parser.add_argument("--real-test-dir", type=Path, default=DEFAULT_REAL_TEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=16)
    args = parser.parse_args()

    all_results = {}

    for model_name in args.models:
        dataset_dir = args.output_dir / "datasets" / model_name
        if not dataset_dir.exists():
            logger.error(f"Dataset not found for {model_name}: {dataset_dir}")
            logger.info("Run convert-synthetic-to-yolo-format.py first")
            continue

        result = train_and_evaluate(
            model_name, dataset_dir, args.output_dir,
            epochs=args.epochs, batch_size=args.batch_size,
        )
        if result:
            all_results[model_name] = result

    # Save raw results
    results_path = args.output_dir / "validation-results.json"
    with open(results_path, "w") as f:
        json.dump(all_results, f, indent=2)
    logger.info(f"Results saved: {results_path}")

    # Generate report
    generate_final_report(all_results, args.output_dir)


if __name__ == "__main__":
    main()
