from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
errors: list[str] = []


def fail(message: str) -> None:
    errors.append(message)


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.is_file():
        fail(f"Thiếu file: {rel}")
        return ""
    return path.read_text(encoding="utf-8-sig")


def load_json(rel: str) -> dict:
    text = read(rel)
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        fail(f"JSON không hợp lệ {rel}: {exc}")
        return {}


index = read("index.html")
app = read("js/app.js")
data_js = read("js/data.js")
fallback_js = read("js/master-data-fallback.js")
config = read("js/config.js")
read("js/extra-data.js")
read("css/styles.css")
sw = read("sw.js")
master = load_json("data/thu-tuc.json")
excluded_payload = load_json("data/master-data-excluded.json")
city_updates = load_json("data/source-audit/city-updates-current.json")
decision_manifest = load_json("data/source-audit/official-decision-manifest.json")
source_index = load_json("data/source-audit/official-source-index.json")
priority51_payload = load_json("data/priority-51-crosswalk.json")
priority51_legal_payload = load_json("data/priority-51-legal-verification.json")
dvcqg_live_payload = load_json("data/source-audit/dvcqg-live-verification-current.json")

# Thẻ thủ tục phải thao tác được chỉ bằng bàn phím và trả focus sau khi đóng.
keyboard_markers = {
    'tabindex="0" role="button"': "Thẻ thủ tục thiếu semantics/focus bàn phím",
    'aria-label="Xem chi tiết: ${esc(tt.ten)}"': "Thẻ thủ tục thiếu tên truy cập",
    'thuTucList.addEventListener("keydown"': "Thiếu xử lý bàn phím cho danh sách thủ tục",
    'e.key !== "Enter" && e.key !== " "': "Thiếu kích hoạt bằng Enter/Space",
    'trigger.isConnected) trigger.focus()': "Thiếu khôi phục focus sau khi đóng chi tiết",
}
for marker, message in keyboard_markers.items():
    if marker not in app:
        fail(message)

# Mọi src/href nội bộ trong HTML phải tồn tại.
for _, ref in re.findall(r'\b(src|href)="([^"]+)"', index):
    if not ref or ref.startswith(("http://", "https://", "tel:", "mailto:", "#", "data:")):
        continue
    rel = urlsplit(ref).path.lstrip("./")
    if rel and not (ROOT / rel).is_file():
        fail(f"Tham chiếu HTML không tồn tại: {ref}")

# Các ID mà app.js dùng trực tiếp phải tồn tại trong HTML.
html_ids = set(re.findall(r'\bid="([^"]+)"', index))
js_ids = set(re.findall(r'getElementById\("([^"]+)"\)', app))
missing_ids = sorted(js_ids - html_ids)
if missing_ids:
    fail("ID dùng trong app.js nhưng thiếu ở index.html: " + ", ".join(missing_ids))

# Không cho quay lại URL DVCQG kiểu cũ.
for marker in [
    "dvc-chi-tiet-thu-tuc-dung-chung.html?ma_thu_tuc=",
    "dvc-chi-tiet-thu-tuc-hanh-chinh.html?ma_thu_tuc=",
]:
    if marker in app:
        fail(f"Còn URL DVCQG kiểu cũ: {marker}")

for marker in [
    "https://dichvucong.gov.vn/thu-tuc-hanh-chinh/",
    "019d2bfd-95d6-778f-889b-e3045003fa5e",
    "019bad30-cd83-76ea-9f9a-bc6cebad4138",
    "019bad30-cd84-7750-aaa5-8100fc7ceef8",
]:
    if marker not in app:
        fail(f"Thiếu cấu hình DVCQG bắt buộc: {marker}")

# Runtime phải ưu tiên JSON và có fallback cùng dữ liệu.
if 'remoteJsonUrl: "data/thu-tuc.json"' not in config:
    fail("Chưa bật data/thu-tuc.json trong js/config.js")
cache_match = re.search(r'cacheKey:\s*"tthc_vinhbao_v(\d+)"', config)
if not cache_match:
    fail("Không xác định được version cache trong js/config.js")
    cache_version = ""
else:
    cache_version = cache_match.group(1)
for marker in ['js/data.js', 'js/master-data-fallback.js', 'js/app.js']:
    if marker not in index:
        fail(f"Thiếu script runtime trong index.html: {marker}")
