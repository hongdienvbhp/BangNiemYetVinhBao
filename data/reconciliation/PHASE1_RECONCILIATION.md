# PHASE 1 — RECONCILIATION TTHC

- Canonical dataset: `2026.10.09`
- Baseline: 2026-07-20 — 323 TTHC (257 cấp xã + 66 dùng chung)
- Canonical hiện có: **536** bản ghi
- Mã có khả năng thuộc Phase 1: **321**
- TTHC cấp tỉnh ngoài Phase 1: **215**
- Mã được parser heading chính thức phân loại: **36**
- Xung đột phân loại với evidence chính thức: **3**
- Nhãn còn mơ hồ xã/dùng chung: **129**
- Số thiếu tối thiểu so với baseline aggregate: **2**
- Tổng hợp chính thức mới nhất (Q3/2026): **348** TTHC cấp xã + dùng chung; thiếu tối thiểu: **27**

## Kết luận

Chưa được phép sinh danh sách MISSING theo mã chỉ từ phép trừ số lượng. Parser heading chỉ nhận phân loại có section heading chính thức rõ ràng; địa điểm tiếp nhận tại cấp xã không được dùng để suy ra thẩm quyền.

## MISCLASSIFIED theo evidence hiện có

| Mã | Nhãn hiện tại | Evidence | Phân loại đúng |
|---|---|---|---|
| 1.002407 | Cấp tỉnh - tiếp nhận tại Trung tâm PVHCC cấp xã | 1635/QĐ-UBND (2026-04-24) | SHARED |
| 1.012531 | Xã | 541/QĐ-UBND (2026-02-07) | PROVINCE |
| 2.002020 | Xã / điểm tiếp nhận cấp xã | 3204/QĐ-UBND (2026-08-11) | PROVINCE |

## Gate tiếp theo

1. Mở rộng parser trên toàn bộ phụ lục chính thức để tăng coverage.
2. Materialize authoritative 323-code baseline.
3. Chốt MATCHED/MISSING/EXTRA/MISCLASSIFIED theo Mã TTHC.
4. Gán authorityLevel/serviceScope/onlineServiceLevel + provenance.
5. Chỉ migrate canonical v5 sau khi validator PASS.
