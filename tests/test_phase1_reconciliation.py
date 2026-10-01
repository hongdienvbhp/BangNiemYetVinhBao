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
        self.assertEqual(result["canonicalTotal"], 535)
        self.assertEqual(result["summary"]["phase1CandidateCodes"], 321)
        self.assertEqual(result["summary"]["outOfScopeProvinceReceptionOnly"], 214)
        self.assertEqual(result["summary"]["misclassifiedByOfficialEvidence"], 3)  # cờ rà soát: lệch giữa bảng phân loại chính thức và QĐ thành phố
        self.assertEqual(result["summary"]["minimumMissingAgainstAggregateBaseline"], 2)
        self.assertEqual(result["COUNT_DRIFT"]["delta"], -2)

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


class LatestOfficialAggregateTests(unittest.TestCase):
    def test_q3_2026_aggregate_is_recorded_without_overwriting_baseline(self):
        import json
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        b = json.loads((root / "data/source-audit/phase1-authoritative-baseline.json").read_text(encoding="utf-8"))
        self.assertEqual(b["aggregate"]["combined"]["total"], 323)
        q3 = b["officialAggregateUpdates"][-1]
        self.assertEqual(q3["reportPeriod"], "Q3/2026")
        for block in ("communeAuthority", "shared", "combined", "provinceOnly"):
            v = q3[block]
            self.assertEqual(v["total"], v["FULL"] + v["PARTIAL"] + v["NOT_ONLINE"], block)
        self.assertEqual(q3["combined"]["total"], q3["communeAuthority"]["total"] + q3["shared"]["total"])
        self.assertEqual(q3["cityTotal"], q3["provinceOnly"]["total"] + q3["combined"]["total"])
        r = json.loads((root / "data/reconciliation/phase1-current.json").read_text(encoding="utf-8"))
        self.assertEqual(r["summary"]["latestOfficialAggregateTarget"], 348)
        self.assertEqual(
            r["summary"]["minimumMissingAgainstLatestOfficialAggregate"],
            348 - r["summary"]["phase1CandidateCodes"],
        )

if __name__ == "__main__":
    unittest.main()
