# Pipeline canonical TTHC → Google Sheets

## 1. Vai trò kiến trúc

`BangNiemYetVinhBao` tiếp tục là owner của chuỗi **official-source ingestion → evidence/provenance → normalization → canonical Master Data → delta/validation**.

Hai Google Sheets là **read model**, không phải nguồn sự thật và không được write-back ngược vào canonical:

- `01_Danh_muc_TTHC_cap_xa_Vinh_Bao` — ID `1tUBoVAWEZcqTD6onoeN-PJVmy_Ffz_CAav9u1-aKIYA`.
- `02_Danh_muc_TTHC_cap_thanh_pho_Hai_Phong` — ID `1PhUDRljGGErXnolqxRj9jPdJSacLFkBTGFJjUBTqVXk`.

Mỗi file giữ 6 sheet nghiệp vụ (`01_CHI_TIET_TTHC` đến `06_TONG_HOP_CHUNG`) và 2 sheet kỹ thuật `NGUON_DU_LIEU`, `NHAT_KY_CAP_NHAT`. Live sync chỉ được ghi vào file đích đã kiểm tra đúng header/schema.

Luồng chuẩn:

`official source → source-index → decision-manifest/PDF/hash → extract → canonical Master Data → delta → CI/review gate → merge main → Google Sheets sync → nhật ký/cảnh báo`

### Integration boundary trong hệ sinh thái Vĩnh Bảo

- `BangNiemYetVinhBao`: canonical owner của danh mục TTHC, evidence/provenance, trạng thái kiểm chứng và publication projection.
- `tthc-monitor`: consumer read-only của Master TTHC; owner của snapshot hồ sơ, mapping trách nhiệm theo dõi, cảnh báo sắp hạn/quá hạn và báo cáo giám sát. Không write-back dữ liệu TTHC hoặc hồ sơ vào `BangNiemYetVinhBao`.
- Vĩnh Bảo AI Operating System: governance/integration/orchestration hub khi kết nối các dự án; không tạo thêm Master TTHC cạnh tranh và không thay đổi ownership nghiệp vụ của hai repository trên.
- Google Sheets: terminal read model phục vụ công khai, đối soát và báo cáo; không phải integration source và không write-back canonical.

Mọi tích hợp sau này phải đi theo `canonical source → shared interface/integration layer → consumer/view`, không đồng bộ vòng tròn giữa các repository.

## 2. Cổng an toàn

1. Chỉ chạy live sync sau khi thay đổi canonical đã merge vào `main`.
2. Identity bắt buộc là **Mã TTHC**.
3. Không suy diễn hiệu lực từ DVCQG hoặc dữ liệu legacy.
4. Không xóa một dòng đang có trên Sheet chỉ vì nó biến mất khỏi projection mới. Dòng đó được giữ lại và đổi trạng thái `Cần xác minh`.
5. Cột nghiệp vụ do Trung tâm quản trị được giữ nguyên khi canonical không sở hữu dữ liệu đó:
   - Bộ/ngành quản lý;
   - Quy trình nội bộ;
   - Thời gian sau rút ngắn;
   - Lệ phí;
   - Quy trình ISO;
   - Mã lĩnh vực/nhóm báo cáo;
   - Đã công khai tại Trung tâm?;
   - Người cập nhật;
   - Ghi chú chi tiết.
6. Mọi thay đổi tự động được append vào `NHAT_KY_CAP_NHAT`.
7. Các trạng thái `needs_*`, thiếu mã, xung đột scope, trạng thái excluded không xác định được đưa vào review queue.
8. File cấp thành phố hiện có safety gate `PARTIAL_BASELINE`. Workflow **không live-sync city** cho đến khi baseline cấp thành phố được kiểm chứng đầy đủ và biến repository `TTHC_CITY_BASELINE_COMPLETE=true`.

## 3. Trạng thái TTHC

- `Còn hiệu lực`: nằm trong canonical public hiện hành.
- `Bãi bỏ`: có bằng chứng chính thức về bãi bỏ.
- `Hết hiệu lực`: chỉ dùng khi canonical có căn cứ tương ứng.
- `Chưa hiệu lực`: đã công bố nhưng ngày hiệu lực ở tương lai.
- `Cần xác minh`: không đủ bằng chứng để tự động quyết định; không tự xóa hoặc coi là bãi bỏ.

Các sheet 02–04 lọc duy nhất `Còn hiệu lực`. Sheet chi tiết và tổng hợp giữ lịch sử các trạng thái khác.

## 4. Credential để GitHub Actions ghi Google Sheets

Cần một Google Cloud service account có quyền Google Sheets API. **Secret bắt buộc duy nhất cho xác thực**:

- `GOOGLE_SERVICE_ACCOUNT_JSON`: toàn bộ JSON key của service account, lưu bằng GitHub Actions Secret; tuyệt đối không commit vào repository.

Hai production Sheet ID đã được cấu hình làm default trong workflow. Có thể override bằng repository variables `TTHC_SHEET_CAP_XA_ID` và `TTHC_SHEET_CAP_TP_ID` khi đổi file đích.

