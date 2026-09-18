# Bảng Niêm Yết Thủ Tục Hành Chính — UBND xã Vĩnh Bảo

Trang web phục vụ niêm yết, tra cứu thủ tục hành chính liên quan hoạt động tiếp nhận tại Trung tâm Phục vụ hành chính công xã Vĩnh Bảo, thành phố Hải Phòng.

> **Trạng thái dữ liệu chốt đến 07/09/2026:** đã audit **245 mã**, trong đó **229 TTHC hiện hành** được đưa vào tập công khai, **14 mã bị bãi bỏ** và **02 mã đã công bố nhưng chưa đến ngày hiệu lực**. Tập 229 có thể gồm TTHC cấp tỉnh được tiếp nhận tại Trung tâm PVHCC cấp xã; không đồng nhất với số TTHC thuộc thẩm quyền giải quyết của UBND xã. Trong 51 TTHC trọng điểm, **50 mã đang public** và **01 mã (`2.001009`) được giữ ở excluded do có bằng chứng bãi bỏ chính thức**.

Con số **473 TTHC** từng xuất hiện trong báo cáo cũ không tái lập được từ lịch sử Git và **không được dùng làm mục tiêu dữ liệu**.

## Chạy local

```bash
git clone https://github.com/hongdienvbhp/BangNiemYetVinhBao.git
cd BangNiemYetVinhBao
python -m http.server 8080
# http://localhost:8080
```

## Nguồn dữ liệu runtime

- `data/thu-tuc.json`: Master Data public, được ưu tiên khi tải trang.
- `js/master-data-fallback.js`: fallback sinh tự động từ cùng Master Data.
- `js/data.js`: dữ liệu legacy để đối chiếu/bổ sung metadata; không còn là danh mục hiện hành chính.
- `data/master-data-audit.csv`: toàn bộ mã đã audit và URL nguồn.
- `data/master-data-excluded.json`: mã bãi bỏ hoặc chưa đến ngày hiệu lực.
- `data/BAO_CAO_MASTER_DATA_HIEN_HANH.md`: báo cáo Master Data được pipeline tái tạo theo snapshot đang áp dụng.
- `data/priority-51-crosswalk.json`: crosswalk kỹ thuật cho 51 TTHC trọng điểm; không phải căn cứ hiệu lực pháp lý.
- `data/priority-51-legal-verification.json`: ma trận kiểm chứng pháp lý cho 37 mã trọng điểm từng thiếu khỏi Master Data; 36 current cấp xã, 01 bãi bỏ.
- `data/BAO_CAO_51_TTHC_TRONG_DIEM_2026-09-07.md`: báo cáo 51 TTHC, UUID và kết quả kiểm chứng pháp lý.
- `data/source-audit/`: snapshot nguồn, bằng chứng và PDF quyết định chính thức.

## Nguồn kiểm chứng đến 07/09/2026

Master Data kết hợp snapshot công bố TTHC trên cổng xã Vĩnh Bảo với các quyết định mới của UBND thành phố Hải Phòng: `3500/QĐ-UBND`, `3501/QĐ-UBND`, `3508/QĐ-UBND`, `3509/QĐ-UBND`, `3517/QĐ-UBND`, `3523/QĐ-UBND`.

`3501/QĐ-UBND` có hiệu lực từ **01/03/2027**, nên 02 mã tương ứng được giữ ở nhóm tương lai và chưa hiển thị như TTHC hiện hành ngày 07/09/2026. Các quyết định/quy trình nội bộ không phải TTHC công khai cho người dân không được đưa vào Master Data public.

## Tự động cập nhật nguồn chính thức

Pipeline tự động được tổ chức theo chuỗi:

`official-source-config → source-index → decision-manifest → PDF/hash → city-updates-current + priority-51-legal-verification → Master Data → delta → CI`

Các file/chương trình chính:

- `data/source-audit/official-source-config.json`: danh sách nguồn chính thức được phép quét.
- `data/source-audit/official-source-index.json`: chỉ mục URL bài/quyết định đã quan sát; ngăn quét lại lịch sử như dữ liệu mới.
- `data/source-audit/official-decision-manifest.json`: manifest quyết định, phân biệt `public_tthc` và `internal_process`.
- `scripts/update_official_sources.py`: phát hiện bài mới, trích metadata, tải PDF chính thức và lưu SHA-256.
- `scripts/extract_city_updates.py`: đọc PDF từ manifest, xác định mã TTHC, trạng thái mục, tiếp nhận cấp xã và điều khoản hiệu lực.
- `scripts/build_master_data.py`: hợp nhất với snapshot Vĩnh Bảo, áp dụng nguyên tắc quyết định mới hơn và sinh Master Data.
- `scripts/build_master_delta.py`: so sánh trước/sau khi có thay đổi.
- `.github/workflows/official-data-update.yml`: chạy **07:30 hằng ngày giờ Việt Nam** và có `workflow_dispatch` để chạy thủ công.

Quy tắc tự động:

