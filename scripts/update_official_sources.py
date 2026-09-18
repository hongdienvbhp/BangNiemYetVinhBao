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
import hashlib
import html
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "data/source-audit/official-source-config.json"
MANIFEST_PATH = ROOT / "data/source-audit/official-decision-manifest.json"
INDEX_PATH = ROOT / "data/source-audit/official-source-index.json"
AUTO_PDF_DIR = ROOT / "data/source-audit/city-decisions"

USER_AGENT = "BangNiemYetVinhBao-Official-TTHC-Monitor/1.0"
DECISION_URL_RE = re.compile(
    r"quyet-dinh-so-(?P<num>\d+)-qd-ubnd-ngay-(?P<day>\d{1,2})-(?P<month>\d{1,2})-(?P<year>\d{4})",
    re.IGNORECASE,
)
DECISION_TEXT_RE = re.compile(
    r"(?:Quyết\s*định\s*(?:số\s*:?)?\s*)(?P<num>\d+)\s*/\s*Q(?:Đ|D)-UBND",
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


def decode_html(body: bytes, content_type: str) -> str:
    charset = "utf-8"
    match = re.search(r"charset=([\w-]+)", content_type or "", re.I)
    if match:
        charset = match.group(1)
    try:
        return body.decode(charset, errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self.title_parts: list[str] = []
        self.in_title = False
        self._anchor_href = ""
        self._anchor_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = {k.lower(): (v or "") for k, v in attrs}
        if tag.lower() == "title":
            self.in_title = True
        if tag.lower() == "a":
            self._anchor_href = attrs_map.get("href", "")
            self._anchor_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self.in_title = False
        if tag.lower() == "a" and self._anchor_href:
            text = re.sub(r"\s+", " ", " ".join(self._anchor_parts)).strip()
            self.links.append((self._anchor_href, text))
            self._anchor_href = ""
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


def parse_decision_identity(url: str, text: str = "") -> tuple[str, str]:
    match = DECISION_URL_RE.search(url)
    if match:
        number = match.group("num")
        date = f"{int(match.group('year')):04d}-{int(match.group('month')):02d}-{int(match.group('day')):02d}"
        return f"{number}/QĐ-UBND", date

    text_decision = DECISION_TEXT_RE.search(text or "")
    text_date = DATE_TEXT_RE.search(text or "")
    number = text_decision.group("num") if text_decision else ""
    date = ""
    if text_date:
        date = f"{int(text_date.group('year')):04d}-{int(text_date.group('month')):02d}-{int(text_date.group('day')):02d}"
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
            published_date = f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
        else:
            published_date = raw[:10]
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


def discover_candidates(config: dict) -> tuple[list[Candidate], list[dict[str, str]]]:
    found: dict[str, Candidate] = {}
    source_errors: list[dict[str, str]] = []
    for source in config.get("listingSources", []):
        source_url = source["url"]
        try:
            body, content_type = fetch_bytes(source_url)
        except Exception as exc:
            source_errors.append({
                "sourceId": str(source.get("id", "")),
                "sourceUrl": source_url,
                "authority": str(source.get("authority", "")),
                "error": f"{type(exc).__name__}: {exc}",
            })
            continue
        page = decode_html(body, content_type)
        parser = PageParser()
        parser.feed(page)
        for href, anchor in parser.links:
            if not href:
                continue
            article_url = urljoin(source_url, href)
            if urlparse(article_url).netloc != urlparse(source_url).netloc:
                continue
            if not is_candidate_link(article_url, anchor):
                continue
            decision_no, decision_date = parse_decision_identity(article_url, anchor)
            key = article_url.rstrip("/")
            found[key] = Candidate(
                source_id=source.get("id", ""),
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
    return (
        sorted(found.values(), key=lambda x: (x.decision_date, x.decision_no, x.article_url)),
        source_errors,
    )


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
    args = parser.parse_args()

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

    candidates, source_errors = discover_candidates(config)
    new_articles = [x for x in candidates if x.article_url.rstrip("/") not in known_urls]
    retry_articles = [
        x for x in candidates
        if x.article_url.rstrip("/") in known_urls
        and known_urls[x.article_url.rstrip("/")].get("classification") == "needs_review"
    ]
    work_articles = new_articles + retry_articles

    stats = {
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
