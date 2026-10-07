"""Bước 5 (plan 261003): chỉ sinh lại loại bị núm đổi chạm tới, loại khác dùng lại số đo bản tốt nhất.
Không ghi realism/state thật: mọi đường dẫn trạng thái patch sang thư mục tạm, không gọi GPU.
Run: .venv/bin/python3 tests/test-realism-loop-partial.py
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from realism import knobs, loop, loop_partial  # noqa: E402

TYPES = ["crack", "porosity", "lack_of_penetration", "lack_of_fusion"]
BASE = dict(knobs.DEFAULTS)


class AffectedTypes(unittest.TestCase):
    def test_type_specific_knob_hits_only_owner(self):
        self.assertEqual(loop_partial.affected_types({**BASE, "crack_transverse_share": 0.3}, BASE, TYPES), ["crack"])
        self.assertEqual(loop_partial.affected_types({**BASE, "lop_tilt_max_deg": 3.0}, BASE, TYPES),
                         ["lack_of_penetration"])
        self.assertEqual(loop_partial.affected_types({**BASE, "pore_aspect_min": 1.3}, BASE, TYPES), ["porosity"])

    def test_common_knob_hits_all_selected(self):
        self.assertEqual(loop_partial.affected_types({**BASE, "post_edge_blur_sigma": 3.0}, BASE, TYPES), TYPES)
        self.assertEqual(loop_partial.affected_types({**BASE, "controlnet_strength": 0.7}, BASE, ["crack"]), ["crack"])

    def test_no_change_no_type_and_unselected_owner_ignored(self):
        self.assertEqual(loop_partial.affected_types(BASE, BASE, TYPES), [])
        self.assertEqual(loop_partial.affected_types({**BASE, "crack_widen_px": 2.0}, BASE, ["porosity"]), [])


class PlanCycle(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        src = Path(self.tmp.name) / "iter-07"
        src.mkdir()
        jobs = [{"case_id": f"{t}-{i:03d}", "defect_type": t} for t in TYPES[:3] for i in range(20)]   # thiếu LF
        (src / "fixed-jobs.json").write_text(json.dumps(jobs))
        best = {"iter": 7, "eval_run": "ev7", "knobs": {k: {"value": v} for k, v in BASE.items()}}
        hist = [{"iter": 7, "eval_run": "ev7", "source": str(src)}]
        self.p = [mock.patch.object(loop_partial.loop_gate, "read_best", return_value=best),
                  mock.patch.object(loop_partial, "history", return_value=hist)]
        for p in self.p:
            p.start()

    def tearDown(self):
        for p in self.p:
            p.stop()
        self.tmp.cleanup()

    def test_only_affected_plus_missing_types(self):
        gen, reused, best = loop_partial.plan_cycle({**BASE, "crack_transverse_share": 0.3}, TYPES, 20)
        self.assertEqual(gen, ["crack", "lack_of_fusion"])            # nứt bị ảnh hưởng, LF bản tốt nhất chưa có
        self.assertEqual(reused, ["porosity", "lack_of_penetration"])
        self.assertEqual(best["iter"], 7)

    def test_different_n_regenerates_all(self):
        gen, reused, _ = loop_partial.plan_cycle(BASE, TYPES, 10)
        self.assertEqual((gen, reused), (TYPES, []))

    def test_no_best_generates_all(self):
        with mock.patch.object(loop_partial.loop_gate, "read_best", return_value=None):
            self.assertEqual(loop_partial.plan_cycle(BASE, TYPES, 20)[:2], (TYPES, []))


class Merge(unittest.TestCase):
    def test_reused_types_taken_verbatim_from_best(self):
        new = {"run_id": "ev8", "knobs_pv": {"x": 1},
               "pairs": [{"pair": "CR↔crack", "synthetic": "crack", "c2st": 0.6}],
               "cases": [{"case_id": "crack-000", "kind": "crack", "pair": "CR↔crack"}]}
        best = {"pairs": [{"pair": "CR↔crack", "synthetic": "crack", "c2st": 0.7},
                          {"pair": "PO↔porosity", "synthetic": "porosity", "c2st": 0.8}],
                "cases": [{"case_id": "crack-000", "kind": "crack"}, {"case_id": "porosity-000", "kind": "porosity"}]}
        m = loop_partial.merge(new, best, ["porosity"], "ev7")
        self.assertEqual({p["pair"]: p["c2st"] for p in m["pairs"]}, {"CR↔crack": 0.6, "PO↔porosity": 0.8})
        self.assertEqual(sorted(c["case_id"] for c in m["cases"]), ["crack-000", "porosity-000"])
        self.assertEqual(m["reused"], {"from_eval_run": "ev7", "types": ["porosity"]})
        self.assertEqual((m["run_id"], m["knobs_pv"]), ("ev8", {"x": 1}))


class DoCycleGeneratesOnlyPlannedTypes(unittest.TestCase):
    def test_generate_called_with_gen_types_and_merge_applied(self):
        log = mock.Mock()
        best = {"iter": 7, "eval_run": "ev7"}
        with mock.patch.object(loop.loop_partial, "plan_cycle", return_value=(["crack"], ["porosity"], best)), \
                mock.patch.object(loop.loop_generate, "do_generate", return_value=(8, Path("/x"), "h:1", 20)) as gen, \
                mock.patch.object(loop, "do_evaluate", return_value={"all_pass": False}) as ev, \
                mock.patch.object(loop, "candidate", return_value=BASE), \
                mock.patch.object(loop.loop_generate, "clamp_n", return_value=20):
            loop.do_cycle(log, ["crack", "porosity"], 20)
        gen.assert_called_once_with(log, ["crack"], 20)
        extra, reuse = ev.call_args.args[3], ev.call_args.kwargs["reuse"]
        self.assertEqual((extra["generated_types"], extra["reused_types"], extra["types"]),
                         (["crack"], ["porosity"], ["crack", "porosity"]))
        self.assertEqual(reuse, (["porosity"], best))

    def test_skip_when_nothing_to_generate(self):
        log = mock.Mock()
        with mock.patch.object(loop.loop_partial, "plan_cycle", return_value=([], TYPES, {"iter": 7})), \
                mock.patch.object(loop.loop_generate, "do_generate") as gen, \
                mock.patch.object(loop, "history", return_value=[{"all_pass": False}]), \
                mock.patch.object(loop, "candidate", return_value=BASE), \
                mock.patch.object(loop.loop_generate, "clamp_n", return_value=20):
            rec = loop.do_cycle(log, TYPES, 20)
        gen.assert_not_called()
        self.assertEqual(rec["decision"], "skipped")


class CoverageCarriedThroughMerge(unittest.TestCase):
    def test_merged_coverage_keeps_reused_and_reads_new_source(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "fixed-jobs.json").write_text(json.dumps([{"defect_type": "crack"}] * 20))
            m = loop_partial.merge({"source": d, "pairs": [], "cases": []}, {"pairs": [], "cases": []},
                                   ["porosity"], "ev7", {"crack": 20, "porosity": 20, "lack_of_fusion": 20})
        self.assertEqual(m["coverage"], {"porosity": 20, "crack": 20})

    def test_plan_reads_coverage_from_merged_best(self):
        best = {"iter": 8, "eval_run": "ev8", "knobs": {k: {"value": v} for k, v in BASE.items()}}
        with mock.patch.object(loop_partial.loop_gate, "read_best", return_value=best), \
                mock.patch.object(loop_partial, "read_json", return_value={"coverage": {t: 20 for t in TYPES}}):
            gen, reused, _ = loop_partial.plan_cycle({**BASE, "lop_wave_amp_px": 1.0}, TYPES, 20)
        self.assertEqual(gen, ["lack_of_penetration"])


class CarryUnselectedTypes(unittest.TestCase):
    def _plan(self, cand, types, n):
        best = {"iter": 7, "eval_run": "ev7", "knobs": {k: {"value": v} for k, v in BASE.items()}}
        with mock.patch.object(loop_partial.loop_gate, "read_best", return_value=best), \
                mock.patch.object(loop_partial, "read_json", return_value={"coverage": {t: 20 for t in TYPES}}):
            return loop_partial.plan_cycle(cand, types, n)

    def test_porosity_only_round_carries_other_types(self):
        gen, reused, _ = self._plan({**BASE, "pore_aspect_min": 1.5}, ["porosity"], 40)
        self.assertEqual(gen, ["porosity"])
        self.assertEqual(reused, ["crack", "lack_of_penetration", "lack_of_fusion"])

    def test_common_knob_change_does_not_carry(self):
        gen, reused, _ = self._plan({**BASE, "post_edge_blur_sigma": 3.0}, ["porosity"], 40)
        self.assertEqual((gen, reused), (["porosity"], []))


class MergeDefectMetrics(unittest.TestCase):
    def test_reused_types_defect_metrics_carried(self):
        new = {"pairs": [], "cases": [], "defect_metrics": {"ruler": "v2", "types": {"porosity": {"c2st": 0.6}}}}
        best = {"pairs": [], "cases": [], "defect_metrics": {"ruler": "v2", "types": {"porosity": {"c2st": 0.7},
                                                                                     "crack": {"c2st": 0.8}}}}
        m = loop_partial.merge(new, best, ["crack"], "ev12")
        self.assertEqual(m["defect_metrics"]["types"], {"porosity": {"c2st": 0.6}, "crack": {"c2st": 0.8}})


class PlanCycleRulerOutdated(unittest.TestCase):
    """Follow-up 7/10 (thước theo loại): bản tốt nhất đo bằng sơ đồ ruler KHÁC hiện hành -> sinh lại TẤT
    CẢ loại được chọn, không mang theo loại nào (dù núm không đổi, dù bản tốt nhất đã đủ n ca)."""

    def _best(self):
        return {"iter": 7, "eval_run": "ev7", "knobs": {k: {"value": v} for k, v in BASE.items()}}

    def test_different_ruler_regenerates_all_even_with_matching_coverage_and_no_knob_change(self):
        old_result = {"defect_metrics": {"ruler": "thuoc-cu", "types": {}}}
        with mock.patch.object(loop_partial.loop_gate, "read_best", return_value=self._best()), \
                mock.patch.object(loop_partial, "read_json", return_value=old_result):
            gen, reused, best = loop_partial.plan_cycle(BASE, TYPES, 20)   # núm KHÔNG đổi, n khớp
        self.assertEqual((gen, reused), (TYPES, []))
        self.assertEqual(best["iter"], 7)

    def test_same_ruler_does_not_force_full_regen(self):
        from realism.loop_partial import DEFECT_METRICS_RULER
        same_result = {"defect_metrics": {"ruler": DEFECT_METRICS_RULER, "types": {}},
                        "coverage": {t: 20 for t in TYPES}}
        with mock.patch.object(loop_partial.loop_gate, "read_best", return_value=self._best()), \
                mock.patch.object(loop_partial, "read_json", return_value=same_result):
            gen, reused, _ = loop_partial.plan_cycle(BASE, TYPES, 20)      # núm không đổi, n khớp -> dùng lại hết
        self.assertEqual((gen, reused), ([], TYPES))

    def test_missing_ruler_on_best_does_not_force_full_regen(self):
        """Bản tốt nhất rất cũ, chưa từng có defect_metrics (ruler=None): KHÔNG coi là lỗi thời, giữ hành vi
        gốc dựa trên fixed-jobs.json/coverage (xem _best_ruler_outdated)."""
        with mock.patch.object(loop_partial.loop_gate, "read_best", return_value=self._best()), \
                mock.patch.object(loop_partial, "read_json", return_value={"coverage": {t: 20 for t in TYPES}}):
            gen, reused, _ = loop_partial.plan_cycle(BASE, TYPES, 20)
        self.assertEqual((gen, reused), ([], TYPES))


if __name__ == "__main__":
    unittest.main()
