# Pipeline canonical TTHC → Google Sheets

## 1. Vai trò kiến trúc

`BangNiemYetVinhBao` tiếp tục là owner của chuỗi **official-source ingestion → evidence/provenance → normalization → canonical Master Data → delta/validation**.

Hai Google Sheets là **read model**, không phải nguồn sự thật và không được write-back ngược vào canonical:

- File cấp xã: danh mục thuộc thẩm quyền cấp xã.
- File cấp thành phố: danh mục thuộc thẩm quyền cấp thành phố.

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

Cần một Google Cloud service account có quyền Google Sheets API. Repository secrets:

- `GOOGLE_SERVICE_ACCOUNT_JSON`: toàn bộ JSON key của service account.
- `TTHC_SHEET_CAP_XA_ID`: ID file Google Sheet cấp xã.
- `TTHC_SHEET_CAP_TP_ID`: ID file Google Sheet cấp thành phố.

Cần share **Editor** hai file Google Sheets cho email `client_email` trong service-account JSON.

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

## 8. Nguồn chính thức

Source registry hiện ưu tiên cổng thuộc hệ thống Hải Phòng/Vĩnh Bảo và PDF trên `cdn.haiphong.gov.vn`. DVCQG được dùng để đối chiếu định danh/kỹ thuật khi có đường dẫn xác minh; không quyết định hiệu lực pháp lý.

Hai đường tra cứu chính thức Hải Phòng trên DVCQG hiện tương ứng:
- cấp tỉnh: `cap_thuc_hien=1&co_quan_cong_bo=387628`;
- cấp xã: `cap_thuc_hien=3&co_quan_cong_bo=387628`.

Do endpoint công khai có thể trả lỗi/không ổn định cho machine access, pipeline không phụ thuộc duy nhất vào endpoint này.
