# Canonical TTHC Architecture — CLOSED 20/09/2026

## Phạm vi

Chuỗi canonical đã khép kín: `BangNiemYetVinhBao → tthc-monitor / CongkhaiTTHC / thutuchanhchinh`.

## Bằng chứng nguồn chuẩn

- Canonical contract: `data/thu-tuc.json`.
- `dataset_version`: `2026.09.18`.
- `source_commit`: `d720f07659f8571e03f16ecdb3cc914598550c57`.
- Tổng số TTHC canonical: 254.
- TTHC trọng điểm hiện hành (`priority51=true`): 50.
- Mã `2.001009` đã bãi bỏ: không tồn tại trong canonical hiện hành.
- Validator canonical trên clean `BangNiemYetVinhBao/main@6370637`: PASS; 4/4 unit tests PASS; `git diff --check` PASS.

## Consumer

### tthc-monitor

- `main@ed95aab` mặc định đọc trực tiếp canonical live từ `BangNiemYetVinhBao/main/data/thu-tuc.json`.
- Output mang `dataset_version/source_commit`.
- Khi dùng canonical local, hệ thống kiểm tra độ mới so với nguồn live và cảnh báo nếu lệch.
- CI gate chặn Master TTHC riêng.
- Kiểm thử độc lập trên clean `origin/main@ed95aab` bằng đúng Python 3.12.10: gate PASS, compile PASS, 40/40 unit tests PASS, `git diff --check` PASS, working tree sạch.
- GitHub-hosted Actions endpoint không truy xuất được từ executor hiện tại; việc này chỉ là giới hạn quan sát của môi trường, không còn là blocker kỹ thuật sau khi exact-head workflow-equivalent validation đã PASS.

### CongkhaiTTHC

- Chỉ đọc canonical `BangNiemYetVinhBao/main/data/thu-tuc.json`.
- Kiểm tra `dataset_version/source_commit`.
- Có gate chống Master TTHC riêng.
- PR #97 đã merge; exact-head CI và Secret Scan đã SUCCESS.
- Không có thay đổi canonical nào sau commit đã được CI xác minh.

### thutuchanhchinh

- Chỉ render view/filter theo `priority51 === true`.
- Hiển thị `dataset_version/source_commit`.
- Không còn fallback 51 TTHC hard-code.
- Có gate chống Master TTHC riêng.
- PR #27 đã merge; exact-head workflow “Kiểm tra preview TTHC” SUCCESS, gồm bước validate canonical view và reject private Master.

## GitHub / Linear

- GitHub đã cập nhật đầy đủ các commit canonical và closure record trên `main`.
- Đã rà soát repo, lịch sử công việc và Library nhưng không tồn tại Linear project/issue identifier cụ thể cho work package canonical này. Theo nguyên tắc không tạo tracker trùng, không tạo Linear item mới chỉ để đóng thủ tục. Trạng thái Linear của work package này: `N/A — no existing tracker identified`.

## Definition of Done

- Một canonical source: PASS.
- Version/source commit xuyên consumer: PASS.
- Không Master TTHC riêng: PASS.
- 50 TTHC trọng điểm hiện hành đồng bộ: PASS.
- TTHC đã bãi bỏ không tái xuất hiện: PASS.
- End-to-end / contract validation: PASS.
- Consumer gates: PASS.
- GitHub checkpoint: PASS.
- Linear: N/A, không có tracker hiện hữu để cập nhật.
- Blocker kỹ thuật: 0.
- NEXT_SAFE_ACTION: maintenance only; chỉ mở lại khi canonical có thay đổi chính thức hoặc phát hiện regression.

## Hậu kiểm sau closure

- `BangNiemYetVinhBao/main@3754c86`: validator canonical PASS; 4/4 contract tests PASS; dataset giữ 254 TTHC, 50 TTHC trọng điểm hiện hành.
- `tthc-monitor/main@ed95aab`: kiểm thử lại trên clean origin/main, gate chống Master PASS, compile PASS, 40/40 tests PASS.
- `CongkhaiTTHC/main@614a83a`: không phát hiện Master TTHC riêng; `canonical:check` vẫn hiện diện.
- `thutuchanhchinh/main@c21d1b9`: loại toàn bộ hard-code user-facing “51 thủ tục” ở trang phụ; mẫu số hiển thị chuyển sang `priorityProcedures.length`; hậu kiểm không còn chuỗi UI cũ.
- Đã xóa các remote branch canonical/priority đã merge hoặc bị main thay thế:
  - `BangNiemYetVinhBao`: `feat/issue-6-priority51-formality`, `feat/issue-8-priority51-legal-verification`, `fix/canonical-tthc-integrity-20260920`, `fix/dvcqg-priority51-reconcile-20260920`.
  - `CongkhaiTTHC`: `data/verify-priority-51-batch-04`, `data/verify-priority-51-batch-20`, `feat/priority51-publication-readiness`, `feat/priority51-review-queue`, `feat/priority51-verified-enrichment`.
- Các branch verification batch chưa merge còn lại của `CongkhaiTTHC` được giữ nguyên như hồ sơ lịch sử cho đến khi có archive/reconciliation rõ ràng; không được coi là nguồn runtime hoặc canonical.

## Kết luận

**CANONICAL TTHC ARCHITECTURE CLOSED.**
