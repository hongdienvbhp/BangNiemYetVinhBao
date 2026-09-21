#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

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
}


def is_official_url(value: str) -> bool:
    try:
        host = (urlparse(value).hostname or "").lower()
    except ValueError:
        return False
    return (
        host == "dichvucong.gov.vn"
        or host.endswith(".dichvucong.gov.vn")
        or host.endswith(".gov.vn")
    )


def validate_vinhbao_submission_url(value: str, formality_id: str = "") -> list[str]:
    errors: list[str] = []
    try:
        parsed = urlparse(value)
        query = parse_qs(parsed.query)
    except ValueError:
        return ["URL nộp hồ sơ không hợp lệ"]

    if (parsed.hostname or "").lower() != "dichvucong.gov.vn":
        errors.append("URL nộp hồ sơ phải thuộc dichvucong.gov.vn")
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
    rows = payload.get("rows")
    if not isinstance(rows, list):
        return errors + ["rows phải là mảng"]

    seen: set[str] = set()
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            errors.append(f"rows[{index}] không phải object")
            continue
        code = str(row.get("ma") or "").strip()
        if not CODE_RE.fullmatch(code):
            errors.append(f"rows[{index}] mã TTHC không hợp lệ: {code or 'trống'}")
        if code in seen:
            errors.append(f"trùng mã enrichment: {code}")
        seen.add(code)

        status = str(row.get("verificationStatus") or "").strip()
        if status not in ALLOWED_STATUS:
            errors.append(f"{code or index}: verificationStatus phải là verified_official")

        sources = row.get("sources")
        has_substantive = any(row.get(field) not in (None, "", [], {}) for field in SUBSTANTIVE_FIELDS)
        if has_substantive and (not isinstance(sources, list) or not sources):
            errors.append(f"{code or index}: dữ liệu hướng dẫn phải có sources")
        if isinstance(sources, list):
            for source_index, source in enumerate(sources, start=1):
                if not isinstance(source, dict):
                    errors.append(f"{code or index}: sources[{source_index}] không phải object")
                    continue
                url = str(source.get("url") or "").strip()
                if not url or not is_official_url(url):
                    errors.append(f"{code or index}: nguồn {source_index} không phải URL chính thức")

        submission_url = str(row.get("submissionUrl") or "").strip()
        if submission_url:
            for message in validate_vinhbao_submission_url(
                submission_url, str(row.get("formalityId") or "").strip()
            ):
                errors.append(f"{code or index}: {message}")
    return errors


def main() -> int:
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    errors = validate(payload)
    if errors:
        raise SystemExit("\n".join(errors))
    print(json.dumps({"rows": len(payload["rows"]), "status": "PASS"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
