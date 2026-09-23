#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the verified 03/07/2025 Hai Phong city-reception TTHC baseline.

The official PDF contains multiple logical table streams on some physical pages.
We preserve content-stream order and split streams whenever the vertical position
resets sharply, then extract each stream independently. Identity is Mã TTHC.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
from pathlib import Path
from urllib.request import Request, urlopen

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
ARTICLE_URL = "https://haiphong.gov.vn/thu-tuc-hanh-chinh-76761/danh-muc-thu-tuc-hanh-chinh-tiep-nhan-tai-trung-tam-phuc-vu-hanh-chinh-cong-thanh-pho-hai-phong--760833"
PDF_URL = "https://cdn.haiphong.gov.vn/gov-hpg/1/tintuc/2025/7/danh-muc-thu-tuc-hanh-chinh-thuc-hien-tiep-nhan-tai-trung-tam-phuc-vu-hanh-chinh-cong-thanh-pho-hai-phong638871741697189500.pdf"
PUBLISHED_DATE = "2025-07-03"
EXPECTED_SHA256 = "22c2a8ab6abc6aa0df4694da6eebafe51f5a75bf76bae97f22c19af5fa082425"
EXPECTED_PAGES = 114
EXPECTED_UNIQUE_CODES = 1928
CODE_RE = re.compile(r"^\d{1,2}\.\d{3,6}$")

# Three rows sit on stream boundaries where the source PDF exposes the code but
# not a stable name fragment. Names below were independently cross-checked from
# official Hai Phong/DVCQG publications. They do not alter legal status.
NAME_OVERRIDES = {
    "1.013980": {
        "name": "Đăng ký biến động đối với trường hợp thay đổi quyền sử dụng đất, quyền sở hữu tài sản gắn liền với đất theo thỏa thuận của các thành viên hộ gia đình hoặc của vợ và chồng",
        "field": "ĐẤT ĐAI",
        "evidenceUrl": "https://namsach.haiphong.gov.vn/cong-khai-danh-muc-thu-tuc-hanh-chinh",
    },
    "1.013951": {
        "name": "Cấp giấy phép sử dụng thiết bị bức xạ chụp cắt lớp vi tính tích hợp với PET, (PET/CT), tích hợp với SPECT (SPECT/CT); thiết bị bức xạ phát tia X trong phân tích huỳnh quang tia X, phân tích nhiễu xạ tia X, soi bo mạch, soi hiển vi điện tử, soi kiểm tra an ninh",
        "field": "AN TOÀN BỨC XẠ VÀ HẠT NHÂN",
        "evidenceUrl": "https://cdn.haiphong.gov.vn/gov-hpg/6860/tintuc/2025/7/tp-danh-muc-thu-tuc-hanh-chinh-thuc-hien-tiep-nhan-tai-trung-tam-phuc-vu-hanh-chinh-cong-thanh-pho-hai-phong638871741697189500638871777775583332638874713710462106.pdf",
    },
    "1.013885": {
        "name": "Ngừng kinh doanh dịch vụ viễn thông đối với doanh nghiệp viễn thông không phải là doanh nghiệp viễn thông nắm giữ phương tiện thiết yếu, doanh nghiệp viễn thông có vị trí thống lĩnh thị trường hoặc doanh nghiệp thuộc nhóm doanh nghiệp viễn thông có vị trí thống lĩnh thị trường đối với thị trường dịch vụ viễn thông Nhà nước quản lý, doanh nghiệp cung cấp dịch vụ viễn thông công ích (có giấy phép cung cấp dịch vụ có hạ tầng mạng, loại mạng viễn thông công cộng cố định mặt đất không sử dụng băng tần số vô tuyến điện, không sử dụng số thuê bao viễn thông có phạm vi thiết lập mạng viễn thông trên một tỉnh, thành phố trực thuộc trung ương) khi ngừng kinh doanh một phần hoặc toàn bộ các dịch vụ viễn thông",
        "field": "HOẠT ĐỘNG VIỄN THÔNG",
        "evidenceUrl": "https://cdn.haiphong.gov.vn/gov-hpg/1/steeringdocument/2025/8/quyet-dinh-ve-viec-cong-bo-danh-muc-thu-tuc-hanh-chinh-thuc-hien-khong-phu-thuoc-vao-dia-gioi-hanh-chinh-trong-pham-vi-thanh-pho-thuoc-pham-vi-chuc-nang-quan-ly-cua-so-khoa-hoc-va-cong-nghe638913867171575582.pdf",
    },
}


