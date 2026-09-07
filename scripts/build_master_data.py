#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build provenance-backed Master Data for BangNiemYetVinhBao.

Authoritative status evidence comes from the Vinh Bao / Hai Phong official
portal attachment snapshot stored under data/source-audit. Third-party DVCQG
snapshots, when present, are used only as technical formalityId candidates.
The script deliberately does NOT target a pre-decided procedure count.
"""

from __future__ import annotations

import csv
import json
import re
import unicodedata
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ROOT / "data/source-audit/web010-vinhbao-commune-code-candidates-20260906.json"
ATTACHMENTS = ROOT / "data/source-audit/vinhbao-tthc-attachment-evidence-20260906.json"
DVC_MAPPING = ROOT / "data/source-audit/dvcqg-mapping-candidates-20260907.json"
VERIFIED_DVC_CSV = ROOT / "data/formalityId-mapping-mau.csv"
CITY_UPDATES = ROOT / "data/source-audit/city-updates-20260907.json"
LEGACY_JS = ROOT / "js/data.js"
MASTER_JSON = ROOT / "data/thu-tuc.json"
FALLBACK_JS = ROOT / "js/master-data-fallback.js"
AUDIT_CSV = ROOT / "data/master-data-audit.csv"
EXCLUDED_JSON = ROOT / "data/master-data-excluded.json"
REPORT_MD = ROOT / "data/BAO_CAO_MASTER_DATA_2026-09-07.md"

BASE_SOURCE_SNAPSHOT_DATE = "2026-09-06"
SOURCE_SNAPSHOT_DATE = "2026-09-07"
BUILD_DATE = "2026-09-07"
OFFICIAL_SOURCE = "https://vinhbao.haiphong.gov.vn/thu-tuc-hanh-chinh"
CITY_OFFICIAL_SOURCE = "https://haiphong.gov.vn/thu-tuc-hanh-chinh-76761"

CODE_RE = re.compile(r"\b\d{1,2}\.\d{3,6}\b")
TIME_RE = re.compile(
    r"\b(?:\d+(?:[.,]\d+)?\s*)?(?:ngày|giờ|tháng|năm)(?:\s+làm việc)?\b",
    re.IGNORECASE,
)
DECISION_RE = re.compile(r"\b\d{1,5}/Q(?:Đ|D)-[A-ZĐ]+\b", re.IGNORECASE)

SLUG_FIELD_MAP = {
    "tu-phap": "TƯ PHÁP",
    "noi-vu": "NỘI VỤ",
    "nong-nghiep-va-moi-truong": "NÔNG NGHIỆP VÀ MÔI TRƯỜNG",
    "van-hoa": "VĂN HÓA",
    "y-te": "Y TẾ",
    "xay-dung": "XÂY DỰNG",
    "tai-chinh": "TÀI CHÍNH",
    "khoa-hoc-va-cong-nghe": "KHOA HỌC VÀ CÔNG NGHỆ",
    "dat-dai": "ĐẤT ĐAI",
    "bao-tro-xa-hoi": "BẢO TRỢ XÃ HỘI",
    "giao-duc": "GIÁO DỤC",
    "cong-an": "CÔNG AN",
    "lao-dong": "LAO ĐỘNG",
}

CUT_MARKERS = (
    " - Trung tâm",
    " – Trung tâm",
    " Trung tâm PVHCC",
    " Trung tâm Phục vụ",
    " - UBND",
    " – UBND",
    " Không quy định",
    " Không có",
    " Theo quy định",
    " Nghị quyết số",
    " Nghị định số",
    " Quyết định số",
    " Cung cấp dịch vụ công",
    " Toàn trình",
    " Một phần",
    " - Tại ",
    " Tại Sở ",
    " Tại Trung tâm ",
    " (1) ",
)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def fold(text: str) -> str:
    text = unicodedata.normalize("NFD", text or "")
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", text).strip().lower()


def normalize_code(value: str) -> str:
    m = CODE_RE.search(value or "")
    return m.group(0) if m else (value or "").strip()


def decode_js_string(raw: str) -> str:
    try:
        return json.loads('"' + raw.replace("\n", "\\n") + '"')
    except Exception:
        return raw.replace(r'\"', '"')


def parse_legacy_rows(path: Path) -> dict[str, dict]:
    text = path.read_text(encoding="utf-8", errors="replace")
    start = text.find("thuTuc: [")
    if start < 0:
        return {}
    body = text[start:]
    rows: dict[str, dict] = {}
    str_keys = [
        "ma", "ten", "linhVuc", "cap", "dvctt", "phi", "phiOnline",
        "thoiHan", "qd", "quyetDinh", "coQuan", "formalityId",
    ]
    bool_keys = ["nhanh", "mienPhiTrucTuyen", "phiDiaGioi", "lienThong", "daXacMinh"]
    for line in body.splitlines()[1:]:
        if line.lstrip().startswith("]"):
            break
        if "ma:" not in line or "{" not in line:
            continue
        row: dict = {}
        for key in str_keys:
            m = re.search(rf'\b{re.escape(key)}\s*:\s*"((?:\\.|[^"])*)"', line)
            if m:
                row[key] = decode_js_string(m.group(1))
        for key in bool_keys:
            m = re.search(rf"\b{re.escape(key)}\s*:\s*(true|false)", line, re.I)
            if m:
                row[key] = m.group(1).lower() == "true"
        code = normalize_code(row.get("ma", ""))
        if not code:
            continue
        row["ma"] = code
        prev = rows.get(code)
        if prev:
            merged = dict(prev)
            for k, v in row.items():
                if v not in ("", None, False):
                    if k not in merged or not merged.get(k) or (
                        isinstance(v, str) and len(v) > len(str(merged.get(k, "")))
                    ):
                        merged[k] = v
            for k in bool_keys:
                merged[k] = bool(prev.get(k) or row.get(k))
            rows[code] = merged
        else:
            rows[code] = row
    return rows


def attachment_index(payload: dict) -> dict[str, dict]:
    return {item.get("url"): item for item in payload.get("attachments", []) if item.get("url")}


def latest_evidence(items: list[dict], repeal: bool | None = None) -> list[dict]:
    selected = [x for x in items if repeal is None or bool(x.get("repeal_context")) == repeal]
    return sorted(selected, key=lambda x: (x.get("published_date") or "", x.get("article_url") or ""), reverse=True)


def extract_name_from_snippet(snippet: str, code: str) -> str:
    if not snippet or code not in snippet:
        return ""
    tail = snippet.split(code, 1)[1]
    tail = re.sub(r"^[\s.:;)\]-]+", "", tail)
    tail = re.sub(r"\s+", " ", tail).strip()
    if not tail:
        return ""
    cuts = []
    for marker in CUT_MARKERS:
        pos = tail.find(marker)
        if pos >= 8:
            cuts.append(pos)
    for m in TIME_RE.finditer(tail):
        if m.start() >= 10:
            cuts.append(m.start())
            break
    nxt = CODE_RE.search(tail)
    if nxt and nxt.start() >= 10:
        cuts.append(nxt.start())
    if cuts:
        tail = tail[: min(cuts)]
    tail = tail.strip(" -–—;,.|")
    tail = re.sub(r"^\d+[.)]\s*", "", tail)
    return re.sub(r"\s+", " ", tail).strip()


def looks_like_name(name: str) -> bool:
    if not name or len(name) < 12 or len(name.split()) < 3:
        return False
    bad = ("stt ", "mã số tthc", "tên thủ tục", "trung tâm phục vụ", "phụ lục", "trình tự thực hiện", "bước 1")
    f = fold(name)
    if len(name) > 240 or f.startswith("(1)") or f.startswith("1) trình tự"):
        return False
    return not any(x in f for x in bad)


def infer_field(evidence: list[dict], legacy: dict | None) -> str:
    if legacy and legacy.get("linhVuc"):
        return legacy["linhVuc"].strip()
    for ev in latest_evidence(evidence, False) + latest_evidence(evidence, True):
        path = urlparse(ev.get("article_url") or "").path
        if "quan-ly-ban-hang-da" in path:
            return "QUẢN LÝ BÁN HÀNG ĐA CẤP"
        m = re.search(r"/linh-vuc-([^/]+)/", path)
        if m:
            slug = m.group(1)
            for key, value in SLUG_FIELD_MAP.items():
                if key in slug:
                    return value
        title = ev.get("article_title") or ""
        ft = fold(title)
        for key, value in [
            ("ban hang da cap", "QUẢN LÝ BÁN HÀNG ĐA CẤP"),
            ("di san van hoa", "DI SẢN VĂN HÓA"),
            ("an toan, ve sinh lao dong", "AN TOÀN, VỆ SINH LAO ĐỘNG"),
            ("tre em", "TRẺ EM"),
            ("dan so", "DÂN SỐ"),
            ("boi thuong nha nuoc", "BỒI THƯỜNG NHÀ NƯỚC"),
            ("thue", "THUẾ"),
            ("dat dai", "ĐẤT ĐAI"),
            ("bao tro xa hoi", "BẢO TRỢ XÃ HỘI"),
            ("nguoi lao dong di lam viec o nuoc ngoai", "QUẢN LÝ LAO ĐỘNG NGOÀI NƯỚC"),
            ("viec lam", "VIỆC LÀM"),
            ("khoa hoc va cong nghe", "KHOA HỌC VÀ CÔNG NGHỆ"),
            ("xay dung", "XÂY DỰNG"),
            ("tu phap", "TƯ PHÁP"),
            ("noi vu", "NỘI VỤ"),
            ("nong nghiep", "NÔNG NGHIỆP VÀ MÔI TRƯỜNG"),
        ]:
            if key in ft:
                return value
    return "CHƯA XÁC MINH LĨNH VỰC"


def infer_duration(snippet: str, name: str) -> str:
    if not snippet:
        return ""
    tail = snippet.split(name, 1)[1] if name and name in snippet else snippet
    m = re.search(
        r"\b\d+(?:[.,]\d+)?\s*(?:ngày|giờ|tháng|năm)(?:\s+làm việc)?\b",
        tail,
        re.IGNORECASE,
    )
    return re.sub(r"\s+", " ", m.group(0)).strip() if m else ""


def infer_decisions(evidence: list[dict], attach_idx: dict[str, dict]) -> list[str]:
    vals: list[str] = []
    for ev in evidence:
        att = attach_idx.get(ev.get("attachment_url") or "", {})
        vals.extend(att.get("decision_numbers") or [])
        vals.extend(DECISION_RE.findall(ev.get("article_title") or ""))
    out = []
    for value in vals:
        value = value.replace("QD-", "QĐ-")
        if value not in out:
            out.append(value)
    return out


def evidence_status(evidence: list[dict]) -> tuple[str, str | None, str | None]:
    active_dates = sorted(x.get("published_date") for x in evidence if not x.get("repeal_context") and x.get("published_date"))
    repeal_dates = sorted(x.get("published_date") for x in evidence if x.get("repeal_context") and x.get("published_date"))
    active = active_dates[-1] if active_dates else None
    repeal = repeal_dates[-1] if repeal_dates else None
    if repeal and (not active or repeal >= active):
        return "repealed_official_evidence", active, repeal
    if active:
        return "official_commune_evidence_no_later_repeal_in_snapshot", active, repeal
    return "needs_verification", active, repeal


def load_dvc_mapping() -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    if DVC_MAPPING.exists():
        payload = load_json(DVC_MAPPING)
        for row in payload.get("rows", []):
            grouped[normalize_code(row.get("code", ""))].append(row)
    if VERIFIED_DVC_CSV.exists():
        with VERIFIED_DVC_CSV.open("r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                if not row.get("formalityId"):
                    continue
                grouped[normalize_code(row.get("ma", ""))].append({
                    "code": normalize_code(row.get("ma", "")),
                    "formalityId": row.get("formalityId", "").strip(),
                    "sourceUrl": row.get("link_chi_tiet", "").strip(),
                    "scrapedAt": "",
                    "verificationStatus": row.get("trang_thai_xac_minh", "verified_manual_mapping"),
                    "is_ward": True,
                    "is_province": False,
                })
    return grouped


def choose_dvc_mapping(rows: list[dict]) -> dict | None:
    if not rows:
        return None
    return sorted(
        rows,
        key=lambda x: (
            bool(x.get("is_ward")),
            bool(x.get("is_province")),
            x.get("scrapedAt") or "",
        ),
        reverse=True,
    )[0]


def compact_evidence(evidence: list[dict], attach_idx: dict[str, dict]) -> list[dict]:
    out = []
    seen = set()
    for ev in sorted(evidence, key=lambda x: (x.get("published_date") or "", x.get("article_url") or ""), reverse=True):
        key = (ev.get("article_url"), ev.get("attachment_url"), bool(ev.get("repeal_context")))
        if key in seen:
            continue
        seen.add(key)
        att = attach_idx.get(ev.get("attachment_url") or "", {})
        out.append({
            "articleUrl": ev.get("article_url"),
            "articleTitle": ev.get("article_title"),
            "publishedDate": ev.get("published_date"),
            "classification": ev.get("classification"),
            "attachmentUrl": ev.get("attachment_url"),
            "attachmentSha256": ev.get("attachment_sha256"),
            "decisionNumbers": att.get("decision_numbers") or [],
            "repealContext": bool(ev.get("repeal_context")),
        })
    return out[:8]


CITY_NAME_OVERRIDES = {
    "1.003705": "Công nhận chương trình đào tạo kiến thức pháp luật về bán hàng đa cấp",
    "1.012789": "Cung cấp thông tin, dữ liệu đất đai",
    "1.012818": "Thu hồi Giấy chứng nhận đã cấp lần đầu không đúng quy định của pháp luật đất đai do người sử dụng đất, chủ sở hữu tài sản gắn liền với đất phát hiện và cấp lại Giấy chứng nhận sau khi thu hồi",
    "2.000324": "Xác nhận kiến thức pháp luật về bán hàng đa cấp, kiến thức cho đầu mối tại địa phương",
    "2.000884": "Thủ tục chứng thực chữ ký trong các văn bản (áp dụng cho cả trường hợp chứng thực điểm chỉ và trường hợp người yêu cầu chứng thực không điểm chỉ được)",
    "2.001942": "Chuyển trẻ em đang được chăm sóc thay thế tại cơ sở trợ giúp xã hội đến cá nhân, gia đình nhận chăm sóc thay thế",
    "2.002020": "Chấm dứt hoạt động chi nhánh, văn phòng đại diện, địa điểm kinh doanh",
    "2.002165": "Giải quyết yêu cầu bồi thường tại cơ quan trực tiếp quản lý người thi hành công vụ gây thiệt hại (cấp xã)",
    "1.000321": "Đăng ký khai thác tuyến, bổ sung hoặc thay thế phương tiện khai thác tuyến vận tải hành khách cố định giữa Việt Nam và Campuchia",
    "1.004878": "Giải quyết việc nuôi con nuôi có yếu tố nước ngoài đối với trường hợp cha dượng, mẹ kế nhận con riêng của vợ hoặc chồng; cô, cậu, dì, chú, bác ruột nhận cháu làm con nuôi",
    "1.008675": "Cấp giấy phép trao đổi, tặng cho mẫu vật của loài nguy cấp, quý, hiếm được ưu tiên bảo vệ",
    "1.008725": "Chuyển đổi trường tiểu học, THCS tư thục sang hoạt động không vì lợi nhuận",
    "1.009374": "Cấp giấy phép xuất bản bản tin (địa phương)",
    "1.009386": "Văn bản chấp thuận thay đổi nội dung ghi trong giấy phép xuất bản bản tin (địa phương)",
    "1.013724": "Vay vốn hỗ trợ tạo việc làm, duy trì và mở rộng việc làm từ Quỹ quốc gia về việc làm đối với người lao động",
    "1.013781": "Thủ tục chấp thuận thay đổi nội dung ghi trong giấy phép hoạt động báo chí đối với cơ quan báo chí của địa phương",
    "2.000424": "Hỗ trợ khi hòa giải viên gặp tai nạn hoặc rủi ro ảnh hưởng sức khỏe, tính mạng khi hòa giải",
    "2.000592": "Thủ tục giải quyết khiếu nại về trợ giúp pháp lý",
    "2.002821": "Hỗ trợ đào tạo nghề cho người lao động ở khu vực nông thôn, người lao động là thanh niên",
    "3.000242": "Cấp văn bản cho phép sử dụng thẻ ABTC tại địa phương",
}

NAME_OVERRIDE_SOURCES = {
    "1.008725": "legacy_same_code",
    "2.000424": "legacy_same_code",
}

CITY_SPACING_FIXES = {
    "c ấp": "cấp", "l ại": "lại", "v ận": "vận", "đư ờng": "đường", "b ộ": "bộ",
    "Gi ấy": "Giấy", "gi ấy": "giấy", "g ắn": "gắn", "gi ữa": "giữa", "Vi ệt": "Việt",
    "ti ện": "tiện", "nư ớc": "nước", "th ực": "thực", "Hi ệp": "Hiệp", "đ ịnh": "định",
    "b ổ": "bổ", "ho ặc": "hoặc", "tuy ến": "tuyến", "t ải": "tải", "c ố": "cố",
    "k ỳ": "kỳ", "th ế": "thế", "xu ất": "xuất", "ph ẩm": "phẩm", "đ ặc": "đặc",
    "c ủa": "của", "t ổ": "tổ", "d ịch": "dịch", "v ụ": "vụ", "m ở": "mở",
    "m ục": "mục", "n ội": "nội", "b ị": "bị", "ph ụ": "phụ", "thu ận": "thuận",
    "ho ạt": "hoạt", "đ ộng": "động", "b ản": "bản", "s ở": "sở", "đ ịa": "địa",
    "đ ối": "đối", "v ới": "với", "th ẻ": "thẻ", "đ ồng": "đồng", "qu ốc": "quốc",
    "t ế": "tế", "c ơ": "cơ", "tr ương": "trương", "TT- BNV": "TT-BNV",
    "b ốn": "bốn", "b ằng": "bằng", "h ạn": "hạn", "th ời": "thời", "v ề": "về",
    "đ ổi": "đổi", "đ ến": "đến", "ch ấp": "chấp", "c ầu": "cầu", "h ọc": "học",
    "h ội": "hội", "đ ại": "đại", "k ết": "kết", "hi ện": "hiện", "h ỗ": "hỗ",
    "g ặp": "gặp", "n ạn": "nạn", "hư ởng": "hưởng", "s ức": "sức", "m ạng": "mạng",
    "t ạo": "tạo", "v ực": "vực", "l ập": "lập", "m ẫu": "mẫu", "hi ếm": "hiếm",
    "b ảo": "bảo", "h ồi": "hồi", "s ố": "số", "Th ẻ": "Thẻ", "th ẻ": "thẻ",
    "khi ếu": "khiếu", "n ại": "nại", "vi ệc": "việc", "dư ợng": "dượng", "m ẹ": "mẹ",
    "c ậu": "cậu", "ru ột": "ruột", "nh ận": "nhận", "v ấn": "vấn", "đ ấu": "đấu",
    "s ự": "sự", "t ập": "tập", "d ự": "dự", "ngh ề": "nghề", "duy ệt": "duyệt",
    "nhi ệm": "nhiệm", "ngư ời": "người", "trư ờng": "trường", "ti ểu": "tiểu",
    "th ục": "thục", "t ừ": "từ", "phê duy ệt": "phê duyệt",
}


def repair_city_name(value: str, code: str) -> str:
    if code in CITY_NAME_OVERRIDES:
        return CITY_NAME_OVERRIDES[code]
    value = re.sub(r"\\s+", " ", value or "").strip()
    for bad, good in CITY_SPACING_FIXES.items():
        value = value.replace(bad, good)
    value = re.sub(r"^Thủ tục\\s+Thủ tục\\s+", "Thủ tục ", value, flags=re.IGNORECASE)
    return value.strip(" -–—;,.|")


def city_source_evidence(row: dict) -> dict:
    return {
        "articleUrl": row.get("articleUrl"),
        "articleTitle": f"Quyết định {row.get('decisionNo')}",
        "publishedDate": row.get("publishedDate"),
        "effectiveDate": row.get("effectiveDate"),
        "classification": "public_tthc_city_update",
        "attachmentUrl": row.get("pdfUrl"),
        "attachmentSha256": row.get("pdfSha256"),
        "decisionNumbers": [row.get("decisionNo")] if row.get("decisionNo") else [],
        "repealContext": row.get("sectionStatus") == "repealed",
    }


def make_city_record(row: dict, legacy_row: dict | None, dvc: dict | None) -> dict:
    code = normalize_code(row.get("code", ""))
    name = repair_city_name(row.get("name") or "", code)
    fid = (dvc or {}).get("formalityId") or (legacy_row or {}).get("formalityId") or ""
    record = {
        "ma": code,
        "ten": name,
        "linhVuc": row.get("field") or "CHƯA XÁC MINH LĨNH VỰC",
        "cap": "Cấp tỉnh - tiếp nhận tại Trung tâm PVHCC cấp xã",
        "nhanh": bool((legacy_row or {}).get("nhanh")),
        "mienPhiTrucTuyen": bool((legacy_row or {}).get("mienPhiTrucTuyen")),
        "phiDiaGioi": bool((legacy_row or {}).get("phiDiaGioi")),
        "lienThong": bool((legacy_row or {}).get("lienThong")),
        "phi": (legacy_row or {}).get("phi") or "",
        "phiOnline": (legacy_row or {}).get("phiOnline") or "",
        "thoiHan": (legacy_row or {}).get("thoiHan") or "",
        "dvctt": (legacy_row or {}).get("dvctt") or "",
        "coQuan": (legacy_row or {}).get("coQuan") or "",
        "quyetDinh": row.get("decisionNo") or "",
        "formalityId": fid,
        "daXacMinh": bool(name),
        "verificationStatus": "official_city_decision_commune_reception",
        "nameSource": (
            NAME_OVERRIDE_SOURCES.get(code, "dvcqg_name_by_code_verified")
            if code in CITY_NAME_OVERRIDES
            else "official_city_decision_pdf"
        ),
        "sourceSnapshotDate": SOURCE_SNAPSHOT_DATE,
        "sourceLatestDate": row.get("decisionDate") or row.get("publishedDate"),
        "sourceArticleUrl": row.get("articleUrl"),
        "sourceAttachmentUrl": row.get("pdfUrl"),
        "sourceEvidence": [city_source_evidence(row)],
        "tiepNhanCapXa": True,
    }
    if dvc:
        record["dvcMappingStatus"] = dvc.get("verificationStatus") or "third_party_snapshot_candidate"
        record["dvcMappingSource"] = dvc.get("sourceUrl")
        record["dvcMappingScrapedAt"] = dvc.get("scrapedAt")
    return record


def apply_city_updates(public_rows: list[dict], excluded: list[dict], audit_rows: list[dict], legacy: dict[str, dict], dvc_map: dict[str, list[dict]]) -> dict:
    if not CITY_UPDATES.exists():
        return {"audited": 0, "current": 0, "new": 0, "updated": 0, "repealed": 0, "future": 0}
    payload = load_json(CITY_UPDATES)
    by_code = {normalize_code(x.get("ma", "")): x for x in public_rows}
    excluded_map = {normalize_code(x.get("ma", "")): x for x in excluded}
    audit_map = {normalize_code(x.get("ma", "")): x for x in audit_rows}
    stats = {"audited": 0, "current": 0, "new": 0, "updated": 0, "repealed": 0, "future": 0}
    city_codes = set()

    for item in sorted(payload.get("rows", []), key=lambda x: (x.get("decisionDate") or "", x.get("decisionNo") or "", x.get("code") or "")):
        code = normalize_code(item.get("code", ""))
        if not code:
            continue
        city_codes.add(code)
        name = repair_city_name(item.get("name") or "", code)
        dvc = choose_dvc_mapping(dvc_map.get(code, []))
        decision_no = item.get("decisionNo") or ""
        source_date = item.get("decisionDate") or item.get("publishedDate") or ""
        is_future = item.get("currentStateAtAsOf") == "future_effective"
        is_repealed = item.get("sectionStatus") == "repealed" and not is_future
        is_current = bool(item.get("communeReceptionEvidence")) and not is_future and not is_repealed

        if is_future:
            stats["future"] += 1
            future_meta = {
                "decisionNo": decision_no,
                "effectiveDate": item.get("effectiveDate"),
                "name": name,
                "articleUrl": item.get("articleUrl"),
                "pdfUrl": item.get("pdfUrl"),
            }
            if code in by_code:
                by_code[code]["futureUpdate"] = future_meta
            else:
                record = make_city_record(item, legacy.get(code), dvc)
                record.update({
                    "daXacMinh": False,
                    "verificationStatus": "future_effective_official_decision",
                    "futureEffectiveDate": item.get("effectiveDate"),
                    "exclusionReason": f"Đã công bố nhưng chưa có hiệu lực đến {item.get('effectiveDate')}",
                })
                excluded_map[code] = record
            audit_map[code] = {
                "ma": code, "ten": name, "linhVuc": item.get("field") or "", "status": "future_effective_official_decision",
                "publishable": code in by_code, "active_date": "", "repeal_date": "", "name_source": "official_city_decision_pdf",
                "legacy_match": bool(legacy.get(code)), "name_similarity": "", "phi_dia_gioi": False,
                "formalityId": (dvc or {}).get("formalityId") or "", "decision_numbers": decision_no,
                "article_url": item.get("articleUrl") or "", "attachment_url": item.get("pdfUrl") or "",
                "reason": f"Quyết định có hiệu lực từ {item.get('effectiveDate')}",
            }
            continue

        if is_repealed:
            stats["repealed"] += 1
            prior = by_code.pop(code, None)
            record = dict(prior) if prior else make_city_record(item, legacy.get(code), dvc)
            record.update({
                "ten": record.get("ten") or name,
                "daXacMinh": False,
                "verificationStatus": "repealed_by_official_city_decision",
                "quyetDinh": decision_no,
                "sourceSnapshotDate": SOURCE_SNAPSHOT_DATE,
                "sourceLatestDate": source_date,
                "sourceArticleUrl": item.get("articleUrl"),
                "sourceAttachmentUrl": item.get("pdfUrl"),
                "sourceEvidence": [city_source_evidence(item)],
                "exclusionReason": f"Bị bãi bỏ theo {decision_no}",
            })
            excluded_map[code] = record
            audit_map[code] = {
                "ma": code, "ten": record.get("ten") or name, "linhVuc": record.get("linhVuc") or item.get("field") or "",
                "status": "repealed_by_official_city_decision", "publishable": False, "active_date": "", "repeal_date": source_date,
                "name_source": record.get("nameSource") or "official_city_decision_pdf", "legacy_match": bool(legacy.get(code)),
                "name_similarity": "", "phi_dia_gioi": bool(record.get("phiDiaGioi")), "formalityId": record.get("formalityId") or "",
                "decision_numbers": decision_no, "article_url": item.get("articleUrl") or "", "attachment_url": item.get("pdfUrl") or "",
                "reason": f"Bị bãi bỏ theo {decision_no}",
            }
            continue

        if not is_current:
            continue

        stats["current"] += 1
        if code in by_code:
            stats["updated"] += 1
            record = by_code[code]
            if not record.get("ten"):
                record["ten"] = name
            if not record.get("linhVuc") or record.get("linhVuc") == "CHƯA XÁC MINH LĨNH VỰC":
                record["linhVuc"] = item.get("field") or record.get("linhVuc")
            decisions = [x.strip() for x in (record.get("quyetDinh") or "").split(";") if x.strip()]
            if decision_no and decision_no not in decisions:
                decisions.append(decision_no)
            record.update({
                "quyetDinh": "; ".join(decisions),
                "daXacMinh": True,
                "verificationStatus": "official_city_decision_commune_reception",
                "sourceSnapshotDate": SOURCE_SNAPSHOT_DATE,
                "sourceLatestDate": source_date,
                "sourceArticleUrl": item.get("articleUrl"),
                "sourceAttachmentUrl": item.get("pdfUrl"),
                "tiepNhanCapXa": True,
            })
            record["sourceEvidence"] = ([city_source_evidence(item)] + list(record.get("sourceEvidence") or []))[:8]
        else:
            stats["new"] += 1
            record = make_city_record(item, legacy.get(code), dvc)
            by_code[code] = record

        excluded_map.pop(code, None)
        audit_map[code] = {
            "ma": code, "ten": record.get("ten") or name, "linhVuc": record.get("linhVuc") or "",
            "status": "official_city_decision_commune_reception", "publishable": True, "active_date": source_date, "repeal_date": "",
            "name_source": record.get("nameSource") or "official_city_decision_pdf", "legacy_match": bool(legacy.get(code)),
            "name_similarity": "", "phi_dia_gioi": bool(record.get("phiDiaGioi")), "formalityId": record.get("formalityId") or "",
            "decision_numbers": record.get("quyetDinh") or decision_no, "article_url": item.get("articleUrl") or "",
            "attachment_url": item.get("pdfUrl") or "", "reason": "",
        }

    stats["audited"] = len(city_codes)
    public_rows[:] = list(by_code.values())
    excluded[:] = list(excluded_map.values())
    audit_rows[:] = sorted(audit_map.values(), key=lambda x: normalize_code(x.get("ma", "")))
    return stats


def main() -> int:
    candidates_payload = load_json(CANDIDATES)
    attachment_payload = load_json(ATTACHMENTS)
    attach_idx = attachment_index(attachment_payload)
    legacy = parse_legacy_rows(LEGACY_JS)
    dvc_map = load_dvc_mapping()
    public_rows: list[dict] = []
    excluded: list[dict] = []
    audit_rows: list[dict] = []

    for candidate in candidates_payload.get("candidates", []):
        code = normalize_code(candidate.get("procedure_code", ""))
        evidence = candidate.get("evidence") or []
        legacy_row = legacy.get(code)
        status, active_date, repeal_date = evidence_status(evidence)

        official_name = ""
        for ev in latest_evidence(evidence, False) + latest_evidence(evidence, True):
            name_try = extract_name_from_snippet(ev.get("snippet") or "", code)
            if looks_like_name(name_try):
                official_name = name_try
                break

        official_name = repair_city_name(official_name, code)
        legacy_name = repair_city_name((legacy_row or {}).get("ten", ""), code)
        if official_name:
            name = official_name
            name_source = (
                NAME_OVERRIDE_SOURCES.get(code, "dvcqg_name_by_code_verified")
                if code in CITY_NAME_OVERRIDES
                else "official_attachment_snippet"
            )
        elif legacy_name:
            name = legacy_name
            name_source = "legacy_match_needs_name_recheck"
        else:
            name = ""
            name_source = "unresolved"

        similarity = ""
        if official_name and legacy_name:
            similarity = round(SequenceMatcher(None, fold(official_name), fold(legacy_name)).ratio(), 3)

        field = infer_field(evidence, legacy_row)
        latest_non_repeal = latest_evidence(evidence, False)
        primary_ev = latest_non_repeal[0] if latest_non_repeal else (latest_evidence(evidence)[0] if evidence else {})
        decisions = infer_decisions(evidence, attach_idx)
        dvc = choose_dvc_mapping(dvc_map.get(code, []))
        formality_id = (dvc or {}).get("formalityId") or (legacy_row or {}).get("formalityId") or ""

        row = {
            "ma": code,
            "ten": name,
            "linhVuc": field,
            "cap": (legacy_row or {}).get("cap") or "Xã / điểm tiếp nhận cấp xã",
            "nhanh": bool((legacy_row or {}).get("nhanh")),
            "mienPhiTrucTuyen": bool((legacy_row or {}).get("mienPhiTrucTuyen")),
            "phiDiaGioi": any(ev.get("classification") == "non_geo_tthc" for ev in evidence)
                or bool((legacy_row or {}).get("phiDiaGioi")),
            "lienThong": bool((legacy_row or {}).get("lienThong")),
            "phi": (legacy_row or {}).get("phi") or "",
            "phiOnline": (legacy_row or {}).get("phiOnline") or "",
            "thoiHan": (legacy_row or {}).get("thoiHan") or infer_duration(primary_ev.get("snippet") or "", name),
            "dvctt": (legacy_row or {}).get("dvctt") or "",
            "coQuan": (legacy_row or {}).get("coQuan") or "",
            "quyetDinh": "; ".join(decisions),
            "formalityId": formality_id,
            "daXacMinh": status.startswith("official_") and bool(name),
            "verificationStatus": status,
            "nameSource": name_source,
            "sourceSnapshotDate": SOURCE_SNAPSHOT_DATE,
            "sourceLatestDate": active_date or repeal_date,
            "sourceArticleUrl": primary_ev.get("article_url"),
            "sourceAttachmentUrl": primary_ev.get("attachment_url"),
            "sourceEvidence": compact_evidence(evidence, attach_idx),
        }
        if dvc:
            row["dvcMappingStatus"] = dvc.get("verificationStatus") or "third_party_snapshot_candidate"
            row["dvcMappingSource"] = dvc.get("sourceUrl")
            row["dvcMappingScrapedAt"] = dvc.get("scrapedAt")

        publishable = status.startswith("official_") and bool(name)
        if status == "repealed_official_evidence":
            reason = "Bị bãi bỏ theo bằng chứng chính thức mới nhất trong snapshot"
        elif not name:
            reason = "Chưa trích được tên thủ tục đủ tin cậy"
        elif not publishable:
            reason = "Chưa đủ điều kiện công khai"
        else:
            reason = ""

        audit_rows.append({
            "ma": code,
            "ten": name,
            "linhVuc": field,
            "status": status,
            "publishable": publishable,
            "active_date": active_date or "",
            "repeal_date": repeal_date or "",
            "name_source": name_source,
            "legacy_match": bool(legacy_row),
            "name_similarity": similarity,
            "phi_dia_gioi": row["phiDiaGioi"],
            "formalityId": formality_id,
            "decision_numbers": "; ".join(decisions),
            "article_url": primary_ev.get("article_url") or "",
            "attachment_url": primary_ev.get("attachment_url") or "",
            "reason": reason,
        })
        if publishable:
            public_rows.append(row)
        else:
            excluded.append({**row, "exclusionReason": reason})

    city_stats = apply_city_updates(public_rows, excluded, audit_rows, legacy, dvc_map)

    public_rows.sort(key=lambda x: (fold(x.get("linhVuc", "")), fold(x.get("ten", "")), x.get("ma", "")))
    for i, row in enumerate(public_rows, 1):
        row["stt"] = i

    summary = {
        "officialCandidateCodes": len(candidates_payload.get("candidates", [])),
        "auditedCodes": len(audit_rows),
        "cityUpdateCodes": city_stats["audited"],
        "cityCurrentProcedures": city_stats["current"],
        "cityNewProcedures": city_stats["new"],
        "cityUpdatedProcedures": city_stats["updated"],
        "publishedProcedures": len(public_rows),
        "excludedProcedures": len(excluded),
        "repealedProcedures": sum(1 for x in audit_rows if "repealed" in str(x.get("status", ""))),
        "futureEffectiveProcedures": sum(1 for x in audit_rows if x.get("status") == "future_effective_official_decision" and not x.get("publishable")),
        "unresolvedNameProcedures": sum(1 for x in audit_rows if not x["ten"]),
        "legacyMatchedCodes": sum(1 for x in audit_rows if x["legacy_match"]),
        "formalityIdMapped": sum(1 for x in public_rows if x.get("formalityId")),
        "phiDiaGioi": sum(1 for x in public_rows if x.get("phiDiaGioi")),
    }
    master = {
        "format": "bangniemyet-vinhbao-master-data",
        "version": 2,
        "updatedAt": BUILD_DATE,
        "sourceSnapshotDate": SOURCE_SNAPSHOT_DATE,
        "source": OFFICIAL_SOURCE,
        "sourceSites": [OFFICIAL_SOURCE, CITY_OFFICIAL_SOURCE],
        "statusRule": (
            "Công khai khi mã có bằng chứng trực tiếp cấp xã/điểm tiếp nhận cấp xã trong phụ lục "
            "chính thức và không có bằng chứng bãi bỏ cùng ngày hoặc mới hơn trong snapshot. "
            "Không ép số lượng mục tiêu."
        ),
        "thuTuc": public_rows,
        "summary": summary,
    }

    MASTER_JSON.write_text(json.dumps(master, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    EXCLUDED_JSON.write_text(json.dumps({
        "format": "bangniemyet-vinhbao-master-data-excluded",
        "version": 1,
        "sourceSnapshotDate": SOURCE_SNAPSHOT_DATE,
        "rows": excluded,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    fallback_payload = json.dumps(master, ensure_ascii=False, separators=(",", ":"))
    FALLBACK_JS.write_text(
        "/* Generated by scripts/build_master_data.py. Do not edit manually. */\n"
        f"window.TTHC_MASTER_DATA={fallback_payload};\n"
        "window.TTHC_DATA={...(window.TTHC_DATA||{}),"
        "updatedAt:window.TTHC_MASTER_DATA.updatedAt,"
        "source:window.TTHC_MASTER_DATA.source,"
        "sourceSnapshotDate:window.TTHC_MASTER_DATA.sourceSnapshotDate,"
        "thuTuc:window.TTHC_MASTER_DATA.thuTuc};\n",
        encoding="utf-8",
    )

    with AUDIT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(audit_rows[0].keys()))
        writer.writeheader()
        writer.writerows(audit_rows)

    report = f"""# Báo cáo Master Data TTHC – snapshot {SOURCE_SNAPSHOT_DATE}