if not (index.find('js/data.js') < index.find('js/master-data-fallback.js') < index.find('js/app.js')):
    fail("Thứ tự script fallback không đúng")
sw_cache_match = re.search(r'const CACHE = "tthc-vinhbao-v(\d+)"', sw)
if "./js/master-data-fallback.js" not in sw:
    fail("Service Worker chưa cache master-data-fallback.js")
elif not sw_cache_match:
    fail("Không xác định được version cache trong Service Worker")
elif cache_version and sw_cache_match.group(1) != cache_version:
    fail(f"Version cache lệch nhau: config v{cache_version}, service worker v{sw_cache_match.group(1)}")

# Application shell phải ưu tiên mạng để người dùng nhận bản deploy mới.
for marker, message in {
    'event.request.mode === "navigate" || isCodeAsset': "Service Worker chưa network-first cho điều hướng và tài sản code",
    '["document", "script", "style"].includes(event.request.destination)': "Service Worker thiếu danh sách tài sản code cần làm mới",
    'caches.match(event.request, { ignoreSearch: true })': "Service Worker thiếu fallback offline bỏ qua cache-buster",
}.items():
    if marker not in sw:
        fail(message)

# Master Data.
rows = master.get("thuTuc") if isinstance(master, dict) else None
summary = master.get("summary") if isinstance(master, dict) else None
if not isinstance(rows, list):
    fail("data/thu-tuc.json thiếu mảng thuTuc")
    rows = []
if not isinstance(summary, dict):
    fail("data/thu-tuc.json thiếu summary")
    summary = {}
excluded = excluded_payload.get("rows") if isinstance(excluded_payload, dict) else None
if not isinstance(excluded, list):
    fail("data/master-data-excluded.json thiếu rows")
    excluded = []

codes = [str(row.get("ma") or "").strip() for row in rows]
code_set = set(codes)
if "" in code_set:
    fail("Có TTHC public thiếu mã")
if len(codes) != len(code_set):
    fail("Có mã TTHC trùng trong Master Data public")

# QĐ 3626: Phụ lục B có đúng bốn TTHC cấp xã; Phụ lục C dùng chung không
# được kế thừa nhầm ngữ cảnh cấp xã vào bảng niêm yết phục vụ công dân.
qd3626_expected = {
    "2.001909": "TIẾP CÔNG DÂN",
    "2.001801": "XỬ LÝ ĐƠN",
    "2.002409": "KHIẾU NẠI",
    "2.002396": "TỐ CÁO",
}
qd3626_rows = [
    item for item in city_updates.get("rows", [])
    if item.get("decisionNo") == "3626/QĐ-UBND"
]
qd3626_commune = {
    str(item.get("code") or ""): str(item.get("field") or "")
    for item in qd3626_rows
    if item.get("communeReceptionEvidence")
}
if qd3626_commune != qd3626_expected:
    fail(f"QĐ 3626 phải có đúng bốn TTHC cấp xã: {qd3626_commune}")
if not set(qd3626_expected).issubset(code_set):
    fail("Master Data chưa công bố đủ bốn TTHC cấp xã của QĐ 3626")
for shared_code in {"2.002401", "2.002403"}:
    shared = next((item for item in qd3626_rows if item.get("code") == shared_code), None)
    if shared and shared.get("communeReceptionEvidence"):
        fail(f"QĐ 3626: thủ tục dùng chung {shared_code} bị gắn nhầm cấp xã")

if summary.get("publishedProcedures") != len(rows):
    fail("summary.publishedProcedures không khớp số dòng public")
if summary.get("excludedProcedures") != len(excluded):
    fail("summary.excludedProcedures không khớp số dòng loại trừ")
if summary.get("auditedCodes") != len(rows) + len(excluded):
    fail("summary.auditedCodes không bằng public + excluded")
snapshot_date = str(master.get("sourceSnapshotDate") or "")
if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", snapshot_date):
    fail("Master Data thiếu sourceSnapshotDate hợp lệ")
city_as_of = str(city_updates.get("asOf") or "")
if city_as_of and snapshot_date != city_as_of:
    fail(f"Master Data và city-updates lệch snapshot: master={snapshot_date}, city={city_as_of}")

