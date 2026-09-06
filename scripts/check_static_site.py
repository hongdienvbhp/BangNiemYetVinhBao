from __future__ import annotations

import csv
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


index = read("index.html")
app = read("js/app.js")
data_js = read("js/data.js")
read("js/extra-data.js")
read("js/config.js")
read("css/styles.css")
read("sw.js")

# Kiểm tra mọi src/href nội bộ trong HTML đều tồn tại.
for _, ref in re.findall(r'\b(src|href)="([^"]+)"', index):
    if not ref or ref.startswith(("http://", "https://", "tel:", "mailto:", "#", "data:")):
        continue
    rel = urlsplit(ref).path.lstrip("./")
    if rel and not (ROOT / rel).is_file():
        fail(f"Tham chiếu HTML không tồn tại: {ref}")

# Các ID mà app.js sử dụng trực tiếp phải tồn tại trong HTML.
html_ids = set(re.findall(r'\bid="([^"]+)"', index))
js_ids = set(re.findall(r'getElementById\("([^"]+)"\)', app))
missing_ids = sorted(js_ids - html_ids)
if missing_ids:
    fail("ID dùng trong app.js nhưng thiếu ở index.html: " + ", ".join(missing_ids))

# Không cho quay lại các URL DVCQG kiểu cũ dựa trên ma_thu_tuc.
legacy_markers = [
    "dvc-chi-tiet-thu-tuc-dung-chung.html?ma_thu_tuc=",
    "dvc-chi-tiet-thu-tuc-hanh-chinh.html?ma_thu_tuc=",
]
for marker in legacy_markers:
    if marker in app:
        fail(f"Còn URL DVCQG kiểu cũ: {marker}")

required_dvc_markers = [
    "https://dichvucong.gov.vn/thu-tuc-hanh-chinh/",
    "019d2bfd-95d6-778f-889b-e3045003fa5e",
    "019bad30-cd83-76ea-9f9a-bc6cebad4138",
    "019bad30-cd84-7750-aaa5-8100fc7ceef8",
]
for marker in required_dvc_markers:
    if marker not in app:
        fail(f"Thiếu cấu hình DVCQG bắt buộc: {marker}")

# Đếm dữ liệu thô và mã chuẩn hóa theo đúng quy tắc chính của app.js.
codes = re.findall(r'\bma:\s*["\']([^"\']+)["\']', data_js)
normalized = {
    re.sub(r'\.000\.00\.00$', '', re.sub(r'\.H24$', '', code.strip(), flags=re.I), flags=re.I)
    for code in codes
}
if not codes:
    fail("Không tìm thấy mã TTHC trong js/data.js")

# Kiểm tra file mapping mẫu đọc được và có formalityId mẫu.
mapping_path = ROOT / "data/formalityId-mapping-mau.csv"
if not mapping_path.is_file():
    fail("Thiếu data/formalityId-mapping-mau.csv")
else:
    with mapping_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not any(
        row.get("ma") == "2.000942"
        and row.get("formalityId") == "019d2bfd-95d6-778f-889b-e3045003fa5e"
        for row in rows
    ):
        fail("Mapping mẫu 2.000942 chưa đúng")

print(f"Dòng dữ liệu có mã: {len(codes)}")
print(f"Mã chuẩn hóa duy nhất: {len(normalized)}")
print(f"ID HTML: {len(html_ids)}; ID app.js sử dụng: {len(js_ids)}")

if errors:
    print("\nKIỂM TRA KHÔNG ĐẠT:")
    for item in errors:
        print(f"- {item}")
    sys.exit(1)

print("KIỂM TRA STATIC SITE: ĐẠT")
