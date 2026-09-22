# PHASE 1 — RECONCILIATION TTHC

- Canonical dataset: `2026.09.21`
- Baseline: 2026-07-20 — 323 TTHC (257 cấp xã + 66 dùng chung)
- Canonical hiện có: **254** bản ghi
- Mã có khả năng thuộc Phase 1 theo dữ liệu hiện có: **201**
- TTHC cấp tỉnh chỉ tiếp nhận tại xã, ngoài Phase 1: **53**
- Xung đột phân loại với quyết định Hải Phòng mới hơn: **10**
- Nhãn còn mơ hồ xã/dùng chung: **153**
- Số thiếu tối thiểu so với baseline aggregate: **122**

## Kết luận

Chưa được phép sinh danh sách MISSING theo mã chỉ từ phép trừ số lượng. Cần materialize danh sách 323 mã từ nguồn chính thức. Các mã cấp tỉnh chỉ tiếp nhận tại xã vẫn thuộc canonical tổng thể nhưng không được tính vào 257+66 của Phase 1.

## MISCLASSIFIED theo evidence mới hơn

| Mã | Nhãn hiện tại | Evidence mới | Phân loại mới |
|---|---|---|---|
| 2.000559 | Cấp tỉnh - tiếp nhận tại Trung tâm PVHCC cấp xã | 3643/QĐ-UBND (2026-09-11) | commune |
| 1.006780 | Cấp tỉnh - tiếp nhận tại Trung tâm PVHCC cấp xã | 3643/QĐ-UBND (2026-09-11) | commune |
| 2.000552 | Cấp tỉnh - tiếp nhận tại Trung tâm PVHCC cấp xã | 3643/QĐ-UBND (2026-09-11) | commune |
| 2.002409 | Cấp tỉnh - tiếp nhận tại Trung tâm PVHCC cấp xã | 3626/QĐ-UBND (2026-09-10) | commune |
| 1.014111 | Xã / điểm tiếp nhận cấp xã | 3500/QĐ-UBND (2026-08-30) | shared_including_commune |
| 1.014113 | Cấp tỉnh - tiếp nhận tại Trung tâm PVHCC cấp xã | 3500/QĐ-UBND (2026-08-30) | shared_including_commune |
| 2.001909 | Cấp tỉnh - tiếp nhận tại Trung tâm PVHCC cấp xã | 3626/QĐ-UBND (2026-09-10) | commune |
| 2.002396 | Cấp tỉnh - tiếp nhận tại Trung tâm PVHCC cấp xã | 3626/QĐ-UBND (2026-09-10) | commune |
| 2.002913 | Cấp tỉnh - tiếp nhận tại Trung tâm PVHCC cấp xã | 3582/QĐ-UBND (2026-09-08) | commune |
| 2.001801 | Cấp tỉnh - tiếp nhận tại Trung tâm PVHCC cấp xã | 3626/QĐ-UBND (2026-09-10) | commune |

## Gate tiếp theo

1. Materialize authoritative code-level baseline 323 mã.
2. Đối chiếu theo Mã TTHC để chốt MATCHED/MISSING/EXTRA/MISCLASSIFIED.
3. Gán authorityLevel/serviceScope/onlineServiceLevel và provenance.
4. Chỉ migrate canonical v5 sau khi validator PASS.
