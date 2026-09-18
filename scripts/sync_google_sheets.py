#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Synchronize canonical TTHC projections to the two Google Sheets read models.

Safety model:
- Canonical Git data is the source of truth; Sheets never writes back to Git.
- Upsert identity is Mã TTHC.
- Human-maintained columns are preserved.
- Rows missing from the new projection are not deleted silently; they are retained
  and marked "Cần xác minh" until authoritative evidence resolves them.
- City live sync is gated until a complete city baseline is explicitly confirmed.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

from google_sheets_projection import (
    AUTO_FIELDS,
    HEADERS,
    IDX,
    merge_manual_fields,
    plan as build_plan,
)

DETAIL_SHEET = "01_CHI_TIET_TTHC"
LOG_SHEET = "NHAT_KY_CAP_NHAT"
SCOPES = ("https://www.googleapis.com/auth/spreadsheets",)

def a1_url(spreadsheet_id: str, range_a1: str) -> str:
    encoded = quote(range_a1, safe="!:'")
    return f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{encoded}"

def auth_session(credentials_json: str):
    # Lazy import keeps --dry-run usable without Google client dependencies.
    from google.auth.transport.requests import AuthorizedSession
    from google.oauth2 import service_account

    try:
        info = json.loads(credentials_json)
    except json.JSONDecodeError as exc:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON") from exc
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return AuthorizedSession(creds)

def api_json(resp: Any, context: str) -> dict[str, Any]:
    if not resp.ok:
        raise RuntimeError(f"{context}: HTTP {resp.status_code}: {resp.text[:800]}")
    return resp.json() if resp.text else {}

def read_values(session: Any, spreadsheet_id: str, range_a1: str) -> list[list[Any]]:
    resp = session.get(a1_url(spreadsheet_id, range_a1), timeout=45)
    return api_json(resp, f"read {range_a1}").get("values", [])

def batch_clear(session: Any, spreadsheet_id: str, ranges: list[str]) -> None:
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values:batchClear"
    resp = session.post(url, json={"ranges": ranges}, timeout=45)
    api_json(resp, "batchClear")

def batch_update_values(session: Any, spreadsheet_id: str, data: list[dict[str, Any]]) -> None:
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values:batchUpdate"
    payload = {"valueInputOption": "USER_ENTERED", "data": data}
    resp = session.post(url, json=payload, timeout=60)
    api_json(resp, "batchUpdate values")

def append_values(session: Any, spreadsheet_id: str, range_a1: str, rows: list[list[Any]]) -> None:
    if not rows:
        return
    url = a1_url(spreadsheet_id, range_a1) + ":append?valueInputOption=USER_ENTERED&insertDataOption=INSERT_ROWS"
    resp = session.post(url, json={"majorDimension":"ROWS","values":rows}, timeout=60)
    api_json(resp, "append log")

def padded(row: list[Any], size: int) -> list[str]:
    values = ["" if value is None else str(value) for value in row]
    return values + [""] * max(0, size - len(values))

def existing_rows(session: Any, spreadsheet_id: str) -> tuple[dict[str, dict[str, str]], int]:
    header = read_values(session, spreadsheet_id, f"{DETAIL_SHEET}!A3:AC3")
    actual = padded(header[0] if header else [], len(HEADERS))[:len(HEADERS)]
    if actual != HEADERS:
        raise RuntimeError(
            "Google Sheet header mismatch. Expected exact canonical 29-column layout; "
            f"got {actual!r}"
        )
    values = read_values(session, spreadsheet_id, f"{DETAIL_SHEET}!A4:AC")
    result: dict[str, dict[str, str]] = {}
    for raw in values:
        row = padded(raw, len(HEADERS))
        code = row[IDX["Mã TTHC"]].strip()
        if not code:
            continue
        if code in result:
            raise RuntimeError(
                f"Duplicate Mã TTHC in {DETAIL_SHEET}: {code}. "
                "Refusing to collapse ambiguous Sheet rows."
            )
        result[code] = {name: row[i] for i, name in enumerate(HEADERS)}
    return result, len(values)

def row_vector(row: dict[str, str]) -> list[str]:
    return [str(row.get(name, "") or "") for name in HEADERS]

def changed_fields(old: dict[str, str] | None, new: dict[str, str]) -> dict[str, dict[str, str]]:
    if old is None:
        return {field: {"before":"","after":new.get(field,"")} for field in AUTO_FIELDS if new.get(field,"")}
    changes: dict[str, dict[str, str]] = {}
    for field in AUTO_FIELDS:
        before = str(old.get(field,"") or "")
        after = str(new.get(field,"") or "")
        if before != after:
            changes[field] = {"before":before,"after":after}
    return changes

def unresolved_old_row(old: dict[str, str]) -> dict[str, str]:
    row = dict(old)
    row["Tình trạng hiệu lực"] = "Cần xác minh"
    row["Ghi chú cập nhật"] = "Điều chỉnh"
    note = row.get("Ghi chú chi tiết","").strip()
    marker = "[AUTO] Mã không còn trong projection mới; giữ nguyên để rà soát, không tự xóa."
    if marker not in note:
        row["Ghi chú chi tiết"] = (note + " " + marker).strip()
    return row

