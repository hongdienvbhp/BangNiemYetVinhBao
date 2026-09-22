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

try:
    from scripts.canonical_v4 import (
        SOURCE_COMMIT_KIND,
        compute_source_commit,
        derive_dataset_date,
        upgrade_record_to_v4,
        build_scoped_submission_url,
    )
except ModuleNotFoundError:
    from canonical_v4 import (
        SOURCE_COMMIT_KIND,
        compute_source_commit,
        derive_dataset_date,
        upgrade_record_to_v4,
        build_scoped_submission_url,
    )

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ROOT / "data/source-audit/web010-vinhbao-commune-code-candidates-20260906.json"
ATTACHMENTS = ROOT / "data/source-audit/vinhbao-tthc-attachment-evidence-20260906.json"
DVC_MAPPING = ROOT / "data/source-audit/dvcqg-mapping-candidates-20260907.json"
DVC_FORMALITY_CANDIDATES = ROOT / "data/source-audit/dvcqg-formality-candidates-current.json"
VERIFIED_DVC_CSV = ROOT / "data/formalityId-mapping-mau.csv"
PRIORITY51_CROSSWALK = ROOT / "data/priority-51-crosswalk.json"
PRIORITY51_LEGAL_VERIFICATION = ROOT / "data/priority-51-legal-verification.json"
CITY_UPDATES = ROOT / "data/source-audit/city-updates-current.json"
OFFICIAL_TABLE_LEVELS = ROOT / "data/source-audit/official-table-level-classification.json"
LEGACY_JS = ROOT / "js/data.js"
MASTER_JSON = ROOT / "data/thu-tuc.json"
FALLBACK_JS = ROOT / "js/master-data-fallback.js"
AUDIT_CSV = ROOT / "data/master-data-audit.csv"
EXCLUDED_JSON = ROOT / "data/master-data-excluded.json"
REPORT_MD = ROOT / "data/BAO_CAO_MASTER_DATA_HIEN_HANH.md"

BASE_SOURCE_SNAPSHOT_DATE = "2026-09-06"


def _source_snapshot_date() -> str:
    if CITY_UPDATES.exists():
        try:
            payload = json.loads(CITY_UPDATES.read_text(encoding="utf-8-sig"))
            value = str(payload.get("asOf") or "").strip()
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                return value
        except (OSError, json.JSONDecodeError):
            pass
    return "2026-09-07"


SOURCE_SNAPSHOT_DATE = _source_snapshot_date()
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


def load_priority51() -> dict[str, dict]:
    if not PRIORITY51_CROSSWALK.exists():
        return {}
    payload = load_json(PRIORITY51_CROSSWALK)
    return {
        normalize_code(row.get("code", "")): row
        for row in payload.get("items", [])
        if normalize_code(row.get("code", ""))
    }


def load_priority51_legal() -> dict[str, dict]:
    if not PRIORITY51_LEGAL_VERIFICATION.exists():
        return {}
    payload = load_json(PRIORITY51_LEGAL_VERIFICATION)
    return {
        normalize_code(row.get("code", "")): row
        for row in payload.get("rows", [])
        if normalize_code(row.get("code", ""))
    }


def load_dvc_mapping() -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    if DVC_MAPPING.exists():
        payload = load_json(DVC_MAPPING)
        for row in payload.get("rows", []):
            grouped[normalize_code(row.get("code", ""))].append(row)
    if DVC_FORMALITY_CANDIDATES.exists():
        payload = load_json(DVC_FORMALITY_CANDIDATES)
        for row in payload.get("rows", []):
            code = normalize_code(row.get("ma", ""))
            fid = str(row.get("formalityId") or "").strip()
            if not code or not fid:
                continue
            grouped[code].append({
                "code": code,
                "formalityId": fid,
                "sourceUrl": row.get("sourceUrl") or "",
                "scrapedAt": row.get("scrapedAt") or "",
                "verificationStatus": "technical_exact_code_candidate",
                "is_ward": bool(row.get("isWard")),
                "is_province": bool(row.get("isProvince")),
            })
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
    for code, row in load_priority51().items():
        if not row.get("formalityId"):
            continue
        grouped[code].append({
            "code": code,
            "formalityId": str(row.get("formalityId") or "").strip(),
            "sourceUrl": row.get("dvcUrl") or "",
            "scrapedAt": "2026-09-06",
            "verificationStatus": "verified_priority51_crosswalk",
            "is_ward": True,
            "is_province": False,
        })
    return grouped


