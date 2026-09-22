#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATED = ROOT / "data" / "source-audit" / "official-guidance-validated.json"
CANDIDATES = ROOT / "data" / "source-audit" / "official-guidance-candidates.json"
OUT = ROOT / "data" / "source-audit" / "official-guidance-promotion-plan.json"

TARGETS = {
    "onlineServiceLevel": "onlineServiceLevel",
    "thoiHan": "thoiHan",
    "phiLePhi": "phiLePhi",
    "canCuPhapLy": "canCuPhapLy",
    "coQuanThucHien": "coQuanThucHien",
}

CANDIDATE_KEYS = {
    "onlineServiceLevel": "onlineServiceLevelCandidate",
    "thoiHan": "durationCandidates",
    "phiLePhi": ("feeCandidates", "feeStatusCandidate"),
    "canCuPhapLy": "legalBasisCandidates",
    "coQuanThucHien": "agencyCandidates",
}


def _normalize_values(value: object) -> list[str]:
    if value in (None, "", [], {}):
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    return [str(value).strip()]


def evidence_for_field(candidate: dict, field: str, verified_value: object) -> list[dict]:
    wanted = set(_normalize_values(verified_value))
    out: list[dict] = []
    for evidence in candidate.get("evidence") or []:
        keys = CANDIDATE_KEYS[field]
        keys = keys if isinstance(keys, tuple) else (keys,)
        values: list[str] = []
        for key in keys:
            values.extend(_normalize_values(evidence.get(key)))
        if wanted and not wanted.intersection(values):
            continue
        item = {
            "articleUrls": evidence.get("articleUrls") or [],
            "attachmentUrl": evidence.get("attachmentUrl"),
            "decisionNumbers": evidence.get("decisionNumbers") or [],
            "segment": evidence.get("segment") or "",
        }
        if item not in out:
            out.append(item)
    return out


def build(validated: dict, candidates: dict) -> dict:
    candidate_by_code = {
        str(row.get("ma") or "").strip(): row
        for row in candidates.get("rows") or []
    }
    procedures = []
    field_counts = {field: 0 for field in TARGETS}

    for row in validated.get("rows") or []:
        code = str(row.get("ma") or "").strip()
        candidate = candidate_by_code.get(code)
        if not code or not candidate:
            continue
        promotions = []
        for field in row.get("promotableFields") or []:
            result = (row.get("fields") or {}).get(field) or {}
            if result.get("status") != "verified" or field not in TARGETS:
                continue
            value = result.get("value")
            evidence = evidence_for_field(candidate, field, value)
            # A verified value without recoverable field-level evidence is not promotable.
            if not evidence:
                continue
            promotions.append({
                "field": field,
                "targetPath": TARGETS[field],
                "value": value,
                "status": "ready_for_schema_gate",
                "provenance": evidence,
            })
            field_counts[field] += 1
        if promotions:
            procedures.append({
                "ma": code,
                "promotionStatus": "pending_canonical_schema_gate",
                "promotions": promotions,
            })

    return {
        "format": "official-guidance-promotion-plan",
        "version": 1,
        "sources": [
            str(VALIDATED.relative_to(ROOT)),
            str(CANDIDATES.relative_to(ROOT)),
        ],
        "policy": (
            "Plan only; không mutate canonical. Một field chỉ xuất hiện trong plan khi "
            "validator=verified và truy ngược được evidence cụ thể chứa cùng giá trị."
        ),
        "summary": {
            "procedures": len(procedures),
            "fieldPromotions": sum(field_counts.values()),
            "byField": field_counts,
        },
        "procedures": procedures,
    }


def main() -> int:
    validated = json.loads(VALIDATED.read_text(encoding="utf-8-sig"))
    candidates = json.loads(CANDIDATES.read_text(encoding="utf-8-sig"))
    result = build(validated, candidates)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
