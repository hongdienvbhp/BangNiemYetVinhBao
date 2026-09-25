# Công khai bảng niêm yết TTHC trên Google Firebase Hosting

## 1. Kiến trúc

`data/thu-tuc.json` (canonical) → `scripts/check_static_site.py` → `scripts/build_site.py` (đóng gói 12 tài nguyên runtime vào `_site/`) → `.github/workflows/firebase-hosting.yml` → Firebase Hosting (`https://<PROJECT_ID>.web.app`).

- GitHub vẫn là nơi lưu mã nguồn và dữ liệu canonical; Firebase chỉ là nơi phục vụ bản công khai.
- Google Sheets vẫn là read model phục vụ đối soát/báo cáo (xem `GOOGLE_SHEETS_TTHC_PIPELINE.md`), không phải nguồn của website.
- Pull Request chỉ build + kiểm tra; chỉ push vào `main` hoặc chạy thủ công mới deploy.
- Xác thực OIDC + Workload Identity Federation; **không** tạo/lưu service-account key.

## 2. Việc cần làm một lần trên Google (tài khoản Google của Trung tâm)

| Bước | Việc | Nơi thực hiện |
|---|---|---|
| 1 | Tạo dự án Firebase (hoặc "Add Firebase" vào dự án Google Cloud đang dùng cho Sheets sync). Gói **Spark (miễn phí)** là đủ. | console.firebase.google.com |
| 2 | Vào **Hosting → Get started** để kích hoạt Hosting (không cần làm các bước CLI trên màn hình). | Firebase Console |
| 3 | Cấp vai trò **Firebase Hosting Admin** (`roles/firebasehosting.admin`) và **API Keys Viewer** (`roles/serviceusage.apiKeysViewer`) cho service account dùng để deploy (mặc định dùng lại `GOOGLE_SERVICE_ACCOUNT` của Sheets sync). | Google Cloud Console → IAM của dự án Firebase |
| 4 | Nếu dự án Firebase khác dự án chứa Workload Identity Pool: không cần tạo pool mới, chỉ cần bước 3. | — |
| 5 | Khai báo repository variable `FIREBASE_PROJECT_ID` = Project ID của Firebase. | GitHub → Settings → Secrets and variables → Actions → Variables |
| 6 | Chạy workflow **Deploy Firebase Hosting** (Run workflow) hoặc merge một thay đổi vào `main`. | GitHub Actions |

Tùy chọn: dùng service account/provider riêng cho Firebase qua `FIREBASE_SERVICE_ACCOUNT`, `FIREBASE_WIF_PROVIDER`.

Tên miền riêng (ví dụ tên miền `.gov.vn` của xã): Firebase Console → Hosting → Add custom domain, sau đó bộ phận quản lý tên miền thêm bản ghi DNS theo hướng dẫn. [cần bổ sung: tên miền được cấp]

## 3. Kiểm tra sau deploy

Workflow tự kiểm tra `/`, `/data/thu-tuc.json`, `/js/app.js` trả về HTTP 200 và ghi URL vào Job Summary. Nếu thiếu `FIREBASE_PROJECT_ID`, workflow cảnh báo và bỏ qua deploy (không báo lỗi).

## 4. Chuyển đổi từ GitHub Pages

1. Chạy song song GitHub Pages và Firebase cho đến khi Firebase deploy thành công và được nghiệm thu.
2. Cập nhật đường dẫn công khai (QR tại quầy, cổng thông tin xã) sang địa chỉ Firebase/tên miền riêng.
3. Sau đó mới tắt `pages.yml` qua một PR riêng.

## 5. Chạy cục bộ

```bash
python scripts/check_static_site.py
python scripts/build_site.py --out _site
npx firebase-tools@15.31.0 emulators:start --only hosting   # xem thử tại http://localhost:5000
```
