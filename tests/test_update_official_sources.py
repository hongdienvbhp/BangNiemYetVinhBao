import unittest
from unittest.mock import patch

from scripts import update_official_sources as scanner


class OfficialSourceScannerTests(unittest.TestCase):
    def test_one_source_failure_does_not_abort_other_sources(self):
        config = {
            "listingSources": [
                {"id": "broken", "url": "https://broken.haiphong.gov.vn/thu-tuc-hanh-chinh", "authority": "Broken", "authorityType": "department", "sourceRole": "primary_decision_listing", "legalUse": "primary_publication"},
                {"id": "good", "url": "https://good.haiphong.gov.vn/thu-tuc-hanh-chinh", "authority": "Good", "authorityType": "department", "sourceRole": "primary_decision_listing", "legalUse": "primary_publication"},
            ]
        }
        html = b'<a href="/quyet-dinh-so-123-qd-ubnd-ngay-18-9-2026-cong-bo-thu-tuc-hanh-chinh">Quyet dinh cong bo thu tuc hanh chinh</a>'

        def fake_fetch(url, timeout=35):
            if "broken." in url:
                raise OSError("temporary TLS failure")
            return html, "text/html; charset=utf-8"

        with patch.object(scanner, "fetch_bytes", side_effect=fake_fetch):
            candidates, errors = scanner.discover_candidates(config)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].source_id, "good")
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["sourceId"], "broken")
        self.assertIn("temporary TLS failure", errors[0]["error"])


if __name__ == "__main__":
    unittest.main()
