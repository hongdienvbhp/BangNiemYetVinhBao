#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CITY_UPDATES = ROOT / "data/source-audit/city-updates-current.json"
MASTER = ROOT / "data/thu-tuc.json"
EXCLUDED = ROOT / "data/master-data-excluded.json"
OUTPUT = ROOT / "data/THEO_DOI_THAY_DOI_TTHC.csv"

HEADERS = [
    "Ngày quyết định",
    "Số quyết định",
    "Mã TTHC",
    "Tên thủ tục",
    "Lĩnh vực",
    "Loại thay đổi",
    "Chi tiết thay đổi",
    "Cấp/thẩm quyền",
    "Ngày hiệu lực",
    "Trạng thái canonical",
    "URL bài công bố",
    "URL file quyết định",
    "SHA-256",
    "Ghi chú nguồn",
]


def fold(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value or "")
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn").lower()


def classify_change(row: dict) -> tuple[str, str]:
    status = str(row.get("sectionStatus") or "published").strip()
    context = fold(str(row.get("context") or ""))
    if status == "modified" and "sau cat giam" in context and "khong thuc hien cat giam" not in context:
        return "reduced", "Có bằng chứng trong phụ lục về nội dung sau cắt giảm"
    mapping = {
        "new": ("new", "Ban hành mới"),
        "modified": ("modified", "Sửa đổi/bổ sung"),
        "repealed": ("repealed", "Bãi bỏ"),
        "replaced_or_replacement": ("replaced", "Thay thế/được thay thế"),
        "published": ("published", "Công bố/chuẩn hóa"),
    }
    return mapping.get(status, ("needs_review", status or "Không xác định"))


def build_rows(city: dict, master: dict, excluded: dict) -> list[dict]:
    current = {
        str(row.get("ma") or "").strip(): row
        for row in master.get("thuTuc") or []
        if isinstance(row, dict)
    }
    excluded_by_code = {
        str(row.get("ma") or "").strip(): row
        for row in excluded.get("rows") or []
        if isinstance(row, dict)
    }
    output: list[dict] = []
    for decision in city.get("decisions") or []:
        for row in decision.get("rows") or []:
            code = str(row.get("code") or "").strip()
            if not code:
                continue
            change_type, change_detail = classify_change(row)
            if code in current:
                canonical_status = "current"
            elif str((excluded_by_code.get(code) or {}).get("verificationStatus") or "").startswith("repealed"):
                canonical_status = "repealed"
            elif str((excluded_by_code.get(code) or {}).get("verificationStatus") or "") == "future_effective_official_decision":
                canonical_status = "future_effective"
            else:
                canonical_status = "not_in_current_master"
            output.append({
                "Ngày quyết định": decision.get("decisionDate") or "",
                "Số quyết định": decision.get("decisionNo") or "",
                "Mã TTHC": code,
                "Tên thủ tục": row.get("name") or (current.get(code) or excluded_by_code.get(code) or {}).get("ten") or "",
                "Lĩnh vực": decision.get("field") or (current.get(code) or excluded_by_code.get(code) or {}).get("linhVuc") or "",
                "Loại thay đổi": change_type,
                "Chi tiết thay đổi": change_detail,
                "Cấp/thẩm quyền": row.get("levelHint") or "",
                "Ngày hiệu lực": decision.get("effectiveDate") or "",
                "Trạng thái canonical": canonical_status,
                "URL bài công bố": decision.get("articleUrl") or "",
                "URL file quyết định": decision.get("pdfUrl") or "",
                "SHA-256": decision.get("pdfSha256") or "",
                "Ghi chú nguồn": re.sub(r"\s+", " ", str(row.get("context") or "")).strip()[:500],
            })
    output.sort(key=lambda x: (
        x["Ngày quyết định"],
        x["Số quyết định"],
        x["Mã TTHC"],
        x["Loại thay đổi"],
    ))
    return output


def main() -> int:
    city = json.loads(CITY_UPDATES.read_text(encoding="utf-8"))
    master = json.loads(MASTER.read_text(encoding="utf-8"))
    excluded = json.loads(EXCLUDED.read_text(encoding="utf-8"))
    rows = build_rows(city, master, excluded)
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADERS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"trackingRows": len(rows), "output": str(OUTPUT.relative_to(ROOT))}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
