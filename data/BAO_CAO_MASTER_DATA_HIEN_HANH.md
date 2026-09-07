# Báo cáo Master Data TTHC – snapshot 2026-09-07

## Kết quả

- Mã ứng viên cấp xã/điểm tiếp nhận cấp xã từ snapshot Vĩnh Bảo: **159**
- Tổng mã được audit sau khi hợp nhất nguồn Vĩnh Bảo, quyết định thành phố và ma trận kiểm chứng 51 TTHC: **245**
- Mã xuất hiện trong 06 quyết định cập nhật thành phố: **51**
- Mã Priority 51 được kiểm chứng pháp lý bổ sung: **37**
  - Xác minh current/cấp xã: **36**
  - Xác minh bãi bỏ: **1**
  - Còn cần xác minh: **0**
- TTHC hiện hành đưa vào tập công khai: **229**
- TTHC loại khỏi tập công khai: **16**
  - Bị bãi bỏ: **14**
  - Đã công bố nhưng chưa đến ngày hiệu lực: **2**
- TTHC mới được bổ sung từ quyết định thành phố: **37**
- TTHC hiện có được cập nhật bởi quyết định thành phố: **1**
- Chưa trích được tên đủ tin cậy: **0**
- Có formalityId trong Master Data: **48**
- TTHC trọng điểm đang nằm trong tập public: **50/51**
- Khoảng trống Priority 51 còn lại: **1** (mã bãi bỏ không được phục hồi public)
- Được đánh dấu phi địa giới theo nguồn công bố: **59**

> **Lưu ý phạm vi:** 229 là số TTHC trong tập niêm yết/tra cứu của Trung tâm PVHCC xã Vĩnh Bảo theo bằng chứng nguồn đã audit. Tập này có thể gồm TTHC cấp tỉnh được tiếp nhận tại Trung tâm PVHCC cấp xã; không được hiểu là toàn bộ đều thuộc thẩm quyền giải quyết của UBND xã.

## Nguồn cập nhật đến 07/09/2026

- Snapshot cổng TTHC xã Vĩnh Bảo và các phụ lục chính thức đã lưu trong `data/source-audit/`.
- Quyết định 3500/QĐ-UBND, 3501/QĐ-UBND, 3508/QĐ-UBND, 3509/QĐ-UBND, 3517/QĐ-UBND, 3523/QĐ-UBND của UBND thành phố Hải Phòng.
- QĐ 3501/QĐ-UBND có hiệu lực từ **01/03/2027**; 02 mã trong quyết định được lưu ở nhóm tương lai, chưa đưa vào tập hiện hành ngày 07/09/2026.
- Quyết định/quy trình nội bộ như 3507, 3521, 3537 không được đưa vào Master Data công khai cho người dân.
- `data/priority-51-legal-verification.json`: ma trận kiểm chứng pháp lý riêng cho 37 mã trọng điểm từng thiếu khỏi Master Data; DVCQG chỉ làm lớp định danh kỹ thuật.

## Quy tắc

1. Không ép danh mục về con số 473 hoặc bất kỳ số lượng mục tiêu định trước nào.
2. Trạng thái hiện hành/bãi bỏ lấy từ bằng chứng công bố chính thức Vĩnh Bảo/Hải Phòng, có ngày nguồn và URL truy vết.
3. Mã bị bãi bỏ được loại khỏi `data/thu-tuc.json` nhưng giữ dấu vết trong `data/master-data-excluded.json` và audit CSV.
4. Mã có quyết định chưa đến ngày hiệu lực được lưu riêng và không hiển thị như TTHC hiện hành.
5. Dữ liệu cũ chỉ bổ sung thuộc tính khi trùng mã; không tự xác nhận hiệu lực.
6. Tên bị lỗi trích PDF được chuẩn hóa theo cùng mã từ dữ liệu kế thừa hoặc Cổng DVCQG; việc này không thay đổi căn cứ xác định trạng thái.
7. formalityId là lớp ánh xạ kỹ thuật. Thiếu UUID không làm thay đổi trạng thái pháp lý; website fallback sang tra cứu DVCQG theo tên/mã.
8. Danh sách 51 TTHC cũ không tự tạo thủ tục public. Mã chỉ được bổ sung khi ma trận kiểm chứng pháp lý có nguồn chính thức Hải Phòng/Vĩnh Bảo và trạng thái `current_official_commune_evidence`; mã `repealed_official_evidence` phải ở excluded.

## Tệp kiểm soát

- `data/thu-tuc.json`: Master Data public.
- `data/master-data-audit.csv`: toàn bộ mã đã audit.
- `data/master-data-excluded.json`: mã bãi bỏ/chưa hiệu lực.
- `data/source-audit/`: snapshot, PDF và bằng chứng nguồn.
- `js/master-data-fallback.js`: fallback sinh tự động từ cùng Master Data.
