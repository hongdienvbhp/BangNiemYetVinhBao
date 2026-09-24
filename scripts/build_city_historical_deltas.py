#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hydrate official Hai Phong city TTHC deltas after the 03/07/2025 baseline.

This is a one-way evidence builder. It consumes only official Hai Phong listings
already registered in official-source-index.json plus official cdn.haiphong.gov.vn
attachments. Ambiguous/unresolved decisions make the build fail closed.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import io
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from pypdf import PdfReader

from scripts.extract_city_updates import CODE_RE, detect_effective_date, extract_name, level_hint, merge_rows, section_status
from scripts.update_official_sources import CONFIG_PATH, extract_article_details, load_json

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "data/source-audit/official-source-index.json"
MANIFEST = ROOT / "data/source-audit/official-decision-manifest.json"
BASELINE_DATE = "2025-07-03"
DEFAULT_AS_OF = "2026-09-18"

# Dates verified against signed decision text / official Hai Phong publication.
DECISION_DATE_OVERRIDES = {
    "1248/QĐ-UBND": "2024-04-15",
    "2024/QĐ-UBND": "2025-06-25",
    "2506/QĐ-UBND": "2025-06-30",
    "3186/QĐ-UBND": "2024-09-06",
    "3267/QĐ-UBND": "2025-08-15",
    "3269/QĐ-UBND": "2025-08-15",
    "3270/QĐ-UBND": "2025-08-15",
    "3271/QĐ-UBND": "2025-08-15",
    "3272/QĐ-UBND": "2025-08-15",
    "3323/QĐ-UBND": "2025-08-17",
    "3324/QĐ-UBND": "2025-08-17",
    "3326/QĐ-UBND": "2025-08-17",
    "4774/QĐ-UBND": "2025-11-26",
    "4825/QĐ-UBND": "2025-11-28",
    "4943/QĐ-UBND": "2025-12-05",
    "4272/QĐ-UBND": "2025-10-27",
    "2135/QĐ-UBND": "2026-06-07",
}

EFFECTIVE_DATE_OVERRIDES = {
    # Signed QĐ 3270 states completion/application from 25/08/2025.
    "3270/QĐ-UBND": "2025-08-25",
    # Official Hai Phong steering metadata.
    "3323/QĐ-UBND": "2025-08-17",
    "3433/QĐ-UBND": "2026-08-25",
    "4943/QĐ-UBND": "2025-12-05",
}

PDF_URL_OVERRIDES = {
    "4272/QĐ-UBND": "https://cdn.haiphong.gov.vn/gov-hpg/6872/tintuc/2025/11/qd-4272-ngay-27.10.2025638984854024007617.pdf",
    "2135/QĐ-UBND": "https://cdn.haiphong.gov.vn/gov-hpg/5889/tintuc/2026/6/qd-cong-bo-dm-tthc-theo-qd-1289-cua-bo-ct..signed639167043535735176.pdf",
}

NONSEMANTIC_DECISIONS = {
    # Delegation changes handling authority, not TTHC identity/status.
    "689/QĐ-UBND",
}

SUPERSEDED_DECISIONS = {
    # QĐ 3637/QĐ-UBND explicitly replaces QĐ 3271/QĐ-UBND and publishes the
    # complete successor catalogue. Replaying 3271 is unnecessary for the
    # current-state read model when its old attachment is unavailable.
    "3271/QĐ-UBND": "3637/QĐ-UBND",
}


def fold(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value or "")
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn").lower()


def title_kind(title: str) -> str:
    value = fold(title)
    if "thu tuc hanh chinh noi bo" in value or "tthc noi bo" in value or "quy trinh noi bo" in value:
        return "internal"
    nonsemantic = (
        "tai cau truc quy trinh",
        "du dieu kien cung cap dich vu cong",
        "uy quyen thuc hien",
        "ke hoach kiem tra",
        "hoi thi truc tuyen",
    )
    if any(marker in value for marker in nonsemantic):
        return "nonsemantic"
    public = (
        "cong bo danh muc thu tuc hanh chinh",
        "cong bo danh muc tthc",
        "cong bo thu tuc hanh chinh",
        "cong bo tthc chuan hoa",
        "cong bo danh muc tthc chuan hoa",
    )
    return "public" if any(marker in value for marker in public) else "unknown"


def fetch_pdf(url: str) -> bytes | None:
    if not url or (urlparse(url).hostname or "") != "cdn.haiphong.gov.vn":
        return None
    request = Request(url, headers={"User-Agent": "BangNiemYetVinhBao-Historical-Deltas/1.0"})
    with urlopen(request, timeout=60) as response:
        data = response.read()
    return data if data.startswith(b"%PDF") else None