bad_names = []
for row in rows:
    code = row.get("ma") or "?"
    name = str(row.get("ten") or "").strip()
    field = str(row.get("linhVuc") or "").strip()
    status = str(row.get("verificationStatus") or "")
    if not name:
        bad_names.append(f"{code}: thiếu tên")
    if len(name) > 500 or re.search(r"trình tự thực hiện|bước 1|Thủ tục Thủ tục", name, re.I):
        bad_names.append(f"{code}: tên có dấu hiệu trích sai")
    if name.endswith(":") or name.count("(") != name.count(")") or "|" in name:
        bad_names.append(f"{code}: tên chưa sạch")
    if re.search(r" [bcdfghjklmnpqrstvxđ] [a-zà-ỹ]{2,}", name, re.I):
        bad_names.append(f"{code}: tên còn lỗi tách ký tự")
    if not field or field.startswith("CHƯA XÁC MINH"):
        fail(f"{code}: lĩnh vực chưa xác định")
    if "repealed" in status or "future_effective" in status:
        fail(f"{code}: trạng thái không được phép nằm trong public: {status}")
    if not row.get("daXacMinh"):
        fail(f"{code}: public nhưng daXacMinh=false")
    if not row.get("sourceEvidence"):
        fail(f"{code}: thiếu sourceEvidence")
if bad_names:
    fail("Tên TTHC chưa đạt: " + "; ".join(bad_names[:10]))

excluded_by_code = {str(row.get("ma") or "").strip(): row for row in excluded}
for code in ["1.003596", "1.014311", "1.014116", "2.001034", "2.002287"]:
    if code in code_set:
        fail(f"Mã đã bãi bỏ vẫn nằm trong public: {code}")
    if code not in excluded_by_code:
        fail(f"Thiếu dấu vết mã đã bãi bỏ trong excluded: {code}")
for code in ["1.013860", "1.013864"]:
    if code in code_set:
        fail(f"Mã chưa đến hiệu lực vẫn nằm trong public: {code}")
    if "future_effective" not in str(excluded_by_code.get(code, {}).get("verificationStatus", "")):
        fail(f"Mã tương lai chưa được đánh dấu đúng: {code}")
for code in ["1.000302", "1.000321", "3.000242", "1.013781", "3.000574", "1.014111"]:
    if code not in code_set:
        fail(f"Thiếu TTHC hiện hành từ quyết định mới: {code}")

# Các quyết định công khai nền phải còn đầy đủ trong snapshot audit.
decision_nos = {str(x.get("decisionNo") or "") for x in city_updates.get("decisions", [])}
for qd in {"3500/QĐ-UBND", "3501/QĐ-UBND", "3508/QĐ-UBND", "3509/QĐ-UBND", "3517/QĐ-UBND", "3523/QĐ-UBND"}:
    if qd not in decision_nos:
        fail(f"Thiếu quyết định trong source audit: {qd}")

# QĐ 3582 có mã cũ và mã thay thế nằm chung hàng; phải giữ đúng hai phía.
city_rows_by_code = {
    str(row.get("code") or ""): row
    for row in city_updates.get("rows", [])
    if row.get("decisionNo") == "3582/QĐ-UBND"
}
for code in {"2.001023", "2.002621", "2.000986", "2.002622"}:
    if city_rows_by_code.get(code, {}).get("sectionStatus") != "repealed":
        fail(f"{code}: mã bị thay thế theo QĐ 3582 chưa được loại đúng")
for code in {"3.000722", "2.002913"}:
    if city_rows_by_code.get(code, {}).get("sectionStatus") != "new":
        fail(f"{code}: mã thay thế theo QĐ 3582 chưa được ghi nhận đúng")

# Manifest/index là cổng provenance của pipeline tự động.
manifest_rows = decision_manifest.get("decisions") if isinstance(decision_manifest, dict) else None
if not isinstance(manifest_rows, list):
    fail("official-decision-manifest.json thiếu decisions")
    manifest_rows = []
index_rows = source_index.get("articles") if isinstance(source_index, dict) else None
if not isinstance(index_rows, list):
    fail("official-source-index.json thiếu articles")
    index_rows = []

manifest_public = [row for row in manifest_rows if row.get("classification") == "public_tthc"]
manifest_internal = [row for row in manifest_rows if row.get("classification") == "internal_process"]
manifest_nos = [str(row.get("decisionNo") or "") for row in manifest_rows]
if len(manifest_nos) != len(set(manifest_nos)):
    fail("Manifest có decisionNo trùng")
