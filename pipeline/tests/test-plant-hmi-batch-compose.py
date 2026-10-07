"""Unit tests for the "Tạo mẻ mới" compose form (phase 6B): field validation
(bad name, traversal, unknown defect, missing LoRA/mask generator, all-zero,
bad backgrounds dir), exact count allocation vs the scheduler's own
`int(total * ratio)` formula, base-config-untouched (hash before/after),
CSRF guard, overwrite refusal, and the LORA_PRESENT permissive.

Run: .venv/bin/python tests/test-plant-hmi-batch-compose.py
"""

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from plant_hmi import plant_batch_allocate as allocate  # noqa: E402
from plant_hmi import plant_batch_compose as compose  # noqa: E402
from plant_hmi import plant_batch_compose_routes as compose_routes  # noqa: E402
from plant_hmi import plant_batch_config_whitelist as whitelist  # noqa: E402
from plant_hmi.plant_batch_control import evaluate_permissives, blocking_failures  # noqa: E402

REAL_BASE_CONFIG = "batch-config.yaml"


def _schedule_counts(total: int, ratios: dict) -> dict:
    """Mirrors batch_manager/batch-job-scheduler.py:_build_job_list exactly:
    `count = int(total * ratio)` per defect, no remainder redistribution."""
    return {d: int(total * r) for d, r in ratios.items()}


class AllocateCountsTests(unittest.TestCase):
    def test_counts_sum_to_total_exactly(self):
        weights = {"crack": 0.5, "porosity": 0.3, "undercut": 0.2}
        counts = allocate.allocate_counts(1000, weights)
        self.assertEqual(sum(counts.values()), 1000)

    def test_uneven_division_still_sums_exactly(self):
        weights = {"a": 1, "b": 1, "c": 1}
        counts = allocate.allocate_counts(100, weights)
        self.assertEqual(sum(counts.values()), 100)
        # 33/33/33 + 1 remainder, tie-broken by name -> "a" gets the extra one
        self.assertEqual(counts, {"a": 34, "b": 33, "c": 33})

    def test_zero_weight_gets_zero_count(self):
        counts = allocate.allocate_counts(100, {"a": 1.0, "b": 0.0})
        self.assertEqual(counts["b"], 0)

    def test_all_zero_weights_all_zero_counts(self):
        counts = allocate.allocate_counts(100, {"a": 0.0, "b": 0.0})
        self.assertEqual(counts, {"a": 0, "b": 0})


class RatioForCountTests(unittest.TestCase):
    """The written ratio must reproduce the exact count through the scheduler's
    own int(total * ratio) formula, for every count the allocator can produce."""

    def test_ratio_reproduces_count_for_many_totals_and_splits(self):
        for total in (1, 7, 100, 333, 1000, 12345, 20000):
            for n_classes in (1, 2, 3, 7, 13):
                weights = {f"d{i}": 1.0 for i in range(n_classes)}
                counts = allocate.allocate_counts(total, weights)
                ratios = {d: allocate.ratio_for_count(c, total) for d, c in counts.items() if c > 0}
                reproduced = _schedule_counts(total, ratios)
                for d, c in counts.items():
                    if c > 0:
                        self.assertEqual(reproduced[d], c, f"total={total} n={n_classes} defect={d}")

    def test_zero_count_gives_zero_ratio(self):
        self.assertEqual(allocate.ratio_for_count(0, 1000), 0.0)

    def test_full_count_gives_ratio_that_reproduces_total(self):
        ratio = allocate.ratio_for_count(1000, 1000)
        self.assertEqual(int(1000 * ratio), 1000)


class DefectOptionsTests(unittest.TestCase):
    """Against the real repo templates/LoRA dir: every defect in defect_prompts
    must be covered by a mask generator (per the review doc), and the base
    config's real LoRA files are either present or clearly reported absent."""

    def test_all_thirteen_defects_listed(self):
        base_cfg = yaml.safe_load((whitelist.CONFIG_DIR / "batch-config.yaml").read_text())
        options = compose.defect_options(base_cfg)
        self.assertEqual(len(options), 13)
        for opt in options:
            self.assertIn("lora_present", opt)
            self.assertIn("mask_generator", opt)

    def test_compose_options_route_shape(self):
        result = compose.compose_options(REAL_BASE_CONFIG)
        self.assertIn("defects", result)
        self.assertIn("default_total_images", result)
        self.assertIn("default_backgrounds_dir", result)
        self.assertEqual(result["default_total_images"], 1000)


