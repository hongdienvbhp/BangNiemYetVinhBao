#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

try:
    from scripts.canonical_v4 import SOURCE_ROLES
except ModuleNotFoundError:
    from canonical_v4 import SOURCE_ROLES

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/tthc-guidance-enrichment.json"
CODE_RE = re.compile(r"^\d{1,2}\.\d{3,6}$")
ALLOWED_STATUS = {"verified_official"}
SUBSTANTIVE_FIELDS = {
    "quyTrinh",
    "thanhPhanHoSo",
    "bieuMau",
    "lePhi",
    "thoiHan",
    "coQuanThucHien",
    "ketQua",
    "dvctt",
    "submissionUrl",
}

ALLOWED_LEGACY_OVERRIDES = {"thoiHan"}


def is_official_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
        host = (parsed.hostname or "").lower()
    except ValueError:
        return False
    return (
        parsed.scheme == "https"
        and (
            host == "dichvucong.gov.vn"
            or host.endswith(".dichvucong.gov.vn")
            or host.endswith(".gov.vn")
        )
    )


def validate_vinhbao_submission_url(value: str, formality_id: str = "") -> list[str]:
    errors: list[str] = []
    try:
        parsed = urlparse(value)
        query = parse_qs(parsed.query)
    except ValueError:
        return ["URL nộp hồ sơ không hợp lệ"]

    if parsed.scheme != "https" or (parsed.hostname or "").lower() != "dichvucong.gov.vn":
        errors.append("URL nộp hồ sơ phải là HTTPS thuộc dichvucong.gov.vn")
    expected = {
        "provinceCode": "31",
        "wardCode": "11824",
        "commune": "WARD",
    }
    for key, wanted in expected.items():
        actual = (query.get(key) or [""])[0]
        if actual != wanted:
            errors.append(f"URL nộp hồ sơ sai {key}: cần {wanted}, hiện {actual or 'trống'}")
    if formality_id:
        actual = (query.get("formalityId") or [""])[0]
        if actual != formality_id:
            errors.append("URL nộp hồ sơ không khớp formalityId")
    return errors


def validate(payload: object) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["Tệp enrichment phải là JSON object"]
    if payload.get("format") != "bangniemyet-tthc-guidance-enrichment":
        errors.append("format enrichment không đúng")
    if payload.get("version") != 1:
        errors.append("version enrichment phải là 1")

    source_roles = payload.get("sourceRoles")
    if source_roles is not None:
        if not isinstance(source_roles, dict):
            errors.append("sourceRoles phải là object")
        else:
            missing = SOURCE_ROLES - set(source_roles)
            if missing:
                errors.append("sourceRoles thiếu: " + ", ".join(sorted(missing)))

    rows = payload.get("rows")
    if not isinstance(rows, list):
        return errors + ["rows phải là mảng"]

    seen: set[str] = set()
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            errors.append(f"rows[{index}] không phải object")
            continue

        code = str(row.get("ma") or "").strip()
        label = code or str(index)
        if not CODE_RE.fullmatch(code):
            errors.append(f"rows[{index}] mã TTHC không hợp lệ: {code or 'trống'}")
        if code in seen:
            errors.append(f"trùng mã enrichment: {code}")
        seen.add(code)

        status = str(row.get("verificationStatus") or "").strip()
        if status not in ALLOWED_STATUS:
            errors.append(f"{label}: verificationStatus phải là verified_official")

        sources = row.get("sources")
        source_by_id: dict[str, dict] = {}
        has_substantive = any(
            row.get(field) not in (None, "", [], {}) for field in SUBSTANTIVE_FIELDS
        )
        if has_substantive and (not isinstance(sources, list) or not sources):
            errors.append(f"{label}: dữ liệu hướng dẫn phải có sources")

        if isinstance(sources, list):
            for source_index, source in enumerate(sources, start=1):
                if not isinstance(source, dict):
                    errors.append(f"{label}: sources[{source_index}] không phải object")
                    continue
                source_id = str(source.get("id") or "").strip()
                role = str(source.get("sourceRole") or "").strip()
                url = str(source.get("url") or "").strip()
                if not source_id:
                    errors.append(f"{label}: sources[{source_index}] thiếu id")
                elif source_id in source_by_id:
                    errors.append(f"{label}: trùng source id {source_id}")
                else:
                    source_by_id[source_id] = source
                if role not in SOURCE_ROLES:
                    errors.append(
                        f"{label}: sources[{source_index}] sourceRole không hợp lệ: {role or 'trống'}"
                    )
                if not url or not is_official_url(url):
                    errors.append(
                        f"{label}: nguồn {source_index} không phải URL chính thức HTTPS"
                    )

        provenance = row.get("fieldProvenance")
        if has_substantive and not isinstance(provenance, dict):
            errors.append(f"{label}: dữ liệu hướng dẫn phải có fieldProvenance")
            provenance = {}
        elif provenance is None:
            provenance = {}

        if isinstance(provenance, dict):
            for field in SUBSTANTIVE_FIELDS:
                value = row.get(field)
                if value in (None, "", [], {}):
                    continue
                refs = provenance.get(field)
                if not isinstance(refs, list) or not refs:
                    errors.append(
                        f"{label}: fieldProvenance.{field} phải có ít nhất 1 source id"
                    )
                    continue
                for ref in refs:
                    if not isinstance(ref, str) or ref not in source_by_id:
                        errors.append(
                            f"{label}: fieldProvenance.{field} tham chiếu source id không tồn tại: {ref}"
                        )
                if field in {"submissionUrl", "dvctt"}:
                    roles = {
                        str(source_by_id[ref].get("sourceRole") or "")
                        for ref in refs
                        if isinstance(ref, str) and ref in source_by_id
                    }
                    if roles - {"local_execution"}:
                        errors.append(
                            f"{label}: {field} chỉ được provenance từ local_execution"
                        )

        legacy_overrides = row.get("legacyOverrides")
        if legacy_overrides is not None:
            if not isinstance(legacy_overrides, dict):
                errors.append(f"{label}: legacyOverrides phải là object")
            else:
                source_by_id = {
                    str(item.get("id") or "").strip(): item
                    for item in (sources if isinstance(sources, list) else [])
                    if isinstance(item, dict) and str(item.get("id") or "").strip()
                }
                for field, override_value in legacy_overrides.items():
                    if field not in ALLOWED_LEGACY_OVERRIDES:
                        errors.append(f"{label}: legacyOverrides.{field} không được hỗ trợ")
                        continue
                    if not isinstance(override_value, str) or not override_value.strip():
                        errors.append(f"{label}: legacyOverrides.{field} phải là chuỗi không rỗng")
                    refs = provenance.get(field) if isinstance(provenance, dict) else None
                    if not isinstance(refs, list) or not refs:
                        errors.append(f"{label}: legacyOverrides.{field} cần fieldProvenance.{field}")
                        continue
                    missing_refs = [ref for ref in refs if str(ref).strip() not in source_by_id]
                    if missing_refs:
                        errors.append(f"{label}: legacyOverrides.{field} tham chiếu nguồn không tồn tại")
                        continue
                    if field == "thoiHan":
                        roles = {
                            str(source_by_id[str(ref).strip()].get("sourceRole") or "").strip()
                            for ref in refs
                        }
                        if "local_legal_effect" not in roles:
                            errors.append(f"{label}: legacyOverrides.thoiHan phải có nguồn pháp lý địa phương")
        submission_url = str(row.get("submissionUrl") or "").strip()
        if submission_url:
            for message in validate_vinhbao_submission_url(
                submission_url, str(row.get("formalityId") or "").strip()
            ):
                errors.append(f"{label}: {message}")
    return errors