def parse_date_from_text(*texts: str) -> str:
    for text in texts:
        if not text:
            continue
        value = fold(text)
        patterns = (
            r"(?:ngay\s*)?(\d{1,2})[/-](\d{1,2})[/-](20\d{2})",
            r"hai phong,?\s*ngay\s*(\d{1,2})\s*thang\s*(\d{1,2})\s*nam\s*(20\d{2})",
        )
        for pattern in patterns:
            match = re.search(pattern, value)
            if match:
                return f"{int(match.group(3)):04d}-{int(match.group(2)):02d}-{int(match.group(1)):02d}"
    return ""


def detect_application_date(reader: PdfReader) -> str:
    sample = "\n".join((page.extract_text() or "") for page in reader.pages[:5])
    value = fold(sample)
    patterns = (
        r"ap dung ke tu ngay\s*(\d{1,2})\s+thang\s+(\d{1,2})\s+nam\s+(\d{4})",
        r"ap dung tu ngay\s*(\d{1,2})\s+thang\s+(\d{1,2})\s+nam\s+(\d{4})",
        r"ap dung ke tu ngay\s*(\d{1,2})[./-](\d{1,2})[./-](\d{4})",
        r"ap dung tu ngay\s*(\d{1,2})[./-](\d{1,2})[./-](\d{4})",
    )
    for pattern in patterns:
        match = re.search(pattern, value, re.S)
        if match:
            return f"{int(match.group(3)):04d}-{int(match.group(2)):02d}-{int(match.group(1)):02d}"
    return ""


def infer_field(title: str, sample: str) -> str:
    value = " ".join((title + " " + sample[:12000]).split())
    for pattern in (
        r"lĩnh vực\s+(.{2,140}?)\s+thuộc phạm vi",
        r"lĩnh vực\s+(.{2,120}?)\s+thuộc thẩm quyền",
        r"lĩnh vực\s+(.{2,120}?)\s+thuộc chức năng",
    ):
        match = re.search(pattern, value, re.I)
        if match:
            return match.group(1).strip(" ,.;:-").upper()
    return ""


def pick_official_attachment(decision_no: str, entries: list[dict], config: dict) -> tuple[dict, dict, bytes | None]:
    rank = {"primary_publication": 4, "cross_check_and_local_publication": 3, "identity_and_coverage_cross_check": 2, "cross_check_only": 1}
    entries = sorted(entries, key=lambda item: -rank.get(item.get("legalUse", ""), 0))
    best_details: dict = {}
    best_entry = entries[0] if entries else {}
    for entry in entries:
        try:
            details = extract_article_details(entry["articleUrl"], config)
            if not best_details:
                best_details = details
                best_entry = entry
            pdf_url = PDF_URL_OVERRIDES.get(decision_no) or details.get("pdfUrl") or ""
            data = fetch_pdf(pdf_url)
            if data:
                details = dict(details)
                details["pdfUrl"] = pdf_url
                return entry, details, data
        except Exception:
            continue
    override_url = PDF_URL_OVERRIDES.get(decision_no, "")
    if override_url:
        data = fetch_pdf(override_url)
        if data:
            best_details = dict(best_details)
            best_details["pdfUrl"] = override_url
            return best_entry, best_details, data
    return best_entry, best_details, None


def extract_rows(reader: PdfReader) -> list[dict]:
    rows: list[dict] = []
    status = "published"
    level = ""
    start_page = 2 if len(reader.pages) > 2 else 0
    for page_index, page in enumerate(reader.pages):
        if page_index < start_page:
            continue
        lines = [re.sub(r"\s+", " ", item).strip() for item in (page.extract_text() or "").splitlines()]
        for line_index, line in enumerate(lines):
            if not line:
                continue
            status = section_status(line, status)
            level = level_hint(line, level)
            for match in CODE_RE.finditer(line):
                code = match.group(0)
                rows.append(
                    {
                        "code": code,
                        "name": extract_name(lines, line_index, code),
                        "sectionStatus": status,
                        "levelHint": level,
                        "communeReceptionEvidence": False,
                        "page": page_index + 1,
                        "context": " ".join(lines[max(0, line_index - 2) : min(len(lines), line_index + 12)])[:1200],
                    }
                )
    return list(merge_rows(rows).values())


