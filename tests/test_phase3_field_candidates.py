from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "extract_phase3_field_candidates",
    ROOT / "scripts" / "extract_phase3_field_candidates.py",
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

class Phase3FieldCandidateTests(unittest.TestCase):
    def test_window_stops_before_next_code(self):
        text = "2.001019 Chứng thực di chúc 50.000 đồng/di chúc x Nghị định số 280/2025/NĐ-CP 2.001016 Thủ tục khác"
        window = MODULE.procedure_window("2.001019", text)
        self.assertIn("50.000 đồng/di chúc", window)
        self.assertNotIn("2.001016", window)

    def test_fee_candidate(self):
        values = [x["value"] for x in MODULE.extract_fee("Thủ tục 50.000 đồng/văn bản x")]
        self.assertTrue(any("50.000 đồng" in x for x in values))

    def test_legal_candidate(self):
        values = [x["value"] for x in MODULE.extract_legal("Nghị định số 280/2025/NĐ-CP; Thông tư số 01/2020/TT-BTP")]
        self.assertTrue(any("280/2025" in x for x in values))
        self.assertTrue(any("01/2020" in x for x in values))

    def test_does_not_infer_online_level_from_x(self):
        self.assertEqual(MODULE.extract_online_level("Không quy định x Nghị định số 1/2025/NĐ-CP"), [])

    def test_explicit_online_level(self):
        result = MODULE.extract_online_level("Cung cấp dịch vụ công trực tuyến toàn trình")
        self.assertEqual(result[0]["value"], "FULL")
        self.assertEqual(result[0]["confidence"], "high")

if __name__ == "__main__":
    unittest.main()