for row in manifest_public:
    qd = str(row.get("decisionNo") or "?")
    for field_name in ["decisionDate", "articleUrl", "pdfUrl", "filePath"]:
        if not row.get(field_name):
            fail(f"{qd}: manifest public thiếu {field_name}")
    file_path = str(row.get("filePath") or "")
    if file_path and not (ROOT / file_path).is_file():
        fail(f"{qd}: manifest trỏ tới PDF không tồn tại: {file_path}")
for row in manifest_internal:
    qd = str(row.get("decisionNo") or "")
    if qd and qd in decision_nos:
        fail(f"Quyết định nội bộ bị đưa vào city-updates public: {qd}")

article_urls = [str(row.get("articleUrl") or "").rstrip("/") for row in index_rows if row.get("articleUrl")]
if len(article_urls) != len(set(article_urls)):
    fail("official-source-index.json có articleUrl trùng")
needs_review_index = [row for row in index_rows if row.get("classification") == "needs_review" or str(row.get("status") or "").startswith(("missing_", "unclassified_", "article_fetch_failed", "pdf_download_failed"))]
if needs_review_index:
    fail(f"Nguồn mới cần rà soát trước khi merge: {len(needs_review_index)} bài")
if int(summary.get("cityNeedsReviewRows") or 0) > 0:
    fail(f"Có {summary.get('cityNeedsReviewRows')} dòng quyết định thành phố chưa đủ điều kiện tự động áp dụng")

# Crosswalk 51 TTHC trọng điểm chỉ là lớp kỹ thuật, không phải căn cứ hiệu lực.
priority51_rows = priority51_payload.get("items") if isinstance(priority51_payload, dict) else None
if not isinstance(priority51_rows, list):
    fail("data/priority-51-crosswalk.json thiếu items")
    priority51_rows = []

p51_ordinals = [row.get("ordinal") for row in priority51_rows]
p51_codes = [str(row.get("code") or "").strip() for row in priority51_rows]
p51_ids = [str(row.get("formalityId") or "").strip().lower() for row in priority51_rows if row.get("formalityId")]
p51_fallback_codes = {
    str(row.get("code") or "").strip()
    for row in priority51_rows
    if row.get("mappingMode") == "keyword_fallback"
}
if len(priority51_rows) != 51:
    fail(f"Crosswalk trọng điểm phải có 51 dòng, hiện có {len(priority51_rows)}")
if sorted(x for x in p51_ordinals if isinstance(x, int)) != list(range(1, 52)):
    fail("Crosswalk trọng điểm thiếu/trùng STT 1..51")
if len(p51_codes) != len(set(p51_codes)) or "" in p51_codes:
    fail("Crosswalk trọng điểm có mã trống hoặc trùng")
if len(p51_ids) != 48 or len(p51_ids) != len(set(p51_ids)):
    fail(f"Crosswalk phải có 48 formalityId trực tiếp duy nhất, hiện có {len(p51_ids)}/{len(set(p51_ids))}")
uuid_re = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
for fid in p51_ids:
    if not uuid_re.fullmatch(fid):
        fail(f"formalityId trọng điểm không hợp lệ: {fid}")
expected_fallback = {"2.001283", "2.000720", "2.001009"}
if p51_fallback_codes != expected_fallback:
    fail(f"Tập keyword fallback trọng điểm không đúng: {sorted(p51_fallback_codes)}")
for row in priority51_rows:
    code = str(row.get("code") or "").strip()
    url = str(row.get("dvcUrl") or "")
    if not url.startswith("https://dichvucong.gov.vn/"):
        fail(f"{code}: URL crosswalk không thuộc DVCQG")
    if row.get("legalStatusAssertion") != "none_from_priority_crosswalk":
        fail(f"{code}: crosswalk không được khẳng định trạng thái pháp lý")

p51_by_code = {str(row.get("code") or "").strip(): row for row in priority51_rows}
master_by_code = {str(row.get("ma") or "").strip(): row for row in rows}
excluded_by_code = {str(row.get("ma") or "").strip(): row for row in excluded}
p51_in_master = sorted(set(p51_by_code) & code_set)

# Crosswalk phải được reconcile từ canonical hiện hành, không giữ snapshot Master riêng.
p51_summary = priority51_payload.get("summary") or {}
if p51_summary.get("inCurrentMaster") != len(p51_in_master):
    fail("Crosswalk summary.inCurrentMaster lệch canonical")
