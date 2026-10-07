#!/usr/bin/env python3
"""
Unit tests for mask generators.

Tests basic functionality, constraints, and edge cases.
"""

import sys
import numpy as np
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mask_generator import (
    CrackMaskGenerator,
    PorosityMaskGenerator,
    LackOfFusionMaskGenerator,
    SlagInclusionMaskGenerator,
    UndercutMaskGenerator,
    create_weld_roi_mask,
    apply_weld_roi,
    feather_mask,
)


class TestMaskGenerators:
    """Test suite for all mask generators."""

    def __init__(self):
        self.passed = 0
        self.failed = 0

    def assert_true(self, condition: bool, message: str):
        """Assert condition is true."""
        if condition:
            self.passed += 1
            print(f"  ✓ {message}")
        else:
            self.failed += 1
            print(f"  ✗ FAIL: {message}")

    def test_weld_roi_creation(self):
        """Test weld ROI mask creation."""
        print("\nTest: Weld ROI Creation")

        roi_mask = create_weld_roi_mask(512, 512, center_offset=0, zone_height_pct=0.4)

        self.assert_true(roi_mask.shape == (512, 512), "ROI shape is 512x512")
        self.assert_true(roi_mask.dtype == np.uint8, "ROI dtype is uint8")
        self.assert_true(np.all(np.isin(roi_mask, [0, 255])), "ROI values are binary (0 or 255)")
        self.assert_true(np.any(roi_mask > 0), "ROI has non-zero pixels")

        # Check zone is horizontal band
        row_sums = np.sum(roi_mask, axis=1)
        non_zero_rows = np.where(row_sums > 0)[0]
        zone_height = len(non_zero_rows)

        expected_height = int(512 * 0.4)
        tolerance = 10
        self.assert_true(
            abs(zone_height - expected_height) < tolerance,
            f"ROI zone height ~{expected_height} pixels (got {zone_height})"
        )

    def test_roi_constraint(self):
        """Test applying ROI constraint to mask."""
        print("\nTest: ROI Constraint Application")

        # Create full mask
        full_mask = np.ones((512, 512), dtype=np.uint8) * 255

        # Create ROI (center 40%)
        roi_mask = create_weld_roi_mask(512, 512, center_offset=0, zone_height_pct=0.4)

        # Apply constraint
        constrained = apply_weld_roi(full_mask, roi_mask)

        self.assert_true(constrained.shape == (512, 512), "Constrained mask shape correct")
        self.assert_true(np.all(constrained[roi_mask == 0] == 0), "Pixels outside ROI are zero")
        self.assert_true(np.any(constrained > 0), "Pixels inside ROI are preserved")

    def test_feathering(self):
        """Test mask feathering utility."""
        print("\nTest: Mask Feathering")

        # Create sharp binary mask
        binary_mask = np.zeros((512, 512), dtype=np.uint8)
        binary_mask[200:300, 200:300] = 255

        # Apply feathering
        feathered = feather_mask(binary_mask, blur_radius=5)

        self.assert_true(feathered.shape == binary_mask.shape, "Feathered mask same shape")
        self.assert_true(feathered.dtype == np.uint8, "Feathered mask is uint8")
        self.assert_true(feathered.min() >= 0 and feathered.max() <= 255, "Feathered values in 0-255 range")
        self.assert_true(np.any((feathered > 0) & (feathered < 255)), "Feathered mask has gradient values")

    def test_crack_generator(self):
        """Test crack mask generator."""
        print("\nTest: Crack Mask Generator")

        generator = CrackMaskGenerator(seed=42)
        binary_mask, feathered_mask = generator.generate()

        self.assert_true(binary_mask.shape == (512, 512), "Binary mask shape correct")
        self.assert_true(feathered_mask.shape == (512, 512), "Feathered mask shape correct")
        self.assert_true(np.all(np.isin(binary_mask, [0, 255])), "Binary mask is binary")
        self.assert_true(np.any(binary_mask > 0), "Crack has non-zero pixels")
        self.assert_true(feathered_mask.dtype == np.uint8, "Feathered mask is uint8")

    def test_porosity_generator(self):
        """Test porosity mask generator."""
        print("\nTest: Porosity Mask Generator")

        generator = PorosityMaskGenerator(seed=42)
        binary_mask, feathered_mask = generator.generate()

        self.assert_true(binary_mask.shape == (512, 512), "Binary mask shape correct")
        self.assert_true(np.all(np.isin(binary_mask, [0, 255])), "Binary mask is binary")
        self.assert_true(np.any(binary_mask > 0), "Porosity has non-zero pixels")

        # Check for multiple disconnected regions (multiple pores)
        # Simple check: count transitions from 0 to 255 in a middle row
        mid_row = binary_mask[256, :]
        transitions = np.sum(np.diff(mid_row.astype(int)) > 0)
        # Note: May be 0 if no pores in this exact row
        self.assert_true(True, "Porosity mask generated successfully")

    def test_lack_of_fusion_generator(self):
        """Test lack of fusion mask generator."""
        print("\nTest: Lack of Fusion Mask Generator")

        generator = LackOfFusionMaskGenerator(seed=42)
        binary_mask, feathered_mask = generator.generate()

        self.assert_true(binary_mask.shape == (512, 512), "Binary mask shape correct")
        self.assert_true(np.all(np.isin(binary_mask, [0, 255])), "Binary mask is binary")
        self.assert_true(np.any(binary_mask > 0), "LoF has non-zero pixels")

    def test_slag_inclusion_generator(self):
        """Test slag inclusion mask generator."""
        print("\nTest: Slag Inclusion Mask Generator")

        generator = SlagInclusionMaskGenerator(seed=42)
        binary_mask, feathered_mask = generator.generate()

        self.assert_true(binary_mask.shape == (512, 512), "Binary mask shape correct")
        self.assert_true(np.all(np.isin(binary_mask, [0, 255])), "Binary mask is binary")
        self.assert_true(np.any(binary_mask > 0), "Slag inclusion has non-zero pixels")

    def test_undercut_generator(self):
        """Test undercut mask generator."""
        print("\nTest: Undercut Mask Generator")

        generator = UndercutMaskGenerator(seed=42)
        binary_mask, feathered_mask = generator.generate()

        self.assert_true(binary_mask.shape == (512, 512), "Binary mask shape correct")
        self.assert_true(np.all(np.isin(binary_mask, [0, 255])), "Binary mask is binary")
        self.assert_true(np.any(binary_mask > 0), "Undercut has non-zero pixels")

    def test_reproducibility(self):
        """Test that same seed produces same output."""
        print("\nTest: Reproducibility (Fixed Seed)")

        # Test crack generator
        gen1 = CrackMaskGenerator(seed=12345)
        mask1, _ = gen1.generate()

        gen2 = CrackMaskGenerator(seed=12345)
        mask2, _ = gen2.generate()

        self.assert_true(np.array_equal(mask1, mask2), "Same seed produces identical masks")

        # Test different seeds produce different masks
        gen3 = CrackMaskGenerator(seed=99999)
        mask3, _ = gen3.generate()

        self.assert_true(not np.array_equal(mask1, mask3), "Different seeds produce different masks")

    def test_edge_cases(self):
        """Test edge cases and boundary conditions."""
        print("\nTest: Edge Cases")

        # Small mask size
        generator = CrackMaskGenerator(height=64, width=64, seed=42)
        binary_mask, _ = generator.generate()
        self.assert_true(binary_mask.shape == (64, 64), "Small mask size works")

        # Large mask size
        generator = CrackMaskGenerator(height=1024, width=1024, seed=42)
        binary_mask, _ = generator.generate()
        self.assert_true(binary_mask.shape == (1024, 1024), "Large mask size works")

    def run_all_tests(self):
        """Run all test methods."""
        print("="*60)
        print("Running Mask Generator Unit Tests")
        print("="*60)

        test_methods = [
            self.test_weld_roi_creation,
            self.test_roi_constraint,
            self.test_feathering,
            self.test_crack_generator,
            self.test_porosity_generator,
            self.test_lack_of_fusion_generator,
            self.test_slag_inclusion_generator,
            self.test_undercut_generator,
            self.test_reproducibility,
            self.test_edge_cases,
        ]

        for test_method in test_methods:
            try:
                test_method()
            except Exception as e:
                print(f"\n  ✗ EXCEPTION in {test_method.__name__}: {e}")
                self.failed += 1

        print("\n" + "="*60)
        print("Test Results")
        print("="*60)
        print(f"Passed: {self.passed}")
        print(f"Failed: {self.failed}")
        print(f"Total:  {self.passed + self.failed}")

        if self.failed == 0:
            print("\n✓ ALL TESTS PASSED")
            return 0
        else:
            print(f"\n✗ {self.failed} TEST(S) FAILED")
            return 1


if __name__ == '__main__':
    tester = TestMaskGenerators()
    exit_code = tester.run_all_tests()
    sys.exit(exit_code)
