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

    def test_flattened_online_duration_and_agency_are_not_auto_promoted(self):
        row = {
            "ma": "1.000001",
            "onlineServiceLevelCandidate": "FULL",
            "durationCandidates": ["05 ngày"],
            "feeCandidates": [],
            "feeStatusCandidates": [],
            "legalBasisCandidates": ["Nghị định 01/2026/NĐ-CP"],
            "agencyCandidates": ["UBND cấp xã"],
        }
        result = MODULE.validate_row(row)
        self.assertNotIn("onlineServiceLevel", result["promotableFields"])
        self.assertNotIn("thoiHan", result["promotableFields"])
        self.assertNotIn("coQuanThucHien", result["promotableFields"])
        self.assertIn("canCuPhapLy", result["promotableFields"])

    def test_truncated_legal_citations_are_rejected(self):
        for value in ("Nghị quyết số", "Nghị quyết số 190/2", "Nghị định số 151/2026/NĐ"):
            result = MODULE.validate_legal({"legalBasisCandidates": [value]})
            self.assertEqual(result["status"], "insufficient", value)

    def test_complete_legal_citation_is_verified(self):
        result = MODULE.validate_legal({
            "legalBasisCandidates": ["Nghị định 151/2026/NĐ-CP"]
        })
        self.assertEqual(result["status"], "verified")

    def test_not_published_fee_status_is_not_promoted(self):
        result = MODULE.validate_fee({
            "feeCandidates": [],
            "feeStatusCandidates": ["NOT_PUBLISHED"],
        })
        self.assertEqual(result["status"], "insufficient")

    def test_explicit_money_or_exemption_can_pass_fee_gate(self):
        self.assertEqual(MODULE.validate_fee({
            "feeCandidates": ["50.000 đồng"], "feeStatusCandidates": []
        })["status"], "verified")
        self.assertEqual(MODULE.validate_fee({
            "feeCandidates": [], "feeStatusCandidates": ["EXEMPT"]
        })["status"], "verified")


if __name__ == "__main__":
    unittest.main()
