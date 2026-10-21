from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "extract_guidance_field_candidates",
    ROOT / "scripts" / "extract_guidance_field_candidates.py",
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class GuidanceFieldCandidateTests(unittest.TestCase):
    def test_duration_near_code(self):
        window = "1.000001 Thủ tục mẫu 05 ngày làm việc Trung tâm PVHCC"
        result = MODULE.duration_candidate(window, "1.000001")
        self.assertIsNotNone(result)
        self.assertIn("05 ngày", result["candidateValue"])

    def test_online_requires_single_explicit_mark(self):
        self.assertEqual(
            MODULE.online_candidate("1.000001 Tên thủ tục x Một phần", "1.000001")["candidateValue"],
            "PARTIAL",
        )
        self.assertIsNone(
            MODULE.online_candidate(
                "1.000001 Tên thủ tục x Toàn trình x Một phần",
                "1.000001",
            )
        )

    def test_repository_build_is_candidate_only(self):
        payload = json.loads(
            (ROOT / "data" / "source-audit" / "vinhbao-tthc-attachment-evidence-20260906.json")
            .read_text(encoding="utf-8-sig")
        )
        result = MODULE.build(payload)
        self.assertGreater(result["summary"]["procedures"], 0)
        self.assertTrue(all(row["promotionStatus"] == "candidate_only" for row in result["rows"]))


if __name__ == "__main__":
    unittest.main()
