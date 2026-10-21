#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "data" / "thu-tuc.json"
CANDIDATES = ROOT / "data" / "source-audit" / "guidance-field-candidates.json"

ND_RE = re.compile(
    r"Nghị\s*định\s+(?:s\s*ố\s*)?(\d+)\s*/\s*(\d{4})\s*/\s*NĐ\s*-\s*CP",
    re.IGNORECASE,
)
TT_RE = re.compile(
    r"Thông\s*tư\s+(?:s\s*ố\s*)?(\d+)\s*/\s*(\d{4})\s*/\s*TT\s*-\s*([A-ZĐ0-9]+(?:\s*-\s*[A-ZĐ0-9]+)*)",
    re.IGNORECASE,
)
QD_RE = re.compile(
    r"Quyết\s*định\s+(?:s\s*ố\s*)?(\d+)\s*/\s*QĐ\s*-\s*([A-ZĐ0-9]+(?:\s*-\s*[A-ZĐ0-9]+)*)",
    re.IGNORECASE,
)
LAW_NUMBER_RE = re.compile(
    r"Luật(?:\s+[^.;]{1,100}?)?\s+s\s*ố\s*(\d+)\s*/\s*(\d{4})\s*/\s*QH\s*(\d+)",
    re.IGNORECASE,
)
LAW_NUMBER_DIRECT_RE = re.compile(
    r"Luật\s+(?:s\s*ố\s*)?(\d+)\s*/\s*(\d{4})\s*/\s*QH\s*(\d+)",
    re.IGNORECASE,
)
LAW_DATE_TEXT_RE = re.compile(
    r"((?:Luật|luật)\s+[^.;]{3,100}?)\s+ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})",
    re.IGNORECASE,
)
LAW_DATE_SLASH_RE = re.compile(
    r"((?:Luật|luật)\s+[^.;]{3,100}?)\s+ngày\s+(\d{1,2})/(\d{1,2})/(\d{4})",
    re.IGNORECASE,
)