if p51_summary.get("missingFromCurrentMaster") != len(set(p51_by_code) - code_set):
    fail("Crosswalk summary.missingFromCurrentMaster lệch canonical")
if priority51_payload.get("canonicalContract") != "data/thu-tuc.json":
    fail("Crosswalk phải khai báo data/thu-tuc.json là canonical contract")
if priority51_payload.get("canonicalDatasetVersion") != master.get("dataset_version"):
    fail("Crosswalk canonicalDatasetVersion lệch canonical")
if priority51_payload.get("canonicalSourceCommit") != master.get("source_commit"):
    fail("Crosswalk canonicalSourceCommit lệch canonical")
for code, cross in p51_by_code.items():
    master_row = master_by_code.get(code)
    if master_row:
        if cross.get("inCurrentMaster") is not True:
            fail(f"{code}: crosswalk chưa đánh dấu có trong canonical")
        if cross.get("currentMasterName") != master_row.get("ten"):
            fail(f"{code}: currentMasterName lệch canonical")
        if cross.get("exactNameMatch") is not (cross.get("name") == master_row.get("ten")):
            fail(f"{code}: exactNameMatch không phản ánh đúng chênh lệch tên")
    else:
        if cross.get("inCurrentMaster") is not False:
            fail(f"{code}: crosswalk phải đánh dấu không có trong canonical")
        if cross.get("currentMasterName") is not None or cross.get("exactNameMatch") is not None:
            fail(f"{code}: mã ngoài canonical không được giữ currentMasterName/exactNameMatch")

# Manifest DVCQG live chỉ xác minh identity/display kỹ thuật, không quyết định hiệu lực pháp lý.
live_rows = dvcqg_live_payload.get("items") if isinstance(dvcqg_live_payload, dict) else None
live_totals = dvcqg_live_payload.get("totals") if isinstance(dvcqg_live_payload, dict) else {}
if dvcqg_live_payload.get("format") != "DVCQG_LIVE_READONLY_VERIFICATION":
    fail("Manifest DVCQG live sai format")
if not isinstance(live_rows, list) or len(live_rows) != 51:
    fail("Manifest DVCQG live phải có 51 dòng")
    live_rows = []
live_by_code = {str(row.get("code") or "").strip(): row for row in live_rows}
if set(live_by_code) != set(p51_by_code):
    fail("Manifest DVCQG live lệch tập 51 mã crosswalk")
live_verified = sum(
    1
    for row in live_rows
    if row.get("result") in {"VERIFIED_VISIBLE_IDENTITY", "VERIFIED_VISIBLE_IDENTITY_AND_AGENCY"}
)
live_unresolved = sum(1 for row in live_rows if row.get("result") == "UNRESOLVED_VISIBLE_IDENTITY")
live_waf = sum(1 for row in live_rows if row.get("result") == "WAF_REJECTED")
if live_verified != 36 or live_unresolved != 15 or live_waf != 0:
    fail(f"DVCQG live baseline phải là 36 verified / 15 unresolved / 0 WAF, hiện {live_verified}/{live_unresolved}/{live_waf}")
if live_totals.get("items") != 51 or live_totals.get("unresolved") != live_unresolved or live_totals.get("waf_rejected") != live_waf:
    fail("Manifest DVCQG live totals không tự đối chiếu")
if p51_summary.get("liveVerifiedIdentity") != live_verified:
    fail("Crosswalk summary.liveVerifiedIdentity lệch manifest")
if p51_summary.get("liveUnresolved") != live_unresolved:
    fail("Crosswalk summary.liveUnresolved lệch manifest")
if p51_summary.get("liveWafRejected") != live_waf:
    fail("Crosswalk summary.liveWafRejected lệch manifest")
if priority51_payload.get("liveVerificationManifest") != "data/source-audit/dvcqg-live-verification-current.json":
    fail("Crosswalk thiếu tham chiếu manifest DVCQG live")
for code, cross in p51_by_code.items():
    live_row = live_by_code.get(code) or {}
    if cross.get("liveVerificationResult") != live_row.get("result"):
        fail(f"{code}: liveVerificationResult lệch manifest")
    if bool(cross.get("liveNameVisible")) != bool(live_row.get("name_visible")):
        fail(f"{code}: liveNameVisible lệch manifest")

