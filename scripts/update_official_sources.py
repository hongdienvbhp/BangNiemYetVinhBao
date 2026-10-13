#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Discover and stage official Hai Phong / Vinh Bao TTHC decision updates.

The scanner is intentionally provenance-first:
- it only discovers from configured official government portals;
- legal status is never inferred from third-party data;
- internal/process-only decisions are recorded but never fed to public Master Data;
- a new public decision is ingestible only when the article exposes an official PDF;
- existing decision numbers are never silently overwritten by a newly discovered source.

On the first run, the current listing is recorded as a baseline. Subsequent runs
only act on newly observed article URLs, which prevents historic pages from being
re-imported as if they were new.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import re
import sys
import unicodedata
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "data/source-audit/official-source-config.json"
MANIFEST_PATH = ROOT / "data/source-audit/official-decision-manifest.json"
INDEX_PATH = ROOT / "data/source-audit/official-source-index.json"
SNAPSHOT_PATH = ROOT / "data/source-audit/official-source-snapshot.json"
AUTO_PDF_DIR = ROOT / "data/source-audit/city-decisions"

USER_AGENT = "BangNiemYetVinhBao-Official-TTHC-Monitor/1.0"
DECISION_URL_RE = re.compile(
    r"quyet-dinh-so-(?P<num>\d+)-qd-ubnd-ngay-(?P<day>\d{1,2})-(?P<month>\d{1,2})-(?P<year>\d{4})",
    re.IGNORECASE,
)
DECISION_TEXT_RE = re.compile(
    r"(?:Quyết\s*định\s*(?:số\s*)?:?\s*)(?P<num>\d+)\s*/\s*Q(?:Đ|D)-UBND",
    re.IGNORECASE,
)
DATE_TEXT_RE = re.compile(
    r"(?:ngày\s*)(?P<day>\d{1,2})\s*[/-]\s*(?P<month>\d{1,2})\s*[/-]\s*(?P<year>\d{4})",
    re.IGNORECASE,
)
PDF_RE = re.compile(r"https?://[^\"'<>\s]+\.pdf(?:\?[^\"'<>\s]*)?", re.IGNORECASE)


def fold(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value or "")
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn").lower()


def load_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json_if_changed(path: Path, payload: dict) -> bool:
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if path.exists() and path.read_text(encoding="utf-8-sig") == rendered:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered, encoding="utf-8")
    return True


def fetch_bytes(url: str, timeout: int = 35) -> tuple[bytes, str]:
    req = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.8",
        },
    )
    with urlopen(req, timeout=timeout) as resp:
        body = resp.read()
        content_type = resp.headers.get("Content-Type", "")
    return body, content_type


def fetch_form_bytes(
    url: str,
    form_data: dict[str, str],
    referer: str,
    timeout: int = 35,
) -> tuple[bytes, str]:
    parsed_referer = urlparse(referer)
    req = Request(
        url,
        data=urlencode(form_data).encode("utf-8"),
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "Referer": referer,
            "Origin": f"{parsed_referer.scheme}://{parsed_referer.netloc}",
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        },
        method="POST",
    )
    with urlopen(req, timeout=timeout) as resp:
        body = resp.read()
        content_type = resp.headers.get("Content-Type", "")
    return body, content_type


