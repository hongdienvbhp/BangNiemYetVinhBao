# Rà soát Nghị quyết 23/2026/NQ-HĐND – mức thu phí, lệ phí khi thực hiện TTHC trực tuyến

> **Trạng thái:** BẢN NHÁP – lớp ứng viên (`candidate_only`). Chưa promote vào `data/thu-tuc.json`, chưa ghi Google Sheets.
> Dữ liệu máy đọc: `data/source-audit/fee-policy/nq-23-2026-online-fee-candidates.json` (sinh bằng `scripts/build_online_fee_policy_candidates.py`).

## 1. Văn bản gốc (đã kiểm chứng)

| Mục | Nội dung | Nguồn |
|---|---|---|
| Số hiệu | 23/2026/NQ-HĐND | Metadata Công báo Hải Phòng (lớp chữ của PDF ký số để trống số/ngày) |
| Cơ quan ban hành | HĐND thành phố Hải Phòng, khóa XVII, Kỳ họp thứ 3 | Câu kết Nghị quyết |
| Ngày thông qua | 28/7/2026 | Câu kết Nghị quyết; metadata Công báo (issueTime) |
| Đăng Công báo | 30/7/2026 | Metadata Công báo |
| Ngày hiệu lực | 08/8/2026 | Điều 3 khoản 1 |
| Thời hạn áp dụng | Không quy định thời hạn | Điều 3 |
| Phạm vi | Toàn thành phố; không giới hạn cấp giải quyết → áp dụng cả TTHC cấp xã có phát sinh các khoản tại Điều 2 | Điều 1 |
| Điều kiện "trực tuyến" | Yêu cầu giải quyết TTHC qua hình thức trực tuyến **tại Cổng Dịch vụ công quốc gia hoặc Ứng dụng định danh quốc gia (VNeID)**; không phân biệt toàn trình/một phần | Điều 1 khoản 2 điểm a |
| Chuyển tiếp | Hồ sơ nộp trực tuyến **trước 08/8/2026** vẫn theo NQ 07/2025/NQ-HĐND (Hải Dương) và NQ 08/2025/NQ-HĐND (Hải Phòng) | Điều 3 khoản 3 |
| Văn bản hết hiệu lực | NQ 07/2025/NQ-HĐND ngày 10/6/2025 (HĐND tỉnh Hải Dương); NQ 08/2025/NQ-HĐND ngày 17/6/2025 (HĐND TP Hải Phòng) | Điều 3 khoản 2 |
| File gốc | https://congbao.haiphong.gov.vn/upload/105430/20260730/NQ_QPPL_23_ce7a8.pdf — SHA-256 `6437d5562e94e5a4eab835459cddd17038046370e40d447eae81d0fdcf8a4eb7` | Lưu tại `data/source-audit/fee-policy/` (Git LFS) |

**Sai khác so với tin báo:** Nghị quyết ghi "phí đăng ký **giao dịch** bảo đảm" (tin báo: "biện pháp bảo đảm"); điểm e là "phí bình tuyển, công nhận cây mẹ, cây đầu dòng, vườn giống cây lâm nghiệp, rừng giống".

## 2. Kết quả đối chiếu với 254 TTHC canonical

- Khớp 47 dòng: 19 thuộc 51 TTHC trọng điểm; độ tin cậy Cao 24, Trung bình 12, Thấp 11; 1 dòng không thuộc phạm vi.
- 7/11 khoản **không có TTHC nào trong canonical**: GPLĐ người nước ngoài (1.b), GPXD (1.d), giấy phép môi trường (2.c), ĐTM (2.d), tài nguyên nước (2.đ), giống cây lâm nghiệp (2.e), cơ sở thể thao (2.g).
- Trường `phi`/`phiOnline` trong canonical **đang trống toàn bộ 254 TTHC** → không có mức phí trực tiếp đã kiểm chứng để so sánh; mức thu trực tiếp theo NQ HĐND chuyên ngành: [cần bổ sung].
- Hướng dẫn DVCQG ghi "0 — mức lệ phí cụ thể do HĐND quyết định" là **giá trị mặc định của DVCQG**, không phải mức thu của Hải Phòng.

