#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sinh js/extra-generated.js: danh mục QĐ công bố, QĐ theo TTHC và phí/lệ phí.

Nguồn (không nhập tay vào file sinh):
- data/thu-tuc.json                                   (canonical Master TTHC)
- data/source-audit/city-updates-current.json         (QĐ công bố của UBND TP đã đối chiếu PDF)
- data/phu-luc/phi-le-phi-van-ban.json                (registry văn bản phí, lệ phí)

Chạy: python scripts/build_extra_data.py            # ghi file
      python scripts/build_extra_data.py --check    # báo lỗi nếu file sinh đã cũ
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "data/thu-tuc.json"
CITY = ROOT / "data/source-audit/city-updates-current.json"
FEES = ROOT / "data/phu-luc/phi-le-phi-van-ban.json"
SPECIALIZED = ROOT / "data/phu-luc/phi-le-phi-chuyen-nganh.json"
OUTPUT = ROOT / "js/extra-generated.js"

# Trích xuất văn bản từ bài đăng QĐ 3433/QĐ-UBND (27/8/2026, đất đai cấp xã) đã ghi nhầm
# "2026/QĐ-UBND" và "2628/QĐ-UBND" vào decisionNumbers; tiêu đề bài nêu rõ là QĐ 3433.
DECISION_ALIASES = {
    "2026/QĐ-UBND": "3433/QĐ-UBND",
    "2628/QĐ-UBND": "3433/QĐ-UBND",
}
# QĐ 3433 không có dòng trong city-updates-current (được nạp qua đường đất đai cấp xã).
SUPPLEMENTAL_CITY = {
    "3433/QĐ-UBND": {
        "decisionNo": "3433/QĐ-UBND",
        "decisionDate": "",
        "publishedDate": "2026-08-27",
        "effectiveDate": "",
        "field": "ĐẤT ĐAI",
        "title": "Quyết định số 3433/QĐ-UBND của UBND thành phố: công bố thủ tục hành chính đặc thù được sửa đổi, bổ sung lĩnh vực đất đai thuộc phạm vi chức năng quản lý của Sở Nông nghiệp và Môi trường",
        "articleUrl": "https://vinhbao.haiphong.gov.vn/linh-vuc-dat-dai/quyet-dinh-so-3433-qd-ubnd-cua-ubnd-thanh-pho-cong-bo-thu-tuc-hanh-chinh-dac-thu-duoc-sua-doi-bo-956002",
        "ingestStatus": "applied",
        "currentStateAtAsOf": "current_or_immediate_unless_repealed",
    }
}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def vn_date(iso: str) -> str:
    if not iso:
        return ""
    y, m, d = iso.split("-")
    return f"{int(d):02d}/{int(m):02d}/{y}"


def decision_sort_key(item: dict):
    return (item.get("decisionDate") or item.get("publishedDate") or "", item["decisionNo"])


def build_decisions(master_rows: list[dict], city: dict, today: str) -> list[dict]:
    by_no: dict[str, dict] = {}
    for d in city["decisions"]:
        if d.get("classification") != "public_tthc":
            continue
        by_no[d["decisionNo"]] = d
    for no, d in SUPPLEMENTAL_CITY.items():
        by_no.setdefault(no, d)

    used = Counter()
    for row in master_rows:
        for raw in str(row.get("quyetDinh") or "").split(";"):
            no = DECISION_ALIASES.get(raw.strip(), raw.strip())
            if no:
                used[no] += 1

    out = []
    for d in sorted(by_no.values(), key=decision_sort_key, reverse=True):
        no = d["decisionNo"]
        status = d.get("ingestStatus", "")
        eff = d.get("effectiveDate") or ""
        if status.startswith("reviewed_"):
            trang_thai = "Đã rà soát – không làm thay đổi TTHC tiếp nhận tại cấp xã"
        elif eff and eff > today:
            trang_thai = f"Chưa có hiệu lực – từ {vn_date(eff)}"
        else:
            trang_thai = "Còn hiệu lực"
        title = (d.get("title") or "").strip()
        for prefix in ("Công khai Quyết định số:", "Công khai Quyết định:"):
            if title.startswith(prefix):
                title = "Quyết định " + title[len(prefix):].strip()
        if not title:
            title = (
                f"Quyết định {no} của UBND thành phố công bố danh mục thủ tục hành chính "
                f"lĩnh vực {(d.get('field') or '').lower()} (trích yếu đầy đủ xem tại nguồn)"
            )
        out.append(
            {
                "so": no,
                "ngay": vn_date(d.get("decisionDate") or d.get("publishedDate") or ""),
                "trichYeu": title,
                "linhVuc": d.get("field") or "",
                "hieuLuc": vn_date(eff) if eff else "[cần bổ sung]",
                "trangThai": trang_thai,
                "soTTHC": used.get(no, 0),
                "link": d.get("articleUrl") or "",
            }
        )
    return out


