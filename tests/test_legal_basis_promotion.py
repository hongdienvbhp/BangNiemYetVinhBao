from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.validate_legal_basis_candidates import build, extract_legal_refs

ROOT = Path(__file__).resolve().parents[1]


class LegalBasisPromotionGateTests(unittest.TestCase):
    def test_extracts_complete_official_references(self):
        value = (
            "Nghị định số 280 /2025/NĐ-CP; "
            "Thông tư số 01/2020/TT-BTP; "
            "Quyết định số 320/QĐ- BNV"
        )
        self.assertEqual(
            extract_legal_refs(value),
            [
                "Nghị định số 280/2025/NĐ-CP",
                "Thông tư số 01/2020/TT-BTP",
                "Quyết định số 320/QĐ-BNV",
            ],
        )

    def test_extracts_named_law_with_complete_number(self):
        self.assertEqual(
            extract_legal_refs(
                "Luật Đất đai số 31/2024/QH15 ngày trường hợp chuyển nhượng"
            ),
            ["Luật số 31/2024/QH15"],
        )

    def test_rejects_truncated_references(self):
        self.assertEqual(extract_legal_refs("Nghị định số 28"), [])
        self.assertEqual(extract_legal_refs("Thông tư số 226"), [])
        self.assertEqual(extract_legal_refs("Luật việc làm ngày 16 thá"), [])
        self.assertEqual(extract_legal_refs("Nghị định số 151/2026/NĐ - C"), [])

    def test_mixed_complete_and_truncated_candidate_stays_review(self):
        canonical = {"thuTuc": [{"ma": "1.000001"}]}
        candidates = {
            "rows": [
                {
                    "ma": "1.000001",
                    "fields": {
                        "canCuPhapLy": {
                            "candidateValue": [
                                "Nghị định số 280/2025/NĐ-CP",
                                "Thông tư số 226",
                            ],
                            "confidence": "medium",
                        }
                    },
                    "source": {},
                }
            ]
        }

        result = build(canonical, candidates)
        self.assertEqual(result["summary"]["legalNeedsReview"], 1)
        self.assertEqual(
            result["needsReview"][0]["reason"],
            "incomplete_or_ocr_truncated_legal_reference",
        )

    def test_missing_canonical_code_is_kept_for_phase2(self):
        canonical = {"thuTuc": []}
        candidates = {
            "rows": [
                {
                    "ma": "1.000002",
                    "fields": {
                        "canCuPhapLy": {
                            "candidateValue": ["Nghị định số 148/2025/NĐ-CP"],
                            "confidence": "medium",
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
                    "ma": "1.000003",
                    "canCuPhapLy": ["Nghị định số 23/2015/NĐ-CP"],
                }
            ]
        }
        candidates = {
            "rows": [
                {
                    "ma": "1.000003",
                    "fields": {
                        "canCuPhapLy": {
                            "candidateValue": ["Nghị định số 280/2025/NĐ-CP"],
                            "confidence": "medium",
                        }
                    },
                    "source": {},
                }
            ]
        }

        result = build(canonical, candidates)
        self.assertEqual(result["summary"]["legalNeedsReview"], 1)
        self.assertEqual(result["needsReview"][0]["reason"], "conflicts_with_canonical")

    def test_repository_snapshot_matches_strict_gate(self):
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
                "candidateCodes": 171,
                "legalReady": 13,
                "legalConfirmedExisting": 0,
                "legalNeedsReview": 72,
                "pendingCanonicalPhase2": 86,
            },
        )

        ready_codes = {item["ma"] for item in result["ready"]}
        self.assertTrue(
            {
                "2.001008",
                "2.001016",
                "2.001406",
                "1.013994",
                "1.014390",
                "1.116316",
            }.issubset(ready_codes)
        )

        review_codes = {item["ma"] for item in result["needsReview"]}
        self.assertIn("2.000992", review_codes)
        self.assertIn("1.013734", review_codes)
        self.assertIn("1.008925", review_codes)


if __name__ == "__main__":
    unittest.main()