def choose_dvc_mapping(rows: list[dict]) -> dict | None:
    if not rows:
        return None

    def rank(row: dict) -> tuple:
        status = str(row.get("verificationStatus") or "").lower()
        verified = status.startswith("verified_") or status.startswith("da_xac_minh")
        return (
            verified,
            bool(row.get("is_ward")),
            bool(row.get("is_province")),
            row.get("scrapedAt") or "",
        )

    return sorted(rows, key=rank, reverse=True)[0]


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
    "1.008725": "Chuyển đổi trường tiểu học tư thục, trường trung học cơ sở tư thục, trường phổ thông tư thục có nhiều cấp học có cấp học cao nhất là trung học cơ sở do nhà đầu tư trong nước đầu tư sang trường tiểu học tư thục, trường trung học cơ sở tư thục, trường phổ thông tư thục có nhiều cấp học có cấp học cao nhất là trung học cơ sở hoạt động không vì lợi nhuận",
    "1.009374": "Cấp giấy phép xuất bản bản tin (địa phương)",
    "1.009386": "Văn bản chấp thuận thay đổi nội dung ghi trong giấy phép xuất bản bản tin (địa phương)",
    "1.013724": "Vay vốn hỗ trợ tạo việc làm, duy trì và mở rộng việc làm từ Quỹ quốc gia về việc làm đối với người lao động",
    "1.013781": "Thủ tục chấp thuận thay đổi nội dung ghi trong giấy phép hoạt động báo chí đối với cơ quan báo chí của địa phương",
    "2.000424": "Thủ tục thực hiện hỗ trợ khi hòa giải viên gặp tai nạn hoặc rủi ro ảnh hưởng đến sức khỏe, tính mạng trong khi thực hiện hoạt động hòa giải",
    "2.000592": "Thủ tục giải quyết khiếu nại về trợ giúp pháp lý",
    "2.002821": "Hỗ trợ đào tạo nghề cho người lao động ở khu vực nông thôn, người lao động là thanh niên",
    "3.000242": "Cấp văn bản cho phép sử dụng thẻ ABTC tại địa phương",
    "1.001138": "Cấp Giấy phép hoạt động đối với trạm sơ cấp cứu chữ thập đỏ",
    "1.003915": "Thủ tục cấp Chứng chỉ hành nghề đấu giá",
    "1.013822": "Hỗ trợ chi phí mai táng đối với nghệ nhân nhân dân, nghệ nhân ưu tú có thu nhập thấp, hoàn cảnh khó khăn",
    "2.000559": "Cấp Giấy phép hoạt động đối với điểm sơ cấp cứu chữ thập đỏ",
    "2.000815": "Chứng thực bản sao từ bản chính giấy tờ, văn bản do cơ quan, tổ chức có thẩm quyền của Việt Nam; cơ quan, tổ chức có thẩm quyền của nước ngoài; cơ quan, tổ chức có thẩm quyền của Việt Nam liên kết với cơ quan, tổ chức có thẩm quyền của nước ngoài cấp hoặc chứng nhận",
    "1.003622": "Thông báo tổ chức lễ hội cấp xã",
    "1.009453": "Thỏa thuận thông số kỹ thuật xây dựng bến khách ngang sông, bến thủy nội địa phục vụ thi công công trình chính",
    "1.010803": "Giải quyết chế độ trợ cấp thờ cúng liệt sĩ.",
    "1.012753": "Đăng ký đất đai, tài sản gắn liền với đất, cấp Giấy chứng nhận quyền sử dụng đất, quyền sở hữu tài sản gắn liền với đất lần đầu đối với tổ chức đang sử dụng đất",
    "1.012812": "Hòa giải tranh chấp đất đai",
    "1.012817": "Xác định lại diện tích đất ở của hộ gia đình, cá nhân đã được cấp Giấy chứng nhận trước ngày 01 tháng 7 năm 2004",
    "1.013040": "Thủ tục khai, nộp phí bảo vệ môi trường đối với khí thải",
    "1.013128": "Thủ tục thẩm định và phê duyệt kế hoạch ứng phó sự cố tràn dầu của các cửa hàng bán lẻ xăng dầu trên đất liền, trên sông, trên biển và các cơ sở, dự án trên địa bàn xã không thuộc đối tượng kinh doanh, vận chuyển xăng dầu có nguy cơ xảy ra sự cố tràn dầu mức độ nhỏ (dung tích chứa dưới 50 m3)",
    "1.013734": "Đăng ký hợp đồng lao động trực tiếp giao kết.",
    "1.013949": "Giao đất, cho thuê đất, chuyển mục đích sử dụng đất đối với trường hợp giao đất, cho thuê đất không đấu giá quyền sử dụng đất, không đấu thầu lựa chọn nhà đầu tư thực hiện dự án có sử dụng đất; trường hợp giao đất, cho thuê đất thông qua đấu thầu lựa chọn nhà đầu tư thực hiện dự án có sử dụng đất; giao đất và giao rừng; cho thuê đất và cho thuê rừng, gia hạn sử dụng đất khi hết thời hạn sử dụng đất",
    "1.013950": "Chuyển hình thức giao đất, cho thuê đất.",
    "1.013952": "Điều chỉnh quyết định giao đất, cho thuê đất, cho phép chuyển mục đích sử dụng đất do thay đổi căn cứ quyết định giao đất, cho thuê đất, cho phép chuyển mục đích sử dụng đất; điều chỉnh thời hạn sử dụng đất của dự án đầu tư.",
    "1.013953": "Điều chỉnh quyết định giao đất, cho thuê đất, cho phép chuyển mục đích sử dụng đất do sai sót về ranh giới, vị trí, diện tích, mục đích sử dụng giữa bản đồ quy hoạch, bản đồ địa chính, quyết định giao đất, cho thuê đất, cho phép chuyển mục đích sử dụng đất và số liệu bàn giao đất trên thực địa",
    "1.013962": "Giao đất ở có thu tiền sử dụng đất không thông qua đấu giá, không đấu thầu lựa chọn nhà đầu tư thực hiện dự án có sử dụng đất đối với cá nhân là cán bộ, công chức, viên chức, sĩ quan tại ngũ, quân nhân chuyên nghiệp, công chức quốc phòng, công nhân và viên chức quốc phòng, sĩ quan, hạ sĩ quan, công nhân công an, người làm công tác cơ yếu và người làm công tác khác trong tổ chức cơ yếu hưởng lương từ ngân sách nhà nước mà chưa được giao đất ở, nhà ở; giáo viên, nhân viên y tế đang công tác tại các xã biên giới, hải đảo thuộc vùng có điều kiện kinh tế - xã hội khó khăn, vùng có điều kiện kinh tế - xã hội đặc biệt khó khăn nhưng chưa có đất ở, nhà ở tại nơi công tác hoặc chưa được hưởng chính sách hỗ trợ về nhà ở theo quy định của pháp luật về nhà ở; cá nhân thường trú tại xã mà không có đất ở và chưa được Nhà nước giao đất ở hoặc chưa được hưởng chính sách hỗ trợ về nhà ở theo quy định của pháp luật về nhà ở",
    "1.013965": "Sử dụng đất kết hợp đa mục đích, gia hạn phương án sử dụng đất kết hợp đa mục đích.",
    "1.013967": "Giải quyết tranh chấp đất đai thuộc thẩm quyền của Chủ tịch Ủy ban nhân dân cấp xã",
    "1.013978": "Đăng ký đất đai, tài sản gắn liền với đất, cấp Giấy chứng nhận quyền sử dụng đất, quyền sở hữu tài sản gắn liền với đất lần đầu đối với hộ gia đình, cá nhân, cộng đồng dân cư, người gốc Việt Nam định cư ở nước ngoài",
    "1.013979": "Tặng cho quyền sử dụng đất cho Nhà nước hoặc cộng đồng dân cư hoặc mở rộng đường giao thông đối với trường hợp thửa đất chưa được cấp Giấy chứng nhận",
    "1.014111": "Thi tuyển công chức",
    "1.014310": "Thủ tục hưởng trợ cấp sinh hoạt hàng tháng đối với Nghệ nhân nhân dân, Nghệ nhân ưu tú",
    "1.014312": "Thủ tục thôi hưởng trợ cấp sinh hoạt hàng tháng, bảo hiểm y tế đối với Nghệ nhân nhân dân, Nghệ nhân ưu tú",
    "1.115649": "Giao đất, cho thuê đất không thông qua hình thức đấu giá quyền sử dụng đất, không đấu thầu lựa chọn nhà đầu tư thực hiện dự án có sử dụng đất đối với trường hợp thuộc diện chấp thuận chủ trương đầu tư, chấp thuận nhà đầu tư",
    "2.000942": "Thủ tục cấp bản sao có chứng thực từ bản chính hợp đồng, giao dịch đã được chứng thực",
    "2.000992": "Chứng thực chữ ký người dịch mà người dịch là cộng tác viên dịch thuật của Ủy ban nhân dân cấp xã, tổ chức hành nghề công chứng",
    "2.001035": "Chứng thực giao dịch liên quan đến tài sản là động sản, quyền sử dụng đất, nhà ở",
    "2.002481": "Chuyển trường đối với học sinh trung học cơ sở.",
}

