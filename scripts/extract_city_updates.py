#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract commune-relevant TTHC evidence from the official decision manifest.

Public Master Data is fed only by manifest entries classified as public_tthc.
Internal/process-only decisions are retained in the manifest/index but skipped.

For auto-discovered decisions, the extractor requires enough evidence to decide
whether the decision is effective at the evaluation date. If no explicit
effective-date clause can be found, the decision is marked for review instead
of being treated as current.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from datetime import date
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data/source-audit/official-decision-manifest.json"
OUTPUT = ROOT / "data/source-audit/city-updates-current.json"

CODE_RE = re.compile(r"\b\d{1,2}\.\d{3,6}\b")
TIME_OR_COLUMN_RE = re.compile(
    r"^(?:\d+(?:[.,]\d+)?\s*(?:ngày|giờ|tháng|năm)|"
    r"Không\b|Tại\b|-\s*Trung tâm|Trung tâm\b|Phí\b|Theo quy định|"
    r"Tối đa\b|Ngay trong\b)",
    re.IGNORECASE,
)

# Quyết định 3582 trình bày mã cũ và mã thay thế trong cùng một hàng bảng.
# Trích xuất văn bản thuần không giữ được ranh giới cột, nên khóa lại đúng quan
# hệ thay thế đã thể hiện trực tiếp trong phụ lục chính thức.
DECISION_ROW_OVERRIDES = {
    "3582/QĐ-UBND": {
        "2.001023": {
            "name": "Liên thông các thủ tục hành chính về đăng ký khai sinh, cấp Thẻ bảo hiểm y tế cho trẻ em dưới 6 tuổi",
            "sectionStatus": "repealed",
        },
        "2.002621": {
            "name": "Đăng ký khai sinh, đăng ký thường trú, cấp thẻ bảo hiểm y tế cho trẻ em dưới 6 tuổi",
            "sectionStatus": "repealed",
        },
        "2.000986": {
            "name": "Liên thông thủ tục hành chính về đăng ký khai sinh, đăng ký thường trú, cấp thẻ bảo hiểm y tế cho trẻ em dưới 6 tuổi",
            "sectionStatus": "repealed",
        },
        "2.002622": {
            "name": "Đăng ký khai tử, xóa đăng ký thường trú, giải quyết mai táng phí, tử tuất",
            "sectionStatus": "repealed",
        },
        "3.000722": {
            "name": "Liên thông điện tử: đăng ký khai sinh, đăng ký thường trú, cấp thẻ bảo hiểm y tế, cấp thẻ căn cước cho trẻ em dưới 6 tuổi",
            "sectionStatus": "new",
        },
        "2.002913": {
            "name": "Liên thông điện tử: đăng ký khai tử, xóa đăng ký thường trú, giải quyết mai táng phí, tử tuất",
            "sectionStatus": "new",
        },
    },
    # Ba tên trong QĐ 3584 tiếp tục ở đầu trang kế tiếp của phụ lục.
    "3584/QĐ-UBND": {
        "1.004191": {
            "name": "Thủ tục sửa đổi, bổ sung/cấp lại Giấy phép: kinh doanh tạm nhập, tái xuất; tạm nhập, tái xuất theo hình thức khác; tạm xuất, tái nhập; kinh doanh chuyển khẩu",
        },
        "1.000477": {
            "name": "Thủ tục cấp Giấy phép quá cảnh hàng hóa cấm xuất khẩu, cấm nhập khẩu; hàng hóa tạm ngừng xuất khẩu, tạm ngừng nhập khẩu; hàng hóa cấm kinh doanh theo quy định pháp luật",
        },
        "1.013771": {
            "name": "Thủ tục cấp Giấy phép gia công hàng hóa thuộc diện hàng hóa cấm xuất khẩu, cấm nhập khẩu; hàng hóa tạm ngừng xuất khẩu, tạm ngừng nhập khẩu",
        },
    },
}


def fold(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value or "")
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn").lower()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def section_status(line: str, current: str) -> str:
    value = fold(line)
    if "danh muc" not in value and not re.match(r"^[a-d][.)]\s", value):
        return current
    if "bi bai bo" in value:
        return "repealed"
    if "thay the" in value:
        return "replaced_or_replacement"
    if "sua doi" in value or "bo sung" in value:
        return "modified"
    if "ban hanh moi" in value:
        return "new"
    return current


def level_hint(line: str, current: str) -> str:
    value = fold(line)
    if "thu tuc hanh chinh" not in value and "cap xa" not in value:
        return current
    if "dung chung" in value and "cap xa" in value:
        return "shared_including_commune"
    if "cap xa" in value:
        return "commune"
    if "cap tinh" in value:
        return "province"
    return current


