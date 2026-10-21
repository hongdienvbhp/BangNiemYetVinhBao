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


def series_key_from_block(block_text: str) -> str:
    """The source PDF has two row-block shapes; keep their agency state separate."""
    lines = [space(line) for line in (block_text or "").splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        return "code-first"
    if ROW_ORDINAL_RE.fullmatch(lines[0]):
        return "ordinal-first"
    first_match = ROW_CODE_LINE_RE.fullmatch(lines[0])
    if first_match and first_match.group(1) != lines[0]:
        return "ordinal-first"
    return "code-first"


def words_text(words, xmin: float, xmax: float) -> str:
    """Join words from one table cell using the source block's line/word order."""
    by_line = {}
    for word in words:
        x0 = float(word[0])
        if xmin <= x0 < xmax:
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
    if AGENCY_RE.match(text):
        text = re.sub(r"\s+STT\s+Mã TTHC.*$", "", text, flags=re.I)
        return space(text), 1
    if AGENCY_PREFIX_RE.fullmatch(text) and index + 1 < len(blocks):
        following = space(str(blocks[index + 1][4]))
        if AGENCY_BODY_RE.match(following):
            return f"{text} {following}", 2
    return None, 0


def collect_separate_cells(blocks, block_index, words_by_block, row_code_indices, need_name, need_field):
    """Collect name/field cell blocks following a code block until the next row starts."""
    name_parts = []
    field_parts = []
    for candidate_index in range(block_index + 1, len(blocks)):
        candidate = blocks[candidate_index]
        if candidate_index in row_code_indices:
            break
        candidate_text = space(str(candidate[4]))
        if AGENCY_RE.match(candidate_text) or HEADER_RE.match(candidate_text):
            break
        candidate_words = words_by_block.get(int(candidate[5]), [])
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
    """Extract row blocks and adjacent cell blocks in PDF content order."""
    page_records = []
    for page_no, page in enumerate(pages, start=1):
        blocks = page.get_text("blocks", sort=False)
        words_by_block = {}
        for word in page.get_text("words", sort=False):
            words_by_block.setdefault(int(word[5]), []).append(word)
        row_code_indices = {
            index: code
            for index, block in enumerate(blocks)
            if (code := code_from_block(str(block[4]))) is not None
        }
        row_series = {
            index: series_key_from_block(str(blocks[index][4]))
            for index in row_code_indices
        }
        page_records.append((page_no, blocks, words_by_block, row_code_indices, row_series))

    current_agency = ""
    rows = []

    for page_no, blocks, words_by_block, row_code_indices, row_series in page_records:
        block_index = 0
        while block_index < len(blocks):
            block = blocks[block_index]
            heading, consumed = agency_heading(blocks, block_index)
            if heading:
                current_agency = heading
                block_index += consumed
                continue

            code = row_code_indices.get(block_index)
            if not code:
                block_index += 1
                continue

            block_words = words_by_block.get(int(block[5]), [])
            name = words_text(block_words, 160.0, 443.0)
            field = words_text(block_words, 443.0, 700.0)
            if not name or not field:
                extra_name, extra_field = collect_separate_cells(
                    blocks,
                    block_index,
                    words_by_block,
                    row_code_indices,
                    need_name=not name,
                    need_field=not field,
                )
                if not name:
                    name = extra_name
                if not field:
                    field = extra_field

            rows.append({
                "code": code,
                "name": name,
                "field": field,
                "agency": current_agency,
                "page": page_no,
            })
            block_index += 1

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


def build(data: bytes):
    digest = hashlib.sha256(data).hexdigest()
    if digest != EXPECTED_SHA256:
        raise RuntimeError(f"SHA256 changed: {digest}")

    with fitz.open(stream=data, filetype="pdf") as pdf:
        if len(pdf) != EXPECTED_PAGES:
            raise RuntimeError(f"Page count changed: {len(pdf)}")
        rows, duplicate_conflicts = dedupe(extract_rows(pdf))

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
