#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "data/thu-tuc.json"
GUIDANCE = ROOT / "data/tthc-guidance-enrichment.json"
FIELDS = ("coQuanThucHien", "thanhPhanHoSo", "thoiHan", "lePhi", "dvctt", "ketQua")
TARGET = 50


def filled(value: object) -> bool:
    return value not in (None, "", [], {})


def validate(require_complete: bool = False) -> tuple[list[str], dict]:
    errors: list[str] = []
    master = json.loads(MASTER.read_text(encoding="utf-8-sig"))
    guidance = json.loads(GUIDANCE.read_text(encoding="utf-8-sig"))
    target_codes = {
        str(row.get("ma") or "").strip()
        for row in master.get("thuTuc") or []
        if isinstance(row, dict) and row.get("priority51") is True
    }
    if len(target_codes) != TARGET:
        errors.append(f"canonical priority set phải có {TARGET} mã, hiện {len(target_codes)}")

    rows = guidance.get("rows") or []
    by_code = {
        str(row.get("ma") or "").strip(): row
        for row in rows
        if isinstance(row, dict) and str(row.get("ma") or "").strip()
    }
    if set(by_code) != target_codes:
        errors.append(
            "guidance rows phải đúng tập 50 priority active; "
            f"missing={sorted(target_codes-set(by_code))}, extra={sorted(set(by_code)-target_codes)}"
        )

    counts = {field: sum(1 for row in by_code.values() if filled(row.get(field))) for field in FIELDS}
    unresolved = {
        field: sorted(code for code, row in by_code.items() if not filled(row.get(field)))
        for field in FIELDS
    }

    for code, row in by_code.items():
        prov = row.get("fieldProvenance") or {}
        for field in FIELDS:
            if filled(row.get(field)) and not prov.get(field):
                errors.append(f"{code}: {field} có dữ liệu nhưng thiếu fieldProvenance")

    if require_complete:
        incomplete = {field: codes for field, codes in unresolved.items() if codes}
        if incomplete:
            errors.append("P1 chưa complete 50/50 cho mọi field: " + json.dumps(incomplete, ensure_ascii=False))

    report = {"target": TARGET, "reviewed": len(by_code), "counts": counts, "unresolved": unresolved}
    return errors, report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()
    errors, report = validate(args.require_complete)
    print(json.dumps(report, ensure_ascii=False))
    if errors:
        raise SystemExit("\n".join(errors))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
