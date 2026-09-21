#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ROOT / "data/source-audit/priority50-guidance-candidates.json"
EXCEPTIONS = ROOT / "data/source-audit/priority50-official-guidance-exceptions.json"
AGENCY_OVERRIDES = ROOT / "data/source-audit/priority50-local-agency-overrides.json"
LEGAL = ROOT / "data/priority-51-legal-verification.json"
GUIDANCE = ROOT / "data/tthc-guidance-enrichment.json"

TARGET = 50
FIELDS = ("coQuanThucHien", "thanhPhanHoSo", "thoiHan", "lePhi", "dvctt", "ketQua")

CHANNELS = {
    "DIRECT": "Trực tiếp",
    "ONLINE": "Trực tuyến",
    "POSTAL": "Dịch vụ bưu chính",
}
UNITS = {
    "WORKING_DAY": "Ngày làm việc",
    "DAY": "Ngày",
    "HOUR": "Giờ",
    "OTHER": "Khác",
}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def filled(value: object) -> bool:
    return value not in (None, "", [], {})


def parse_dossier(text: object) -> list[dict]:
    raw = str(text or "").strip()
    if not raw:
        return []
    lines = [re.sub(r"\s+", " ", line).strip() for line in raw.splitlines() if line.strip()]
    items: list[str] = []
    current = ""
    for line in lines:
        if line.startswith("- "):
            if current:
                items.append(current.strip())
            current = line[2:].strip()
        else:
            if current:
                current += " " + line
            else:
                current = line
    if current:
        items.append(current.strip())
    if not items:
        items = [raw]
    return [{"ten": item} for item in items if item]


def parse_time(text: object) -> list[dict]:
    raw = str(text or "").strip()
    if not raw:
        return []
    result: list[dict] = []
    for line in [x.strip() for x in raw.splitlines() if x.strip()]:
        if "—" in line:
            channel_raw, value_raw = [part.strip() for part in line.split("—", 1)]
        elif "-" in line:
            channel_raw, value_raw = [part.strip() for part in line.split("-", 1)]
        else:
            channel_raw, value_raw = "", line
        channel = CHANNELS.get(channel_raw.upper(), channel_raw or "Không xác định")
        match = re.fullmatch(r"(\d+(?:[.,]\d+)?)\s+([A-Z_]+)", value_raw.upper())
        if match:
            qty, unit = match.groups()
            value = f"{qty} {UNITS.get(unit, unit)}"
        else:
            value = value_raw
        result.append({"hinhThuc": channel, "giaTri": value})
    return result


def parse_fee(text: object) -> list[dict]:
    raw = str(text or "").strip()
    if not raw:
        return [{
            "trangThai": "not_published",
            "mucThu": None,
            "ghiChu": "Nguồn DVCQG chính thức không công bố mức thu.",
        }]
    return [{"mucThu": re.sub(r"\s+", " ", line).strip()} for line in raw.splitlines() if line.strip()]


def legal_source_map() -> dict[str, dict]:
    payload = load(LEGAL)
    mapping: dict[str, dict] = {}
    for row in payload.get("rows") or []:
        if not isinstance(row, dict):
            continue
        code = str(row.get("code") or "").strip()
        sources = row.get("sources") or []
        if not code or not isinstance(sources, list):
            continue
        source = next((x for x in sources if isinstance(x, dict) and x.get("url")), None)
        if source:
            mapping[code] = {
                "id": "local_legal_agency",
                "url": str(source["url"]).strip(),
                "sourceRole": "local_legal_effect",
                "classification": "official_local_agency_scope",
                "verifiedAt": str(row.get("verificationCheckedAt") or ""),
            }
    for row in load(AGENCY_OVERRIDES).get("rows") or []:
        if not isinstance(row, dict):
            continue
        code = str(row.get("ma") or "").strip()
        if not code:
            continue
        mapping[code] = {
            "id": "local_legal_agency",
            "url": str(row.get("sourceUrl") or "").strip(),
            "sourceRole": "local_legal_effect",
            "classification": "official_local_agency_override",
            "verifiedAt": str(load(AGENCY_OVERRIDES).get("verifiedAt") or ""),
            "note": str(row.get("note") or "").strip(),
        }
    return mapping


