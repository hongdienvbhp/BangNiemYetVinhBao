#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

try:
    from scripts.validate_guidance_field_candidates import build as build_duration_gate
    from scripts.validate_online_service_candidates import build as build_online_gate
    from scripts.validate_fee_candidates import build as build_fee_gate
    from scripts.validate_legal_basis_candidates import build as build_legal_gate
    from scripts.validate_official_guidance_fields import build as build_official_validation
except ModuleNotFoundError:
    from validate_guidance_field_candidates import build as build_duration_gate
    from validate_online_service_candidates import build as build_online_gate
    from validate_fee_candidates import build as build_fee_gate
    from validate_legal_basis_candidates import build as build_legal_gate
    from validate_official_guidance_fields import build as build_official_validation

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "data" / "thu-tuc.json"
FIELD_CANDIDATES = ROOT / "data" / "source-audit" / "guidance-field-candidates.json"
OFFICIAL_CANDIDATES = ROOT / "data" / "source-audit" / "official-guidance-candidates.json"
OUT = ROOT / "data" / "source-audit" / "official-guidance-promotion-plan.json"

FIELDS = (
    "onlineServiceLevel",
    "thoiHan",
    "phiLePhi",
    "canCuPhapLy",
    "coQuanThucHien",
)


def _ready_codes(payload: dict) -> list[str]:
    return sorted({
        str(item.get("ma") or "").strip()
        for item in payload.get("ready") or []
        if str(item.get("ma") or "").strip()
    })


def build(canonical: dict, field_candidates: dict, official_candidates: dict) -> dict:
    duration = build_duration_gate(canonical, field_candidates)
    online = build_online_gate(canonical, field_candidates)
    fee = build_fee_gate(canonical, field_candidates)
    legal = build_legal_gate(canonical, field_candidates)
    official = build_official_validation(official_candidates)
    agency = (official.get("summary") or {}).get("coQuanThucHien") or {}

    ready_codes = {
        "onlineServiceLevel": _ready_codes(online),
        "thoiHan": _ready_codes(duration),
        "phiLePhi": _ready_codes(fee),
        "canCuPhapLy": _ready_codes(legal),
        # Raw agency candidates are intentionally never promoted from this plan.
        # The official-guidance validator must first produce a verified agency
        # from explicitly labelled evidence.
        "coQuanThucHien": [],
    }
    all_ready_codes = sorted({
        code
        for codes in ready_codes.values()
        for code in codes
    })
    by_field = {field: len(ready_codes[field]) for field in FIELDS}

    return {
        "format": "official-guidance-promotion-plan",
        "version": 2,
        "sources": [
            "data/thu-tuc.json",
            "data/source-audit/guidance-field-candidates.json",
            "data/source-audit/official-guidance-candidates.json",
        ],
        "policy": (
            "Plan an toàn chỉ tổng hợp candidate đã qua specialized field gate. "
            "Không mutate canonical và không phát lệnh promotion cho đến khi có "
            "PR migrate canonical v5 riêng, có provenance/validator/CI đầy đủ."
        ),
        "schemaGate": {
            "requiredCanonicalContractVersion": 5,
            "canonicalVersion": canonical.get("version"),
            "status": "blocked",
            "reason": (
                "Canonical hiện chưa materialize đầy đủ contract v5; "
                "promotion phải thực hiện trong PR schema-gated riêng."
            ),
        },
        "summary": {
            "procedures": 0,
            "fieldPromotions": 0,
            "safeReadyProcedures": len(all_ready_codes),
            "safeReadyFields": sum(by_field.values()),
            "byField": by_field,
            "confirmedExisting": {
                "onlineServiceLevel": len(online.get("confirmedExisting") or []),
                "thoiHan": len(duration.get("confirmedExisting") or []),
                "phiLePhi": len(fee.get("confirmedExisting") or []),
                "canCuPhapLy": len(legal.get("confirmedExisting") or []),
                "coQuanThucHien": int(agency.get("verified") or 0),
            },
            "needsReview": {
                "onlineServiceLevel": len(online.get("needsReview") or []),
                "thoiHan": len(duration.get("needsReview") or []),
                "phiLePhi": len(fee.get("needsReview") or []),
                "canCuPhapLy": len(legal.get("needsReview") or []),
                "coQuanThucHien": {
                    "conflicting": int(agency.get("conflicting") or 0),
                    "insufficient": int(agency.get("insufficient") or 0),
                },
            },
            "pendingCanonicalPhase2": {
                "onlineServiceLevel": len(online.get("pendingCanonicalPhase2") or []),
                "phiLePhi": len(fee.get("pendingCanonicalPhase2") or []),
                "canCuPhapLy": len(legal.get("pendingCanonicalPhase2") or []),
            },
        },
        "readyCandidateCodes": ready_codes,
        "procedures": [],
    }


def main() -> int:
    canonical = json.loads(CANONICAL.read_text(encoding="utf-8-sig"))
    field_candidates = json.loads(FIELD_CANDIDATES.read_text(encoding="utf-8-sig"))
    official_candidates = json.loads(OFFICIAL_CANDIDATES.read_text(encoding="utf-8-sig"))
    result = build(canonical, field_candidates, official_candidates)
    OUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
