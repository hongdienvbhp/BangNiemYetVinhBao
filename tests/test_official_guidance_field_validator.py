from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_official_guidance_fields",
    ROOT / "scripts" / "validate_official_guidance_fields.py",
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class OfficialGuidanceFieldValidatorTests(unittest.TestCase):
    def test_single_value_is_verified(self):
        self.assertEqual(MODULE.validate_single(["05 ngày"])["status"], "verified")

    def test_multiple_values_are_conflicting(self):
        self.assertEqual(
            MODULE.validate_single(["05 ngày", "03 ngày"])["status"],
            "conflicting",
        )

    def test_empty_is_insufficient(self):
        self.assertEqual(MODULE.validate_single([])["status"], "insufficient")

    def test_row_never_promotes_conflicting_duration(self):
        row = {
            "ma": "1.000001",
            "onlineServiceLevelCandidate": "FULL",
            "durationCandidates": ["05 ngày", "03 ngày"],
            "feeCandidates": [],
            "feeStatusCandidates": [],
            "legalBasisCandidates": ["Nghị định 01/2026/NĐ-CP"],
            "agencyCandidates": ["UBND cấp xã"],
        }
        result = MODULE.validate_row(row)
        self.assertIn("onlineServiceLevel", result["promotableFields"])
        self.assertNotIn("thoiHan", result["promotableFields"])


if __name__ == "__main__":
    unittest.main()
