#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build verified city TTHC reception baseline from the official Hai Phong PDF."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
from pathlib import Path
from statistics import median
from urllib.request import Request, urlopen

import fitz

ARTICLE_URL = "https://haiphong.gov.vn/thu-tuc-hanh-chinh-76761/danh-muc-thu-tuc-hanh-chinh-tiep-nhan-tai-trung-tam-phuc-vu-hanh-chinh-cong-thanh-pho-hai-phong--760833"
PDF_URL = "https://cdn.haiphong.gov.vn/gov-hpg/1/tintuc/2025/7/danh-muc-thu-tuc-hanh-chinh-thuc-hien-tiep-nhan-tai-trung-tam-phuc-vu-hanh-chinh-cong-thanh-pho-hai-phong638871741697189500.pdf"
PUBLISHED_DATE = "2025-07-03"
EXPECTED_SHA256 = "22c2a8ab6abc6aa0df4694da6eebafe51f5a75bf76bae97f22c19af5fa082425"
EXPECTED_PAGES = 114
CODE_RE = re.compile(r"^\d{1,2}\.\d{3,6}$")
ROW_CODE_LINE_RE = re.compile(r"^(?:\d{1,3}\.\s+)?(\d{1,2}\.\d{3,6})$")
ROW_ORDINAL_RE = re.compile(r"^\d{1,3}\.$")
HEADER_RE = re.compile(r"^STT\s+Mã TTHC\b", re.I)
AGENCY_RE = re.compile(r"^(?:[IVXLCDM]+\.|\d+\.)\s+(?:SỞ|BAN|VĂN PHÒNG|THANH TRA|CÔNG AN|UBND|ỦY BAN)", re.I)
AGENCY_BODY_RE = re.compile(r"^(?:SỞ|BAN|VĂN PHÒNG|THANH TRA|CÔNG AN|UBND|ỦY BAN)\b", re.I)
AGENCY_PREFIX_RE = re.compile(r"^(?:[IVXLCDM]+\.|\d+\.)$")


