#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "data" / "thu-tuc.json"
CANDIDATES = ROOT / "data" / "source-audit" / "guidance-field-candidates.json"

ALLOWED_LEVELS = {"FULL", "PARTIAL", "INFORMATION_ONLY", "NONE", "UNKNOWN"}


def build(canonical: dict, candidates: dict) -> dict:
    by_code = {
        str(row.get("ma") or "").strip(): row
        for row in canonical.get("thuTuc") or []
        if str(row.get("ma") or "").strip()
    }
    grouped: dict[str, list[dict]] = defaultdict(list)

    for row in candidates.get("rows") or []:
        code = str(row.get("ma") or "").strip()
        field = (row.get("fields") or {}).get("onlineServiceLevel")
        if not code or not isinstance(field, dict):
            continue
        if field.get("confidence") != "high":
            continue
        value = str(field.get("candidateValue") or "").strip().upper()
        if value not in ALLOWED_LEVELS:
            continue
        grouped[code].append({
            "value": value,
            "source": row.get("source") or {},
            "rawSnippet": row.get("rawSnippet") or "",
        })

    ready: list[dict] = []
    confirmed: list[dict] = []
    needs_review: list[dict] = []
    pending_canonical: list[dict] = []

    for code, items in sorted(grouped.items()):
        values = sorted({item["value"] for item in items})
        sources = [item["source"] for item in items]

        if len(values) != 1:
            needs_review.append({
                "ma": code,
                "field": "onlineServiceLevel",
                "reason": "candidate_disagreement",
                "candidateValues": values,
                "sources": sources,
            })
            continue

        value = values[0]
        canonical_row = by_code.get(code)
        if canonical_row is None:
            pending_canonical.append({
                "ma": code,
                "field": "onlineServiceLevel",
                "candidateValue": value,
                "confidence": "high_consensus",
                "sources": sources,
                "promotionStatus": "pending_canonical_phase2",
            })
            continue

        current = str(canonical_row.get("onlineServiceLevel") or "").strip().upper()
        if current and current != "UNKNOWN":
            if current == value:
                confirmed.append({
                    "ma": code,
                    "field": "onlineServiceLevel",
                    "currentValue": current,
                    "candidateValue": value,
                    "sources": sources,
                })
            else:
                needs_review.append({
                    "ma": code,
                    "field": "onlineServiceLevel",
                    "reason": "conflicts_with_canonical",
                    "currentValue": current,
                    "candidateValue": value,
                    "sources": sources,
                })
            continue

        ready.append({
            "ma": code,
            "field": "onlineServiceLevel",
            "candidateValue": value,
            "confidence": "high_consensus",
            "sources": sources,
            "promotionStatus": "ready",
        })

    return {
        "format": "online-service-promotion-gate",
        "version": 1,
        "policy": (
            "Chỉ promotion onlineServiceLevel khi candidate high-confidence, "
            "mọi evidence cùng mã đồng thuận và mã đã tồn tại trong canonical. "
            "Mã chưa có trong canonical được giữ pending_canonical_phase2."
        ),
        "summary": {
            "candidateCodes": len(grouped),
            "onlineReady": len(ready),
            "onlineConfirmedExisting": len(confirmed),
            "onlineNeedsReview": len(needs_review),
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
