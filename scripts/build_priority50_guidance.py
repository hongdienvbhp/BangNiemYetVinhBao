#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import unicodedata
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/source-audit/priority50-guidance-raw-current.json"
MASTER = ROOT / "data/thu-tuc.json"
GUIDANCE = ROOT / "data/tthc-guidance-enrichment.json"

EXPECTED_PRIORITY = 50
LOCAL_SCOPE = {
    "provinceCode": "31",
    "provinceName": "Hải Phòng",
    "wardCode": "11824",
    "wardName": "Vĩnh Bảo",
    "commune": "WARD",
}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def norm(value: object) -> str:
    text = unicodedata.normalize("NFC", str(value or ""))
    return re.sub(r"\s+", " ", text).strip()


def fold(value: object) -> str:
    text = unicodedata.normalize("NFD", norm(value))
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return text.lower()


def substantive(value: object) -> bool:
    return value not in (None, "", [], {})


def label_value(text: str, labels: tuple[str, ...]) -> str:
    lines = [norm(line) for line in str(text or "").splitlines()]
    folded_labels = [fold(label) for label in labels]
    for idx, line in enumerate(lines):
        fline = fold(line)
        for label, flabel in zip(labels, folded_labels):
            if fline == flabel or fline == flabel + ":":
                for nxt in lines[idx + 1 : idx + 5]:
                    if nxt:
                        return nxt
            if fline.startswith(flabel + ":"):
                value = norm(line[len(label) + 1 :])
                if value:
                    return value
    return ""


def _header_index(headers: list[str], needles: tuple[str, ...]) -> int | None:
    for idx, header in enumerate(headers):
        fheader = fold(header)
        if any(needle in fheader for needle in needles):
            return idx
    return None


def _find_table(raw_tables: list[dict], required: tuple[str, ...]) -> tuple[list[str], list[list[str]]] | None:
    for table in raw_tables:
        rows = table.get("rows") if isinstance(table, dict) else None
        if not isinstance(rows, list):
            continue
        for header_idx, raw_row in enumerate(rows[:6]):
            headers = [norm(cell) for cell in (raw_row or [])]
            joined = fold(" ".join(headers))
            if all(term in joined for term in required):
                body = [
                    [norm(cell) for cell in row]
                    for row in rows[header_idx + 1 :]
                    if isinstance(row, list) and any(norm(cell) for cell in row)
                ]
                return headers, body
    return None


def parse_process_tables(raw_tables: list[dict]) -> tuple[list[dict], list[dict]]:
    found = _find_table(raw_tables, ("hinh thuc nop", "thoi han"))
    if not found:
        return [], []
    headers, rows = found
    hinh_thuc_idx = _header_index(headers, ("hinh thuc nop", "cach thuc"))
    thoi_han_idx = _header_index(headers, ("thoi han",))
    phi_idx = _header_index(headers, ("phi", "le phi"))
    mo_ta_idx = _header_index(headers, ("mo ta", "ghi chu"))
    times: list[dict] = []
    fees: list[dict] = []
    seen_time: set[tuple[str, str, str]] = set()
    seen_fee: set[tuple[str, str]] = set()

    for row in rows:
        def cell(index: int | None) -> str:
            return row[index] if index is not None and index < len(row) else ""

        channel = cell(hinh_thuc_idx)
        time_value = cell(thoi_han_idx)
        description = cell(mo_ta_idx)
        fee_value = cell(phi_idx)

        if time_value:
            key = (channel, time_value, description)
            if key not in seen_time:
                item = {"hinhThuc": channel or "Không xác định", "giaTri": time_value}
                if description:
                    item["moTa"] = description
                times.append(item)
                seen_time.add(key)

        if fee_value:
            key = (channel, fee_value)
            if key not in seen_fee:
                fees.append({"hinhThuc": channel or "Không xác định", "mucThu": fee_value})
                seen_fee.add(key)
    if phi_idx is not None and not fees:
        fees.append({
            "trangThai": "not_listed_on_dvcqg",
            "mucThu": None,
            "ghiChu": "Cột Phí, lệ phí trên nguồn DVCQG chính thức không hiển thị mức thu.",
        })
    return times, fees


def parse_dossier_table(raw_tables: list[dict]) -> list[dict]:
    items: list[dict] = []
    seen: set[tuple[str, str, str, str]] = set()

    for table in raw_tables:
        rows = table.get("rows") if isinstance(table, dict) else None
        if not isinstance(rows, list):
            continue
        header_idx = None
        headers: list[str] = []
        for idx, raw_row in enumerate(rows[:6]):
            candidate = [norm(cell) for cell in (raw_row or [])]
            joined = fold(" ".join(candidate))
            if any(term in joined for term in ("ten giay to", "thanh phan ho so", "loai giay to")):
                header_idx = idx
                headers = candidate
                break
        if header_idx is None:
            continue

        name_idx = _header_index(headers, ("ten giay to", "thanh phan ho so", "loai giay to"))
        form_idx = _header_index(headers, ("mau don", "to khai", "bieu mau"))
        original_idx = _header_index(headers, ("ban chinh",))
        copy_idx = _header_index(headers, ("ban sao",))
        quantity_idx = _header_index(headers, ("so luong",))

        for raw_row in rows[header_idx + 1 :]:
            if not isinstance(raw_row, list):
                continue
            row = [norm(cell) for cell in raw_row]
            if not any(row):
                continue

            def cell(index: int | None) -> str:
                return row[index] if index is not None and index < len(row) else ""

            name = cell(name_idx)
            if not name:
                continue
            if fold(name) in {"ten giay to", "thanh phan ho so", "loai giay to"}:
                continue
            form = cell(form_idx)
            original = cell(original_idx)
            copy = cell(copy_idx)
            quantity = cell(quantity_idx)
            key = (fold(name), fold(form), fold(original or quantity), fold(copy))
            if key in seen:
                continue

            item: dict[str, Any] = {"ten": name}
            if form:
                item["bieuMau"] = form
            if original:
                item["banChinh"] = original
            if copy:
                item["banSao"] = copy
            if quantity:
                item["soLuong"] = quantity
                match_original = re.search(r"bản chính\s*:\s*(\d+)", quantity, re.IGNORECASE)
                match_copy = re.search(r"bản sao\s*:\s*(\d+)", quantity, re.IGNORECASE)
                if match_original and "banChinh" not in item:
                    item["banChinh"] = match_original.group(1)
                if match_copy and "banSao" not in item:
                    item["banSao"] = match_copy.group(1)
            items.append(item)
            seen.add(key)
    return items


