#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "data" / "thu-tuc.json"
CANDIDATES = ROOT / "data" / "source-audit" / "guidance-field-candidates.json"
OUT = ROOT / "data" / "source-audit" / "guidance-field-promotion-ready.json"


def norm(value: object) -> str:
    text = unicodedata.normalize("NFD", str(value or ""))
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", text).strip().lower()


def trim_duration(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    markers = (
        " Trung tâm ", " Phục vụ hành chính", " Miễn lệ phí", " Lệ phí:",
        " Phí:", " Toàn trình", " Một phần", " Căn cứ pháp lý",
        " Dịch vụ công trực tuyến", " Nộp trực tiếp", " Địa điểm ",
    )
    cuts = [text.find(marker) for marker in markers if text.find(marker) > 0]
    if cuts:
        text = text[:min(cuts)]
    return text.strip(" -;,.")


DURATION_TOKEN_RE = re.compile(
    r"(?<!\\d)(?:\\d+(?:[.,]\\d+)?)\\s*(?:ngày|giờ|tháng)(?:\\s+làm việc)?",
    re.IGNORECASE,
)


def duration_is_unambiguous(value: str) -> bool:
    text = trim_duration(value)
    if not text:
        return False
    if re.fullmatch(r"Không quy định", text, flags=re.IGNORECASE):
        return True
    if text.lower().startswith("ngay trong ngày làm việc"):
        return True
    return len(DURATION_TOKEN_RE.findall(text)) == 1


def build(canonical: dict, candidates: dict) -> dict:
    by_code = {
        str(row.get("ma") or "").strip(): row
        for row in canonical.get("thuTuc") or []
        if str(row.get("ma") or "").strip()
    }
    duration_values: dict[str, list[dict]] = defaultdict(list)

    for row in candidates.get("rows") or []:
        code = str(row.get("ma") or "").strip()
        if code not in by_code:
            continue
        field = (row.get("fields") or {}).get("thoiHan")
        if not isinstance(field, dict) or field.get("confidence") != "high":
            continue
        value = trim_duration(str(field.get("candidateValue") or ""))
        if not value:
            continue
        duration_values[code].append({
            "value": value,
            "source": row.get("source") or {},
            "rawSnippet": row.get("rawSnippet") or "",
        })

    ready = []
    conflicts = []
    confirmed = []

    for code, items in sorted(duration_values.items()):
        canonical_row = by_code[code]
        grouped: dict[str, list[dict]] = defaultdict(list)
        for item in items:
            grouped[norm(item["value"])].append(item)

        if len(grouped) != 1:
            conflicts.append({
                "ma": code,
                "field": "thoiHan",
                "reason": "candidate_disagreement",
                "currentValue": canonical_row.get("thoiHan") or "",
                "candidates": items,
            })
            continue

        value = items[0]["value"]
        current = str(canonical_row.get("thoiHan") or "").strip()
        if not duration_is_unambiguous(value):
            conflicts.append({
                "ma": code,
                "field": "thoiHan",
                "reason": "multiple_or_ambiguous_duration_tokens",
                "currentValue": current,
                "candidateValue": value,
                "sources": [item["source"] for item in items],
            })
            continue
        if current:
            n_current, n_value = norm(current), norm(value)
            if n_current in n_value or n_value in n_current:
                confirmed.append({
                    "ma": code,
                    "field": "thoiHan",
                    "currentValue": current,
                    "candidateValue": value,
                    "sources": [item["source"] for item in items],
                })
            else:
                conflicts.append({
                    "ma": code,
                    "field": "thoiHan",
                    "reason": "conflicts_with_canonical",
                    "currentValue": current,
                    "candidateValue": value,
                    "sources": [item["source"] for item in items],
                })
            continue

        ready.append({
            "ma": code,
            "field": "thoiHan",
            "candidateValue": value,
            "confidence": "high_consensus",
            "sources": [item["source"] for item in items],
            "promotionStatus": "ready",
        })

    return {
        "format": "guidance-field-promotion-ready",
        "version": 1,
        "policy": "Chỉ promotion khi canonical đang thiếu, candidate high-confidence và mọi evidence hiện có cho cùng mã đồng thuận.",
        "summary": {
            "durationReady": len(ready),
            "durationConfirmedExisting": len(confirmed),
            "durationNeedsReview": len(conflicts),
        },
        "ready": ready,
        "confirmedExisting": confirmed,
        "needsReview": conflicts,
    }


def main() -> int:
    canonical = json.loads(CANONICAL.read_text(encoding="utf-8-sig"))
    candidates = json.loads(CANDIDATES.read_text(encoding="utf-8-sig"))
    result = build(canonical, candidates)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
