from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "extract_official_guidance_candidates",
    ROOT / "scripts" / "extract_official_guidance_candidates.py",
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

class OfficialGuidanceCandidateTests(unittest.TestCase):
    def test_segment_stops_at_next_code(self):
        value = MODULE.procedure_segment(
            "1.000001",
            "1.000001 Thủ tục A 05 ngày làm việc 1.000002 Thủ tục B 10 ngày",
        )
        self.assertIn("05 ngày làm việc", value)
        self.assertNotIn("1.000002", value)

    def test_online_level_requires_unambiguous_label(self):
        self.assertEqual(MODULE.online_level("1.000001 A Toàn trình"), "FULL")
        self.assertEqual(MODULE.online_level("1.000001 A Một phần"), "PARTIAL")
        self.assertEqual(MODULE.online_level("Toàn trình Một phần"), "UNKNOWN")

    def test_reception_text_does_not_become_authority(self):
        fields = MODULE.guidance_candidates(
            "1.000001 Tên thủ tục Trung tâm PVHCC cấp xã 05 ngày làm việc"
        )
        self.assertIn("Trung tâm PVHCC cấp xã", fields["agencyCandidates"])

    def test_repository_build_has_candidate_rows(self):
        payload = json.loads(
            (ROOT / "data" / "source-audit" / "vinhbao-tthc-attachment-evidence-20260906.json")
            .read_text(encoding="utf-8-sig")
        )
        result = MODULE.build(payload)
        self.assertGreater(result["summary"]["codes"], 0)
        self.assertGreater(result["summary"]["durationCandidates"], 0)

if __name__ == "__main__":
    unittest.main()
