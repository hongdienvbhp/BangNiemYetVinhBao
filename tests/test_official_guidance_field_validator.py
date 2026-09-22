from __future__ import annotations

import importlib.util
import json
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


    def test_reception_center_is_not_executing_agency(self):
        result = MODULE.validate_agency(
            ["Trung tâm Phục vụ hành chính công thành phố"],
            [{"segment": "1.000001 Tên thủ tục Trung tâm Phục vụ hành chính công thành phố"}],
        )
        self.assertEqual(result["status"], "insufficient")
        self.assertEqual(result["reason"], "reception_location_only")

    def test_unlabelled_commune_mention_is_not_promotable(self):
        result = MODULE.validate_agency(
            ["Ủy ban nhân dân cấp xã"],
            [{"segment": "1.000001 Cơ quan A trả lời Ủy ban nhân dân cấp xã"}],
        )
        self.assertEqual(result["status"], "insufficient")
        self.assertEqual(result["reason"], "unlabelled_agency_mention")

    def test_explicit_agency_label_can_be_verified(self):
        result = MODULE.validate_agency(
            ["Ủy ban nhân dân cấp xã"],
            [{"segment": "Cơ quan thực hiện: Ủy ban nhân dân cấp xã"}],
        )
        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["value"], "Ủy ban nhân dân cấp xã")

    def test_multiple_agency_mentions_are_conflicting(self):
        result = MODULE.validate_agency(
            [
                "Ủy ban nhân dân cấp xã",
                "Trung tâm Phục vụ hành chính công thành phố",
            ],
            [],
        )
        self.assertEqual(result["status"], "conflicting")
        self.assertEqual(result["reason"], "multiple_agency_mentions")

    def test_repository_agency_candidates_are_not_auto_promoted(self):
        payload = json.loads(
            (
                ROOT
                / "data"
                / "source-audit"
                / "official-guidance-candidates.json"
            ).read_text(encoding="utf-8-sig")
        )
        result = MODULE.build(payload)
        self.assertEqual(
            result["summary"]["coQuanThucHien"],
            {"verified": 0, "conflicting": 18, "insufficient": 540},
        )


if __name__ == "__main__":
    unittest.main()