def decode_html(body: bytes, content_type: str) -> str:
    charset = "utf-8"
    match = re.search(r"charset=([\w-]+)", content_type or "", re.I)
    if match:
        charset = match.group(1)
    try:
        return body.decode(charset, errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")


def extract_ajax_pagination_config(page_html: str, source_url: str) -> dict | None:
    """Read the existing official portal's AJAX pagination contract from its script."""
    script_blocks = re.findall(
        r"<script\b[^>]*>(.*?)</script\s*>",
        page_html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    matching_scripts = [
        script for script in script_blocks
        if "ArticleInMenuPagination.aspx/LoadArticle" in script
    ]
    if not matching_scripts:
        return None
    if len(matching_scripts) != 1:
        raise RuntimeError(
            f"ambiguous AJAX pagination configuration: {len(matching_scripts)} scripts"
        )

    script = matching_scripts[0]
    endpoint_match = re.search(
        r"\burl\s*:\s*([\"'])([^\"']*ArticleInMenuPagination\.aspx/LoadArticle)\1",
        script,
        flags=re.IGNORECASE,
    )
    if not endpoint_match:
        raise RuntimeError("AJAX pagination endpoint was not recognized")
    endpoint = urljoin(source_url, endpoint_match.group(2))
    source_parts = urlparse(source_url)
    endpoint_parts = urlparse(endpoint)
    expected_path = "/DesktopModule/UIArticleInMenu/ArticleInMenuPagination.aspx/LoadArticle"
    if (
        endpoint_parts.scheme not in {"http", "https"}
        or endpoint_parts.scheme != source_parts.scheme
        or endpoint_parts.netloc.lower() != source_parts.netloc.lower()
        or not endpoint_parts.path.endswith(expected_path)
        or endpoint_parts.query
        or endpoint_parts.fragment
    ):
        raise RuntimeError("AJAX pagination endpoint is outside the approved source origin/path")

    ajax_start = script.rfind("$.ajax", 0, endpoint_match.start())
    if ajax_start < 0:
        raise RuntimeError("AJAX pagination request wrapper was not found")
    ajax_script = script[ajax_start:]
    data_match = re.search(
        r"\bdata\s*:\s*\{(.*?)\}\s*,\s*success\s*:",
        ajax_script,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not data_match:
        raise RuntimeError("AJAX pagination form data was not recognized")

    form_data: dict[str, str] = {}
    property_pattern = re.compile(
        r"""(?P<key>[A-Za-z_]\w*)\s*:\s*"""
        r"""(?P<value>"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[^,\r\n}]+)(?=[,\r\n}]|$)"""
    )
    for match in property_pattern.finditer(data_match.group(1)):
        key = match.group("key")
        raw_value = match.group("value").strip()
        if raw_value.startswith('"') and raw_value.endswith('"'):
            try:
                value = json.loads(raw_value)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"invalid AJAX form string for {key}") from exc
        elif raw_value.startswith("'") and raw_value.endswith("'"):
            value = raw_value[1:-1].replace(r"\'", "'").replace(r"\\", "\\")
        elif re.fullmatch(r"(?:-?\d+|[A-Za-z_]\w*)", raw_value):
            value = raw_value
        else:
            raise RuntimeError(f"unsupported AJAX form value for {key}")
        form_data[key] = str(value)

    required_fields = {
        "article_category_id", "categoryIds", "site_id", "page", "page_size",
        "keyword", "date_begin", "date_end", "show_no", "show_post_date",
        "num_of_text", "show_view_count", "filter_order_in_list", "is_default",
        "new", "number_of_day", "no", "articlelang", "is_authenticated",
    }
    missing_fields = sorted(required_fields - form_data.keys())
    if missing_fields:
        raise RuntimeError("AJAX pagination form missing fields: " + ", ".join(missing_fields))
    if form_data["page"].strip() != "chosenPage":
        raise RuntimeError("AJAX pagination page field is not bound to the selected page")
    if not form_data["categoryIds"].strip() or not form_data["article_category_id"].isdigit():
        raise RuntimeError("AJAX pagination category configuration is invalid")
    if not form_data["site_id"].isdigit() or not form_data["page_size"].isdigit():
        raise RuntimeError("AJAX pagination site/page-size configuration is invalid")
    if int(form_data["page_size"]) < 1:
        raise RuntimeError("AJAX pagination page size must be positive")

    max_page_match = re.search(
        r"\bmaxPage\s*=\s*parseInt\(\s*(\d+)\s*\)",
        script,
        flags=re.IGNORECASE,
    )
    if not max_page_match:
        raise RuntimeError("AJAX pagination declared maximum page was not recognized")
    max_page = int(max_page_match.group(1))
    if max_page < 1 or max_page > 500:
        raise RuntimeError(f"AJAX pagination declared page count is invalid: {max_page}")

    return {
        "endpoint": endpoint,
        "formData": form_data,
        "maxPage": max_page,
        "pageSize": int(form_data["page_size"]),
    }


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self.next_links: list[str] = []
        self.numbered_page_links: list[tuple[str, str]] = []
        self.title_parts: list[str] = []
        self.in_title = False
        self._anchor_href = ""
        self._anchor_attrs: dict[str, str] = {}
        self._anchor_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = {k.lower(): (v or "") for k, v in attrs}
        if tag.lower() == "title":
            self.in_title = True
        if tag.lower() == "a":
            self._anchor_href = attrs_map.get("href", "")
            self._anchor_attrs = attrs_map
            self._anchor_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self.in_title = False
        if tag.lower() == "a" and self._anchor_href:
            text = re.sub(r"\s+", " ", " ".join(self._anchor_parts)).strip()
            self.links.append((self._anchor_href, text))
            if re.fullmatch(r"\d{1,3}", text):
                self.numbered_page_links.append((self._anchor_href.strip(), text))
            rel_tokens = set(self._anchor_attrs.get("rel", "").lower().split())
            class_tokens = set(re.split(r"\s+", self._anchor_attrs.get("class", "").lower()))
            label = fold(" ".join((text, self._anchor_attrs.get("aria-label", ""), self._anchor_attrs.get("title", ""))).strip())
            next_classes = {"next", "pager-next", "pagination-next", "page-next", "next-page", "older"}
            next_labels = {"next", "older", "newer", "trang sau", "sau", "tiep", "tiep theo", "ke tiep", "»", "›", "→"}
            href = self._anchor_href.strip()
            is_non_navigable = (
                not href
                or href.startswith("#")
                or href.lower().startswith(("javascript:", "mailto:"))
            )
            if not is_non_navigable and (
                "next" in rel_tokens
                or bool(class_tokens & next_classes)
                or label in next_labels
                or label.startswith(("next ", "older ", "trang sau", "tiep theo", "ke tiep"))
            ):
                self.next_links.append(href)
            self._anchor_href = ""
            self._anchor_attrs = {}
            self._anchor_parts = []

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)
        if self._anchor_href:
            self._anchor_parts.append(data)

    @property
    def title(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self.title_parts)).strip()


@dataclass(frozen=True)
class Candidate:
    source_id: str
    source_url: str
    source_authority: str
    authority_type: str
    source_role: str
    legal_use: str
    article_url: str
    anchor_text: str
    decision_no: str
    decision_date: str


