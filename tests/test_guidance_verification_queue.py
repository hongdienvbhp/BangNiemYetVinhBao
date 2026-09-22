from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "build_guidance_verification_queue",
    ROOT / "scripts" / "build_guidance_verification_queue.py",
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class GuidanceVerificationQueueTests(unittest.TestCase):
    def test_queue_excludes_existing_guidance_and_requires_exact_identity(self):
        master = {
            "dataset_version": "2026.09.21",
            "source_commit": "a" * 40,
            "thuTuc": [
                {"ma": "1.000001", "ten": "A", "lifecycle": {"status": "active"}, "formalityId": "fid-a", "nopHoSoUrl": "https://dichvucong.gov.vn/x"},
                {"ma": "1.000002", "ten": "B", "lifecycle": {"status": "active"}, "formalityId": "fid-b", "huongDan": {}},
                {"ma": "1.000003", "ten": "C", "lifecycle": {"status": "repealed"}, "formalityId": "fid-c"},
            ],
        }
        locators = {"rows": [{
            "ma": "1.000001", "canonicalName": "A", "candidateName": "A", "formalityId": "fid-a",
            "sourceUrl": "https://dichvucong.gov.vn/tim-kiem-thu-tuc-hanh-chinh?formalityId=fid-a",
            "contentHash": "hash", "scrapedAt": "2026-06-23T00:00:00Z",
        }]}
        result = MODULE.build(master, locators)
        self.assertEqual(result["summary"]["active"], 2)
        self.assertEqual(result["summary"]["existingGuidance"], 1)
        self.assertEqual(result["summary"]["queued"], 1)
        self.assertEqual(result["summary"]["exactOfficialLocators"], 1)
        self.assertFalse(result["rows"][0]["publishAllowed"])
        self.assertEqual(result["rows"][0]["verificationStatus"], "awaiting_current_official_verification")
        self.assertEqual(result["rows"][0]["verificationLane"], "EXACT_FORMALITY_CASE")
        self.assertEqual(result["rows"][0]["verificationPriority"], 1)

    def test_mismatched_candidate_is_not_treated_as_official_locator(self):
        master = {"thuTuc": [{
            "ma": "1.000001", "ten": "A", "lifecycle": {"status": "active"}, "formalityId": "fid-a"
        }]}
        locators = {"rows": [{
            "ma": "1.000001", "canonicalName": "A", "candidateName": "Wrong", "formalityId": "fid-a",
            "sourceUrl": "https://dichvucong.gov.vn/x",
        }]}
        result = MODULE.build(master, locators)
        self.assertFalse(result["rows"][0]["identityMatch"])
        self.assertEqual(result["rows"][0]["candidateOfficialUrl"], "")
        self.assertEqual(result["rows"][0]["verificationLane"], "FORMALITY_ID_LOOKUP")
        self.assertEqual(result["rows"][0]["verificationPriority"], 2)
        self.assertIn("formalityId=fid-a", result["rows"][0]["verificationUrl"])

    def test_missing_formality_uses_keyword_search_lane(self):
        master = {"thuTuc": [{
            "ma": "1.000001", "ten": "A", "lifecycle": {"status": "active"},
            "nopHoSoUrl": "https://dichvucong.gov.vn/tim-kiem-thu-tuc-hanh-chinh?keyword=1.000001",
        }]}
        result = MODULE.build(master, {"rows": []})
        row = result["rows"][0]
        self.assertEqual(row["verificationLane"], "KEYWORD_SEARCH_ONLY")
        self.assertEqual(row["verificationPriority"], 3)
        self.assertEqual(row["verificationUrl"], master["thuTuc"][0]["nopHoSoUrl"])


if __name__ == "__main__":
    unittest.main()
