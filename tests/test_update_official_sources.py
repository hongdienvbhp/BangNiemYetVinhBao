import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
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

    def test_page_parser_detects_rel_next_and_vietnamese_next_label(self):
        parser = scanner.PageParser()
        parser.feed(
            '<a href="/listing?page=2" rel="next">Trang sau</a>'
            '<a href="/unrelated">Tin mới</a>'
        )
        self.assertEqual(parser.next_links, ["/listing?page=2"])
        self.assertEqual(len(parser.links), 2)

    def test_page_parser_ignores_hash_only_carousel_arrows(self):
        parser = scanner.PageParser()
        parser.feed(
            '<div class="ArticleCat"><div class="ArticleInMenu"><div class="Pagination">'
            '<a href="#" class="LeftArrow">&#8592;</a>'
            '<a href="#" class="RightArrow">&#8594;</a>'
            '</div></div></div>'
        )
        self.assertEqual(parser.next_links, [])
        self.assertEqual(len(parser.links), 2)

    def test_page_parser_captures_numbered_page_links(self):
        parser = scanner.PageParser()
        parser.feed(
            '<nav class="pagination">'
            '<a href="/listing">1</a>'
            '<a href="/listing?page=2">2</a>'
            '<a href="/listing?page=3">3</a>'
            '</nav>'
        )
        self.assertEqual(
            parser.numbered_page_links,
            [("/listing", "1"), ("/listing?page=2", "2"), ("/listing?page=3", "3")],
        )

    def test_external_ministry_reference_is_not_treated_as_city_decision(self):
        title = (
            "Công khai Quyết định số 2841/QĐ-UBND ngày 08/9/2026 của Bộ Y tế "
            "về việc phê duyệt phương án tái cấu trúc thủ tục hành chính lĩnh vực dược phẩm"
        )
        self.assertEqual(scanner.classify_title(title, {}), "external_reference")

    def test_invalid_calendar_date_is_preserved_as_unknown(self):
        number, date = scanner.parse_decision_identity(
            "https://example.gov.vn/quyet-dinh-so-9170-qd-ubnd-ngay-31-2-2026-cong-bo-thu-tuc-hanh-chinh",
            "",
        )
        self.assertEqual(number, "9170/QĐ-UBND")
        self.assertEqual(date, "")

    def test_strict_iso_date_rejects_out_of_range_month_and_day(self):
        self.assertEqual(scanner.strict_iso_date("2026", "13", "01"), "")
        self.assertEqual(scanner.strict_iso_date("2026", "06", "31"), "")
        self.assertEqual(scanner.strict_iso_date("2024", "02", "29"), "2024-02-29")

    def test_decision_identity_accepts_colon_without_word_so(self):
        number, date = scanner.parse_decision_identity(
            "https://namsach.haiphong.gov.vn/article",
            "Công khai Quyết định: 3879/QĐ-UBND ngày 20/9/2026 của UBND thành phố Hải Phòng",
        )
        self.assertEqual(number, "3879/QĐ-UBND")
        self.assertEqual(date, "2026-09-20")

    def test_delegation_decision_is_internal_process(self):
        title = (
            "Quyết định 3871/QĐ-UBND ủy quyền cho Giám đốc Sở Văn hóa, Thể thao và Du lịch "
            "thực hiện nhiệm vụ giải quyết các thủ tục hành chính lĩnh vực Báo chí"
        )
        self.assertEqual(scanner.classify_title(title, {}), "internal_process")

    def test_unrelated_decision_on_tthc_listing_is_non_tthc(self):
        title = "Quyết định ban hành Kế hoạch tổ chức Hội thi trực tuyến tìm hiểu công tác cải cách hành chính"
        self.assertEqual(scanner.classify_title(title, {}), "non_tthc")

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

    def test_source_snapshot_is_incomplete_when_any_source_fails(self):
        self.assertFalse(scanner.source_snapshot_is_complete([
            {"sourceId": "broken", "error": "temporary TLS failure"}
        ]))

    def test_source_snapshot_is_complete_when_no_source_fails(self):
        self.assertTrue(scanner.source_snapshot_is_complete([]))

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


    def test_discover_candidates_follows_all_next_pages_and_records_snapshot(self):
        source_url = "https://good.haiphong.gov.vn/thu-tuc-hanh-chinh"
        page_two = "https://good.haiphong.gov.vn/thu-tuc-hanh-chinh?page=2"
        pages = {
            source_url: (
                b'<a href="/quyet-dinh-so-123-qd-ubnd-ngay-18-9-2026-cong-bo-thu-tuc-hanh-chinh">Quyet dinh cong bo thu tuc hanh chinh</a>'
                b'<a rel="next" href="/thu-tuc-hanh-chinh?page=2">Trang sau</a>',
                "text/html; charset=utf-8",
            ),
            page_two: (
                b'<a href="/quyet-dinh-so-124-qd-ubnd-ngay-19-9-2026-cong-bo-thu-tuc-hanh-chinh">Quyet dinh cong bo thu tuc hanh chinh</a>',
                "text/html; charset=utf-8",
            ),
        }
        config = {"listingSources": [{
            "id": "good", "url": source_url, "authority": "Good",
            "authorityType": "department", "sourceRole": "primary_decision_listing",
            "legalUse": "primary_publication",
        }]}
        snapshot = {}

        with patch.object(scanner, "fetch_bytes", side_effect=lambda url, timeout=35: pages[url]):
            candidates, errors = scanner.discover_candidates(config, snapshot)

        self.assertEqual(errors, [])
        self.assertEqual({x.decision_no for x in candidates}, {"123/QĐ-UBND", "124/QĐ-UBND"})
        self.assertEqual(snapshot["sources"][0]["pagesFetched"], 2)
        self.assertEqual(snapshot["sources"][0]["candidateCount"], 2)
        self.assertEqual(len(snapshot["sources"][0]["pages"]), 2)
        self.assertTrue(all(len(x["sha256"]) == 64 for x in snapshot["sources"][0]["pages"]))

    def test_discover_candidates_follows_numbered_listing_pages_without_guessing_urls(self):
        source_url = "https://good.haiphong.gov.vn/thu-tuc-hanh-chinh"
        page_two = source_url + "?page=2"
        page_three = source_url + "?page=3"

        def page(code):
            return (
                f'<a href="/quyet-dinh-so-{code}-qd-ubnd-ngay-18-9-2026-cong-bo-thu-tuc-hanh-chinh">'
                "Quyet dinh cong bo thu tuc hanh chinh</a>"
                '<nav class="pagination">'
                '<a href="/thu-tuc-hanh-chinh">1</a>'
                '<a href="/thu-tuc-hanh-chinh?page=2">2</a>'
                '<a href="/thu-tuc-hanh-chinh?page=3">3</a>'
                '</nav>'
            ).encode(), "text/html; charset=utf-8"

        responses = {
            source_url: page("123"),
            page_two: page("124"),
            page_three: page("125"),
        }
        config = {"listingSources": [{
            "id": "numbered",
            "url": source_url,
            "authority": "Official portal",
            "authorityType": "city_portal",
            "sourceRole": "primary_decision_listing",
            "legalUse": "primary_publication",
        }]}
        snapshot = {}

        with patch.object(scanner, "fetch_bytes", side_effect=lambda url, timeout=35: responses[url]) as fetch:
            candidates, errors = scanner.discover_candidates(config, snapshot)

        self.assertEqual(errors, [])
        self.assertEqual({item.decision_no for item in candidates}, {
            "123/QĐ-UBND", "124/QĐ-UBND", "125/QĐ-UBND"
        })
        self.assertEqual(fetch.call_count, 3)
        self.assertEqual(snapshot["sources"][0]["pagesFetched"], 3)
        self.assertEqual(len(snapshot["sources"][0]["pages"]), 3)

    def test_discover_candidates_fails_closed_when_numbered_pages_have_no_navigable_urls(self):
        source_url = "https://good.haiphong.gov.vn/thu-tuc-hanh-chinh"
        page_html = (
            '<a href="#">1</a><a href="#">2</a><a href="#">3</a>'
        ).encode()
        config = {"listingSources": [{"id": "numbered", "url": source_url}]}

        with patch.object(scanner, "fetch_bytes", return_value=(page_html, "text/html")):
            _candidates, errors = scanner.discover_candidates(config)

        self.assertEqual(len(errors), 1)
        self.assertIn("numeric pagination controls detected", errors[0]["error"])

    def test_discover_candidates_fails_closed_on_pagination_loop(self):
        source_url = "https://good.haiphong.gov.vn/thu-tuc-hanh-chinh"
        page_two = "https://good.haiphong.gov.vn/thu-tuc-hanh-chinh?page=2"
        pages = {
            source_url: (b'<a rel="next" href="/thu-tuc-hanh-chinh?page=2">Trang sau</a>', "text/html"),
            page_two: (b'<a rel="next" href="/thu-tuc-hanh-chinh">Trang sau</a>', "text/html"),
        }
        config = {"listingSources": [{"id": "good", "url": source_url}]}

        with patch.object(scanner, "fetch_bytes", side_effect=lambda url, timeout=35: pages[url]):
            _, errors = scanner.discover_candidates(config)

        self.assertEqual(len(errors), 1)
        self.assertIn("pagination loop detected", errors[0]["error"])

    def test_discover_candidates_fails_closed_when_page_limit_is_reached(self):
        source_url = "https://good.haiphong.gov.vn/thu-tuc-hanh-chinh"
        html = b'<a rel="next" href="/thu-tuc-hanh-chinh?page=2">Trang sau</a>'
        config = {"maxPagesPerSource": 1, "listingSources": [{"id": "good", "url": source_url}]}

        with patch.object(scanner, "fetch_bytes", return_value=(html, "text/html")):
            _, errors = scanner.discover_candidates(config)

        self.assertEqual(len(errors), 1)
        self.assertIn("pagination page limit reached", errors[0]["error"])

    def test_discover_candidates_fails_closed_on_ambiguous_next_links(self):
        source_url = "https://good.haiphong.gov.vn/thu-tuc-hanh-chinh"
        html = (
            b'<a rel="next" href="?page=2">Trang sau</a>'
            b'<a rel="next" href="?page=3">Trang sau</a>'
        )
        config = {"listingSources": [{"id": "good", "url": source_url}]}

        with patch.object(scanner, "fetch_bytes", return_value=(html, "text/html")):
            _, errors = scanner.discover_candidates(config)

        self.assertEqual(len(errors), 1)
        self.assertIn("ambiguous pagination", errors[0]["error"])


    def test_ajax_pagination_uses_declared_pages_and_records_response_hashes(self):
        source_url = "https://good.haiphong.gov.vn/thu-tuc-hanh-chinh"
        endpoint = "/DesktopModule/UIArticleInMenu/ArticleInMenuPagination.aspx/LoadArticle"
        html = f"""
        <div class="Pagination">
          <a class="RightArrow" href="#">→</a>
        </div>
        <a href="/quyet-dinh-so-999-qd-ubnd-ngay-18-9-2026-cong-bo-thu-tuc-hanh-chinh">Unrelated static widget</a>
        <script>
          var maxPage = parseInt(3);
          $.ajax({{
            url: "{endpoint}",
            type: "POST",
            data: {{
              article_category_id: 123,
              categoryIds: "123, 124",
              site_id: 77,
              page: chosenPage,
              page_size: 10,
              keyword: "",
              date_begin: "",
              date_end: "",
              show_no: "False",
              show_post_date: "False",
              num_of_text: 0,
              show_view_count: "False",
              filter_order_in_list: "False",
              is_default: "False",
              new: "False",
              number_of_day: 3,
              no: -15,
              articlelang: "vi-VN",
              is_authenticated: "False"
            }},
            success: function (result) {{}}
          }});
        </script>
        """.encode()
        ajax_pages = {
            "1": (
                b'<ul class="ArticleList"><a href="/quyet-dinh-so-123-qd-ubnd-ngay-18-9-2026-cong-bo-thu-tuc-hanh-chinh">Quyet dinh 123</a></ul>',
                "text/html; charset=utf-8",
            ),
            "2": (
                b'<ul class="ArticleList"><a href="/quyet-dinh-so-124-qd-ubnd-ngay-19-9-2026-cong-bo-thu-tuc-hanh-chinh">Quyet dinh 124</a></ul>',
                "text/html; charset=utf-8",
            ),
            "3": (b"", "text/html; charset=utf-8"),
        }
        config = {
            "maxPagesPerSource": 4,
            "listingSources": [{
                "id": "good",
                "url": source_url,
                "authority": "Good",
                "authorityType": "city_portal",
                "sourceRole": "primary_decision_listing",
                "legalUse": "primary_publication",
            }],
        }
        snapshot = {}

        with (
            patch.object(scanner, "fetch_bytes", return_value=(html, "text/html; charset=utf-8")),
            patch.object(
                scanner,
                "fetch_form_bytes",
                side_effect=lambda url, form_data, referer, timeout=35: ajax_pages[form_data["page"]],
            ) as fetch_form,
        ):
            candidates, errors = scanner.discover_candidates(config, snapshot)

        self.assertEqual(errors, [])
        self.assertEqual({item.decision_no.split("/", 1)[0] for item in candidates}, {"123", "124"})
        self.assertEqual(fetch_form.call_count, 3)
        source = snapshot["sources"][0]
        self.assertEqual(source["paginationMode"], "ajax_form_post")
        self.assertEqual(source["ajaxDeclaredMaxPage"], 3)
        self.assertEqual(source["ajaxLastNonEmptyPage"], 2)
        self.assertEqual(source["ajaxEmptyPages"], [3])
        self.assertEqual(source["pagesFetched"], 4)
        self.assertEqual(source["candidateCount"], 2)
        ajax_entries = source["pages"][1:]
        self.assertEqual([entry["pageNumber"] for entry in ajax_entries], [1, 2, 3])
        self.assertTrue(all(len(entry["sha256"]) == 64 for entry in source["pages"]))
        self.assertTrue(all(len(entry["payloadSha256"]) == 64 for entry in ajax_entries))
        self.assertNotIn("999/QD-UBND", {item.decision_no for item in candidates})

    def test_ajax_pagination_fails_closed_if_data_returns_after_an_empty_page(self):
        source_url = "https://good.haiphong.gov.vn/thu-tuc-hanh-chinh"
        html = b"""
        <script>
          var maxPage = parseInt(3);
          $.ajax({
            url: "/DesktopModule/UIArticleInMenu/ArticleInMenuPagination.aspx/LoadArticle",
            data: {
              article_category_id: 123, categoryIds: "123, 124", site_id: 77,
              page: chosenPage, page_size: 10, keyword: "", date_begin: "", date_end: "",
              show_no: "False", show_post_date: "False", num_of_text: 0,
              show_view_count: "False", filter_order_in_list: "False", is_default: "False",
              new: "False", number_of_day: 3, no: 0, articlelang: "vi-VN",
              is_authenticated: "False"
            },
            success: function (result) {}
          });
        </script>
        """
        ajax_pages = {
            "1": (
                b'<ul class="ArticleList"><a href="/quyet-dinh-so-123-qd-ubnd-ngay-18-9-2026-cong-bo-thu-tuc-hanh-chinh">Quyet dinh 123</a></ul>',
                "text/html; charset=utf-8",
            ),
            "2": (b"", "text/html; charset=utf-8"),
            "3": (
                b'<ul class="ArticleList"><a href="/quyet-dinh-so-124-qd-ubnd-ngay-19-9-2026-cong-bo-thu-tuc-hanh-chinh">Quyet dinh 124</a></ul>',
                "text/html; charset=utf-8",
            ),
        }
        config = {
            "maxPagesPerSource": 4,
            "listingSources": [{"id": "good", "url": source_url}],
        }

        with (
            patch.object(scanner, "fetch_bytes", return_value=(html, "text/html; charset=utf-8")),
            patch.object(
                scanner,
                "fetch_form_bytes",
                side_effect=lambda url, form_data, referer, timeout=35: ajax_pages[form_data["page"]],
            ),
        ):
            _, errors = scanner.discover_candidates(config)

        self.assertEqual(len(errors), 1)
        self.assertIn("pagination returned data on page 3 after empty page(s) [2]", errors[0]["error"])

    def test_ajax_pagination_uses_server_rendered_first_page_when_ajax_page_one_is_empty(self):
        source_url = "https://good.haiphong.gov.vn/thu-tuc-hanh-chinh"
        html = b"""
        <div class="ArticleOfCat">
          <a href="/quyet-dinh-so-777-qd-ubnd-ngay-20-9-2026-cong-bo-danh-muc-thu-tuc-hanh-chinh">
            Quyet dinh so 777/QD-UBND cong bo danh muc thu tuc hanh chinh
          </a>
        </div>
        <script>
          var maxPage = parseInt(3);
          $.ajax({
            url: "/DesktopModule/UIArticleInMenu/ArticleInMenuPagination.aspx/LoadArticle",
            data: {
              article_category_id: 123, categoryIds: "123, 124", site_id: 77,
              page: chosenPage, page_size: 10, keyword: "", date_begin: "", date_end: "",
              show_no: "False", show_post_date: "True", num_of_text: 0,
              show_view_count: "False", filter_order_in_list: "False", is_default: "False",
              new: "False", number_of_day: 3, no: -15, articlelang: "vi-VN",
              is_authenticated: "False"
            },
            success: function (result) {}
          });
        </script>
        """
        ajax_pages = {
            "1": (b"", "text/html; charset=utf-8"),
            "2": (
                b'<ul class="ArticleList"><a href="/quyet-dinh-so-778-qd-ubnd-ngay-21-9-2026-cong-bo-danh-muc-thu-tuc-hanh-chinh">Quyet dinh so 778/QD-UBND cong bo danh muc thu tuc hanh chinh</a></ul>',
                "text/html; charset=utf-8",
            ),
            "3": (b"", "text/html; charset=utf-8"),
        }
        config = {
            "maxPagesPerSource": 4,
            "listingSources": [{
                "id": "good",
                "url": source_url,
                "authority": "Good",
                "authorityType": "city_portal",
                "sourceRole": "primary_decision_listing",
                "legalUse": "primary_publication",
            }],
        }
        snapshot = {}
        with (
            patch.object(scanner, "fetch_bytes", return_value=(html, "text/html; charset=utf-8")),
            patch.object(
                scanner,
                "fetch_form_bytes",
                side_effect=lambda url, form_data, referer, timeout=35: ajax_pages[form_data["page"]],
            ) as fetch_form,
        ):
            candidates, errors = scanner.discover_candidates(config, snapshot)

        self.assertEqual(errors, [])
        self.assertEqual({item.decision_no.split("/", 1)[0] for item in candidates}, {"777", "778"})
        self.assertEqual(fetch_form.call_count, 3)
        source = snapshot["sources"][0]
        self.assertEqual(source["pages"][0]["candidateCollection"], "server_rendered_html")
        self.assertEqual(source["pages"][0]["candidateCount"], 1)
        self.assertEqual(source["ajaxEmptyPages"], [1, 3])
        self.assertEqual(source["ajaxLastNonEmptyPage"], 2)
        self.assertEqual(source["pagesFetched"], 4)
        self.assertEqual(source["candidateCount"], 2)

    def test_ajax_pagination_blocks_when_static_page_one_has_no_following_ajax_data(self):
        source_url = "https://good.haiphong.gov.vn/thu-tuc-hanh-chinh"
        html = b"""
        <div class="ArticleOfCat">
          <a href="/quyet-dinh-so-777-qd-ubnd-ngay-20-9-2026-cong-bo-danh-muc-thu-tuc-hanh-chinh">
            Quyet dinh so 777/QD-UBND cong bo danh muc thu tuc hanh chinh
          </a>
        </div>
        <script>
          var maxPage = parseInt(3);
          $.ajax({
            url: "/DesktopModule/UIArticleInMenu/ArticleInMenuPagination.aspx/LoadArticle",
            data: {
              article_category_id: 123, categoryIds: "123, 124", site_id: 77,
              page: chosenPage, page_size: 10, keyword: "", date_begin: "", date_end: "",
              show_no: "False", show_post_date: "True", num_of_text: 0,
              show_view_count: "False", filter_order_in_list: "False", is_default: "False",
              new: "False", number_of_day: 3, no: -15, articlelang: "vi-VN",
              is_authenticated: "False"
            },
            success: function (result) {}
          });
        </script>
        """
        config = {
            "maxPagesPerSource": 4,
            "listingSources": [{"id": "good", "url": source_url}],
        }
        with (
            patch.object(scanner, "fetch_bytes", return_value=(html, "text/html; charset=utf-8")),
            patch.object(
                scanner,
                "fetch_form_bytes",
                return_value=(b"", "text/html; charset=utf-8"),
            ) as fetch_form,
        ):
            candidates, errors = scanner.discover_candidates(config)

        self.assertEqual({item.decision_no.split("/", 1)[0] for item in candidates}, {"777"})
        self.assertEqual(fetch_form.call_count, 3)
        self.assertEqual(len(errors), 1)
        self.assertIn("AJAX pages 2..3 returned no content", errors[0]["error"])

    def test_ajax_pagination_fails_closed_on_empty_page_before_declared_final_page(self):
        source_url = "https://good.haiphong.gov.vn/thu-tuc-hanh-chinh"
        html = b"""
        <script>
          var maxPage = parseInt(3);
          $.ajax({
            url: "/DesktopModule/UIArticleInMenu/ArticleInMenuPagination.aspx/LoadArticle",
            data: {
              article_category_id: 123, categoryIds: "123, 124", site_id: 77,
              page: chosenPage, page_size: 10, keyword: "", date_begin: "", date_end: "",
              show_no: "False", show_post_date: "True", num_of_text: 0,
              show_view_count: "False", filter_order_in_list: "False", is_default: "False",
              new: "False", number_of_day: 3, no: -15, articlelang: "vi-VN",
              is_authenticated: "False"
            },
            success: function (result) {}
          });
        </script>
        """
        ajax_pages = {
            "1": (
                b'<ul class="ArticleList"><a href="/quyet-dinh-so-123-qd-ubnd-ngay-18-9-2026-cong-bo-thu-tuc-hanh-chinh">Quyet dinh so 123</a></ul>',
                "text/html; charset=utf-8",
            ),
            "2": (b"", "text/html; charset=utf-8"),
            "3": (b"", "text/html; charset=utf-8"),
        }
        config = {
            "maxPagesPerSource": 4,
            "listingSources": [{"id": "good", "url": source_url}],
        }

        with (
            patch.object(scanner, "fetch_bytes", return_value=(html, "text/html; charset=utf-8")),
            patch.object(
                scanner,
                "fetch_form_bytes",
                side_effect=lambda url, form_data, referer, timeout=35: ajax_pages[form_data["page"]],
            ),
        ):
            candidates, errors = scanner.discover_candidates(config)

        self.assertEqual({item.decision_no.split("/", 1)[0] for item in candidates}, {"123"})
        self.assertEqual(len(errors), 1)
        self.assertIn("empty page(s) [2] before declared final page 3", errors[0]["error"])

    def test_scan_only_does_not_write_snapshot_index_manifest_or_pdfs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "config.json"
            manifest_path = root / "manifest.json"
            index_path = root / "index.json"
            snapshot_path = root / "snapshot.json"
            config_path.write_text(json.dumps({"baselineDate": "2026-09-07", "listingSources": []}), encoding="utf-8")
            manifest_path.write_text(json.dumps({"decisions": []}), encoding="utf-8")
            index_path.write_text(json.dumps({"articles": []}), encoding="utf-8")
            before = {path: path.read_bytes() for path in (config_path, manifest_path, index_path)}

            with (
                patch.object(scanner, "CONFIG_PATH", config_path),
                patch.object(scanner, "MANIFEST_PATH", manifest_path),
                patch.object(scanner, "INDEX_PATH", index_path),
                patch.object(scanner, "SNAPSHOT_PATH", snapshot_path),
                patch.object(scanner, "discover_candidates", return_value=([], [])),
                patch.object(scanner, "write_json_if_changed") as write_json,
                patch.object(scanner.sys, "argv", ["update_official_sources.py", "--online", "--scan-only"]),
                contextlib.redirect_stdout(io.StringIO()) as output,
            ):
                result = scanner.main()

            self.assertEqual(result, 0)
            payload = json.loads(output.getvalue())
            self.assertEqual(payload["status"], "scan_only_complete")
            self.assertFalse(payload["writesPerformed"])
            write_json.assert_not_called()
            self.assertEqual({path: path.read_bytes() for path in before}, before)
            self.assertFalse(snapshot_path.exists())

if __name__ == "__main__":
    unittest.main()
