# PHASE 1 — RECONCILIATION TTHC

- Canonical dataset: `2026.09.21`
- Baseline: 2026-07-20 — 323 TTHC (257 cấp xã + 66 dùng chung)
- Canonical hiện có: **254** bản ghi
- Mã có khả năng thuộc Phase 1: **199**
- TTHC cấp tỉnh ngoài Phase 1: **55**
- Mã được parser heading chính thức phân loại: **36**
- Xung đột phân loại với evidence chính thức: **0**
- Nhãn còn mơ hồ xã/dùng chung: **149**
- Số thiếu tối thiểu so với baseline aggregate: **124**

## Kết luận

Chưa được phép sinh danh sách MISSING theo mã chỉ từ phép trừ số lượng. Parser heading chỉ nhận phân loại có section heading chính thức rõ ràng; địa điểm tiếp nhận tại cấp xã không được dùng để suy ra thẩm quyền.

## MISCLASSIFIED theo evidence hiện có

Không còn mã MISCLASSIFIED sau khi canonical builder áp dụng lớp heading phụ lục chính thức.

## Gate tiếp theo

1. Mở rộng parser trên toàn bộ phụ lục chính thức để tăng coverage.
2. Materialize authoritative 323-code baseline.
3. Chốt MATCHED/MISSING/EXTRA/MISCLASSIFIED theo Mã TTHC.
4. Gán authorityLevel/serviceScope/onlineServiceLevel + provenance.
5. Chỉ migrate canonical v5 sau khi validator PASS.
