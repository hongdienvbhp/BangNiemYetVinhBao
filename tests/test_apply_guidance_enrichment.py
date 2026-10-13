from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from scripts.apply_guidance_enrichment import apply_enrichment
from scripts.validate_tthc_guidance import validate_legacy_field_overrides

ROOT = Path(__file__).resolve().parents[1]


def load_json(relative_path: str) -> dict:
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8-sig"))


class LegacyGuidanceOverrideTests(unittest.TestCase):
    def test_qd_4123_duration_is_mirrored_without_changing_priority_contract_or_scope(self) -> None:
        master = load_json("data/thu-tuc.json")
        priority = load_json("data/priority-51-crosswalk.json")
        guidance = load_json("data/tthc-guidance-enrichment.json")
        overrides = load_json("data/source-audit/official-legacy-field-overrides.json")

        self.assertEqual(len(guidance["rows"]), 48)
        self.assertNotIn("2.001576", {item.get("ma") for item in guidance["rows"]})
        result = apply_enrichment(master, priority, guidance, legacy_overrides_payload=overrides)
        row = next(item for item in result["thuTuc"] if item.get("ma") == "2.001576")

        self.assertEqual(row.get("thoiHan"), "11,5 ng\u00e0y l\u00e0m vi\u1ec7c")
        self.assertEqual(row.get("cap"), "C\u1ea5p t\u1ec9nh - ti\u1ebfp nh\u1eadn t\u1ea1i Trung t\u00e2m PVHCC c\u1ea5p x\u00e3")
        override = next(item for item in overrides["rows"] if item.get("ma") == "2.001576")
        expected_source_id = row["fieldSources"]["thoiHan"]
        evidence_ids = {
            str(item.get("evidenceId") or "")
            for item in row.get("sourceEvidence", [])
            if isinstance(item, dict)
        }
        self.assertTrue(expected_source_id)
        self.assertTrue(set(expected_source_id).issubset(evidence_ids))
        self.assertEqual(override["fieldProvenance"]["thoiHan"], ["official_decision_4123_annex_pdf"])

    def test_legacy_override_rejects_unknown_field(self) -> None:
        overrides = deepcopy(load_json("data/source-audit/official-legacy-field-overrides.json"))
        overrides["rows"][0]["legacyOverrides"] = {"cap": "C?p t?nh"}
        errors = validate_legacy_field_overrides(overrides)
        self.assertTrue(any("legacyOverrides.cap" in error for error in errors), errors)

    def test_legacy_override_requires_field_provenance(self) -> None:
        overrides = deepcopy(load_json("data/source-audit/official-legacy-field-overrides.json"))
        overrides["rows"][0]["fieldProvenance"].pop("thoiHan", None)
        errors = validate_legacy_field_overrides(overrides)
        self.assertTrue(any("legacyOverrides.thoiHan" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
