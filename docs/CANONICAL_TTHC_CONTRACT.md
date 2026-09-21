# Hợp đồng dữ liệu TTHC canonical

Nguồn duy nhất của danh mục TTHC dùng chung là `data/thu-tuc.json` trong repository `BangNiemYetVinhBao`.

## Định danh phiên bản

- `version`: phiên bản schema contract.
- `dataset_version`: phiên bản dữ liệu dạng `YYYY.MM.DD`, tăng theo ngày snapshot/enrichment đã xác minh mới nhất và không được lùi.
- `source_commit`: commit của **nguồn đầu vào đã được kiểm chứng dùng để dựng dataset**, không phải mặc định là SHA của commit hiện đang chứa `data/thu-tuc.json`.
- `thuTuc[].ma`: khóa nghiệp vụ duy nhất giữa mọi consumer.

Consumer chỉ được tải, kiểm tra, ánh xạ và tạo view/filter từ tệp này. Không commit snapshot Master TTHC độc lập. Dữ liệu nghiệp vụ phát sinh riêng của consumer phải lưu tách biệt và tham chiếu bằng mã TTHC.

## Hai lớp dữ liệu

### Lớp 1 — lifecycle/hiệu lực

Nguồn Hải Phòng/Vĩnh Bảo quyết định tập TTHC đang còn hiệu lực, mới ban hành, sửa đổi/bổ sung, bãi bỏ, thay thế và nội dung cắt giảm tại địa phương. Quyết định Bộ/ngành không được tự động thêm hoặc phục hồi một mã đã bị loại khỏi canonical địa phương.

### Lớp 2 — hướng dẫn đã xác minh

Enrichment nằm tại `data/tthc-guidance-enrichment.json`, keyed bằng mã TTHC. Đây là evidence/staging để merge vào canonical, không phải Master thứ hai.

Ba vai trò nguồn bắt buộc:

1. `central_content_reference`: quyết định/danh mục TTHC chính thức của Bộ, cơ quan ngang Bộ; dùng lấy nội dung chuẩn theo mã như thành phần hồ sơ, biểu mẫu, trình tự.
2. `local_legal_effect`: quyết định/công bố chính thức Hải Phòng; quyết định hiệu lực, thẩm quyền, thời hạn/cắt giảm và nội dung áp dụng tại địa phương.
3. `local_execution`: DVCQG/hệ thống thực thi chính thức; dùng xác minh formalityId, địa bàn, cơ quan tiếp nhận và URL nộp hồ sơ.

Mỗi trường có nội dung trong enrichment phải có `fieldProvenance` trỏ tới `sources[].id`. Riêng `submissionUrl` chỉ được provenance từ `local_execution` và phải đúng:

- `provinceCode=31`
- `wardCode=11824`
- `commune=WARD`
- `formalityId` khớp khi canonical đã có UUID.

Nếu nguồn trung ương và Hải Phòng khác nhau về nội dung áp dụng tại Hải Phòng, `local_legal_effect` được ưu tiên. Nội dung thiếu bằng chứng hoặc chưa xác minh không được publish.

## Phát hành

Mỗi lần phát hành dữ liệu phải:

1. rebuild deterministic từ nguồn đã lưu;
2. chạy `python scripts/validate_tthc_guidance.py`;
3. chạy `python scripts/validate_canonical_contract.py`;
4. chạy unit test/CI;
5. chỉ merge khi không có drift không giải thích được.

Google Sheets/Excel, `CongkhaiTTHC`, `tthc-monitor` và `thutuchanhchinh` là consumer/read-model; không được sở hữu Master TTHC riêng.
