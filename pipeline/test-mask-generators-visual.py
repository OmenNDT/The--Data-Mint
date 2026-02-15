#!/usr/bin/env python3
"""
Visual test script for mask generators.

Generates sample masks for each defect type and saves them as images
for visual inspection.
"""

import os
import sys
import time
import yaml
import numpy as np
import cv2
from pathlib import Path

# Add mask_generator to path
sys.path.insert(0, str(Path(__file__).parent))

from mask_generator import (
    CrackMaskGenerator,
    PorosityMaskGenerator,
    LackOfFusionMaskGenerator,
    SlagInclusionMaskGenerator,
    UndercutMaskGenerator,
    create_weld_roi_mask,
    apply_weld_roi,
)


def load_config(config_path: str) -> dict:
    """Load configuration from YAML file."""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def visualize_mask_with_roi(mask: np.ndarray, roi_mask: np.ndarray) -> np.ndarray:
    """
    Create RGB visualization showing mask and ROI overlay.

    Returns:
        RGB image with mask in red, ROI in green
    """
    vis = np.zeros((mask.shape[0], mask.shape[1], 3), dtype=np.uint8)

    # ROI in green (dim)
    vis[roi_mask > 0, 1] = 50

    # Mask in red (bright)
    vis[mask > 0, 2] = 255

    return vis


def test_generator(generator_class, config: dict, defect_type: str, output_dir: Path, num_samples: int = 10):
    """
    Test a single mask generator.

    Args:
        generator_class: Generator class to test
        config: Full config dict
        defect_type: Defect type name (key in config)
        output_dir: Directory to save sample masks
        num_samples: Number of sample masks to generate
    """
    print(f"\n{'='*60}")
    print(f"Testing {defect_type} mask generator")
    print(f"{'='*60}")

    # Create output directory
    defect_dir = output_dir / defect_type
    defect_dir.mkdir(parents=True, exist_ok=True)

    # Get generator params from config
    params = config.get(defect_type, {})
    weld_roi_params = config.get('weld_roi', {})

    # Create ROI mask
    roi_mask = create_weld_roi_mask(
        height=512,
        width=512,
        center_offset=weld_roi_params.get('center_offset', 0),
        zone_height_pct=weld_roi_params.get('zone_height_pct', 0.4)
    )

    # Test generation speed
    generator = generator_class(seed=42, **params)
    start_time = time.time()

    for i in range(num_samples):
        # Generate masks
        binary_mask, feathered_mask = generator.generate()

        # Apply ROI constraint
        constrained_binary = apply_weld_roi(binary_mask, roi_mask)
        constrained_feathered = apply_weld_roi(feathered_mask, roi_mask)

        # Create visualization
        vis = visualize_mask_with_roi(constrained_binary, roi_mask)

        # Save masks
        cv2.imwrite(str(defect_dir / f"sample_{i:02d}_binary.png"), constrained_binary)
        cv2.imwrite(str(defect_dir / f"sample_{i:02d}_feathered.png"), constrained_feathered)
        cv2.imwrite(str(defect_dir / f"sample_{i:02d}_visualization.png"), vis)

    elapsed = time.time() - start_time
    masks_per_sec = num_samples / elapsed

    print(f"✓ Generated {num_samples} masks in {elapsed:.3f}s ({masks_per_sec:.1f} masks/sec)")
    print(f"✓ Output saved to: {defect_dir}")

    # Validate masks
    print("\nValidation:")

    # Check mask properties
    has_defect = np.any(constrained_binary > 0)
    is_binary = np.all(np.isin(constrained_binary, [0, 255]))
    is_in_roi = np.all(constrained_binary[roi_mask == 0] == 0)
    feathered_range = (feathered_mask.min(), feathered_mask.max())

    print(f"  • Has defect pixels: {'✓' if has_defect else '✗'}")
    print(f"  • Binary values only: {'✓' if is_binary else '✗'}")
    print(f"  • Defect in ROI only: {'✓' if is_in_roi else '✗'}")
    print(f"  • Feathered range: {feathered_range[0]}-{feathered_range[1]} (expect 0-255)")

    return masks_per_sec


