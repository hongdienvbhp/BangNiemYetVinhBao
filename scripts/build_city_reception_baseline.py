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
        field = re.sub(r"\\s+STT\\s+Mã TTHC.*$", "", match.group(1), flags=re.I)
        sections.append({**line, "field": space(field)})
    return sections

def heading_distance(x, heading):
    if x < heading["x0"]:
        return heading["x0"] - x
    if x > heading["x1"]:
        return x - heading["x1"]
    return 0.0


def resolve_agency(code_record, headings, previous_headings):
    """Resolve the agency by nearest matching table column and preceding visual heading."""
    x = code_record["x"]
    y = code_record["y"]
    eligible = [heading for heading in headings if heading["y0"] <= y]
    if eligible:
        min_distance = min(heading_distance(x, heading) for heading in eligible)
        same_column = [
            heading for heading in eligible
            if heading_distance(x, heading) <= min_distance + 5.0
        ]
        return max(same_column, key=lambda heading: heading["y0"])["agency"]

    if previous_headings:
        min_distance = min(heading_distance(x, heading) for heading in previous_headings)
        same_column = [
            heading for heading in previous_headings
            if heading_distance(x, heading) <= min_distance + 5.0
        ]
        return max(same_column, key=lambda heading: heading["page"])["agency"]
    return ""


def resolve_section_field(code_record, sections, previous_sections):
    """Use a field label only when the PDF explicitly supplies it as a section heading."""
    x = code_record["x"]
    y = code_record["y"]
    eligible = [section for section in sections if section["y0"] <= y]
    if eligible:
        min_distance = min(heading_distance(x, section) for section in eligible)
        same_column = [
            section for section in eligible
            if heading_distance(x, section) <= min_distance + 5.0
        ]
        return max(same_column, key=lambda section: section["y0"])["field"]
    if previous_sections:
        min_distance = min(heading_distance(x, section) for section in previous_sections)
        same_column = [
            section for section in previous_sections
            if heading_distance(x, section) <= min_distance + 5.0
        ]
        return max(same_column, key=lambda section: section["page"])["field"]
    return ""


