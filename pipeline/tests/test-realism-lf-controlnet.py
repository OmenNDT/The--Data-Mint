"""Lack of fusion in issue 1, the controlnet_strength knob, and "newest set" with per-run folders.

Run: .venv/bin/python tests/test-realism-lf-controlnet.py
"""

import importlib.util
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

PIPELINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPELINE))

from realism import issues, knobs, loop  # noqa: E402


def _load_scheduler():
    spec = importlib.util.spec_from_file_location("bjs", PIPELINE / "batch_manager" / "batch-job-scheduler.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class IssueOneCoversLackOfFusion(unittest.TestCase):
    def test_lf_pair_has_edge_targets(self):
        one = next(i for i in issues.ISSUES if i["id"] == 1)
        lf = [t for t in one["targets"] if t["pair"] == "LP↔lack_of_fusion"]
        self.assertEqual(sorted(t["crit"] for t in lf), ["_hit", "bien_daodong", "bien_doc"])
        self.assertIn("lack_of_fusion", one["types"])
        self.assertIn("lack_of_fusion", loop.DEFAULT_TYPES)

    def test_lf_edge_failure_detected_from_real_numbers(self):
        # LF-100 run (2026-10-02): edge slope 9.64 vs real 3.64, oscillation AUC 0.06
        result = {"pairs": [{"pair": "LP↔lack_of_fusion", "hit": 0.96, "crit": {
            "bien_doc": {"syn_med": 9.636, "real_med": 3.642, "auc": 0.96, "syn_iqr": [8, 11]},
            "bien_daodong": {"syn_med": 0.268, "real_med": 0.497, "auc": 0.06, "syn_iqr": [0.2, 0.3]}}}]}
        one = next(i for i in issues.evaluate(result) if i["id"] == 1)
        lf = {t["crit"]: t["pass"] for t in one["targets"] if t["pair"] == "LP↔lack_of_fusion"}
        self.assertEqual(lf, {"bien_doc": False, "bien_daodong": False, "_hit": True})


class ControlNetKnob(unittest.TestCase):
    def test_default_is_current_workflow_value_first_fix_is_0_7(self):
        spec = knobs.REGISTRY["controlnet_strength"]
        self.assertEqual((spec[2], spec[3], spec[4], spec[5]), (0.3, 1.0, 0.8, 0.7))
        self.assertEqual(knobs.validate("controlnet_strength", 0.55), 0.55)
        with self.assertRaises(ValueError):
            knobs.validate("controlnet_strength", 1.5)

    def test_scheduler_applies_knob_only_to_controlnet_node(self):
        import yaml
        base = yaml.safe_load((PIPELINE / "config" / "batch-config.yaml").read_text())
        if not Path(base["paths"]["backgrounds_dir"]).is_dir():
            self.skipTest("no background patches on this machine")
        bjs = _load_scheduler()
        base["generation"]["total_images"] = 1
        base["generation"]["defect_distribution"] = {"lack_of_fusion": 1.0}
        for knob, expected in ((None, 0.8), (0.55, 0.55)):
            cfg = {**base, "_realism_knobs": {} if knob is None else {"controlnet_strength": knob}}
            with mock.patch("builtins.print"):
                sched = bjs.BatchJobScheduler(cfg)
            wf = sched.build_workflow(sched.get_next_job(), "bg.png", "mask.png")
            self.assertEqual(wf["9"]["class_type"], "ControlNetApplyAdvanced")
            self.assertEqual(wf["9"]["inputs"]["strength"], expected)


class ControlNetAutoTuning(unittest.TestCase):
    """The loop moves controlnet_strength: first round to 0.7 with the other edge knobs, then
    −0.05 while the edge slope fails, +0.05 when lesions stop matching the mask (hit < 0.7)."""

    @staticmethod
    def _result(slope_ratio, hit):
        crit = {"bien_doc": {"syn_med": 3.642 * slope_ratio, "real_med": 3.642, "auc": 0.9, "syn_iqr": [1, 2]},
                "bien_daodong": {"syn_med": 0.45, "real_med": 0.497, "auc": 0.4, "syn_iqr": [0.4, 0.5]}}
        return {"pairs": [{"pair": p, "hit": hit, "crit": crit} for p in issues.MAIN]}

    def test_first_round_jumps_to_suggested(self):
        new, _ = issues.propose(self._result(2.6, 0.96), dict(knobs.DEFAULTS))
        self.assertEqual(new["controlnet_strength"], 0.7)

    def test_edge_still_sharp_lowers_adherence(self):
        cur = {**knobs.DEFAULTS, "post_depth_min": 0.45, "post_depth_max": 0.65, "post_modulation": 0.65,
               "post_edge_blur_sigma": 3.0, "controlnet_strength": 0.7}
        new, why = issues.propose(self._result(2.0, 0.96), cur)
        self.assertAlmostEqual(new["controlnet_strength"], 0.65)
        self.assertTrue(any("ControlNet bớt bám mask" in w for w in why))

    def test_lost_lesions_raise_adherence_and_block_lowering(self):
        cur = {**knobs.DEFAULTS, "post_depth_min": 0.45, "post_depth_max": 0.65, "post_modulation": 0.65,
               "post_edge_blur_sigma": 3.0, "controlnet_strength": 0.5}
        new, _ = issues.propose(self._result(2.0, 0.5), cur)
        self.assertAlmostEqual(new["controlnet_strength"], 0.55)

    def test_never_leaves_registry_bounds(self):
        cur = {**knobs.DEFAULTS, "post_depth_min": 0.45, "post_depth_max": 0.65, "post_modulation": 0.65,
               "post_edge_blur_sigma": 3.0, "controlnet_strength": 0.3}
        new, _ = issues.propose(self._result(2.0, 0.96), cur)
        self.assertEqual(new["controlnet_strength"], 0.3)


class ProposeAfterRejection(unittest.TestCase):
    """After a rejected round the candidate knobs are back at the best round, so the next proposal
    must read the BEST round's measurements, not the rejected one's."""

    def _propose_reads(self, hist, best):
        seen = []
        with mock.patch.object(loop, "history", return_value=hist), \
                mock.patch.object(loop.loop_gate, "read_best", return_value=best), \
                mock.patch.object(loop, "read_json", side_effect=lambda run, name: {"run": run}), \
                mock.patch.object(loop.issues, "propose", side_effect=lambda r, c: (seen.append(r["run"]) or (dict(c), []))), \
                mock.patch.object(loop, "candidate", return_value=dict(knobs.DEFAULTS)), \
                mock.patch.object(loop.tuning_memory, "apply_to_proposal", side_effect=lambda cur, new: new):
            loop.do_propose(mock.Mock())
        return seen[0]

    def test_rejected_round_uses_best_measurements(self):
        hist = [{"iter": 2, "eval_run": "e2", "decision": "best"}, {"iter": 3, "eval_run": "e3", "decision": "rejected"}]
        self.assertEqual(self._propose_reads(hist, {"iter": 2, "eval_run": "e2"}), "e2")

    def test_accepted_round_uses_its_own_measurements(self):
        hist = [{"iter": 2, "eval_run": "e2", "decision": "best"}, {"iter": 3, "eval_run": "e3", "decision": "accepted"}]
        self.assertEqual(self._propose_reads(hist, {"iter": 2, "eval_run": "e2"}), "e3")


class GateScoreCountsTargets(unittest.TestCase):
    def test_one_passing_target_counts_even_if_issue_still_fails(self):
        from realism import loop_gate
        # round A on the exam set (2026-10-02 12:33): LF edge targets fail, lesion hit 1.0 passes
        result = {"pairs": [{"pair": "LP↔lack_of_fusion", "synthetic": "lack_of_fusion", "hit": 1.0, "c2st": 0.958,
                             "crit": {"bien_doc": {"syn_med": 9.87, "real_med": 3.642, "auc": 0.97, "syn_iqr": [8, 11]},
                                      "bien_daodong": {"syn_med": 0.27, "real_med": 0.497, "auc": 0.07,
                                                       "syn_iqr": [0.2, 0.3]}}}]}
        n_pass, c2st = loop_gate.score(result, ["lack_of_fusion"])
        self.assertEqual((n_pass, round(c2st, 3)), (1, 0.958))


class NewestSet(unittest.TestCase):
    def test_newest_run_folder_or_loop_iteration_wins(self):
        with tempfile.TemporaryDirectory() as d:
            silo, loop_out = Path(d) / "synthetic", Path(d) / "realism-loop" / "iter-01"
            old_run, new_run = silo / "2026-10-01_080000_a", silo / "2026-10-02_090000_b"
            for p in (old_run, new_run, loop_out):
                p.mkdir(parents=True)
            now = time.time()
            os.utime(old_run, (now - 300, now - 300))
            os.utime(loop_out, (now - 200, now - 200))
            os.utime(new_run, (now - 100, now - 100))
            hist = [{"iter": 1, "source": str(loop_out)}]
            with mock.patch.object(loop, "BASELINE", silo), mock.patch.object(loop, "history", return_value=hist):
                self.assertEqual(loop.latest_source(), new_run)
                os.utime(loop_out, (now, now))
                self.assertEqual(loop.latest_source(), loop_out)
            with mock.patch.object(loop, "BASELINE", Path(d) / "empty"), mock.patch.object(loop, "history", return_value=[]):
                self.assertEqual(loop.latest_source(), Path(d) / "empty")


if __name__ == "__main__":
    unittest.main(verbosity=2)