1. Lần đầu chỉ ghi nhận baseline URL, không nhập lại quyết định lịch sử.
2. Quyết định nội bộ được lưu dấu vết nhưng không đưa vào Master Data public.
3. Quyết định công khai mới chỉ được tải/đưa vào extractor khi có PDF chính thức.
4. Quyết định tự phát hiện nhưng chưa xác định được điều khoản hiệu lực hoặc lĩnh vực bị đánh dấu `needs_*`; builder không được phép áp dụng vào tập public và CI sẽ chặn merge.
5. Khi phát hiện thay đổi, GitHub Actions tự tạo **Issue → branch `auto/official-tthc-update` → Pull Request**; workflow **không tự merge**.
6. Nếu PR tự động cũ còn mở, lần chạy sau không tạo PR trùng.

Chạy kiểm tra nguồn thủ công tại máy phát triển:

```bash
python -m pip install pypdf==6.17.0
python scripts/update_official_sources.py --online
python scripts/extract_city_updates.py --as-of 2026-09-07
python scripts/build_master_data.py
python scripts/check_static_site.py
```

## formalityId — Cổng Dịch vụ công Quốc gia

Link chi tiết trực tiếp chỉ tạo khi có `formalityId` đã xác minh:

```text
https://dichvucong.gov.vn/thu-tuc-hanh-chinh/{formalityId}
```

Ánh xạ mẫu đã xác minh:

- Mã `2.000942`
- `formalityId`: `019d2bfd-95d6-778f-889b-e3045003fa5e`
- UUID Hải Phòng: `019bad30-cd83-76ea-9f9a-bc6cebad4138`
- UUID xã Vĩnh Bảo: `019bad30-cd84-7750-aaa5-8100fc7ceef8`
- `provinceCode=31`, `wardCode=11824`

Danh sách 51 TTHC trọng điểm được chuẩn hóa tại `data/priority-51-crosswalk.json`: 51/51 có mã canonical, 48/51 có `formalityId` trực tiếp và 03 mã dùng liên kết tìm kiếm DVCQG theo `keyword`. Ma trận `data/priority-51-legal-verification.json` đã kiểm chứng 37 mã từng thiếu: 36 mã có bằng chứng chính thức current/cấp xã và đã được bổ sung vào Master Data; mã `2.001009` có bằng chứng bãi bỏ nên chỉ nằm trong `master-data-excluded.json`. Kết quả hiện tại: **50/51 mã trọng điểm public**, **48 formalityId trong Master Data**. DVCQG chỉ dùng định danh kỹ thuật, không quyết định hiệu lực pháp lý.

## Nguyên tắc dữ liệu

1. Không ép số lượng theo danh mục cũ.
2. Trạng thái hiện hành/bãi bỏ phải có nguồn công bố chính thức và dấu vết audit.
3. Quyết định có hiệu lực trong tương lai không được làm thay đổi danh mục hiện hành trước ngày hiệu lực.
4. Dữ liệu legacy chỉ được bổ sung thuộc tính khi trùng mã, không tự xác nhận hiệu lực.
5. Tên thủ tục lỗi trích PDF được sửa theo cùng mã từ nguồn tin cậy; không dùng việc sửa tên để suy diễn trạng thái pháp lý.
6. CI chặn mã bãi bỏ/chưa hiệu lực lọt vào public, mã trùng, tên lỗi, lĩnh vực chưa xác định và lệch JSON/fallback.

## Kiểm thử

```bash
python scripts/check_static_site.py
```

CI trên Pull Request chạy kiểm tra Master Data, HTML/assets và cú pháp JavaScript.

## Phát hành website

Website được phát hành bằng GitHub Pages qua `.github/workflows/pages.yml`. Workflow chạy kiểm tra Master Data trước khi đóng gói đúng 13 tài nguyên runtime và chỉ deploy khi `main` được cập nhật hoặc khi chạy thủ công; Pull Request chỉ chạy phần validation/build, không deploy.

URL dự kiến sau khi GitHub Pages được bật cho repository:

`https://hongdienvbhp.github.io/BangNiemYetVinhBao/`

## Liên hệ

**Trung tâm Phục vụ hành chính công xã Vĩnh Bảo** — Đường 20/8, xã Vĩnh Bảo, thành phố Hải Phòng

Hotline: 0823.919.686 · 0967.311.138


## Đồng bộ Google Sheets canonical

Hai Google Sheets theo dõi TTHC cấp xã/cấp thành phố là **read model** của canonical pipeline, không phải nguồn sự thật độc lập.

- Projection: `scripts/google_sheets_projection.py`
- Live sync: `scripts/sync_google_sheets.py`
- Workflow: `.github/workflows/google-sheets-sync.yml`
- Hướng dẫn: `docs/GOOGLE_SHEETS_TTHC_PIPELINE.md`

Live sync chỉ chạy sau merge vào `main`. Upsert theo **Mã TTHC**, giữ nguyên các cột nghiệp vụ quản trị thủ công, append nhật ký và không tự xóa dòng thiếu bằng chứng. File cấp thành phố đang có cổng `PARTIAL_BASELINE` và không tự công bố cho đến khi baseline city được xác minh đầy đủ.
