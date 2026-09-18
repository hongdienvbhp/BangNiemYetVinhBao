# AGENTS.md

## Canonical governance bắt buộc

Trước mọi thay đổi mã nguồn, dữ liệu, kiến trúc hoặc hạ tầng, AI/Agent phải đọc và tuân thủ `00_AI_WORKING_CONSTITUTION_VINH_BAO.md`.

- Constitution là baseline nguyên tắc dùng chung cho hệ sinh thái Vĩnh Bảo.
- `AGENTS.md` chỉ bổ sung hướng dẫn thực thi riêng của repository; không được tạo bộ nguyên tắc cạnh tranh.
- Khi có thay đổi Constitution, đồng bộ theo version qua Issue → branch → PR.
- Nếu có mâu thuẫn, ưu tiên pháp luật/quy định có thẩm quyền, sau đó là chỉ đạo mới hơn và cụ thể hơn của người dùng trong phạm vi hợp lệ.

## GitHub workflow mặc định

Thực hiện theo: **Issue → branch riêng → thay đổi → kiểm tra/test phù hợp → Pull Request → kiểm tra → merge khi có thẩm quyền/chỉ đạo phù hợp**.

Không sửa trực tiếp `main`; không ghi secret/credential/token/cookie hoặc dữ liệu cá nhân nhạy cảm vào repository.
