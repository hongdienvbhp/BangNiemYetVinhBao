from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "reconcile_phase1", ROOT / "scripts" / "reconcile_phase1.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Phase1ReconciliationTests(unittest.TestCase):
    def test_repository_reconciliation_invariants(self):
        canonical = json.loads((ROOT / "data" / "thu-tuc.json").read_text(encoding="utf-8-sig"))
        city = json.loads((ROOT / "data" / "source-audit" / "city-updates-current.json").read_text(encoding="utf-8-sig"))
        baseline = json.loads((ROOT / "data" / "source-audit" / "phase1-authoritative-baseline.json").read_text(encoding="utf-8-sig"))
        table_levels = json.loads((ROOT / "data" / "source-audit" / "official-table-level-classification.json").read_text(encoding="utf-8-sig"))
        result = MODULE.reconcile(canonical, city, baseline, table_levels)

        self.assertEqual(result["baselineTarget"], 323)
        self.assertEqual(result["canonicalTotal"], 254)
        self.assertEqual(result["summary"]["phase1CandidateCodes"], 199)
        self.assertEqual(result["summary"]["outOfScopeProvinceReceptionOnly"], 55)
        self.assertEqual(result["summary"]["misclassifiedByOfficialEvidence"], 2)
        self.assertEqual(result["summary"]["minimumMissingAgainstAggregateBaseline"], 124)
        self.assertEqual(result["COUNT_DRIFT"]["delta"], -124)

    def test_missing_codes_are_not_invented(self):
        canonical = {"thuTuc": []}
        city = {"decisions": []}
        baseline = {
            "aggregate": {"combined": {"total": 323}},
            "codeLevelList": {"status": "pending_authoritative_materialization"},
            "asOf": "2026-07-20",
        }
        result = MODULE.reconcile(canonical, city, baseline)
        self.assertEqual(result["MISSING"]["items"], [])
        self.assertEqual(result["MISSING"]["minimumCount"], 323)


if __name__ == "__main__":
    unittest.main()
