from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "reconcile_priority51_crosswalk",
    ROOT / "scripts" / "reconcile_priority51_crosswalk.py",
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ReconcilePriority51CrosswalkTest(unittest.TestCase):
    def fixture_payloads(self) -> tuple[dict, dict, dict, dict]:
        items = []
        live_items = []
        for ordinal in range(1, 52):
            code = f"1.{ordinal:06d}"
            items.append({
                "ordinal": ordinal,
                "code": code,
                "name": f"Technical name {ordinal}",
                "formalityId": (
                    f"00000000-0000-4000-8000-{ordinal:012d}"
                    if ordinal <= 48 else None
                ),
                "mappingMode": "formality_id" if ordinal <= 48 else "keyword_fallback",
                "inCurrentMaster": False,
                "currentMasterName": "stale",
                "exactNameMatch": False,
                "legalStatusAssertion": "none_from_priority_crosswalk",
                "liveVerificationResult": "STALE",
                "liveNameVisible": False,
                "liveAgencyVisible": False,
            })
            live_items.append({
                "code": code,
                "result": "VERIFIED_VISIBLE_IDENTITY" if ordinal <= 36 else "UNRESOLVED_VISIBLE_IDENTITY",
                "name_visible": ordinal <= 36,
                "vinh_bao_agency_visible": False,
            })

        crosswalk = {
            "format": "vinhbao-priority-51-crosswalk",
            "version": 1,
            "generatedAt": "2026-09-07",
            "sourceSnapshotDate": "2026-09-06",
            "canonicalContract": "data/thu-tuc.json",
            "canonicalDatasetVersion": "2026.09.07",
            "canonicalSourceCommit": "b" * 40,
            "liveVerificationManifest": "data/source-audit/dvcqg-live-verification-current.json",
            "summary": {},
            "items": items,
        }
        master_rows = [
            {"ma": "1.000001", "ten": "Canonical name 1"},
            {"ma": "1.000002", "ten": "Technical name 2"},
        ]
        master_rows.extend(
            {"ma": f"1.{ordinal:06d}", "ten": f"Technical name {ordinal}"}
            for ordinal in range(3, 49)
        )
        master = {
            "format": "bangniemyet-vinhbao-master-data",
            "version": 4,
            "dataset_version": "2026.10.09",
            "source_commit": "a" * 40,
            "thuTuc": master_rows,
        }
        live = {
            "verified_at": "2026-10-09T00:00:00Z",
            "totals": {
                "verified_identity_only": 36,
                "verified_identity_and_agency": 0,
                "unresolved": 15,
                "waf_rejected": 0,
            },
            "items": live_items,
        }
        legal_rows = []
        for ordinal, decision in [(49, "TEST-REPEAL-49"), (50, "TEST-REPEAL-50"), (51, "TEST-REPEAL-51")]:
            legal_rows.append({
                "code": f"1.{ordinal:06d}",
                "legalStatus": "repealed_official_evidence",
                "communeScopeEvidence": True,
                "decisionNo": decision,
                "decisionDate": "2026-09-01",
                "sources": [{"url": f"https://official.example.gov.vn/{ordinal}.pdf"}],
                "verificationCheckedAt": "2026-10-09",
                "legalStatusBasis": "official_haiphong_source",
                "dvcqgRole": "technical_identity_only",
            })
        legal = {
            "format": "vinhbao-priority-51-legal-verification",
            "version": 1,
            "asOf": "2026-10-09",
            "summary": {"total": 3, "currentOfficialCommune": 0, "repealedOfficial": 3, "needsVerification": 0},
            "rows": legal_rows,
        }
        return crosswalk, master, live, legal

    def run_reconcile(self, directory: Path, crosswalk: dict, master: dict, live: dict, legal: dict) -> dict:
        cross_path = directory / "priority-51-crosswalk.json"
        master_path = directory / "thu-tuc.json"
        live_path = directory / "dvcqg-live-verification-current.json"
        legal_path = directory / "priority-51-legal-verification.json"
        cross_path.write_text(json.dumps(crosswalk, ensure_ascii=False, indent=2), encoding="utf-8")
        master_path.write_text(json.dumps(master, ensure_ascii=False, indent=2), encoding="utf-8")
        live_path.write_text(json.dumps(live, ensure_ascii=False, indent=2), encoding="utf-8")
        legal_path.write_text(json.dumps(legal, ensure_ascii=False, indent=2), encoding="utf-8")

        with (
            patch.object(MODULE, "CROSSWALK", cross_path),
            patch.object(MODULE, "MASTER", master_path),
            patch.object(MODULE, "LIVE", live_path),
            patch.object(MODULE, "LEGAL", legal_path),
        ):
            with redirect_stdout(StringIO()):
                MODULE.main()
        return json.loads(cross_path.read_text(encoding="utf-8"))

    def test_joins_legal_evidence_without_rewriting_technical_identity(self) -> None:
        crosswalk, master, live, legal = self.fixture_payloads()
        identity_before = {
            item["code"]: (item.get("formalityId"), item.get("mappingMode"), item.get("legalStatusAssertion"))
            for item in crosswalk["items"]
        }

        with tempfile.TemporaryDirectory() as td:
            reconciled = self.run_reconcile(Path(td), crosswalk, master, live, legal)

        self.assertEqual(reconciled["canonicalDatasetVersion"], master["dataset_version"])
        self.assertEqual(reconciled["canonicalSourceCommit"], master["source_commit"])
        self.assertEqual(reconciled["canonicalContract"], "data/thu-tuc.json")
        self.assertEqual(reconciled["generatedAt"], "2026-09-07")
        self.assertEqual(reconciled["sourceSnapshotDate"], "2026-09-06")

        by_code = {item["code"]: item for item in reconciled["items"]}
        self.assertTrue(by_code["1.000001"]["inCurrentMaster"])
        self.assertEqual(by_code["1.000001"]["currentMasterName"], "Canonical name 1")
        self.assertFalse(by_code["1.000001"]["exactNameMatch"])
        self.assertTrue(by_code["1.000002"]["exactNameMatch"])
        self.assertFalse(by_code["1.000051"]["inCurrentMaster"])
        self.assertIsNone(by_code["1.000051"]["currentMasterName"])
        self.assertIsNone(by_code["1.000051"]["exactNameMatch"])
        self.assertEqual(by_code["1.000051"]["legalVerification"]["status"], "repealed_official_evidence")
        self.assertEqual(by_code["1.000051"]["legalVerification"]["decisionNo"], "TEST-REPEAL-51")
        self.assertEqual(by_code["1.000051"]["legalVerification"]["sourceUrls"], ["https://official.example.gov.vn/51.pdf"])
        self.assertEqual(by_code["1.000001"]["legalVerification"]["status"], "not_covered_by_legal_verification_manifest")

        for item in reconciled["items"]:
            self.assertEqual(
                (item.get("formalityId"), item.get("mappingMode"), item.get("legalStatusAssertion")),
                identity_before[item["code"]],
            )

        summary = reconciled["summary"]
        self.assertEqual(summary["total"], 51)
        self.assertEqual(summary["directFormalityIds"], 48)
        self.assertEqual(summary["keywordFallbacks"], 3)
        self.assertEqual(summary["inCurrentMaster"], 48)
        self.assertEqual(summary["missingFromCurrentMaster"], 3)
        self.assertEqual(summary["liveVerifiedIdentity"], 36)
        self.assertEqual(summary["liveUnresolved"], 15)
        self.assertEqual(summary["liveWafRejected"], 0)
        self.assertEqual(summary["legalVerificationCovered"], 3)
        self.assertEqual(summary["legalRepealedOfficial"], 3)
        self.assertEqual(summary["missingFromMasterWithRepealedOfficialEvidence"], 3)
        self.assertEqual(summary["missingFromMasterWithCurrentLegalEvidence"], 0)
        self.assertEqual(summary["missingFromMasterWithoutLegalEvidence"], 0)
        self.assertEqual(reconciled["liveVerifiedAt"], live["verified_at"])

    def test_fails_closed_if_master_missing_code_is_not_officially_repealed(self) -> None:
        crosswalk, master, live, legal = self.fixture_payloads()
        legal["rows"] = legal["rows"][:-1]
        legal["summary"]["total"] = 2
        with tempfile.TemporaryDirectory() as td:
            cross_path = Path(td) / "priority-51-crosswalk.json"
            cross_path.write_text(json.dumps(crosswalk, ensure_ascii=False, indent=2), encoding="utf-8")
            before = cross_path.read_text(encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "absent from Master Data without official repeal evidence: 1.000051"):
                self.run_reconcile(Path(td), crosswalk, master, live, legal)
            self.assertEqual(cross_path.read_text(encoding="utf-8"), before)

    def test_refuses_live_manifest_with_incomplete_51_code_set_without_writing(self) -> None:
        crosswalk, master, live, legal = self.fixture_payloads()
        live["items"] = live["items"][:-1]

        with tempfile.TemporaryDirectory() as td:
            cross_path = Path(td) / "priority-51-crosswalk.json"
            master_path = Path(td) / "thu-tuc.json"
            live_path = Path(td) / "dvcqg-live-verification-current.json"
            legal_path = Path(td) / "priority-51-legal-verification.json"
            cross_path.write_text(json.dumps(crosswalk, ensure_ascii=False, indent=2), encoding="utf-8")
            master_path.write_text(json.dumps(master, ensure_ascii=False, indent=2), encoding="utf-8")
            live_path.write_text(json.dumps(live, ensure_ascii=False, indent=2), encoding="utf-8")
            legal_path.write_text(json.dumps(legal, ensure_ascii=False, indent=2), encoding="utf-8")
            before = cross_path.read_text(encoding="utf-8")

            with (
                patch.object(MODULE, "CROSSWALK", cross_path),
                patch.object(MODULE, "MASTER", master_path),
                patch.object(MODULE, "LIVE", live_path),
                patch.object(MODULE, "LEGAL", legal_path),
            ):
                with self.assertRaisesRegex(ValueError, "Expected 51 live verification items"):
                    MODULE.main()

            self.assertEqual(cross_path.read_text(encoding="utf-8"), before)


if __name__ == "__main__":
    unittest.main()
