#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "source-audit" / "official-guidance-candidates.json"
OUT = ROOT / "data" / "source-audit" / "official-guidance-validated.json"


def validate_single(values: list[str]) -> dict:
    unique = list(dict.fromkeys(str(x).strip() for x in values if str(x).strip()))
    if not unique:
        return {"status": "insufficient", "value": None, "candidates": []}
    if len(unique) == 1:
        return {"status": "verified", "value": unique[0], "candidates": unique}
    return {"status": "conflicting", "value": None, "candidates": unique}


def validate_row(row: dict) -> dict:
    online = validate_single(
        [row.get("onlineServiceLevelCandidate")]
        if row.get("onlineServiceLevelCandidate") not in (None, "", "UNKNOWN")
        else []
    )
    duration = validate_single(row.get("durationCandidates") or [])

    fee_values = list(row.get("feeCandidates") or [])
    fee_values.extend(row.get("feeStatusCandidates") or [])
    fee = validate_single(fee_values)

    legal_values = list(dict.fromkeys(
        str(x).strip() for x in row.get("legalBasisCandidates") or [] if str(x).strip()
    ))
    legal = {
        "status": "verified" if legal_values else "insufficient",
        "value": legal_values if legal_values else None,
        "candidates": legal_values,
    }

    agency = validate_single(row.get("agencyCandidates") or [])

    fields = {
        "onlineServiceLevel": online,
        "thoiHan": duration,
        "phiLePhi": fee,
        "canCuPhapLy": legal,
        "coQuanThucHien": agency,
    }
    promotable = sorted(
        field for field, result in fields.items()
        if result["status"] == "verified"
    )
    return {
        "ma": row.get("ma"),
        "verificationStatus": (
            "field_validated"
            if promotable
            else "no_promotable_field"
        ),
        "promotableFields": promotable,
        "fields": fields,
        "candidateSource": "data/source-audit/official-guidance-candidates.json",
    }


def build(payload: dict) -> dict:
    rows = [validate_row(row) for row in payload.get("rows") or []]
    field_names = (
        "onlineServiceLevel",
        "thoiHan",
        "phiLePhi",
        "canCuPhapLy",
        "coQuanThucHien",
    )
    summary = {
        "codes": len(rows),
        "codesWithPromotableFields": sum(1 for row in rows if row["promotableFields"]),
    }
    for field in field_names:
        summary[field] = {
            "verified": sum(1 for row in rows if row["fields"][field]["status"] == "verified"),
            "conflicting": sum(1 for row in rows if row["fields"][field]["status"] == "conflicting"),
            "insufficient": sum(1 for row in rows if row["fields"][field]["status"] == "insufficient"),
        }
    return {
        "format": "official-guidance-field-validation",
        "version": 1,
        "source": str(SOURCE.relative_to(ROOT)),
        "policy": (
            "Chỉ field status=verified mới đủ điều kiện promotion. "
            "conflicting/insufficient phải giữ ở candidate layer."
        ),
        "summary": summary,
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
