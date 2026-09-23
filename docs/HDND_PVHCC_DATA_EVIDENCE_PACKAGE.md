# Gói dữ liệu và minh chứng giám sát của Trung tâm PVHCC

## 1. Mục đích và phạm vi

Gói này chuẩn hóa hồ sơ dữ liệu phục vụ giám sát của HĐND về chất lượng giải quyết thủ tục hành chính (TTHC) và chuyển đổi số tại Trung tâm Phục vụ hành chính công (PVHCC) xã Vĩnh Bảo. Mỗi kỳ báo cáo phải truy được số liệu về nguồn, thời điểm trích xuất, quy tắc tính và minh chứng gốc.

Tài liệu này là hợp đồng dữ liệu và hướng dẫn đóng gói. Không ghi số liệu giả định hoặc tự điền kết quả khi chưa có bản trích xuất/đối soát từ hệ thống nghiệp vụ.

## 2. Nguồn dữ liệu và quyền sở hữu

| Dữ liệu | Nguồn ưu tiên | Vai trò |
|---|---|---|
| Danh mục, mã, tên, thẩm quyền, phạm vi TTHC, thành phần hướng dẫn đã xác minh | `data/thu-tuc.json` trong BangNiemYetVinhBao | Nguồn canonical duy nhất về dữ liệu TTHC |
| Tiếp nhận, trạng thái, hạn giải quyết, kết quả, thời điểm trả | Hệ thống một cửa đang ghi nhận hồ sơ (VNPT iGate/motcua) | Nguồn giao dịch nghiệp vụ; trích xuất theo kỳ |
| Giao dịch trực tuyến, thanh toán, số hóa hồ sơ/kết quả | Hệ thống một cửa và Cổng DVC tương ứng | Nguồn chỉ số chuyển đổi số; đối chiếu trước khi tổng hợp |
| Phản ánh/đánh giá hài lòng | Kênh đánh giá chính thức được sử dụng trong kỳ | Nguồn phản hồi; nêu rõ số lượt hợp lệ và cách tổng hợp |
| Sự cố nền tảng ảnh hưởng tiếp nhận/giải quyết | Nhật ký sự cố, thông báo nhà cung cấp/cơ quan quản lý và sổ theo dõi của Trung tâm | Bằng chứng giải trình ảnh hưởng; không tự quy kết nguyên nhân |

Google Sheets, dashboard, báo cáo xuất ra và OA/Mini App là bản chiếu hoặc kênh tương tác. Chúng không có quyền định nghĩa, sửa độc lập hoặc làm nguồn gốc thay thế danh mục TTHC canonical.

## 3. Cấu trúc gói theo kỳ

Mỗi kỳ lập một thư mục với mã kỳ duy nhất, ví dụ `YYYY-QN` hoặc `YYYY-MM`:

- `manifest.json`: kỳ báo cáo, ngày chốt, người lập/kiểm tra theo chức danh, nguồn, thời điểm trích xuất, phiên bản bộ dữ liệu và mã commit canonical.
- `metrics.csv`: một dòng cho mỗi chỉ tiêu, gồm mã chỉ tiêu, giá trị tử số, mẫu số, đơn vị, giá trị hiển thị, quy tắc tính, nguồn và trạng thái kiểm chứng.
- `case-status-aggregate.csv`: bảng tổng hợp hồ sơ theo mã TTHC/lĩnh vực/tháng và trạng thái; không xuất dữ liệu nhận diện cá nhân.
- `digital-aggregate.csv`: tổng hợp hồ sơ trực tuyến, số hóa, thanh toán trực tuyến và kết quả điện tử, kèm tử/mẫu.
- `incidents.csv`: sự cố, khoảng thời gian ảnh hưởng, hệ thống liên quan, nguồn xác nhận và biện pháp xử lý.
- `evidence-index.csv`: mã minh chứng, chỉ tiêu được hỗ trợ, tên tệp/đường dẫn nội bộ, nguồn, ngày tạo, người xác nhận và ghi chú đối soát.
- `reconciliation.md`: số liệu nguồn, phép đối chiếu, chênh lệch, cách xử lý và nội dung còn chưa xác nhận.

