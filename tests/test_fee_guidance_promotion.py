from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.validate_fee_candidates import build, normalize_fee_candidate

ROOT = Path(__file__).resolve().parents[1]


class FeeGuidancePromotionGateTests(unittest.TestCase):
    def test_normalizes_only_safe_fee_markers(self):
        self.assertEqual(
            normalize_fee_candidate("Không quy định x Toàn trình"),
            "Không quy định",
        )
        self.assertEqual(
            normalize_fee_candidate("Không thu phí x x Thông tư số 22/2025/TT-BYT"),
            "Không thu phí",
        )
        self.assertIsNone(
            normalize_fee_candidate("Lệ phí: 500.000/")
        )
        self.assertIsNone(
            normalize_fee_candidate("không có hạ tầng mạng")
        )
        self.assertIsNone(
            normalize_fee_candidate("Phí: 07 ngày làm việc")
        )

    def test_safe_consensus_is_ready_for_existing_code(self):
        canonical = {"thuTuc": [{"ma": "1.000001"}]}
        candidates = {
            "rows": [
                {
                    "ma": "1.000001",
                    "fields": {
                        "phiLePhi": {
                            "candidateValue": "Không quy định x Toàn trình",
                            "confidence": "high",
                        }
                    },
                    "source": {"attachmentUrl": "https://example.gov.vn/a.pdf"},
                },
                {
                    "ma": "1.000001",
                    "fields": {
                        "phiLePhi": {
                            "candidateValue": "Không quy định - Luật A",
                            "confidence": "high",
                        }
                    },
                    "source": {"attachmentUrl": "https://example.gov.vn/b.pdf"},
                },
            ]
        }

        result = build(canonical, candidates)
        self.assertEqual(result["summary"]["feeReady"], 1)
        self.assertEqual(result["ready"][0]["candidateValue"], "Không quy định")

    def test_unsafe_text_is_kept_for_review(self):
        canonical = {"thuTuc": [{"ma": "1.000002"}]}
        candidates = {
            "rows": [
                {
                    "ma": "1.000002",
                    "fields": {
                        "phiLePhi": {
                            "candidateValue": "Lệ phí: 500.000/",
                            "confidence": "high",
                        }
                    },
                    "source": {},
                }
            ]
        }

        result = build(canonical, candidates)
        self.assertEqual(result["summary"]["feeNeedsReview"], 1)
        self.assertEqual(
            result["needsReview"][0]["reason"],
            "unsafe_or_truncated_fee_text",
        )

    def test_missing_canonical_code_is_kept_for_phase2(self):
        canonical = {"thuTuc": []}
        candidates = {
            "rows": [
                {
                    "ma": "1.000003",
                    "fields": {
                        "phiLePhi": {
                            "candidateValue": "Không thu phí x x",
                            "confidence": "high",
                        }
                    },
                    "source": {},
                }
            ]
        }

        result = build(canonical, candidates)
        self.assertEqual(result["summary"]["pendingCanonicalPhase2"], 1)
        self.assertEqual(
            result["pendingCanonicalPhase2"][0]["promotionStatus"],
            "pending_canonical_phase2",
        )

    def test_existing_different_value_is_not_overwritten(self):
        canonical = {
            "thuTuc": [
                {
                    "ma": "1.000004",
                    "phiLePhi": {
                        "status": "verified",
                        "note": "Có thu phí",
                    },
                }
            ]
        }
        candidates = {
            "rows": [
                {
                    "ma": "1.000004",
                    "fields": {
                        "phiLePhi": {
                            "candidateValue": "Không quy định",
                            "confidence": "high",
                        }
                    },
                    "source": {},
                }
            ]
        }

        result = build(canonical, candidates)
        self.assertEqual(result["summary"]["feeNeedsReview"], 1)
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
                "candidateCodes": 50,
                "feeReady": 14,
                "feeConfirmedExisting": 0,
                "feeNeedsReview": 18,
                "pendingCanonicalPhase2": 18,
            },
        )
        self.assertEqual(
            {item["ma"] for item in result["ready"]},
            {
                "1.013734",
                "1.012756",
                "1.000464",
                "1.000479",
                "1.014390",
                "2.001576",
                "1.014953",
                "2.001225",
                "1.008925",
                "1.008926",
                "1.008927",
                "1.008928",
                "1.000302",
                "1.000321",
            },
        )


if __name__ == "__main__":
    unittest.main()
