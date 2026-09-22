from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.canonical_v4 import (
    SOURCE_BUNDLE_PATHS,
    compute_source_commit,
    derive_dataset_date,
    evidence_id,
)


class CanonicalV4DeterminismTests(unittest.TestCase):
    def test_evidence_id_is_stable(self):
        item = {
            "sourceRole": "local_legal_effect",
            "url": "https://haiphong.gov.vn/a",
            "publishedDate": "2026-09-21",
            "classification": "public_tthc_city_update",
            "repealContext": False,
        }
        self.assertEqual(evidence_id(item), evidence_id(dict(reversed(list(item.items())))))

    def test_source_commit_changes_when_verified_source_changes(self):
        rel = SOURCE_BUNDLE_PATHS[0]
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('{"asOf":"2026-09-20"}', encoding="utf-8")
            first = compute_source_commit(root)
            path.write_text('{"asOf":"2026-09-21"}', encoding="utf-8")
            second = compute_source_commit(root)
            self.assertNotEqual(first, second)
            self.assertEqual(len(first), 40)
            self.assertEqual(len(second), 40)

    def test_source_commit_is_line_ending_independent(self):
        rel = SOURCE_BUNDLE_PATHS[0]
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'{"asOf":"2026-09-21"}\n')
            lf_hash = compute_source_commit(root)
            path.write_bytes(b'{"asOf":"2026-09-21"}\r\n')
            crlf_hash = compute_source_commit(root)
            self.assertEqual(lf_hash, crlf_hash)

    def test_dataset_version_never_rolls_back(self):
        rel = SOURCE_BUNDLE_PATHS[0]
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"asOf": "2026-09-20"}), encoding="utf-8")
            self.assertEqual(derive_dataset_date(root, "2026.09.21"), "2026-09-21")


if __name__ == "__main__":
    unittest.main()