def space(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def norm_code(value: str) -> str:
    value = value.strip().rstrip(".")
    if not CODE_RE.fullmatch(value):
        return value
    prefix, suffix = value.split(".", 1)
    return f"{prefix}.{suffix.ljust(6, '0')}"


def fetch_pdf() -> bytes:
    req = Request(PDF_URL, headers={"User-Agent": "BangNiemYetVinhBao-City-Baseline/3.0"})
    with urlopen(req, timeout=60) as response:
        data = response.read()
    if not data.startswith(b"%PDF"):
        raise RuntimeError("Official attachment is not PDF")
    return data


def code_from_block(block_text: str):
    """Read a standalone code line, optionally sharing a line with its row ordinal."""
    lines = [space(line) for line in (block_text or "").splitlines()]
    lines = [line for line in lines if line]
    for line in lines[:5]:
        match = ROW_CODE_LINE_RE.fullmatch(line)
        if match:
            return norm_code(match.group(1))
    return None


def words_text(words, xmin: float, xmax: float, *, min_order=None, max_order=None) -> str:
    """Join cell words by source text order, which disambiguates overlapped rows."""
    selected = []
    for word in words:
        x0 = float(word[0])
        order = (int(word[6]), int(word[7]))
        if not (xmin <= x0 < xmax):
            continue
        if min_order is not None and order < min_order:
            continue
        if max_order is not None and order >= max_order:
            continue
        selected.append(word)
    by_line = {}
    for word in selected:
        by_line.setdefault(int(word[6]), []).append(word)
    lines = []
    for line_no in sorted(by_line):
        ordered = sorted(by_line[line_no], key=lambda word: int(word[7]))
        line = space(" ".join(str(word[4]) for word in ordered))
        if line:
            lines.append(line)
    return space(" ".join(lines))


def agency_heading(blocks, index):
    text = space(str(blocks[index][4]))
    match = re.search(
        r"(?:[IVXLCDM]+|\d+)\.\s+(?:SỞ|BAN|VĂN PHÒNG|THANH TRA|CÔNG AN|UBND|ỦY BAN)\b.*",
        text,
        flags=re.I,
    )
    if match:
        heading = re.sub(r"\s+STT\s+Mã TTHC.*$", "", match.group(0), flags=re.I)
        return space(heading), 1
    if AGENCY_PREFIX_RE.fullmatch(text) and index + 1 < len(blocks):
        following = space(str(blocks[index + 1][4]))
        if AGENCY_BODY_RE.match(following):
            heading = re.sub(r"\s+STT\s+Mã TTHC.*$", "", f"{text} {following}", flags=re.I)
            return space(heading), 2
    return None, 0


def block_line_records(blocks, words_by_block):
    """Represent each text line with its own physical coordinates."""
    lines = []
    for block_index, block in enumerate(blocks):
        block_words = words_by_block.get(int(block[5]), [])
        by_line = {}
        for word in block_words:
            by_line.setdefault(int(word[6]), []).append(word)
        for line_no, line_words in by_line.items():
            line_words.sort(key=lambda word: float(word[0]))
            text = space(" ".join(str(word[4]) for word in line_words))
            if not text:
                continue
            lines.append({
                "text": text,
                "x0": min(float(word[0]) for word in line_words),
                "y0": min(float(word[1]) for word in line_words),
                "x1": max(float(word[2]) for word in line_words),
                "y1": max(float(word[3]) for word in line_words),
                "block_index": block_index,
                "line_no": line_no,
            })
    return sorted(lines, key=lambda line: (line["y0"], line["x0"]))


def agency_heading_records(blocks, words_by_block):
    """Find every agency heading line, including headings sharing a text block."""
    lines = block_line_records(blocks, words_by_block)
    headings = []
    consumed = set()
    for index, line in enumerate(lines):
        if index in consumed:
            continue
        text = line["text"]
        match = re.search(
            r"((?:[IVXLCDM]+|\d+)\.\s+(?:SỞ|BAN|VĂN PHÒNG|THANH TRA|CÔNG AN|UBND|ỦY BAN)\b.*)",
            text,
            flags=re.I,
        )
        if match:
            heading = re.sub(r"\s+STT\s+Mã TTHC.*$", "", match.group(1), flags=re.I)
            headings.append({**line, "agency": space(heading)})
            continue
        if AGENCY_PREFIX_RE.fullmatch(text):
            for next_index in range(index + 1, len(lines)):
                following = lines[next_index]
                if following["y0"] - line["y1"] > 18.0:
                    break
                if abs(following["x0"] - line["x0"]) <= 25.0 and AGENCY_BODY_RE.match(following["text"]):
                    headings.append({
                        "agency": space(f"{text} {following['text']}"),
                        "x0": min(line["x0"], following["x0"]),
                        "y0": min(line["y0"], following["y0"]),
                        "x1": max(line["x1"], following["x1"]),
                        "y1": max(line["y1"], following["y1"]),
                        "block_index": line["block_index"],
                        "line_no": line["line_no"],
                    })
                    consumed.add(next_index)
                    break
    return headings


def section_field_records(blocks, words_by_block):
    """Extract explicit field names from the appendix's lettered field headings."""
    sections = []
    for line in block_line_records(blocks, words_by_block):
        match = re.match(r"^[A-I]\s+LĨNH VỰC\s+(.+)$", line["text"], flags=re.I)
        if not match:
            continue
        field = re.sub(r"\s+STT\s+Mã TTHC.*$", "", match.group(1), flags=re.I)
        sections.append({**line, "field": space(field)})
    return sections

def heading_distance(x, heading):
    if x < heading["x0"]:
        return heading["x0"] - x
    if x > heading["x1"]:
        return x - heading["x1"]
    return 0.0


def resolve_agency(code_record, headings, previous_headings):
    """Choose the nearest matching table column, including section headings from prior pages."""
    x = code_record["x"]
    y = code_record["y"]
    candidates = [heading for heading in headings if heading["y0"] <= y] + previous_headings
    if not candidates:
        return ""
    min_distance = min(heading_distance(x, heading) for heading in candidates)
    same_column = [
        heading for heading in candidates
        if heading_distance(x, heading) <= min_distance + 5.0
    ]
    return max(same_column, key=lambda heading: (heading.get("page", 0), heading["y0"]))["agency"]


def resolve_section_field(code_record, sections, previous_sections):
    """Use a field label only when the PDF explicitly supplies it as a section heading."""
    x = code_record["x"]
    y = code_record["y"]
    candidates = [section for section in sections if section["y0"] <= y] + previous_sections
    if not candidates:
        return ""
    min_distance = min(heading_distance(x, section) for section in candidates)
    same_column = [
        section for section in candidates
        if heading_distance(x, section) <= min_distance + 5.0
    ]
    return max(same_column, key=lambda section: (section.get("page", 0), section["y0"]))["field"]


def collect_nearest_field(blocks, block_index, words_by_block, row_codes_by_block, code_record, max_distance=24.0):
    """Recover a field cell from a separate PDF text block aligned to the code row."""
    candidates = []
    for candidate_index, candidate in enumerate(blocks):
        if candidate_index == block_index or row_codes_by_block.get(candidate_index):
            continue
        text = space(str(candidate[4]))
        if HEADER_RE.match(text) or agency_heading(blocks, candidate_index)[0]:
            continue
        if re.match(r"^[A-I]\\s+LĨNH VỰC\\s+", text, flags=re.I):
            continue
        candidate_words = words_by_block.get(int(candidate[5]), [])
        if not candidate_words:
            continue
        part = words_text(candidate_words, 443.0, 700.0)
        if not part:
            continue
        center_y = (float(candidate[1]) + float(candidate[3])) / 2.0
        distance = abs(center_y - code_record["y"])
        if distance <= max_distance:
            candidates.append((distance, part))
    if not candidates:
        return ""
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]

