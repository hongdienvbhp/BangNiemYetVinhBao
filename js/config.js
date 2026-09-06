/**
 * Cấu hình đồng bộ dữ liệu định kỳ
 * — Không dùng API Cổng DVC (không có API công khai).
 * — Nguồn khuyến nghị: Google Sheet xuất CSV công khai, hoặc file JSON trên cùng host.
 *
 * Cách bật Google Sheet:
 * 1. Tạo sheet với dòng 1 (header):
 *    ma | ten | linhVuc | cap | nhanh | mienPhiTrucTuyen | phiDiaGioi | lienThong | phi | phiOnline | thoiHan | qd
 * 2. File → Chia sẻ → Bất kỳ ai có đường liên kết (người xem)
 * 3. File → Chia sẻ → Xuất bản lên web → định dạng CSV → lấy link
 *    hoặc dùng: https://docs.google.com/spreadsheets/d/SHEET_ID/export?format=csv&gid=0
 * 4. Dán link vào remoteCsvUrl bên dưới.
 *
 * Cách dùng file JSON trên host (cập nhật tay / CI):
 *  - Đặt file data/thu-tuc.json ({ updatedAt, source, thuTuc: [...] })
 *  - Gán remoteJsonUrl = "data/thu-tuc.json"
 */
window.TTHC_CONFIG = {
  /** URL CSV (Google Sheet xuất bản). Để "" nếu chưa dùng. */
  remoteCsvUrl: "",

  /** URL JSON (mảng thủ tục hoặc object { thuTuc: [...] }). Chỉ bật khi file Master Data đã được tạo và kiểm duyệt. */
  remoteJsonUrl: "",

  /** Số giờ giữ cache localStorage trước khi tải lại nguồn remote */
  refreshHours: 12,

  /** Tự tải lại nền khi mở trang nếu cache hết hạn */
  autoSyncOnLoad: true,

  /** Khóa cache (đổi version khi schema dữ liệu đổi) */
  cacheKey: "tthc_vinhbao_v2"
};
