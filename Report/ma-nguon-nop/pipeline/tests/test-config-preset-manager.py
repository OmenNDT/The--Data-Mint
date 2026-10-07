#!/usr/bin/env python3
"""Unit tests for ConfigPresetManager."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from launcher.config_preset_manager import ConfigPresetManager


class TestConfigPresetManager:
    """Test suite for ConfigPresetManager."""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.pm = ConfigPresetManager()

    def assert_true(self, condition: bool, message: str):
        if condition:
            self.passed += 1
            print(f"  ✓ {message}")
        else:
            self.failed += 1
            print(f"  ✗ FAIL: {message}")

    def test_list_presets_returns_three(self):
        """3 built-in presets: pilot, standard, full."""
        print("\nTest: list_presets returns 3 presets")
        presets = self.pm.list_presets()
        self.assert_true(len(presets) == 3, f"Expected 3 presets, got {len(presets)}")
        names = {p.file_path.stem for p in presets}
        self.assert_true(names == {"pilot", "standard", "full"}, f"Names: {names}")

    def test_load_pilot_preset(self):
        """Pilot preset has 500 total_images."""
        print("\nTest: load_preset('pilot') has 500 images")
        config = self.pm.load_preset("pilot")
        total = config.get("generation", {}).get("total_images", 0)
        self.assert_true(total == 500, f"total_images={total}, expected 500")

    def test_apply_overrides(self):
        """Override total_images in config."""
        print("\nTest: apply_overrides changes total_images")
        config = self.pm.load_preset("pilot")
        overrides = {"total_images": 1000}
        result = self.pm.apply_overrides(config, overrides)
        total = result.get("generation", {}).get("total_images", 0)
        self.assert_true(total == 1000, f"total_images={total}, expected 1000")

    def test_validate_config_catches_missing_generation(self):
        """Missing generation section triggers error."""
        print("\nTest: validate_config catches missing generation")
        errors = self.pm.validate_config({"validation": {"epochs": 20, "batch_size": 16, "ratios": [1.0]}})
        has_error = any("generation" in e for e in errors)
        self.assert_true(has_error, f"Errors: {errors}")

    def test_validate_config_passes_valid(self):
        """Valid config returns no errors."""
        print("\nTest: validate_config passes valid config")
        config = self.pm.load_preset("pilot")
        errors = self.pm.validate_config(config)
        self.assert_true(len(errors) == 0, f"Errors: {errors}")

    def test_estimate_runtime(self):
        """Pilot estimate ~30 minutes."""
        print("\nTest: estimate_runtime reasonable for pilot")
        config = self.pm.load_preset("pilot")
        estimate = self.pm.estimate_runtime(config)
        self.assert_true(estimate.total_minutes > 0, f"Total: {estimate.total_minutes:.1f} min")
        self.assert_true(estimate.total_minutes < 120, f"Under 2h: {estimate.total_minutes:.1f} min")

    def run_all(self):
        print("=" * 50)
        print("ConfigPresetManager Unit Tests")
        print("=" * 50)

        self.test_list_presets_returns_three()
        self.test_load_pilot_preset()
        self.test_apply_overrides()
        self.test_validate_config_catches_missing_generation()
        self.test_validate_config_passes_valid()
        self.test_estimate_runtime()

        print(f"\n{'=' * 50}")
        print(f"Results: {self.passed} passed, {self.failed} failed")
        print(f"{'=' * 50}")
        return self.failed == 0


if __name__ == "__main__":
    tests = TestConfigPresetManager()
    success = tests.run_all()
    sys.exit(0 if success else 1)
