# Báo cáo rà soát chất lượng dữ liệu TTHC — UBND xã Vĩnh Bảo

Cập nhật: **06/09/2026**

## 1. Kết quả kiểm tra repository

| Chỉ số | Kết quả kiểm tra |
|---|---:|
| Dòng dữ liệu có trường `ma` trong `js/data.js` | **400** |
| Mã TTHC chuẩn hóa duy nhất theo logic hiện tại | **313** |
| `formalityId` đã xác định chắc chắn trong repo | **1** |
| Mã mẫu có `formalityId` | `2.000942` |
| File Master Data `data/thu-tuc.json` | **Chưa có** |
| Đồng bộ JSON tự động | **Tạm tắt** |

## 2. Bất nhất đã phát hiện

Báo cáo trước đây từng ghi **473 TTHC**, 67 lĩnh vực, 473/473 có thời hạn và phí. Tuy nhiên các file nguồn tương ứng (`data/thu-tuc.json`, bản `js/data.js` 473 thủ tục và file mapping đầy đủ) **không có trong lịch sử Git của repository** tại thời điểm rà soát.

Vì vậy:

- Không tiếp tục công bố số **473** như số liệu đã xác minh từ repository hiện tại.
- Bộ dữ liệu phục hồi chỉ được coi là **nguồn cục bộ kế thừa để đối chiếu**, chưa phải Master Data hiện hành.
- Cần dựng lại danh mục hiện hành từ quyết định công bố/sửa đổi/bãi bỏ và nguồn chính thức của thành phố trước khi bật đồng bộ JSON.

## 3. formalityId DVCQG

Đã có một ánh xạ xác định:

| Mã TTHC | formalityId |
|---|---|
| `2.000942` | `019d2bfd-95d6-778f-889b-e3045003fa5e` |

Ứng dụng đã được sửa theo nguyên tắc:

- Có `formalityId` → tạo link chi tiết theo `/thu-tuc-hanh-chinh/{formalityId}` và link chọn/nộp hồ sơ theo địa bàn Hải Phòng – xã Vĩnh Bảo.
- Chưa có `formalityId` → chỉ mở chức năng tra cứu; không tạo URL chi tiết giả định từ mã TTHC.

## 4. Việc tiếp theo về dữ liệu

1. Đối chiếu danh mục TTHC cấp xã từ các quyết định công bố còn hiệu lực.
2. Loại bỏ thủ tục bị bãi bỏ/thay thế và bản ghi trùng.
3. Chuẩn hóa trường: mã, tên, lĩnh vực, cơ quan/đơn vị, thời hạn, phí/lệ phí, hình thức DVCTT, phi địa giới, căn cứ và trạng thái xác minh.
4. Bổ sung `formalityId` có bằng chứng.
5. Sinh `data/thu-tuc.json` và chỉ sau đó bật `remoteJsonUrl` trong `js/config.js`.