# Ma trận kiểm chứng pháp lý của 37 mã từng thiếu ở bước trước.
legal_rows = priority51_legal_payload.get("rows") if isinstance(priority51_legal_payload, dict) else None
if not isinstance(legal_rows, list):
    fail("data/priority-51-legal-verification.json thiếu rows")
    legal_rows = []
legal_codes = [str(row.get("code") or "").strip() for row in legal_rows]
if len(legal_rows) != 37 or len(legal_codes) != len(set(legal_codes)) or "" in legal_codes:
    fail(f"Ma trận pháp lý phải có 37 mã duy nhất, hiện {len(legal_rows)}/{len(set(legal_codes))}")
legal_current = [row for row in legal_rows if row.get("legalStatus") == "current_official_commune_evidence"]
legal_repealed = [row for row in legal_rows if row.get("legalStatus") == "repealed_official_evidence"]
legal_other = [row for row in legal_rows if row.get("legalStatus") not in {"current_official_commune_evidence", "repealed_official_evidence"}]
if len(legal_current) != 36 or len(legal_repealed) != 1 or legal_other:
    fail(f"Ma trận pháp lý phải là 36 current + 1 repealed + 0 pending, hiện {len(legal_current)}/{len(legal_repealed)}/{len(legal_other)}")
if {str(row.get("code") or "") for row in legal_repealed} != {"2.001009"}:
    fail("Mã bãi bỏ trong ma trận 51 phải là 2.001009")

source_validation = priority51_legal_payload.get("sourceValidation") or {}
if source_validation.get("uniquePrimaryOfficialSources") != 11:
    fail("Ma trận pháp lý phải ghi nhận 11 nguồn primary chính thức")
if source_validation.get("currentPrimarySourcesChecked") != 10 or source_validation.get("currentPrimarySourcesContainingAssignedCodes") != 10:
    fail("10 nguồn primary của nhóm current phải được kiểm tra và chứa đúng mã đã gán")
repeal_validation = source_validation.get("repealedCodeIndependentVerification") or {}
if repeal_validation.get("code") != "2.001009" or repeal_validation.get("decisionNo") != "4517/QĐ-UBND":
    fail("Thiếu kiểm chứng độc lập QĐ 4517/QĐ-UBND cho mã 2.001009")

allowed_legal_hosts = {"cdn.haiphong.gov.vn", "vinhbao.haiphong.gov.vn", "haiphong.gov.vn"}
for row in legal_rows:
    code = str(row.get("code") or "").strip()
    if row.get("legalStatusBasis") != "official_haiphong_source":
        fail(f"{code}: trạng thái pháp lý không được gắn nguồn chính thức Hải Phòng")
    if row.get("dvcqgRole") != "technical_identity_only":
        fail(f"{code}: DVCQG phải chỉ là lớp định danh kỹ thuật")
    sources = row.get("sources") or []
    if not sources:
        fail(f"{code}: ma trận pháp lý thiếu nguồn")
    for source in sources:
        url = str(source.get("url") or "")
        host = urlsplit(url).hostname or ""
        if host not in allowed_legal_hosts:
            fail(f"{code}: nguồn trạng thái pháp lý không thuộc hệ thống chính thức Hải Phòng: {url}")

for item in legal_current:
    code = str(item.get("code") or "").strip()
    if code not in code_set:
        fail(f"{code}: đã xác minh current cấp xã nhưng thiếu khỏi Master public")
    row = master_by_code.get(code, {})
    if row.get("priority51LegalVerificationStatus") != "current_official_commune_evidence":
        fail(f"{code}: Master thiếu trạng thái kiểm chứng pháp lý Priority 51")
    if row.get("priority51") is not True:
        fail(f"{code}: thủ tục trọng điểm current chưa được đánh priority51")
    if not row.get("sourceArticleUrl"):
        fail(f"{code}: bản ghi current thiếu sourceArticleUrl")

for item in legal_repealed:
    code = str(item.get("code") or "").strip()
    if code in code_set:
        fail(f"{code}: thủ tục đã bãi bỏ vẫn còn trong Master public")
    row = excluded_by_code.get(code)
    if not row or row.get("verificationStatus") != "repealed_official_evidence":
        fail(f"{code}: thủ tục bãi bỏ chưa được lưu đúng trong excluded")

if len(p51_in_master) != 50:
    fail(f"Sau kiểm chứng pháp lý phải có 50/51 mã trọng điểm trong Master public, hiện {len(p51_in_master)}")