def extract_name(lines: list[str], line_index: int, code: str) -> str:
    line = lines[line_index]
    after = line.split(code, 1)[1].strip(" .:-") if code in line else ""
    parts = [after] if after else []
    for j in range(line_index + 1, min(len(lines), line_index + 16)):
        value = re.sub(r"\s+", " ", lines[j]).strip()
        if not value:
            continue
        if CODE_RE.search(value):
            break
        if TIME_OR_COLUMN_RE.match(value) and parts:
            break
        if value == "STT" or "Mã TTHC" in value or "Tên TTHC" in value:
            continue
        parts.append(value)
        if len(" ".join(parts)) > 220:
            break
    return re.sub(r"\s+", " ", " ".join(parts)).strip(" .;:-|")


def context_is_commune(lines: list[str], idx: int, level: str) -> bool:
    if level in {"commune", "shared_including_commune"}:
        return True
    context = " ".join(lines[max(0, idx - 20) : min(len(lines), idx + 80)])
    value = fold(context)
    compact = re.sub(r"[^a-z0-9]", "", value)
    return (
        ("trung tam" in value and ("cap xa" in value or "cac xa" in value or "pvhcc cac xa" in value))
        or "trung tam phuc vu hcc cac xa" in value
        or "trungtamphucvuhanhchinhcongcapxa" in compact
        or "trungtamphucvuhcccacxa" in compact
    )


def parse_iso_date(day: str, month: str, year: str) -> str:
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


def detect_effective_date(reader: PdfReader, decision_date: str) -> tuple[str | None, str]:
    sample = "\n".join((page.extract_text() or "") for page in reader.pages[:5])
    value = fold(sample)
    numeric_patterns = [
        r"co hieu luc(?: thi hanh)? ke tu ngay\s*(\d{1,2})[./-](\d{1,2})[./-](\d{4})",
        r"co hieu luc(?: thi hanh)? tu ngay\s*(\d{1,2})[./-](\d{1,2})[./-](\d{4})",
        r"co hieu luc(?: thi hanh)? ke tu ngay\s*(\d{1,2})\s+thang\s+(\d{1,2})\s+nam\s+(\d{4})",
        r"co hieu luc(?: thi hanh)? tu ngay\s*(\d{1,2})\s+thang\s+(\d{1,2})\s+nam\s+(\d{4})",
    ]
    for pattern in numeric_patterns:
        match = re.search(pattern, value, re.I)
        if match:
            return parse_iso_date(match.group(1), match.group(2), match.group(3)), "explicit_date_clause"

    if re.search(r"co hieu luc(?: thi hanh)?(?: ke)? tu ngay ky", value, re.I):
        return decision_date or None, "effective_from_signing_clause"

    return None, "effective_clause_not_found"


def merge_rows(rows: list[dict]) -> dict[str, dict]:
    priority = {
        "repealed": 5,
        "replaced_or_replacement": 4,
        "modified": 3,
        "new": 2,
        "published": 1,
    }
    merged: dict[str, dict] = {}
    for row in rows:
        code = row["code"]
        previous = merged.get(code)
        if not previous:
            merged[code] = row
            continue
        if priority.get(row["sectionStatus"], 0) > priority.get(previous["sectionStatus"], 0):
            previous["sectionStatus"] = row["sectionStatus"]
        previous["communeReceptionEvidence"] = bool(
            previous["communeReceptionEvidence"] or row["communeReceptionEvidence"]
        )
        if len(row.get("name") or "") > len(previous.get("name") or "") and len(row.get("name") or "") <= 240:
            previous["name"] = row["name"]
        previous["context"] = (previous.get("context", "") + " | " + row.get("context", ""))[:2400]
    return merged


