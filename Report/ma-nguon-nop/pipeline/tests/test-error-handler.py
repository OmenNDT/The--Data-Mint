#!/usr/bin/env python3
"""Unit tests for ErrorHandler."""

import sys
import tempfile
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from launcher.error_handler import ErrorHandler, format_error_message


class TestErrorHandler:
    """Test suite for ErrorHandler."""

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

    def test_check_dataset_path_valid(self):
        """Existing directory passes validation."""
        print("\nTest: valid dataset path")
        handler = ErrorHandler()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = handler.check_dataset_path(tmpdir)
            self.assert_true(result is True, f"Valid path returns True")
            self.assert_true(len(handler.errors) == 0, "No errors")

    def test_check_dataset_path_empty(self):
        """Empty string fails validation."""
        print("\nTest: empty dataset path")
        handler = ErrorHandler()
        result = handler.check_dataset_path("")
        self.assert_true(result is False, "Empty path returns False")
        self.assert_true(len(handler.errors) == 1, f"1 error: {handler.errors}")

    def test_check_gpu_success(self):
        """GPU check passes (machine has GPU)."""
        print("\nTest: GPU check success")
        handler = ErrorHandler()
        result = handler.check_gpu_available()
        self.assert_true(result is True, "GPU available")

    def test_preflight_collects_errors(self):
        """Preflight collects multiple errors from different checks."""
        print("\nTest: preflight collects errors")
        handler = ErrorHandler()
        config = {
            "phases_to_run": [6, 7, 8],
            "dataset_path": "/nonexistent/path/dataset",
        }
        passed, errors, warnings = handler.run_preflight_checks(config)
        # Dataset path doesn't exist → error
        has_dataset_error = any("Dataset" in e or "not found" in e for e in errors)
        self.assert_true(has_dataset_error, f"Dataset error found in: {errors}")

    def test_format_error_message(self):
        """Error messages get emoji prefix."""
        print("\nTest: format_error_message")
        gpu_msg = format_error_message("GPU: not found")
        self.assert_true("🖥️" in gpu_msg, f"GPU emoji: {gpu_msg}")
        dataset_msg = format_error_message("Dataset: empty")
        self.assert_true("📁" in dataset_msg, f"Dataset emoji: {dataset_msg}")

    def run_all(self):
        print("=" * 50)
        print("ErrorHandler Unit Tests")
        print("=" * 50)

        self.test_check_dataset_path_valid()
        self.test_check_dataset_path_empty()
        self.test_check_gpu_success()
        self.test_preflight_collects_errors()
        self.test_format_error_message()

        print(f"\n{'=' * 50}")
        print(f"Results: {self.passed} passed, {self.failed} failed")
        print(f"{'=' * 50}")
        return self.failed == 0


if __name__ == "__main__":
    tests = TestErrorHandler()
    success = tests.run_all()
    sys.exit(0 if success else 1)
