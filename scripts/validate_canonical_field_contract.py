#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "data" / "canonical-field-contract.json"

REQUIRED_TOP = {
    "contract",
    "version",
    "ownerRepository",
    "canonicalPath",
    "principles",
    "enums",
    "requiredPerProcedure",
    "valueOrStatus",
    "phase1Baseline",
    "phases",
}
REQUIRED_ENUMS = {
    "authorityLevel",
    "serviceScope",
    "onlineServiceLevel",
    "dataStatus",
    "lifecycleStatus",
}
REQUIRED_SEMANTIC_FIELDS = {
    "coQuanThucHien",
    "thoiHan",
    "submissionUrl",
    "thanhPhanHoSo",
    "bieuMau",
    "quyTrinh",
    "phiLePhi",
    "ketQua",
    "canCuPhapLy",
}

def validate(payload: object) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["canonical-field-contract phải là JSON object"]

    missing = sorted(REQUIRED_TOP - set(payload))
    if missing:
        errors.append("Thiếu top-level fields: " + ", ".join(missing))

    if payload.get("version") != 5:
        errors.append("Contract version phải là 5")
    if payload.get("ownerRepository") != "hongdienvbhp/BangNiemYetVinhBao":
        errors.append("ownerRepository không đúng canonical owner")
    if payload.get("canonicalPath") != "data/thu-tuc.json":
        errors.append("canonicalPath phải là data/thu-tuc.json")

    enums = payload.get("enums")
    if not isinstance(enums, dict):
        errors.append("enums phải là object")
        enums = {}
    missing_enums = sorted(REQUIRED_ENUMS - set(enums))
    if missing_enums:
        errors.append("Thiếu enums: " + ", ".join(missing_enums))

    baseline = payload.get("phase1Baseline")
    if not isinstance(baseline, dict):
        errors.append("phase1Baseline phải là object")
    else:
        commune = baseline.get("communeAuthority") or {}
        shared = baseline.get("shared") or {}
        combined = baseline.get("combined") or {}
        for name, block in (("communeAuthority", commune), ("shared", shared), ("combined", combined)):
            if not isinstance(block, dict):
                errors.append(f"{name} phải là object")
                continue
            calc = sum(int(block.get(k, 0)) for k in ("FULL", "PARTIAL", "INFORMATION_ONLY"))
            if calc != int(block.get("total", -1)):
                errors.append(f"{name}: tổng mức DVC không bằng total")
        if isinstance(commune, dict) and isinstance(shared, dict) and isinstance(combined, dict):
            if int(commune.get("total", 0)) + int(shared.get("total", 0)) != int(combined.get("total", -1)):
                errors.append("combined.total không bằng communeAuthority.total + shared.total")
            for level in ("FULL", "PARTIAL", "INFORMATION_ONLY"):
                if int(commune.get(level, 0)) + int(shared.get(level, 0)) != int(combined.get(level, -1)):
                    errors.append(f"combined.{level} không bằng tổng hai nhóm")

    value_or_status = payload.get("valueOrStatus")
    if not isinstance(value_or_status, dict):
        errors.append("valueOrStatus phải là object")
    else:
        missing_semantic = sorted(REQUIRED_SEMANTIC_FIELDS - set(value_or_status))
        if missing_semantic:
            errors.append("Thiếu valueOrStatus fields: " + ", ".join(missing_semantic))
        for key in REQUIRED_SEMANTIC_FIELDS & set(value_or_status):
            if value_or_status[key] is not True:
                errors.append(f"valueOrStatus.{key} phải là true")

    principles = payload.get("principles")
    if not isinstance(principles, dict) or principles.get("singleWriteModel") is not True:
        errors.append("singleWriteModel phải được khóa true")
    if isinstance(principles, dict) and principles.get("consumerCopiesForbidden") is not True:
        errors.append("consumerCopiesForbidden phải được khóa true")
    return errors

def main() -> int:
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    errors = validate(payload)
    if errors:
        raise SystemExit("\n".join(errors))
    print(json.dumps({
        "contract": payload["contract"],
        "version": payload["version"],
        "ownerRepository": payload["ownerRepository"],
        "phase1Total": payload["phase1Baseline"]["combined"]["total"],
    }, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