Tệp gốc do hệ thống nghiệp vụ xuất được lưu kèm trong kho hồ sơ nội bộ có kiểm soát truy cập theo quy định của đơn vị. Gói gửi HĐND chỉ gồm số liệu tổng hợp và minh chứng đã rà soát; không đưa tên, số định danh, địa chỉ, số điện thoại, tài khoản, nội dung hồ sơ cá nhân hoặc mã tra cứu hồ sơ của công dân.

## 4. Danh mục chỉ tiêu tối thiểu

| Mã | Chỉ tiêu | Cách ghi nhận tối thiểu |
|---|---|---|
| `REC` | Hồ sơ tiếp nhận trong kỳ | Đếm theo thời điểm tiếp nhận; tách kênh trực tiếp/trực tuyến nếu nguồn có trường kênh |
| `SOL` | Hồ sơ đã giải quyết trong kỳ | Đếm theo thời điểm có kết quả/trạng thái hoàn tất; ghi riêng hồ sơ kỳ trước |
| `ONTIME` | Hồ sơ giải quyết đúng hạn | Tử số là hồ sơ hoàn tất không muộn hơn hạn trên hệ thống; mẫu số và cách xử lý hồ sơ xin rút/hủy phải nêu rõ |
| `OVERDUE` | Hồ sơ quá hạn | Đếm hồ sơ quá hạn theo trạng thái và thời điểm chốt; phân biệt còn đang xử lý và đã trả quá hạn |
| `ONLINE` | Hồ sơ nộp trực tuyến | Ghi tử số, tổng hồ sơ tiếp nhận có thể phân loại kênh, tỷ lệ và nguồn trường kênh |
| `DIGI` | Số hóa thành phần/kết quả | Báo cáo riêng từng loại; ghi số hồ sơ đủ điều kiện làm mẫu số, không gộp hai tỷ lệ khác bản chất |
| `PAY` | Thanh toán trực tuyến | Ghi số giao dịch thành công và số hồ sơ thuộc diện/có hỗ trợ thanh toán trực tuyến |
| `RESULT` | Kết quả điện tử | Ghi số kết quả điện tử được phát hành/trả và tổng hồ sơ đã giải quyết thuộc diện áp dụng |
| `SAT` | Mức độ hài lòng | Ghi số lượt đánh giá hợp lệ, tổng lượt phản hồi và phương pháp tính; không coi thiếu phản hồi là hài lòng |
| `INC` | Sự cố ảnh hưởng phục vụ | Ghi số sự cố đã xác nhận, khoảng thời gian, chức năng bị ảnh hưởng, nguồn xác nhận và cách giảm thiểu |

Không cộng các nhóm có khả năng giao nhau thành một tổng mới nếu chưa xác định rõ quy tắc loại trừ. Tỷ lệ phải lưu cả tử số và mẫu số; không chỉ lưu số phần trăm đã làm tròn.

## 5. Trường dữ liệu và truy xuất nguồn

Mỗi dòng chỉ tiêu hoặc tổng hợp tối thiểu có:

`period_start`, `period_end`, `as_of`, `indicator_code`, `numerator`, `denominator`, `value`, `unit`, `scope`, `source_system`, `source_export_id`, `extracted_at`, `canonical_dataset_version`, `canonical_source_commit`, `calculation_rule_version`, `evidence_id`, `verification_status`.

`verification_status` dùng một trong: `verified`, `needs_reconciliation`, `not_available`. Giá trị `not_available` phải có lý do và đầu mối khắc phục; không thay bằng 0. Nếu nguồn thay đổi hoặc xuất lại dữ liệu, giữ dấu vết phiên bản và nêu chênh lệch thay vì ghi đè minh chứng kỳ trước.

