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
    return path.read_text(encoding="utf-8")


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
city_updates = load_json("data/source-audit/city-updates-20260907.json")

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
if 'cacheKey: "tthc_vinhbao_v3"' not in config:
    fail("Cache key chưa nâng lên v3")
for marker in ['js/data.js', 'js/master-data-fallback.js', 'js/app.js']:
    if marker not in index:
        fail(f"Thiếu script runtime trong index.html: {marker}")
if not (index.find('js/data.js') < index.find('js/master-data-fallback.js') < index.find('js/app.js')):
    fail("Thứ tự script fallback không đúng")
if "./js/master-data-fallback.js" not in sw or "tthc-vinhbao-v3" not in sw:
    fail("Service Worker chưa cache fallback hoặc chưa nâng cache v3")

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
if summary.get("publishedProcedures") != len(rows):
    fail("summary.publishedProcedures không khớp số dòng public")
if summary.get("excludedProcedures") != len(excluded):
    fail("summary.excludedProcedures không khớp số dòng loại trừ")
if summary.get("auditedCodes") != len(rows) + len(excluded):
    fail("summary.auditedCodes không bằng public + excluded")
if master.get("sourceSnapshotDate") != "2026-09-07":
    fail("Master Data chưa chốt snapshot 2026-09-07")

bad_names = []
for row in rows:
    code = row.get("ma") or "?"
    name = str(row.get("ten") or "").strip()
    field = str(row.get("linhVuc") or "").strip()
    status = str(row.get("verificationStatus") or "")
    if not name:
        bad_names.append(f"{code}: thiếu tên")
    if len(name) > 200 or re.search(r"trình tự thực hiện|bước 1|Thủ tục Thủ tục", name, re.I):
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

# 6 quyết định công khai mới phải còn đầy đủ trong snapshot audit.
decision_nos = {str(x.get("decisionNo") or "") for x in city_updates.get("decisions", [])}
for qd in {"3500/QĐ-UBND", "3501/QĐ-UBND", "3508/QĐ-UBND", "3509/QĐ-UBND", "3517/QĐ-UBND", "3523/QĐ-UBND"}:
    if qd not in decision_nos:
        fail(f"Thiếu quyết định trong source audit: {qd}")

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
