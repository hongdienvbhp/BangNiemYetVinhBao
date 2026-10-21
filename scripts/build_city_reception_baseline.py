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

from pypdf import PdfReader

ARTICLE_URL = "https://haiphong.gov.vn/thu-tuc-hanh-chinh-76761/danh-muc-thu-tuc-hanh-chinh-tiep-nhan-tai-trung-tam-phuc-vu-hanh-chinh-cong-thanh-pho-hai-phong--760833"
PDF_URL = "https://cdn.haiphong.gov.vn/gov-hpg/1/tintuc/2025/7/danh-muc-thu-tuc-hanh-chinh-thuc-hien-tiep-nhan-tai-trung-tam-phuc-vu-hanh-chinh-cong-thanh-pho-hai-phong638871741697189500.pdf"
PUBLISHED_DATE = "2025-07-03"
EXPECTED_SHA256 = "22c2a8ab6abc6aa0df4694da6eebafe51f5a75bf76bae97f22c19af5fa082425"
EXPECTED_PAGES = 114
CODE_RE = re.compile(r"^\d{1,2}\.\d{3,6}$")
AGENCY_RE = re.compile(r"^(?:[IVXLCDM]+\.|\d+\.)\s+(?:SỞ|BAN|VĂN PHÒNG|THANH TRA|CÔNG AN|UBND|ỦY BAN)", re.I)

# The official PDF uses repeated, side-by-side tables. The old parser read tm
# without composing cm, causing text from separate table columns to overlap.
# These bounds are relative to the left edge of each repeated table template.
CODE_COLUMN_GAP = 180.0
BASE_CODE_X_CENTER = 140.0
BASE_NAME_X_MIN = 160.0
BASE_NAME_X_MAX = 443.0
BASE_FIELD_X_MAX = 700.0