## 6. Kiểm soát chất lượng trước khi phát hành

1. Đối chiếu tổng hồ sơ theo trạng thái với tổng hồ sơ theo kênh và kiểm tra phần chênh lệch.
2. Kiểm tra trùng mã hồ sơ trong nguồn, bản ghi thiếu mã TTHC, ngày tiếp nhận/kết quả ngoài kỳ và trạng thái không hợp lệ.
3. Kiểm tra tử số không vượt mẫu số; tỷ lệ tính lại từ tử/mẫu và làm tròn nhất quán.
4. So sánh số liệu đầu kỳ/cuối kỳ với kỳ liền trước; giải trình biến động lớn bằng dữ liệu hoặc minh chứng.
5. Đối chiếu một mẫu bản ghi với hệ thống nghiệp vụ bằng mã tra cứu nội bộ; không đưa mã đó vào gói chia sẻ.
6. Người lập và người kiểm tra xác nhận trên manifest hoặc biên bản nội bộ; ghi ngày và chức danh.
7. Chỉ phát hành các chỉ tiêu `verified`; các chỉ tiêu còn lại gắn trạng thái và nêu rõ giới hạn dữ liệu.

## 7. Quy tắc tích hợp OA/Mini App

OA/Mini App là lớp tiếp nhận tương tác và hiển thị. Khi cung cấp danh mục/hướng dẫn TTHC, ứng dụng chỉ đọc API hoặc read model được tạo từ canonical. Mỗi phản hồi dữ liệu TTHC phải kèm `dataset_version` và `source_commit` để truy nguồn.

Phản ánh, câu hỏi, trạng thái đăng ký nhận tin và nhật ký tương tác thuộc kho dữ liệu tương tác riêng, theo mục đích và thời hạn lưu được đơn vị phê duyệt. Chúng không được ghi ngược vào `data/thu-tuc.json`. Thay đổi danh mục TTHC phải qua nguồn chính thức → quy trình xác minh → cập nhật canonical → validator/CI → xuất bản read model. Nếu API lỗi hoặc dữ liệu cũ quá ngưỡng vận hành được công bố, hiển thị thời điểm cập nhật gần nhất và đường dẫn đến kênh chính thức.

## 8. Danh mục minh chứng cần thu thập mỗi kỳ

- Bản xuất tổng hợp từ hệ thống một cửa có ngày/giờ tạo và kỳ lọc.
- Bản xuất hoặc màn hình báo cáo số hóa, trực tuyến, thanh toán và kết quả điện tử từ hệ thống nguồn.
- Bảng đối soát tử số/mẫu số và chênh lệch giữa các báo cáo.
- Nhật ký sự cố hoặc thông báo chính thức đối với sự cố được viện dẫn.
- Biên bản rà soát, xác nhận số liệu của người lập và người kiểm tra.
- Bản sao manifest và `evidence-index.csv` đã khóa phiên bản.
- Nhật ký phát hành báo cáo/gói dữ liệu và phạm vi người nhận.

Danh mục này là yêu cầu thu thập minh chứng, không khẳng định các tệp nêu trên đã được cung cấp hoặc kiểm tra. Hồ sơ kỳ chỉ được đánh dấu hoàn thành sau khi tệp thực tế, nguồn và đối soát đã được lưu.

## 9. Nguyên tắc lưu trữ và chia sẻ

Bản làm việc có dữ liệu chi tiết chỉ được lưu tại vị trí nội bộ đã được đơn vị cho phép. Bản gửi giám sát ưu tiên dữ liệu tổng hợp, giới hạn đúng mục đích; phân quyền người xem, ghi nhận ngày phát hành và duy trì bản đã phát hành để có thể giải trình. Thời hạn lưu và hủy thực hiện theo quy định hồ sơ, lưu trữ và bảo vệ dữ liệu hiện hành của cơ quan; tài liệu này không tự đặt một thời hạn mới.