def validate_legacy_field_overrides(payload: object) -> list[str]:
    """Validate independent legal mirrors; these rows are not priority guidance."""
    errors: list[str] = []
    if not isinstance(payload, dict): return ["legacy field overrides: payload ph?i l? object"]
    if payload.get("format") != "official-legacy-field-overrides-v1": errors.append("legacy field overrides: format kh?ng h?p l?")
    if payload.get("version") != 1: errors.append("legacy field overrides: version kh?ng h?p l?")
    rows = payload.get("rows")
    if not isinstance(rows, list): return errors + ["legacy field overrides: rows ph?i l? danh s?ch"]
    seen: set[str] = set()
    for i, row in enumerate(rows):
        label = f"legacy field overrides[{i}]"
        if not isinstance(row, dict): errors.append(f"{label}: ph?i l? object"); continue
        code = str(row.get("ma") or "").strip()
        if not (len(code) == 8 and code[0].isdigit() and code[1] == "." and code[2:].isdigit()): errors.append(f"{label}: m? TTHC kh?ng h?p l?")
        if code in seen: errors.append(f"{label}: m? TTHC tr?ng l?p {code}")
        seen.add(code)
        if row.get("verificationStatus") != "verified_official": errors.append(f"{label}: verificationStatus ph?i l? verified_official")
        legacy = row.get("legacyOverrides")
        if not isinstance(legacy, dict) or not legacy: errors.append(f"{label}: legacyOverrides ph?i l? object kh?ng r?ng"); continue
        for field, value in legacy.items():
            if field != "thoiHan": errors.append(f"{label}: legacyOverrides.{field} kh?ng ???c h? tr?")
            elif not isinstance(value, str) or not value.strip(): errors.append(f"{label}: legacyOverrides.thoiHan ph?i l? chu?i kh?ng r?ng")
        sources = row.get("sources"); sources = sources if isinstance(sources, list) else []
        source_by_id = {str(x.get("id") or "").strip(): x for x in sources if isinstance(x, dict) and str(x.get("id") or "").strip()}
        provenance = row.get("fieldProvenance"); provenance = provenance if isinstance(provenance, dict) else {}
        for field in legacy:
            refs = provenance.get(field)
            if not isinstance(refs, list) or not refs: errors.append(f"{label}: legacyOverrides.{field} c?n fieldProvenance.{field}"); continue
            if any(str(ref).strip() not in source_by_id for ref in refs): errors.append(f"{label}: {field} tham chi?u source id kh?ng t?n t?i"); continue
            roles = {str(source_by_id[str(ref).strip()].get("sourceRole") or "").strip() for ref in refs}
            if field == "thoiHan" and "local_legal_effect" not in roles: errors.append(f"{label}: thoiHan ph?i c? ngu?n hi?u l?c ph?p l? ??a ph??ng")
        if not str(row.get("formalityId") or "").strip(): errors.append(f"{label}: formalityId kh?ng ???c ?? tr?ng")
        for source in sources:
            if not isinstance(source, dict): continue
            url = str(source.get("url") or "").strip()
            if not is_official_url(url): errors.append(f"{label}: ngu?n ph?i l? URL ch?nh th?c")
            if not str(source.get("contentHash") or "").strip(): errors.append(f"{label}: ngu?n thi?u contentHash")
    return errors


def main() -> int:
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    errors = validate(payload)
    sidecar_path = ROOT / "data/source-audit/official-legacy-field-overrides.json"
    sidecar = {"rows": []}
    if sidecar_path.exists():
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        errors.extend(validate_legacy_field_overrides(sidecar))
    if errors:
        raise SystemExit("\n".join(errors))
    print(json.dumps({"rows": len(payload["rows"]), "legacyOverrideRows": len(sidecar.get("rows", [])), "status": "PASS"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