def strict_iso_date(year: str, month: str, day: str) -> str:
    """Return an ISO date only when it is a real calendar date; otherwise unknown."""
    try:
        return dt.date(int(year), int(month), int(day)).isoformat()
    except (TypeError, ValueError):
        return ""


def parse_decision_identity(url: str, text: str = "") -> tuple[str, str]:
    match = DECISION_URL_RE.search(url)
    if match:
        number = match.group("num")
        date = strict_iso_date(match.group("year"), match.group("month"), match.group("day"))
        return f"{number}/QĐ-UBND", date

    text_decision = DECISION_TEXT_RE.search(text or "")
    text_date = DATE_TEXT_RE.search(text or "")
    number = text_decision.group("num") if text_decision else ""
    date = ""
    if text_date:
        date = strict_iso_date(text_date.group("year"), text_date.group("month"), text_date.group("day"))
    return (f"{number}/QĐ-UBND" if number else ""), date


def is_candidate_link(url: str, anchor_text: str) -> bool:
    value = fold(url + " " + anchor_text)
    has_decision_signal = "quyet-dinh" in value or "quyet dinh" in value
    has_tthc_signal = "thu-tuc-hanh-chinh" in value or "thu tuc hanh chinh" in value
    # Listing pages include site-wide "Tin m?i" links. Require an explicit TTHC
    # signal so unrelated decisions elsewhere on the portal are never staged.
    return has_decision_signal and has_tthc_signal


def classify_title(title: str, config: dict) -> str:
    value = fold(title)
    for marker in config.get("internalDecisionMarkers", []):
        if fold(marker) in value:
            return "internal_process"
    # Quyết định ủy quyền/phân công giải quyết TTHC là quyết định tổ chức thực hiện,
    # không phải quyết định công bố danh mục TTHC cho người dân.
    if "uy quyen cho" in value and "thu tuc hanh chinh" in value:
        return "internal_process"
    # Local portals can republish ministry decisions and occasionally carry a
    # misleading QD-UBND slug. Do not ingest those as city legal decisions.
    if re.search(r"\bcua bo\b", value) and not any(
        marker in value for marker in ("ubnd thanh pho", "uy ban nhan dan thanh pho")
    ):
        return "external_reference"
    for marker in config.get("publicDecisionMarkers", []):
        if fold(marker) in value:
            return "public_tthc"
    if "cong bo" in value and "thu tuc hanh chinh" in value:
        return "public_tthc"
    # Trang TTHC có thể lẫn quyết định/kế hoạch CCHC không công bố TTHC.
    if "thu tuc hanh chinh" not in value:
        return "non_tthc"
    return "needs_review"


def infer_field(title: str) -> str:
    clean = html.unescape(re.sub(r"\s+", " ", title or "")).strip()
    patterns = [
        r"lĩnh vực\s+(.+?)\s+thuộc\s+phạm\s+vi",
        r"lĩnh vực\s+(.+?)\s+thuộc\s+thẩm\s+quyền",
        r"lĩnh vực\s+(.+?)\s+do\s+Sở",
        r"lĩnh vực\s+(.+?)\s+của\s+Sở",
    ]
    for pattern in patterns:
        match = re.search(pattern, clean, re.IGNORECASE)
        if match:
            value = match.group(1).strip(" .,:;-")
            if 2 <= len(value) <= 120:
                return value.upper()
    return ""


def extract_article_details(url: str, config: dict) -> dict:
    body, content_type = fetch_bytes(url)
    page = decode_html(body, content_type)
    parser = PageParser()
    parser.feed(page)
    title = html.unescape(parser.title)
    decision_no, decision_date = parse_decision_identity(url, title)
    allowed_hosts = {str(host).lower() for host in config.get("allowedAttachmentHosts", [])}
    pdf_urls = []
    for match in PDF_RE.finditer(page):
        candidate_pdf = html.unescape(match.group(0))
        host = (urlparse(candidate_pdf).hostname or "").lower()
        if allowed_hosts and host not in allowed_hosts:
            continue
        if candidate_pdf not in pdf_urls:
            pdf_urls.append(candidate_pdf)
    preferred = ""
    if decision_no:
        number = decision_no.split("/", 1)[0]
        preferred = next((x for x in pdf_urls if re.search(rf"(?:qd[-_ ]?{re.escape(number)}|/{re.escape(number)}[-_])", x, re.I)), "")
    if not preferred and pdf_urls:
        preferred = pdf_urls[0]

    published_date = ""
    published_patterns = [
        r"(?:article:published_time|datePublished)[^>]{0,180}(\d{4}-\d{2}-\d{2})",
        r"(?:Ngày đăng|Ngày cập nhật)[^0-9]{0,40}(\d{1,2}/\d{1,2}/\d{4})",
    ]
    for pattern in published_patterns:
        match = re.search(pattern, page, re.I)
        if not match:
            continue
        raw = match.group(1)
        if "/" in raw:
            d, m, y = raw.split("/")
            published_date = strict_iso_date(y, m, d)
        else:
            published_date = strict_iso_date(raw[0:4], raw[5:7], raw[8:10])
        break

    return {
        "title": title,
        "decisionNo": decision_no,
        "decisionDate": decision_date,
        "publishedDate": published_date,
        "classification": classify_title(title, config),
        "field": infer_field(title),
        "pdfUrl": preferred,
        "allPdfUrls": pdf_urls,
    }


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def download_pdf(url: str, decision_no: str) -> tuple[str, str]:
    body, content_type = fetch_bytes(url, timeout=60)
    if not (body.startswith(b"%PDF") or "pdf" in fold(content_type)):
        raise RuntimeError(f"Attachment for {decision_no} is not a PDF: {content_type}")
    number = decision_no.split("/", 1)[0] if decision_no else "unknown"
    AUTO_PDF_DIR.mkdir(parents=True, exist_ok=True)
    path = AUTO_PDF_DIR / f"QD-{number}.pdf"
    digest = sha256_bytes(body)
    if path.exists():
        existing = hashlib.sha256(path.read_bytes()).hexdigest()
        if existing == digest:
            return path.relative_to(ROOT).as_posix(), digest
        # Never silently overwrite legal evidence.
        versioned = AUTO_PDF_DIR / f"QD-{number}-{digest[:12]}.pdf"
        versioned.write_bytes(body)
        return versioned.relative_to(ROOT).as_posix(), digest
    path.write_bytes(body)
    return path.relative_to(ROOT).as_posix(), digest


