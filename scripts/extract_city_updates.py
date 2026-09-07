#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract TTHC evidence from recent Hai Phong city decisions.

This supplements the Vinh Bao portal snapshot with city-level decisions
published after that portal snapshot's practical cut-off (2026-08-31).
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
PDF_DIR = ROOT / "data/source-audit/city-updates-20260907"
OUTPUT = ROOT / "data/source-audit/city-updates-20260907.json"
AS_OF = "2026-09-07"

DECISIONS = {
    "3500/QĐ-UBND": {
        "file": "QD-3500.pdf",
        "decisionDate": "2026-08-30",
        "publishedDate": "2026-09-03",
        "effectiveDate": None,
        "articleUrl": "https://namsach.haiphong.gov.vn/cong-khai-danh-muc-thu-tuc-hanh-chinh/cong-khai-quyet-dinh-so-3500-qd-ubnd-ngay-30-8-2026-cua-ubnd-thanh-pho-hai-phong-ve-viec-cong-bo-958426",
        "pdfUrl": "https://cdn.haiphong.gov.vn/gov-hpg/6833/tintuc/2026/9/qd-3500-nv639240495312924587.pdf",
        "field": "NỘI VỤ",
    },
    "3501/QĐ-UBND": {
        "file": "QD-3501.pdf",
        "decisionDate": "2026-09-01",
        "publishedDate": "2026-09-03",
        "effectiveDate": "2027-03-01",
        "articleUrl": "https://namsach.haiphong.gov.vn/cong-khai-danh-muc-thu-tuc-hanh-chinh/cong-khai-quyet-dinh-so-3501-qd-ubnd-ngay-01-9-2026-cua-ubnd-thanh-pho-hai-phong-ve-viec-cong-bo-958422",
        "pdfUrl": "https://cdn.haiphong.gov.vn/gov-hpg/6833/tintuc/2026/9/qd-3501-yt639240494398182291.pdf",
        "field": "PHÒNG BỆNH",
    },
    "3508/QĐ-UBND": {
        "file": "QD-3508.pdf",
        "decisionDate": "2026-09-03",
        "publishedDate": "2026-09-03",
        "effectiveDate": None,
        "articleUrl": "https://namsach.haiphong.gov.vn/cong-khai-danh-muc-thu-tuc-hanh-chinh/cong-khai-quyet-dinh-so-3508-qd-ubnd-ngay-03-9-2026-cua-ubnd-thanh-pho-hai-phong-ve-viec-cong-bo-958460",
        "pdfUrl": "https://cdn.haiphong.gov.vn/gov-hpg/6833/tintuc/2026/9/qd-3508-xd639240506704881699.pdf",
        "field": "ĐƯỜNG BỘ",
    },
    "3509/QĐ-UBND": {
        "file": "QD-3509.pdf",
        "decisionDate": "2026-09-03",
        "publishedDate": "2026-09-03",
        "effectiveDate": None,
        "articleUrl": "https://namsach.haiphong.gov.vn/cong-khai-danh-muc-thu-tuc-hanh-chinh/cong-khai-quyet-dinh-so-3509-qd-ubnd-ngay-03-9-2026-cua-ubnd-thanh-pho-hai-phong-ve-viec-cong-bo-958459",
        "pdfUrl": "https://cdn.haiphong.gov.vn/gov-hpg/6833/tintuc/2026/9/qd-3509-gd639240505714779683.pdf",
        "field": "GIÁO DỤC VÀ ĐÀO TẠO",
    },
    "3517/QĐ-UBND": {
        "file": "QD-3517.pdf",
        "decisionDate": "2026-09-03",
        "publishedDate": "2026-09-04",
        "effectiveDate": None,
        "articleUrl": "https://namsach.haiphong.gov.vn/cong-khai-danh-muc-thu-tuc-hanh-chinh/cong-khai-quyet-dinh-so-3517-qd-ubnd-ngay-03-9-2026-cua-ubnd-thanh-pho-hai-phong-ve-viec-cong-bo-959309",
        "pdfUrl": "https://cdn.haiphong.gov.vn/gov-hpg/6833/tintuc/2026/9/qd-3517-ct639241368528261775.pdf",
        "field": "XUẤT CẢNH, NHẬP CẢNH",
    },
    "3523/QĐ-UBND": {
        "file": "QD-3523.pdf",
        "decisionDate": "2026-09-04",
        "publishedDate": "2026-09-04",
        "effectiveDate": None,
        "articleUrl": "https://namsach.haiphong.gov.vn/cong-khai-danh-muc-thu-tuc-hanh-chinh/cong-khai-quyet-dinh-so-3523-qd-ubnd-ngay-04-9-2026-cua-ubnd-thanh-pho-hai-phong-ve-viec-cong-bo-959292",
        "pdfUrl": "https://cdn.haiphong.gov.vn/gov-hpg/6833/tintuc/2026/9/qd-3523-vh639241356960920960.pdf",
        "field": "BÁO CHÍ",
    },
}