def exception_map() -> dict[str, dict]:
    payload = load(EXCEPTIONS)
    return {
        str(row.get("ma") or "").strip(): row
        for row in payload.get("rows") or []
        if isinstance(row, dict) and str(row.get("ma") or "").strip()
    }


def current_execution_rows() -> dict[str, dict]:
    payload = load(GUIDANCE)
    return {
        str(row.get("ma") or "").strip(): deepcopy(row)
        for row in payload.get("rows") or []
        if isinstance(row, dict) and str(row.get("ma") or "").strip()
    }


def add_source(sources: list[dict], source: dict) -> None:
    sid = str(source.get("id") or "").strip()
    if not sid:
        raise ValueError("source thiếu id")
    if all(str(item.get("id") or "") != sid for item in sources):
        sources.append(source)


def build_candidate_row(candidate: dict, execution: dict, legal_sources: dict[str, dict]) -> dict:
    code = str(candidate["ma"]).strip()
    content_source = {
        "id": "official_dvcqg_content",
        "url": str(candidate.get("sourceUrl") or "").strip(),
        "sourceRole": "central_content_reference",
        "classification": "verified_dvcqg_content_snapshot",
        "verifiedAt": str(candidate.get("scrapedAt") or ""),
        "contentHash": str(candidate.get("contentHash") or ""),
    }
    if not content_source["url"]:
        raise ValueError(f"{code}: candidate thiếu sourceUrl")

    sources: list[dict] = [content_source]
    agency = str(candidate.get("coQuanThucHien") or "").strip()
    agency_ref = "official_dvcqg_content"
    if not agency:
        local = legal_sources.get(code)
        if not local:
            raise ValueError(f"{code}: thiếu local legal source cho agency override")
        add_source(sources, deepcopy(local))
        agency = "Ủy ban nhân dân cấp xã"
        agency_ref = "local_legal_agency"

    for source in execution.get("sources") or []:
        if isinstance(source, dict) and source.get("sourceRole") == "local_execution":
            add_source(sources, deepcopy(source))

    row = {
        "ma": code,
        "verificationStatus": "verified_official",
        "verifiedAt": datetime.now(timezone.utc).date().isoformat(),
        "coQuanThucHien": agency,
        "thanhPhanHoSo": parse_dossier(candidate.get("thanhPhanHoSo")),
        "thoiHan": parse_time(candidate.get("thoiHan")),
        "lePhi": parse_fee(candidate.get("lePhi")),
        "ketQua": str(candidate.get("ketQua") or "").strip(),
        "dvctt": deepcopy(execution.get("dvctt")),
        "submissionUrl": str(execution.get("submissionUrl") or "").strip(),
        "sources": sources,
        "fieldProvenance": {
            "coQuanThucHien": [agency_ref],
            "thanhPhanHoSo": ["official_dvcqg_content"],
            "thoiHan": ["official_dvcqg_content"],
            "lePhi": ["official_dvcqg_content"],
            "ketQua": ["official_dvcqg_content"],
            "dvctt": ["dvcqg_vinhbao"],
            "submissionUrl": ["dvcqg_vinhbao"],
        },
        "verificationNotes": {
            "candidateNameExact": bool(candidate.get("nameExact")),
            "candidateFormalityIdExact": bool(candidate.get("formalityIdExact")),
            "candidateScrapedAt": str(candidate.get("scrapedAt") or ""),
            "candidateOnlySourceWasNotPublishedDirectly": True,
        },
    }
    if execution.get("formalityId"):
        row["formalityId"] = execution["formalityId"]
    return row