def discover_candidates(
    config: dict,
    snapshot_metadata: dict | None = None,
) -> tuple[list[Candidate], list[dict[str, str]]]:
    """Read configured official listings, following explicit next and numbered page URLs.

    No page URL is synthesized. If a contiguous numbered pagination control exists but
    its navigable same-origin URLs cannot be extracted, the source snapshot is incomplete.
    """
    found: dict[str, Candidate] = {}
    source_errors: list[dict[str, str]] = []
    source_snapshots: list[dict] = []

    for source in config.get("listingSources", []):
        source_url = str(source["url"])
        source_id = str(source.get("id", ""))
        source_origin = (urlparse(source_url).scheme.lower(), urlparse(source_url).netloc.lower())
        max_pages = source.get("maxPages", config.get("maxPagesPerSource", 100))
        source_snapshot = {
            "sourceId": source_id,
            "sourceUrl": source_url,
            "pagesFetched": 0,
            "candidateCount": 0,
            "pages": [],
        }

        def normalized_url(value: str) -> str:
            return urlunparse(urlparse(value)._replace(fragment=""))

        def is_same_origin_page(value: str) -> bool:
            parsed = urlparse(value)
            return (
                parsed.scheme.lower() in {"http", "https"}
                and (parsed.scheme.lower(), parsed.netloc.lower()) == source_origin
            )

        try:
            max_pages = int(max_pages)
            if max_pages < 1 or max_pages > 500:
                raise ValueError("maxPagesPerSource must be between 1 and 500")

            source_url = normalized_url(source_url)
            page_queue = [source_url]
            queued_urls = {source_url}
            visited_urls: set[str] = set()

            while page_queue:
                if source_snapshot["pagesFetched"] >= max_pages:
                    raise RuntimeError(
                        f"pagination page limit reached ({max_pages}) while listing pages remained"
                    )

                current_url = normalized_url(page_queue.pop(0))
                if current_url in visited_urls:
                    continue
                if not is_same_origin_page(current_url):
                    raise RuntimeError(f"pagination next link leaves source origin: {current_url}")
                visited_urls.add(current_url)

                body, content_type = fetch_bytes(current_url)
                page = decode_html(body, content_type)
                page_parser = PageParser()
                page_parser.feed(page)
                digest = sha256_bytes(body)
                ajax_config = (
                    extract_ajax_pagination_config(page, source_url)
                    if current_url == source_url
                    else None
                )

                if ajax_config:
                    ajax_max_page = ajax_config["maxPage"]
                    if source_snapshot["pagesFetched"] + 1 + ajax_max_page > max_pages:
                        raise RuntimeError(
                            f"AJAX pagination page limit reached ({max_pages}) "
                            f"for {ajax_max_page} declared pages plus initial HTML"
                        )

                    # The static HTML contains unrelated article widgets and # placeholder
                    # arrow controls. Candidate collection must use the configured AJAX list.
                    source_snapshot["paginationMode"] = "ajax_form_post"
                    source_snapshot["ajaxEndpoint"] = ajax_config["endpoint"]
                    source_snapshot["ajaxDeclaredMaxPage"] = ajax_max_page
                    source_snapshot["ajaxPageSize"] = ajax_config["pageSize"]
                    source_snapshot["pages"].append({
                        "url": current_url,
                        "requestMethod": "GET",
                        "sha256": digest,
                        "linkCount": len(page_parser.links),
                        "candidateCount": 0,
                        "candidateCollection": "ajax",
                    })
                    source_snapshot["pagesFetched"] += 1

                    empty_pages: list[int] = []
                    last_non_empty_page = 0
                    server_rendered_initial_page = False
                    nonempty_ajax_page_after_initial = False
                    for page_number in range(1, ajax_max_page + 1):
                        form_data = dict(ajax_config["formData"])
                        form_data["page"] = str(page_number)
                        encoded_form = urlencode(form_data).encode("utf-8")
                        response_body, response_type = fetch_form_bytes(
                            ajax_config["endpoint"],
                            form_data,
                            source_url,
                        )
                        response_html = decode_html(response_body, response_type)
                        response_parser = PageParser()
                        response_parser.feed(response_html)
                        response_empty = not response_body.strip()
                        page_candidate_count = 0

                        if not response_empty:
                            if "ArticleList" not in response_html:
                                raise RuntimeError(
                                    f"AJAX page {page_number} lacks the expected ArticleList container"
                                )
                            for href, anchor in response_parser.links:
                                if not href:
                                    continue
                                article_url = urljoin(source_url, href)
                                if urlparse(article_url).netloc.lower() != urlparse(source_url).netloc.lower():
                                    continue
                                if not is_candidate_link(article_url, anchor):
                                    continue
                                decision_no, decision_date = parse_decision_identity(article_url, anchor)
                                key = article_url.rstrip("/")
                                found[key] = Candidate(
                                    source_id=source_id,
                                    source_url=source_url,
                                    source_authority=source.get("authority", ""),
                                    authority_type=source.get("authorityType", ""),
                                    source_role=source.get("sourceRole", ""),
                                    legal_use=source.get("legalUse", ""),
                                    article_url=article_url,
                                    anchor_text=anchor,
                                    decision_no=decision_no,
                                    decision_date=decision_date,
                                )
                                page_candidate_count += 1

                        source_snapshot["pages"].append({
                            "url": ajax_config["endpoint"],
                            "requestMethod": "POST",
                            "listingUrl": source_url,
                            "pageNumber": page_number,
                            "pageSize": ajax_config["pageSize"],
                            "payloadSha256": sha256_bytes(encoded_form),
                            "sha256": sha256_bytes(response_body),
                            "linkCount": len(response_parser.links),
                            "candidateCount": page_candidate_count,
                        })
                        source_snapshot["pagesFetched"] += 1
                        source_snapshot["candidateCount"] += page_candidate_count

                        if response_empty:
                            empty_pages.append(page_number)
                            if page_number == 1:
                                # Some official portals render page 1 in the GET HTML and
                                # only use the AJAX endpoint for navigation after page 1.
                                # Accept that fallback only when the GET page itself contains
                                # candidate links; still require actual AJAX data for later pages.
                                static_candidate_count = 0
                                for href, anchor in page_parser.links:
                                    if not href:
                                        continue
                                    article_url = urljoin(source_url, href)
                                    if urlparse(article_url).netloc.lower() != urlparse(source_url).netloc.lower():
                                        continue
                                    if not is_candidate_link(article_url, anchor):
                                        continue
                                    decision_no, decision_date = parse_decision_identity(article_url, anchor)
                                    key = article_url.rstrip("/")
                                    found[key] = Candidate(
                                        source_id=source_id,
                                        source_url=source_url,
                                        source_authority=source.get("authority", ""),
                                        authority_type=source.get("authorityType", ""),
                                        source_role=source.get("sourceRole", ""),
                                        legal_use=source.get("legalUse", ""),
                                        article_url=article_url,
                                        anchor_text=anchor,
                                        decision_no=decision_no,
                                        decision_date=decision_date,
                                    )
                                    static_candidate_count += 1
                                if static_candidate_count == 0:
                                    raise RuntimeError(
                                        "AJAX page 1 was empty and the initial HTML contained no candidate links"
                                    )
                                server_rendered_initial_page = True
                                last_non_empty_page = 1
                                source_snapshot["pages"][0]["candidateCollection"] = "server_rendered_html"
                                source_snapshot["pages"][0]["candidateCount"] = static_candidate_count
                                source_snapshot["candidateCount"] += static_candidate_count
                        else:
                            invalid_empty_pages = [
                                value for value in empty_pages
                                if value > 1 or not server_rendered_initial_page
                            ]
                            if invalid_empty_pages:
                                raise RuntimeError(
                                    f"AJAX pagination returned data on page {page_number} "
                                    f"after empty page(s) {invalid_empty_pages}"
                                )
                            last_non_empty_page = page_number
                            if page_number > 1:
                                nonempty_ajax_page_after_initial = True

                    source_snapshot["ajaxEmptyPages"] = empty_pages
                    source_snapshot["ajaxLastNonEmptyPage"] = last_non_empty_page
                    if (
                        server_rendered_initial_page
                        and ajax_max_page > 1
                        and not nonempty_ajax_page_after_initial
                    ):
                        raise RuntimeError(
                            f"AJAX pages 2..{ajax_max_page} returned no content after the server-rendered first page"
                        )

                    premature_empty_pages = [
                        page_number
                        for page_number in empty_pages
                        if page_number < ajax_max_page
                        and not (page_number == 1 and server_rendered_initial_page)
                    ]
                    if premature_empty_pages:
                        raise RuntimeError(
                            f"AJAX pagination returned empty page(s) {premature_empty_pages} "
                            f"before declared final page {ajax_max_page}"
                        )
                    next_url = ""
                    continue

                page_candidate_count = 0
                for href, anchor in page_parser.links:
                    if not href:
                        continue
                    article_url = urljoin(current_url, href)
                    if (urlparse(article_url).netloc or "").lower() != source_origin[1]:
                        continue
                    if not is_candidate_link(article_url, anchor):
                        continue
                    decision_no, decision_date = parse_decision_identity(article_url, anchor)
                    key = article_url.rstrip("/")
                    found[key] = Candidate(
                        source_id=source_id,
                        source_url=source["url"],
                        source_authority=source.get("authority", ""),
                        authority_type=source.get("authorityType", ""),
                        source_role=source.get("sourceRole", ""),
                        legal_use=source.get("legalUse", ""),
                        article_url=article_url,
                        anchor_text=anchor,
                        decision_no=decision_no,
                        decision_date=decision_date,
                    )
                    page_candidate_count += 1

                source_snapshot["pages"].append({
                    "url": current_url,
                    "requestMethod": "GET",
                    "sha256": digest,
                    "linkCount": len(page_parser.links),
                    "candidateCount": page_candidate_count,
                })
                source_snapshot["pagesFetched"] += 1
                source_snapshot["candidateCount"] += page_candidate_count

                # Some official portals expose numbered page links but no rel=next.
                # Only follow URLs actually present in HTML; never invent ?page=N.
                numeric_labels = sorted({
                    int(label)
                    for _href, label in page_parser.numbered_page_links
                    if re.fullmatch(r"\d{1,3}", label)
                })
                has_numbered_pagination = len(numeric_labels) >= 3 and any(
                    numeric_labels[i + 1] == numeric_labels[i] + 1
                    and numeric_labels[i + 2] == numeric_labels[i] + 2
                    for i in range(len(numeric_labels) - 2)
                )

                numeric_targets: list[tuple[int, str]] = []
                if has_numbered_pagination:
                    for href, label in page_parser.numbered_page_links:
                        if not re.fullmatch(r"\d{1,3}", label) or not href:
                            continue
                        if href.startswith("#") or href.lower().startswith(("javascript:", "mailto:")):
                            continue
                        resolved = normalized_url(urljoin(current_url, href.strip()))
                        if not is_same_origin_page(resolved):
                            continue
                        numeric_targets.append((int(label), resolved))

                    distinct_numeric_urls = {url for _label, url in numeric_targets}
                    if len(distinct_numeric_urls) < 3:
                        raise RuntimeError(
                            "numeric pagination controls detected but fewer than 3 navigable "
                            "same-origin page URLs were found; refusing a partial source snapshot"
                        )

                    for _label, target_url in sorted(set(numeric_targets), key=lambda item: (item[0], item[1])):
                        if target_url in visited_urls or target_url in queued_urls:
                            continue
                        page_queue.append(target_url)
                        queued_urls.add(target_url)

                next_urls: list[str] = []
                for href in page_parser.next_links:
                    if not href:
                        continue
                    target_url = normalized_url(urljoin(current_url, href))
                    if target_url not in next_urls:
                        next_urls.append(target_url)

                if len(next_urls) > 1:
                    raise RuntimeError(f"ambiguous pagination: {len(next_urls)} distinct next links")

                if next_urls:
                    target_url = next_urls[0]
                    if not is_same_origin_page(target_url):
                        raise RuntimeError(f"pagination next link leaves source origin: {target_url}")
                    if target_url in visited_urls:
                        raise RuntimeError(f"pagination loop detected at {target_url}")
                    if target_url not in queued_urls:
                        page_queue.append(target_url)
                        queued_urls.add(target_url)

        except Exception as exc:
            source_errors.append({
                "sourceId": source_id,
                "sourceUrl": str(source.get("url", "")),
                "authority": str(source.get("authority", "")),
                "pagesFetched": str(source_snapshot["pagesFetched"]),
                "error": f"{type(exc).__name__}: {exc}",
            })
        source_snapshots.append(source_snapshot)

    if snapshot_metadata is not None:
        snapshot_metadata["sources"] = source_snapshots
    return (
        sorted(found.values(), key=lambda x: (x.decision_date, x.decision_no, x.article_url)),
        source_errors,
    )


