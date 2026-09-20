#!/usr/bin/env python3
from __future__ import annotations
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data/thu-tuc.json"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
VERSION = re.compile(r"^\d{4}\.\d{2}\.\d{2}$")

def main() -> int:
    payload = json.loads(DATASET.read_text(encoding="utf-8"))
    errors: list[str] = []
    if payload.get("format") != "bangniemyet-vinhbao-master-data":
        errors.append("format không đúng canonical contract")
    if payload.get("version") != 3:
        errors.append("contract version phải là 3")
    if not VERSION.fullmatch(str(payload.get("dataset_version", ""))):
        errors.append("dataset_version phải theo YYYY.MM.DD")
    if not HEX40.fullmatch(str(payload.get("source_commit", ""))):
        errors.append("source_commit phải là Git SHA 40 ký tự")
    rows = payload.get("thuTuc")
    if not isinstance(rows, list) or not rows:
        errors.append("thuTuc phải là mảng không rỗng")
        rows = []
    seen: set[str] = set()
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            errors.append(f"thuTuc[{index}] không phải object")
            continue
        code = str(row.get("ma", "")).strip()
        name = str(row.get("ten", "")).strip()
        if not code or not name:
            errors.append(f"thuTuc[{index}] thiếu ma/ten")
        if code in seen:
            errors.append(f"trùng mã TTHC: {code}")
        seen.add(code)
    if errors:
        raise SystemExit("\n".join(errors))
    print(json.dumps({"dataset_version": payload["dataset_version"], "source_commit": payload["source_commit"], "procedures": len(rows)}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