NAME_OVERRIDE_SOURCES = {
    "1.001138": "official_source_name_verified",
    "1.003915": "dvcqg_name_by_code_verified",
    "1.013822": "official_source_name_verified",
    "2.000559": "official_source_name_verified",
    "2.000815": "official_source_name_verified",
    "1.008725": "dvcqg_name_by_code_verified",
    "2.000424": "dvcqg_name_by_code_verified",
    "1.003622": "official_city_decision_pdf",
    "1.009453": "official_city_decision_pdf",
    "1.010803": "dvcqg_name_by_code_verified",
    "1.012753": "dvcqg_name_by_code_verified",
    "1.012812": "dvcqg_name_by_code_verified",
    "1.012817": "dvcqg_name_by_code_verified",
    "1.013040": "dvcqg_name_by_code_verified",
    "1.013128": "dvcqg_name_by_code_verified",
    "1.013734": "dvcqg_name_by_code_verified",
    "1.013949": "dvcqg_name_by_code_verified",
    "1.013950": "dvcqg_name_by_code_verified",
    "1.013952": "dvcqg_name_by_code_verified",
    "1.013953": "dvcqg_name_by_code_verified",
    "1.013962": "dvcqg_name_by_code_verified",
    "1.013965": "dvcqg_name_by_code_verified",
    "1.013967": "dvcqg_name_by_code_verified",
    "1.013978": "dvcqg_name_by_code_verified",
    "1.013979": "dvcqg_name_by_code_verified",
    "1.014111": "dvcqg_name_by_code_verified",
    "1.014310": "dvcqg_name_by_code_verified",
    "1.014312": "dvcqg_name_by_code_verified",
    "1.115649": "official_city_decision_pdf",
    "2.000884": "dvcqg_name_by_code_verified",
    "2.000942": "dvcqg_name_by_code_verified",
    "2.000992": "dvcqg_name_by_code_verified",
    "2.001035": "dvcqg_name_by_code_verified",
    "2.002481": "dvcqg_name_by_code_verified",
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
    value = value or ""
    if "\x07" in value:
        parts = [part.strip() for part in value.split("\x07") if part.strip()]
        value = parts[0] if parts else ""
    value = re.sub(r"\s+", " ", value).strip()
    for bad, good in CITY_SPACING_FIXES.items():
        value = value.replace(bad, good)
    value = unicodedata.normalize("NFC", value)
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


def canonical_cap_from_city_row(
    row: dict,
    fallback: str = "Cấp tỉnh - tiếp nhận tại Trung tâm PVHCC cấp xã",
) -> str:
    """Map an explicit extractor levelHint to the legal resolution level.

    communeReceptionEvidence only proves a reception location. When levelHint
    is absent, preserve the existing classification through the fallback value
    rather than inventing a new legal level.
    """
    hint = str(row.get("levelHint") or "").strip().lower()
    if hint == "commune":
        return "Xã"
    if hint == "shared_including_commune":
        return "Dùng chung (cấp bộ, cấp tỉnh, cấp xã)"
    if hint == "province":
        return "Cấp tỉnh - tiếp nhận tại Trung tâm PVHCC cấp xã"
    return fallback

def make_city_record(row: dict, legacy_row: dict | None, dvc: dict | None) -> dict:
    code = normalize_code(row.get("code", ""))
    name = repair_city_name(row.get("name") or "", code)
    fid = (dvc or {}).get("formalityId") or (legacy_row or {}).get("formalityId") or ""
    record = {
        "ma": code,
        "ten": name,
        "linhVuc": row.get("field") or "CHƯA XÁC MINH LĨNH VỰC",
        "cap": canonical_cap_from_city_row(row),
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
        return {"audited": 0, "current": 0, "new": 0, "updated": 0, "repealed": 0, "future": 0, "needsReview": 0}
    payload = load_json(CITY_UPDATES)
    by_code = {normalize_code(x.get("ma", "")): x for x in public_rows}
    excluded_map = {normalize_code(x.get("ma", "")): x for x in excluded}
    audit_map = {normalize_code(x.get("ma", "")): x for x in audit_rows}
    stats = {"audited": 0, "current": 0, "new": 0, "updated": 0, "repealed": 0, "future": 0, "needsReview": 0}
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
        current_state = str(item.get("currentStateAtAsOf") or "")
        needs_review = current_state.startswith("needs_")
        is_future = current_state == "future_effective"
        is_repealed = item.get("sectionStatus") == "repealed" and not is_future and not needs_review
        is_current = (
            bool(item.get("communeReceptionEvidence"))
            and current_state == "current_or_immediate_unless_repealed"
            and not is_repealed
        )

        if needs_review:
            stats["needsReview"] += 1
            continue

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
                "cap": canonical_cap_from_city_row(item, str(record.get("cap") or "")),
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


def priority51_legal_evidence(item: dict) -> list[dict]:
    out: list[dict] = []
    decision_no = str(item.get("decisionNo") or "").strip()
    decision_date = item.get("decisionDate") or None
    is_repealed = item.get("legalStatus") == "repealed_official_evidence"
    for source in item.get("sources") or []:
        url = str(source.get("url") or "").strip()
        if not url:
            continue
        out.append({
            "articleUrl": url,
            "articleTitle": source.get("note") or "Kiểm chứng pháp lý 51 TTHC trọng điểm",
            "publishedDate": decision_date,
            "classification": "priority51_legal_verification",
            "attachmentUrl": url if urlparse(url).path.lower().endswith((".pdf", ".doc", ".docx")) else None,
            "attachmentSha256": None,
            "decisionNumbers": [decision_no] if decision_no else [],
            "repealContext": is_repealed,
        })
    for local in item.get("localCorpusEvidence") or []:
        article_urls = local.get("articleUrls") or []
        out.append({
            "articleUrl": article_urls[0] if article_urls else None,
            "articleTitle": "Bằng chứng đối chiếu trong corpus nguồn chính thức Vĩnh Bảo",
            "publishedDate": None,
            "classification": "priority51_local_corpus_support",
            "attachmentUrl": local.get("attachmentUrl"),
            "attachmentSha256": local.get("attachmentSha256"),
            "decisionNumbers": local.get("decisionNumbers") or [],
            "repealContext": is_repealed,
        })
    return out[:8]


def make_priority51_legal_record(item: dict, legacy_row: dict, dvc: dict | None) -> dict:
    code = normalize_code(item.get("code", ""))
    name = str(item.get("canonicalName") or item.get("priorityName") or "").strip()
    field = str(item.get("field") or "").strip() or "CHƯA XÁC MINH LĨNH VỰC"
    decision_no = str(item.get("decisionNo") or "").strip()
    decision_date = str(item.get("decisionDate") or "").strip()
    checked_at = str(item.get("verificationCheckedAt") or SOURCE_SNAPSHOT_DATE)
    sources = item.get("sources") or []
    source_url = str((sources[0] if sources else {}).get("url") or "")
    formality_id = (dvc or {}).get("formalityId") or ""
    phi_dia_gioi = any("phi-dia-gioi" in str(x.get("url") or "").lower() for x in sources)
    record = {
        "ma": code,
        "ten": name,
        "linhVuc": field,
        "cap": "Xã / điểm tiếp nhận cấp xã",
        "nhanh": False,
        "mienPhiTrucTuyen": False,
        "phiDiaGioi": phi_dia_gioi,
        "lienThong": bool(legacy_row.get("lienThong")),
        "phi": "",
        "phiOnline": "",
        "thoiHan": "",
        "dvctt": "",
        "coQuan": "",
        "quyetDinh": decision_no,
        "formalityId": formality_id,
        "nameSource": "priority51_official_legal_verification",
        "sourceSnapshotDate": SOURCE_SNAPSHOT_DATE,
        "sourceLatestDate": decision_date or checked_at,
        "sourceArticleUrl": source_url,
        "sourceAttachmentUrl": source_url if urlparse(source_url).path.lower().endswith((".pdf", ".doc", ".docx")) else None,
        "sourceEvidence": priority51_legal_evidence(item),
        "priority51LegalVerificationStatus": item.get("legalStatus"),
        "legalVerificationCheckedAt": checked_at,
    }
    if dvc:
        record["dvcMappingStatus"] = dvc.get("verificationStatus") or "verified_priority51_crosswalk"
        record["dvcMappingSource"] = dvc.get("sourceUrl")
        record["dvcMappingScrapedAt"] = dvc.get("scrapedAt")
    return record


def apply_priority51_legal_verification(
    public_rows: list[dict],
    excluded: list[dict],
    audit_rows: list[dict],
    legacy: dict[str, dict],
    dvc_map: dict[str, list[dict]],
    legal_map: dict[str, dict],
) -> dict:
    by_code = {normalize_code(x.get("ma", "")): x for x in public_rows}
    excluded_map = {normalize_code(x.get("ma", "")): x for x in excluded}
    audit_map = {normalize_code(x.get("ma", "")): x for x in audit_rows}
    stats = {"audited": 0, "current": 0, "repealed": 0, "needsVerification": 0, "addedCurrent": 0, "alreadyCurrent": 0, "supersededByNewerEvidence": 0}

    for code, item in sorted(legal_map.items()):
        status = str(item.get("legalStatus") or "needs_verification")
        stats["audited"] += 1
        if status not in {"current_official_commune_evidence", "repealed_official_evidence"}:
            stats["needsVerification"] += 1
            continue

        dvc = choose_dvc_mapping(dvc_map.get(code, []))
        record = make_priority51_legal_record(item, legacy.get(code) or {}, dvc)
        decision_date = str(item.get("decisionDate") or "").strip()
        evidence_date = decision_date or str(item.get("verificationCheckedAt") or "").strip()
        source_url = str(record.get("sourceArticleUrl") or "")
        formality_id = str(record.get("formalityId") or "")

        if status == "repealed_official_evidence":
            stats["repealed"] += 1
            current_existing = by_code.get(code)
            current_date = str((current_existing or {}).get("sourceLatestDate") or "").strip()
            if current_existing and current_date and evidence_date and current_date > evidence_date:
                stats["supersededByNewerEvidence"] += 1
                continue
            by_code.pop(code, None)
            record.update({
                "daXacMinh": False,
                "verificationStatus": "repealed_official_evidence",
                "exclusionReason": (
                    f"Bị bãi bỏ theo {record.get('quyetDinh')}"
                    if record.get("quyetDinh") else "Bị bãi bỏ theo bằng chứng chính thức cấp xã"
                ),
            })
            excluded_map[code] = record
            audit_map[code] = {
                "ma": code, "ten": record.get("ten") or "", "linhVuc": record.get("linhVuc") or "",
                "status": "repealed_official_evidence", "publishable": False,
                "active_date": "", "repeal_date": decision_date,
                "name_source": "priority51_official_legal_verification", "legacy_match": bool(legacy.get(code)),
                "name_similarity": "", "phi_dia_gioi": bool(record.get("phiDiaGioi")),
                "formalityId": formality_id, "decision_numbers": record.get("quyetDinh") or "",
                "article_url": source_url, "attachment_url": record.get("sourceAttachmentUrl") or "",
                "reason": record.get("exclusionReason") or "",
            }
            continue

        stats["current"] += 1
        excluded_existing = excluded_map.get(code)
        excluded_date = str((excluded_existing or {}).get("sourceLatestDate") or "").strip()
        if excluded_existing and excluded_date and evidence_date and excluded_date >= evidence_date:
            stats["supersededByNewerEvidence"] += 1
            continue
        if code in by_code:
            stats["alreadyCurrent"] += 1
            current = by_code[code]
            current["priority51LegalVerificationStatus"] = status
            current["legalVerificationCheckedAt"] = item.get("verificationCheckedAt") or SOURCE_SNAPSHOT_DATE
            existing_urls = {str(x.get("articleUrl") or "") for x in current.get("sourceEvidence") or []}
            additions = [x for x in record.get("sourceEvidence") or [] if str(x.get("articleUrl") or "") not in existing_urls]
            if additions:
                current["sourceEvidence"] = (list(current.get("sourceEvidence") or []) + additions)[:8]
            continue

        stats["addedCurrent"] += 1
        record.update({
            "daXacMinh": True,
            "verificationStatus": "priority51_current_official_commune_evidence",
            "tiepNhanCapXa": True,
        })
        by_code[code] = record
        excluded_map.pop(code, None)
        audit_map[code] = {
            "ma": code, "ten": record.get("ten") or "", "linhVuc": record.get("linhVuc") or "",
            "status": "priority51_current_official_commune_evidence", "publishable": True,
            "active_date": decision_date or item.get("verificationCheckedAt") or SOURCE_SNAPSHOT_DATE,
            "repeal_date": "", "name_source": "priority51_official_legal_verification",
            "legacy_match": bool(legacy.get(code)), "name_similarity": "",
            "phi_dia_gioi": bool(record.get("phiDiaGioi")), "formalityId": formality_id,
            "decision_numbers": record.get("quyetDinh") or "", "article_url": source_url,
            "attachment_url": record.get("sourceAttachmentUrl") or "", "reason": "",
        }

    public_rows[:] = list(by_code.values())
    excluded[:] = list(excluded_map.values())
    audit_rows[:] = sorted(audit_map.values(), key=lambda x: normalize_code(x.get("ma", "")))
    return stats



def load_official_table_levels() -> dict[str, str]:
    if not OFFICIAL_TABLE_LEVELS.exists():
        return {}
    payload = load_json(OFFICIAL_TABLE_LEVELS)
    return {
        normalize_code(item.get("ma", "")): str(item.get("classification") or "").strip()
        for item in payload.get("rows") or []
        if normalize_code(item.get("ma", ""))
        and str(item.get("classification") or "").strip() in {"COMMUNE", "SHARED", "PROVINCE"}
    }


def apply_official_table_levels(
    public_rows: list[dict],
    excluded: list[dict],
    audit_rows: list[dict],
    level_map: dict[str, str],
) -> dict:
    cap_by_level = {
        "COMMUNE": "Xã",
        "SHARED": "Dùng chung (cấp bộ, cấp tỉnh, cấp xã)",
        "PROVINCE": "Cấp tỉnh - tiếp nhận tại Trung tâm PVHCC cấp xã",
    }
    stats = {"classified": len(level_map), "changedPublic": 0, "changedExcluded": 0}

    for collection_name, rows in (("public", public_rows), ("excluded", excluded)):
        for row in rows:
            code = normalize_code(row.get("ma", ""))
            level = level_map.get(code)
            if not level:
                continue
            new_cap = cap_by_level[level]
            if str(row.get("cap") or "") == new_cap:
                continue
            row["cap"] = new_cap
            row["levelClassificationStatus"] = "strong_official_section_heading"
            row["levelClassificationSource"] = "official-table-level-classification"
            if collection_name == "public":
                stats["changedPublic"] += 1
            else:
                stats["changedExcluded"] += 1

    return stats


def main() -> int:
    candidates_payload = load_json(CANDIDATES)
    attachment_payload = load_json(ATTACHMENTS)
    attach_idx = attachment_index(attachment_payload)
    legacy = parse_legacy_rows(LEGACY_JS)
    priority51 = load_priority51()
    priority51_legal = load_priority51_legal()
    official_table_levels = load_official_table_levels()
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
    priority51_legal_stats = apply_priority51_legal_verification(
        public_rows, excluded, audit_rows, legacy, dvc_map, priority51_legal
    )

    for row in public_rows:
        code = normalize_code(row.get("ma", ""))
        priority = priority51.get(code)
        row["priority51"] = bool(priority)
        if not priority:
            continue
        row["priority51Ordinal"] = priority.get("ordinal")
        row["priority51MappingStatus"] = priority.get("mappingStatus")
        if priority.get("mappingMode") == "keyword_fallback":
            row["dvcKeywordUrl"] = priority.get("dvcUrl") or ""
        if priority.get("formalityId") and not row.get("formalityId"):
            row["formalityId"] = priority.get("formalityId")
            row["dvcMappingStatus"] = "verified_priority51_crosswalk"
            row["dvcMappingSource"] = priority.get("dvcUrl") or ""

    audit_by_code = {normalize_code(row.get("ma", "")): row for row in audit_rows}
    for row in public_rows:
        audit = audit_by_code.get(normalize_code(row.get("ma", "")))
        if audit is not None:
            audit["formalityId"] = row.get("formalityId") or ""

    official_table_level_stats = apply_official_table_levels(
        public_rows, excluded, audit_rows, official_table_levels
    )

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
        "cityNeedsReviewRows": city_stats["needsReview"],
        "publishedProcedures": len(public_rows),
        "excludedProcedures": len(excluded),
        "repealedProcedures": sum(1 for x in audit_rows if "repealed" in str(x.get("status", ""))),
        "futureEffectiveProcedures": sum(1 for x in audit_rows if x.get("status") == "future_effective_official_decision" and not x.get("publishable")),
        "unresolvedNameProcedures": sum(1 for x in audit_rows if not x["ten"]),
        "legacyMatchedCodes": sum(1 for x in audit_rows if x["legacy_match"]),
        "formalityIdMapped": sum(1 for x in public_rows if x.get("formalityId")),
        "priority51InCurrentMaster": sum(1 for x in public_rows if x.get("priority51")),
        "priority51CrosswalkTotal": len(priority51),
        "priority51Gap": sum(1 for code in priority51 if code not in {normalize_code(x.get("ma", "")) for x in public_rows}),
        "priority51LegalAudited": priority51_legal_stats["audited"],
        "priority51LegalVerifiedCurrent": priority51_legal_stats["current"],
        "priority51LegalVerifiedRepealed": priority51_legal_stats["repealed"],
        "priority51LegalNeedsVerification": priority51_legal_stats["needsVerification"],
        "priority51LegalAddedCurrent": priority51_legal_stats["addedCurrent"],
        "priority51LegalSupersededByNewerEvidence": priority51_legal_stats["supersededByNewerEvidence"],
        "phiDiaGioi": sum(1 for x in public_rows if x.get("phiDiaGioi")),
        "officialTableLevelClassified": official_table_level_stats["classified"],
        "officialTableLevelChangedPublic": official_table_level_stats["changedPublic"],
        "officialTableLevelChangedExcluded": official_table_level_stats["changedExcluded"],
    }
    existing_version = ""
    if MASTER_JSON.exists():
        try:
            existing_version = str(load_json(MASTER_JSON).get("dataset_version") or "")
        except (OSError, json.JSONDecodeError):
            existing_version = ""
    dataset_date = derive_dataset_date(ROOT, existing_version)
    source_commit = compute_source_commit(ROOT)
    for row in public_rows:
        code = str(row.get("ma") or "").strip()
        formality_id = str(row.get("formalityId") or "").strip()
        if not code:
            continue
        row["nopHoSoUrl"] = build_scoped_submission_url(code, formality_id, str(row.get("cap") or ""))
        route = "province" if str(row.get("cap") or "").strip().lower().startswith("cấp tỉnh") else "ward"
        row["nopHoSoScope"] = {
            "route": route,
            "provinceCode": "31",
            "provinceName": "Hải Phòng",
            **({
                "wardCode": "11824",
                "wardName": "Vĩnh Bảo",
                "commune": "WARD",
            } if route == "ward" else {}),
        }
        row["submissionLinkStatus"] = "resolution_level_scope_verified"
        row["submissionLinkMode"] = "formality_id" if formality_id else "keyword_fallback"

    public_rows = [upgrade_record_to_v4(row, SOURCE_SNAPSHOT_DATE) for row in public_rows]

    master = {
        "format": "bangniemyet-vinhbao-master-data",
        "version": 4,
        "dataset_version": dataset_date.replace("-", "."),
        "source_commit": source_commit,
        "source_commit_kind": SOURCE_COMMIT_KIND,
        "updatedAt": dataset_date,
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
        writer = csv.DictWriter(
            f, fieldnames=list(audit_rows[0].keys()), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(audit_rows)

    report = f"""# Báo cáo Master Data TTHC – snapshot {SOURCE_SNAPSHOT_DATE}

## Kết quả

- Mã ứng viên cấp xã/điểm tiếp nhận cấp xã từ snapshot Vĩnh Bảo: **{summary['officialCandidateCodes']}**
- Tổng mã được audit sau khi hợp nhất nguồn Vĩnh Bảo, quyết định thành phố và ma trận kiểm chứng 51 TTHC: **{summary['auditedCodes']}**
- Mã xuất hiện trong 06 quyết định cập nhật thành phố: **{summary['cityUpdateCodes']}**
- Mã Priority 51 được kiểm chứng pháp lý bổ sung: **{summary['priority51LegalAudited']}**
  - Xác minh current/cấp xã: **{summary['priority51LegalVerifiedCurrent']}**
  - Xác minh bãi bỏ: **{summary['priority51LegalVerifiedRepealed']}**
  - Còn cần xác minh: **{summary['priority51LegalNeedsVerification']}**
- TTHC hiện hành đưa vào tập công khai: **{summary['publishedProcedures']}**
- TTHC loại khỏi tập công khai: **{summary['excludedProcedures']}**
  - Bị bãi bỏ: **{summary['repealedProcedures']}**
  - Đã công bố nhưng chưa đến ngày hiệu lực: **{summary['futureEffectiveProcedures']}**
- TTHC mới được bổ sung từ quyết định thành phố: **{summary['cityNewProcedures']}**
- TTHC hiện có được cập nhật bởi quyết định thành phố: **{summary['cityUpdatedProcedures']}**
- Chưa trích được tên đủ tin cậy: **{summary['unresolvedNameProcedures']}**
- Có formalityId trong Master Data: **{summary['formalityIdMapped']}**
- TTHC trọng điểm đang nằm trong tập public: **{summary['priority51InCurrentMaster']}/{summary['priority51CrosswalkTotal']}**
- Khoảng trống Priority 51 còn lại: **{summary['priority51Gap']}** (mã bãi bỏ không được phục hồi public)
- Được đánh dấu phi địa giới theo nguồn công bố: **{summary['phiDiaGioi']}**

> **Lưu ý phạm vi:** {summary['publishedProcedures']} là số TTHC trong tập niêm yết/tra cứu của Trung tâm PVHCC xã Vĩnh Bảo theo bằng chứng nguồn đã audit. Tập này có thể gồm TTHC cấp tỉnh được tiếp nhận tại Trung tâm PVHCC cấp xã; không được hiểu là toàn bộ đều thuộc thẩm quyền giải quyết của UBND xã.

## Nguồn cập nhật đến 07/09/2026

- Snapshot cổng TTHC xã Vĩnh Bảo và các phụ lục chính thức đã lưu trong `data/source-audit/`.
- Quyết định 3500/QĐ-UBND, 3501/QĐ-UBND, 3508/QĐ-UBND, 3509/QĐ-UBND, 3517/QĐ-UBND, 3523/QĐ-UBND của UBND thành phố Hải Phòng.
- QĐ 3501/QĐ-UBND có hiệu lực từ **01/03/2027**; 02 mã trong quyết định được lưu ở nhóm tương lai, chưa đưa vào tập hiện hành ngày 07/09/2026.
- Quyết định/quy trình nội bộ như 3507, 3521, 3537 không được đưa vào Master Data công khai cho người dân.
- `data/priority-51-legal-verification.json`: ma trận kiểm chứng pháp lý riêng cho 37 mã trọng điểm từng thiếu khỏi Master Data; DVCQG chỉ làm lớp định danh kỹ thuật.

## Quy tắc

1. Không ép danh mục về con số 473 hoặc bất kỳ số lượng mục tiêu định trước nào.
2. Trạng thái hiện hành/bãi bỏ lấy từ bằng chứng công bố chính thức Vĩnh Bảo/Hải Phòng, có ngày nguồn và URL truy vết.
3. Mã bị bãi bỏ được loại khỏi `data/thu-tuc.json` nhưng giữ dấu vết trong `data/master-data-excluded.json` và audit CSV.
4. Mã có quyết định chưa đến ngày hiệu lực được lưu riêng và không hiển thị như TTHC hiện hành.
5. Dữ liệu cũ chỉ bổ sung thuộc tính khi trùng mã; không tự xác nhận hiệu lực.
6. Tên bị lỗi trích PDF được chuẩn hóa theo cùng mã từ dữ liệu kế thừa hoặc Cổng DVCQG; việc này không thay đổi căn cứ xác định trạng thái.
7. formalityId là lớp ánh xạ kỹ thuật. Thiếu UUID không làm thay đổi trạng thái pháp lý; website fallback sang tra cứu DVCQG theo tên/mã.
8. Danh sách 51 TTHC cũ không tự tạo thủ tục public. Mã chỉ được bổ sung khi ma trận kiểm chứng pháp lý có nguồn chính thức Hải Phòng/Vĩnh Bảo và trạng thái `current_official_commune_evidence`; mã `repealed_official_evidence` phải ở excluded.

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