def source_snapshot_is_complete(source_errors: list[dict[str, str]]) -> bool:
    """A snapshot is complete only when every configured listing source was fetched."""
    return not source_errors


def source_ids_requiring_baseline(config: dict, index_rows: list[dict]) -> set[str]:
    """Return configured source IDs that have never been observed in the source index.

    A newly registered listing source must be baselined on its first successful scan.
    Otherwise every historic URL already present on that listing is misclassified as a
    new decision and can trigger an expensive historic PDF backfill.
    """
    configured = {
        str(source.get("id") or "")
        for source in config.get("listingSources", [])
        if source.get("id")
    }
    observed = {
        str(row.get("sourceId") or "")
        for row in index_rows
        if row.get("sourceId")
    }
    return configured - observed


def reconcile_missing_manifest_dates(manifest_by_no: dict[str, dict], candidates: list[Candidate]) -> dict[str, str]:
    """Fill a missing decision date only when official listings agree on one date."""
    dates_by_no: dict[str, set[str]] = {}
    for candidate in candidates:
        if candidate.decision_no and candidate.decision_date:
            dates_by_no.setdefault(candidate.decision_no, set()).add(candidate.decision_date)

    enriched: dict[str, str] = {}
    for decision_no, entry in manifest_by_no.items():
        if entry.get("classification") != "public_tthc" or entry.get("decisionDate"):
            continue
        dates = dates_by_no.get(decision_no, set())
        if len(dates) == 1:
            decision_date = next(iter(dates))
            entry["decisionDate"] = decision_date
            enriched[decision_no] = decision_date
    return enriched


