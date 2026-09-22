#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "source-audit" / "official-guidance-candidates.json"
OUT = ROOT / "data" / "source-audit" / "official-guidance-validated.json"

LEGAL_RE = re.compile(
    r"^(?:"
    r"Nghị định\s+(?:số\s*)?\d+(?:\.\d+)?/\d{4}/NĐ-CP\b"
    r"|Thông tư\s+(?:số\s*)?\d+(?:\.\d+)?/\d{4}/TT-[A-ZĐ]+(?:-[A-ZĐ]+)*\b"
    r"|Nghị quyết\s+(?:số\s*)?\d+(?:\.\d+)?/\d{4}/NQ-[A-ZĐ]+(?:-[A-ZĐ]+)*\b"
    r"|Quyết định\s+(?:số\s*)?\d+(?:\.\d+)?/QĐ-[A-ZĐ]+(?:-[A-ZĐ]+)*\b"
    r"|Luật\s+(?:số\s*)?\d+(?:\.\d+)?/\d{4}/QH\d+\b"
    r")",
    re.IGNORECASE,
)
MONEY_RE = re.compile(r"^\d{1,3}(?:[.\s]\d{3})*(?:,\d+)?\s*đồng$", re.IGNORECASE)


def validate_single(values: list[str]) -> dict:
    unique = list(dict.fromkeys(str(x).strip() for x in values if str(x).strip()))
    if not unique:
        return {"status": "insufficient", "value": None, "candidates": []}
    if len(unique) == 1:
        return {"status": "verified", "value": unique[0], "candidates": unique}
    return {"status": "conflicting", "value": None, "candidates": unique}


def validate_fee(row: dict) -> dict:
    values = [
        str(x).strip() for x in row.get("feeCandidates") or []
        if MONEY_RE.fullmatch(str(x).strip())
    ]
    statuses = [
        str(x).strip() for x in row.get("feeStatusCandidates") or []
        if str(x).strip() == "EXEMPT"
    ]
    # Chỉ mức tiền cụ thể hoặc miễn phí/lệ phí explicit mới đủ điều kiện.
    return validate_single(values + statuses)


def validate_legal(row: dict) -> dict:
    raw = list(dict.fromkeys(
        str(x).strip() for x in row.get("legalBasisCandidates") or [] if str(x).strip()
    ))
    complete = [value for value in raw if LEGAL_RE.search(value)]
    if not complete:
        return {"status": "insufficient", "value": None, "candidates": raw}
    # Legal basis có thể có nhiều văn bản; chỉ giữ các citation hoàn chỉnh.
    return {"status": "verified", "value": complete, "candidates": raw}


def validate_row(row: dict) -> dict:
    # Không auto-promote DVCTT từ PDF flattened: mức dịch vụ phải lấy từ nguồn
    # cấu trúc/local_execution. Không auto-promote thời hạn ở pipeline này vì
    # thoiHan đã có dedicated deterministic gate (guidance-field-promotion-ready).
    online = {
        "status": "insufficient",
        "value": None,
        "candidates": [row.get("onlineServiceLevelCandidate")]
        if row.get("onlineServiceLevelCandidate") not in (None, "", "UNKNOWN") else [],
    }
    duration = {
        "status": "insufficient",
        "value": None,
        "candidates": list(row.get("durationCandidates") or []),
    }
    fee = validate_fee(row)
    legal = validate_legal(row)
    # Địa điểm tiếp nhận trong PDF flattened không đủ để kết luận cơ quan thực hiện.
    agency = {
        "status": "insufficient",
        "value": None,
        "candidates": list(row.get("agencyCandidates") or []),
    }

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
        "verificationStatus": "field_validated" if promotable else "no_promotable_field",
        "promotableFields": promotable,
        "fields": fields,
        "candidateSource": "data/source-audit/official-guidance-candidates.json",
    }


def build(payload: dict) -> dict:
    rows = [validate_row(row) for row in payload.get("rows") or []]
    field_names = (
        "onlineServiceLevel", "thoiHan", "phiLePhi", "canCuPhapLy", "coQuanThucHien",
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
        "version": 2,
        "source": SOURCE.relative_to(ROOT).as_posix(),
        "policy": (
            "Fail-closed field validator. PDF flattened không được suy diễn DVCTT, cơ quan thực hiện "
            "hoặc NOT_PUBLISHED; thoiHan do dedicated gate sở hữu. Chỉ fee explicit và citation pháp lý "
            "hoàn chỉnh mới có thể vào promotion plan, vẫn phải qua provenance/schema gate."
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