def build_by_tthc(master_rows: list[dict], city_numbers: set[str]) -> list[dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in master_rows:
        groups[row["linhVuc"]].append(row)
    result = []
    for field in sorted(groups, key=lambda f: (-len(groups[f]), f)):
        rows = groups[field]
        city_cnt: Counter = Counter()
        other_cnt: Counter = Counter()
        for row in rows:
            seen = set()
            for raw in str(row.get("quyetDinh") or "").split(";"):
                no = DECISION_ALIASES.get(raw.strip(), raw.strip())
                if not no or no in seen:
                    continue
                seen.add(no)
                (city_cnt if no in city_numbers else other_cnt)[no] += 1
        lines = [
            f"{no} – {n} TTHC" for no, n in sorted(city_cnt.items(), key=lambda kv: (-kv[1], kv[0]))
        ]
        if other_cnt:
            lines.append(
                "Văn bản công bố khác viện dẫn trong Master Data (Bộ, ngành, QĐ UBND TP đợt trước; số hiệu theo trích xuất Master Data, chưa đối chiếu từng văn bản): "
                + ", ".join(f"{no} ({n})" for no, n in sorted(other_cnt.items(), key=lambda kv: (-kv[1], kv[0])))
            )
        if not lines:
            lines.append("[cần bổ sung] – Master Data chưa ghi quyết định công bố cho nhóm này")
        result.append({"nhom": f"{field} ({len(rows)} TTHC)", "vanBan": lines})
    return result


def build_fees(fees: dict, specialized: dict | None = None) -> dict:
    docs = fees["documents"]
    status_label = {
        "current": "Đang áp dụng",
        "expired": "Đã hết hiệu lực",
        "repealed": "Đã bãi bỏ",
        "partially_repealed": "Bãi bỏ một phần – cần xác minh phần còn lại",
        "unverified": "Chưa xác minh hiệu lực",
    }
    verify_label = {
        "primary_text_read": "đã đọc toàn văn bản gốc",
        "secondary_only": "mới có nguồn thứ cấp",
        "unverified": "chưa đối chiếu",
    }
    tier_label = fees.get("tiers", {})

    def card(doc: dict) -> dict:
        hieu_luc = doc.get("hieuLuc") or ""
        het = doc.get("hetHieuLuc") or ""
        parts = [tier_label.get(str(doc.get("tang", "")), "")] if doc.get("tang") else []
        parts.append(status_label.get(doc["trangThai"], doc["trangThai"]))
        if hieu_luc:
            parts.append(f"hiệu lực từ {hieu_luc}")
        if het:
            parts.append(f"hết hiệu lực từ {het}")
        parts.append(verify_label.get(doc["verification"], doc["verification"]))
        ghi_chu = " ".join(
            x for x in [doc.get("pham_vi", ""), doc.get("chuyenTiep", ""), doc.get("ghiChu", "")] if x
        )
        src = next((s["url"] for s in doc.get("sources", []) if s["role"] in ("primary_text", "official_listing")), "")
        if not src and doc.get("sources"):
            src = doc["sources"][-1]["url"]
        return {
            "so": doc["so"],
            "ngay": doc["ngay"],
            "trichYeu": doc["trichYeu"],
            "trangThai": " · ".join(parts),
            "nhom": doc["nhomHienThi"],
            "tang": doc.get("tang", 5),
            "thuTu": doc.get("thuTu", 50),
            "ghiChu": ghi_chu,
            "link": src,
        }

    cards = sorted((card(d) for d in docs), key=lambda c: (c["tang"], c["thuTu"], c["so"]))

    nq23 = next(d for d in docs if d["id"] == "NQ-23-2026")
    online = nq23["mienPhiTrucTuyen"]
    muc = [
        {
            "nhom": "Nộp hồ sơ trực tuyến – mức thu 0 đồng (NQ 23/2026/NQ-HĐND, từ 08/8/2026)",
            "muc": [{"ten": "Lệ phí: " + t, "muc": "0 đồng"} for t in online["lePhi"]]
            + [{"ten": "Phí: " + t, "muc": "0 đồng"} for t in online["phi"]],
        }
    ]
    for table in fees["feeTables"]:
        muc.append(
            {
                "nhom": table["nhom"],
                "muc": [{"ten": r[0], "muc": r[1]} for r in table["rows"]],
                "ghiChu": table["ghiChu"] + " Đơn vị: " + table["donVi"] + ".",
            }
        )

    if specialized:
        groups: dict[str, dict] = {}
        for item in specialized["items"]:
            g = groups.setdefault(item["loai"], {"vanBan": item["vanBan"], "ghiChu": item.get("ghiChu", ""), "n": 0})
            g["n"] += 1
        muc.append(
            {
                "nhom": "Phí, lệ phí theo văn bản chuyên ngành (không thuộc NQ 23/2026, không miễn khi nộp trực tuyến)",
                "muc": [{"ten": f"{loai} ({g['n']} TTHC)", "muc": g["vanBan"]} for loai, g in groups.items()],
                "ghiChu": specialized["rule"] + " Chi tiết mức thu và căn cứ xem tại từng thủ tục.",
            }
        )

    return {
        "ghiChuChung": (
            "Cập nhật 01/10/2026. Từ 08/8/2026, NQ 23/2026/NQ-HĐND quy định mức thu 0 đồng đối với 04 loại lệ phí và 07 loại phí "
            "khi thực hiện TTHC trực tuyến tại Cổng DVCQG hoặc VNeID; NQ 07/2025 (Hải Dương) và NQ 08/2025 (Hải Phòng) hết hiệu lực "
            "(hồ sơ nộp trước 08/8/2026 vẫn theo nghị quyết cũ). Nộp trực tiếp hoặc qua bưu chính: áp dụng mức thu theo từng loại phí, "
            "lệ phí. Mức thu cụ thể của từng TTHC xem trong chi tiết thủ tục (nguồn Cổng DVCQG). "
            + " ".join(fees["notes"])
        ),
        "nghiQuyetHP": cards,
        "mucThamKhao": muc,
        "capNhat": fees["verifiedAt"],
    }


def render(today: str) -> str:
    master = load(MASTER)
    city = load(CITY)
    fees = load(FEES)
    specialized = load(SPECIALIZED)
    rows = master["thuTuc"]
    decisions = build_decisions(rows, city, today)
    city_numbers = {d["so"] for d in decisions}
    payload = {
        "generated": {
            "dataset_version": master.get("dataset_version"),
            "cityUpdatesAsOf": city.get("asOf"),
            "feeRegistryVerifiedAt": fees.get("verifiedAt"),
            "note": "Sinh tự động bởi scripts/build_extra_data.py — không sửa tay.",
        },
        "quyetDinhCongBo": decisions,
        "quyetDinhTheoTTHC": build_by_tthc(rows, city_numbers),
        "phiLePhi": build_fees(fees, specialized),
    }
    body = json.dumps(payload, ensure_ascii=False, indent=2)
    return (
        "/* Sinh tự động bởi scripts/build_extra_data.py từ data/thu-tuc.json, "
        "city-updates-current.json và data/phu-luc/phi-le-phi-van-ban.json. Không sửa tay. */\n"
        "window.TTHC_EXTRA = Object.assign(window.TTHC_EXTRA || {}, "
        + body
        + ");\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail nếu file sinh khác nội dung hiện có")
    parser.add_argument("--as-of", default=None, help="YYYY-MM-DD; mặc định = asOf của city-updates-current")
    args = parser.parse_args()
    today = args.as_of or load(CITY)["asOf"]
    # Không dùng đồng hồ máy: đầu ra phải tái lập được (CI --check).
    date.fromisoformat(today)
    content = render(today)
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != content:
            print("js/extra-generated.js đã cũ — chạy: python scripts/build_extra_data.py", file=sys.stderr)
            return 1
        print("js/extra-generated.js khớp dữ liệu nguồn")
        return 0
    OUTPUT.write_text(content, encoding="utf-8", newline="\n")
    print(f"Đã ghi {OUTPUT.relative_to(ROOT)} (as-of {today})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