def build_row(raw: dict, master_row: dict, captured_at: str) -> dict:
    code = norm(master_row.get("ma"))
    detail_url = norm(raw.get("detailUrl"))
    execution_url = norm(master_row.get("nopHoSoUrl"))
    status = norm(raw.get("status"))
    body = str(raw.get("bodyText") or "")
    tables = raw.get("tables") if isinstance(raw.get("tables"), list) else []

    sources: list[dict] = []
    provenance: dict[str, list[str]] = {}
    row: dict[str, Any] = {
        "ma": code,
        "verificationStatus": "verified_official",
        "verifiedAt": captured_at[:10],
    }

    if status == "DETAIL_CAPTURED" and detail_url:
        content_id = "dvcqg_detail"
        sources.append({
            "id": content_id,
            "url": detail_url,
            "sourceRole": "central_content_reference",
            "classification": "official_dvcqg_procedure_detail",
            "verifiedAt": captured_at,
        })

        agency = label_value(body, ("Cơ quan thực hiện", "Cơ quan có thẩm quyền"))
        result = label_value(body, ("Kết quả thực hiện", "Kết quả của việc thực hiện TTHC"))
        times, fees = parse_process_tables(tables)
        dossiers = parse_dossier_table(tables)

        for field, value in (
            ("coQuanThucHien", agency),
            ("thanhPhanHoSo", dossiers),
            ("thoiHan", times),
            ("lePhi", fees),
            ("ketQua", result),
        ):
            if substantive(value):
                row[field] = value
                provenance[field] = [content_id]

    if execution_url:
        execution_id = "dvcqg_vinhbao"
        sources.append({
            "id": execution_id,
            "url": execution_url,
            "sourceRole": "local_execution",
            "classification": "dvcqg_vinhbao_execution_scope",
            "verifiedAt": norm(master_row.get("submissionLinkCheckedAt")) or captured_at,
        })
        formality_id = norm(master_row.get("formalityId"))
        dvctt: dict[str, Any] = {
            "accessUrl": execution_url,
            "scope": deepcopy(LOCAL_SCOPE),
            "verificationStatus": norm(master_row.get("submissionLinkStatus")) or "vinhbao_scope_parameters_verified",
            "mappingMode": "formality_id" if formality_id else "keyword_fallback",
        }
        if formality_id:
            dvctt["formalityId"] = formality_id
            row["formalityId"] = formality_id
        row["dvctt"] = dvctt
        row["submissionUrl"] = execution_url
        provenance["dvctt"] = [execution_id]
        provenance["submissionUrl"] = [execution_id]

    row["sources"] = sources
    row["fieldProvenance"] = provenance
    row["reviewStatus"] = status
    return row


def build() -> dict:
    raw = load(RAW)
    master = load(MASTER)
    template = load(GUIDANCE)

    priority = [
        row for row in master.get("thuTuc") or []
        if isinstance(row, dict) and row.get("priority51") is True
    ]
    if len(priority) != EXPECTED_PRIORITY:
        raise ValueError(f"Expected {EXPECTED_PRIORITY} priority records, found {len(priority)}")

    raw_items = raw.get("items") or []
    raw_by_code = {
        norm(item.get("code")): item
        for item in raw_items
        if isinstance(item, dict) and norm(item.get("code"))
    }
    if len(raw_by_code) != EXPECTED_PRIORITY:
        raise ValueError(
            f"Raw evidence must review exactly {EXPECTED_PRIORITY} codes, found {len(raw_by_code)}"
        )

    target_codes = {norm(row.get("ma")) for row in priority}
    if set(raw_by_code) != target_codes:
        missing = sorted(target_codes - set(raw_by_code))
        extra = sorted(set(raw_by_code) - target_codes)
        raise ValueError(f"Raw/canonical priority set mismatch; missing={missing}, extra={extra}")

    captured_at = norm(raw.get("capturedAt"))
    rows = [
        build_row(raw_by_code[norm(master_row.get("ma"))], master_row, captured_at)
        for master_row in priority
    ]

    fields = (
        "coQuanThucHien",
        "thanhPhanHoSo",
        "thoiHan",
        "lePhi",
        "dvctt",
        "ketQua",
    )
    coverage = {
        field: sum(1 for row in rows if substantive(row.get(field)))
        for field in fields
    }
    unresolved = {
        field: [row["ma"] for row in rows if not substantive(row.get(field))]
        for field in fields
    }

    result = deepcopy(template)
    result["rows"] = rows
    result["coverage"] = {
        "target": EXPECTED_PRIORITY,
        "reviewed": len(rows),
        "detailCaptured": sum(1 for row in rows if row.get("reviewStatus") == "DETAIL_CAPTURED"),
        "fields": coverage,
        "unresolved": unresolved,
    }
    result["generatedFrom"] = "data/source-audit/priority50-guidance-raw-current.json"
    result["generatedAt"] = captured_at
    return result


def main() -> int:
    result = build()
    GUIDANCE.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result["coverage"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
