#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

try:
    from scripts.canonical_v4 import (
        LIFECYCLE_STATUSES,
        SOURCE_COMMIT_KIND,
        SOURCE_ROLES,
        compute_source_commit,
        evidence_id,
    )
except ModuleNotFoundError:
    from canonical_v4 import (
        LIFECYCLE_STATUSES,
        SOURCE_COMMIT_KIND,
        SOURCE_ROLES,
        compute_source_commit,
        evidence_id,
    )

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data/thu-tuc.json"

HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
VERSION = re.compile(r"^\d{4}\.\d{2}\.\d{2}$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
EVIDENCE_ID = re.compile(r"^ev_[0-9a-f]{24}$")
CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
CP437_MARKERS = ("├", "┬", "┌", "└", "┼", "╬", "╟", "╚", "╠", "╩", "╦", "╔", "║", "╒", "╘", "╞", "╪", "╧", "╤")
OCR_SPLIT_MARKERS = ("tr ạm", "Ch ứng", "nh ập", "th ấp", "đi ểm", "t ờ", "th ẩm", "quy ền")
VERIFIED_LINK_STATUSES = {"resolution_level_scope_verified", "vinhbao_scope_parameters_verified", "verified_official_guidance"}

LEGAL_FIELDS = {
    "ma",
    "ten",
    "linhVuc",
    "cap",
    "quyetDinh",
    "lifecycle.status",
    "lifecycle.effectiveFrom",
    "lifecycle.effectiveTo",
}
EXECUTION_FIELDS = {
    "formalityId",
    "nopHoSoUrl",
    "nopHoSoScope",
    "submissionLinkStatus",
    "huongDan.submissionUrl",
    "huongDan.dvctt",
}
GUIDANCE_FIELDS = {
    "huongDan.quyTrinh",
    "huongDan.thanhPhanHoSo",
    "huongDan.bieuMau",
    "huongDan.lePhi",
    "huongDan.thoiHan",
    "huongDan.coQuanThucHien",
    "huongDan.ketQua",
    "huongDan.canCuPhapLy",
}


def _official_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and (
        host == "dichvucong.gov.vn"
        or host.endswith(".dichvucong.gov.vn")
        or host.endswith(".gov.vn")
    )


def _validate_submission_url(value: str, formality_id: str, cap: str) -> list[str]:
    try:
        parsed = urlparse(value)
        query = parse_qs(parsed.query)
    except ValueError:
        return ["URL nộp hồ sơ không hợp lệ"]

    errors: list[str] = []
    if parsed.scheme != "https" or (parsed.hostname or "").lower() != "dichvucong.gov.vn":
        errors.append("URL nộp hồ sơ phải là HTTPS thuộc dichvucong.gov.vn")

    province_code = (query.get("provinceCode") or [""])[0]
    if province_code != "31":
        errors.append(f"URL nộp hồ sơ sai provinceCode: cần 31, hiện {province_code or 'trống'}")

    is_province_route = str(cap or "").strip().lower().startswith("cấp tỉnh")
    if is_province_route:
        if (query.get("isProvince") or [""])[0] != "1":
            errors.append("TTHC cấp tỉnh phải dùng isProvince=1")
        forbidden = ("wardCode", "ward", "agency", "departmentId", "commune")
        present = [key for key in forbidden if (query.get(key) or [""])[0]]
        if present:
            errors.append("TTHC cấp tỉnh không được ép scope cấp xã: " + ", ".join(present))
    else:
        for key, expected in {"wardCode": "11824", "commune": "WARD"}.items():
            actual = (query.get(key) or [""])[0]
            if actual != expected:
                errors.append(f"URL nộp hồ sơ cấp xã sai {key}: cần {expected}, hiện {actual or 'trống'}")
        is_province = (query.get("isProvince") or [""])[0]
        if is_province and is_province != "0":
            errors.append("TTHC cấp xã phải dùng isProvince=0 khi tham số này được khai báo")

    if formality_id:
        actual = (query.get("formalityId") or [""])[0]
        if actual != formality_id:
            errors.append("URL nộp hồ sơ không khớp formalityId")
    return errors


def _validate_guidance(code: str, guide: Any) -> list[str]:
    if not isinstance(guide, dict):
        return [f"{code}: huongDan phải là object"]
    errors: list[str] = []
    if guide.get("verificationStatus") != "verified_official":
        errors.append(f"{code}: huongDan chưa có verificationStatus=verified_official")

    sources = guide.get("sources")
    if not isinstance(sources, list) or not sources:
        errors.append(f"{code}: huongDan thiếu sources")
    else:
        for index, source in enumerate(sources, start=1):
            if not isinstance(source, dict):
                errors.append(f"{code}: huongDan.sources[{index}] không phải object")
                continue
            if not _official_url(str(source.get("url") or "").strip()):
                errors.append(f"{code}: huongDan.sources[{index}] không phải nguồn chính thức HTTPS")
            role = str(source.get("sourceRole") or "").strip()
            if role not in SOURCE_ROLES:
                errors.append(f"{code}: huongDan.sources[{index}] sourceRole không hợp lệ")

    submission_url = str(guide.get("submissionUrl") or "").strip()
    if submission_url and not _official_url(submission_url):
        errors.append(f"{code}: huongDan.submissionUrl không phải nguồn DVCQG HTTPS hợp lệ")

    for field in ("quyTrinh", "thanhPhanHoSo", "bieuMau", "lePhi"):
        value = guide.get(field)
        if value is not None and not isinstance(value, list):
            errors.append(f"{code}: huongDan.{field} phải là mảng")
    for field in ("coQuanThucHien", "verifiedAt"):
        value = guide.get(field)
        if value is not None and not isinstance(value, str):
            errors.append(f"{code}: huongDan.{field} phải là chuỗi")
    time_value = guide.get("thoiHan")
    if time_value is not None and not isinstance(time_value, (str, list)):
        errors.append(f"{code}: huongDan.thoiHan phải là chuỗi hoặc mảng có cấu trúc")
    dvctt = guide.get("dvctt")
    if dvctt is not None and not isinstance(dvctt, dict):
        errors.append(f"{code}: huongDan.dvctt phải là object")
    result_value = guide.get("ketQua")
    if result_value is not None and not isinstance(result_value, (dict, list, str)):
        errors.append(f"{code}: huongDan.ketQua phải là object, mảng hoặc chuỗi")
    legal_basis = guide.get("canCuPhapLy")
    if legal_basis is not None:
        if not isinstance(legal_basis, list) or not legal_basis or any(
            not isinstance(item, str) or not item.strip() for item in legal_basis
        ):
            errors.append(f"{code}: huongDan.canCuPhapLy phải là mảng chuỗi không rỗng")
    return errors


def _validate_lifecycle(code: str, lifecycle: Any) -> list[str]:
    if not isinstance(lifecycle, dict):
        return [f"{code}: thiếu lifecycle object"]
    errors: list[str] = []
    status = str(lifecycle.get("status") or "")
    if status not in LIFECYCLE_STATUSES:
        errors.append(f"{code}: lifecycle.status không hợp lệ")
    as_of = str(lifecycle.get("asOf") or "")
    if not DATE.fullmatch(as_of):
        errors.append(f"{code}: lifecycle.asOf phải theo YYYY-MM-DD")
    for field in ("effectiveFrom", "effectiveTo"):
        value = lifecycle.get(field)
        if value not in (None, "") and not DATE.fullmatch(str(value)):
            errors.append(f"{code}: lifecycle.{field} phải là YYYY-MM-DD hoặc null")
    if status == "future_effective" and lifecycle.get("effectiveFrom") and as_of:
        if str(lifecycle["effectiveFrom"]) <= as_of:
            errors.append(f"{code}: future_effective phải có effectiveFrom sau asOf")
    if status == "repealed" and lifecycle.get("effectiveTo") and as_of:
        if str(lifecycle["effectiveTo"]) > as_of:
            errors.append(f"{code}: repealed không thể có effectiveTo sau asOf")
    return errors


def _validate_evidence(code: str, item: Any, index: int) -> list[str]:
    if not isinstance(item, dict):
        return [f"{code}: sourceEvidence[{index}] không phải object"]
    errors: list[str] = []
    role = str(item.get("sourceRole") or "")
    if role not in SOURCE_ROLES:
        errors.append(f"{code}: sourceEvidence[{index}].sourceRole không hợp lệ")
    ev_id = str(item.get("evidenceId") or "")
    if not EVIDENCE_ID.fullmatch(ev_id):
        errors.append(f"{code}: sourceEvidence[{index}].evidenceId không hợp lệ")
    elif ev_id != evidence_id(item):
        errors.append(f"{code}: sourceEvidence[{index}].evidenceId không khớp nội dung evidence")

    urls = [
        str(item.get("url") or "").strip(),
        str(item.get("articleUrl") or "").strip(),
        str(item.get("attachmentUrl") or "").strip(),
    ]
    urls = [value for value in urls if value]
    if not urls:
        errors.append(f"{code}: sourceEvidence[{index}] thiếu URL nguồn")
    for value in urls:
        if not _official_url(value):
            errors.append(f"{code}: sourceEvidence[{index}] URL không phải nguồn chính thức HTTPS: {value}")

    sha256 = str(item.get("attachmentSha256") or "").strip()
    if sha256 and not HEX64.fullmatch(sha256):
        errors.append(f"{code}: sourceEvidence[{index}].attachmentSha256 không hợp lệ")
    for field in ("publishedDate", "effectiveDate"):
        value = item.get(field)
        if value not in (None, "") and not DATE.fullmatch(str(value)):
            errors.append(f"{code}: sourceEvidence[{index}].{field} phải theo YYYY-MM-DD")
    return errors


def _evidence_date(item: dict[str, Any]) -> str:
    return str(item.get("effectiveDate") or item.get("publishedDate") or "")


def _validate_precedence(
    code: str,
    row: dict[str, Any],
    evidence_by_id: dict[str, dict[str, Any]],
    field_sources: dict[str, Any],
) -> list[str]:
    errors: list[str] = []

    required = {"ma", "ten", "linhVuc", "cap", "lifecycle.status"}
    if row.get("quyetDinh"):
        required.add("quyetDinh")
    if row.get("formalityId"):
        required.add("formalityId")
    if row.get("nopHoSoUrl"):
        required.update({"nopHoSoUrl", "nopHoSoScope", "submissionLinkStatus"})
    guide = row.get("huongDan")
    if isinstance(guide, dict):
        for field in ("quyTrinh", "thanhPhanHoSo", "bieuMau", "lePhi", "thoiHan", "coQuanThucHien", "ketQua", "canCuPhapLy", "dvctt", "submissionUrl"):
            if guide.get(field) not in (None, "", [], {}):
                required.add(f"huongDan.{field}")

    missing = sorted(field for field in required if not field_sources.get(field))
    for field in missing:
        errors.append(f"{code}: fieldSources thiếu provenance cho {field}")

    for field, refs in field_sources.items():
        if not isinstance(field, str) or not isinstance(refs, list) or not refs:
            errors.append(f"{code}: fieldSources.{field} phải là mảng evidenceId không rỗng")
            continue
        if len(refs) != len(set(refs)):
            errors.append(f"{code}: fieldSources.{field} chứa evidenceId trùng")
        roles: set[str] = set()
        for ref in refs:
            if ref not in evidence_by_id:
                errors.append(f"{code}: fieldSources.{field} tham chiếu evidenceId không tồn tại: {ref}")
                continue
            roles.add(str(evidence_by_id[ref].get("sourceRole") or ""))

        if field in LEGAL_FIELDS:
            if "local_legal_effect" not in roles:
                errors.append(f"{code}: {field} phải có nguồn local_legal_effect")
            if "central_content_reference" in roles:
                errors.append(f"{code}: central_content_reference không được xác lập {field}")
        if field in EXECUTION_FIELDS:
            if "local_execution" not in roles:
                errors.append(f"{code}: {field} phải có nguồn local_execution")
            if "central_content_reference" in roles:
                errors.append(f"{code}: central_content_reference không được xác lập {field}")
        if field in GUIDANCE_FIELDS and roles and not roles.issubset(
            {"central_content_reference", "local_legal_effect"}
        ):
            errors.append(f"{code}: {field} chỉ được lấy từ nguồn nội dung trung ương hoặc hiệu lực địa phương")
    return errors


def validate(payload: Any, root: Path | None = None) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["Tệp canonical phải là một JSON object."]
    if payload.get("format") != "bangniemyet-vinhbao-master-data":
        errors.append("format không đúng canonical contract")
    if payload.get("version") != 4:
        errors.append("contract version phải là 4")
    if not VERSION.fullmatch(str(payload.get("dataset_version", ""))):
        errors.append("dataset_version phải theo YYYY.MM.DD")
    if not HEX40.fullmatch(str(payload.get("source_commit", ""))):
        errors.append("source_commit phải là SHA-1 40 ký tự")
    if payload.get("source_commit_kind") != SOURCE_COMMIT_KIND:
        errors.append(f"source_commit_kind phải là {SOURCE_COMMIT_KIND}")
    if root is not None:
        try:
            expected_commit = compute_source_commit(root)
            if payload.get("source_commit") != expected_commit:
                errors.append("source_commit không khớp fingerprint deterministic của verified source bundle")
        except (OSError, ValueError) as exc:
            errors.append(f"không tính được source_commit deterministic: {exc}")

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

        if CONTROL.search(name):
            errors.append(f"{code or index}: tên chứa ký tự điều khiển")
        if any(marker in name for marker in CP437_MARKERS):
            errors.append(f"{code or index}: tên có dấu hiệu lỗi giải mã CP437")
        bad_split = next((marker for marker in OCR_SPLIT_MARKERS if marker in name), None)
        if bad_split:
            errors.append(f"{code or index}: tên có dấu hiệu tách chữ OCR bất thường: {bad_split}")
        if name and unicodedata.normalize("NFC", name) != name:
            errors.append(f"{code or index}: tên chưa chuẩn hóa Unicode NFC")

        errors.extend(_validate_lifecycle(code or str(index), row.get("lifecycle")))

        evidence = row.get("sourceEvidence")
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"{code or index}: sourceEvidence phải là mảng không rỗng")
            evidence = []
        evidence_by_id: dict[str, dict[str, Any]] = {}
        for source_index, item in enumerate(evidence, start=1):
            errors.extend(_validate_evidence(code or str(index), item, source_index))
            if isinstance(item, dict):
                ev_id = str(item.get("evidenceId") or "")
                if ev_id:
                    if ev_id in evidence_by_id:
                        errors.append(f"{code or index}: sourceEvidence trùng evidenceId {ev_id}")
                    evidence_by_id[ev_id] = item

        lifecycle = row.get("lifecycle") if isinstance(row.get("lifecycle"), dict) else {}
        if lifecycle.get("status") == "active":
            legal = [
                item for item in evidence
                if isinstance(item, dict) and item.get("sourceRole") == "local_legal_effect"
            ]
            if not legal:
                errors.append(f"{code or index}: active TTHC thiếu local_legal_effect evidence")
            latest_active = max(
                (_evidence_date(item) for item in legal if not item.get("repealContext")),
                default="",
            )
            latest_repeal = max(
                (_evidence_date(item) for item in legal if item.get("repealContext")),
                default="",
            )
            if latest_repeal and (not latest_active or latest_repeal >= latest_active):
                errors.append(f"{code or index}: lifecycle active mâu thuẫn bằng chứng bãi bỏ")

        field_sources = row.get("fieldSources")
        if not isinstance(field_sources, dict):
            errors.append(f"{code or index}: fieldSources phải là object")
            field_sources = {}
        errors.extend(
            _validate_precedence(code or str(index), row, evidence_by_id, field_sources)
        )

        submission_url = str(row.get("nopHoSoUrl") or "").strip()
        if submission_url:
            status = str(row.get("submissionLinkStatus") or "").strip()
            if status not in VERIFIED_LINK_STATUSES:
                errors.append(f"{code or index}: link nộp hồ sơ chưa có trạng thái xác minh")
            errors.extend(
                f"{code or index}: {message}"
                for message in _validate_submission_url(
                    submission_url,
                    str(row.get("formalityId") or "").strip(),
                    str(row.get("cap") or "").strip(),
                )
            )

        if "huongDan" in row:
            errors.extend(_validate_guidance(code or str(index), row["huongDan"]))

    return errors


def main() -> int:
    payload = json.loads(DATASET.read_text(encoding="utf-8"))
    errors = validate(payload, ROOT)
    if errors:
        raise SystemExit("\n".join(errors))
    print(
        json.dumps(
            {
                "contract_version": payload["version"],
                "dataset_version": payload["dataset_version"],
                "source_commit": payload["source_commit"],
                "source_commit_kind": payload["source_commit_kind"],
                "procedures": len(payload["thuTuc"]),
                "verified_submission_links": sum(
                    1 for row in payload["thuTuc"] if row.get("nopHoSoUrl")
                ),
                "official_guidance": sum(
                    1 for row in payload["thuTuc"] if row.get("huongDan")
                ),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