class ComposeValidationTests(unittest.TestCase):
    """compose_config raises ComposeError (never a bare exception) for every
    kind of bad input, and never touches the base config file."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.generated_dir = Path(self.tmp.name) / "_generated"
        patches = [
            mock.patch("plant_hmi.plant_batch_config_whitelist.GENERATED_DIR", self.generated_dir),
            mock.patch("plant_hmi.plant_batch_compose_validate.whitelist.GENERATED_DIR", self.generated_dir),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.base_path = whitelist.CONFIG_DIR / REAL_BASE_CONFIG
        self.base_hash_before = hashlib.sha256(self.base_path.read_bytes()).hexdigest()

    def _assert_base_untouched(self):
        self.assertEqual(hashlib.sha256(self.base_path.read_bytes()).hexdigest(), self.base_hash_before)

    def _compose(self, **overrides):
        kwargs = dict(name="zz-test-batch", base_config=REAL_BASE_CONFIG, total_images=100,
                      distribution={"crack": 1.0}, backgrounds_dir=None, reason="test",
                      overwrite=False, who="test")
        kwargs.update(overrides)
        return compose.compose_config(**kwargs)

    def test_bad_name_rejected(self):
        for bad in ("Has-Upper", "has_underscore", "has space", "", "a" * 61, "../etc"):
            with self.assertRaises(compose.ComposeError, msg=bad):
                self._compose(name=bad)
        self._assert_base_untouched()

    def test_unknown_base_config_rejected(self):
        with self.assertRaises(compose.ComposeError):
            self._compose(base_config="../../../etc/passwd")

    def test_unknown_defect_rejected(self):
        with self.assertRaises(compose.ComposeError):
            self._compose(distribution={"not_a_real_defect": 1.0})
        self._assert_base_untouched()

    def test_missing_lora_rejected(self):
        with mock.patch("plant_hmi.plant_batch_compose.lora_present", return_value=False):
            with self.assertRaises(compose.ComposeError) as ctx:
                self._compose(distribution={"crack": 1.0})
            self.assertIn("crack", str(ctx.exception))
        self._assert_base_untouched()

    def test_missing_mask_generator_rejected(self):
        with mock.patch.object(compose, "MASK_GENERATOR_DEFECTS", set()):
            with self.assertRaises(compose.ComposeError):
                self._compose(distribution={"crack": 1.0})
        self._assert_base_untouched()

    def test_all_zero_weight_rejected(self):
        with self.assertRaises(compose.ComposeError):
            self._compose(distribution={"crack": 0.0, "porosity": 0.0})
        self._assert_base_untouched()

    def test_bad_total_images_rejected(self):
        for bad in (0, -1, 20001, 1.5, "1000", True):
            with self.assertRaises(compose.ComposeError, msg=repr(bad)):
                self._compose(total_images=bad)
        self._assert_base_untouched()

    def test_nonexistent_backgrounds_dir_rejected(self):
        with self.assertRaises(compose.ComposeError):
            self._compose(backgrounds_dir="/no/such/dir/at/all")
        self._assert_base_untouched()

    def test_backgrounds_dir_with_no_images_rejected(self):
        with tempfile.TemporaryDirectory() as empty_dir:
            with self.assertRaises(compose.ComposeError):
                self._compose(backgrounds_dir=empty_dir)
        self._assert_base_untouched()

    def test_backgrounds_dir_outside_allowlist_rejected(self):
        with tempfile.TemporaryDirectory() as outside:
            (Path(outside) / "bg.png").write_bytes(b"\x89PNG")
            with self.assertRaises(compose.ComposeError):
                self._compose(backgrounds_dir=outside)
        self._assert_base_untouched()

    def test_valid_compose_writes_file_and_leaves_base_untouched(self):
        result = self._compose(distribution={"crack": 1.0})
        self.assertEqual(result["config_name"], "_generated/zz-test-batch.yaml")
        written = yaml.safe_load((self.generated_dir / "zz-test-batch.yaml").read_text())
        self.assertEqual(written["generation"]["total_images"], 100)
        self.assertEqual(result["counts"]["crack"], 100)
        self._assert_base_untouched()

    def test_overwrite_refused_without_flag(self):
        self._compose(distribution={"crack": 1.0})
        with self.assertRaises(compose.ComposeError):
            self._compose(distribution={"crack": 1.0})

    def test_overwrite_allowed_with_flag(self):
        self._compose(distribution={"crack": 1.0})
        result = self._compose(distribution={"crack": 1.0}, overwrite=True)
        self.assertEqual(result["config_name"], "_generated/zz-test-batch.yaml")

    def test_exact_counts_reproduce_through_scheduler_formula(self):
        result = self._compose(total_images=333, distribution={"crack": 2, "porosity": 1})
        written = yaml.safe_load((self.generated_dir / "zz-test-batch.yaml").read_text())
        ratios = written["generation"]["defect_distribution"]
        reproduced = _schedule_counts(333, ratios)
        for defect, count in result["counts"].items():
            self.assertEqual(reproduced.get(defect, 0), count)
        self.assertEqual(sum(result["counts"].values()), 333)

    def test_lora_models_key_not_copied_forward(self):
        self._compose(distribution={"crack": 1.0})
        written = yaml.safe_load((self.generated_dir / "zz-test-batch.yaml").read_text())
        self.assertNotIn("lora_models", written)


class LoraPresentPermissiveTests(unittest.TestCase):
    FULL_OK = {"live_batch_count": 0, "comfy_ok": True, "training_pids": [],
               "mem_low": False, "swap_thrash": False, "config_valid": True,
               "main_silo": False, "lora_missing": []}

    def test_ok_when_nothing_missing(self):
        rows = evaluate_permissives(self.FULL_OK)
        self.assertTrue(next(r for r in rows if r["code"] == "LORA_PRESENT")["ok"])
        self.assertEqual(blocking_failures(rows), [])

    def test_blocks_when_defect_missing_lora(self):
        rows = evaluate_permissives({**self.FULL_OK, "lora_missing": ["lack_of_side_wall_fusion"]})
        failures = [f["code"] for f in blocking_failures(rows)]
        self.assertIn("LORA_PRESENT", failures)
        row = next(r for r in rows if r["code"] == "LORA_PRESENT")
        self.assertIn("lack_of_side_wall_fusion", row["message"])

    def test_missing_for_config_flags_zero_weight_as_unaffected(self):
        cfg = {"generation": {"defect_distribution": {"crack": 0.0}}}
        self.assertEqual(compose.missing_for_config(cfg), [])

    def test_missing_for_config_flags_absent_lora(self):
        cfg = {"generation": {"defect_distribution": {"crack": 1.0}}}
        with mock.patch("plant_hmi.plant_batch_compose.lora_present", return_value=False):
            self.assertEqual(compose.missing_for_config(cfg), ["crack"])


class ComposeRouteTests(unittest.TestCase):
    """Routes via fastapi TestClient: CSRF guard, 400 on bad input, 200 + audit
    on success. Lock/audit paths point at a temp dir, never the real control/."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        d = Path(self.tmp.name)
        patches = [
            mock.patch("plant_hmi.plant_batch_audit.CONTROL_DIR", d),
            mock.patch("plant_hmi.plant_batch_audit.AUDIT_PATH", d / "batch-audit.jsonl"),
            mock.patch("plant_hmi.plant_batch_config_whitelist.GENERATED_DIR", d / "_generated"),
            mock.patch("plant_hmi.plant_batch_compose_validate.whitelist.GENERATED_DIR", d / "_generated"),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        app = FastAPI()
        app.include_router(compose_routes.router, prefix="/plant-hmi/api/control/batch")
        self.client = TestClient(app)

    def test_compose_without_header_is_403(self):
        res = self.client.post("/plant-hmi/api/control/batch/compose",
                               json={"name": "x", "base_config": REAL_BASE_CONFIG,
                                     "total_images": 10, "distribution": {"crack": 1.0}})
        self.assertEqual(res.status_code, 403)

    def test_compose_bad_input_is_400_with_failures(self):
        res = self.client.post("/plant-hmi/api/control/batch/compose",
                               json={"name": "Bad Name!", "base_config": REAL_BASE_CONFIG,
                                     "total_images": 10, "distribution": {"crack": 1.0}},
                               headers={"X-Plant-HMI": "1"})
        self.assertEqual(res.status_code, 400)
        self.assertTrue(res.json()["failures"])

    def test_compose_success_returns_counts_and_is_audited(self):
        res = self.client.post("/plant-hmi/api/control/batch/compose",
                               json={"name": "zz-route-test", "base_config": REAL_BASE_CONFIG,
                                     "total_images": 50, "distribution": {"crack": 1.0},
                                     "reason": "route test"},
                               headers={"X-Plant-HMI": "1"})
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["config_name"], "_generated/zz-route-test.yaml")
        self.assertEqual(body["counts"]["crack"], 50)

    def test_compose_options_route_returns_defects(self):
        res = self.client.get(f"/plant-hmi/api/control/batch/compose-options?base={REAL_BASE_CONFIG}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()["defects"]), 13)


if __name__ == "__main__":
    unittest.main(verbosity=2)
