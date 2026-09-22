from __future__ import annotations

import unittest

from scripts.apply_guidance_promotion_plan import apply_plan


def legal_row() -> dict:
    return {
        "ma": "1.000001",
        "lifecycle": {"status": "active"},
        "sourceEvidence": [],
        "fieldSources": {},
    }


def promotion(field: str, value):
    return {
        "field": field,
        "targetPath": field,
        "value": value,
        "status": "ready_for_schema_gate",
        "provenance": [{
            "articleUrls": ["https://haiphong.gov.vn/thu-tuc-hanh-chinh"],
            "attachmentUrl": "https://haiphong.gov.vn/a.pdf",
            "decisionNumbers": ["123/QĐ-UBND"],
        }],
    }


class ApplyGuidancePromotionPlanTests(unittest.TestCase):
    def test_promotes_missing_field_with_provenance(self):
        master = {"thuTuc": [legal_row()]}
        plan = {"procedures": [{
            "ma": "1.000001",
            "promotions": [promotion("thoiHan", "05 ngày làm việc")],
        }]}
        result, audit = apply_plan(master, plan)
        row = result["thuTuc"][0]
        self.assertEqual(row["thoiHan"], "05 ngày làm việc")
        self.assertEqual(audit["summary"]["promotedFields"], 1)
        self.assertTrue(row["fieldSources"]["thoiHan"])
        self.assertEqual(
            row["sourceEvidence"][0]["sourceRole"],
            "local_legal_effect",
        )

    def test_never_overwrites_different_existing_value(self):
        row = legal_row()
        row["thoiHan"] = "03 ngày làm việc"
        master = {"thuTuc": [row]}
        plan = {"procedures": [{
            "ma": "1.000001",
            "promotions": [promotion("thoiHan", "05 ngày làm việc")],
        }]}
        result, audit = apply_plan(master, plan)
        self.assertEqual(result["thuTuc"][0]["thoiHan"], "03 ngày làm việc")
        self.assertEqual(audit["summary"]["conflicts"], 1)

    def test_fee_not_published_is_explicit_status(self):
        master = {"thuTuc": [legal_row()]}
        plan = {"procedures": [{
            "ma": "1.000001",
            "promotions": [promotion("phiLePhi", "NOT_PUBLISHED")],
        }]}
        result, _ = apply_plan(master, plan)
        self.assertEqual(
            result["thuTuc"][0]["phiLePhi"],
            {"status": "not_published", "items": []},
        )

    def test_skips_inactive_and_noncanonical(self):
        inactive = legal_row()
        inactive["lifecycle"]["status"] = "repealed"
        master = {"thuTuc": [inactive]}
        plan = {"procedures": [
            {"ma": "1.000001", "promotions": [promotion("thoiHan", "01 ngày")]},
            {"ma": "9.999999", "promotions": [promotion("thoiHan", "01 ngày")]},
        ]}
        result, audit = apply_plan(master, plan)
        self.assertNotIn("thoiHan", result["thuTuc"][0])
        self.assertEqual(audit["summary"]["skippedInactive"], 1)
        self.assertEqual(audit["summary"]["skippedNotCanonical"], 1)


if __name__ == "__main__":
    unittest.main()
