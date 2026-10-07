"""Thử bước 4: hậu móc lưu ảnh trước-làm-tối (REALISM_SAVE_PREDARKEN), replay CPU trùng điểm ảnh với
apply_dark_defect_convention, ghép hiệu ứng biến thể/lượt gốc (effects schema), chọn biến thể cho pilot,
và do_screen không ghi bản PV sản xuất khi pilot.

Run: .venv/bin/python3 tests/test-realism-sensitivity-screen.py
"""
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
from PIL import Image

PIPELINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPELINE))

from realism import knobs, predarken_replay, sensitivity_groups  # noqa: E402
from realism import sensitivity_screen, sensitivity_screen_effects as effects_mod  # noqa: E402
from realism import sensitivity_screen_gen as gen  # noqa: E402
from realism.loop_common import GpuBusy, Stopped  # noqa: E402


def _load_batch_main():
    """batch-production-main.py (tên gạch nối) không import được bằng tên module thường."""
    spec = importlib.util.spec_from_file_location("bpm", PIPELINE / "batch_manager" / "batch-production-main.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class KnobDir(unittest.TestCase):
    """Cô lập kho núm + biến môi trường, không đụng realism/state thật (giống tests/test-realism-loop.py)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.p = [mock.patch.object(knobs, "STATE_DIR", Path(self.tmp.name)),
                  mock.patch.dict(os.environ, {}, clear=False)]
        for p in self.p:
            p.start()
        os.environ.pop("REALISM_KNOBS", None)
        os.environ.pop(knobs.FROZEN_ENV, None)
        os.environ.pop("REALISM_SAVE_PREDARKEN", None)

    def tearDown(self):
        for p in reversed(self.p):
            p.stop()
        self.tmp.cleanup()

    def freeze(self, vals):
        os.environ[knobs.FROZEN_ENV] = json.dumps({k: {"value": v, "source": "LOCAL"} for k, v in vals.items()})


def _make_case(tmp_dir, defect_type, job_id, size=64, seed=0):
    """Dựng một ca giả: ảnh "SD vẽ xong bước 1" (img), nền, mặt nạ, chạy apply_dark_defect_convention thật
    (REALISM_SAVE_PREDARKEN=1) để có cả ảnh ra lẫn .npz, giống batch-production-main.py sinh ra."""
    rng = np.random.default_rng(seed)
    type_dir = Path(tmp_dir) / defect_type
    type_dir.mkdir(parents=True, exist_ok=True)
    name = f"{defect_type}_{job_id:06d}"

    bg = (120 + rng.normal(0, 5, (size, size))).clip(0, 255).astype(np.uint8)
    img = bg.copy()
    mask = np.zeros((size, size), np.uint8)
    mask[20:40, 10:50] = 255
    img[mask > 0] = np.clip(img[mask > 0].astype(int) + 60, 0, 255).astype(np.uint8)  # LoRA vẽ lỗi sáng

    bg_path, mask_path, img_path = type_dir / f"{name}_bg.png", type_dir / f"{name}_mask.png", type_dir / f"{name}.png"
    Image.fromarray(bg, mode="L").save(bg_path)
    Image.fromarray(mask, mode="L").save(mask_path)
    Image.fromarray(img, mode="L").save(img_path)
    (type_dir / f"{name}.json").write_text(json.dumps({"job_id": job_id}), encoding="utf-8")
    return img_path, mask_path, bg_path


class PredarkenHookReplayTest(KnobDir):
    """Pha 1: nghiệm thu bắt buộc, replay núm gốc ra ảnh TRÙNG TỪNG ĐIỂM ẢNH với ảnh lượt gốc."""

    def _run_production(self, defect_type="crack"):
        """Thư mục tạm KHÔNG tự xoá khi hàm trả về (dọn qua addCleanup): caller còn cần đọc lại file ra."""
        bpm = _load_batch_main()
        src = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, src, True)
        img_path, mask_path, bg_path = _make_case(src, defect_type, 1)
        with mock.patch.dict(os.environ, {"REALISM_SAVE_PREDARKEN": "1"}):
            bpm.apply_dark_defect_convention(img_path, str(mask_path), str(bg_path), defect_type=defect_type)
        produced = np.asarray(Image.open(img_path))
        npz_path = img_path.with_name(img_path.stem + "_predarken.npz")
        self.assertTrue(npz_path.exists())
        return src, produced

    def test_default_knobs_replay_matches_production_pixel_exact(self):
        src, produced = self._run_production("crack")
        with tempfile.TemporaryDirectory() as dst:
            base_knobs = {k: s[4] for k, s in knobs.REGISTRY.items()}  # mặc định = hành vi cũ
            predarken_replay.replay(src, dst, base_knobs, ["crack"])
            replayed = np.asarray(Image.open(Path(dst) / "crack" / "crack_000001.png"))
        np.testing.assert_array_equal(replayed, produced)

    def test_non_default_knobs_replay_matches_production_pixel_exact(self):
        custom = {k: s[4] for k, s in knobs.REGISTRY.items()}
        custom.update(post_depth_min=0.5, post_depth_max=0.7, post_modulation=0.4, post_edge_blur_sigma=3.5)
        self.freeze(custom)
        src, produced = self._run_production("crack")
        with tempfile.TemporaryDirectory() as dst:
            predarken_replay.replay(src, dst, custom, ["crack"])
            replayed = np.asarray(Image.open(Path(dst) / "crack" / "crack_000001.png"))
        np.testing.assert_array_equal(replayed, produced)

    def test_no_env_is_byte_identical_to_old_behaviour(self):
        """Không bật REALISM_SAVE_PREDARKEN: không lưu .npz, ảnh ra không đổi so với trước khi có hook."""
        bpm = _load_batch_main()
        with tempfile.TemporaryDirectory() as src:
            img_path, mask_path, bg_path = _make_case(src, "crack", 2)
            before = np.asarray(Image.open(img_path)).copy()
            bpm.apply_dark_defect_convention(img_path, str(mask_path), str(bg_path), defect_type="crack")
            after_no_env = np.asarray(Image.open(img_path)).copy()
            npz_path = img_path.with_name(img_path.stem + "_predarken.npz")
            self.assertFalse(npz_path.exists())
        self.assertFalse(np.array_equal(before, after_no_env))  # đã bị làm tối (khác ảnh gốc)

    def test_predarken_replay_copies_mask_json_and_fixed_jobs_and_writes_pv(self):
        src, _ = self._run_production("porosity")
        (Path(src) / "fixed-jobs.json").write_text(json.dumps([{"case_id": "porosity-000"}]), encoding="utf-8")
        with tempfile.TemporaryDirectory() as dst:
            predarken_replay.replay(src, dst, {k: s[4] for k, s in knobs.REGISTRY.items()}, ["porosity"])
            dst = Path(dst)
            self.assertTrue((dst / "porosity" / "porosity_000001_mask.png").exists())
            self.assertTrue((dst / "porosity" / "porosity_000001.json").exists())
            self.assertTrue((dst / "fixed-jobs.json").exists())
            pv = json.loads((dst / knobs.PV_NAME).read_text(encoding="utf-8"))
            self.assertIn("ts", pv)
            self.assertEqual(pv["knobs"]["post_depth_min"]["source"], "LOCAL")

    def test_metallic_inclusion_never_saves_predarken(self):
        """skip_darkening trả về sớm trước khi tới hook: không npz dù có bật env."""
        bpm = _load_batch_main()
        with tempfile.TemporaryDirectory() as src:
            img_path, mask_path, bg_path = _make_case(src, "metallic_inclusion", 3)
            with mock.patch.dict(os.environ, {"REALISM_SAVE_PREDARKEN": "1"}):
                bpm.apply_dark_defect_convention(img_path, str(mask_path), str(bg_path), defect_type="metallic_inclusion")
            self.assertFalse(img_path.with_name(img_path.stem + "_predarken.npz").exists())


class SensitivityEffectsTest(unittest.TestCase):
    """Ghép hiệu ứng biến thể/lượt gốc trên kết quả giả, lọc theo loại biến thể chạm tới."""

    @staticmethod
    def _result(pair, kind, values):
        cases = [{"case_id": f"{kind}-{i:03d}", "pair": pair, "kind": kind, "hit": 1.0,
                  **{k: float(v) for k in ("vung_dac", "vung_huong", "bien_daodong", "vung_lechtam", "vung_dayhop",
                                            "bien_doc")}}
                 for i, v in enumerate(values)]
        return {"pairs": [{"pair": pair, "crit": {}, "hit": 1.0, "c2st": 0.6}], "cases": cases}

    def test_schema_and_type_filter(self):
        rng = np.random.default_rng(0)
        base = self._result("CR↔crack", "crack", rng.normal(0.6, 0.02, 40))
        var = self._result("CR↔crack", "crack", rng.normal(0.9, 0.02, 40))
        out = effects_mod.assemble_effects(base, var, ["crack"])
        self.assertIn("targets", out)
        self.assertIn("c2st", out)
        self.assertTrue(out["targets"])
        for label, e in out["targets"].items():
            self.assertEqual(effects_mod.TYPE_OF_PAIR[e["pair"]], "crack")
        self.assertIn("CR↔crack", out["c2st"])
        self.assertEqual(out["c2st"]["CR↔crack"]["base"], 0.6)
        # Biến thể không chạm loại porosity: không mục tiêu/c2st nào của PO↔porosity lọt qua
        self.assertNotIn("PO↔porosity", out["c2st"])

    def test_empty_results_still_have_schema_keys(self):
        out = effects_mod.assemble_effects({"pairs": [], "cases": []}, {"pairs": [], "cases": []}, ["crack"])
        self.assertEqual(set(out), {"targets", "c2st"})


class PickVariantsTest(unittest.TestCase):
    def test_pilot_keeps_only_replay_and_controlnet_plus(self):
        base = {k: s[4] for k, s in knobs.REGISTRY.items()}
        out = sensitivity_screen.pick_variants(base, None, pilot=True)
        ids = {v[0] for v in out}
        self.assertIn("controlnet_strength+", ids)
        self.assertNotIn("controlnet_strength-", ids)
        self.assertNotIn("crack_widen_px+", ids)
        for vid, group, sign, _ in out:
            self.assertTrue(sensitivity_groups.GROUPS[group]["mode"] == "replay" or vid == "controlnet_strength+")

    def test_groups_filter_restricts_to_named_groups(self):
        # post_edge_blur_sigma: mặc định 2.0 nằm GIỮA [1.0, 5.0], cả hai phía đều hợp lệ (khác post_depth,
        # mặc định 1.0 nằm sát biên trên nên phía "+" bị kẹp về chính nó và loại bỏ).
        base = {k: s[4] for k, s in knobs.REGISTRY.items()}
        out = sensitivity_screen.pick_variants(base, ["post_edge_blur_sigma"], pilot=False)
        self.assertEqual({v[1] for v in out}, {"post_edge_blur_sigma"})
        self.assertEqual(len(out), 2)  # two_sided


class GenHelpersTest(unittest.TestCase):
    def test_sanitize_plus_minus(self):
        self.assertEqual(gen.sanitize("controlnet_strength+"), "controlnet_strengthp")
        self.assertEqual(gen.sanitize("post_depth-"), "post_depthm")

    def test_clamp_n_builds_exam_set_and_clamps(self):
        with tempfile.TemporaryDirectory() as tmp:
            bg = Path(tmp) / "bg"
            bg.mkdir()
            for i in range(3):
                Image.new("L", (4, 4)).save(bg / f"bg{i}.png")
            exam_path = Path(tmp) / "exam.json"
            with mock.patch("realism.exam_set.EXAM_SET_PATH", exam_path), \
                 mock.patch("realism.exam_set.STATE", Path(tmp)), \
                 mock.patch("realism.sensitivity_screen_gen.PIPELINE", Path(tmp)):
                cfg_dir = Path(tmp) / "config"
                cfg_dir.mkdir()
                (cfg_dir / "batch-config.yaml").write_text(
                    f"paths:\n  backgrounds_dir: {bg}\ncomfyui:\n  host: x\n  port: 1\n", encoding="utf-8")
                n = gen.clamp_n(999)
                n_small = gen.clamp_n(5)
        self.assertEqual(n, 40)  # kẹp về per_type mặc định của bộ đề thi (exam_set.DEFAULT_PER_TYPE)
        self.assertEqual(n_small, 5)


class DoScreenPilotSkipsProductionCopyTest(unittest.TestCase):
    """do_screen: pilot không ghi realism/state/sensitivity.json; chạy đủ (không pilot, mọi biến thể
    qua được) thì ghi. Mọi phần nặng (sinh GPU, evaluate thật) bị thế bằng hàm giả — chỉ kiểm luồng
    điều khiển của sensitivity_screen.py, không chạy batch/ComfyUI thật."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state_dir = Path(self.tmp.name) / "state"
        self.runs_dir = Path(self.tmp.name) / "runs"
        patches = [
            mock.patch.object(sensitivity_screen, "STATE", self.state_dir),
            mock.patch("realism.runlog.RUNS_DIR", self.runs_dir),
            mock.patch.object(sensitivity_screen, "_generate_base", lambda *a, **k: None),
            mock.patch.object(sensitivity_screen, "_generate_variant", lambda *a, **k: None),
            mock.patch.object(sensitivity_screen, "_self_check_replay", lambda *a, **k: {"n": 8, "max_diff": 0}),
            mock.patch.object(predarken_replay, "replay", lambda *a, **k: None),
            mock.patch.object(sensitivity_screen, "evaluate", mock.Mock(
                run=lambda source, run_id, scale=2, workers=32, log=None: {"run_id": run_id, "pairs": [], "cases": []})),
            mock.patch.object(gen, "clamp_n", lambda n: n),
            mock.patch("plant_hmi.plant_gpu_lease.acquire", return_value=(True, None)),
            mock.patch("plant_hmi.plant_gpu_lease.release"),
        ]
        knobs_state_patch = mock.patch.object(knobs, "STATE_DIR", Path(self.tmp.name) / "knobs-state")
        patches.append(knobs_state_patch)
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def test_pilot_true_skips_state_write(self):
        result = sensitivity_screen.do_screen("sens-test-pilot", n_per_type=4,
                                              groups_filter=["post_edge_blur_sigma"], pilot=True)
        self.assertEqual(result["finished"], True)
        self.assertEqual(result["pilot"], True)
        self.assertFalse((self.state_dir / "sensitivity.json").exists())

    def test_full_run_writes_state_file(self):
        result = sensitivity_screen.do_screen("sens-test-full", n_per_type=4,
                                              groups_filter=["post_edge_blur_sigma"], pilot=False)
        self.assertTrue((self.state_dir / "sensitivity.json").exists())
        written = json.loads((self.state_dir / "sensitivity.json").read_text(encoding="utf-8"))
        self.assertEqual(written["run_id"], "sens-test-full")
        self.assertEqual(set(result), {"run_id", "finished", "pilot", "n_per_type", "base_knobs", "base_eval_run",
                                        "variants", "effects", "replay_check"})
        self.assertEqual(len(result["variants"]), 2)  # post_edge_blur_sigma: two_sided

    def test_variant_failure_is_recorded_and_others_continue(self):
        calls = {"n": 0}

        def flaky_replay(*a, **k):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("boom")

        with mock.patch.object(predarken_replay, "replay", flaky_replay):
            result = sensitivity_screen.do_screen("sens-test-flaky", n_per_type=4,
                                                  groups_filter=["post_edge_blur_sigma"], pilot=True)
        self.assertEqual(len(result["variants"]), 1)  # một biến thể lỗi, một biến thể còn lại vẫn đo được
        self.assertFalse((self.state_dir / "sensitivity.json").exists())  # pilot: dù sao cũng không ghi


class DarkenKeyByCaseTest(KnobDir):
    """Khoá ngẫu nhiên làm tối theo CA (loại + seed), không theo tên tệp có số thứ tự job (lỗi thấy 2/10)."""

    def _darken(self, job_id, darken_key):
        bpm = _load_batch_main()
        src = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, src, True)
        img_path, mask_path, bg_path = _make_case(src, "porosity", job_id, seed=3)   # cùng nội dung, khác job_id
        bpm.apply_dark_defect_convention(img_path, str(mask_path), str(bg_path), defect_type="porosity",
                                         darken_key=darken_key)
        return np.asarray(Image.open(img_path))

    def test_same_case_different_job_index_identical(self):
        custom = {k: s[4] for k, s in knobs.REGISTRY.items()}
        custom.update(post_depth_min=0.4, post_depth_max=0.7, post_modulation=0.6)     # có rút ngẫu nhiên
        self.freeze(custom)
        a, b = self._darken(0, "porosity-123"), self._darken(20, "porosity-123")
        np.testing.assert_array_equal(a, b)
        c = self._darken(0, "porosity-124")
        self.assertGreater(int(np.abs(a.astype(int) - c.astype(int)).max()), 0)        # khác ca thì khác rút


if __name__ == "__main__":
    unittest.main(verbosity=2)
