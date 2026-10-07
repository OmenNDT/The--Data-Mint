"""Thử vòng cải thiện độ thật: bộ đo khớp bảng RIAWELC, núm vặn (giải, đóng băng, PV), móc bộ sinh (mặc định giữ nguyên,
núm sửa đổi đúng hướng, chặn mặt nạ trống), 5 vấn đề (chấm, đề xuất), tuyến HTTP (CSRF, 422, 409; không mở tiến trình).

Run: .venv/bin/python tests/test-realism-loop.py
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import cv2
import numpy as np
import pandas as pd
from PIL import Image
from skimage.measure import label, regionprops

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from mask_generator import CrackMaskGenerator, LackOfPenetrationMaskGenerator, PorosityMaskGenerator  # noqa: E402
from realism import exam_set, issues, knobs, loop, loop_gate, paired_stats, tuning_memory  # noqa: E402
from realism.evaluate import compare  # noqa: E402
from realism.features import CRITERIA, REF_DIR, six_criteria  # noqa: E402
from realism.generator_hooks import darken_strength, shape_generated_mask  # noqa: E402

RIAWELC = Path("/home/sontn/Projects/The Data Mint/dataset/RIAWELC/extracted-fresh/DB - Copy")
PRESET = {k: s[5] for k, s in knobs.REGISTRY.items()}


class KnobDir(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        self.p = [mock.patch.object(knobs, "STATE_DIR", d), mock.patch.dict(os.environ, {}, clear=False),
                  mock.patch.object(loop_gate, "BEST_PATH", d / "best.json"),
                  mock.patch.object(loop_gate, "STATE", d), mock.patch.object(tuning_memory, "PATH", d / "tuning-memory.json")]
        for p in self.p:
            p.start()
        os.environ.pop("REALISM_KNOBS", None)
        os.environ.pop(knobs.FROZEN_ENV, None)

    def tearDown(self):
        for p in reversed(self.p):
            p.stop()
        self.tmp.cleanup()

    def freeze(self, vals):
        os.environ[knobs.FROZEN_ENV] = json.dumps({k: {"value": v, "source": "LOCAL"} for k, v in vals.items()})


class FeaturesMatchReference(unittest.TestCase):
    @unittest.skipUnless(RIAWELC.exists(), "không có bộ RIAWELC trên máy")
    def test_six_criteria_equal_reference(self):
        ref = pd.read_csv(REF_DIR / "riawelc-six-criteria.csv").sample(25, random_state=7)
        for _, r in ref.iterrows():
            f = six_criteria(np.asarray(Image.open(RIAWELC / r["file"]).convert("L"), np.float32))
            self.assertEqual(bool(f["has_region"]), r["vung_sodom"] > 0, r["file"])
            if r["vung_sodom"] > 0:
                for k in CRITERIA:
                    self.assertAlmostEqual(f[k], r[k], delta=1e-4 * max(1, abs(r[k])), msg=f"{r['file']} {k}")


class KnobsTest(KnobDir):
    def test_resolve_order_and_bounds(self):
        self.assertEqual(knobs.resolve()["crack_transverse_share"], {"value": 0.0, "source": "default"})
        knobs.write_many({"crack_transverse_share": 0.3}, "test", "r")
        self.assertEqual(knobs.resolve()["crack_transverse_share"]["source"], "REMOTE")
        os.environ["REALISM_KNOBS"] = json.dumps({"crack_transverse_share": 0.5})
        self.assertEqual(knobs.resolve()["crack_transverse_share"], {"value": 0.5, "source": "LOCAL"})
        with self.assertRaises(ValueError):
            knobs.write_many({"crack_transverse_share": 2}, "test", "ngoài giới hạn")
        self.assertEqual(len(knobs.audit_tail()), 1)

    def test_freeze_writes_pv(self):
        with tempfile.TemporaryDirectory() as out:
            r = knobs.freeze_for_batch(out)
            self.assertEqual(knobs.read_pv(out)["knobs"], r)
            knobs.write_many({"lop_gap_max": 2}, "test", "đổi giữa đợt")
            self.assertEqual(knobs.resolve()["lop_gap_max"]["value"], 0)       # đã đóng băng: không đổi giữa đợt


class HooksTest(KnobDir):
    def test_defaults_are_identical_to_old_code(self):
        b, f = CrackMaskGenerator(height=512, width=512, seed=3, weld_center_y=256).generate()
        b2, f2 = shape_generated_mask("crack", 3, b, f, regenerate=None)
        self.assertIs(b2, b)
        m = np.zeros((512, 512), np.uint8)
        m[200:230, 100:400] = 255
        old = cv2.GaussianBlur(m.astype(np.float32), (0, 0), sigmaX=2.0) / 255.0
        np.testing.assert_array_equal(darken_strength(m, 0.92, "a.png"), old / old.max() * 0.92)

    def test_preset_moves_shapes_toward_riawelc(self):
        self.freeze(PRESET)
        big = lambda a: max(regionprops(label(a > 127)), key=lambda r: r.area)
        vert, e0, e1, tilt = 0, [], [], []
        for s in range(40):
            b, f = CrackMaskGenerator(height=512, width=512, seed=s, weld_center_y=256).generate()
            vert += abs(np.degrees(big(shape_generated_mask("crack", s, b, f, None)[0]).orientation)) < 45
            b, f = PorosityMaskGenerator(height=512, width=512, seed=s, weld_center_y=256).generate()
            if (b > 127).any():
                e0.append(big(b).eccentricity)
                e1.append(big(shape_generated_mask("porosity", s, b, f, None)[0]).eccentricity)
            b, f = LackOfPenetrationMaskGenerator(height=512, width=512, seed=s, weld_center_y=256).generate()
            tilt.append(abs(np.degrees(big(shape_generated_mask("lack_of_penetration", s, b, f, None)[0]).orientation)))
        self.assertTrue(0.25 <= vert / 40 <= 0.7, vert)
        self.assertGreater(np.median(e1), np.median(e0) + 0.1)
        self.assertLess(np.percentile(tilt, 25), 89.0)
        m = np.zeros((512, 512), np.uint8)
        m[200:230, 100:400] = 255
        s = darken_strength(m, 0.92, "a.png")
        self.assertLess(s.max(), 0.92 * 0.66)                                   # nông hơn, không đều
        self.assertGreater(s[m > 0].std(), 0.02)

    def test_bright_sd_defect_still_darker_than_background(self):
        from realism.generator_hooks import darken_image
        rng = np.random.default_rng(0)
        bg = 120 + rng.normal(0, 5, (512, 512)).astype(np.float32)
        m = np.zeros((512, 512), np.uint8)
        m[250:262, 100:400] = 255
        img = bg.copy()
        img[m > 0] += 70                                                        # LoRA vẽ lỗi SÁNG
        old = darken_image(img, bg, m, 0.78, "k.png")                          # núm mặc định: đúng cách cũ
        s = darken_strength(m, 0.78, "k.png")
        np.testing.assert_allclose(old, img * (1 - s))
        self.freeze(PRESET)
        new = darken_image(img, bg, m, 0.78, "k.png")
        self.assertLess(new[m > 0].mean(), bg[m > 0].mean() - 10)              # luôn tối hơn nền
        self.assertLess(np.abs(new - bg)[:200].max(), 1e-3)                     # xa lỗi: đúng nền

    def test_transverse_crack_sits_on_weld_line(self):
        from realism.mask_shaping import shape_mask
        self.freeze(PRESET)
        from realism.knobs import values
        k = dict(values(), crack_transverse_share=0.8)
        for s in range(10):
            b, _ = CrackMaskGenerator(height=512, width=512, seed=s, weld_center_y=300).generate()
            out = shape_mask("crack", b, s, k, weld_center_y=300)
            p = max(regionprops(label(out > 127)), key=lambda r: r.area)
            if abs(np.degrees(p.orientation)) < 45:
                self.assertLess(abs(p.centroid[0] - 300), 60)
            b, _ = CrackMaskGenerator(height=512, width=512, seed=s, weld_center_y=64).generate()
            rows = np.nonzero((shape_mask("crack", b, s, k, weld_center_y=64) > 127).any(1))[0]
            self.assertGreater(rows.min(), 0)                                  # tâm hàn sát mép: không tràn khung

    def test_untouched_types_keep_original_masks(self):
        self.freeze({**{k: s[4] for k, s in knobs.REGISTRY.items()}, "crack_transverse_share": 0.5})
        b, f = PorosityMaskGenerator(height=512, width=512, seed=5, weld_center_y=256).generate()
        b2, f2 = shape_generated_mask("porosity", 5, b, f, regenerate=None)
        self.assertIs(b2, b)
        self.assertIs(f2, f)

    def test_empty_mask_is_regenerated(self):
        seeds = []

        def regen(s):
            seeds.append(s)
            return (np.pad(np.full((4, 4), 255, np.uint8), 254), None)
        b, _ = shape_generated_mask("porosity", 1, np.zeros((512, 512), np.uint8), None, regenerate=regen)
        self.assertTrue((b > 127).any())
        self.assertEqual(len(seeds), 1)


def _fake_result(over):
    crit = {k: {"real_med": 1.0, "real_iqr": [0.5, 1.5], "syn_med": 1.0, "syn_iqr": [0.5, 1.5], "auc": 0.5,
                "real_lt45": 0.4, "syn_lt45": 0.4} for k in CRITERIA}
    pairs = []
    for p in ("CR↔crack", "PO↔porosity", "LP↔lack_of_penetration"):
        c = json.loads(json.dumps(crit))
        for (pp, k, key), v in over.items():
            if pp == p:
                c[k][key] = v
        pairs.append({"pair": p, "crit": c})
    return {"pairs": pairs}


class IssuesTest(unittest.TestCase):
    def test_evaluate_and_propose(self):
        r = _fake_result({("CR↔crack", "vung_huong", "syn_lt45"): 0.01})
        st = {i["id"]: i["status"] for i in issues.evaluate(r)}
        self.assertEqual(st[2], "fail")
        cur = {k: s[4] for k, s in knobs.REGISTRY.items()}
        new, why = issues.propose(r, cur)
        self.assertEqual(new["crack_transverse_share"], PRESET["crack_transverse_share"])  # mặc định → nhảy tới giá trị sửa
        new2, _ = issues.propose(r, new)
        self.assertAlmostEqual(new2["crack_transverse_share"], PRESET["crack_transverse_share"] + 0.1)
        self.assertEqual(issues.evaluate(None)[0]["status"], "na")

    def test_one_step_per_knob_per_round(self):
        over = {(p, "bien_doc", "syn_med"): 3.0 for p in ("CR↔crack", "PO↔porosity", "LP↔lack_of_penetration")}
        cur = dict(PRESET)
        new, _ = issues.propose(_fake_result(over), cur)
        self.assertAlmostEqual(new["post_depth_max"], cur["post_depth_max"] * 0.85)   # một lần, không phải 0,85³

    def test_low_detection_blocks_shallower_darkening(self):
        r = _fake_result({(p, "bien_doc", "syn_med"): 3.0 for p in ("CR↔crack",)})
        r["pairs"][0]["hit"] = 0.4
        new, why = issues.propose(r, dict(PRESET))
        self.assertGreater(new["post_depth_max"], PRESET["post_depth_max"])          # làm tối sâu hơn, không nông hơn


SYN_OF = {"CR↔crack": "crack", "PO↔porosity": "porosity", "LP↔lack_of_penetration": "lack_of_penetration"}


def _cases_for(pair, kind, ids, value=0.5):
    return [{"case_id": c, "pair": pair, "kind": kind, "hit": 1.0, **{k: value for k in CRITERIA}} for c in ids]


def _fake_round(over, c2st=0.6, cases=None):
    """_fake_result (IssuesTest) + các trường loop_gate cần: synthetic/c2st mỗi cặp, cases (ghép cặp)."""
    r = _fake_result(over)
    for p in r["pairs"]:
        p["synthetic"] = SYN_OF[p["pair"]]
        p["c2st"] = c2st
    r["cases"] = cases or []
    return r


class GateTest(KnobDir):
    """Cổng nghiệm thu bước 3: nhận/giữ nguyên/loại so bản tốt nhất, trên dữ liệu tổng hợp (không gọi ComfyUI)."""

    def setUp(self):
        super().setUp()
        self.results = {}
        self.p.append(mock.patch.object(loop_gate, "read_json", side_effect=lambda rid, name: self.results.get(rid)))
        self.p[-1].start()

    def _set(self, run_id, result):
        self.results[run_id] = result

    def _rec(self, it, run_id, knobs_vals=None):
        return {"iter": it, "eval_run": run_id, "knobs": {k: {"value": v} for k, v in (knobs_vals or {}).items()},
                "issues": {}, "c2st": {}, "all_pass": False, "types": ["crack", "porosity"]}

    def test_no_best_and_no_cases_is_neutral_non_exam_ignored(self):
        self._set("r0", _fake_result({}))                       # không "cases": bộ ngẫu nhiên cũ
        rec = loop_gate.gate(self._rec(0, "r0"))
        self.assertEqual(rec["decision"], "neutral")
        self.assertIsNone(loop_gate.read_best())                 # không trở thành mốc

    def test_first_exam_set_round_becomes_best(self):
        ids = [f"c{i}" for i in range(6)]
        self._set("r1", _fake_round({}, cases=_cases_for("CR↔crack", "crack", ids)))
        rec = loop_gate.gate(self._rec(1, "r1", {"crack_transverse_share": 0.2}))
        self.assertEqual(rec["decision"], "best")
        self.assertEqual(rec["reasons"], ["mốc mới: bộ đề thi"])
        self.assertEqual(loop_gate.read_best()["iter"], 1)

    def test_improved_round_is_accepted_and_becomes_new_best(self):
        ids = [f"c{i}" for i in range(6)]
        cases = _cases_for("CR↔crack", "crack", ids) + _cases_for("PO↔porosity", "porosity", ids) \
            + _cases_for("LP↔lack_of_penetration", "lack_of_penetration", ids)
        fail_crack = {("CR↔crack", "vung_dac", "syn_med"): 0.1}          # issue 2 trượt ở bản tốt nhất (n_pass thấp hơn)
        self._set("best", _fake_round(fail_crack, cases=cases))
        loop_gate.gate(self._rec(1, "best", {"crack_transverse_share": 0.1}))
        self._set("new", _fake_round({}, cases=cases))                   # issue 2 đạt ở vòng mới: n_pass tăng
        rec = loop_gate.gate(self._rec(2, "new", {"crack_transverse_share": 0.3}))
        self.assertEqual(rec["decision"], "accepted")
        self.assertEqual(loop_gate.read_best()["iter"], 2)

    def test_neutral_when_identical_to_best(self):
        ids = [f"c{i}" for i in range(6)]
        cases = _cases_for("CR↔crack", "crack", ids) + _cases_for("PO↔porosity", "porosity", ids) \
            + _cases_for("LP↔lack_of_penetration", "lack_of_penetration", ids)
        self._set("best", _fake_round({}, cases=cases))
        loop_gate.gate(self._rec(1, "best", {"crack_transverse_share": 0.1}))
        self._set("new", _fake_round({}, cases=cases))                   # giống hệt bản tốt nhất
        rec = loop_gate.gate(self._rec(2, "new", {"crack_transverse_share": 0.1}))
        self.assertEqual(rec["decision"], "neutral")
        self.assertEqual(loop_gate.read_best()["iter"], 1)                # best không đổi

    def test_score_regression_rejects_and_reverts_knobs_exactly(self):
        ids = [f"c{i}" for i in range(6)]
        cases = _cases_for("CR↔crack", "crack", ids) + _cases_for("PO↔porosity", "porosity", ids) \
            + _cases_for("LP↔lack_of_penetration", "lack_of_penetration", ids)
        self._set("best", _fake_round({}, cases=cases))                           # n_pass cao
        loop_gate.gate(self._rec(1, "best", {"crack_transverse_share": 0.1}))
        fail_crack = {("CR↔crack", "vung_dac", "syn_med"): 0.1}                   # n_pass thấp hơn rõ
        self._set("new", _fake_round(fail_crack, cases=cases))
        rec = loop_gate.gate(self._rec(2, "new", {"crack_transverse_share": 0.3}))
        self.assertEqual(rec["decision"], "rejected")
        self.assertEqual(knobs.resolve("candidate", use_env=False)["crack_transverse_share"]["value"], 0.1)  # lùi đúng về best

    def test_must_keep_target_breaking_rejects_even_with_equal_score(self):
        """n_pass bằng nhau (1 cả hai vòng) nhưng mục tiêu ĐANG ĐẠT ở bản tốt nhất (issue 2, nứt) bị trượt ở vòng
        mới, đổi lại issue 3 (rỗ khí) đạt bù — tổng điểm không đổi nhưng vẫn phải loại (lưới "phải giữ")."""
        ids = [f"c{i}" for i in range(6)]
        cases = _cases_for("CR↔crack", "crack", ids) + _cases_for("PO↔porosity", "porosity", ids) \
            + _cases_for("LP↔lack_of_penetration", "lack_of_penetration", ids)
        fail_porosity = {("PO↔porosity", "vung_lechtam", "syn_med"): 0.1}         # issue 3 trượt ở bản tốt nhất
        self._set("best", _fake_round(fail_porosity, cases=cases))
        ev_best = issues.evaluate(self.results["best"])
        self.assertEqual({i["id"]: i["status"] for i in ev_best}[2], "pass")      # issue 2 (nứt) đạt ở bản tốt nhất
        loop_gate.gate(self._rec(1, "best", {"crack_transverse_share": 0.1}))
        fail_crack_pass_porosity = {("CR↔crack", "vung_dac", "syn_med"): 0.1}     # issue 2 trượt, issue 3 giờ đạt
        self._set("new", _fake_round(fail_crack_pass_porosity, cases=cases))
        rec = loop_gate.gate(self._rec(2, "new", {"crack_transverse_share": 0.3}))
        self.assertEqual(rec["decision"], "rejected")
        self.assertTrue(any("Độ đặc" in r for r in rec["reasons"]))               # nhãn mục tiêu vung_dac issue 2


class TuningMemoryTest(KnobDir):
    def test_half_step_then_flip_direction(self):
        best, rejected = {"crack_widen_px": 1.0}, {"crack_widen_px": 2.0}         # thử hướng +1
        mem = tuning_memory.record_rejection(best, rejected)
        self.assertEqual(mem["crack_widen_px"], {"direction": 1, "scale": 0.5})
        mem = tuning_memory.record_rejection(best, rejected)                     # nửa bước cùng hướng cũng bị loại
        self.assertEqual(mem["crack_widen_px"], {"direction": -1, "scale": 1.0})  # đổi hướng, về bước đầy đủ

    def test_apply_to_proposal_uses_memory_direction_and_scale(self):
        current = {"crack_widen_px": 1.0}
        proposed = {"crack_widen_px": 2.0}                                        # rule thô: +1 (lên)
        mem = {"crack_widen_px": {"direction": -1, "scale": 0.5}}                 # bộ nhớ: đi xuống, nửa bước
        out = tuning_memory.apply_to_proposal(current, proposed, mem)
        self.assertAlmostEqual(out["crack_widen_px"], 1.0 - 1.0 * 0.5)            # 0,5, không phải 2,0

    def test_clear_removes_only_named_knobs(self):
        tuning_memory._write({"a": {"direction": 1, "scale": 0.5}, "b": {"direction": -1, "scale": 1.0}})
        tuning_memory.clear(["a"])
        self.assertNotIn("a", tuning_memory.read())
        self.assertIn("b", tuning_memory.read())

    def test_empty_memory_leaves_proposal_unchanged(self):
        proposed = {k: s[4] for k, s in knobs.REGISTRY.items()}
        out = tuning_memory.apply_to_proposal(dict(proposed), dict(proposed), mem={})
        self.assertEqual(out, proposed)                                          # không bộ nhớ: không đổi gì


class AutoStopTest(unittest.TestCase):
    def test_two_consecutive_neutral_stops(self):
        with mock.patch.object(loop, "history", return_value=[
                {"iter": 1, "decision": "best", "all_pass": False},
                {"iter": 2, "decision": "neutral", "all_pass": False},
                {"iter": 3, "decision": "neutral", "all_pass": False}]):
            self.assertTrue(loop._two_consecutive_neutral())
        with mock.patch.object(loop, "history", return_value=[
                {"iter": 1, "decision": "neutral", "all_pass": False},
                {"iter": 2, "decision": "accepted", "all_pass": False}]):
            self.assertFalse(loop._two_consecutive_neutral())


class EvaluateRobustness(unittest.TestCase):
    def test_unreadable_image_is_a_drain_not_a_crash(self):
        from realism.evaluate import measure
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "crack"
            p.mkdir()
            (p / "crack_000001.png").write_bytes(b"not a png")
            r = measure((str(p / "crack_000001.png"), 2))
        self.assertIn("error", r)
        self.assertEqual(r["kind"], "crack")


class SchedulerFixedJobsTest(unittest.TestCase):
    """fixed_jobs (bước 2 của plan): đúng thứ tự/ids, không random/shuffle; vắng khoá thì hành vi cũ y nguyên."""

    def _base_config(self, tmp, generation):
        workflow_path = Path(__file__).resolve().parent.parent / "comfyui-workflows" \
            / "sd15-lora-controlnet-inpaint-batch-api-workflow.json"
        prompts_path = Path(__file__).resolve().parent.parent / "comfyui-workflows" \
            / "defect-type-prompt-templates.yaml"
        bg_dir = Path(tmp) / "bg"
        bg_dir.mkdir(exist_ok=True)
        for i in range(3):
            Image.new("L", (8, 8)).save(bg_dir / f"bg{i}.png")
        return {
            "comfyui": {"workflow_path": str(workflow_path), "prompts_path": str(prompts_path)},
            "generation": generation,
            "paths": {"backgrounds_dir": str(bg_dir)},
        }

    def test_fixed_jobs_exact_order_ids_no_random(self):
        from batch_manager import BatchJobScheduler
        with tempfile.TemporaryDirectory() as tmp:
            cases = [
                {"case_id": "crack-000", "defect_type": "crack", "seed": 111, "background_image": "/x/a.png"},
                {"case_id": "porosity-000", "defect_type": "porosity", "seed": 222, "background_image": "/x/b.png"},
                {"case_id": "crack-001", "defect_type": "crack", "seed": 333, "background_image": "/x/c.png"},
            ]
            jobs_path = Path(tmp) / "jobs.json"
            jobs_path.write_text(json.dumps(cases), encoding="utf-8")
            cfg = self._base_config(tmp, {"total_images": 999, "fixed_jobs": str(jobs_path)})

            sched = BatchJobScheduler(cfg)
            self.assertEqual(len(sched.jobs), 3)
            for i, (job, case) in enumerate(zip(sched.jobs, cases)):
                self.assertEqual(job["job_id"], i)
                self.assertEqual(job["case_id"], case["case_id"])
                self.assertEqual(job["defect_type"], case["defect_type"])
                self.assertEqual(job["seed"], case["seed"])
                self.assertEqual(str(job["background_image"]), case["background_image"])

            sched2 = BatchJobScheduler(cfg)   # chạy lại: y hệt, không random/shuffle
            self.assertEqual([j["seed"] for j in sched.jobs], [j["seed"] for j in sched2.jobs])
            self.assertEqual([j["case_id"] for j in sched.jobs], [j["case_id"] for j in sched2.jobs])

    def test_absent_fixed_jobs_key_keeps_old_random_behaviour(self):
        from batch_manager import BatchJobScheduler
        import random
        with tempfile.TemporaryDirectory() as tmp:
            cfg = self._base_config(tmp, {"total_images": 6, "defect_distribution": {"crack": 0.5, "porosity": 0.5}})
            random.seed(42)
            sched = BatchJobScheduler(cfg)
            random.seed(42)
            sched2 = BatchJobScheduler(cfg)
            self.assertEqual(len(sched.jobs), 6)
            self.assertFalse(any("case_id" in j for j in sched.jobs))                   # không gắn case_id
            self.assertEqual([j["seed"] for j in sched.jobs], [j["seed"] for j in sched2.jobs])  # cùng seed random


class ExamSetTest(unittest.TestCase):
    def test_build_is_deterministic_and_subset_works(self):
        with tempfile.TemporaryDirectory() as tmp:
            bg = Path(tmp) / "bg"
            bg.mkdir()
            for i in range(5):
                Image.new("L", (4, 4)).save(bg / f"bg{i}.png")
            exam_path = Path(tmp) / "exam.json"
            with mock.patch.object(exam_set, "EXAM_SET_PATH", exam_path), \
                 mock.patch.object(exam_set, "STATE", Path(tmp)):
                exam1 = exam_set.build_exam_set(bg, types=["crack", "porosity"], per_type=5, seed=7)
                exam2 = exam_set.build_exam_set(bg, types=["crack", "porosity"], per_type=5, seed=7)
                self.assertEqual(exam1["cases"], exam2["cases"])
                self.assertEqual(len(exam1["cases"]), 10)
                self.assertEqual(exam_set.load_exam_set(exam_path), exam1)

            sub = exam_set.subset(["crack"], 3, exam=exam1)
            self.assertEqual(len(sub), 3)
            self.assertEqual(sub, [c for c in exam1["cases"] if c["defect_type"] == "crack"][:3])
            with self.assertRaises(ValueError):
                exam_set.subset(["crack"], 99, exam=exam1)


class EvaluateCaseRowsTest(unittest.TestCase):
    def test_compare_emits_case_rows_with_case_id(self):
        rows = []
        for i in range(12):
            row = {k: float(i % 5) for k in CRITERIA}
            row.update(kind="crack", empty_mask=False, has_region=True, hit=1.0, case_id=f"crack-{i:03d}")
            rows.append(row)
        real = pd.DataFrame({"cls": ["CR"] * 20, **{k: np.linspace(0, 1, 20) for k in CRITERIA}})
        pairs, cases = compare(rows, real)
        self.assertEqual(len(cases), 12)
        self.assertEqual({c["case_id"] for c in cases}, {f"crack-{i:03d}" for i in range(12)})
        for c in cases:
            self.assertEqual(c["pair"], "CR↔crack")
            for k in CRITERIA:
                self.assertIn(k, c)

    def test_job_id_and_case_map(self):
        from realism.evaluate import _job_id_of, load_case_map
        self.assertEqual(_job_id_of("/x/crack_000012.png"), 12)
        self.assertIsNone(_job_id_of("/x/crack_000012_mask.png"))
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(load_case_map(tmp), {})
            cases = [{"case_id": "a"}, {"case_id": "b"}]
            (Path(tmp) / "fixed-jobs.json").write_text(json.dumps(cases), encoding="utf-8")
            self.assertEqual(load_case_map(tmp), {0: "a", 1: "b"})


class PairedStatsTest(unittest.TestCase):
    """Bootstrap CI (bước 2): khoảng tin cậy ôm trung vị thật, ghép cặp phát hiện lệch rõ, bỏ qua nhiễu nhỏ."""

    @staticmethod
    def _result(values, pair="CR↔crack", crit="vung_dac"):
        cases = []
        for i, v in enumerate(values):
            c = {"case_id": f"c{i}", "pair": pair, "kind": "crack", "hit": 1.0, **{k: 0.5 for k in CRITERIA}}
            c[crit] = float(v)
            cases.append(c)
        return {"cases": cases}

    def test_bootstrap_targets_ci_contains_true_median(self):
        rng = np.random.default_rng(1)
        vals = rng.normal(0.6, 0.05, 60)
        boot = paired_stats.bootstrap_targets(self._result(vals), B=300, seed=0)
        entries = [e for e in boot if e["pair"] == "CR↔crack" and e["crit"] == "vung_dac" and "ci_low" in e]
        self.assertTrue(entries)
        true_med = float(np.median(vals))
        for e in entries:
            self.assertLessEqual(e["ci_low"], true_med)
            self.assertGreaterEqual(e["ci_high"], true_med)

    def test_compare_paired_detects_shift_but_not_noise(self):
        rng = np.random.default_rng(2)
        base = rng.normal(0.6, 0.03, 60)
        prev = self._result(base)
        same = self._result(base + rng.normal(0, 0.001, 60))
        shifted = self._result(base + 0.3)

        def entry_for(d):
            return next(e for e in d.values() if e["pair"] == "CR↔crack" and e["crit"] == "vung_dac")

        e_same = entry_for(paired_stats.compare_paired(prev, same, B=300, seed=0))
        e_shift = entry_for(paired_stats.compare_paired(prev, shifted, B=300, seed=0))
        self.assertFalse(e_same.get("significant", False))
        self.assertTrue(e_shift.get("significant", False))
        self.assertAlmostEqual(e_shift["delta"], 0.3, delta=0.02)


class RoutesTest(KnobDir):
    def setUp(self):
        super().setUp()
        import tempfile
        from plant_hmi import plant_realism_job_status as job_status
        from plant_hmi import plant_realism_routes as routes
        from realism import runlog
        # /api/run creates the run folder before spawning: keep it out of the real realism/state/runs
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        for target in (runlog, routes, job_status):
            patcher = mock.patch.object(target, "RUNS_DIR", Path(tmp.name))
            patcher.start()
            self.addCleanup(patcher.stop)
        app = FastAPI()
        app.include_router(routes.router, prefix="/plant-hmi")
        self.c = TestClient(app)
        self.h = {"X-Plant-HMI": "1"}

    def test_page_and_state(self):
        self.assertEqual(self.c.get("/plant-hmi/realism/").status_code, 200)
        s = self.c.get("/plant-hmi/realism/api/state").json()
        self.assertIn("job", s)
        self.assertEqual(set(s["knobs"]["registry"]), set(knobs.REGISTRY))

    def test_writes_need_csrf_header_and_valid_values(self):
        self.assertEqual(self.c.put("/plant-hmi/realism/api/knobs", json={"changes": {"lop_gap_max": 1}}).status_code, 403)
        self.assertEqual(self.c.put("/plant-hmi/realism/api/knobs", json={"changes": {"lop_gap_max": 99}}, headers=self.h).status_code, 422)
        self.assertEqual(self.c.put("/plant-hmi/realism/api/knobs", json={"changes": {"lop_gap_max": 1}}, headers=self.h).status_code, 200)
        self.assertEqual(self.c.post("/plant-hmi/realism/api/run", json={"action": "cycle"}).status_code, 403)
        self.assertEqual(self.c.post("/plant-hmi/realism/api/run", json={"action": "x"}, headers=self.h).status_code, 422)
        self.assertEqual(self.c.post("/plant-hmi/realism/api/run", json={"action": "cycle", "n_per_type": 0}, headers=self.h).status_code, 422)
        self.assertEqual(knobs.resolve("candidate", use_env=False)["lop_gap_max"]["value"], 1)
        self.assertEqual(knobs.resolve("production", use_env=False)["lop_gap_max"]["value"], 0)   # sản xuất chưa đổi
        self.assertEqual(self.c.post("/plant-hmi/realism/api/promote", headers=self.h).status_code, 409)  # chưa có bản tốt nhất
        loop_gate._write_best({"iter": 3, "eval_run": "x", "knobs": {"lop_gap_max": {"value": 1}}, "score": None, "ts": 0})
        self.assertEqual(self.c.post("/plant-hmi/realism/api/promote", headers=self.h).status_code, 200)
        self.assertEqual(knobs.resolve("production", use_env=False)["lop_gap_max"]["value"], 1)
        self.assertEqual(self.c.post("/plant-hmi/realism/api/reset-production", headers=self.h).status_code, 200)
        self.assertEqual(knobs.resolve("production", use_env=False)["lop_gap_max"]["value"], 0)
        self.assertEqual(self.c.post("/plant-hmi/realism/api/promote").status_code, 403)
        bad = {"origin": "http://evil.example", **self.h}
        self.assertEqual(self.c.put("/plant-hmi/realism/api/knobs", json={"changes": {"lop_gap_max": 1}}, headers=bad).status_code, 403)

    @mock.patch("plant_hmi.plant_realism_job_status.batch_running", return_value=False)
    @mock.patch("plant_hmi.plant_realism_routes.subprocess.run")
    def test_run_spawns_via_systemd_run_never_a_shell_string(self, mock_run, mock_batch):
        """Bước 1: the loop runs under `systemd-run --user`, never a bare Popen (so
        a tdm-backend restart cannot SIGKILL it, rule R8). argv is a list; the loop's
        own module+action/run-id show up as literal args, never shell-interpolated."""
        mock_run.return_value = mock.Mock(returncode=0, stdout="", stderr="")
        res = self.c.post("/plant-hmi/realism/api/run", json={"action": "cycle", "n_per_type": 5},
                          headers=self.h)
        self.assertEqual(res.status_code, 200)
        rid = res.json()["run_id"]
        self.assertEqual(res.json()["unit"], "tdm-realism-" + rid)
        argv = mock_run.call_args[0][0]
        self.assertIsInstance(argv, list)
        self.assertEqual(argv[0], "systemd-run")
        self.assertIn("--user", argv)
        self.assertIn(f"--unit=tdm-realism-{rid}", argv)
        self.assertIn("--service-type=exec", argv)
        self.assertIn("--collect", argv)
        self.assertIn("--expand-environment=no", argv)
        self.assertIn("-m", argv)
        self.assertIn("realism.loop", argv)
        self.assertIn("--run-id", argv)
        self.assertIn(rid, argv)

    @mock.patch("plant_hmi.plant_realism_routes.subprocess.run")
    def test_run_returns_500_when_systemd_run_fails(self, mock_run):
        mock_run.return_value = mock.Mock(returncode=1, stdout="", stderr="unit tên xấu")
        res = self.c.post("/plant-hmi/realism/api/run", json={"action": "evaluate"}, headers=self.h)
        self.assertEqual(res.status_code, 500)

    @mock.patch("plant_hmi.plant_realism_routes.job_status.unit_for", return_value="tdm-realism-fake")
    @mock.patch("plant_hmi.plant_realism_routes.job_status.job")
    @mock.patch("plant_hmi.plant_realism_routes.subprocess.run")
    def test_stop_sets_flag_first_then_escalates_to_systemctl_after_grace(self, mock_run, mock_job, mock_unit):
        from realism import loop
        mock_job.return_value = {"state": "running", "run_id": "loop-fake"}
        mock_run.return_value = mock.Mock(returncode=0, stdout="", stderr="")
        loop.STATE.mkdir(parents=True, exist_ok=True)
        loop.STOP.unlink(missing_ok=True)
        try:
            res1 = self.c.post("/plant-hmi/realism/api/stop", headers=self.h)
            self.assertEqual(res1.status_code, 200)
            self.assertTrue(res1.json()["stopping"])
            mock_run.assert_not_called()  # first call: just the flag, no escalation yet
            with mock.patch("plant_hmi.plant_realism_routes.time.time",
                            return_value=loop.STOP.stat().st_mtime + 60):
                res2 = self.c.post("/plant-hmi/realism/api/stop", headers=self.h)
            self.assertEqual(res2.status_code, 200)
            self.assertEqual(res2.json()["escalated_unit"], "tdm-realism-fake")
            mock_run.assert_called_once()
            self.assertEqual(mock_run.call_args[0][0][:3], ["systemctl", "--user", "stop"])
        finally:
            loop.STOP.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