def build_exception_row(exc: dict, execution: dict) -> dict:
    code = str(exc["ma"]).strip()
    content_source = {
        "id": "official_dvcqg_content",
        "url": str(exc.get("officialSourceUrl") or "").strip(),
        "sourceRole": "central_content_reference",
        "classification": "current_official_dvcqg_exception",
        "verifiedAt": str(load(EXCEPTIONS).get("verifiedAt") or ""),
    }
    local_source = {
        "id": "local_legal_agency",
        "url": str(exc.get("localLegalSourceUrl") or "").strip(),
        "sourceRole": "local_legal_effect",
        "classification": "official_local_agency_scope",
        "verifiedAt": str(load(EXCEPTIONS).get("verifiedAt") or ""),
    }
    sources = [content_source, local_source]
    for source in execution.get("sources") or []:
        if isinstance(source, dict) and source.get("sourceRole") == "local_execution":
            add_source(sources, deepcopy(source))

    row = {
        "ma": code,
        "verificationStatus": "verified_official",
        "verifiedAt": str(load(EXCEPTIONS).get("verifiedAt") or ""),
        "coQuanThucHien": str(exc.get("coQuanThucHien") or "").strip(),
        "thanhPhanHoSo": deepcopy(exc.get("thanhPhanHoSo") or []),
        "thoiHan": deepcopy(exc.get("thoiHan") or []),
        "lePhi": deepcopy(exc.get("lePhi") or []),
        "ketQua": str(exc.get("ketQua") or "").strip(),
        "dvctt": deepcopy(execution.get("dvctt")),
        "submissionUrl": str(execution.get("submissionUrl") or "").strip(),
        "sources": sources,
        "fieldProvenance": {
            "coQuanThucHien": ["local_legal_agency"],
            "thanhPhanHoSo": ["official_dvcqg_content"],
            "thoiHan": ["official_dvcqg_content"],
            "lePhi": ["official_dvcqg_content"],
            "ketQua": ["official_dvcqg_content"],
            "dvctt": ["dvcqg_vinhbao"],
            "submissionUrl": ["dvcqg_vinhbao"],
        },
        "verificationNotes": {"officialException": True},
    }
    if execution.get("formalityId"):
        row["formalityId"] = execution["formalityId"]
    return row


def main() -> int:
    candidates_payload = load(CANDIDATES)
    candidates = {
        str(row.get("ma") or "").strip(): row
        for row in candidates_payload.get("rows") or []
        if isinstance(row, dict) and str(row.get("ma") or "").strip()
    }
    exceptions = exception_map()
    execution = current_execution_rows()
    legal_sources = legal_source_map()

    target_codes = set(execution)
    if len(target_codes) != TARGET:
        raise ValueError(f"Expected {TARGET} current guidance targets, found {len(target_codes)}")
    if set(candidates) | set(exceptions) != target_codes:
        raise ValueError(
            "candidate + exception set phải đúng 50 mã; "
            f"missing={sorted(target_codes - (set(candidates)|set(exceptions)))}, "
            f"extra={sorted((set(candidates)|set(exceptions)) - target_codes)}"
        )

    rows: list[dict] = []
    for code in sorted(target_codes):
        exec_row = execution[code]
        if code in exceptions:
            row = build_exception_row(exceptions[code], exec_row)
        else:
            row = build_candidate_row(candidates[code], exec_row, legal_sources)
        for field in FIELDS:
            if not filled(row.get(field)):
                raise ValueError(f"{code}: materialize thiếu {field}")
        rows.append(row)

    template = load(GUIDANCE)
    result = {
        key: deepcopy(value)
        for key, value in template.items()
        if key not in {"rows", "coverage", "generatedFrom", "generatedAt"}
    }
    result["rows"] = rows
    result["coverage"] = {
        "target": TARGET,
        "reviewed": len(rows),
        "fields": {field: sum(filled(row.get(field)) for row in rows) for field in FIELDS},
        "unresolved": {
            field: [row["ma"] for row in rows if not filled(row.get(field))]
            for field in FIELDS
        },
    }
    result["generatedFrom"] = [
        "data/source-audit/priority50-guidance-candidates.json",
        "data/source-audit/priority50-official-guidance-exceptions.json",
        "data/priority-51-legal-verification.json",
        "data/source-audit/priority50-local-agency-overrides.json",
    ]
    result["generatedAt"] = datetime.now(timezone.utc).isoformat()
    GUIDANCE.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["coverage"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