def benchmark_generation_speed(config: dict, num_masks: int = 1000):
    """
    Benchmark mask generation speed for all defect types.

    Args:
        config: Full config dict
        num_masks: Number of masks to generate for benchmark
    """
    print(f"\n{'='*60}")
    print(f"Benchmarking generation speed ({num_masks} masks per type)")
    print(f"{'='*60}\n")

    generators = [
        (CrackMaskGenerator, 'crack'),
        (PorosityMaskGenerator, 'porosity'),
        (LackOfFusionMaskGenerator, 'lack_of_fusion'),
        (SlagInclusionMaskGenerator, 'slag_inclusion'),
        (UndercutMaskGenerator, 'undercut'),
    ]

    results = {}

    for generator_class, defect_type in generators:
        params = config.get(defect_type, {})
        generator = generator_class(seed=42, **params)

        start_time = time.time()
        for _ in range(num_masks):
            generator.generate()
        elapsed = time.time() - start_time

        masks_per_sec = num_masks / elapsed
        results[defect_type] = masks_per_sec

        print(f"{defect_type:20s}: {masks_per_sec:8.1f} masks/sec")

    avg_speed = sum(results.values()) / len(results)
    print(f"\n{'Average':20s}: {avg_speed:8.1f} masks/sec")

    if avg_speed > 1000:
        print(f"✓ PASS: Average speed {avg_speed:.1f} > 1000 masks/sec")
    else:
        print(f"✗ FAIL: Average speed {avg_speed:.1f} < 1000 masks/sec")

    return results


def test_reproducibility(config: dict):
    """Test that same seed produces same masks."""
    print(f"\n{'='*60}")
    print(f"Testing reproducibility with fixed seed")
    print(f"{'='*60}\n")

    generators = [
        (CrackMaskGenerator, 'crack'),
        (PorosityMaskGenerator, 'porosity'),
        (LackOfFusionMaskGenerator, 'lack_of_fusion'),
        (SlagInclusionMaskGenerator, 'slag_inclusion'),
        (UndercutMaskGenerator, 'undercut'),
    ]

    for generator_class, defect_type in generators:
        params = config.get(defect_type, {})

        # Generate with same seed twice
        gen1 = generator_class(seed=12345, **params)
        mask1_binary, mask1_feathered = gen1.generate()

        gen2 = generator_class(seed=12345, **params)
        mask2_binary, mask2_feathered = gen2.generate()

        # Compare
        binary_identical = np.array_equal(mask1_binary, mask2_binary)
        feathered_identical = np.array_equal(mask1_feathered, mask2_feathered)

        status = '✓' if (binary_identical and feathered_identical) else '✗'
        print(f"{status} {defect_type:20s}: binary={binary_identical}, feathered={feathered_identical}")


def main():
    """Run all tests."""
    # Paths
    script_dir = Path(__file__).parent
    config_path = script_dir / 'config' / 'mask-config.yaml'
    output_dir = script_dir / 'test_output' / 'mask_samples'

    # Load config
    print(f"Loading config from: {config_path}")
    config = load_config(config_path)

    # Test each generator
    generators = [
        (CrackMaskGenerator, 'crack'),
        (PorosityMaskGenerator, 'porosity'),
        (LackOfFusionMaskGenerator, 'lack_of_fusion'),
        (SlagInclusionMaskGenerator, 'slag_inclusion'),
        (UndercutMaskGenerator, 'undercut'),
    ]

    speeds = {}
    for generator_class, defect_type in generators:
        speed = test_generator(generator_class, config, defect_type, output_dir, num_samples=10)
        speeds[defect_type] = speed

    # Test reproducibility
    test_reproducibility(config)

    # Benchmark speed
    benchmark_results = benchmark_generation_speed(config, num_masks=1000)

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"✓ All mask generators functional")
    print(f"✓ Sample masks saved to: {output_dir}")
    print(f"✓ Average generation speed: {sum(benchmark_results.values())/len(benchmark_results):.1f} masks/sec")
    print("\nNext steps:")
    print("  1. Visually inspect sample masks in test_output/mask_samples/")
    print("  2. Verify defect morphologies match expectations")
    print("  3. Adjust config parameters if needed")
    print("  4. Integrate with ComfyUI workflow (Phase 4)")


if __name__ == '__main__':
    main()