def extract_decision(meta: dict, as_of: str) -> dict:
    file_path = str(meta.get("filePath") or "")
    if not file_path:
        raise ValueError(f"{meta.get('decisionNo')}: missing filePath")
    path = ROOT / file_path
    if not path.is_file():
        raise FileNotFoundError(f"{meta.get('decisionNo')}: missing PDF {file_path}")

    reader = PdfReader(str(path))
    decision_date = str(meta.get("decisionDate") or "")
    effective_date = meta.get("effectiveDate")
    effective_source = "manifest"
    if not effective_date:
        detected, source = detect_effective_date(reader, decision_date)
        effective_date = detected
        effective_source = source

    ingest_status = str(meta.get("ingestStatus") or "")
    if effective_date:
        current_state = "future_effective" if effective_date > as_of else "current_or_immediate_unless_repealed"
    elif ingest_status == "applied":
        # Baseline decisions were manually verified before this automation existed.
        current_state = "current_or_immediate_unless_repealed"
        effective_source = "baseline_manual_verification"
    else:
        current_state = "needs_effective_date_review"

    if not meta.get("field") and ingest_status != "applied":
        current_state = "needs_field_review"

    rows: list[dict] = []
    status = "published"
    level = ""
    start_page = 2 if len(reader.pages) > 2 else 0
    for page_index, page in enumerate(reader.pages):
        if page_index < start_page:
            continue
        text = page.extract_text() or ""
        lines = [re.sub(r"\s+", " ", item).strip() for item in text.splitlines()]
        for i, line in enumerate(lines):
            if not line:
                continue
            status = section_status(line, status)
            level = level_hint(line, level)
            for match in CODE_RE.finditer(line):
                code = match.group(0)
                rows.append(
                    {
                        "code": code,
                        "name": extract_name(lines, i, code),
                        "sectionStatus": status,
                        "levelHint": level,
                        "communeReceptionEvidence": context_is_commune(lines, i, level),
                        "page": page_index + 1,
                        "context": " ".join(lines[max(0, i - 3) : min(len(lines), i + 18)])[:1800],
                    }
                )

    merged = merge_rows(rows)
    for code, override in DECISION_ROW_OVERRIDES.get(str(meta.get("decisionNo") or ""), {}).items():
        if code in merged:
            merged[code].update(override)
    return {
        "decisionNo": meta.get("decisionNo"),
        "decisionDate": decision_date,
        "publishedDate": meta.get("publishedDate") or "",
        "effectiveDate": effective_date,
        "effectiveDateSource": effective_source,
        "currentStateAtAsOf": current_state,
        "classification": meta.get("classification"),
        "ingestStatus": ingest_status,
        "field": meta.get("field") or "",
        "title": meta.get("title") or "",
        "articleUrl": meta.get("articleUrl"),
        "pdfUrl": meta.get("pdfUrl"),
        "filePath": file_path,
        "pdfSha256": sha256(path),
        "pageCount": len(reader.pages),
        "rows": sorted(merged.values(), key=lambda item: item["code"]),
    }


def semantic_payload(payload: dict) -> dict:
    clone = json.loads(json.dumps(payload, ensure_ascii=False))
    clone.pop("asOf", None)
    return clone


def write_if_semantically_changed(payload: dict) -> bool:
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if OUTPUT.exists():
        old = load_json(OUTPUT)
        if semantic_payload(old) == semantic_payload(payload):
            return False
    OUTPUT.write_text(rendered, encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", default=date.today().isoformat())
    args = parser.parse_args()

    manifest = load_json(MANIFEST)
    public_meta = [
        item
        for item in manifest.get("decisions", [])
        if item.get("classification") == "public_tthc" and item.get("filePath")
    ]
    decisions = [extract_decision(meta, args.as_of) for meta in public_meta]

    all_rows: list[dict] = []
    for decision in decisions:
        for row in decision["rows"]:
            all_rows.append(
                {
                    "decisionNo": decision["decisionNo"],
                    "decisionDate": decision["decisionDate"],
                    "publishedDate": decision["publishedDate"],
                    "effectiveDate": decision["effectiveDate"],
                    "effectiveDateSource": decision["effectiveDateSource"],
                    "currentStateAtAsOf": decision["currentStateAtAsOf"],
                    "classification": decision["classification"],
                    "ingestStatus": decision["ingestStatus"],
                    "field": decision["field"],
                    "articleUrl": decision["articleUrl"],
                    "pdfUrl": decision["pdfUrl"],
                    "pdfSha256": decision["pdfSha256"],
                    **row,
                }
            )

    payload = {
        "format": "haiphong-city-tthc-updates",
        "version": 2,
        "asOf": args.as_of,
        "scope": (
            "Public TTHC decisions in the official decision manifest. "
            "Internal/process-only decisions are retained in the manifest/source index but excluded here."
        ),
        "decisions": decisions,
        "rows": all_rows,
        "summary": {
            "decisions": len(decisions),
            "uniqueCodes": len({item["code"] for item in all_rows}),
            "communeReceptionCodes": len(
                {item["code"] for item in all_rows if item["communeReceptionEvidence"]}
            ),
            "repealedCodes": len(
                {item["code"] for item in all_rows if item["sectionStatus"] == "repealed"}
            ),
            "futureEffectiveCodes": len(
                {item["code"] for item in all_rows if item["currentStateAtAsOf"] == "future_effective"}
            ),
            "needsReviewDecisions": sum(
                1 for item in decisions if str(item["currentStateAtAsOf"]).startswith("needs_")
            ),
        },
    }
    changed = write_if_semantically_changed(payload)
    print(json.dumps({**payload["summary"], "outputChanged": changed, "asOf": args.as_of}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