## Kết quả

- Mã ứng viên cấp xã/điểm tiếp nhận cấp xã từ snapshot Vĩnh Bảo: **{summary['officialCandidateCodes']}**
- Mã được audit sau khi bổ sung 06 quyết định thành phố: **{summary['auditedCodes']}**
- Mã xuất hiện trong 06 quyết định cập nhật thành phố: **{summary['cityUpdateCodes']}**
- TTHC hiện hành đưa vào tập công khai: **{summary['publishedProcedures']}**
- TTHC loại khỏi tập công khai: **{summary['excludedProcedures']}**
  - Bị bãi bỏ: **{summary['repealedProcedures']}**
  - Đã công bố nhưng chưa đến ngày hiệu lực: **{summary['futureEffectiveProcedures']}**
- TTHC mới được bổ sung từ quyết định thành phố: **{summary['cityNewProcedures']}**
- TTHC hiện có được cập nhật bởi quyết định thành phố: **{summary['cityUpdatedProcedures']}**
- Chưa trích được tên đủ tin cậy: **{summary['unresolvedNameProcedures']}**
- Có formalityId trong Master Data: **{summary['formalityIdMapped']}**
- Được đánh dấu phi địa giới theo nguồn công bố: **{summary['phiDiaGioi']}**

> **Lưu ý phạm vi:** {summary['publishedProcedures']} là số TTHC trong tập niêm yết/tra cứu của Trung tâm PVHCC xã Vĩnh Bảo theo bằng chứng nguồn đã audit. Tập này có thể gồm TTHC cấp tỉnh được tiếp nhận tại Trung tâm PVHCC cấp xã; không được hiểu là toàn bộ đều thuộc thẩm quyền giải quyết của UBND xã.

