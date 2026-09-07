# Bảng Niêm Yết Thủ Tục Hành Chính — UBND xã Vĩnh Bảo

Trang web phục vụ niêm yết, tra cứu thủ tục hành chính liên quan hoạt động tiếp nhận tại Trung tâm Phục vụ hành chính công xã Vĩnh Bảo, thành phố Hải Phòng.

> **Trạng thái dữ liệu chốt đến 07/09/2026:** đã audit **208 mã**, trong đó **193 TTHC hiện hành** được đưa vào tập công khai, **13 mã bị bãi bỏ** và **02 mã đã công bố nhưng chưa đến ngày hiệu lực**. Tập 193 có thể gồm TTHC cấp tỉnh được tiếp nhận tại Trung tâm PVHCC cấp xã; không đồng nhất với số TTHC thuộc thẩm quyền giải quyết của UBND xã.

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
- `data/source-audit/`: snapshot nguồn, bằng chứng và PDF quyết định chính thức.

## Nguồn kiểm chứng đến 07/09/2026

Master Data kết hợp snapshot công bố TTHC trên cổng xã Vĩnh Bảo với các quyết định mới của UBND thành phố Hải Phòng: `3500/QĐ-UBND`, `3501/QĐ-UBND`, `3508/QĐ-UBND`, `3509/QĐ-UBND`, `3517/QĐ-UBND`, `3523/QĐ-UBND`.

`3501/QĐ-UBND` có hiệu lực từ **01/03/2027**, nên 02 mã tương ứng được giữ ở nhóm tương lai và chưa hiển thị như TTHC hiện hành ngày 07/09/2026. Các quyết định/quy trình nội bộ không phải TTHC công khai cho người dân không được đưa vào Master Data public.

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

Master Data hiện chưa có mapping UUID hàng loạt. Khi thiếu `formalityId`, website dùng tra cứu DVCQG thay vì tự dựng URL chi tiết từ mã TTHC.

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

## Liên hệ

**Trung tâm Phục vụ hành chính công xã Vĩnh Bảo** — Đường 20/8, xã Vĩnh Bảo, thành phố Hải Phòng

Hotline: 0823.919.686 · 0967.311.138