**Quy tắc độ tin cậy:** Cao = Nghị quyết nêu đích danh khoản thu và kết quả TTHC tạo ra khoản thu đó; Trung bình = khớp nhưng tên khoản thu khác (giao dịch/biện pháp bảo đảm) hoặc chỉ phát sinh khi có cấp GCN mới; Thấp = chưa có nguồn xác nhận phát sinh khoản thu, hoặc thủ tục lưu động.

| # | Mã TTHC | Tên TTHC | 51 TĐ | Cấp thực hiện | Phí hiện ghi | Phí đề xuất khi nộp trực tuyến | Căn cứ NQ 23/2026 | Phạm vi | Độ tin cậy |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 1.000593 | Thủ tục đăng ký kết hôn lưu động | ✔ | Xã | Canonical: trống; DVCQG ghi "0" | 0 đồng | Điều 2 khoản 1 điểm a | Áp dụng nếu nộp trực tuyến được | Thấp |
| 2 | 1.000656 | Thủ tục đăng ký khai tử | ✔ | Xã / điểm TN cấp xã | Canonical: trống; DVCQG ghi "0 — mức cụ thể do HĐND quyết định" | 0 đồng | Điều 2 khoản 1 điểm a | Áp dụng | Cao |
| 3 | 1.000689 | Thủ tục đăng ký khai sinh kết hợp đăng ký nhận cha, mẹ, con | ✔ | Xã / điểm TN cấp xã | Canonical: trống; DVCQG ghi "0 — mức cụ thể do HĐND quyết định" | 0 đồng | Điều 2 khoản 1 điểm a | Áp dụng | Cao |
| 4 | 1.000894 | Thủ tục đăng ký kết hôn | ✔ | Xã | Canonical: trống; DVCQG ghi "Miễn lệ phí" | 0 đồng | Điều 2 khoản 1 điểm a | Áp dụng | Cao |
| 5 | 1.001193 | Thủ tục đăng ký khai sinh | ✔ | Xã / điểm TN cấp xã | Canonical: trống; DVCQG ghi "0" | 0 đồng | Điều 2 khoản 1 điểm a | Áp dụng | Cao |
| 6 | 1.004746 | Thủ tục đăng ký lại kết hôn | ✔ | Xã | Canonical: trống; DVCQG ghi "0 — mức cụ thể do HĐND quyết định" | 0 đồng | Điều 2 khoản 1 điểm a | Áp dụng | Cao |
| 7 | 1.004772 | Thủ tục đăng ký khai sinh cho người đã có hồ sơ, giấy tờ cá nhân | ✔ | Xã / điểm TN cấp xã | Canonical: trống; DVCQG ghi "0 — mức cụ thể do HĐND quyết định" | 0 đồng | Điều 2 khoản 1 điểm a | Áp dụng | Cao |
| 8 | 1.004837 | Thủ tục đăng ký giám hộ | ✔ | Xã / điểm TN cấp xã | Canonical: trống; DVCQG ghi "0" (chỉ nêu phí bản sao) | 0 đồng | Điều 2 khoản 1 điểm a | Áp dụng | Cao |
| 9 | 1.004859 | Thủ tục thay đổi, cải chính, bổ sung thông tin hộ tịch, xác định lại dân tộc | ✔ | Xã / điểm TN cấp xã | Canonical: trống; DVCQG ghi "0 — mức cụ thể do HĐND quyết định" | 0 đồng | Điều 2 khoản 1 điểm a | Áp dụng | Cao |
| 10 | 1.004873 | Thủ tục cấp Giấy xác nhận tình trạng hôn nhân | ✔ | Xã / điểm TN cấp xã | Canonical: trống; DVCQG ghi "0 — mức cụ thể do HĐND quyết định" | 0 đồng | Điều 2 khoản 1 điểm a | Áp dụng | Cao |
| 11 | 1.004884 | Thủ tục đăng ký lại khai sinh | ✔ | Xã / điểm TN cấp xã | Canonical: trống; DVCQG ghi "0 — mức cụ thể do HĐND quyết định" | 0 đồng | Điều 2 khoản 1 điểm a | Áp dụng | Cao |
| 12 | 1.005461 | Đăng ký lại khai tử | ✔ | Xã / điểm TN cấp xã | Canonical: trống; DVCQG ghi "0 — mức cụ thể do HĐND quyết định" | 0 đồng | Điều 2 khoản 1 điểm a | Áp dụng | Cao |
| 13 | 2.000528 | Thủ tục đăng ký khai sinh có yếu tố nước ngoài | ✔ | Xã / điểm TN cấp xã | Canonical: trống; DVCQG ghi "0 — mức cụ thể do HĐND quyết định" | 0 đồng | Điều 2 khoản 1 điểm a | Áp dụng | Cao |
| 14 | 2.000635 | Cấp bản sao Trích lục hộ tịch, bản sao Giấy khai sinh | ✔ | Xã / điểm TN cấp xã | Canonical: trống; DVCQG ghi "8,000" | Không đề xuất | Điều 2 khoản 1 điểm a | Không thuộc phạm vi | Trung bình |
| 15 | 2.000806 | Thủ tục đăng ký kết hôn có yếu tố nước ngoài | ✔ | Xã | Canonical: trống; DVCQG ghi "0 — mức cụ thể do HĐND quyết định" | 0 đồng | Điều 2 khoản 1 điểm a | Áp dụng | Cao |
| 16 | 2.002189 | Thủ tục ghi vào Sổ hộ tịch việc kết hôn của công dân Việt Nam đã được giải quyết tại cơ quan có thẩm quyền của nước ngoài | ✔ | Xã / điểm TN cấp xã | Canonical: trống; DVCQG ghi "0 — mức cụ thể do HĐND quyết định" | 0 đồng | Điều 2 khoản 1 điểm a | Áp dụng | Cao |
| 17 | 1.012796 | Đính chính Giấy chứng nhận đã cấp lần đầu có sai sót | ✔ | Xã | Canonical: trống; DVCQG ghi "0 — theo Luật Phí và lệ phí" | 0 đồng | Điều 2 khoản 1 điểm c; Điều 2 khoản 2 điểm b | Áp dụng nếu phát sinh | Thấp |
| 18 | 1.012818 | Thu hồi Giấy chứng nhận đã cấp lần đầu không đúng quy định của pháp luật đất đai do người sử dụng đất, chủ sở hữu tài sản gắn liền với đất phát hiện và cấp lại Giấy chứng nhận sau khi thu hồi | ✔ | Xã | Canonical: trống; DVCQG ghi "0 — theo Luật Phí và lệ phí" | 0 đồng | Điều 2 khoản 1 điểm c; Điều 2 khoản 2 điểm b | Áp dụng nếu phát sinh | Thấp |
| 19 | 1.013978 | Đăng ký đất đai, tài sản gắn liền với đất, cấp Giấy chứng nhận quyền sử dụng đất, quyền sở hữu tài sản gắn liền với đất lần đầu đối với hộ gia đình, cá nhân, cộng đồng dân cư, người gốc Việt Nam định cư ở nước ngoài | ✔ | Xã | Canonical: trống; DVCQG ghi "0 — theo Luật Phí và lệ phí" | 0 đồng | Điều 2 khoản 1 điểm c; Điều 2 khoản 2 điểm b | Áp dụng | Cao |
| 20 | 1.000419 | Thủ tục đăng ký khai tử lưu động |  | Xã | Canonical: trống; hướng dẫn: chưa có | 0 đồng | Điều 2 khoản 1 điểm a | Áp dụng nếu nộp trực tuyến được | Thấp |
| 21 | 1.003583 | Thủ tục đăng ký khai sinh lưu động |  | Xã | Canonical: trống; hướng dẫn: chưa có | 0 đồng | Điều 2 khoản 1 điểm a | Áp dụng nếu nộp trực tuyến được | Thấp |
| 22 | 1.012753 | Đăng ký đất đai, tài sản gắn liền với đất, cấp Giấy chứng nhận quyền sử dụng đất, quyền sở hữu tài sản gắn liền với đất lần đầu đối với tổ chức đang sử dụng đất |  | Xã | Canonical: trống; hướng dẫn: chưa có | 0 đồng | Điều 2 khoản 1 điểm c; Điều 2 khoản 2 điểm b | Áp dụng | Cao |
| 23 | 1.012756 | Đăng ký đất đai lần đầu đối với trường hợp được Nhà nước giao đất để quản lý |  | Xã / điểm TN cấp xã | Canonical: trống; hướng dẫn: chưa có | 0 đồng | Điều 2 khoản 1 điểm c; Điều 2 khoản 2 điểm b | Áp dụng nếu phát sinh | Thấp |
| 24 | 1.012781 | Đăng ký, cấp Giấy chứng nhận đối với thửa đất có diện tích tăng thêm do thay đổi ranh giới so với Giấy chứng nhận đã cấp |  | Xã / điểm TN cấp xã | Canonical: trống; hướng dẫn: chưa có | 0 đồng | Điều 2 khoản 1 điểm c; Điều 2 khoản 2 điểm b | Áp dụng | Cao |
| 25 | 1.012782 | Đăng ký, cấp Giấy chứng nhận đối với trường hợp cá nhân, hộ gia đình đã được cấp Giấy chứng nhận một phần diện tích vào loại đất ở trước |  | Xã / điểm TN cấp xã | Canonical: trống; hướng dẫn: chưa có | 0 đồng | Điều 2 khoản 1 điểm c; Điều 2 khoản 2 điểm b | Áp dụng | Cao |
| 26 | 1.012783 | Cấp đổi Giấy chứng nhận quyền sử dụng đất, quyền sở hữu tài sản gắn liền với đất |  | Xã / điểm TN cấp xã | Canonical: trống; hướng dẫn: chưa có | 0 đồng | Điều 2 khoản 1 điểm c; Điều 2 khoản 2 điểm b | Áp dụng | Cao |
| 27 | 1.012785 | Đăng ký, cấp Giấy chứng nhận đối với trường hợp đã chuyển quyền sử dụng đất trước |  | Xã / điểm TN cấp xã | Canonical: trống; hướng dẫn: chưa có | 0 đồng | Điều 2 khoản 1 điểm c; Điều 2 khoản 2 điểm b | Áp dụng | Cao |
| 28 | 1.012786 | Cấp lại Giấy chứng nhận do bị mất |  | Xã / điểm TN cấp xã | Canonical: trống; hướng dẫn: chưa có | 0 đồng | Điều 2 khoản 1 điểm c; Điều 2 khoản 2 điểm b | Áp dụng | Cao |
| 29 | 1.012787 | Đăng ký, cấp Giấy chứng nhận quyền sử dụng đất, quyền sở hữu tài sản gắn liền với đất cho người nhận chuyển nhượng quyền sử dụng đất, quyền sở hữu nhà ở, công trình xây |  | Xã / điểm TN cấp xã | Canonical: trống; hướng dẫn: chưa có | 0 đồng | Điều 2 khoản 1 điểm c; Điều 2 khoản 2 điểm b | Áp dụng | Cao |
| 30 | 1.012790 | Đính chính Giấy chứng nhận đã cấp |  | Xã / điểm TN cấp xã | Canonical: trống; hướng dẫn: chưa có | 0 đồng | Điều 2 khoản 1 điểm c; Điều 2 khoản 2 điểm b | Áp dụng nếu phát sinh | Thấp |
| 31 | 1.012791 | Thu hồi Giấy chứng nhận đã cấp không đúng quy định của pháp luật đất đai do người sử dụng đất, chủ sở hữu tài sản gắn liền với đất phát hiện và cấp lại Giấy chứng nhận s |  | Xã / điểm TN cấp xã | Canonical: trống; hướng dẫn: chưa có | 0 đồng | Điều 2 khoản 1 điểm c; Điều 2 khoản 2 điểm b | Áp dụng nếu phát sinh | Thấp |
| 32 | 1.012793 | Đăng ký biến động đối với trường hợp thành viên của hộ gia đình hoặc cá nhân đang sử dụng đất thành lập doanh nghiệp tư nhân và sử dụng đất vào hoạt động sản xuất kinh d |  | Xã / điểm TN cấp xã | Canonical: trống; hướng dẫn: chưa có | 0 đồng | Điều 2 khoản 1 điểm c; Điều 2 khoản 2 điểm b | Áp dụng nếu phát sinh | Trung bình |
| 33 | 1.012817 | Xác định lại diện tích đất ở của hộ gia đình, cá nhân đã được cấp Giấy chứng nhận trước ngày 01 tháng 7 năm 2004 |  | Xã | Canonical: trống; hướng dẫn: chưa có | 0 đồng | Điều 2 khoản 1 điểm c; Điều 2 khoản 2 điểm b | Áp dụng nếu phát sinh | Thấp |
| 34 | 1.013831 | Đăng ký biến động quyền sử dụng đất, quyền sở hữu tài sản gắn liền với đất trong các trường hợp chuyển đổi quyền sử dụng đất nông nghiệp mà không theo phương án dồn điền |  | Xã / điểm TN cấp xã | Canonical: trống; hướng dẫn: chưa có | 0 đồng | Điều 2 khoản 1 điểm c; Điều 2 khoản 2 điểm b | Áp dụng nếu phát sinh | Trung bình |
| 35 | 1.013833 | Đăng ký biến động đối với trường hợp đổi tên hoặc thay đổi thông tin về người sử dụng đất, chủ sở hữu tài sản gắn liền với đất hoặc thay đổi số hiệu hoặc địa chỉ của thử |  | Xã / điểm TN cấp xã | Canonical: trống; hướng dẫn: chưa có | 0 đồng | Điều 2 khoản 1 điểm c; Điều 2 khoản 2 điểm b | Áp dụng nếu phát sinh | Trung bình |
| 36 | 1.013977 | Đăng ký biến động thay đổi quyền sử dụng đất, quyền sở hữu tài sản gắn liền với đất do chia, tách, hợp nhất, sáp nhập tổ chức hoặc chuyển đổi mô hình tổ chức, chuyển đổi |  | Xã / điểm TN cấp xã | Canonical: trống; hướng dẫn: chưa có | 0 đồng | Điều 2 khoản 1 điểm c; Điều 2 khoản 2 điểm b | Áp dụng nếu phát sinh | Trung bình |
| 37 | 1.013979 | Tặng cho quyền sử dụng đất cho Nhà nước hoặc cộng đồng dân cư hoặc mở rộng đường giao thông đối với trường hợp thửa đất chưa được cấp Giấy chứng nhận |  | Xã | Canonical: trống; hướng dẫn: chưa có | 0 đồng | Điều 2 khoản 1 điểm c; Điều 2 khoản 2 điểm b | Áp dụng nếu phát sinh | Thấp |
| 38 | 1.013980 | Đăng ký biến động đối với trường hợp thay đổi quyền sử dụng đất, quyền sở hữu tài sản gắn liền với đất theo thỏa thuận của các thành viên hộ gia đình hoặc của vợ và chồn |  | Xã / điểm TN cấp xã | Canonical: trống; hướng dẫn: chưa có | 0 đồng | Điều 2 khoản 1 điểm c; Điều 2 khoản 2 điểm b | Áp dụng nếu phát sinh | Trung bình |
| 39 | 1.013988 | Xóa ghi nợ tiền sử dụng đất, lệ phí trước bạ trên Giấy chứng nhận đã cấp |  | Xã / điểm TN cấp xã | Canonical: trống; hướng dẫn: chưa có | 0 đồng | Điều 2 khoản 1 điểm c; Điều 2 khoản 2 điểm b | Áp dụng nếu phát sinh | Thấp |
| 40 | 1.013992 | Đăng ký biến động chuyển mục đích sử dụng đất không phải xin phép cơ quan nhà nước có thẩm quyền |  | Xã / điểm TN cấp xã | Canonical: trống; hướng dẫn: chưa có | 0 đồng | Điều 2 khoản 1 điểm c; Điều 2 khoản 2 điểm b | Áp dụng nếu phát sinh | Trung bình |
| 41 | 1.013993 | Đăng ký, cấp Giấy chứng nhận đối với trường hợp hộ gia đình, cá nhân đang sử dụng đất không đúng mục đích đã được Nhà nước công nhận quyền sử dụng đất trước |  | Xã / điểm TN cấp xã | Canonical: trống; hướng dẫn: chưa có | 0 đồng | Điều 2 khoản 1 điểm c; Điều 2 khoản 2 điểm b | Áp dụng | Cao |
| 42 | 1.013994 | Đăng ký, cấp Giấy chứng nhận đối với trường hợp chuyển nhượng dự án đầu tư có sử dụng đất |  | Xã / điểm TN cấp xã | Canonical: trống; hướng dẫn: chưa có | 0 đồng | Điều 2 khoản 1 điểm c; Điều 2 khoản 2 điểm b | Áp dụng | Cao |
| 43 | 1.013995 | Đăng ký tài sản gắn liền với thửa đất đã được cấp Giấy chứng nhận hoặc đăng ký thay đổi về tài sản gắn liền với đất so với nội dung đã đăng ký, gia hạn thời hạn sở hữu n |  | Xã / điểm TN cấp xã | Canonical: trống; hướng dẫn: chưa có | 0 đồng | Điều 2 khoản 1 điểm c; Điều 2 khoản 2 điểm b | Áp dụng nếu phát sinh | Trung bình |
| 44 | 1.011441 | Đăng ký biện pháp bảo đảm bằng quyền sử dụng đất, tài sản gắn liền với đất |  | Xã / điểm TN cấp xã | Canonical: trống; hướng dẫn: chưa có | 0 đồng | Điều 2 khoản 2 điểm a | Áp dụng | Trung bình |
| 45 | 1.011442 | Đăng ký thay đổi biện pháp bảo đảm bằng quyền sử dụng đất, tài sản gắn liền với đất |  | Xã / điểm TN cấp xã | Canonical: trống; hướng dẫn: chưa có | 0 đồng | Điều 2 khoản 2 điểm a | Áp dụng | Trung bình |
| 46 | 1.011443 | Xoá Đăng ký biện pháp bảo đảm bằng quyền sử dụng đất, tài sản gắn liền với đất |  | Xã / điểm TN cấp xã | Canonical: trống; hướng dẫn: chưa có | 0 đồng | Điều 2 khoản 2 điểm a | Áp dụng | Trung bình |
| 47 | 1.011445 | Chuyển tiếp đăng ký thế chấp quyền tài sản phát sinh từ hợp đồng mua bán nhà ở hoặc từ hợp đồng mua bán tài sản khác gắn liền với đất |  | Xã / điểm TN cấp xã | Canonical: trống; hướng dẫn: chưa có | 0 đồng | Điều 2 khoản 2 điểm a | Áp dụng | Trung bình |

## 3. Việc cần làm trước khi đề xuất promotion

1. Bổ sung mức thu trực tiếp hiện hành (NQ HĐND về lệ phí hộ tịch, lệ phí cấp GCN, phí thẩm định hồ sơ cấp GCN, phí đăng ký giao dịch bảo đảm) làm evidence riêng.
2. Chốt schema cho `phiOnline` (giá trị + điều kiện kênh DVCQG/VNeID + ngày hiệu lực + evidenceId) qua review canonical contract.
3. Review nghiệp vụ các dòng Trung bình/Thấp; dòng 2.000635 cần xác minh phí cấp bản sao trích lục có thuộc thẩm quyền HĐND hay không.
4. Chỉ promote sau khi merge; Google Sheets nhận thay đổi qua pipeline sync hiện có, không sửa tay.
