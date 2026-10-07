"""Thử pha 3 (đề xuất núm theo ma trận độ nhạy): `realism/sensitivity_propose.py`.

Không ghi vào `realism/state` thật: mọi test tự dựng result/sens giả, không đọc đĩa trừ test đọc tệp
(patch `SENS_PATH` vào thư mục tạm). Không gọi GPU, không gọi ComfyUI.

Run: .venv/bin/python tests/test-realism-sensitivity-propose.py
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from realism import issues, knobs, sensitivity_propose as sp  # noqa: E402

# Các test ở đây là hành vi thước CŨ (v1): cô lập khỏi realism/state/best.json thật. Khi bản tốt nhất thật chuyển sang
# thước v2 (6/10), propose() trả "none" nên test đọc trạng thái thật sẽ hỏng oan.
from unittest import mock as _mock  # noqa: E402
from realism import loop_gate as _lg  # noqa: E402
_BEST_PATCH = _mock.patch.object(_lg, "read_best", return_value=None)


def setUpModule():
    _BEST_PATCH.start()


def tearDownModule():
    _BEST_PATCH.stop()

DEFAULTS = dict(knobs.DEFAULTS)


def _c(syn_med=1.0, real_med=1.0, auc=0.5, syn_iqr=(0.5, 1.5), syn_lt45=0.4):
    return {"syn_med": syn_med, "real_med": real_med, "auc": auc, "syn_iqr": list(syn_iqr), "syn_lt45": syn_lt45}


# Mỗi cặp loại một bộ tiêu chí mặc định ĐẠT mọi mục tiêu issues.py liên quan tới nó; test chỉ cần ghi đè
# đúng trường muốn làm trượt (overrides), các mục tiêu khác giữ nguyên để không rối phép thử "đang đạt".
BASE_CRIT = {
    "CR↔crack": {"bien_doc": _c(), "bien_daodong": _c(), "vung_huong": _c(syn_lt45=0.4),
                 "vung_dac": _c(syn_med=0.8), "vung_dayhop": _c(syn_med=0.5), "vung_lechtam": _c(auc=0.5)},
    "PO↔porosity": {"bien_doc": _c(), "bien_daodong": _c(), "vung_huong": _c(auc=0.5),
                    "vung_dac": _c(auc=0.5), "vung_dayhop": _c(), "vung_lechtam": _c(syn_med=0.8)},
    "LP↔lack_of_penetration": {"bien_doc": _c(), "bien_daodong": _c(), "vung_huong": _c(syn_iqr=(80, 90)),
                               "vung_dac": _c(syn_med=0.6), "vung_dayhop": _c(syn_med=0.6), "vung_lechtam": _c()},
}


def _result(overrides=None, hit=0.9):
    """overrides: {(cặp, tiêu chí, trường): giá trị}. Mặc định mọi mục tiêu ĐẠT; dùng overrides để làm trượt
    đúng mục tiêu test cần."""
    pairs = []
    for pair, tmpl in BASE_CRIT.items():
        crit = json.loads(json.dumps(tmpl))
        for (p, k, f), v in (overrides or {}).items():
            if p == pair:
                crit[k][f] = v
        pairs.append({"pair": pair, "hit": hit, "crit": crit})
    return {"pairs": pairs}


def _label(pair, crit):
    return next(t["label"] for iss in issues.ISSUES for t in iss["targets"]
                if t["pair"] == pair and t["crit"] == crit)


def _variant(vid, group, changed, mode="generate"):
    return {"id": vid, "group": group, "sign": 1, "mode": mode, "types": [],
            "knobs": {}, "changed": {k: list(v) for k, v in changed.items()}, "eval_run": f"run-{vid}"}


def _effect(delta, significant=True):
    return {"pair": None, "crit": None, "stat": None, "label": None, "prev": None, "new": None,
            "n_common": 20, "delta": delta, "ci_low": None, "ci_high": None, "significant": significant}


def _sens(base_knobs, variants, effects_by_variant, run_id="sens-test"):
    effects = {vid: {"targets": targets, "c2st": {}} for vid, targets in effects_by_variant.items()}
    return {"run_id": run_id, "finished": True, "n_per_type": 20, "base_knobs": dict(base_knobs),
            "base_eval_run": "base-run", "variants": variants, "effects": effects}


class PicksSignificantRightDirectionKnob(unittest.TestCase):
    def test_single_candidate_used(self):
        cur = {**DEFAULTS, "crack_transverse_share": 0.05}             # núm đã lệch mặc định: không nhảy luật cũ
        result = _result({("CR↔crack", "vung_huong", "syn_lt45"): 0.05})
        label = _label("CR↔crack", "vung_huong")
        variant = _variant("crack_transverse_share+", "crack_transverse_share",
                            {"crack_transverse_share": (0.05, 0.35)})
        sens = _sens(cur, [variant], {"crack_transverse_share+": {label: _effect(0.3)}})

        new, why, mode = sp.propose(result, cur, sens)

        self.assertEqual(mode, "data")
        self.assertAlmostEqual(new["crack_transverse_share"], 0.2625, places=3)   # 0,05 + 0,7083×0,3
        self.assertTrue(any("crack_transverse_share+" in w for w in why))


class LambdaClamping(unittest.TestCase):
    def _once(self, delta):
        cur = {**DEFAULTS, "crack_transverse_share": 0.05}
        result = _result({("CR↔crack", "vung_huong", "syn_lt45"): 0.05})   # cần ≈ 0,2125
        label = _label("CR↔crack", "vung_huong")
        variant = _variant("v+", "crack_transverse_share", {"crack_transverse_share": (0.05, 0.35)})
        sens = _sens(cur, [variant], {"v+": {label: _effect(delta)}})
        new, _why, _mode = sp.propose(result, cur, sens)
        return new["crack_transverse_share"]

    def test_clamped_to_upper_bound(self):
        self.assertAlmostEqual(self._once(0.02), 0.05 + 2.0 * 0.3)       # raw λ=10,6 → kẹp 2,0

    def test_clamped_to_lower_bound(self):
        self.assertAlmostEqual(self._once(2.0), 0.05 + 0.5 * 0.3)        # raw λ=0,106 → kẹp 0,5


class RejectsCandidateBreakingPassingTarget(unittest.TestCase):
    def test_second_candidate_chosen_when_first_breaks_a_passing_target(self):
        cur = {**DEFAULTS, "crack_transverse_share": 0.05}
        result = _result({("CR↔crack", "vung_huong", "syn_lt45"): 0.05})
        x_label = _label("CR↔crack", "vung_huong")
        y_label = _label("CR↔crack", "vung_dac")                        # đang đạt (mặc định syn_med=0,8 ≥ 0,65)
        bad = _variant("crack_widen_px+", "crack_widen_px", {"crack_widen_px": (0.0, 2.0)})
        good = _variant("crack_transverse_share+", "crack_transverse_share",
                         {"crack_transverse_share": (0.05, 0.35)})
        sens = _sens(cur, [bad, good], {
            "crack_widen_px+": {x_label: _effect(0.3), y_label: _effect(-0.3)},   # kéo Độ đặc xuống 0,5 < 0,65
            "crack_transverse_share+": {x_label: _effect(0.3)},                  # không chạm Độ đặc
        })

        new, why, mode = sp.propose(result, cur, sens)

        self.assertEqual(mode, "data")
        self.assertEqual(new["crack_widen_px"], DEFAULTS["crack_widen_px"])      # ứng viên xấu bị loại
        self.assertAlmostEqual(new["crack_transverse_share"], 0.2625, places=3)
        self.assertTrue(any("crack_transverse_share+" in w for w in why))


class NoCandidateMessage(unittest.TestCase):
    def test_message_when_no_significant_effect_available(self):
        cur = {**DEFAULTS, "crack_transverse_share": 0.05}
        result = _result({("CR↔crack", "vung_huong", "syn_lt45"): 0.05})
        label = _label("CR↔crack", "vung_huong")
        variant = _variant("v+", "crack_transverse_share", {"crack_transverse_share": (0.05, 0.35)})
        sens = _sens(cur, [variant], {"v+": {label: _effect(0.3, significant=False)}})

        new, why, mode = sp.propose(result, cur, sens)

        self.assertEqual(mode, "data")
        self.assertEqual(new["crack_transverse_share"], cur["crack_transverse_share"])
        self.assertTrue(any("chưa có núm nào đẩy được" in w and "sens-test" in w for w in why))


class StaleBaseFallsBackToRules(unittest.TestCase):
    def test_mismatch_falls_back_with_note(self):
        cur = {**DEFAULTS, "crack_transverse_share": 0.3}
        result = _result({("CR↔crack", "vung_huong", "syn_lt45"): 0.01})
        sens = _sens({**DEFAULTS, "crack_transverse_share": 0.1}, [], {}, run_id="sens-stale")   # điểm gốc khác cur

        new, why, mode = sp.propose(result, cur, sens)
        expected_new, expected_why = issues.propose(result, cur)

        self.assertEqual(mode, "stale")
        self.assertEqual(new, expected_new)
        self.assertTrue(set(expected_why) <= set(why))
        self.assertTrue(any("độ nhạy đã cũ" in w and "sens-stale" in w for w in why))


class NoSensitivityFileFallsBackToRules(unittest.TestCase):
    def test_none_sens_identical_to_old_behavior(self):
        cur = {**DEFAULTS, "crack_transverse_share": 0.3}
        result = _result({("CR↔crack", "vung_huong", "syn_lt45"): 0.01})

        new, why, mode = sp.propose(result, cur, None)
        expected_new, expected_why = issues.propose(result, cur)

        self.assertEqual(mode, "none")
        self.assertEqual(new, expected_new)
        self.assertTrue(set(expected_why) <= set(why))
        self.assertTrue(any("chưa có số đo độ nhạy" in w for w in why))

    def test_read_sensitivity_missing_file_returns_none(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(sp.read_sensitivity(Path(d) / "khong-ton-tai.json"))

    def test_read_sensitivity_invalid_json_returns_none(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "sensitivity.json"
            p.write_text("{ không hợp lệ", encoding="utf-8")
            self.assertIsNone(sp.read_sensitivity(p))


class PreRuleAtDefaults(unittest.TestCase):
    def test_default_knobs_jump_to_suggested_fix_without_sensitivity_search(self):
        cur = dict(DEFAULTS)                                            # mọi núm còn mặc định
        result = _result({("CR↔crack", "vung_huong", "syn_lt45"): 0.01})
        sens = _sens(cur, [], {})                                       # không ứng viên nào, vẫn phải qua được

        new, why, mode = sp.propose(result, cur, sens)

        self.assertEqual(mode, "data")
        self.assertEqual(new["crack_transverse_share"], knobs.REGISTRY["crack_transverse_share"][5])
        self.assertEqual(new["crack_widen_px"], knobs.REGISTRY["crack_widen_px"][5])
        self.assertTrue(any("núm còn ở mặc định" in w for w in why))


class IntKnobRoundedAndBoundsClamped(unittest.TestCase):
    def test_lop_gap_max_rounded_and_clamped_to_registry_max(self):
        cur = {**DEFAULTS, "lop_tilt_max_deg": 1.0}                     # lệch mặc định: tránh pre-rule vấn đề 4
        result = _result({("LP↔lack_of_penetration", "vung_dayhop", "syn_med"): 0.3})   # < 0,50: trượt phía dưới
        label = _label("LP↔lack_of_penetration", "vung_dayhop")
        variant = _variant("lop_gap_max+", "lop_gap_max", {"lop_gap_max": (0.0, 10.0)})  # vượt xa biên đăng ký (0..5)
        sens = _sens(cur, [variant], {"lop_gap_max+": {label: _effect(0.211)}})          # λ≈1,0

        new, _why, mode = sp.propose(result, cur, sens)

        self.assertEqual(mode, "data")
        self.assertEqual(new["lop_gap_max"], 5)                          # kẹp biên trên, vẫn là int
        self.assertIsInstance(new["lop_gap_max"], int)


class MinMaxPairSwappedWhenCrossed(unittest.TestCase):
    def test_post_depth_min_exceeding_max_is_swapped(self):
        cur = {**DEFAULTS, "post_depth_min": 0.3, "post_depth_max": 0.5}  # lệch mặc định: tránh pre-rule vấn đề 1
        result = _result({("CR↔crack", "bien_daodong", "auc"): 0.1})     # trượt phía dưới (cần ≥0,35)
        label = _label("CR↔crack", "bien_daodong")
        variant = _variant("post_depth_min+", "post_depth_min_push", {"post_depth_min": (0.3, 0.9)})
        sens = _sens(cur, [variant], {"post_depth_min+": {label: _effect(0.2675)}})       # λ≈1,0

        new, _why, mode = sp.propose(result, cur, sens)

        self.assertEqual(mode, "data")
        self.assertAlmostEqual(new["post_depth_min"], 0.5)                # 0,9 và 0,5 bị đổi chỗ
        self.assertAlmostEqual(new["post_depth_max"], 0.9)


class TwoVariantsSameGroupChooseMatchingSign(unittest.TestCase):
    def test_opposite_sign_variant_is_filtered_out(self):
        cur = {**DEFAULTS, "post_depth_min": 0.5, "post_depth_max": 0.7}
        result = _result({("CR↔crack", "bien_doc", "syn_med"): 3.0})     # ratio 3,0 > 1,5: cần GIẢM
        label = _label("CR↔crack", "bien_doc")
        plus = _variant("post_depth+", "post_depth", {"post_depth_min": (0.5, 0.6), "post_depth_max": (0.7, 0.8)})
        minus = _variant("post_depth-", "post_depth", {"post_depth_min": (0.5, 0.4), "post_depth_max": (0.7, 0.6)})
        sens = _sens(cur, [plus, minus], {
            "post_depth+": {label: _effect(0.5)},     # cùng chiều dương: sai hướng (cần âm)
            "post_depth-": {label: _effect(-1.575)},   # λ≈1,0, đúng hướng
        })

        new, why, mode = sp.propose(result, cur, sens)

        self.assertEqual(mode, "data")
        self.assertTrue(any("post_depth-" in w for w in why))
        self.assertFalse(any("post_depth+" in w for w in why))
        self.assertAlmostEqual(new["post_depth_min"], 0.4)
        self.assertAlmostEqual(new["post_depth_max"], 0.6)


class CombinedPredictionIsAdditive(unittest.TestCase):
    def test_predict_sums_lambda_times_delta_across_moves(self):
        result = _result({("CR↔crack", "vung_huong", "syn_lt45"): 0.05})
        label = _label("CR↔crack", "vung_huong")
        other_label = _label("CR↔crack", "vung_dac")                     # biến thể 2 không chạm mục tiêu này
        v1 = _variant("v1", "g1", {"crack_transverse_share": (0.05, 0.35)})
        v2 = _variant("v2", "g2", {"crack_widen_px": (0.0, 2.0)})
        sens = _sens({}, [v1, v2], {"v1": {label: _effect(0.3)}, "v2": {label: _effect(0.2)}})

        pred = sp.predict(result, sens, [(v1, 0.5), (v2, 1.5)])

        self.assertAlmostEqual(pred[label], 0.05 + 0.5 * 0.3 + 1.5 * 0.2)
        self.assertAlmostEqual(pred[other_label], 0.8)                   # biến thể không chạm: giữ nguyên đo


class ReviewFixes(unittest.TestCase):
    """Ba lỗi review bước 4: H2 cộng dồn bước cho mục tiêu đã dự báo đạt, H3 làm tệ thêm mục tiêu đang trượt,
    M1 sàn λ đẩy mục tiêu "between" vượt sang phía bên kia."""
    CUR = {**DEFAULTS, "post_depth_min": 0.45, "post_depth_max": 0.65, "pore_aspect_min": 1.2,
           "pore_aspect_max": 1.2}

    def test_h2_no_extra_step_when_already_predicted_to_pass(self):
        result = _result({("CR↔crack", "bien_doc", "syn_med"): 2.0, ("PO↔porosity", "bien_doc", "syn_med"): 2.0})
        a, b = _label("CR↔crack", "bien_doc"), _label("PO↔porosity", "bien_doc")
        v1 = _variant("post_edge_blur_sigma+", "post_edge_blur_sigma", {"post_edge_blur_sigma": (2.0, 2.75)}, "replay")
        v2 = _variant("post_modulation+", "post_modulation", {"post_modulation": (0.0, 0.15)}, "replay")
        sens = _sens(self.CUR, [v1, v2], {"post_edge_blur_sigma+": {a: _effect(-0.6), b: _effect(-0.6)},
                                           "post_modulation+": {b: _effect(-0.6)}})
        new, why, _ = sp.propose(result, self.CUR, sens)
        self.assertEqual(new["post_modulation"], self.CUR["post_modulation"])     # không vặn thêm cho b
        self.assertTrue(any(w.startswith(b) and "dự báo đạt" in w for w in why))

    def test_h3_rejects_step_that_worsens_a_failing_hit_rate(self):
        result = _result({("CR↔crack", "bien_doc", "syn_med"): 2.0}, hit=0.6)    # chạm lỗi đang trượt
        a, hit = _label("CR↔crack", "bien_doc"), _label("CR↔crack", "_hit")
        shallow = _variant("post_depth-", "post_depth", {"post_depth_min": (0.45, 0.35), "post_depth_max": (0.65, 0.55)},
                           "replay")
        blur = _variant("post_edge_blur_sigma+", "post_edge_blur_sigma", {"post_edge_blur_sigma": (2.0, 2.75)}, "replay")
        sens = _sens(self.CUR, [shallow, blur], {"post_depth-": {a: _effect(-0.8), hit: _effect(-0.2)},
                                                  "post_edge_blur_sigma+": {a: _effect(-0.6)}})
        new, why, _ = sp.propose(result, self.CUR, sens)
        self.assertEqual(new["post_depth_min"], self.CUR["post_depth_min"])      # không làm tối nông thêm
        self.assertGreater(new["post_edge_blur_sigma"], self.CUR["post_edge_blur_sigma"])

    def test_m1_between_overshoot_rejected(self):
        result = _result({("PO↔porosity", "vung_lechtam", "syn_med"): 0.70})       # cần vào [0,72; 0,90]
        lab = _label("PO↔porosity", "vung_lechtam")
        v = _variant("pore_aspect+", "pore_aspect", {"pore_aspect_min": (1.2, 1.7), "pore_aspect_max": (1.2, 1.7)})
        sens = _sens(self.CUR, [v], {"pore_aspect+": {lab: _effect(0.5)}})        # λ sàn 0,5 → 0,95: vượt khoảng
        new, why, _ = sp.propose(result, self.CUR, sens)
        self.assertEqual(new["pore_aspect_min"], self.CUR["pore_aspect_min"])
        self.assertTrue(any(w.startswith(lab) and "làm hỏng" in w for w in why))

    def test_noise_on_other_failing_target_does_not_veto(self):
        """Hiệu ứng KHÔNG ý nghĩa lên một mục tiêu đang trượt khác không được chặn bước có ích (đo đủ 2/10)."""
        result = _result({("CR↔crack", "bien_doc", "syn_med"): 2.0}, hit=0.6)
        a, hit = _label("CR↔crack", "bien_doc"), _label("CR↔crack", "_hit")
        blur = _variant("post_edge_blur_sigma+", "post_edge_blur_sigma", {"post_edge_blur_sigma": (2.0, 2.75)}, "replay")
        sens = _sens(self.CUR, [blur], {"post_edge_blur_sigma+": {a: _effect(-0.6), hit: _effect(-0.05, False)}})
        new, _, _ = sp.propose(result, self.CUR, sens)
        self.assertGreater(new["post_edge_blur_sigma"], self.CUR["post_edge_blur_sigma"])

    def test_pre_rule_defers_to_measured_knobs(self):
        """Vấn đề 4 còn ở mặc định nhưng núm đã đo, không có hiệu ứng ý nghĩa → không nhảy giá trị sửa (2/10)."""
        cur = {**self.CUR}
        result = _result({("LP↔lack_of_penetration", "vung_huong", "syn_iqr"): (89.5, 90.0)})
        lab = _label("LP↔lack_of_penetration", "vung_huong")
        v = _variant("lop_tilt_max_deg+", "lop_tilt_max_deg", {"lop_tilt_max_deg": (0.0, 3.0)})
        sens = _sens(cur, [v], {"lop_tilt_max_deg+": {lab: _effect(-1.7, False)}})
        new, why, _ = sp.propose(result, cur, sens)
        self.assertEqual(new["lop_tilt_max_deg"], 0.0)
        self.assertTrue(any(w.startswith(lab) and "chưa có núm" in w for w in why))


if __name__ == "__main__":
    unittest.main(verbosity=2)