if set(p51_by_code) - code_set != {"2.001009"}:
    fail(f"Sau kiểm chứng, khoảng trống Priority 51 chỉ được là mã bãi bỏ 2.001009: {sorted(set(p51_by_code) - code_set)}")
for code in p51_in_master:
    cross = p51_by_code[code]
    master_row = master_by_code[code]
    if master_row.get("priority51") is not True:
        fail(f"{code}: có trong crosswalk nhưng Master chưa đánh priority51")
    if master_row.get("priority51Ordinal") != cross.get("ordinal"):
        fail(f"{code}: priority51Ordinal lệch crosswalk")
    fid = str(cross.get("formalityId") or "")
    if fid and master_row.get("formalityId") != fid:
        fail(f"{code}: formalityId Master lệch crosswalk")
if summary.get("priority51CrosswalkTotal") != 51:
    fail("summary.priority51CrosswalkTotal phải bằng 51")
if summary.get("priority51InCurrentMaster") != 50:
    fail("summary.priority51InCurrentMaster phải bằng 50")
if summary.get("priority51Gap") != 1:
    fail("summary.priority51Gap phải bằng 1 (mã bãi bỏ 2.001009)")
if summary.get("formalityIdMapped") != 48:
    fail(f"Snapshot này phải có 48 formalityId trong Master, hiện {summary.get('formalityIdMapped')}")
if summary.get("priority51LegalAudited") != 37:
    fail("summary.priority51LegalAudited phải bằng 37")
if summary.get("priority51LegalVerifiedCurrent") != 36:
    fail("summary.priority51LegalVerifiedCurrent phải bằng 36")
if summary.get("priority51LegalVerifiedRepealed") != 1:
    fail("summary.priority51LegalVerifiedRepealed phải bằng 1")
if summary.get("priority51LegalNeedsVerification") != 0:
    fail("summary.priority51LegalNeedsVerification phải bằng 0")
if summary.get("priority51LegalAddedCurrent") != 36:
    fail("summary.priority51LegalAddedCurrent phải bằng 36 ở snapshot này")
if summary.get("priority51LegalSupersededByNewerEvidence") != 0:
    fail("Có bằng chứng chính thức mới hơn ma trận Priority 51; phải rà soát lại snapshot pháp lý trước khi merge")

# Fallback phải chứa chính xác tập mã public của JSON.
fallback_codes = set(re.findall(r'"ma":"([^"]+)"', fallback_js))
if fallback_codes != code_set:
    fail(f"Fallback và JSON lệch tập mã: json={len(code_set)}, fallback={len(fallback_codes)}")
if "window.TTHC_MASTER_DATA=" not in fallback_js:
    fail("Fallback thiếu window.TTHC_MASTER_DATA")

# Dữ liệu legacy chỉ còn là nguồn bổ sung metadata/fallback lịch sử.
legacy_codes = re.findall(r'\bma:\s*["\']([^"\']+)["\']', data_js)
if not legacy_codes:
    fail("Không đọc được dữ liệu legacy js/data.js")

# Mapping mẫu đã xác minh trước đây vẫn phải giữ nguyên.
mapping_path = ROOT / "data/formalityId-mapping-mau.csv"
if not mapping_path.is_file():
    fail("Thiếu data/formalityId-mapping-mau.csv")
else:
    with mapping_path.open("r", encoding="utf-8", newline="") as handle:
        mapping_rows = list(csv.DictReader(handle))
    if not any(
        row.get("ma") == "2.000942"
        and row.get("formalityId") == "019d2bfd-95d6-778f-889b-e3045003fa5e"
        for row in mapping_rows
    ):
        fail("Mapping mẫu 2.000942 chưa đúng")

print(f"Master Data public: {len(rows)}")
print(f"Excluded: {len(excluded)}; audited: {summary.get('auditedCodes')}")
print(f"Legacy rows: {len(legacy_codes)}")
print(f"ID HTML: {len(html_ids)}; ID app.js sử dụng: {len(js_ids)}")
print(f"formalityId trong Master Data: {summary.get('formalityIdMapped', 0)}")

if errors:
    print("\nKIỂM TRA KHÔNG ĐẠT:")
    for item in errors:
        print(f"- {item}")
    sys.exit(1)

print("KIỂM TRA STATIC SITE + MASTER DATA: ĐẠT")
