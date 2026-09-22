from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_canonical_field_contract",
    ROOT / "scripts" / "validate_canonical_field_contract.py",
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

class CanonicalFieldContractTests(unittest.TestCase):
    def payload(self) -> dict:
        return json.loads(
            (ROOT / "data" / "canonical-field-contract.json").read_text(encoding="utf-8")
        )

    def test_repository_contract_passes(self):
        self.assertEqual(MODULE.validate(self.payload()), [])

    def test_phase1_baseline_is_consistent(self):
        data = self.payload()["phase1Baseline"]
        self.assertEqual(data["communeAuthority"]["total"], 257)
        self.assertEqual(data["shared"]["total"], 66)
        self.assertEqual(data["combined"]["total"], 323)
        self.assertEqual(data["combined"]["FULL"], 212)
        self.assertEqual(data["combined"]["PARTIAL"], 109)
        self.assertEqual(data["combined"]["INFORMATION_ONLY"], 2)

    def test_single_write_model_is_locked(self):
        data = self.payload()
        self.assertTrue(data["principles"]["singleWriteModel"])
        self.assertTrue(data["principles"]["consumerCopiesForbidden"])

if __name__ == "__main__":
    unittest.main()
