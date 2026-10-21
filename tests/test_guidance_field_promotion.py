from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_guidance_field_candidates",
    ROOT / "scripts" / "validate_guidance_field_candidates.py",
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class GuidancePromotionGateTests(unittest.TestCase):
    def test_missing_consensus_is_ready(self):
        canonical = {"thuTuc": [{"ma": "1.000001", "thoiHan": ""}]}
        candidates = {"rows": [
            {"ma": "1.000001", "fields": {"thoiHan": {"candidateValue": "05 ngày làm việc", "confidence": "high"}}, "source": {"attachmentUrl": "a"}},
            {"ma": "1.000001", "fields": {"thoiHan": {"candidateValue": "05 ngày làm việc", "confidence": "high"}}, "source": {"attachmentUrl": "b"}},
        ]}
        result = MODULE.build(canonical, candidates)
        self.assertEqual(result["summary"]["durationReady"], 1)

    def test_flattened_cut_reduction_column_is_trimmed(self):
        canonical = {"thuTuc": [{"ma": "1.000001", "thoiHan": ""}]}
        candidates = {"rows": [
            {"ma": "1.000001", "fields": {"thoiHan": {"candidateValue": "01 ngày làm việc kể từ ngày nhận đủ hồ sơ hợp lệ Không thực hi ện cắt giảm", "confidence": "high"}}, "source": {"attachmentUrl": "a"}},
        ]}
        result = MODULE.build(canonical, candidates)
        self.assertEqual(result["summary"]["durationReady"], 1)
        self.assertEqual(result["ready"][0]["candidateValue"], "01 ngày làm việc kể từ ngày nhận đủ hồ sơ hợp lệ")

    def test_existing_conflict_needs_review(self):
        canonical = {"thuTuc": [{"ma": "1.000001", "thoiHan": "10 ngày"}]}
        candidates = {"rows": [
            {"ma": "1.000001", "fields": {"thoiHan": {"candidateValue": "05 ngày", "confidence": "high"}}, "source": {}},
        ]}
        result = MODULE.build(canonical, candidates)
        self.assertEqual(result["summary"]["durationNeedsReview"], 1)

    def test_disagreement_needs_review(self):
        canonical = {"thuTuc": [{"ma": "1.000001", "thoiHan": ""}]}
        candidates = {"rows": [
            {"ma": "1.000001", "fields": {"thoiHan": {"candidateValue": "05 ngày", "confidence": "high"}}, "source": {}},
            {"ma": "1.000001", "fields": {"thoiHan": {"candidateValue": "10 ngày", "confidence": "high"}}, "source": {}},
        ]}
        result = MODULE.build(canonical, candidates)
        self.assertEqual(result["summary"]["durationNeedsReview"], 1)


if __name__ == "__main__":
    unittest.main()
