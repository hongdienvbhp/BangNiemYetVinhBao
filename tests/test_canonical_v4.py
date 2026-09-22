from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.canonical_v4 import (
    SOURCE_BUNDLE_PATHS,
    classify_v5_record,
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

    def test_v5_commune_mapping(self):
        self.assertEqual(
            classify_v5_record({"cap": "Xã"}),
            {
                "authorityLevel": "COMMUNE",
                "serviceScope": "COMMUNE_AUTHORITY",
                "receivableAtCommune": True,
                "onlineServiceLevel": "UNKNOWN",
            },
        )

    def test_v5_province_reception_only_mapping(self):
        result = classify_v5_record({
            "cap": "Cấp tỉnh - tiếp nhận tại Trung tâm PVHCC cấp xã"
        })
        self.assertEqual(result["authorityLevel"], "PROVINCE")
        self.assertEqual(result["serviceScope"], "COMMUNE_RECEPTION_ONLY")
        self.assertTrue(result["receivableAtCommune"])

    def test_v5_shared_does_not_invent_single_authority(self):
        result = classify_v5_record({
            "cap": "Dùng chung (cấp bộ, cấp tỉnh, cấp xã)"
        })
        self.assertEqual(result["authorityLevel"], "OTHER")
        self.assertEqual(result["serviceScope"], "SHARED")
        self.assertTrue(result["receivableAtCommune"])

    def test_v5_ambiguous_commune_reception_stays_other(self):
        result = classify_v5_record({"cap": "Xã / điểm tiếp nhận cấp xã"})
        self.assertEqual(result["authorityLevel"], "OTHER")
        self.assertEqual(result["serviceScope"], "OTHER")
        self.assertTrue(result["receivableAtCommune"])

    def test_v5_unknown_cap_only_uses_explicit_reception_evidence(self):
        self.assertFalse(
            classify_v5_record({"cap": "Không rõ"})["receivableAtCommune"]
        )
        self.assertTrue(
            classify_v5_record({
                "cap": "Không rõ",
                "tiepNhanCapXa": True,
            })["receivableAtCommune"]
        )

    def test_v5_online_level_preserves_only_contract_enum(self):
        self.assertEqual(
            classify_v5_record({
                "cap": "Xã",
                "onlineServiceLevel": "FULL",
            })["onlineServiceLevel"],
            "FULL",
        )
        self.assertEqual(
            classify_v5_record({
                "cap": "Xã",
                "onlineServiceLevel": "toàn trình",
            })["onlineServiceLevel"],
            "UNKNOWN",
        )

    def test_repository_v5_mapping_snapshot(self):
        payload = json.loads(
            (Path(__file__).resolve().parents[1] / "data" / "thu-tuc.json")
            .read_text(encoding="utf-8-sig")
        )
        authority = {}
        scope = {}
        receivable = {True: 0, False: 0}
        online = {}
        for row in payload.get("thuTuc") or []:
            result = classify_v5_record(row)
            authority[result["authorityLevel"]] = (
                authority.get(result["authorityLevel"], 0) + 1
            )
            scope[result["serviceScope"]] = (
                scope.get(result["serviceScope"], 0) + 1
            )
            receivable[result["receivableAtCommune"]] += 1
            online[result["onlineServiceLevel"]] = (
                online.get(result["onlineServiceLevel"], 0) + 1
            )

        self.assertEqual(
            authority,
            {"PROVINCE": 55, "OTHER": 151, "COMMUNE": 48},
        )
        self.assertEqual(
            scope,
            {
                "COMMUNE_RECEPTION_ONLY": 55,
                "OTHER": 149,
                "COMMUNE_AUTHORITY": 48,
                "SHARED": 2,
            },
        )
        self.assertEqual(receivable, {True: 254, False: 0})
        self.assertEqual(online, {"UNKNOWN": 254})

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
