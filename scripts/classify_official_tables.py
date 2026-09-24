#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "source-audit" / "vinhbao-tthc-attachment-evidence-20260906.json"
OUT = ROOT / "data" / "source-audit" / "official-table-level-classification.json"

MARKERS = (
    ("SHARED", "THỦ TỤC HÀNH CHÍNH DÙNG CHUNG"),
    ("COMMUNE", "THỦ TỤC HÀNH CHÍNH CẤP XÃ"),
    ("PROVINCE", "THỦ TỤC HÀNH CHÍNH CẤP TỈNH"),
    ("SHARED", "DANH MỤC THỦ TỤC HÀNH CHÍNH DÙNG CHUNG"),
)

def norm(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).upper().strip()

def classify_snippet(code: str, snippet: str) -> tuple[str, str] | None:
    text = norm(snippet)
    pos = text.find(code)
    if pos < 0:
        return None
    before = text[max(0, pos - 1200):pos]
    best: tuple[int, str, str] | None = None
    for classification, marker in MARKERS:
        marker_pos = before.rfind(marker)
        if marker_pos >= 0 and (best is None or marker_pos > best[0]):
            best = (marker_pos, classification, marker)
    return (best[1], best[2]) if best else None

def build(payload: dict) -> dict:
    by_code: dict[str, list[dict]] = {}
    for attachment in payload.get("attachments") or []:
        for item in attachment.get("code_snippets") or []:
            code = str(item.get("code") or "").strip()
            result = classify_snippet(code, str(item.get("snippet") or ""))
            if not code or not result:
                continue
            classification, marker = result
            by_code.setdefault(code, []).append({
                "classification": classification,
                "marker": marker,
                "attachmentUrl": attachment.get("url"),
                "articleUrls": attachment.get("article_urls") or [],
                "decisionNumbers": attachment.get("decision_numbers") or [],
                "snippet": item.get("snippet") or "",
            })

    rows = []
    conflicts = []
    for code, evidence in sorted(by_code.items()):
        classes = sorted({item["classification"] for item in evidence})
        if len(classes) != 1:
            conflicts.append({"ma": code, "classifications": classes, "evidence": evidence})
            continue
        rows.append({
            "ma": code,
            "classification": classes[0],
            "verificationStatus": "strong_official_section_heading",
            "evidenceCount": len(evidence),
            "evidence": evidence,
        })

    return {
        "format": "official-table-level-classification",
        "version": 1,
        "source": SOURCE.relative_to(ROOT).as_posix(),
        "rule": "Chỉ phân loại khi heading chính thức cấp xã/dùng chung/cấp tỉnh xuất hiện trước Mã TTHC trong cửa sổ 1200 ký tự của snippet. Không suy diễn từ địa điểm tiếp nhận.",
        "summary": {
            "resolved": len(rows),
            "conflicts": len(conflicts),
            "commune": sum(1 for x in rows if x["classification"] == "COMMUNE"),
            "shared": sum(1 for x in rows if x["classification"] == "SHARED"),
            "province": sum(1 for x in rows if x["classification"] == "PROVINCE"),
        },
        "rows": rows,
        "conflicts": conflicts,
    }

def main() -> int:
    payload = json.loads(SOURCE.read_text(encoding="utf-8-sig"))
    result = build(payload)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
