from __future__ import annotations

import unittest

from scripts.build_master_data import apply_duration_promotions
from scripts.canonical_v4 import upgrade_record_to_v4


class DurationPromotionTests(unittest.TestCase):
    def test_promotes_only_missing_duration(self):
        rows = [
            {"ma": "1.000001", "thoiHan": "", "sourceEvidence": []},
            {"ma": "1.000002", "thoiHan": "10 ngày", "sourceEvidence": []},
        ]
        payload = {
            "ready": [
                {
                    "ma": "1.000001",
                    "field": "thoiHan",
                    "candidateValue": "05 ngày làm việc",
                    "promotionStatus": "ready",
                    "sources": [{
                        "attachmentUrl": "https://example.gov.vn/a.pdf",
                        "articleUrls": ["https://example.gov.vn/a"],
                        "decisionNumbers": ["1/QĐ-TEST"],
                    }],
                },
                {
                    "ma": "1.000002",
                    "field": "thoiHan",
                    "candidateValue": "05 ngày",
                    "promotionStatus": "ready",
                    "sources": [],
                },
            ]
        }
        stats = apply_duration_promotions(rows, payload)
        self.assertEqual(rows[0]["thoiHan"], "05 ngày làm việc")
        self.assertEqual(rows[1]["thoiHan"], "10 ngày")
        self.assertEqual(stats["promoted"], 1)
        self.assertEqual(stats["skippedExisting"], 1)

    def test_confirmed_existing_candidate_restores_missing_builder_value(self):
        rows = [{"ma": "1.000001", "thoiHan": "", "sourceEvidence": []}]
        payload = {
            "confirmedExisting": [{
                "ma": "1.000001",
                "field": "thoiHan",
                "currentValue": "05 ngày làm việc",
                "candidateValue": "05 ngày làm việc",
                "sources": [{
                    "attachmentUrl": "https://example.gov.vn/a.pdf",
                    "articleUrls": ["https://example.gov.vn/a"],
                    "decisionNumbers": ["1/QĐ-TEST"],
                }],
            }]
        }
        stats = apply_duration_promotions(rows, payload)
        self.assertEqual(rows[0]["thoiHan"], "05 ngày làm việc")
        self.assertEqual(stats["confirmedExisting"], 1)
        self.assertEqual(stats["promoted"], 1)

    def test_duration_evidence_gets_field_level_provenance(self):
        row = {
            "ma": "1.000001",
            "ten": "Test",
            "linhVuc": "TEST",
            "cap": "Xã",
            "thoiHan": "05 ngày làm việc",
            "sourceEvidence": [{
                "sourceRole": "local_legal_effect",
                "articleUrl": "https://example.gov.vn/a",
                "attachmentUrl": "https://example.gov.vn/a.pdf",
                "decisionNumbers": ["1/QĐ-TEST"],
                "classification": "official_table_guidance_duration",
                "repealContext": False,
            }],
        }
        upgraded = upgrade_record_to_v4(row, "2026-09-22")
        duration_ids = [
            item["evidenceId"]
            for item in upgraded["sourceEvidence"]
            if item.get("classification") == "official_table_guidance_duration"
        ]
        self.assertTrue(duration_ids)
        self.assertEqual(upgraded["fieldSources"]["thoiHan"], duration_ids)


if __name__ == "__main__":
    unittest.main()
