# Hợp đồng dữ liệu TTHC canonical

Nguồn duy nhất của danh mục TTHC dùng chung là `data/thu-tuc.json` trong repository `BangNiemYetVinhBao`.

- `version`: phiên bản schema contract.
- `dataset_version`: phiên bản dữ liệu dạng `YYYY.MM.DD`.
- `source_commit`: commit nguồn đã được kiểm chứng để tạo phiên bản dữ liệu.
- `thuTuc[].ma`: khóa nghiệp vụ duy nhất.

Consumer chỉ được tải, kiểm tra, ánh xạ và tạo view/filter từ tệp này. Không commit snapshot Master TTHC độc lập. Dữ liệu nghiệp vụ phát sinh riêng của consumer phải lưu tách biệt và tham chiếu bằng mã TTHC.

Mỗi lần phát hành dữ liệu phải cập nhật `dataset_version` và `source_commit`, chạy `python scripts/validate_canonical_contract.py`, test repository và CI trước khi merge.
