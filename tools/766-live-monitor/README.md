# 766 Live Monitor

Collector thử nghiệm dữ liệu Chỉ số 766 trực tiếp từ Cổng Dịch vụ công Quốc gia.

## Mục tiêu
- Gọi API công khai của Cổng thay vì phụ thuộc Google Drive/Sheets.
- Giữ nguyên payload và score do Cổng trả về.
- Lọc đúng departmentName = UBND xã Vĩnh Bảo.
- Xuất JSON thô + snapshot làm bằng chứng.
- Có thể chạy thủ công hoặc theo lịch GitHub Actions 07:00 giờ Việt Nam.

## API thử nghiệm
POST /api/v1/reporting/evaluation/dossier-digitized

Kỳ mặc định trong test: tháng 09/2026, Hải Phòng.
