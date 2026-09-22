from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "build_guidance_promotion_plan",
    ROOT / "scripts" / "build_guidance_promotion_plan.py",
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class GuidancePromotionPlanTests(unittest.TestCase):
    def test_requires_matching_field_evidence(self):
        candidate = {
            "evidence": [{
                "durationCandidates": ["05 ngày"],
                "articleUrls": ["https://example.gov.vn/a"],
                "attachmentUrl": "https://example.gov.vn/a.pdf",
                "decisionNumbers": ["1/QĐ-X"],
                "segment": "05 ngày",
            }]
        }
        self.assertTrue(MODULE.evidence_for_field(candidate, "thoiHan", "05 ngày"))
        self.assertFalse(MODULE.evidence_for_field(candidate, "thoiHan", "03 ngày"))

    def test_plan_does_not_promote_without_evidence(self):
        validated = {
            "rows": [{
                "ma": "1.000001",
                "promotableFields": ["thoiHan"],
                "fields": {"thoiHan": {"status": "verified", "value": "05 ngày"}},
            }]
        }
        candidates = {"rows": [{"ma": "1.000001", "evidence": []}]}
        result = MODULE.build(validated, candidates)
        self.assertEqual(result["summary"]["fieldPromotions"], 0)

    def test_target_mapping_is_canonical_contract(self):
        self.assertEqual(MODULE.TARGETS["phiLePhi"], "huongDan.lePhi")
        self.assertEqual(MODULE.TARGETS["canCuPhapLy"], "huongDan.canCuPhapLy")
        self.assertEqual(MODULE.AUTO_PROMOTION_FIELDS, {"phiLePhi", "canCuPhapLy"})

    def test_plan_filters_non_active_codes(self):
        validated = {"rows": [{
            "ma": "1.000001",
            "promotableFields": ["canCuPhapLy"],
            "fields": {"canCuPhapLy": {"status": "verified", "value": ["Nghị định 1/2026/NĐ-CP"]}},
        }]}
        candidates = {"rows": [{
            "ma": "1.000001",
            "evidence": [{
                "legalBasisCandidates": ["Nghị định 1/2026/NĐ-CP"],
                "articleUrls": ["https://example.gov.vn/a"],
            }],
        }]}
        result = MODULE.build(validated, candidates, {"2.000002"})
        self.assertEqual(result["summary"]["fieldPromotions"], 0)


if __name__ == "__main__":
    unittest.main()