def sync_target(
    session: Any,
    spreadsheet_id: str,
    scope_name: str,
    projected_rows: list[dict[str, str]],
) -> dict[str, Any]:
    old_by_code, old_physical_count = existing_rows(session, spreadsheet_id)
    new_by_code: dict[str, dict[str, str]] = {}
    logs: list[list[Any]] = []
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

    for projected in projected_rows:
        code = projected["Mã TTHC"].strip()
        old = old_by_code.get(code)
        merged = merge_manual_fields(projected, old)
        new_by_code[code] = merged
        changes = changed_fields(old, merged)
        if changes:
            kind = "Thêm mới" if old is None else merged.get("Ghi chú cập nhật","Điều chỉnh")
            if merged.get("Tình trạng hiệu lực") == "Bãi bỏ":
                kind = "Bãi bỏ"
            logs.append([
                now, scope_name, code, kind,
                json.dumps({k:v["before"] for k,v in changes.items()}, ensure_ascii=False, separators=(",",":")),
                json.dumps({k:v["after"] for k,v in changes.items()}, ensure_ascii=False, separators=(",",":")),
                merged.get("Nguồn chính thức",""), "AUTO_PIPELINE", "SYNCED",
            ])

    # Never silently remove a Sheet row when canonical evidence is insufficient.
    for code, old in old_by_code.items():
        if code in new_by_code:
            continue
        held = unresolved_old_row(old)
        new_by_code[code] = held
        logs.append([
            now, scope_name, code, "Cần xác minh",
            json.dumps({"Tình trạng hiệu lực":old.get("Tình trạng hiệu lực","")}, ensure_ascii=False),
            json.dumps({"Tình trạng hiệu lực":"Cần xác minh"}, ensure_ascii=False),
            old.get("Nguồn chính thức",""), "AUTO_PIPELINE", "HELD_NOT_DELETED",
        ])

    ordered = sorted(
        new_by_code.values(),
        key=lambda r: (r.get("Lĩnh vực","").casefold(), r.get("Thủ tục hành chính","").casefold(), r.get("Mã TTHC","")),
    )
    if not ordered:
        raise RuntimeError(
            f"Refusing to sync an empty {scope_name} projection; existing Sheet data was not modified."
        )

    b_to_z: list[list[str]] = []
    ab_to_ac: list[list[str]] = []
    for row in ordered:
        vec = row_vector(row)
        b_to_z.append(vec[1:26])   # B:Z; preserve A and AA ARRAYFORMULA columns
        ab_to_ac.append(vec[27:29]) # AB:AC

    data: list[dict[str, Any]] = []
    if b_to_z:
        data.append({"range":f"{DETAIL_SHEET}!B4:Z{len(b_to_z)+3}","majorDimension":"ROWS","values":b_to_z})
        data.append({"range":f"{DETAIL_SHEET}!AB4:AC{len(ab_to_ac)+3}","majorDimension":"ROWS","values":ab_to_ac})
    if data:
        # Write the new read model before clearing stale tail rows. If the write
        # fails, the previously published Sheet remains intact instead of being
        # cleared first and left partially empty.
        batch_update_values(session, spreadsheet_id, data)

    stale_start = len(ordered) + 4
    stale_end = old_physical_count + 3
    if stale_start <= stale_end:
        batch_clear(session, spreadsheet_id, [
            f"{DETAIL_SHEET}!B{stale_start}:Z{stale_end}",
            f"{DETAIL_SHEET}!AB{stale_start}:AC{stale_end}",
        ])

    append_values(session, spreadsheet_id, f"{LOG_SHEET}!A:I", logs)
    return {
        "scope":scope_name,
        "rows":len(ordered),
        "changedCodes":len(logs),
        "heldForReview":sum(1 for row in ordered if row.get("Tình trạng hiệu lực") == "Cần xác minh"),
    }

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--plan-out", type=Path)
    p.add_argument("--commune-sheet-id", default=os.getenv("TTHC_SHEET_CAP_XA_ID",""))
    p.add_argument("--city-sheet-id", default=os.getenv("TTHC_SHEET_CAP_TP_ID",""))
    p.add_argument("--credentials-json", default=os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON",""))
    p.add_argument(
        "--city-baseline-complete",
        action="store_true",
        default=os.getenv("TTHC_CITY_BASELINE_COMPLETE","").lower() in {"1","true","yes"},
    )
    return p.parse_args()

def main() -> int:
    args = parse_args()
    sync_plan = build_plan()
    if args.plan_out:
        args.plan_out.parent.mkdir(parents=True, exist_ok=True)
        args.plan_out.write_text(json.dumps(sync_plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    summary: dict[str, Any] = {
        "communeRows":sync_plan["commune"]["count"],
        "cityRowsObserved":sync_plan["city"]["count"],
        "reviewCount":sync_plan["reviewCount"],
        "cityCoverage":sync_plan["city"]["coverage"],
        "dryRun":args.dry_run,
    }
    if args.dry_run:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    if not args.credentials_json:
        raise RuntimeError("Missing GOOGLE_SERVICE_ACCOUNT_JSON")
    if not args.commune_sheet_id:
        raise RuntimeError("Missing TTHC_SHEET_CAP_XA_ID")
    session = auth_session(args.credentials_json)
    summary["commune"] = sync_target(
        session, args.commune_sheet_id, "Cấp xã", sync_plan["commune"]["rows"]
    )

    if args.city_baseline_complete:
        if not args.city_sheet_id:
            raise RuntimeError("TTHC_CITY_BASELINE_COMPLETE=true but TTHC_SHEET_CAP_TP_ID is missing")
        summary["city"] = sync_target(
            session, args.city_sheet_id, "Cấp thành phố", sync_plan["city"]["rows"]
        )
    else:
        summary["city"] = {
            "skipped":True,
            "reason":"PARTIAL_CITY_BASELINE",
            "message":"City read model is planned but not auto-published until completeness is verified.",
        }

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
