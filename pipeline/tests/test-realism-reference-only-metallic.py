"""Kiểm loại "chỉ tham khảo" (bước 3, plan 261006-defect-metrics-w0003-reference): metallic_inclusion có
reference_only=True (defect_eval.REFERENCE_ONLY_TYPES) phải bị loại khỏi issues_v2.all_pass VÀ
loop_gate_v2._types_considered, không chặn cổng dù detection_gap tính trực tiếp (không qua null) có thể
trượt trên 3 mẫu thật.

Run: .venv/bin/python tests/test-realism-reference-only-metallic.py
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from realism import issues_v2, loop_gate_v2  # noqa: E402
from realism.defect_eval import REFERENCE_ONLY_TYPES  # noqa: E402


def _entry(reference="Crack", reference_only=False, n_real=20, det_real=0.9, det_syn=0.5):
    """det_syn=0.5 mặc định tạo gap 0,4 (trượt detection_gap rõ rệt) để phân biệt rõ reference_only có
    chặn hay không; null rỗng (không tính được) để c2st/kid/density/coverage đều None (chỉ detection_gap
    đo được trực tiếp, đúng tình huống thật của metallic_inclusion khi dưới MIN_ROWS null)."""
    return {"reference": reference, "reference_only": reference_only, "n_real": n_real,
            "detection_rate_real": det_real, "detection_rate_syn": det_syn,
            "c2st": None, "kid": {"value": None}, "density_coverage": {"density": None, "coverage": None},
            "null": None, "cases": []}


class MetallicInclusionIsFlaggedReferenceOnly(unittest.TestCase):
    def test_metallic_inclusion_in_reference_only_set(self):
        self.assertIn("metallic_inclusion", REFERENCE_ONLY_TYPES)


class IssuesV2ReferenceOnlyExcluded(unittest.TestCase):
    """all_pass không được ăn nhầm detection_gap trượt của loại reference_only=True."""

    def test_reference_only_type_has_no_targets(self):
        self.assertEqual(issues_v2.evaluate_type(_entry(reference_only=True, det_syn=0.0)), [])

    def test_reference_only_excluded_from_evaluate_v2_dict(self):
        result = {"defect_metrics": {"types": {
            "metallic_inclusion": _entry(reference="Metallic_Inclusion", reference_only=True, det_syn=0.0),
        }}}
        self.assertEqual(issues_v2.evaluate_v2(result), {})

    def test_failing_reference_only_type_does_not_block_all_pass(self):
        """metallic_inclusion trượt detection_gap (gap 0,9) nhưng crack đạt hết -> all_pass vẫn True."""
        result = {"defect_metrics": {"types": {
            "crack": _entry(reference="Crack", det_real=0.9, det_syn=0.85),
            "metallic_inclusion": _entry(reference="Metallic_Inclusion", reference_only=True,
                                          det_real=0.9, det_syn=0.0),
        }}}
        self.assertTrue(issues_v2.all_pass(result))

    def test_without_reference_only_flag_would_have_blocked(self):
        """Đối chứng: bỏ cờ reference_only thì chính kết quả trên PHẢI trượt (chứng minh cờ có tác dụng
        thật, không phải all_pass tình cờ đúng vì lý do khác)."""
        result = {"defect_metrics": {"types": {
            "crack": _entry(reference="Crack", det_real=0.9, det_syn=0.85),
            "metallic_inclusion": _entry(reference="Metallic_Inclusion", reference_only=False,
                                          det_real=0.9, det_syn=0.0),
        }}}
        self.assertFalse(issues_v2.all_pass(result))


class LoopGateV2ReferenceOnlyExcluded(unittest.TestCase):
    """_types_considered phải loại metallic_inclusion dù n_real đủ MIN_REAL_ROWS (không chỉ dựa vào n_real
    nhỏ như trước — xem ghi chú trong loop_gate_v2._types_considered)."""

    def test_reference_only_excluded_even_with_enough_real_rows(self):
        new_dm = {"metallic_inclusion": _entry(reference="Metallic_Inclusion", reference_only=True, n_real=20)}
        best_dm = {"metallic_inclusion": _entry(reference="Metallic_Inclusion", reference_only=True, n_real=20)}
        self.assertEqual(loop_gate_v2._types_considered(None, new_dm, best_dm), [])

    def test_non_reference_only_type_still_considered(self):
        new_dm = {"crack": _entry(reference="Crack", reference_only=False, n_real=20)}
        best_dm = {"crack": _entry(reference="Crack", reference_only=False, n_real=20)}
        self.assertEqual(loop_gate_v2._types_considered(None, new_dm, best_dm), ["crack"])


if __name__ == "__main__":
    unittest.main()