def cell_text(words):
    """Join cell words by physical line, independent of block-local text order."""
    ordered = sorted(words, key=lambda word: ((float(word[1]) + float(word[3])) / 2.0, float(word[0])))
    lines = []
    current = []
    current_y = None
    for word in ordered:
        y = (float(word[1]) + float(word[3])) / 2.0
        if current and abs(y - current_y) > 2.5:
            lines.append(space(" ".join(str(item[4]) for item in sorted(current, key=lambda item: float(item[0])))))
            current = []
            current_y = None
        if not current:
            current_y = y
        current.append(word)
    if current:
        lines.append(space(" ".join(str(item[4]) for item in sorted(current, key=lambda item: float(item[0])))))
    return space(" ".join(line for line in lines if line))

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
    """Extract code rows and associate each cell by its physical position in the PDF."""
    page_records = []

    for page_no, page in enumerate(pages, start=1):
        blocks = page.get_text("blocks", sort=False)
        block_no_to_index = {int(block[5]): index for index, block in enumerate(blocks)}
        words_by_block = {}
        words = page.get_text("words", sort=False)
        for word in words:
            words_by_block.setdefault(int(word[5]), []).append(word)

        row_codes_by_block = {}
        code_records = []
        for word in words:
            code_token = space(str(word[4])).rstrip(".")
            if float(word[0]) >= 160.0 or not CODE_RE.fullmatch(code_token):
                continue
            block_index = block_no_to_index.get(int(word[5]))
            if block_index is None:
                continue
            record = {
                "id": len(code_records),
                "code": norm_code(code_token),
                "order": (int(word[6]), int(word[7])),
                "x": float(word[0]),
                "y": (float(word[1]) + float(word[3])) / 2.0,
                "block_index": block_index,
                "page": page_no,
            }
            code_records.append(record)
            row_codes_by_block.setdefault(block_index, []).append(record)

        code_records.sort(key=lambda record: (record["y"], record["x"]))
        headings = agency_heading_records(blocks, words_by_block)
        sections = section_field_records(blocks, words_by_block)
        page_records.append((
            page_no, blocks, words_by_block, row_codes_by_block,
            code_records, headings, sections,
        ))

    previous_headings = []
    previous_sections = []
    rows = []

    for page_no, blocks, words_by_block, row_codes_by_block, code_records, headings, sections in page_records:
        name_words_by_id = {record["id"]: [] for record in code_records}
        field_words_by_id = {record["id"]: [] for record in code_records}
        heading_blocks = {heading["block_index"] for heading in headings}
        section_blocks = {section["block_index"] for section in sections}

        if not code_records:
            previous_headings.extend({**heading, "page": page_no} for heading in headings)
            previous_sections.extend({**section, "page": page_no} for section in sections)
            continue

        for block_index, block in enumerate(blocks):
            block_words = words_by_block.get(int(block[5]), [])
            if not block_words:
                continue
            block_codes = row_codes_by_block.get(block_index, [])
            codes_inside_block = [
                record for record in code_records
                if float(block[1]) - 1.0 <= record["y"] <= float(block[3]) + 1.0
            ]

            if block_codes:
                for word in block_words:
                    x = float(word[0])
                    if not (160.0 <= x < 700.0):
                        continue
                    y = (float(word[1]) + float(word[3])) / 2.0
                    if len(block_codes) == 1 and len(codes_inside_block) <= 1:
                        target = block_codes[0]
                    else:
                        target = min(code_records, key=lambda record: abs(record["y"] - y))
                    if 160.0 <= x < 443.0:
                        name_words_by_id[target["id"]].append(word)
                    elif 443.0 <= x < 700.0:
                        field_words_by_id[target["id"]].append(word)
                continue

            text = space(str(block[4]))
            if (
                HEADER_RE.match(text)
                or block_index in heading_blocks
                or block_index in section_blocks
            ):
                continue

            cell_words = [
                word for word in block_words
                if 160.0 <= float(word[0]) < 700.0
            ]
            if not cell_words:
                continue

            block_center_y = (float(block[1]) + float(block[3])) / 2.0
            codes_inside_block = [
                record for record in code_records
                if float(block[1]) - 1.0 <= record["y"] <= float(block[3]) + 1.0
            ]
            if len(codes_inside_block) > 1:
                for word in cell_words:
                    y = (float(word[1]) + float(word[3])) / 2.0
                    target = min(code_records, key=lambda record: abs(record["y"] - y))
                    if 160.0 <= float(word[0]) < 443.0:
                        name_words_by_id[target["id"]].append(word)
                    else:
                        field_words_by_id[target["id"]].append(word)
            else:
                target = min(code_records, key=lambda record: abs(record["y"] - block_center_y))
                for word in cell_words:
                    if 160.0 <= float(word[0]) < 443.0:
                        name_words_by_id[target["id"]].append(word)
                    else:
                        field_words_by_id[target["id"]].append(word)

        for record in code_records:
            name = cell_text(name_words_by_id[record["id"]])
            field = cell_text(field_words_by_id[record["id"]])
            field_source = None
            if not field:
                section_field = resolve_section_field(record, sections, previous_sections)
                if section_field:
                    field = section_field
                    field_source = "PDF_SECTION_HEADING"

            row = {
                "code": record["code"],
                "name": name,
                "field": field,
                "agency": resolve_agency(record, headings, previous_headings),
                "page": page_no,
            }
            if field_source:
                row["fieldSource"] = field_source
            rows.append(row)

        previous_headings.extend({**heading, "page": page_no} for heading in headings)
        previous_sections.extend({**section, "page": page_no} for section in sections)

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
            if key == "agency":
                if old and new and old != new:
                    previous[key] = "; ".join(dict.fromkeys([*old.split("; "), *new.split("; ")]))
                elif not old and new:
                    previous[key] = new
                continue

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