def space(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_code(value: str) -> str:
    value = value.strip().rstrip(".")
    if not CODE_RE.fullmatch(value):
        return value
    left, right = value.split(".", 1)
    return f"{left}.{right.ljust(6, '0')}"


def fetch_pdf() -> bytes:
    req = Request(PDF_URL, headers={"User-Agent": "BangNiemYetVinhBao-City-Baseline/1.0"})
    with urlopen(req, timeout=60) as response:
        data = response.read()
    if not data.startswith(b"%PDF"):
        raise RuntimeError("Official city baseline attachment is not a PDF")
    return data


def page_fragments(page) -> list[tuple[float, float, str]]:
    fragments: list[tuple[float, float, str]] = []

    def visitor(text, cm, tm, font, size):
        value = space(text)
        if value:
            fragments.append((float(tm[5]), float(tm[4]), value))

    page.extract_text(visitor_text=visitor)
    return fragments


def logical_streams(fragments: list[tuple[float, float, str]]) -> list[list[tuple[float, float, str]]]:
    if not fragments:
        return []
    streams: list[list[tuple[float, float, str]]] = [[]]
    previous_y = fragments[0][0]
    for item in fragments:
        y = item[0]
        if streams[-1] and y - previous_y > 250:
            streams.append([])
        streams[-1].append(item)
        previous_y = y
    return streams


def column_text(items, lower: float, upper: float, xmin: float, xmax: float) -> str:
    selected = [item for item in items if lower < item[0] <= upper and xmin <= item[1] < xmax]
    buckets: dict[float, list[tuple[float, float, str]]] = {}
    for item in selected:
        buckets.setdefault(round(item[0], 1), []).append(item)
    lines: list[str] = []
    for y in sorted(buckets, reverse=True):
        line = space(" ".join(item[2] for item in sorted(buckets[y], key=lambda item: item[1])))
        if line:
            lines.append(line)
    return space(" ".join(lines))


def extract_rows(reader: PdfReader) -> list[dict]:
    rows: list[dict] = []
    for page_no, page in enumerate(reader.pages, start=1):
        for stream_no, items in enumerate(logical_streams(page_fragments(page)), start=1):
            codes: list[tuple[float, str]] = []
            for y, x, text in items:
                code = text.strip().rstrip(".")
                if 105 <= x <= 175 and CODE_RE.fullmatch(code):
                    codes.append((y, normalize_code(code)))
            codes.sort(key=lambda item: -item[0])
            for index, (y, code) in enumerate(codes):
                upper = (codes[index - 1][0] + y) / 2 if index else min(800.0, y + 60.0)
                lower = (y + codes[index + 1][0]) / 2 if index + 1 < len(codes) else max(30.0, y - 60.0)
                rows.append(
                    {
                        "code": code,
                        "name": column_text(items, lower, upper, 180.0, 443.0),
                        "field": column_text(items, lower, upper, 443.0, 700.0),
                        "sourcePage": page_no,
                        "sourceStream": stream_no,
                    }
                )
    return rows


def dedupe(rows: list[dict]) -> list[dict]:
    by_code: dict[str, dict] = {}
    for row in rows:
        code = row["code"]
        previous = by_code.get(code)
        if not previous:
            by_code[code] = dict(row)
            continue
        # Duplicate codes only occur in later supplementary sections. Keep the
        # first official occurrence, using the later one only to fill a blank or
        # obvious truncated prefix from the same source PDF.
        for field in ("name", "field"):
            old = space(str(previous.get(field, "")))
            new = space(str(row.get(field, "")))
            if not old and new:
                previous[field] = new
            elif old and new and old != new and (old.startswith(new) or new.startswith(old)):
                previous[field] = new if len(new) > len(old) else old

    for code, override in NAME_OVERRIDES.items():
        if code in by_code:
            by_code[code]["name"] = override["name"]
            by_code[code]["field"] = override["field"]
            by_code[code]["overrideEvidenceUrl"] = override["evidenceUrl"]

    rows_out = sorted(by_code.values(), key=lambda row: row["code"])
    missing_names = [row["code"] for row in rows_out if not space(str(row.get("name", "")))]
    if missing_names:
        raise RuntimeError(f"Baseline rows without TTHC name: {missing_names}")
    return rows_out


def build(data: bytes) -> dict:
    digest = hashlib.sha256(data).hexdigest()
    if digest != EXPECTED_SHA256:
        raise RuntimeError(f"Official city baseline SHA256 changed: {digest}")
    reader = PdfReader(io.BytesIO(data))
    if len(reader.pages) != EXPECTED_PAGES:
        raise RuntimeError(f"Official city baseline page count changed: {len(reader.pages)}")
    rows = dedupe(extract_rows(reader))
    if len(rows) != EXPECTED_UNIQUE_CODES:
        raise RuntimeError(f"Official city baseline code count changed: {len(rows)}")
    return {
        "format": "haiphong-city-reception-baseline",
        "version": 1,
        "publishedDate": PUBLISHED_DATE,
        "articleUrl": ARTICLE_URL,
        "pdfUrl": PDF_URL,
        "pdfSha256": digest,
        "pageCount": len(reader.pages),
        "scope": "Danh mục TTHC thực hiện tiếp nhận tại Trung tâm Phục vụ hành chính công thành phố Hải Phòng",
        "identity": "Mã TTHC",
        "rowCount": len(rows),
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "data/source-audit/city-reception-baseline.json")
    args = parser.parse_args()
    data = args.pdf.read_bytes() if args.pdf else fetch_pdf()
    payload = build(data)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"rowCount": payload["rowCount"], "pageCount": payload["pageCount"], "pdfSha256": payload["pdfSha256"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
