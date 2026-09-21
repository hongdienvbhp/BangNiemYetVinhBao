#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from scripts.canonical_v4 import upgrade_payload_to_v4
except ModuleNotFoundError:
    from canonical_v4 import upgrade_payload_to_v4

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "data/thu-tuc.json"
FALLBACK = ROOT / "js/master-data-fallback.js"


def _fallback_text(master: dict) -> str:
    payload = json.dumps(master, ensure_ascii=False, separators=(",", ":"))
    return (
        "/* Generated from data/thu-tuc.json canonical. Do not edit manually. */\n"
        f"window.TTHC_MASTER_DATA={payload};\n"
        "window.TTHC_DATA={...(window.TTHC_DATA||{}),"
        "updatedAt:window.TTHC_MASTER_DATA.updatedAt,"
        "source:window.TTHC_MASTER_DATA.source,"
        "sourceSnapshotDate:window.TTHC_MASTER_DATA.sourceSnapshotDate,"
        "thuTuc:window.TTHC_MASTER_DATA.thuTuc};\n"
    )


def migrate(check: bool = False) -> dict:
    before = json.loads(MASTER.read_text(encoding="utf-8"))
    after = upgrade_payload_to_v4(before, ROOT)

    if len(after.get("thuTuc") or []) != len(before.get("thuTuc") or []):
        raise ValueError("Migration không được thay đổi số lượng TTHC")

    master_text = json.dumps(after, ensure_ascii=False, indent=2) + "\n"
    fallback_text = _fallback_text(after)

    if check:
        current_master = MASTER.read_text(encoding="utf-8")
        current_fallback = FALLBACK.read_text(encoding="utf-8")
        if current_master != master_text:
            raise SystemExit("data/thu-tuc.json chưa ở canonical v4 deterministic")
        if current_fallback != fallback_text:
            raise SystemExit("js/master-data-fallback.js chưa đồng bộ canonical v4")
    else:
        MASTER.write_text(master_text, encoding="utf-8")
        FALLBACK.write_text(fallback_text, encoding="utf-8")

    return {
        "procedures": len(after.get("thuTuc") or []),
        "contract_version": after.get("version"),
        "dataset_version": after.get("dataset_version"),
        "source_commit": after.get("source_commit"),
        "check": check,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    print(json.dumps(migrate(check=args.check), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
