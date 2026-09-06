# Báo cáo chất lượng dữ liệu TTHC — UBND xã Vĩnh Bảo

Cập nhật: **2026-09-06**

## Tổng quan

| Chỉ số | Giá trị |
|--------|---------|
| Tổng TTHC | **473** |
| Lĩnh vực | 67 |
| Có thời hạn | **473 / 473** |
| Có phí | **473 / 473** |
| Phi địa giới | 123 |
| Miễn phí trực tuyến | 141 |
| Liên thông | 4 |
| Trong ngày (T4) | 26 |
| formalityId DVCQG | **1 / 473** |

## Ưu tiên đã xử lý

### 1. Làm giàu thoiHan / phi (xong)
- Ưu tiên giá trị từ phụ lục QĐ (3433, 2893, 556, 2831…).
- Phần còn thiếu gán mặc định theo lĩnh vực (cùng logic DETAIL_BY_LV trong app.js).
- Kết quả: **100%** bản ghi có `thoiHan` và `phi`.

### 2. formalityId DVCQG (đang chờ)
- Cổng DVCQG không có API công khai map mã TTHC → UUID.
- Hiện **1/473** (mẫu `2.000942`).
- Cách làm: mở CSV `data/formalityId-mapping-mau.csv` → tra trên dichvucong.gov.vn → dán formalityId → gửi lại file.

### 3. GitHub (một phần)
- Repo: https://github.com/hongdienvbhp/BangNiemYetVinhBao
- Cần push nốt: `js/data.js`, `data/thu-tuc.json`, `js/app.js`, `css/styles.css`…

## Đồng bộ file

| File | Vai trò |
|------|---------|
| `data/thu-tuc.json` | Nguồn JSON + remote sync |
| `js/data.js` | `window.TTHC_DATA` load offline |
| `data/formalityId-mapping-mau.csv` | Template điền UUID |
| `js/app.js` | Link DVCQG (formalityId + UUID Vĩnh Bảo) |
