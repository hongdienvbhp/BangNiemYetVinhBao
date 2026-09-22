#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "source-audit" / "vinhbao-tthc-attachment-evidence-20260906.json"
OUT = ROOT / "data" / "source-audit" / "guidance-field-candidates.json"

DURATION_RE = re.compile(
    r"(?P<value>(?:Ngay trong ngày làm việc|Không quy định|\d+(?:[.,]\d+)?\s*(?:ngày|giờ|tháng)(?:\s+làm việc)?(?:[^\n\r\x07]{0,90})?))",
    re.IGNORECASE,
)
LEGAL_RE = re.compile(
    r"(?P<value>(?:Luật|Nghị định|Thông tư|Quyết định)\s+(?:số\s*)?[^.;\n\r\x07]{3,180})",
    re.IGNORECASE,
)
FEE_MARKERS = (
    "không thu phí",
    "không quy định",
    "không có",
    "lệ phí:",
    "phí:",
)
ONLINE_PATTERNS = (
    ("FULL", re.compile(r"\bx\s+Toàn\s+trình\b|\bToàn\s+trình\s+x\b", re.IGNORECASE)),
    ("PARTIAL", re.compile(r"\bx\s+Một\s+phần\b|\bMột\s+phần\s+x\b", re.IGNORECASE)),
)


def compact(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def local_window(snippet: str, code: str, before: int = 120, after: int = 1100) -> str:
    raw = str(snippet or "")
    pos = raw.find(code)
    if pos < 0:
        return compact(raw[:after])
    return compact(raw[max(0, pos - before): pos + len(code) + after])


def duration_candidate(window: str, code: str) -> dict | None:
    pos = window.find(code)
    tail = window[pos + len(code):] if pos >= 0 else window
    match = DURATION_RE.search(tail[:500])
    if not match:
        return None
    value = compact(match.group("value"))
    confidence = "high" if match.start() < 220 else "medium"
    return {"candidateValue": value, "confidence": confidence}


def online_candidate(window: str, code: str) -> dict | None:
    pos = window.find(code)
    tail = window[pos + len(code):] if pos >= 0 else window
    scope = tail[:700]
    matches = [(level, rx.search(scope)) for level, rx in ONLINE_PATTERNS]
    found = [(level, m) for level, m in matches if m]
    if len(found) != 1:
        return None
    level, match = found[0]
    return {
        "candidateValue": level,
        "confidence": "high" if match.start() < 500 else "medium",
    }


def fee_candidate(window: str, code: str) -> dict | None:
    pos = window.find(code)
    tail = window[pos + len(code):] if pos >= 0 else window
    low = tail.lower()
    hits = []
    for marker in FEE_MARKERS:
        idx = low.find(marker)
        if 0 <= idx < 750:
            hits.append((idx, marker))
    if not hits:
        return None
    idx, marker = sorted(hits)[0]
    excerpt = compact(tail[idx: idx + 260])
    return {
        "candidateValue": excerpt,
        "confidence": "high" if idx < 500 else "medium",
        "marker": marker,
    }


def legal_candidate(window: str, code: str) -> dict | None:
    pos = window.find(code)
    tail = window[pos + len(code):] if pos >= 0 else window
    values = []
    for match in LEGAL_RE.finditer(tail[:1000]):
        value = compact(match.group("value"))
        if value and value not in values:
            values.append(value)
        if len(values) >= 6:
            break
    if not values:
        return None
    return {
        "candidateValue": values,
        "confidence": "medium",
    }


def build(payload: dict) -> dict:
    rows = []
    stats = {"procedures": 0, "duration": 0, "onlineServiceLevel": 0, "fee": 0, "legalBasis": 0}
    seen_codes = set()

    for attachment in payload.get("attachments") or []:
        for item in attachment.get("code_snippets") or []:
            code = str(item.get("code") or "").strip()
            if not code:
                continue
            window = local_window(str(item.get("snippet") or ""), code)
            fields = {}

            duration = duration_candidate(window, code)
            if duration:
                fields["thoiHan"] = duration
                stats["duration"] += 1

            online = online_candidate(window, code)
            if online:
                fields["onlineServiceLevel"] = online
                stats["onlineServiceLevel"] += 1

            fee = fee_candidate(window, code)
            if fee:
                fields["phiLePhi"] = fee
                stats["fee"] += 1

            legal = legal_candidate(window, code)
            if legal:
                fields["canCuPhapLy"] = legal
                stats["legalBasis"] += 1

            if not fields:
                continue

            seen_codes.add(code)
            rows.append({
                "ma": code,
                "fields": fields,
                "source": {
                    "attachmentUrl": attachment.get("url"),
                    "articleUrls": attachment.get("article_urls") or [],
                    "decisionNumbers": attachment.get("decision_numbers") or [],
                },
                "rawSnippet": window,
                "promotionStatus": "candidate_only",
            })

    stats["procedures"] = len(seen_codes)
    return {
        "format": "guidance-field-candidates",
        "version": 1,
        "source": str(SOURCE.relative_to(ROOT)),
        "policy": (
            "Candidate layer only. No value is promoted to canonical until field-specific "
            "validation confirms table-column alignment and provenance."
        ),
        "summary": stats,
        "rows": rows,
    }


def main() -> int:
    payload = json.loads(SOURCE.read_text(encoding="utf-8-sig"))
    result = build(payload)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
