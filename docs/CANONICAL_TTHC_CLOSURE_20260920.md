# Canonical TTHC Architecture — Closure Checkpoint 20/09/2026

## Phạm vi

Chuỗi canonical được kiểm tra: `BangNiemYetVinhBao → tthc-monitor / CongkhaiTTHC / thutuchanhchinh`.

## Bằng chứng kỹ thuật đã xác minh

- Canonical contract: `data/thu-tuc.json`.
- `dataset_version`: `2026.09.18`.
- `source_commit`: `d720f07659f8571e03f16ecdb3cc914598550c57`.
- Tổng số TTHC canonical: 254.
- TTHC trọng điểm hiện hành (`priority51=true`): 50.
- Mã `2.001009` đã bãi bỏ: không tồn tại trong canonical hiện hành.
- `tthc-monitor`: mặc định đọc trực tiếp canonical live; output mang `dataset_version/source_commit`; có cảnh báo khi dùng canonical local lệch bản hiện hành; CI gate chống Master riêng; 40/40 unit tests PASS; commit `ed95aab` đã fast-forward lên `main`.
- `CongkhaiTTHC`: canonical loader trỏ `BangNiemYetVinhBao/main/data/thu-tuc.json`, kiểm tra `dataset_version/source_commit`, có gate chống Master riêng.
- `thutuchanhchinh`: view/filter động theo `priority51 === true`, hiển thị `dataset_version/source_commit`, không còn fallback TTHC hard-code, có gate chống Master riêng.

## Trạng thái closure

Kỹ thuật canonical: PASS.

Chưa được phép kết luận toàn bộ work package `CLOSED` cho đến khi có thêm:
1. bằng chứng GitHub Actions của commit `tthc-monitor/main@ed95aab` hoàn tất SUCCESS;
2. cập nhật trạng thái tương ứng trên Linear.

Executor hiện tại không có connector Linear và không đọc được GitHub Actions endpoint, vì vậy hai bước trên được ghi nhận là blocker quản trị/bằng chứng, không phải blocker code.
