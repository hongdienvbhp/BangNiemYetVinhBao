from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.validate_online_service_candidates import build

ROOT = Path(__file__).resolve().parents[1]


class OnlineServicePromotionGateTests(unittest.TestCase):
    def test_high_confidence_consensus_is_ready_for_existing_code(self):
        canonical = {"thuTuc": [{"ma": "1.000001"}]}
        candidates = {
            "rows": [
                {
                    "ma": "1.000001",
                    "fields": {
                        "onlineServiceLevel": {
                            "candidateValue": "FULL",
                            "confidence": "high",
                        }
                    },
                    "source": {"attachmentUrl": "https://example.gov.vn/a.pdf"},
                },
                {
                    "ma": "1.000001",
                    "fields": {
                        "onlineServiceLevel": {
                            "candidateValue": "FULL",
                            "confidence": "high",
                        }
                    },
                    "source": {"attachmentUrl": "https://example.gov.vn/b.pdf"},
                },
            ]
        }

        result = build(canonical, candidates)
        self.assertEqual(result["summary"]["onlineReady"], 1)
        self.assertEqual(result["ready"][0]["candidateValue"], "FULL")

    def test_missing_canonical_code_is_kept_for_phase2(self):
        canonical = {"thuTuc": []}
        candidates = {
            "rows": [
                {
                    "ma": "1.000002",
                    "fields": {
                        "onlineServiceLevel": {
                            "candidateValue": "PARTIAL",
                            "confidence": "high",
                        }
                    },
                    "source": {"attachmentUrl": "https://example.gov.vn/a.pdf"},
                }
            ]
        }

        result = build(canonical, candidates)
        self.assertEqual(result["summary"]["pendingCanonicalPhase2"], 1)
        self.assertEqual(
            result["pendingCanonicalPhase2"][0]["promotionStatus"],
            "pending_canonical_phase2",
        )

    def test_conflicting_evidence_needs_review(self):
        canonical = {"thuTuc": [{"ma": "1.000003"}]}
        candidates = {
            "rows": [
                {
                    "ma": "1.000003",
                    "fields": {
                        "onlineServiceLevel": {
                            "candidateValue": "FULL",
                            "confidence": "high",
                        }
                    },
                    "source": {},
                },
                {
                    "ma": "1.000003",
                    "fields": {
                        "onlineServiceLevel": {
                            "candidateValue": "PARTIAL",
                            "confidence": "high",
                        }
                    },
                    "source": {},
                },
            ]
        }

        result = build(canonical, candidates)
        self.assertEqual(result["summary"]["onlineNeedsReview"], 1)
        self.assertEqual(result["needsReview"][0]["reason"], "candidate_disagreement")

    def test_existing_different_value_is_not_overwritten(self):
        canonical = {
            "thuTuc": [{"ma": "1.000004", "onlineServiceLevel": "PARTIAL"}]
        }
        candidates = {
            "rows": [
                {
                    "ma": "1.000004",
                    "fields": {
                        "onlineServiceLevel": {
                            "candidateValue": "FULL",
                            "confidence": "high",
                        }
                    },
                    "source": {},
                }
            ]
        }

        result = build(canonical, candidates)
        self.assertEqual(result["summary"]["onlineNeedsReview"], 1)
        self.assertEqual(result["needsReview"][0]["reason"], "conflicts_with_canonical")

    def test_repository_snapshot_matches_current_gate(self):
        canonical = json.loads(
            (ROOT / "data" / "thu-tuc.json").read_text(encoding="utf-8-sig")
        )
        candidates = json.loads(
            (
                ROOT
                / "data"
                / "source-audit"
                / "guidance-field-candidates.json"
            ).read_text(encoding="utf-8-sig")
        )

        result = build(canonical, candidates)

        self.assertEqual(
            result["summary"],
            {
                "candidateCodes": 5,
                "onlineReady": 1,
                "onlineConfirmedExisting": 0,
                "onlineNeedsReview": 0,
                "pendingCanonicalPhase2": 4,
            },
        )
        self.assertEqual(
            [(item["ma"], item["candidateValue"]) for item in result["ready"]],
            [("1.013734", "FULL")],
        )
        self.assertEqual(
            [item["ma"] for item in result["pendingCanonicalPhase2"]],
            ["1.013723", "1.013727", "1.013728", "1.013732"],
        )


if __name__ == "__main__":
    unittest.main()