Trước live sync phải share **Editor** cả hai file cho `client_email` trong service-account JSON. Đây là thao tác quyền Google bắt buộc, không thể thay thế bằng việc chỉ biết Sheet ID.

Repository variable:

- `TTHC_CITY_BASELINE_COMPLETE=false` ở giai đoạn hiện tại.
- Chỉ chuyển `true` sau khi đã kiểm chứng baseline city đầy đủ.

Không commit credential, refresh token hoặc service-account key vào repository.

## 5. Chạy kiểm tra

~~~bash
python -m unittest tests.test_google_sheets_projection -v
PYTHONPATH=scripts python scripts/google_sheets_projection.py > /tmp/google-sheets-plan.json
~~~

Dry-run không cần credential:

~~~bash
PYTHONPATH=scripts python scripts/sync_google_sheets.py --dry-run --plan-out /tmp/google-sheets-plan.json
~~~

Live sync sau khi credential đã cấu hình:

~~~bash
export GOOGLE_SERVICE_ACCOUNT_JSON='...'
export TTHC_SHEET_CAP_XA_ID='...'
export TTHC_SHEET_CAP_TP_ID='...'
export TTHC_CITY_BASELINE_COMPLETE='false'
PYTHONPATH=scripts python scripts/sync_google_sheets.py --plan-out /tmp/google-sheets-plan.json
~~~

## 6. Google Sheets ownership

Script chỉ ghi tự động các cột canonical/evidence. Hai cột có công thức tại Sheet chi tiết phải được giữ:

- cột A `STT`;
- cột AA `Cần đối soát?`.

Live sync chỉ clear/write các vùng `B:Z` và `AB:AC`, vì vậy không ghi đè hai cột công thức này.

## 7. Cảnh báo và xử lý ngoại lệ

- Thiếu credential: workflow fail trước khi ghi dữ liệu và tạo Issue một lần.
- Review queue có mục chưa chắc chắn: dữ liệu đã xác minh vẫn được đồng bộ; workflow tạo Issue cảnh báo.
- Lỗi Google API/header mismatch: workflow fail; không được coi là sync thành công.
- Header Sheet chi tiết phải đúng 29 cột canonical. Sai header là blocker để tránh ghi lệch cột.
- City baseline chưa đầy đủ: city sync bị skip có chủ đích; không coi dataset quan sát được là danh mục thành phố đầy đủ.
- Workflow live-sync bị khóa ở `main`: chạy trên branch/PR chỉ validate/dry-run, kể cả khi người dùng bấm `workflow_dispatch` trên feature branch.
- Muốn ghi thật cả 02 file: `GOOGLE_SERVICE_ACCOUNT_JSON` phải tồn tại, cả hai file phải share Editor cho `client_email`, và `TTHC_CITY_BASELINE_COMPLETE=true` chỉ được bật sau khi đối chiếu đủ danh mục cấp thành phố từ các nguồn chính thức mở rộng.

## 8. Nguồn chính thức

Source registry áp dụng 3 lớp:

1. **Primary decision listing**: trang công khai TTHC của các Sở quản lý chuyên ngành (Tư pháp, Tài chính, Nội vụ, Khoa học và Công nghệ, Công Thương, Y tế, Văn hóa-Thể thao-Du lịch, Nông nghiệp và Môi trường, Giáo dục và Đào tạo) để phát hiện quyết định công bố và tài liệu chính thức.
2. **Procedure catalog**: danh mục TTHC trực tiếp của Sở Xây dựng, Giáo dục và các nguồn tương tự để đối chiếu Mã TTHC, cấp thực hiện và độ phủ; không tự quyết định hiệu lực.
3. **Official local mirror**: trang công khai TTHC của Vĩnh Bảo và các xã/phường/đặc khu Hải Phòng như Đại Sơn, Nhị Chiểu, An Dương, Ngô Quyền, Gia Viên, Bạch Long Vỹ, Cát Hải, Thạch Khôi để phát hiện sớm và đối chiếu chéo. Mirror không được tự ghi đè căn cứ pháp lý từ nguồn có thẩm quyền.

PDF bằng chứng chỉ được tự tải từ host cho phép `cdn.haiphong.gov.vn`; mỗi bản ghi giữ `sourceId`, cơ quan nguồn, loại nguồn, mục đích sử dụng và URL bài viết để truy vết provenance.

DVCQG được dùng để đối chiếu định danh/kỹ thuật và kiểm tra độ phủ khi có đường dẫn xác minh; không quyết định hiệu lực pháp lý.

Hai đường tra cứu chính thức Hải Phòng trên DVCQG hiện tương ứng:
- cấp tỉnh: `cap_thuc_hien=1&co_quan_cong_bo=387628`;
- cấp xã: `cap_thuc_hien=3&co_quan_cong_bo=387628`.

Do endpoint công khai có thể trả lỗi/không ổn định cho machine access, pipeline không phụ thuộc duy nhất vào endpoint này.
