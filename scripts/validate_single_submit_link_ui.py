#!/usr/bin/env python3
from pathlib import Path

APP=Path(__file__).resolve().parents[1]/"js/app.js"
text=APP.read_text(encoding="utf-8")
start=text.find("  function openDetail(tt, trigger = null) {")
end=text.find("\n  function closeDetail()",start)
if start<0 or end<0:
    raise SystemExit("Không tìm thấy openDetail")
block=text[start:end]
errors=[]
anchor_count=block.count("<a ")
button_count=block.count('<a class="btn-dvc"')
if button_count != 1:
    errors.append(f"openDetail phải có đúng 1 link nộp hồ sơ, hiện {button_count}")
if anchor_count != 1:
    errors.append(f"openDetail phải có đúng 1 thẻ <a>, hiện {anchor_count}")
for banned in (
    "Xem chi tiết TTHC trên Cổng DVC Quốc gia",
    "Tra cứu TTHC trên Cổng DVC Quốc gia",
    "Danh mục TTHC Quốc gia",
    "Cổng Hải Phòng:",
    "dvcTraCuu",
    "dvcTthcHome",
):
    if banned in block:
        errors.append(f"UI còn link/phần tử DVC phụ: {banned}")
if "NỘP HỒ SƠ TRỰC TUYẾN" not in block:
    errors.append("Thiếu nhãn NỘP HỒ SƠ TRỰC TUYẾN")
if 'href="${esc(tt.dvcNop)}"' not in block:
    errors.append("Nút nộp hồ sơ không dùng tt.dvcNop canonical")
if errors:
    raise SystemExit("\n".join(errors))
print({"status":"PASS","detail_external_links":1})