CODE_RE = re.compile(r"\b\d{1,2}\.\d{3,6}\b")
TIME_OR_COLUMN_RE = re.compile(
    r"^(?:\d+(?:[.,]\d+)?\s*(?:ngày|giờ|tháng|năm)|"
    r"Không\b|Tại\b|-\s*Trung tâm|Trung tâm\b|Phí\b|Theo quy định|"
    r"Tối đa\b|Ngay trong\b)",
    re.IGNORECASE,
)


def fold(value: str) -> str:
    n = unicodedata.normalize("NFD", value or "")
    return "".join(ch for ch in n if unicodedata.category(ch) != "Mn").lower()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def section_status(line: str, current: str) -> str:
    f = fold(line)
    if "danh muc" not in f and not re.match(r"^[a-d][.)]\s", f):
        return current
    if "bi bai bo" in f:
        return "repealed"
    if "thay the" in f:
        return "replaced_or_replacement"
    if "sua doi" in f or "bo sung" in f:
        return "modified"
    if "ban hanh moi" in f:
        return "new"
    return current


def level_hint(line: str, current: str) -> str:
    f = fold(line)
    if "thu tuc hanh chinh" not in f and "cap xa" not in f:
        return current
    if "dung chung" in f and "cap xa" in f:
        return "shared_including_commune"
    if "cap xa" in f:
        return "commune"
    if "cap tinh" in f:
        return "province"
    return current


def extract_name(lines: list[str], line_index: int, code: str) -> str:
    line = lines[line_index]
    after = line.split(code, 1)[1].strip(" .:-") if code in line else ""
    parts = [after] if after else []
    for j in range(line_index + 1, min(len(lines), line_index + 16)):
        s = re.sub(r"\s+", " ", lines[j]).strip()
        if not s:
            continue
        if CODE_RE.search(s):
            break
        if TIME_OR_COLUMN_RE.match(s) and parts:
            break
        if "STT" == s or "Mã TTHC" in s or "Tên TTHC" in s:
            continue
        parts.append(s)
        if len(" ".join(parts)) > 220:
            break
    name = re.sub(r"\s+", " ", " ".join(parts)).strip(" .;:-|")
    return name


def context_is_commune(lines: list[str], idx: int, level: str) -> bool:
    if level in {"commune", "shared_including_commune"}:
        return True
    context = " ".join(lines[max(0, idx - 20) : min(len(lines), idx + 80)])
    f = fold(context)
    compact = re.sub(r"[^a-z0-9]", "", f)
    return (
        ("trung tam" in f and ("cap xa" in f or "cac xa" in f or "pvhcc cac xa" in f))
        or "trung tam phuc vu hcc cac xa" in f
        or "trungtamphucvuhanhchinhcongcapxa" in compact
        or "trungtamphucvuhcccacxa" in compact
    )


