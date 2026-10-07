#!/usr/bin/env python3
"""Unit tests for ProgressTracker."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from launcher.progress_tracker import ProgressTracker, PATTERNS, PHASE_WEIGHTS


class TestProgressTracker:
    """Test suite for ProgressTracker."""

    def __init__(self):
        self.passed = 0
        self.failed = 0

    def assert_true(self, condition: bool, message: str):
        if condition:
            self.passed += 1
            print(f"  ✓ {message}")
        else:
            self.failed += 1
            print(f"  ✗ FAIL: {message}")

    def test_parse_checkpoint_line(self):
        """Extract image count from checkpoint line."""
        print("\nTest: parse checkpoint line")
        tracker = ProgressTracker(config={"total_images": 1000})
        tracker.set_current_phase(6)
        update = tracker.parse_line("[CHECKPOINT] Generated 500 images, elapsed: 30.0s")
        self.assert_true(update is not None, "Returns ProgressUpdate")
        self.assert_true(update.images_generated == 500, f"images={update.images_generated}")

    def test_parse_epoch_line(self):
        """Extract epoch from training line."""
        print("\nTest: parse epoch line")
        tracker = ProgressTracker(config={"epochs": 100})
        tracker.set_current_phase(9)
        update = tracker.parse_line("Epoch 50/100")
        self.assert_true(update is not None, "Returns ProgressUpdate")
        self.assert_true(update.epoch_current == 50, f"epoch={update.epoch_current}")
        self.assert_true(update.epoch_total == 100, f"total={update.epoch_total}")

    def test_parse_thermal_line(self):
        """Extract GPU temperature."""
        print("\nTest: parse thermal line")
        tracker = ProgressTracker()
        tracker.set_current_phase(6)
        update = tracker.parse_line("GPU temp: 78.5")
        self.assert_true(update is not None, "Returns ProgressUpdate")
        self.assert_true(update.gpu_temp == 78.5, f"temp={update.gpu_temp}")

    def test_parse_ssim_line(self):
        """Extract SSIM progress."""
        print("\nTest: parse SSIM line")
        tracker = ProgressTracker()
        tracker.set_current_phase(8)
        update = tracker.parse_line("SSIM check: 75/100 images")
        self.assert_true(update is not None, "Returns ProgressUpdate")
        self.assert_true(abs(update.phase_progress - 0.75) < 0.01, f"progress={update.phase_progress}")

    def test_overall_progress_weighted(self):
        """Phase weights sum to 1.0."""
        print("\nTest: phase weights sum to 1.0")
        total = sum(PHASE_WEIGHTS.values())
        self.assert_true(abs(total - 1.0) < 0.01, f"Sum={total}")

    def test_unknown_line_returns_none(self):
        """Non-progress line returns None."""
        print("\nTest: unknown line returns None")
        tracker = ProgressTracker()
        result = tracker.parse_line("Some random log line")
        self.assert_true(result is None, f"Result={result}")

    def test_eta_decreases_with_progress(self):
        """ETA should decrease as progress increases."""
        print("\nTest: ETA decreases with progress")
        import time
        tracker = ProgressTracker(config={"total_images": 1000})
        tracker.set_current_phase(6)

        # Simulate early progress
        tracker.parse_line("[CHECKPOINT] Generated 100 images")
        time.sleep(0.1)
        eta1 = tracker._calculate_eta(0.1)

        # Simulate more progress
        tracker.parse_line("[CHECKPOINT] Generated 500 images")
        eta2 = tracker._calculate_eta(0.5)

        # Both should be valid
        self.assert_true(eta1 is not None, f"ETA1={eta1}")
        self.assert_true(eta2 is not None, f"ETA2={eta2}")
        # ETA2 should be less (or close) since more progress made
        self.assert_true(eta2 <= eta1 + 1, f"ETA2({eta2}) <= ETA1({eta1})")

    def run_all(self):
        print("=" * 50)
        print("ProgressTracker Unit Tests")
        print("=" * 50)

        self.test_parse_checkpoint_line()
        self.test_parse_epoch_line()
        self.test_parse_thermal_line()
        self.test_parse_ssim_line()
        self.test_overall_progress_weighted()
        self.test_unknown_line_returns_none()
        self.test_eta_decreases_with_progress()

        print(f"\n{'=' * 50}")
        print(f"Results: {self.passed} passed, {self.failed} failed")
        print(f"{'=' * 50}")
        return self.failed == 0


if __name__ == "__main__":
    tests = TestProgressTracker()
    success = tests.run_all()
    sys.exit(0 if success else 1)
