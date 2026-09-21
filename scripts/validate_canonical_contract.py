#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data/thu-tuc.json"

HEX40 = re.compile(r"^[0-9a-f]{40}$")
VERSION = re.compile(r"^\d{4}\.\d{2}\.\d{2}$")
CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
CP437_MARKERS = ("├", "┬", "┌", "└", "┼", "╬", "╟", "╚", "╠", "╩", "╦", "╔", "║", "╒", "╘", "╞", "╪", "╧", "╤")
OCR_SPLIT_MARKERS = ("tr ạm", "Ch ứng", "nh ập", "th ấp", "đi ểm", "t ờ", "th ẩm", "quy ền")
VERIFIED_LINK_STATUSES = {"vinhbao_scope_parameters_verified", "verified_official_guidance"}


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


def _validate_submission_url(value: str, formality_id: str) -> list[str]:
    try:
        parsed = urlparse(value)
        query = parse_qs(parsed.query)
    except ValueError:
        return ["URL nộp hồ sơ không hợp lệ"]

    errors: list[str] = []
    if parsed.scheme != "https" or (parsed.hostname or "").lower() != "dichvucong.gov.vn":
        errors.append("URL nộp hồ sơ phải là HTTPS thuộc dichvucong.gov.vn")
    for key, expected in {
        "provinceCode": "31",
        "wardCode": "11824",
        "commune": "WARD",
    }.items():
        actual = (query.get(key) or [""])[0]
        if actual != expected:
            errors.append(f"URL nộp hồ sơ sai {key}: cần {expected}, hiện {actual or 'trống'}")
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
            if not isinstance(source, dict) or not _official_url(str(source.get("url") or "").strip()):
                errors.append(f"{code}: huongDan.sources[{index}] không phải nguồn chính thức HTTPS")

    submission_url = str(guide.get("submissionUrl") or "").strip()
    if submission_url:
        errors.extend(
            f"{code}: {message}"
            for message in _validate_submission_url(
                submission_url, str(guide.get("formalityId") or "").strip()
            )
        )

    list_fields = ("quyTrinh", "thanhPhanHoSo", "bieuMau", "lePhi")
    for field in list_fields:
        value = guide.get(field)
        if value is not None and not isinstance(value, list):
            errors.append(f"{code}: huongDan.{field} phải là mảng")
    for field in ("thoiHan", "coQuanThucHien", "verifiedAt"):
        value = guide.get(field)
        if value is not None and not isinstance(value, str):
            errors.append(f"{code}: huongDan.{field} phải là chuỗi")
    return errors


def validate(payload: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["Tệp canonical phải là một JSON object."]
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

        if CONTROL.search(name):
            errors.append(f"{code or index}: tên chứa ký tự điều khiển")
        if any(marker in name for marker in CP437_MARKERS):
            errors.append(f"{code or index}: tên có dấu hiệu lỗi giải mã CP437")
        bad_split = next((marker for marker in OCR_SPLIT_MARKERS if marker in name), None)
        if bad_split:
            errors.append(f"{code or index}: tên có dấu hiệu tách chữ OCR bất thường: {bad_split}")
        if name and unicodedata.normalize("NFC", name) != name:
            errors.append(f"{code or index}: tên chưa chuẩn hóa Unicode NFC")

        submission_url = str(row.get("nopHoSoUrl") or "").strip()
        if submission_url:
            status = str(row.get("submissionLinkStatus") or "").strip()
            if status not in VERIFIED_LINK_STATUSES:
                errors.append(f"{code or index}: link nộp hồ sơ chưa có trạng thái xác minh")
            errors.extend(
                f"{code or index}: {message}"
                for message in _validate_submission_url(
                    submission_url, str(row.get("formalityId") or "").strip()
                )
            )

        if "huongDan" in row:
            errors.extend(_validate_guidance(code or str(index), row["huongDan"]))

    return errors


def main() -> int:
    payload = json.loads(DATASET.read_text(encoding="utf-8"))
    errors = validate(payload)
    if errors:
        raise SystemExit("\n".join(errors))
    print(
        json.dumps(
            {
                "dataset_version": payload["dataset_version"],
                "source_commit": payload["source_commit"],
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