def extract_decision(decision_no: str, meta: dict) -> dict:
    path = PDF_DIR / meta["file"]
    reader = PdfReader(str(path))
    rows = []
    status = "published"
    level = ""
    for page_index, page in enumerate(reader.pages):
        if page_index < 2:
            continue
        text = page.extract_text() or ""
        lines = [re.sub(r"\s+", " ", x).strip() for x in text.splitlines()]
        for i, line in enumerate(lines):
            if not line:
                continue
            status = section_status(line, status)
            level = level_hint(line, level)
            for match in CODE_RE.finditer(line):
                code = match.group(0)
                name = extract_name(lines, i, code)
                commune = context_is_commune(lines, i, level)
                rows.append({
                    "code": code,
                    "name": name,
                    "sectionStatus": status,
                    "levelHint": level,
                    "communeReceptionEvidence": commune,
                    "page": page_index + 1,
                    "context": " ".join(lines[max(0, i - 3) : min(len(lines), i + 18)])[:1800],
                })

    # Merge repeated occurrences of the same code, preferring a named row with
    # direct commune evidence and the most explicit section status.
    priority = {"repealed": 5, "replaced_or_replacement": 4, "modified": 3, "new": 2, "published": 1}
    merged = {}
    for row in rows:
        code = row["code"]
        prev = merged.get(code)
        if not prev:
            merged[code] = row
            continue
        if priority.get(row["sectionStatus"], 0) > priority.get(prev["sectionStatus"], 0):
            prev["sectionStatus"] = row["sectionStatus"]
        prev["communeReceptionEvidence"] = bool(prev["communeReceptionEvidence"] or row["communeReceptionEvidence"])
        if len(row.get("name") or "") > len(prev.get("name") or "") and len(row.get("name") or "") <= 240:
            prev["name"] = row["name"]
        prev["context"] = (prev.get("context", "") + " | " + row.get("context", ""))[:2400]

    effective = meta.get("effectiveDate")
    if effective and effective > AS_OF:
        current_state = "future_effective"
    else:
        current_state = "current_or_immediate_unless_repealed"

    return {
        "decisionNo": decision_no,
        "decisionDate": meta["decisionDate"],
        "publishedDate": meta["publishedDate"],
        "effectiveDate": effective,
        "currentStateAtAsOf": current_state,
        "field": meta["field"],
        "articleUrl": meta["articleUrl"],
        "pdfUrl": meta["pdfUrl"],
        "pdfSha256": sha256(path),
        "pageCount": len(reader.pages),
        "rows": sorted(merged.values(), key=lambda x: x["code"]),
    }


def main() -> int:
    decisions = [extract_decision(no, meta) for no, meta in DECISIONS.items()]
    all_rows = []
    for d in decisions:
        for row in d["rows"]:
            all_rows.append({
                "decisionNo": d["decisionNo"],
                "decisionDate": d["decisionDate"],
                "publishedDate": d["publishedDate"],
                "effectiveDate": d["effectiveDate"],
                "currentStateAtAsOf": d["currentStateAtAsOf"],
                "field": d["field"],
                "articleUrl": d["articleUrl"],
                "pdfUrl": d["pdfUrl"],
                "pdfSha256": d["pdfSha256"],
                **row,
            })

    payload = {
        "format": "haiphong-city-tthc-updates",
        "version": 1,
        "asOf": AS_OF,
        "scope": (
            "Public TTHC decisions newly published on Hai Phong commune portal after "
            "the Vinh Bao source snapshot practical cut-off 2026-08-31. Internal "
            "procedures/process-only decisions 3507 and 3521 are intentionally excluded."
        ),
        "decisions": decisions,
        "rows": all_rows,
        "summary": {
            "decisions": len(decisions),
            "uniqueCodes": len({x["code"] for x in all_rows}),
            "communeReceptionCodes": len({x["code"] for x in all_rows if x["communeReceptionEvidence"]}),
            "repealedCodes": len({x["code"] for x in all_rows if x["sectionStatus"] == "repealed"}),
            "futureEffectiveCodes": len({x["code"] for x in all_rows if x["currentStateAtAsOf"] == "future_effective"}),
        },
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    for d in decisions:
        print(d["decisionNo"], len(d["rows"]), "codes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
