# AGENTS.md

## Canonical governance bắt buộc

Trước mọi thay đổi mã nguồn, dữ liệu, kiến trúc hoặc hạ tầng, AI/Agent phải đọc và tuân thủ `00_AI_WORKING_CONSTITUTION_VINH_BAO.md`.

- Constitution là baseline nguyên tắc dùng chung cho hệ sinh thái Vĩnh Bảo.
- `AGENTS.md` chỉ bổ sung hướng dẫn thực thi riêng của repository; không tạo bộ nguyên tắc cạnh tranh.
- Khi có thay đổi Constitution, đồng bộ theo version qua Issue → branch → PR.
- Nếu có mâu thuẫn, ưu tiên pháp luật/quy định có thẩm quyền, sau đó là chỉ đạo mới hơn và cụ thể hơn của người dùng trong phạm vi hợp lệ.

## Handoff Chat Web ↔ Codex

Mô hình chuẩn: **Chat Web → Linear/GitHub Issue → Codex → PR/CI → Chat Web review**.

- Chat Web chịu trách nhiệm phân tích, chia work package, rà soát bằng chứng và xác định bước tiếp theo.
- Codex chỉ thực thi work package được mô tả trong Issue/PR; không cần và không nên nạp toàn bộ lịch sử chat.
- Linear và GitHub Issue/PR là nguồn trạng thái sống; không tạo thêm tracker hoặc file trạng thái trùng lặp nếu chưa có nhu cầu riêng.
- Khi bắt đầu, chỉ đọc Constitution, AGENTS.md, Issue/PR được giao và các file liên quan trực tiếp.

## Kiểm soát tài nguyên

- Không chạy nhiều agent song song trên cùng Issue/branch.
- Ưu tiên tìm kiếm theo file/symbol trước khi quét toàn repo.
- Test mục tiêu trước; full regression/build ở gate cuối hoặc khi phạm vi thay đổi yêu cầu.
- Không dùng AI cho việc rule/script/SQL/API/workflow xử lý ổn định được.
- Ưu tiên incremental processing, cache/reuse và giảm API/token không cần thiết.

## GitHub workflow mặc định

Thực hiện theo: **Issue → branch riêng → thay đổi → kiểm tra/test phù hợp → Pull Request → kiểm tra → merge theo thẩm quyền/chỉ đạo hiện hành**.

Không sửa trực tiếp `main`; không ghi secret/credential/token/cookie hoặc dữ liệu cá nhân nhạy cảm vào repository.

## Handoff cuối work package

Cập nhật Issue/PR tối thiểu:
1. Changes;
2. Tests/CI;
3. Blockers;
4. NEXT_SAFE_ACTION.

Không tuyên bố “đã xong/đã test/đã deploy/đã merge” nếu chưa có bằng chứng kiểm chứng được.