## Nguồn cập nhật đến 07/09/2026

- Snapshot cổng TTHC xã Vĩnh Bảo và các phụ lục chính thức đã lưu trong `data/source-audit/`.
- Quyết định 3500/QĐ-UBND, 3501/QĐ-UBND, 3508/QĐ-UBND, 3509/QĐ-UBND, 3517/QĐ-UBND, 3523/QĐ-UBND của UBND thành phố Hải Phòng.
- QĐ 3501/QĐ-UBND có hiệu lực từ **01/03/2027**; 02 mã trong quyết định được lưu ở nhóm tương lai, chưa đưa vào tập hiện hành ngày 07/09/2026.
- Quyết định/quy trình nội bộ như 3507, 3521, 3537 không được đưa vào Master Data công khai cho người dân.

## Quy tắc

1. Không ép danh mục về con số 473 hoặc bất kỳ số lượng mục tiêu định trước nào.
2. Trạng thái hiện hành/bãi bỏ lấy từ bằng chứng công bố chính thức Vĩnh Bảo/Hải Phòng, có ngày nguồn và URL truy vết.
3. Mã bị bãi bỏ được loại khỏi `data/thu-tuc.json` nhưng giữ dấu vết trong `data/master-data-excluded.json` và audit CSV.
4. Mã có quyết định chưa đến ngày hiệu lực được lưu riêng và không hiển thị như TTHC hiện hành.
5. Dữ liệu cũ chỉ bổ sung thuộc tính khi trùng mã; không tự xác nhận hiệu lực.
6. Tên bị lỗi trích PDF được chuẩn hóa theo cùng mã từ dữ liệu kế thừa hoặc Cổng DVCQG; việc này không thay đổi căn cứ xác định trạng thái.
7. formalityId là lớp ánh xạ kỹ thuật. Thiếu UUID không làm thay đổi trạng thái pháp lý; website fallback sang tra cứu DVCQG theo tên/mã.

## Tệp kiểm soát

- `data/thu-tuc.json`: Master Data public.
- `data/master-data-audit.csv`: toàn bộ mã đã audit.
- `data/master-data-excluded.json`: mã bãi bỏ/chưa hiệu lực.
- `data/source-audit/`: snapshot, PDF và bằng chứng nguồn.
- `js/master-data-fallback.js`: fallback sinh tự động từ cùng Master Data.
"""
    REPORT_MD.write_text(report, encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
