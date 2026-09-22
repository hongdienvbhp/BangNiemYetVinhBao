# CANONICAL TTHC V5 — CONTRACT VÀ LỘ TRÌNH

## 1. Quyền sở hữu dữ liệu

`BangNiemYetVinhBao/data/thu-tuc.json` là **canonical write model duy nhất** của portfolio đối với dữ liệu thủ tục hành chính.

Các dự án khác chỉ được:
- đọc trực tiếp canonical;
- tạo view/filter/read model/cache dẫn xuất;
- lưu `dataset_version` và `source_commit` của bản canonical đã sử dụng.

Không dự án nào khác được duy trì Master TTHC độc lập.

## 2. Mô hình phân loại bắt buộc

Không dùng một trường `cap` để biểu diễn đồng thời thẩm quyền và nơi tiếp nhận.

Mỗi TTHC phải tách:
- `authorityLevel`: cấp có thẩm quyền giải quyết;
- `serviceScope`: thuộc thẩm quyền cấp xã, dùng chung, chỉ tiếp nhận tại xã, hay cấp tỉnh;
- `receivableAtCommune`: có tiếp nhận tại cấp xã hay không;
- `onlineServiceLevel`: toàn trình, một phần, chỉ cung cấp thông tin, không trực tuyến hoặc chưa xác minh.

## 3. Giai đoạn 1 — cấp xã và dùng chung

Baseline nghiệp vụ tháng 9/2026 dùng làm reconciliation gate:

| Nhóm | Toàn trình | Một phần | Chỉ thông tin | Tổng |
|---|---:|---:|---:|---:|
| UBND cấp xã | 166 | 89 | 2 | 257 |
| Dùng chung | 46 | 20 | 0 | 66 |
| Tổng | 212 | 109 | 2 | 323 |

Không được ép số lượng nếu nguồn chính thức thay đổi. Khi lệch baseline phải sinh:
- `MATCHED`;
- `MISSING`;
- `EXTRA`;
- `MISCLASSIFIED`;
- `COUNT_DRIFT`.

Mọi chênh lệch phải truy tới **Mã TTHC + nguồn bằng chứng**.

## 4. Giai đoạn 2 — TTHC cấp tỉnh

TTHC cấp tỉnh được bổ sung vào **cùng canonical**, không tạo dataset riêng.

Link nộp hồ sơ phải route đúng cấp:
- cấp xã → scope xã Vĩnh Bảo;
- cấp tỉnh → scope thành phố Hải Phòng;
- không ép `wardCode` cho TTHC cấp tỉnh.

## 5. Giai đoạn 3 — dữ liệu hướng dẫn

Mỗi TTHC phải có contract thông tin đầy đủ:
- thành phần hồ sơ;
- biểu mẫu/tệp biểu mẫu;
- quy trình thực hiện;
- thời hạn;
- phí, lệ phí;
- cơ quan thực hiện;
- kết quả;
- DVC trực tuyến và link nộp đúng cấp;
- căn cứ pháp lý;
- quyết định công bố;
- lifecycle;
- field-level provenance.

### Không dùng chuỗi rỗng để che dữ liệu thiếu

Với trường chưa có giá trị, phải ghi trạng thái:
- `verified`;
- `not_published`;
- `not_applicable`;
- `pending_verification`;
- `unknown`.

Ví dụ:

```json
{
  "phiLePhi": {
    "status": "not_published",
    "items": [],
    "note": "Nguồn chính thức hiện chưa công bố mức thu"
  }
}
```

## 6. Provenance

Mỗi giá trị có ý nghĩa nghiệp vụ phải truy vết tới `evidenceId`.

Nguồn được ưu tiên:
1. CSDL quốc gia về VBPL/Công báo và quyết định công bố TTHC;
2. Cổng DVCQG;
3. Chính phủ/VPCP;
4. Bộ/ngành;
5. UBND thành phố Hải Phòng và sở/ngành;
6. nguồn chính thức cấp xã.

Nguồn trung ương có thể mô tả nội dung chuẩn; nguồn địa phương xác lập hiệu lực/triển khai tại Hải Phòng; nguồn DVCQG xác lập mapping và route thực thi trực tuyến.

## 7. Gate trước merge

PR thay đổi dữ liệu canonical phải PASS:
- schema/contract;
- unique Mã TTHC;
- lifecycle;
- evidence/provenance;
- reconciliation;
- online service classification;
- link route đúng cấp;
- không có Master độc lập ở consumer;
- build/test hiện hữu.

## 8. Nguyên tắc triển khai

Schema được khóa trước, sau đó mới migrate dữ liệu theo từng giai đoạn. Không nâng version canonical production khi dữ liệu chưa qua reconciliation và CI.
