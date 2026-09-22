from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.build_guidance_promotion_plan import build

ROOT = Path(__file__).resolve().parents[1]


class GuidancePromotionPlanTests(unittest.TestCase):
    def test_plan_never_mutates_before_schema_gate(self):
        canonical = {"version": 4, "thuTuc": []}
        field_candidates = {"rows": []}
        official_candidates = {"rows": []}

        result = build(canonical, field_candidates, official_candidates)

        self.assertEqual(result["schemaGate"]["status"], "blocked")
        self.assertEqual(result["summary"]["procedures"], 0)
        self.assertEqual(result["summary"]["fieldPromotions"], 0)
        self.assertEqual(result["procedures"], [])

    def test_repository_snapshot_uses_only_specialized_gates(self):
        canonical = json.loads(
            (ROOT / "data" / "thu-tuc.json").read_text(encoding="utf-8-sig")
        )
        field_candidates = json.loads(
            (
                ROOT
                / "data"
                / "source-audit"
                / "guidance-field-candidates.json"
            ).read_text(encoding="utf-8-sig")
        )
        official_candidates = json.loads(
            (
                ROOT
                / "data"
                / "source-audit"
                / "official-guidance-candidates.json"
            ).read_text(encoding="utf-8-sig")
        )

        result = build(canonical, field_candidates, official_candidates)

        self.assertEqual(result["version"], 2)
        self.assertEqual(result["schemaGate"]["status"], "blocked")
        self.assertEqual(result["schemaGate"]["canonicalVersion"], 4)
        self.assertEqual(result["summary"]["safeReadyFields"], 28)
        self.assertEqual(result["summary"]["safeReadyProcedures"], 24)
        self.assertEqual(
            result["summary"]["byField"],
            {
                "onlineServiceLevel": 1,
                "thoiHan": 0,
                "phiLePhi": 14,
                "canCuPhapLy": 13,
                "coQuanThucHien": 0,
            },
        )
        self.assertEqual(
            result["summary"]["confirmedExisting"],
            {
                "onlineServiceLevel": 0,
                "thoiHan": 19,
                "phiLePhi": 0,
                "canCuPhapLy": 0,
                "coQuanThucHien": 0,
            },
        )
        self.assertEqual(
            result["summary"]["needsReview"],
            {
                "onlineServiceLevel": 0,
                "thoiHan": 84,
                "phiLePhi": 18,
                "canCuPhapLy": 72,
                "coQuanThucHien": {
                    "conflicting": 18,
                    "insufficient": 540,
                },
            },
        )
        self.assertEqual(
            result["summary"]["pendingCanonicalPhase2"],
            {
                "onlineServiceLevel": 4,
                "phiLePhi": 18,
                "canCuPhapLy": 86,
            },
        )
        self.assertEqual(
            result["readyCandidateCodes"]["onlineServiceLevel"],
            ["1.013734"],
        )
        self.assertEqual(
            result["readyCandidateCodes"]["phiLePhi"],
            [
                "1.000302",
                "1.000321",
                "1.000464",
                "1.000479",
                "1.008925",
                "1.008926",
                "1.008927",
                "1.008928",
                "1.012756",
                "1.013734",
                "1.014390",
                "1.014953",
                "2.001225",
                "2.001576",
            ],
        )
        self.assertEqual(
            result["readyCandidateCodes"]["canCuPhapLy"],
            [
                "1.000321",
                "1.003814",
                "1.008928",
                "1.011606",
                "1.013822",
                "1.013994",
                "1.014310",
                "1.014312",
                "1.014390",
                "1.116316",
                "2.001008",
                "2.001016",
                "2.001406",
            ],
        )
        self.assertEqual(result["readyCandidateCodes"]["coQuanThucHien"], [])
        self.assertEqual(result["procedures"], [])


if __name__ == "__main__":
    unittest.main()
