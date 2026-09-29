#!/usr/bin/env python3
"""Đối chiếu canonical TTHC với Nghị quyết 23/2026/NQ-HĐND (mức thu phí, lệ phí trực tuyến).

Chỉ tạo lớp candidate (promotionStatus=candidate_only); không ghi vào data/thu-tuc.json
và không đồng bộ Google Sheets. Quy tắc khớp là deterministic theo lĩnh vực/tên TTHC.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.canonical_v4 import evidence_id  # noqa: E402

CANONICAL = ROOT / "data" / "thu-tuc.json"
ENRICHMENT = ROOT / "data" / "tthc-guidance-enrichment.json"
POLICY = ROOT / "data" / "source-audit" / "fee-policy" / "nq-23-2026-hdnd-hai-phong.json"
OUTPUT = ROOT / "data" / "source-audit" / "fee-policy" / "nq-23-2026-online-fee-candidates.json"

ONLINE_RATE = "0 đồng"

# Loại trước các TTHC không có kết quả cấp GCN mới (tên chứa "đã được cấp Giấy chứng nhận" không phải kết quả).
LAND_NO_ISSUE = re.compile(r"^(thu hồi|đính chính|xác định lại|tặng cho|xóa ghi nợ|xoá ghi nợ)")
LAND_ISSUE = re.compile(r"(?<!được )(?<!đã )(cấp|cấp đổi|cấp lại) giấy chứng nhận")
LAND_CHANGE = re.compile(r"đăng ký biến động|đăng ký tài sản gắn liền")
LAND_OTHER = re.compile(r"giấy chứng nhận|đăng ký đất đai|xóa ghi nợ|xoá ghi nợ|tặng cho quyền sử dụng đất")
SECURED = re.compile(r"biện pháp bảo đảm|giao dịch bảo đảm|đăng ký thế chấp")
COPY_EXTRACT = re.compile(r"^cấp bản sao trích lục")
MOBILE = re.compile(r"lưu động")


def _low(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().lower()


def classify(row: dict) -> list[dict]:
    """Trả về danh sách match {points, confidence, applicability, reason} cho một TTHC."""
    name = _low(row.get("ten"))
    field = str(row.get("linhVuc") or "").strip().upper()
    out: list[dict] = []

    if field == "HỘ TỊCH":
        if COPY_EXTRACT.search(name):
            out.append({
                "points": ["Điều 2 khoản 1 điểm a"],
                "applicability": "out_of_scope",
                "confidence": "medium",
                "reason": "Khoản thu của TTHC này là phí cấp bản sao trích lục; hướng dẫn DVCQG của các TTHC hộ tịch ghi phí cấp bản sao thực hiện theo Thông tư 281/2016/TT-BTC, không phải lệ phí hộ tịch thuộc thẩm quyền HĐND thành phố. Cần xác minh trước khi kết luận.",
            })
        elif MOBILE.search(name):
            out.append({
                "points": ["Điều 2 khoản 1 điểm a"],
                "applicability": "applies_if_online",
                "confidence": "low",
                "reason": "Thuộc lệ phí hộ tịch nhưng là đăng ký lưu động (cán bộ thực hiện tại nơi cư trú); khả năng nộp qua Cổng DVCQG/VNeID cần xác minh.",
            })
        else:
            out.append({
                "points": ["Điều 2 khoản 1 điểm a"],
                "applicability": "applies",
                "confidence": "high",
                "reason": "TTHC đăng ký hộ tịch; Nghị quyết nêu đích danh lệ phí hộ tịch.",
            })

    if "giấy phép lao động" in name:
        out.append({"points": ["Điều 2 khoản 1 điểm b"], "applicability": "applies", "confidence": "high",
                    "reason": "Tên TTHC là cấp giấy phép lao động."})
    if "giấy phép xây dựng" in name:
        out.append({"points": ["Điều 2 khoản 1 điểm d"], "applicability": "applies", "confidence": "high",
                    "reason": "Tên TTHC là cấp giấy phép xây dựng."})

    if field == "ĐẤT ĐAI":
        land_points = ["Điều 2 khoản 1 điểm c", "Điều 2 khoản 2 điểm b"]
        if LAND_NO_ISSUE.search(name):
            out.append({"points": land_points, "applicability": "applies_if_fee_arises", "confidence": "low",
                        "reason": "TTHC không có kết quả cấp Giấy chứng nhận mới; chưa có nguồn xác nhận phát sinh lệ phí cấp GCN hoặc phí thẩm định."})
        elif LAND_CHANGE.search(name) and not LAND_ISSUE.search(name):
            out.append({"points": land_points, "applicability": "applies_if_fee_arises", "confidence": "medium",
                        "reason": "Đăng ký biến động/đăng ký tài sản: chỉ áp dụng khi hồ sơ có cấp Giấy chứng nhận mới và phát sinh lệ phí cấp GCN/phí thẩm định."})
        elif LAND_ISSUE.search(name):
            out.append({"points": land_points, "applicability": "applies", "confidence": "high",
                        "reason": "Kết quả TTHC là cấp/cấp đổi/cấp lại Giấy chứng nhận."})
        elif LAND_OTHER.search(name):
            out.append({"points": land_points, "applicability": "applies_if_fee_arises", "confidence": "low",
                        "reason": "TTHC liên quan Giấy chứng nhận nhưng chưa có nguồn xác nhận phát sinh lệ phí cấp GCN hoặc phí thẩm định."})

    if SECURED.search(name):
        out.append({"points": ["Điều 2 khoản 2 điểm a"], "applicability": "applies", "confidence": "medium",
                    "reason": "TTHC đăng ký biện pháp bảo đảm; Nghị quyết dùng tên gọi 'phí đăng ký giao dịch bảo đảm' — cần đối chiếu tên khoản phí trên hệ thống Một cửa."})

    env_rules = (
        ("giấy phép môi trường", "Điều 2 khoản 2 điểm c"),
        ("tác động môi trường", "Điều 2 khoản 2 điểm d"),
        ("tài nguyên nước", "Điều 2 khoản 2 điểm đ"),
    )
    for needle, point in env_rules:
        if needle in name:
            out.append({"points": [point], "applicability": "applies", "confidence": "high",
                        "reason": f"Tên TTHC chứa '{needle}'."})
    if re.search(r"cây mẹ|cây đầu dòng|vườn giống|rừng giống", name):
        out.append({"points": ["Điều 2 khoản 2 điểm e"], "applicability": "applies", "confidence": "high",
                    "reason": "Tên TTHC là bình tuyển/công nhận nguồn giống cây lâm nghiệp."})
    if "thể thao" in name and "đủ điều kiện" in name:
        out.append({"points": ["Điều 2 khoản 2 điểm g"], "applicability": "applies", "confidence": "high",
                    "reason": "Tên TTHC là cấp GCN đủ điều kiện kinh doanh hoạt động thể thao."})
    return out


def build(canonical: dict, enrichment: dict, policy: dict) -> dict:
    ev_id = evidence_id(policy["evidence"])
    guidance = {str(r.get("ma")): r for r in enrichment.get("rows") or []}
    valid_points = {item["point"] for item in policy["feeItems"]}
    rows = []
    for row in canonical.get("thuTuc") or []:
        for match in classify(row):
            assert set(match["points"]) <= valid_points, match["points"]
            g = guidance.get(str(row.get("ma")))
            applies = match["applicability"] != "out_of_scope"
            rows.append({
                "ma": row.get("ma"),
                "ten": row.get("ten"),
                "cap": row.get("cap"),
                "linhVuc": row.get("linhVuc"),
                "priority51": bool(row.get("priority51")),
                "currentCanonical": {"phi": row.get("phi", ""), "phiOnline": row.get("phiOnline", "")},
                "currentGuidanceLePhi": (g or {}).get("lePhi"),
                "currentGuidanceProvenance": ((g or {}).get("fieldProvenance") or {}).get("lePhi"),
                "nq23Points": match["points"],
                "applicability": match["applicability"],
                "proposedOnlineFee": ONLINE_RATE if applies else None,
                "proposedOnlineFeeCondition": policy["scope"]["onlineCondition"] if applies else None,
                "effectiveFrom": policy["document"]["effectiveDate"] if applies else None,
                "confidence": match["confidence"],
                "reason": match["reason"],
                "evidenceId": ev_id,
                "promotionStatus": "candidate_only",
            })
    rows.sort(key=lambda r: (not r["priority51"], r["nq23Points"][0], r["ma"]))
    matched_points = {p for r in rows for p in r["nq23Points"]}
    return {
        "format": "online-fee-policy-candidates",
        "version": 1,
        "policy": "Candidate layer only. Không promote vào data/thu-tuc.json, không write-back Google Sheets. Cần review nghiệp vụ trước khi đề xuất promotion.",
        "source": {"decisionNo": policy["document"]["decisionNo"], "evidenceId": ev_id,
                   "attachmentSha256": policy["evidence"]["attachmentSha256"]},
        "summary": {
            "canonicalProcedures": len(canonical.get("thuTuc") or []),
            "matchedRows": len(rows),
            "priority51Rows": sum(r["priority51"] for r in rows),
            "byConfidence": {c: sum(r["confidence"] == c for r in rows) for c in ("high", "medium", "low")},
            "outOfScope": sum(r["applicability"] == "out_of_scope" for r in rows),
            "pointsWithoutCanonicalMatch": sorted(valid_points - matched_points),
        },
        "rows": rows,
    }


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Chỉ kiểm tra file output khớp kết quả build")
    args = parser.parse_args(argv)
    result = build(_load(CANONICAL), _load(ENRICHMENT), _load(POLICY))
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != text:
            print("Online fee candidates lệch so với build; chạy lại script.", file=sys.stderr)
            return 1
        print("Online fee candidates: khớp")
        return 0
    OUTPUT.write_text(text, encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