def process_decision(decision_no: str, entries: list[dict], config: dict, as_of: str) -> dict:
    if decision_no in NONSEMANTIC_DECISIONS:
        return {"decisionNo": decision_no, "classification": "nonsemantic", "reason": "delegation_or_non_catalogue_change"}
    if decision_no in SUPERSEDED_DECISIONS:
        return {"decisionNo": decision_no, "classification": "superseded", "supersededBy": SUPERSEDED_DECISIONS[decision_no]}
    override_date = DECISION_DATE_OVERRIDES.get(decision_no, "")
    if override_date and override_date <= BASELINE_DATE:
        return {"decisionNo": decision_no, "classification": "pre_baseline", "decisionDate": override_date}

    entry, details, data = pick_official_attachment(decision_no, entries, config)
    title = str(details.get("title") or entry.get("title") or "")
    kind = title_kind(title)
    if data is None:
        if kind in {"internal", "nonsemantic"}:
            return {"decisionNo": decision_no, "classification": kind, "title": title}
        return {"decisionNo": decision_no, "classification": "unresolved", "reason": "missing_official_pdf", "title": title}

    reader = PdfReader(io.BytesIO(data))
    sample = "\n".join((page.extract_text() or "") for page in reader.pages[:8])
    combined = fold(sample + " " + title)
    if "quy trinh noi bo" in combined or "thu tuc hanh chinh noi bo" in combined:
        kind = "internal"
    elif kind == "unknown" and ("cong bo danh muc thu tuc hanh chinh" in combined or "cong bo thu tuc hanh chinh" in combined):
        kind = "public"
    if kind in {"internal", "nonsemantic"}:
        return {"decisionNo": decision_no, "classification": kind, "title": title}
    if kind != "public":
        return {"decisionNo": decision_no, "classification": "unresolved", "reason": "unclassified_publication", "title": title}

    decision_date = override_date or str(details.get("decisionDate") or entry.get("decisionDate") or "") or parse_date_from_text(title, sample)
    if not decision_date:
        return {"decisionNo": decision_no, "classification": "unresolved", "reason": "missing_decision_date", "title": title}
    if decision_date <= BASELINE_DATE:
        return {"decisionNo": decision_no, "classification": "pre_baseline", "decisionDate": decision_date, "title": title}

    effective_date = EFFECTIVE_DATE_OVERRIDES.get(decision_no)
    effective_source = "verified_override"
    if not effective_date:
        effective_date, effective_source = detect_effective_date(reader, decision_date)
    if not effective_date:
        effective_date = detect_application_date(reader)
        effective_source = "explicit_application_date_clause" if effective_date else ""
    if not effective_date:
        # Publication decisions often omit a separate effectiveness clause. In
        # that case the signed decision date is the deterministic fallback.
        # Legal-basis dates elsewhere in appendices are deliberately ignored.
        effective_date = decision_date
        effective_source = "decision_date_fallback_no_explicit_effective_or_application_clause"

    return {
        "decisionNo": decision_no,
        "decisionDate": decision_date,
        "effectiveDate": effective_date,
        "effectiveDateSource": effective_source,
        "classification": "public_tthc",
        "field": infer_field(title, sample),
        "title": title,
        "articleUrl": entry.get("articleUrl") or "",
        "pdfUrl": details.get("pdfUrl") or "",
        "pdfSha256": hashlib.sha256(data).hexdigest(),
        "pageCount": len(reader.pages),
        "asOf": as_of,
        "rows": sorted(extract_rows(reader), key=lambda row: row["code"]),
    }


def build(as_of: str) -> dict:
    config = load_json(CONFIG_PATH, {})
    index = load_json(INDEX, {"articles": []})
    manifest = load_json(MANIFEST, {"decisions": []})
    known = {item.get("decisionNo") for item in manifest.get("decisions", []) if item.get("decisionNo")}
    by_decision: dict[str, list[dict]] = {}
    for item in index.get("articles", []):
        decision_no = str(item.get("decisionNo") or "")
        if decision_no and decision_no not in known:
            by_decision.setdefault(decision_no, []).append(item)

    decisions: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(process_decision, number, entries, config, as_of) for number, entries in sorted(by_decision.items())]
        for future in futures:
            decisions.append(future.result())
    decisions.sort(key=lambda item: (item.get("decisionDate") or "", item.get("decisionNo") or ""))
    unresolved = [item for item in decisions if item.get("classification") == "unresolved"]
    if unresolved:
        summary = [{"decisionNo": item.get("decisionNo"), "reason": item.get("reason")} for item in unresolved]
        raise RuntimeError("Historical city delta audit is incomplete: " + json.dumps(summary, ensure_ascii=False))
    public = [item for item in decisions if item.get("classification") == "public_tthc"]
    return {
        "format": "haiphong-city-tthc-historical-deltas",
        "version": 1,
        "baselineDate": BASELINE_DATE,
        "asOf": as_of,
        "sourceIndexDecisionCount": len(by_decision),
        "publicDecisionCount": len(public),
        "publicRowCount": sum(len(item.get("rows", [])) for item in public),
        "complete": True,
        "decisions": decisions,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", default=DEFAULT_AS_OF)
    parser.add_argument("--output", type=Path, default=ROOT / "data/source-audit/city-historical-deltas-current.json")
    args = parser.parse_args()
    payload = build(args.as_of)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: payload[key] for key in ("sourceIndexDecisionCount", "publicDecisionCount", "publicRowCount", "complete")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