def space(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def norm_code(value: str) -> str:
    value = value.strip().rstrip(".")
    if not CODE_RE.fullmatch(value):
        return value
    prefix, suffix = value.split(".", 1)
    return f"{prefix}.{suffix.ljust(6, '0')}"


def matrix_multiply(m1, m2):
    """Compose pypdf's six-element affine matrices using its documented order."""
    return (
        m1[0] * m2[0] + m1[1] * m2[2],
        m1[0] * m2[1] + m1[1] * m2[3],
        m1[2] * m2[0] + m1[3] * m2[2],
        m1[2] * m2[1] + m1[3] * m2[3],
        m1[4] * m2[0] + m1[5] * m2[2] + m2[4],
        m1[4] * m2[1] + m1[5] * m2[3] + m2[5],
    )


def cluster_code_columns(codes, gap: float = CODE_COLUMN_GAP):
    """Group code fragments by physical x-column instead of mixing page rows."""
    groups = []
    for item in sorted(codes, key=lambda row: row[1]):
        if not groups or item[1] - median([row[1] for row in groups[-1]]) > gap:
            groups.append([item])
        else:
            groups[-1].append(item)
    return groups


def fetch_pdf() -> bytes:
    req = Request(PDF_URL, headers={"User-Agent": "BangNiemYetVinhBao-City-Baseline/2.0"})
    with urlopen(req, timeout=60) as response:
        data = response.read()
    if not data.startswith(b"%PDF"):
        raise RuntimeError("Official attachment is not PDF")
    return data


def fragments(page):
    out = []

    def visitor(text, cm, tm, font, size):
        value = space(text)
        if value:
            # Compose the text matrix with the current transformation matrix.
            # Using tm[4]/tm[5] alone collapses transformed table columns.
            matrix = matrix_multiply(tm, cm)
            out.append((float(matrix[5]), float(matrix[4]), value))

    page.extract_text(visitor_text=visitor)
    return out


def column(items, lower, upper, xmin, xmax):
    selected = [item for item in items if lower < item[0] <= upper and xmin <= item[1] < xmax]
    buckets = {}
    for item in selected:
        buckets.setdefault(round(item[0], 1), []).append(item)
    lines = []
    for y in sorted(buckets, reverse=True):
        line = space(" ".join(item[2] for item in sorted(buckets[y], key=lambda row: row[1])))
        if line:
            lines.append(line)
    return space(" ".join(lines))


def extract_rows(reader):
    rows = []
    carried_by_slot = {}

    for page_no, page in enumerate(reader.pages, start=1):
        items = fragments(page)
        code_fragments = []
        for y, x, text in items:
            candidate = text.strip().rstrip(".")
            if CODE_RE.fullmatch(candidate):
                code_fragments.append((y, x, norm_code(candidate)))

        groups = cluster_code_columns(code_fragments)
        if not groups:
            continue

        centers = [median([row[1] for row in group]) for group in groups]
        headings_by_group = {index: [] for index in range(len(groups))}
        for y, x, text in items:
            heading = space(text)
            if AGENCY_RE.match(heading):
                nearest = min(range(len(centers)), key=lambda index: abs(x - centers[index]))
                headings_by_group[nearest].append((y, heading))

        for group_index, group in enumerate(groups):
            center = centers[group_index]
            # With two columns, sorted group order gives stable left/right slots.
            # On a page containing only one table, use its position on the page
            # so a continuation in the right column does not inherit left agency.
            if len(groups) > 1:
                slot = group_index
            else:
                slot = 1 if center > float(page.mediabox.width) / 2 else 0

            headings = sorted(headings_by_group[group_index], key=lambda row: -row[0])
            codes = sorted(group, key=lambda row: -row[0])
            shift = center - BASE_CODE_X_CENTER

            for index, (y, x, code) in enumerate(codes):
                upper = (codes[index - 1][0] + y) / 2 if index else min(730.0, y + 58.0)
                lower = (y + codes[index + 1][0]) / 2 if index + 1 < len(codes) else max(42.0, y - 58.0)

                agency = carried_by_slot.get(slot, "")
                above = [heading for heading in headings if heading[0] > y]
                if above:
                    agency = min(above, key=lambda heading: heading[0] - y)[1]
                if agency:
                    carried_by_slot[slot] = agency

                rows.append({
                    "code": code,
                    "name": column(items, lower, upper, BASE_NAME_X_MIN + shift, BASE_NAME_X_MAX + shift),
                    "field": column(items, lower, upper, BASE_NAME_X_MAX + shift, BASE_FIELD_X_MAX + shift),
                    "agency": agency,
                    "page": page_no,
                })

            if headings:
                carried_by_slot[slot] = headings[-1][1]

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
    reader = PdfReader(io.BytesIO(data))
    if len(reader.pages) != EXPECTED_PAGES:
        raise RuntimeError(f"Page count changed: {len(reader.pages)}")

    rows, duplicate_conflicts = dedupe(extract_rows(reader))
    if len(rows) < 300:
        raise RuntimeError(f"Implausibly small baseline: {len(rows)}")

    missing_name = [row["code"] for row in rows if not space(str(row.get("name", "")))]
    empty_field = [row["code"] for row in rows if not space(str(row.get("field", "")))]
    return {
        "format": "haiphong-city-reception-baseline",
        "version": 2,
        "publishedDate": PUBLISHED_DATE,
        "articleUrl": ARTICLE_URL,
        "pdfUrl": PDF_URL,
        "pdfSha256": digest,
        "pageCount": len(reader.pages),
        "scope": "TTHC tiếp nhận tại Trung tâm Phục vụ hành chính công thành phố Hải Phòng",
        "rowCount": len(rows),
        "missingNameCount": len(missing_name),
        "missingNameCodes": missing_name,
        "emptyFieldCount": len(empty_field),
        "emptyFieldCodes": empty_field,
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
            "rowCount", "missingNameCount", "emptyFieldCount", "duplicateConflictCount",
            "pageCount", "pdfSha256",
        )
    }
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
