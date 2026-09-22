#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "data" / "thu-tuc.json"
CANDIDATES = ROOT / "data" / "source-audit" / "guidance-field-candidates.json"


def normalize_fee_candidate(value: object) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if re.match(r"^Không\s+quy\s+định(?:\s|$)", text, re.IGNORECASE):
        return "Không quy định"
    if re.match(r"^Không\s+thu\s+phí(?:\s|$)", text, re.IGNORECASE):
        return "Không thu phí"
    return None


def _current_marker(value: object) -> str | None:
    if isinstance(value, str):
        return normalize_fee_candidate(value)
    if isinstance(value, dict):
        for key in ("rawValue", "value", "note"):
            marker = normalize_fee_candidate(value.get(key))
            if marker:
                return marker
    return None


def build(canonical: dict, candidates: dict) -> dict:
    by_code = {
        str(row.get("ma") or "").strip(): row
        for row in canonical.get("thuTuc") or []
        if str(row.get("ma") or "").strip()
    }
    grouped: dict[str, list[dict]] = defaultdict(list)

    for row in candidates.get("rows") or []:
        code = str(row.get("ma") or "").strip()
        field = (row.get("fields") or {}).get("phiLePhi")
        if not code or not isinstance(field, dict):
            continue
        if field.get("confidence") != "high":
            continue
        raw_value = re.sub(
            r"\s+", " ", str(field.get("candidateValue") or "")
        ).strip()
        grouped[code].append({
            "value": normalize_fee_candidate(raw_value),
            "rawValue": raw_value,
            "source": row.get("source") or {},
            "rawSnippet": row.get("rawSnippet") or "",
        })

    ready: list[dict] = []
    confirmed: list[dict] = []
    needs_review: list[dict] = []
    pending_canonical: list[dict] = []

    for code, items in sorted(grouped.items()):
        safe_items = [item for item in items if item["value"]]
        unsafe_items = [item for item in items if not item["value"]]

        if unsafe_items:
            needs_review.append({
                "ma": code,
                "field": "phiLePhi",
                "reason": (
                    "mixed_candidate_quality"
                    if safe_items
                    else "unsafe_or_truncated_fee_text"
                ),
                "candidateValues": [item["rawValue"] for item in items],
                "sources": [item["source"] for item in items],
            })
            continue

        values = sorted({str(item["value"]) for item in safe_items})
        if len(values) != 1:
            needs_review.append({
                "ma": code,
                "field": "phiLePhi",
                "reason": "candidate_disagreement",
                "candidateValues": values,
                "sources": [item["source"] for item in safe_items],
            })
            continue

        value = values[0]
        sources = [item["source"] for item in safe_items]
        canonical_row = by_code.get(code)

        if canonical_row is None:
            pending_canonical.append({
                "ma": code,
                "field": "phiLePhi",
                "candidateValue": value,
                "confidence": "high_consensus",
                "sources": sources,
                "promotionStatus": "pending_canonical_phase2",
            })
            continue

        current = canonical_row.get("phiLePhi")
        if current not in (None, "", [], {}):
            current_marker = _current_marker(current)
            if current_marker == value:
                confirmed.append({
                    "ma": code,
                    "field": "phiLePhi",
                    "currentValue": current,
                    "candidateValue": value,
                    "sources": sources,
                })
            else:
                needs_review.append({
                    "ma": code,
                    "field": "phiLePhi",
                    "reason": "conflicts_with_canonical",
                    "currentValue": current,
                    "candidateValue": value,
                    "sources": sources,
                })
            continue

        ready.append({
            "ma": code,
            "field": "phiLePhi",
            "candidateValue": value,
            "confidence": "high_consensus",
            "sources": sources,
            "promotionStatus": "ready",
        })

    return {
        "format": "fee-guidance-promotion-gate",
        "version": 1,
        "policy": (
            "Chỉ tự chuẩn hóa phiLePhi khi ô candidate bắt đầu rõ ràng bằng "
            "'Không quy định' hoặc 'Không thu phí'. Text dính cột, mức thu bị "
            "cắt cụt hoặc marker mơ hồ phải giữ needsReview."
        ),
        "summary": {
            "candidateCodes": len(grouped),
            "feeReady": len(ready),
            "feeConfirmedExisting": len(confirmed),
            "feeNeedsReview": len(needs_review),
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
