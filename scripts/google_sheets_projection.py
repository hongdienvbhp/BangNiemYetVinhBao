#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build deterministic Google Sheets read-model projections from canonical TTHC data.

BangNiemYetVinhBao remains the canonical owner. Google Sheets is a read model only.
No legal status is inferred from third-party sources.
"""
from __future__ import annotations

import json
import re
import unicodedata
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "data/thu-tuc.json"
EXCLUDED = ROOT / "data/master-data-excluded.json"
CITY_UPDATES = ROOT / "data/source-audit/city-updates-current.json"
DELTA = ROOT / "data/source-audit/latest-master-delta.json"
MANIFEST = ROOT / "data/source-audit/official-decision-manifest.json"

HEADERS = [
    "STT","Mã TTHC","Thủ tục hành chính","Lĩnh vực","Bộ/ngành quản lý",
    "Cơ quan công bố","Cơ quan/đơn vị giải quyết","Cấp thực hiện",
    "Quyết định ban hành/công bố","Quy trình nội bộ","Thời gian giải quyết",
    "Thời gian sau rút ngắn","Phí","Lệ phí","Dịch vụ công","Quy trình ISO",
    "Tình trạng hiệu lực","Ngày hiệu lực","Ngày hết hiệu lực/bãi bỏ",
    "Ghi chú cập nhật","Quyết định/văn bản thay thế, bãi bỏ","Nguồn chính thức",
    "Nguồn đối soát bổ sung","Ngày kiểm tra/cập nhật","Mã lĩnh vực/nhóm báo cáo",
    "Đã công khai tại Trung tâm?","Cần đối soát?","Người cập nhật","Ghi chú chi tiết",
]
IDX = {name: i for i, name in enumerate(HEADERS)}
AUTO_FIELDS = {
    "Mã TTHC","Thủ tục hành chính","Lĩnh vực","Cơ quan công bố",
    "Cơ quan/đơn vị giải quyết","Cấp thực hiện","Quyết định ban hành/công bố",
    "Thời gian giải quyết","Phí","Dịch vụ công","Tình trạng hiệu lực",
    "Ngày hiệu lực","Ngày hết hiệu lực/bãi bỏ","Ghi chú cập nhật",
    "Quyết định/văn bản thay thế, bãi bỏ","Nguồn chính thức",
    "Nguồn đối soát bổ sung","Ngày kiểm tra/cập nhật",
}
MANUAL_FIELDS = set(HEADERS) - AUTO_FIELDS - {"STT","Cần đối soát?"}

def load(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return deepcopy(default)
    return json.loads(path.read_text(encoding="utf-8-sig"))

def fold(value: Any) -> str:
    text = unicodedata.normalize("NFD", str(value or ""))
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn").lower()

def first(*values: Any) -> str:
    for value in values:
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""

def canonical_code(row: dict[str, Any]) -> str:
    return first(row.get("ma"), row.get("code"))

def status_for_excluded(row: dict[str, Any]) -> str:
    marker = fold(first(row.get("verificationStatus"), row.get("exclusionReason")))
    if "future_effective" in marker or "chua co hieu luc" in marker or "chua den ngay hieu luc" in marker:
        return "Chưa hiệu lực"
    if "repeal" in marker or "bai bo" in marker:
        return "Bãi bỏ"
    if "het hieu luc" in marker:
        return "Hết hiệu lực"
    return "Cần xác minh"

def scope_for_master(row: dict[str, Any]) -> str:
    cap = fold(row.get("cap"))
    if not cap:
        return "unknown"
    if cap.startswith("cap tinh") or cap.startswith("tinh"):
        return "city"
    if cap.startswith("xa") or cap.startswith("cap xa"):
        return "commune"
    if "cap tinh - tiep nhan" in cap:
        return "city"
    if "cap xa" in cap and "cap tinh" not in cap:
        return "commune"
    return "unknown"

def delta_notes(delta: dict[str, Any]) -> dict[str, str]:
    notes: dict[str, str] = {}
    for row in delta.get("added", []):
        if row.get("ma"):
            notes[str(row["ma"])] = "Thêm mới"
    for row in delta.get("changed", []):
        if row.get("ma"):
            notes[str(row["ma"])] = "Điều chỉnh"
    for row in delta.get("removed", []):
        if row.get("ma"):
            # A delta only proves that the code left the public projection. It is
            # not, by itself, legal evidence that the procedure was repealed.
            notes[str(row["ma"])] = "Loại khỏi danh mục công khai; cần xác minh hiệu lực"
    return notes

def base_projection(
    row: dict[str, Any],
    *,
    status: str,
    note: str,
    level: str | None = None,
    decision: str | None = None,
    effective_date: str | None = None,
    snapshot_date: str | None = None,
    source_url: str | None = None,
    attachment_url: str | None = None,
) -> dict[str, str]:
    code = canonical_code(row)
    qd = first(decision, row.get("quyetDinh"))
    source = first(source_url, row.get("sourceArticleUrl"))
    attachment = first(attachment_url, row.get("sourceAttachmentUrl"))
    cap = first(level, row.get("cap"))
    effective = first(effective_date, row.get("futureEffectiveDate"))
    snapshot = first(snapshot_date, row.get("sourceSnapshotDate"))
    result = {name: "" for name in HEADERS}
    result.update({
        "Mã TTHC": code,
        "Thủ tục hành chính": first(row.get("ten"), row.get("name")),
        "Lĩnh vực": first(row.get("linhVuc"), row.get("field")),
        "Cơ quan công bố": "UBND thành phố Hải Phòng" if "QĐ-UBND" in qd else "",
        "Cơ quan/đơn vị giải quyết": first(row.get("coQuan")),
        "Cấp thực hiện": cap,
        "Quyết định ban hành/công bố": qd,
        "Thời gian giải quyết": first(row.get("thoiHan")),
        "Phí": first(row.get("phi")),
        "Dịch vụ công": first(row.get("dvctt")),
        "Tình trạng hiệu lực": status,
        "Ngày hiệu lực": effective,
        "Ghi chú cập nhật": note,
        "Quyết định/văn bản thay thế, bãi bỏ": qd if status in {"Bãi bỏ","Hết hiệu lực"} else "",
        "Nguồn chính thức": source,
        "Nguồn đối soát bổ sung": attachment,
        "Ngày kiểm tra/cập nhật": snapshot,
    })
    return result

def build_commune_rows() -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    master = load(MASTER, {"thuTuc": []})
    excluded = load(EXCLUDED, {"rows": []})
    notes = delta_notes(load(DELTA, {}))
    rows: list[dict[str, str]] = []
    review: list[dict[str, Any]] = []

    for raw in master.get("thuTuc", []):
        scope = scope_for_master(raw)
        if scope == "commune":
            code = canonical_code(raw)
            rows.append(base_projection(raw, status="Còn hiệu lực", note=notes.get(code, "Không thay đổi")))
        elif scope == "unknown":
            review.append({"scope":"commune","code":canonical_code(raw),"reason":"unclassified_authority","cap":raw.get("cap","")})

    for raw in excluded.get("rows", []):
        scope = scope_for_master(raw)
        if scope == "commune":
            code = canonical_code(raw)
            status = status_for_excluded(raw)
            status_note = {
                "Bãi bỏ": "Bãi bỏ",
                "Hết hiệu lực": "Hết hiệu lực",
                "Chưa hiệu lực": "Chưa hiệu lực",
                "Cần xác minh": "Cần xác minh",
            }.get(status, "Điều chỉnh")
            rows.append(base_projection(raw, status=status, note=status_note))
            if status == "Cần xác minh":
                review.append({"scope":"commune","code":code,"reason":"excluded_status_uncertain"})
        elif scope == "unknown":
            review.append({"scope":"commune","code":canonical_code(raw),"reason":"unclassified_excluded_authority","cap":raw.get("cap","")})

    return dedupe_rows(rows, review, "commune"), review

def city_update_candidates() -> list[dict[str, Any]]:
    payload = load(CITY_UPDATES, {"decisions": []})
    latest: dict[str, dict[str, Any]] = {}
    for decision in payload.get("decisions", []):
        decision_date = first(decision.get("decisionDate"))
        effective = first(decision.get("effectiveDate"))
        for row in decision.get("rows", []):
            hint = fold(row.get("levelHint"))
            if hint in {"commune", "cap xa"}:
                continue
            code = canonical_code(row)
            if not code:
                continue
            candidate = {
                **row,
                "decisionNo": decision.get("decisionNo",""),
                "decisionDate": decision_date,
                "effectiveDate": effective,
                "field": decision.get("field",""),
                "articleUrl": decision.get("articleUrl",""),
                "pdfUrl": decision.get("pdfUrl",""),
                "asOf": payload.get("asOf",""),
            }
            previous = latest.get(code)
            if not previous or first(candidate.get("decisionDate")) >= first(previous.get("decisionDate")):
                latest[code] = candidate
    return list(latest.values())

def build_city_rows() -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    master = load(MASTER, {"thuTuc": []})
    excluded = load(EXCLUDED, {"rows": []})
    notes = delta_notes(load(DELTA, {}))
    rows: list[dict[str, str]] = []
    review: list[dict[str, Any]] = [{
        "scope":"city",
        "reason":"partial_city_baseline",
        "detail":"Current repository does not yet prove a complete city-level baseline; live publication must stay gated.",
    }]

    for raw in master.get("thuTuc", []):
        if scope_for_master(raw) == "city":
            code = canonical_code(raw)
            rows.append(base_projection(raw, status="Còn hiệu lực", note=notes.get(code, "Không thay đổi")))
    for raw in excluded.get("rows", []):
        if scope_for_master(raw) == "city":
            code = canonical_code(raw)
            status = status_for_excluded(raw)
            status_note = {
                "Bãi bỏ": "Bãi bỏ",
                "Hết hiệu lực": "Hết hiệu lực",
                "Chưa hiệu lực": "Chưa hiệu lực",
                "Cần xác minh": "Cần xác minh",
            }.get(status, "Điều chỉnh")
            rows.append(base_projection(raw, status=status, note=status_note))

    for raw in city_update_candidates():
        code = canonical_code(raw)
        section = fold(raw.get("sectionStatus"))
        if section == "repealed":
            status, note = "Bãi bỏ", "Bãi bỏ"
        elif section == "new":
            status, note = "Còn hiệu lực", "Thêm mới"
        elif section == "modified":
            status, note = "Còn hiệu lực", "Điều chỉnh"
        else:
            status, note = "Cần xác minh", "Điều chỉnh"
            review.append({"scope":"city","code":code,"reason":"ambiguous_city_section_status","sectionStatus":raw.get("sectionStatus","")})
        if raw.get("effectiveDate") and first(raw.get("effectiveDate")) > first(load(CITY_UPDATES, {}).get("asOf","")):
            status = "Chưa hiệu lực"
        level_hint = first(raw.get("levelHint"))
        level = "Cấp thành phố" if fold(level_hint) == "province" else ("Dùng chung nhiều cấp" if "shared" in fold(level_hint) else first(level_hint, "Cấp thành phố"))
        rows.append(base_projection(
            raw, status=status, note=note, level=level,
            decision=first(raw.get("decisionNo")), effective_date=first(raw.get("effectiveDate")),
            snapshot_date=first(raw.get("asOf")), source_url=first(raw.get("articleUrl")),
            attachment_url=first(raw.get("pdfUrl")),
        ))
    return dedupe_rows(rows, review, "city"), review

def dedupe_rows(rows: list[dict[str, str]], review: list[dict[str, Any]], scope: str) -> list[dict[str, str]]:
    by_code: dict[str, dict[str, str]] = {}
    rank = {"Còn hiệu lực":4,"Chưa hiệu lực":3,"Bãi bỏ":2,"Hết hiệu lực":1,"Cần xác minh":0}
    for row in rows:
        code = row.get("Mã TTHC","").strip()
        if not code:
            review.append({"scope":scope,"reason":"missing_code","name":row.get("Thủ tục hành chính","")})
            continue
        previous = by_code.get(code)
        if previous and previous != row:
            prev_date = previous.get("Ngày kiểm tra/cập nhật","")
            new_date = row.get("Ngày kiểm tra/cập nhật","")
            if new_date > prev_date or (new_date == prev_date and rank.get(row.get("Tình trạng hiệu lực",""),0) > rank.get(previous.get("Tình trạng hiệu lực",""),0)):
                by_code[code] = row
            elif new_date == prev_date and rank.get(row.get("Tình trạng hiệu lực",""),0) == rank.get(previous.get("Tình trạng hiệu lực",""),0):
                material = ("Thủ tục hành chính","Lĩnh vực","Quyết định ban hành/công bố","Tình trạng hiệu lực")
                if any(row.get(k,"") != previous.get(k,"") for k in material):
                    review.append({"scope":scope,"code":code,"reason":"same_date_material_conflict"})
        else:
            by_code[code] = row
    return sorted(by_code.values(), key=lambda r:(fold(r.get("Lĩnh vực")), fold(r.get("Thủ tục hành chính")), r.get("Mã TTHC","")))

def manifest_review_queue() -> list[dict[str, Any]]:
    payload = load(MANIFEST, {"decisions":[]})
    queue=[]
    for d in payload.get("decisions",[]):
        classification=first(d.get("classification"))
        status=first(d.get("ingestStatus"))
        if classification == "needs_review" or status.startswith("needs_"):
            queue.append({
                "scope":"source",
                "decisionNo":d.get("decisionNo",""),
                "reason":status or classification,
                "articleUrl":d.get("articleUrl",""),
            })
    return queue

def merge_manual_fields(projected: dict[str, str], existing: dict[str, str] | None) -> dict[str, str]:
    if not existing:
        return projected
    merged = dict(projected)
    for field in MANUAL_FIELDS:
        if field in {"Mã TTHC","Cần đối soát?","STT"}:
            continue
        current = first(existing.get(field))
        if current and not first(merged.get(field)):
            merged[field] = current
        elif field in {"Bộ/ngành quản lý","Quy trình nội bộ","Thời gian sau rút ngắn","Lệ phí","Quy trình ISO","Mã lĩnh vực/nhóm báo cáo","Đã công khai tại Trung tâm?","Người cập nhật","Ghi chú chi tiết"}:
            merged[field] = current
    return merged

def plan() -> dict[str, Any]:
    commune, q1 = build_commune_rows()
    city, q2 = build_city_rows()
    queue = manifest_review_queue() + q1 + q2
    return {
        "format":"google-sheets-tthc-sync-plan",
        "version":1,
        "commune":{"rows":commune,"count":len(commune)},
        "city":{"rows":city,"count":len(city),"coverage":"PARTIAL_BASELINE"},
        "reviewQueue":queue,
        "reviewCount":len(queue),
    }

if __name__ == "__main__":
    print(json.dumps(plan(), ensure_ascii=False, indent=2))
