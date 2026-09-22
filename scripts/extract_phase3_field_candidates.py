#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "source-audit" / "vinhbao-tthc-attachment-evidence-20260906.json"
OUT = ROOT / "data" / "source-audit" / "phase3-field-candidates.json"

CODE_RE = re.compile(r"\b\d{1,2}\.\d{3,6}\b")
DURATION_RE = re.compile(
    r"(?i)(?:không\s+quy\s+định|"
    r"(?:không\s+quá\s+)?\d+(?:[.,]\d+)?\s*(?:\([^)]*\)\s*)?"
    r"(?:ngày|giờ|tháng|năm)(?:\s+làm\s+việc)?)"
)
MONEY_RE = re.compile(
    r"(?i)(?:không\s+quy\s+định|không\s+thu|miễn\s+phí|"
    r"\d{1,3}(?:[.\s]\d{3})+(?:\s*đồng)(?:\s*/\s*[^;,.\n]{1,50})?|"
    r"\d+\s*đồng(?:\s*/\s*[^;,.\n]{1,50})?)"
)
LEGAL_RE = re.compile(
    r"(?i)(?:Luật\s+[^;,.]{3,100}|"
    r"Nghị\s+định\s+số\s+[0-9A-Za-z./-]+|"
    r"Thông\s+tư\s+số\s+[0-9A-Za-z./-]+|"
    r"Quyết\s+định\s+số\s+[0-9A-Za-z./-]+)"
)

def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()

def procedure_window(code: str, snippet: str) -> str:
    text = normalize(snippet)
    pos = text.find(code)
    if pos < 0:
        return ""
    tail = text[pos + len(code):]
    nxt = CODE_RE.search(tail)
    if nxt:
        tail = tail[:nxt.start()]
    return tail[:1800].strip()

def extract_duration(window: str) -> list[dict]:
    results = []
    for match in DURATION_RE.finditer(window[:800]):
        value = normalize(match.group(0))
        if value:
            results.append({
                "value": value,
                "confidence": "medium",
                "rule": "duration_pattern_near_code",
            })
    return results[:3]

def extract_fee(window: str) -> list[dict]:
    results = []
    for match in MONEY_RE.finditer(window[:1200]):
        value = normalize(match.group(0))
        if value:
            results.append({
                "value": value,
                "confidence": "medium",
                "rule": "fee_pattern_near_code",
            })
    return results[:4]

def extract_legal(window: str) -> list[dict]:
    seen = set()
    results = []
    for match in LEGAL_RE.finditer(window):
        value = normalize(match.group(0))
        key = value.lower()
        if not value or key in seen:
            continue
        seen.add(key)
        results.append({
            "value": value,
            "confidence": "medium",
            "rule": "legal_reference_pattern_near_code",
        })
    return results[:12]

def extract_online_level(window: str) -> list[dict]:
    # Deliberately conservative: only explicit semantic phrases, never infer
    # service level from a free-standing x/× because PDF table flattening loses columns.
    text = window.lower()
    results = []
    explicit = (
        ("FULL", ("dịch vụ công trực tuyến toàn trình", "dịch vụ công toàn trình")),
        ("PARTIAL", ("dịch vụ công trực tuyến một phần", "dịch vụ công một phần")),
        ("INFORMATION_ONLY", ("chỉ cung cấp thông tin",)),
    )
    for level, phrases in explicit:
        for phrase in phrases:
            if phrase in text:
                results.append({
                    "value": level,
                    "confidence": "high",
                    "rule": f"explicit_phrase:{phrase}",
                })
                break
    return results

def build(payload: dict) -> dict:
    by_code: dict[str, dict] = {}
    for attachment in payload.get("attachments") or []:
        for item in attachment.get("code_snippets") or []:
            code = str(item.get("code") or "").strip()
            snippet = str(item.get("snippet") or "")
            if not code or not snippet:
                continue
            window = procedure_window(code, snippet)
            if not window:
                continue
            fields = {
                "thoiHan": extract_duration(window),
                "phiLePhi": extract_fee(window),
                "canCuPhapLy": extract_legal(window),
                "onlineServiceLevel": extract_online_level(window),
            }
            if not any(fields.values()):
                continue
            entry = by_code.setdefault(code, {
                "ma": code,
                "sources": [],
                "candidates": {
                    "thoiHan": [],
                    "phiLePhi": [],
                    "canCuPhapLy": [],
                    "onlineServiceLevel": [],
                },
            })
            source = {
                "attachmentUrl": attachment.get("url"),
                "articleUrls": attachment.get("article_urls") or [],
                "decisionNumbers": attachment.get("decision_numbers") or [],
                "rawWindow": window,
            }
            source_index = len(entry["sources"])
            entry["sources"].append(source)
            for field, candidates in fields.items():
                for candidate in candidates:
                    candidate = dict(candidate)
                    candidate["sourceIndex"] = source_index
                    if candidate not in entry["candidates"][field]:
                        entry["candidates"][field].append(candidate)

    rows = []
    coverage = {
        "thoiHan": 0,
        "phiLePhi": 0,
        "canCuPhapLy": 0,
        "onlineServiceLevel": 0,
    }
    for code in sorted(by_code):
        entry = by_code[code]
        for field in coverage:
            if entry["candidates"][field]:
                coverage[field] += 1
        rows.append(entry)

    return {
        "format": "phase3-field-candidates",
        "version": 1,
        "source": str(SOURCE.relative_to(ROOT)),
        "policy": {
            "promotion": "Candidates are not canonical values until field-specific validation passes.",
            "onlineServiceLevel": "Never infer FULL/PARTIAL from x/× in flattened PDF text; require explicit phrase or stronger structured source.",
            "provenance": "Every candidate references a sourceIndex containing rawWindow and official attachment/article URLs.",
        },
        "summary": {
            "proceduresWithCandidates": len(rows),
            **coverage,
        },
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
