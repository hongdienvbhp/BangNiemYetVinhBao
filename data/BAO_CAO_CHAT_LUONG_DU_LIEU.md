# Báo cáo rà soát chất lượng dữ liệu TTHC — UBND xã Vĩnh Bảo

Cập nhật: **07/09/2026**

## 1. Trạng thái Master Data

| Chỉ số | Kết quả |
|---|---:|
| Mã đã audit | **208** |
| TTHC hiện hành trong tập công khai | **193** |
| Mã bị bãi bỏ/loại khỏi public | **13** |
| Mã đã công bố nhưng chưa đến ngày hiệu lực | **2** |
| Mã trùng trong public | **0** |
| Tên chưa đạt cổng chất lượng | **0** |
| Lĩnh vực chưa xác định | **0** |
| Mã mới từ 06 quyết định thành phố | **37** |
| Mã hiện có được cập nhật bởi quyết định thành phố | **1** |
| Mã phi địa giới theo nguồn công bố | **56** |
| `formalityId` trong Master Data | **14** |
| Crosswalk 51 TTHC trọng điểm | **51 mã; 48 UUID trực tiếp; 3 keyword fallback** |
| TTHC trọng điểm có trong Master hiện hành | **14/51** |
| Khoảng trống cần kiểm chứng pháp lý | **37/51** |

## 2. Phạm vi số liệu

**193** là số TTHC trong tập niêm yết/tra cứu hiện hành của dự án theo nguồn đã audit đến 07/09/2026. Tập này có thể gồm TTHC cấp tỉnh có địa điểm tiếp nhận tại Trung tâm PVHCC cấp xã. Vì vậy không được diễn giải thành “193 TTHC thuộc thẩm quyền giải quyết của UBND xã”.

Dữ liệu legacy vẫn còn 400 dòng thô/313 mã chuẩn hóa duy nhất trong `js/data.js` để đối chiếu lịch sử. Đây **không còn là nguồn danh mục hiện hành chính**.

## 3. Cập nhật quyết định mới

Đã bổ sung và audit 06 quyết định công khai mới của UBND thành phố Hải Phòng: `3500`, `3501`, `3508`, `3509`, `3517`, `3523/QĐ-UBND`.

- 51 mã xuất hiện trong 06 quyết định.
- 38 thủ tục đang hiệu lực có bằng chứng tiếp nhận tại Trung tâm PVHCC cấp xã.
- 11 mã bị bãi bỏ trong nhóm quyết định mới.
- 02 mã của `3501/QĐ-UBND` có hiệu lực từ **01/03/2027**, chưa đưa vào public hiện hành.

Kết hợp snapshot trước đó, tổng số mã bãi bỏ được giữ dấu vết là 13.

## 4. Bất nhất 473 TTHC

Số **473** từng ghi trong tài liệu cũ không có bộ file nguồn tương ứng trong lịch sử Git và không tái lập được. Dự án không còn dùng 473 làm tiêu chí hoàn thành hoặc số lượng mục tiêu.

## 5. formalityId và 51 TTHC trọng điểm

Đã chuẩn hóa `data/priority-51-crosswalk.json` từ danh mục 51 TTHC và dữ liệu xác minh trước đây:

- 51/51 dòng có mã TTHC canonical;
- 48/51 có `formalityId` trực tiếp, không trùng UUID;
- 03 mã (`2.001283`, `2.000720`, `2.001009`) chưa xác minh được UUID trực tiếp nên giữ liên kết tìm kiếm DVCQG theo mã;
- 14/51 mã hiện có trong Master Data và đã được gắn `priority51`; cả 14 mã này có UUID kỹ thuật;
- 37/51 mã chưa có trong Master Data hiện hành được chuyển thành danh sách cần kiểm chứng pháp lý ở bước tiếp theo, không tự bổ sung.

Crosswalk chỉ dùng cho danh tính/mapping kỹ thuật. Nó không thay thế bằng chứng về hiệu lực, bãi bỏ, thẩm quyền, phí, thời hạn hoặc quyết định công bố. Website chỉ tạo link chi tiết trực tiếp khi UUID đã được ghi nhận; nếu thiếu thì fallback sang chức năng tra cứu.

## 6. Cổng kiểm soát tự động

`scripts/check_static_site.py` kiểm tra:

- JSON public, excluded và summary khớp nhau;
- không có mã trùng, tên lỗi hoặc lĩnh vực chưa xác định;
- mã bãi bỏ/chưa hiệu lực không lọt vào public;
- các mã mới trọng yếu từ quyết định thành phố có mặt;
- 06 quyết định mới còn đầy đủ trong source audit;
- JSON và `js/master-data-fallback.js` có cùng tập mã;
- runtime đã bật `data/thu-tuc.json`, cache v3 và không quay lại URL DVCQG kiểu cũ.
