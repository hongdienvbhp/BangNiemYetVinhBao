import unittest
from unittest.mock import patch

from scripts import update_official_sources as scanner


class OfficialSourceScannerTests(unittest.TestCase):
    def test_newly_registered_source_requires_its_own_baseline(self):
        config = {
            "listingSources": [
                {"id": "existing", "url": "https://existing.haiphong.gov.vn/thu-tuc-hanh-chinh"},
                {"id": "new-central", "url": "https://www.haiphong.gov.vn/thu-tuc-hanh-chinh-76761"},
            ]
        }
        index_rows = [
            {"sourceId": "existing", "articleUrl": "https://existing.haiphong.gov.vn/a"}
        ]

        self.assertEqual(
            scanner.source_ids_requiring_baseline(config, index_rows),
            {"new-central"},
        )

    def test_source_with_existing_index_rows_is_not_rebaselined(self):
        config = {
            "listingSources": [
                {"id": "existing", "url": "https://existing.haiphong.gov.vn/thu-tuc-hanh-chinh"}
            ]
        }
        index_rows = [
            {"sourceId": "existing", "articleUrl": "https://existing.haiphong.gov.vn/a"}
        ]

        self.assertEqual(scanner.source_ids_requiring_baseline(config, index_rows), set())

    def test_external_ministry_reference_is_not_treated_as_city_decision(self):
        title = (
            "Công khai Quyết định số 2841/QĐ-UBND ngày 08/9/2026 của Bộ Y tế "
            "về việc phê duyệt phương án tái cấu trúc thủ tục hành chính lĩnh vực dược phẩm"
        )
        self.assertEqual(scanner.classify_title(title, {}), "external_reference")

    def test_missing_manifest_date_is_enriched_from_consistent_official_listing(self):
        manifest = {
            "3726/QĐ-UBND": {
                "decisionNo": "3726/QĐ-UBND",
                "decisionDate": "",
                "classification": "public_tthc",
            }
        }
        candidate = scanner.Candidate(
            source_id="official",
            source_url="https://haiphong.gov.vn",
            source_authority="Hai Phong",
            authority_type="city_portal",
            source_role="primary_decision_listing",
            legal_use="primary_publication",
            article_url="https://haiphong.gov.vn/3726",
            anchor_text="QD 3726",
            decision_no="3726/QĐ-UBND",
            decision_date="2026-09-15",
        )

        enriched = scanner.reconcile_missing_manifest_dates(manifest, [candidate])

        self.assertEqual(enriched, {"3726/QĐ-UBND": "2026-09-15"})
        self.assertEqual(manifest["3726/QĐ-UBND"]["decisionDate"], "2026-09-15")

    def test_conflicting_listing_dates_do_not_autofill_manifest(self):
        manifest = {
            "3726/QĐ-UBND": {
                "decisionNo": "3726/QĐ-UBND",
                "decisionDate": "",
                "classification": "public_tthc",
            }
        }
        candidates = [
            scanner.Candidate("a", "https://a.haiphong.gov.vn", "A", "city_portal", "primary_decision_listing", "primary_publication", "https://a/3726", "", "3726/QĐ-UBND", "2026-09-15"),
            scanner.Candidate("b", "https://b.haiphong.gov.vn", "B", "department", "primary_decision_listing", "primary_publication", "https://b/3726", "", "3726/QĐ-UBND", "2026-09-16"),
        ]

        self.assertEqual(scanner.reconcile_missing_manifest_dates(manifest, candidates), {})
        self.assertEqual(manifest["3726/QĐ-UBND"]["decisionDate"], "")

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