def compact(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _suffix(value: str) -> str:
    return re.sub(r"\s+", "", value).replace("--", "-")


def _append_unique(target: list[str], value: str) -> None:
    if value and value not in target:
        target.append(value)


def extract_legal_refs(value: object) -> list[str]:
    text = compact(value)
    refs: list[str] = []

    for match in ND_RE.finditer(text):
        _append_unique(
            refs,
            f"Nghị định số {match.group(1)}/{match.group(2)}/NĐ-CP",
        )

    for match in TT_RE.finditer(text):
        _append_unique(
            refs,
            (
                f"Thông tư số {match.group(1)}/{match.group(2)}/TT-"
                f"{_suffix(match.group(3))}"
            ),
        )

    for match in QD_RE.finditer(text):
        _append_unique(
            refs,
            f"Quyết định số {match.group(1)}/QĐ-{_suffix(match.group(2))}",
        )

    for regex in (LAW_NUMBER_RE, LAW_NUMBER_DIRECT_RE):
        for match in regex.finditer(text):
            _append_unique(
                refs,
                f"Luật số {match.group(1)}/{match.group(2)}/QH{match.group(3)}",
            )

    for match in LAW_DATE_TEXT_RE.finditer(text):
        _append_unique(
            refs,
            (
                f"{compact(match.group(1))} ngày {match.group(2)} "
                f"tháng {match.group(3)} năm {match.group(4)}"
            ),
        )

    for match in LAW_DATE_SLASH_RE.finditer(text):
        _append_unique(
            refs,
            (
                f"{compact(match.group(1))} ngày {match.group(2)}/"
                f"{match.group(3)}/{match.group(4)}"
            ),
        )

    return refs


def _current_refs(value: object) -> list[str]:
    values: list[object]
    if isinstance(value, list):
        values = value
    elif value in (None, "", {}):
        return []
    else:
        values = [value]

    refs: list[str] = []
    for item in values:
        if isinstance(item, dict):
            raw = (
                item.get("soHieu")
                or item.get("value")
                or item.get("rawValue")
                or item.get("ten")
                or item.get("note")
                or ""
            )
        else:
            raw = item
        for ref in extract_legal_refs(raw):
            _append_unique(refs, ref)
    return refs


def build(canonical: dict, candidates: dict) -> dict:
    by_code = {
        str(row.get("ma") or "").strip(): row
        for row in canonical.get("thuTuc") or []
        if str(row.get("ma") or "").strip()
    }
    grouped: dict[str, dict] = defaultdict(
        lambda: {"refs": [], "unsafe": False, "sources": [], "rawValues": []}
    )

    for row in candidates.get("rows") or []:
        code = str(row.get("ma") or "").strip()
        field = (row.get("fields") or {}).get("canCuPhapLy")
        if not code or not isinstance(field, dict):
            continue
        if field.get("confidence") not in {"medium", "high"}:
            continue

        raw_values = field.get("candidateValue")
        values = raw_values if isinstance(raw_values, list) else [raw_values]
        bucket = grouped[code]
        bucket["sources"].append(row.get("source") or {})

        for raw_value in values:
            text = compact(raw_value)
            if not text:
                bucket["unsafe"] = True
                continue
            bucket["rawValues"].append(text)
            refs = extract_legal_refs(text)
            if not refs:
                bucket["unsafe"] = True
                continue
            for ref in refs:
                _append_unique(bucket["refs"], ref)

    ready: list[dict] = []
    confirmed: list[dict] = []
    needs_review: list[dict] = []
    pending_canonical: list[dict] = []

    for code, bucket in sorted(grouped.items()):
        refs = bucket["refs"]
        sources = bucket["sources"]

        if bucket["unsafe"] or not refs:
            needs_review.append({
                "ma": code,
                "field": "canCuPhapLy",
                "reason": "incomplete_or_ocr_truncated_legal_reference",
                "candidateValues": bucket["rawValues"],
                "parsedReferences": refs,
                "sources": sources,
            })
            continue

        canonical_row = by_code.get(code)
        if canonical_row is None:
            pending_canonical.append({
                "ma": code,
                "field": "canCuPhapLy",
                "candidateValue": refs,
                "confidence": "verified_reference_format",
                "sources": sources,
                "promotionStatus": "pending_canonical_phase2",
            })
            continue

        current = canonical_row.get("canCuPhapLy")
        if current not in (None, "", [], {}):
            current_refs = _current_refs(current)
            if current_refs and set(current_refs) == set(refs):
                confirmed.append({
                    "ma": code,
                    "field": "canCuPhapLy",
                    "currentValue": current,
                    "candidateValue": refs,
                    "sources": sources,
                })
            else:
                needs_review.append({
                    "ma": code,
                    "field": "canCuPhapLy",
                    "reason": "conflicts_with_canonical",
                    "currentValue": current,
                    "candidateValue": refs,
                    "sources": sources,
                })
            continue

        ready.append({
            "ma": code,
            "field": "canCuPhapLy",
            "candidateValue": refs,
            "confidence": "verified_reference_format",
            "sources": sources,
            "promotionStatus": "ready",
        })

    return {
        "format": "legal-basis-promotion-gate",
        "version": 1,
        "policy": (
            "Chỉ nhận căn cứ pháp lý có định danh văn bản hoàn chỉnh. "
            "Bất kỳ mục OCR/truncated không đủ định danh trong candidate list "
            "đều giữ cả mã ở needsReview."
        ),
        "summary": {
            "candidateCodes": len(grouped),
            "legalReady": len(ready),
            "legalConfirmedExisting": len(confirmed),
            "legalNeedsReview": len(needs_review),
            "pendingCanonicalPhase2": len(pending_canonical),
        },
        "ready": ready,
        "confirmedExisting": confirmed,
        "needsReview": needs_review,
        "pendingCanonicalPhase2": pending_canonical,
    }


def main() -> int:
    canonical = json.loads(CANONICAL.read_text(encoding="utf-8-sig"))
    candidates = json.loads(CANDIDATES.read_text(encoding="utf-8-sig"))
    result = build(canonical, candidates)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
