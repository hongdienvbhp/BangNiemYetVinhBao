import json
import unittest
from pathlib import Path

from scripts.central_source_registry import build_plan, validate_registry


ROOT = Path(__file__).resolve().parents[1]


class CentralSourceRegistryTests(unittest.TestCase):
    def test_repository_registry_passes(self):
        payload = json.loads((ROOT / "data/source-audit/central-source-registry.json").read_text(encoding="utf-8"))
        self.assertEqual(validate_registry(payload), [])

    def test_central_source_never_changes_legal_status(self):
        registry = {
            "format": "central-tthc-source-registry",
            "version": 1,
            "sourceRole": "central_content_reference",
            "sources": [{
                "id": "moj",
                "authority": "Bộ Tư pháp",
                "domains": ["moj.gov.vn"],
                "fields": ["HỘ TỊCH"],
                "status": "ready",
                "adapter": "direct_code_detail",
                "detailUrlTemplate": "https://moj.gov.vn/detail-{code}.html",
                "provides": ["quyTrinh"],
                "legalUse": "content_only_no_local_effect",
            }],
        }
        master = {"thuTuc": [{
            "ma": "1.000001",
            "ten": "A",
            "linhVuc": "HỘ TỊCH",
            "priority51": True,
            "verificationStatus": "official_current",
        }]}
        plan = build_plan(master, registry)
        self.assertEqual(plan["summary"]["procedures"], 1)
        self.assertEqual(plan["procedures"][0]["sources"][0]["legalUse"], "content_only_no_local_effect")
        self.assertNotIn("verificationStatus", plan["procedures"][0]["sources"][0])

    def test_discovery_only_is_not_ready(self):
        registry = {
            "format": "central-tthc-source-registry",
            "version": 1,
            "sourceRole": "central_content_reference",
            "sources": [{
                "id": "moh",
                "authority": "Bộ Y tế",
                "domains": ["moh.gov.vn"],
                "fields": ["BẢO TRỢ XÃ HỘI"],
                "status": "discovery_only",
                "adapter": "official_portal_discovery",
                "listingUrl": "https://moh.gov.vn/",
                "provides": [],
                "legalUse": "discovery_only_until_code_detail_verified",
            }],
        }
        master = {"thuTuc": [{
            "ma": "1.014027",
            "ten": "A",
            "linhVuc": "BẢO TRỢ XÃ HỘI",
            "priority51": True,
        }]}
        plan = build_plan(master, registry)
        self.assertEqual(plan["procedures"][0]["sourceCoverage"], "discovery_only")
        self.assertEqual(plan["summary"]["withReadySource"], 0)


if __name__ == "__main__":
    unittest.main()