def collect_separate_cells(blocks, block_index, words_by_block, row_codes_by_block, need_name, need_field):
    """Collect cell text following a row, including a previous row's field before the next code."""
    name_parts = []
    field_parts = []
    for candidate_index in range(block_index + 1, len(blocks)):
        candidate = blocks[candidate_index]
        candidate_words = words_by_block.get(int(candidate[5]), [])
        candidate_codes = row_codes_by_block.get(candidate_index, [])

        if candidate_codes:
            candidate_code_order = candidate_codes[0]["order"]
            if need_name:
                part = words_text(candidate_words, 160.0, 443.0, max_order=candidate_code_order)
                if part:
                    name_parts.append(part)
            if need_field:
                part = words_text(candidate_words, 443.0, 700.0, max_order=candidate_code_order)
                if part:
                    field_parts.append(part)
            break

        candidate_text = space(str(candidate[4]))
        candidate_heading, _ = agency_heading(blocks, candidate_index)
        if candidate_heading or HEADER_RE.match(candidate_text):
            break

        if need_name:
            part = words_text(candidate_words, 160.0, 443.0)
            if part:
                name_parts.append(part)
        if need_field:
            part = words_text(candidate_words, 443.0, 700.0)
            if part:
                field_parts.append(part)

    return space(" ".join(name_parts)), space(" ".join(field_parts))


def extract_rows(pages):
    """Extract each code token and associate cells/headings by source order and geometry."""
    page_records = []

    for page_no, page in enumerate(pages, start=1):
        blocks = page.get_text("blocks", sort=False)
        block_no_to_index = {int(block[5]): index for index, block in enumerate(blocks)}
        words_by_block = {}
        row_codes_by_block = {}
        words = page.get_text("words", sort=False)
        for word in words:
            block_no = int(word[5])
            words_by_block.setdefault(block_no, []).append(word)
            code_token = space(str(word[4])).rstrip(".")
            if float(word[0]) >= 160.0 or not CODE_RE.fullmatch(code_token):
                continue
            block_index = block_no_to_index.get(block_no)
            if block_index is None:
                continue
            row_codes_by_block.setdefault(block_index, []).append({
                "code": norm_code(code_token),
                "order": (int(word[6]), int(word[7])),
                "x": float(word[0]),
                "y": (float(word[1]) + float(word[3])) / 2.0,
            })

        for code_records in row_codes_by_block.values():
            code_records.sort(key=lambda item: item["order"])
        headings = [{**heading, "page": page_no} for heading in agency_heading_records(blocks, words_by_block)]
        sections = [{**section, "page": page_no} for section in section_field_records(blocks, words_by_block)]
        page_records.append((
            page_no, blocks, words_by_block, row_codes_by_block, headings, sections,
        ))

    previous_headings = []
    previous_sections = []
    rows = []

    for page_no, blocks, words_by_block, row_codes_by_block, headings, sections in page_records:
        block_index = 0
        while block_index < len(blocks):
            code_records = row_codes_by_block.get(block_index, [])
            if not code_records:
                block_index += 1
                continue

            block_words = words_by_block.get(int(blocks[block_index][5]), [])
            for code_index, code_record in enumerate(code_records):
                code_order = code_record["order"]
                next_code_order = (
                    code_records[code_index + 1]["order"]
                    if code_index + 1 < len(code_records)
                    else None
                )
                name = words_text(
                    block_words, 160.0, 443.0,
                    min_order=code_order, max_order=next_code_order,
                )
                field = words_text(
                    block_words, 443.0, 700.0,
                    min_order=code_order, max_order=next_code_order,
                )

                # Only the final code in a block may borrow cell text from later blocks;
                # earlier codes in the same block are bounded by the next code token.
                if (not name or not field) and code_index == len(code_records) - 1:
                    extra_name, extra_field = collect_separate_cells(
                        blocks,
                        block_index,
                        words_by_block,
                        row_codes_by_block,
                        need_name=not name,
                        need_field=not field,
                    )
                    if not name:
                        name = extra_name
                    if not field:
                        field = extra_field

                field_source = None
                if not field and page_no <= 109:
                    near_field = collect_nearest_field(
                        blocks, block_index, words_by_block, row_codes_by_block,
                        code_record, max_distance=24.0,
                    )
                    if near_field:
                        field = near_field
                        field_source = "PDF_COORDINATE_CELL"
                if not field:
                    section_field = resolve_section_field(code_record, sections, previous_sections)
                    if section_field:
                        field = section_field
                        field_source = "PDF_SECTION_HEADING"

                row = {
                    "code": code_record["code"],
                    "name": name,
                    "field": field,
                    "agency": resolve_agency(code_record, headings, previous_headings),
                    "page": page_no,
                }
                if field_source:
                    row["fieldSource"] = field_source
                rows.append(row)
            block_index += 1

        previous_headings.extend(headings)
        previous_sections.extend(sections)

    return rows

