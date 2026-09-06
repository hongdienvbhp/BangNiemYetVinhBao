# Bảng Niêm Yết Thủ Tục Hành Chính — UBND xã Vĩnh Bảo

Trang web phục vụ công khai, tra cứu thủ tục hành chính liên quan UBND xã Vĩnh Bảo, thành phố Hải Phòng.

> **Trạng thái dữ liệu 06/09/2026:** repository đã phục hồi mã nguồn giao diện và bộ dữ liệu cục bộ trước đây. File `js/data.js` có 400 dòng dữ liệu thô, tương ứng **313 mã TTHC chuẩn hóa duy nhất** theo quy tắc hiện tại của ứng dụng. Con số 473 trong báo cáo cũ chưa thể tái lập từ lịch sử Git nên **không được coi là số liệu đã xác minh** cho bản này.

---

## Repo

https://github.com/hongdienvbhp/BangNiemYetVinhBao

## Chạy local

```bash
git clone https://github.com/hongdienvbhp/BangNiemYetVinhBao.git
cd BangNiemYetVinhBao
python -m http.server 8080
# → http://localhost:8080
```

## Cấu trúc

```text
index.html
css/styles.css
js/config.js
js/data.js
js/extra-data.js
js/app.js
data/formalityId-mapping-mau.csv
data/phu-luc/
manifest.json
sw.js
netlify.toml
vercel.json
```

`data/thu-tuc.json` là nguồn Master Data dự kiến. Cấu hình đồng bộ JSON hiện **đang tắt** cho đến khi file này được dựng lại và kiểm duyệt từ nguồn chính thức.

## formalityId — Cổng Dịch vụ công Quốc gia

Link chi tiết trực tiếp chỉ được tạo khi có `formalityId` đã xác minh:

```text
https://dichvucong.gov.vn/thu-tuc-hanh-chinh/{formalityId}
```

Mẫu đã xác định:

- Mã TTHC `2.000942`
- `formalityId`: `019d2bfd-95d6-778f-889b-e3045003fa5e`
- UUID thành phố Hải Phòng: `019bad30-cd83-76ea-9f9a-bc6cebad4138`
- UUID xã Vĩnh Bảo: `019bad30-cd84-7750-aaa5-8100fc7ceef8`
- `provinceCode=31`, `wardCode=11824`

Các thủ tục chưa có `formalityId` chỉ mở tra cứu, không gắn URL chi tiết kiểu cũ để tránh dẫn sai thủ tục.

## Nguyên tắc dữ liệu

- Không suy đoán thủ tục hiện hành chỉ từ mã/tên có trong bộ dữ liệu cũ.
- Quyết định bãi bỏ, sửa đổi, thay thế phải được kiểm tra theo nguồn công bố chính thức trước khi cập nhật Master Data.
- Các trường chưa đủ căn cứ hiển thị `Chưa xác minh`.
- Danh mục quyết định/phí trong `js/extra-data.js` đang là dữ liệu tham khảo kế thừa và phải tiếp tục kiểm chứng trước khi dùng làm căn cứ nghiệp vụ.

## Liên hệ

**Trung tâm Phục vụ hành chính công xã Vĩnh Bảo** — Đường 20/8, xã Vĩnh Bảo, thành phố Hải Phòng

Hotline: 0823.919.686 · 0967.311.138
