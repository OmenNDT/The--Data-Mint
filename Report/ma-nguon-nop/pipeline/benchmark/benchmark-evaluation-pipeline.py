"""
Benchmark Evaluation Pipeline.

Computes FID, SSIM, sharpness for all 6 models, produces composite ranking.

Usage:
    python3 pipeline/benchmark/benchmark-evaluation-pipeline.py
    python3 pipeline/benchmark/benchmark-evaluation-pipeline.py --models baseline medxray
"""

import json
import logging
import argparse
import sys
from pathlib import Path

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path("/home/sontn/Projects/The Data Mint")
sys.path.insert(0, str(PROJECT_ROOT / "pipeline"))

from benchmark import compute_fid, compute_ssim_distribution, compute_sharpness

BENCHMARK_DIR = PROJECT_ROOT / "output" / "benchmark"
REAL_DATA_DIR = PROJECT_ROOT / "kohya-ss" / "training_data"

ALL_MODELS = ["baseline", "medxray", "realvis", "absreal", "cyberreal", "medxray-direct"]
DEFECTS = ["crack"]
# TODO: restore full list when training data is ready
# DEFECTS = ["crack", "porosity", "inclusion", "lack_of_fusion", "undercut"]

# Mapping defect -> real data subdirectory
REAL_DEFECT_DIRS = {
    "crack": "crack/10_xray_crack",
    "porosity": "porosity/5_xray_porosity",
    "inclusion": "inclusion/20_xray_inclusion",
    "lack_of_fusion": "lack_of_fusion/8_xray_lof",
    "undercut": "undercut/25_xray_undercut",
}

W_FID = 0.4
W_SSIM = 0.4
W_SHARP = 0.2


def evaluate_models(models: list) -> dict:
    """Run full evaluation pipeline on given models."""
    results = {}
    active_defects = [d for d in DEFECTS if (REAL_DATA_DIR / REAL_DEFECT_DIRS[d]).exists()]
    if not active_defects:
        logger.error("No real data found for any defect type")
        return results

    logger.info(f"Active defects: {active_defects}")

    # Step 1: FID per model per defect (averaged)
    logger.info("=== Computing FID ===")
    for model in models:
        synth_dir = BENCHMARK_DIR / model
        if not synth_dir.exists():
            logger.warning(f"Skipping {model}: directory not found")
            continue
        results[model] = {"fid_per_defect": {}, "ssim": {}, "sharpness": {}}
        fid_scores = []
        for defect in active_defects:
            real_dir = REAL_DATA_DIR / REAL_DEFECT_DIRS[defect]
            synth_defect_dir = synth_dir / defect
            if not synth_defect_dir.exists():
                continue
            try:
                fid_score = compute_fid(real_dir, synth_defect_dir)
                results[model]["fid_per_defect"][defect] = round(fid_score, 2)
                fid_scores.append(fid_score)
                logger.info(f"  {model}/{defect}: FID = {fid_score:.2f}")
            except Exception as e:
                logger.error(f"  {model}/{defect}: FID failed: {e}")
        results[model]["fid"] = round(float(np.mean(fid_scores)), 2) if fid_scores else 999.0

    # Step 2: SSIM per model per defect
    logger.info("\n=== Computing SSIM ===")
    for model in models:
        if model not in results:
            continue
        for defect in active_defects:
            synth_dir = BENCHMARK_DIR / model / defect
            real_dir = REAL_DATA_DIR / REAL_DEFECT_DIRS[defect]
            if not synth_dir.exists() or not real_dir.exists():
                results[model]["ssim"][defect] = {"mean": 0.0, "std": 0.0}
                continue
            ssim_result = compute_ssim_distribution(real_dir, synth_dir)
            results[model]["ssim"][defect] = ssim_result
            logger.info(f"  {model}/{defect}: SSIM = {ssim_result['mean']:.4f}")

    # Step 3: Sharpness per model per defect
    logger.info("\n=== Computing Sharpness ===")
    for model in models:
        if model not in results:
            continue
        for defect in active_defects:
            synth_dir = BENCHMARK_DIR / model / defect
            if not synth_dir.exists():
                results[model]["sharpness"][defect] = {"mean": 0.0, "std": 0.0}
                continue
            sharp_result = compute_sharpness(synth_dir)
            results[model]["sharpness"][defect] = sharp_result
            logger.info(f"  {model}/{defect}: Sharpness = {sharp_result['mean']:.1f}")

    # Step 4: Normalize and composite
    logger.info("\n=== Computing Composite Scores ===")
    active_models = [m for m in models if m in results]

    # FID normalization (inverted: lower FID = higher score)
    max_fid = max(results[m]["fid"] for m in active_models) or 1.0
    for m in active_models:
        results[m]["fid_norm"] = round(1.0 - (results[m]["fid"] / max_fid), 4)

    # SSIM mean across active defects
    for m in active_models:
        ssim_vals = [results[m]["ssim"][d]["mean"] for d in active_defects if d in results[m]["ssim"]]
        results[m]["ssim_mean"] = round(float(np.mean(ssim_vals)), 4) if ssim_vals else 0.0

    # Sharpness normalization
    max_sharp = max(
        np.mean([results[m]["sharpness"][d]["mean"] for d in active_defects if d in results[m]["sharpness"]])
        for m in active_models
    ) or 1.0
    for m in active_models:
        sharp_vals = [results[m]["sharpness"][d]["mean"] for d in active_defects if d in results[m]["sharpness"]]
        results[m]["sharpness_norm"] = round(float(np.mean(sharp_vals)) / max_sharp, 4) if sharp_vals else 0.0

    # Composite score
    for m in active_models:
        results[m]["composite"] = round(
            W_FID * results[m]["fid_norm"]
            + W_SSIM * results[m]["ssim_mean"]
            + W_SHARP * results[m]["sharpness_norm"],
            4,
        )

    # Step 5: Rank and print
    ranked = sorted(active_models, key=lambda m: results[m]["composite"], reverse=True)
    for i, m in enumerate(ranked):
        results[m]["rank"] = i + 1

    logger.info("\n=== RANKING ===")
    logger.info(f"{'Rank':<6} {'Model':<16} {'Composite':<12} {'FID':<10} {'SSIM':<10} {'Sharp':<10}")
    logger.info("-" * 64)
    for m in ranked:
        r = results[m]
        logger.info(
            f"{r['rank']:<6} {m:<16} {r['composite']:<12.4f} "
            f"{r['fid']:<10.1f} {r['ssim_mean']:<10.4f} {r['sharpness_norm']:<10.4f}"
        )

    # Step 6: Save results
    output_path = BENCHMARK_DIR / "evaluation-results.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    logger.info(f"\nResults saved: {output_path}")

    # Select top 2 for Phase 7
    top2 = ranked[:2]
    if "baseline" in top2 and len(ranked) > 2:
        top2 = ranked[:3]
    logger.info(f"\nTop models for Phase 7 (YOLOv8): {top2}")

    return results


def main():
    parser = argparse.ArgumentParser(description="Benchmark evaluation pipeline")
    parser.add_argument("--models", nargs="+", default=ALL_MODELS, help="Models to evaluate")
    args = parser.parse_args()

    evaluate_models(args.models)


if __name__ == "__main__":
    main()