def dedupe(rows):
    """Deduplicate exact repeats; expose conflicting official cells instead of guessing."""
    out = {}
    conflicts = []
    conflicted_fields = set()

    for row in rows:
        code = row["code"]
        previous = out.get(code)
        if not previous:
            out[code] = dict(row)
            continue

        for key in ("name", "field", "agency"):
            old = space(str(previous.get(key, "")))
            new = space(str(row.get(key, "")))
            conflict_key = (code, key)
            if conflict_key in conflicted_fields:
                continue
            if old and new and old != new:
                conflicts.append({
                    "code": code,
                    "field": key,
                    "values": [old, new],
                    "pages": [previous.get("page"), row.get("page")],
                })
                previous[key] = ""
                conflicted_fields.add(conflict_key)
            elif not old and new:
                previous[key] = new

    return sorted(out.values(), key=lambda row: row["code"]), conflicts


def mark_manual_review(rows):
    """Keep unresolved source cells blank and label them for explicit human review."""
    for row in rows:
        for field_name in ("name", "field", "agency"):
            value = space(str(row.get(field_name, "")))
            if not value or (field_name == "agency" and "; " in value):
                row[f"{field_name}Status"] = "MANUAL_REVIEW"
    return rows


def build(data: bytes):
    digest = hashlib.sha256(data).hexdigest()
    if digest != EXPECTED_SHA256:
        raise RuntimeError(f"SHA256 changed: {digest}")

    with fitz.open(stream=data, filetype="pdf") as pdf:
        if len(pdf) != EXPECTED_PAGES:
            raise RuntimeError(f"Page count changed: {len(pdf)}")
        rows, duplicate_conflicts = dedupe(extract_rows(pdf))
        rows = mark_manual_review(rows)

    if len(rows) < 300:
        raise RuntimeError(f"Implausibly small baseline: {len(rows)}")

    missing_name = [row["code"] for row in rows if not space(str(row.get("name", "")))]
    empty_field = [row["code"] for row in rows if not space(str(row.get("field", "")))]
    missing_agency = [row["code"] for row in rows if not space(str(row.get("agency", "")))]
    return {
        "format": "haiphong-city-reception-baseline",
        "version": 3,
        "publishedDate": PUBLISHED_DATE,
        "articleUrl": ARTICLE_URL,
        "pdfUrl": PDF_URL,
        "pdfSha256": digest,
        "pageCount": EXPECTED_PAGES,
        "scope": "TTHC tiếp nhận tại Trung tâm Phục vụ hành chính công thành phố Hải Phòng",
        "rowCount": len(rows),
        "missingNameCount": len(missing_name),
        "missingNameCodes": missing_name,
        "emptyFieldCount": len(empty_field),
        "emptyFieldCodes": empty_field,
        "missingAgencyCount": len(missing_agency),
        "missingAgencyCodes": missing_agency,
        "manualReviewNameCount": len(missing_name),
        "manualReviewFieldCount": len(empty_field),
        "manualReviewAgencyCount": sum(1 for row in rows if row.get("agencyStatus") == "MANUAL_REVIEW"),
        "duplicateConflictCount": len(duplicate_conflicts),
        "duplicateConflicts": duplicate_conflicts,
        "rows": rows,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/source-audit/city-reception-baseline.json"))
    args = parser.parse_args()

    data = args.pdf.read_bytes() if args.pdf else fetch_pdf()
    payload = build(data)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {
        key: payload[key]
        for key in (
            "rowCount", "missingNameCount", "emptyFieldCount", "missingAgencyCount",
            "duplicateConflictCount", "pageCount", "pdfSha256",
        )
    }
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
