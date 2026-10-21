import json
import tempfile
import unittest
from pathlib import Path

from scripts import tthc_governance as gov


class GovernanceTests(unittest.TestCase):
    def setUp(self):
        self.policy = json.loads((gov.ROOT / "config/tthc-policy-registry.json").read_text(encoding="utf-8"))

    def test_duplicate_code_is_error(self):
        payload = {
            "format": "bangniemyet-vinhbao-master-data",
            "version": 2,
            "sourceSnapshotDate": "2026-09-22",
            "thuTuc": [
                {"ma": "1", "ten": "A", "linhVuc": "L", "cap": "Xã", "sourceSnapshotDate": "2026-09-22",
                 "sourceEvidence": [{"articleUrl": "https://x", "classification": "official"}]},
                {"ma": "1", "ten": "B", "linhVuc": "L", "cap": "Xã", "sourceSnapshotDate": "2026-09-22",
                 "sourceEvidence": [{"articleUrl": "https://x", "classification": "official"}]},
            ],
        }
        codes = [x.code for x in gov.audit(payload, self.policy)]
        self.assertIn("DUPLICATE_CODE", codes)

    def test_missing_provenance_is_error(self):
        payload = {
            "format": "bangniemyet-vinhbao-master-data",
            "version": 2,
            "sourceSnapshotDate": "2026-09-22",
            "thuTuc": [
                {"ma": "1", "ten": "A", "linhVuc": "L", "cap": "Xã", "sourceSnapshotDate": "2026-09-22",
                 "sourceEvidence": [{"articleUrl": "https://x"}]},
            ],
        }
        codes = [x.code for x in gov.audit(payload, self.policy)]
        self.assertIn("MISSING_PROVENANCE", codes)

    def test_changeset_detects_added_modified_removed(self):
        old = {"thuTuc": [{"ma": "1", "ten": "A"}, {"ma": "2", "ten": "B"}]}
        new = {"thuTuc": [{"ma": "1", "ten": "A2"}, {"ma": "3", "ten": "C"}]}
        result = gov.changeset(old, new)
        self.assertEqual(result["added"], ["3"])
        self.assertEqual(result["removed"], ["2"])
        self.assertEqual(result["modified"], ["1"])

    def test_dataset_version_is_deterministic(self):
        self.assertEqual(
            gov.dataset_version({"version": 2, "sourceSnapshotDate": "2026-09-22"}),
            "2@2026-09-22",
        )


if __name__ == "__main__":
    unittest.main()
