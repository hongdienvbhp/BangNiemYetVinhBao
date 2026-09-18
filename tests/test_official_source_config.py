import json
import unittest
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "data/source-audit/official-source-config.json"


class OfficialSourceConfigTests(unittest.TestCase):
    def setUp(self):
        self.payload = json.loads(CONFIG.read_text(encoding="utf-8-sig"))
        self.sources = self.payload.get("listingSources", [])

    def test_source_ids_and_urls_are_unique(self):
        ids = [row["id"] for row in self.sources]
        urls = [row["url"].rstrip("/") for row in self.sources]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(urls), len(set(urls)))

    def test_only_official_hai_phong_or_education_hosts_are_registered(self):
        allowed_suffixes = ("haiphong.gov.vn", "haiphong.edu.vn")
        for row in self.sources:
            parsed = urlparse(row["url"])
            self.assertEqual(parsed.scheme, "https", row)
            host = (parsed.hostname or "").lower()
            self.assertTrue(any(host == x or host.endswith("." + x) for x in allowed_suffixes), row)

    def test_every_source_has_provenance_role(self):
        allowed_roles = {"primary_decision_listing", "official_local_mirror", "procedure_catalog"}
        allowed_uses = {
            "primary_publication",
            "cross_check_only",
            "cross_check_and_local_publication",
            "identity_and_coverage_cross_check",
        }
        for row in self.sources:
            self.assertTrue(row.get("authority"), row)
            self.assertTrue(row.get("authorityType"), row)
            self.assertIn(row.get("sourceRole"), allowed_roles, row)
            self.assertIn(row.get("legalUse"), allowed_uses, row)

    def test_source_portfolio_covers_agencies_and_local_governments(self):
        agency = [x for x in self.sources if x.get("authorityType") == "department"]
        local = [x for x in self.sources if x.get("authorityType", "").startswith("ubnd_")]
        self.assertGreaterEqual(len(agency), 10)
        self.assertGreaterEqual(len(local), 8)


if __name__ == "__main__":
    unittest.main()