def index_record(candidate: Candidate, *, classification: str, title: str = "", status: str = "") -> dict:
    return {
        "sourceId": candidate.source_id,
        "sourceUrl": candidate.source_url,
        "sourceAuthority": candidate.source_authority,
        "authorityType": candidate.authority_type,
        "sourceRole": candidate.source_role,
        "legalUse": candidate.legal_use,
        "articleUrl": candidate.article_url,
        "decisionNo": candidate.decision_no,
        "decisionDate": candidate.decision_date,
        "title": title or candidate.anchor_text,
        "classification": classification,
        "status": status,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--online", action="store_true", help="Fetch official listing pages and stage newly discovered decisions.")
    parser.add_argument("--initialize", action="store_true", help="Create the baseline source index from current official listings.")
    parser.add_argument(
        "--scan-only",
        action="store_true",
        help="Scan official sources and emit page hashes without writing snapshot, index, manifest, or PDFs.",
    )
    args = parser.parse_args()

    if args.scan_only and (not args.online or args.initialize):
        parser.error("--scan-only requires --online and cannot be combined with --initialize")
    if not args.online and not args.initialize:
        parser.error("Use --online or --initialize")

    config = load_json(CONFIG_PATH, {})
    manifest = load_json(
        MANIFEST_PATH,
        {"format": "official-tthc-decision-manifest", "version": 1, "decisions": []},
    )
    index = load_json(
        INDEX_PATH,
        {
            "format": "official-tthc-source-index",
            "version": 1,
            "baselineDate": config.get("baselineDate", ""),
            "articles": [],
        },
    )

    manifest_by_no = {str(x.get("decisionNo") or ""): x for x in manifest.get("decisions", []) if x.get("decisionNo")}
    index_rows = index.setdefault("articles", [])
    known_urls = {str(x.get("articleUrl") or "").rstrip("/"): x for x in index_rows}
    index_positions = {
        str(row.get("articleUrl") or "").rstrip("/"): pos
        for pos, row in enumerate(index_rows)
        if row.get("articleUrl")
    }

    def set_index_record(record: dict) -> None:
        key = str(record.get("articleUrl") or "").rstrip("/")
        if key in index_positions:
            index_rows[index_positions[key]] = record
        else:
            index_positions[key] = len(index_rows)
            index_rows.append(record)

    initializing = args.initialize or not INDEX_PATH.exists()
    source_baselines = source_ids_requiring_baseline(config, index_rows)

    snapshot_metadata = {}
    candidates, source_errors = discover_candidates(config, snapshot_metadata)
    # Fail closed before processing candidates or writing index/manifest/PDFs.
    # A partial listing scan is not a complete snapshot and must not be published.
    if not source_snapshot_is_complete(source_errors):
        print(
            json.dumps(
                {
                    "snapshotComplete": False,
                    "sourceErrors": source_errors,
                    "sourceErrorCount": len(source_errors),
                    "sources": snapshot_metadata.get("sources", []),
                    "indexChanged": False,
                    "manifestChanged": False,
                    "snapshotChanged": False,
                    "writesPerformed": False,
                    "status": "blocked_incomplete_source_snapshot",
                },
                ensure_ascii=True,
                indent=2,
            )
        )
        return 2

    if args.scan_only:
        print(json.dumps(
            {
                "snapshotComplete": True,
                "sourceCount": len(snapshot_metadata.get("sources", [])),
                "sourceErrorCount": 0,
                "sourceErrors": [],
                "sources": snapshot_metadata.get("sources", []),
                "candidateUrlCount": len(candidates),
                "indexChanged": False,
                "manifestChanged": False,
                "snapshotChanged": False,
                "writesPerformed": False,
                "status": "scan_only_complete",
            },
            ensure_ascii=True,
            indent=2,
        ))
        return 0

    new_articles = [x for x in candidates if x.article_url.rstrip("/") not in known_urls]
    retry_articles = [
        x for x in candidates
        if x.article_url.rstrip("/") in known_urls
        and known_urls[x.article_url.rstrip("/")].get("classification") == "needs_review"
    ]
    work_articles = new_articles + retry_articles

    snapshot_payload = {
        "format": "official-tthc-source-snapshot",
        "version": 1,
        "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "snapshotComplete": True,
        "sourceCount": len(snapshot_metadata.get("sources", [])),
        "sources": snapshot_metadata.get("sources", []),
    }
    snapshot_payload["snapshotSha256"] = sha256_bytes(
        json.dumps(snapshot_payload["sources"], ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    snapshot_changed = write_json_if_changed(SNAPSHOT_PATH, snapshot_payload)

    stats = {
        "snapshotComplete": True,
        "snapshotChanged": snapshot_changed,
        "snapshotSha256": snapshot_payload["snapshotSha256"],
        "observedArticles": len(candidates),
        "newArticles": len(new_articles),
        "pendingRetries": len(retry_articles),
        "publicDecisionsAdded": 0,
        "internalDecisionsRecorded": 0,
        "needsReview": 0,
        "pdfsDownloaded": 0,
        "manifestChanged": False,
        "indexChanged": False,
        "initialBaseline": initializing,
        "newSourceBaselines": sorted(source_baselines),
        "sourceErrors": source_errors,
        "sourceErrorCount": len(source_errors),
    }

    for candidate in work_articles:
        if initializing or candidate.source_id in source_baselines:
            known = manifest_by_no.get(candidate.decision_no)
            classification = known.get("classification", "baseline_only") if known else "baseline_only"
            status = known.get("ingestStatus", "baseline_only") if known else "baseline_only"
            set_index_record(index_record(candidate, classification=classification, status=status))
            continue

        if candidate.decision_no and candidate.decision_no in manifest_by_no:
            known = manifest_by_no[candidate.decision_no]
            set_index_record(
                index_record(
                    candidate,
                    classification="mirror_known_decision",
                    title=known.get("title", ""),
                    status="known_decision_new_listing_url",
                )
            )
            continue

        try:
            details = extract_article_details(candidate.article_url, config)
        except Exception as exc:
            record = index_record(candidate, classification="needs_review", status=f"article_fetch_failed: {exc}")
            set_index_record(record)
            stats["needsReview"] += 1
            continue

        decision_no = details.get("decisionNo") or candidate.decision_no
        decision_date = details.get("decisionDate") or candidate.decision_date
        candidate = Candidate(
            source_id=candidate.source_id,
            source_url=candidate.source_url,
            source_authority=candidate.source_authority,
            authority_type=candidate.authority_type,
            source_role=candidate.source_role,
            legal_use=candidate.legal_use,
            article_url=candidate.article_url,
            anchor_text=candidate.anchor_text,
            decision_no=decision_no,
            decision_date=decision_date,
        )
        classification = details["classification"]

        # Các bài không tạo danh mục/hiệu lực TTHC public được loại theo nội dung
        # trước khi yêu cầu số quyết định; mirror có thể không hiển thị số trong URL/tiêu đề.
        if classification == "external_reference":
            set_index_record(
                index_record(
                    candidate,
                    classification="external_reference",
                    title=details["title"],
                    status="excluded_external_authority",
                )
            )
            continue
        if classification == "non_tthc":
            set_index_record(
                index_record(candidate, classification="non_tthc", title=details["title"], status="excluded_non_tthc")
            )
            continue
        if classification == "internal_process" and not decision_no:
            set_index_record(
                index_record(candidate, classification="internal_process", title=details["title"], status="excluded_internal_unidentified")
            )
            stats["internalDecisionsRecorded"] += 1
            continue

        if not decision_no:
            set_index_record(
                index_record(candidate, classification="needs_review", title=details["title"], status="missing_decision_number")
            )
            stats["needsReview"] += 1
            continue

        if classification == "internal_process":
            manifest_entry = {
                "decisionNo": decision_no,
                "decisionDate": decision_date,
                "publishedDate": details.get("publishedDate") or "",
                "classification": "internal_process",
                "field": details.get("field") or "",
                "articleUrl": candidate.article_url,
                "pdfUrl": details.get("pdfUrl") or "",
                "filePath": "",
                "pdfSha256": "",
                "effectiveDate": None,
                "ingestStatus": "excluded_internal",
            }
            manifest["decisions"].append(manifest_entry)
            manifest_by_no[decision_no] = manifest_entry
            set_index_record(
                index_record(candidate, classification=classification, title=details["title"], status="excluded_internal")
            )
            stats["internalDecisionsRecorded"] += 1
            continue

        if classification != "public_tthc" or not details.get("pdfUrl"):
            reason = "missing_official_pdf" if classification == "public_tthc" else "unclassified_article"
            set_index_record(
                index_record(candidate, classification="needs_review", title=details["title"], status=reason)
            )
            stats["needsReview"] += 1
            continue

        try:
            file_path, digest = download_pdf(details["pdfUrl"], decision_no)
        except Exception as exc:
            set_index_record(
                index_record(
                    candidate,
                    classification="needs_review",
                    title=details["title"],
                    status=f"pdf_download_failed: {exc}",
                )
            )
            stats["needsReview"] += 1
            continue

        manifest_entry = {
            "decisionNo": decision_no,
            "decisionDate": decision_date,
            "publishedDate": details.get("publishedDate") or "",
            "classification": "public_tthc",
            "field": details.get("field") or "",
            "articleUrl": candidate.article_url,
            "pdfUrl": details["pdfUrl"],
            "filePath": file_path,
            "pdfSha256": digest,
            "effectiveDate": None,
            "ingestStatus": "auto_discovered",
            "title": details["title"],
        }
        manifest["decisions"].append(manifest_entry)
        manifest_by_no[decision_no] = manifest_entry
        set_index_record(
            index_record(candidate, classification="public_tthc", title=details["title"], status="auto_discovered")
        )
        stats["publicDecisionsAdded"] += 1
        stats["pdfsDownloaded"] += 1

    stats["manifestDatesEnriched"] = reconcile_missing_manifest_dates(manifest_by_no, candidates)

    index["articles"] = sorted(
        index.get("articles", []),
        key=lambda x: (x.get("decisionDate") or "", x.get("decisionNo") or "", x.get("articleUrl") or ""),
    )
    manifest["decisions"] = sorted(
        manifest.get("decisions", []),
        key=lambda x: (x.get("decisionDate") or "", x.get("decisionNo") or ""),
    )

    stats["indexChanged"] = write_json_if_changed(INDEX_PATH, index)
    stats["manifestChanged"] = write_json_if_changed(MANIFEST_PATH, manifest)
    # Keep CLI output safe on Windows legacy console encodings; persisted JSON remains UTF-8.
    print(json.dumps(stats, ensure_ascii=True, indent=2))

    # Scanner failures do not mutate legal status; review-required records are auditable.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
