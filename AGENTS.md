# AGENTS.md

## GitHub workflow bắt buộc

Mọi Codex/AI/agent làm việc trong repository này phải tuân thủ:

**Tạo Issue → tạo branch riêng → thực hiện thay đổi → chạy test/kiểm tra → tạo Pull Request → DỪNG trước merge.**

Không được:
- sửa trực tiếp `main`;
- tự merge hoặc bật auto-merge;
- bỏ qua test mà không báo;
- mở rộng phạm vi ngoài Issue;
- ghi secret, credential, cookie, token hoặc dữ liệu cá nhân nhạy cảm vào repo.

Khi hoàn thành, báo cáo tối thiểu:
1. Issue;
2. branch;
3. file đã tạo/sửa;
4. test/kiểm tra đã chạy;
5. pass/fail;
6. PR;
7. rủi ro hoặc nội dung cần người dùng kiểm tra.

Chỉ merge khi có chấp thuận rõ ràng của Hồng Diễn.


## Chỉ đạo riêng cho nhiệm vụ portfolio TTHC — 11/09/2026

Người dùng đã ủy quyền tự động merge toàn bộ phần việc hoàn tất từ đầu nhiệm vụ và các phần hoàn tất tiếp theo, không cần hỏi lại. Trong nhiệm vụ portfolio này, chỉ đạo này thay thế yêu cầu dừng/chờ người dùng review trước merge ở trên. Quy trình: Issue → branch → test → PR → agent review diff và kiểm tra CI tại head hiện tại → merge có kiểm tra head → kiểm chứng sau merge. PR Draft, kiểm thử lỗi hoặc dữ liệu chưa đủ căn cứ chưa được coi là hoàn tất. Không bỏ qua branch protection, quyền nền tảng, bảo vệ secret/PII hoặc tự suy đoán dữ liệu pháp lý. Ngoài nhiệm vụ này, quy trình mặc định vẫn áp dụng.


## Handoff Chat Web ↔ Codex

Mô hình chuẩn: **Chat Web → Linear/GitHub Issue → Codex → PR/CI → Chat Web review**.

- Chat Web phân tích, chia work package, rà soát bằng chứng và xác định bước tiếp theo.
- Codex chỉ thực thi work package được mô tả trong Issue/PR; không nạp toàn bộ lịch sử chat.
- Linear và GitHub Issue/PR là nguồn trạng thái sống; không tạo tracker/file trạng thái trùng lặp nếu chưa có nhu cầu riêng.
- Khi bắt đầu, chỉ đọc Constitution, AGENTS.md, Issue/PR được giao và các file liên quan trực tiếp.

## Kiểm soát tài nguyên

- Không chạy nhiều agent song song trên cùng Issue/branch.
- Ưu tiên tìm kiếm theo file/symbol trước khi quét toàn repo.
- Test mục tiêu trước; full regression/build ở gate cuối hoặc khi phạm vi thay đổi yêu cầu.
- Không dùng AI cho việc rule/script/SQL/API/workflow xử lý ổn định được.
- Ưu tiên incremental processing, cache/reuse và giảm API/token không cần thiết.

## Handoff cuối work package

Cập nhật Issue/PR tối thiểu: Changes; Tests/CI; Blockers; NEXT_SAFE_ACTION.
Không tuyên bố hoàn thành nếu chưa có bằng chứng kiểm chứng được.


## Làm việc đa máy / Codex / ChatCode — tự động bắt buộc

Mỗi phiên Codex, ChatGPT Web qua Codex Web GPT hoặc ChatCode khi bắt đầu làm việc trong repo này phải tự động chạy `scripts/ai-safe-start.ps1` (Windows) trước khi sửa code.

Agent phải:
- tự nhận diện máy hiện tại, repo, branch và upstream;
- tự `git fetch origin --prune`;
- nếu working tree sạch và chỉ behind upstream thì tự `git pull --ff-only`;
- nếu dirty/diverged thì bảo toàn thay đổi, không reset/clean/force;
- dùng branch theo Issue/task, không tạo branch theo tên máy;
- trước khi chuyển sang máy/executor khác, tự kiểm tra secret, checkpoint commit, push branch và cập nhật Issue/PR với NEXT_SAFE_ACTION;
- khi nhận lại việc ở máy khác, tự fetch/pull và xác minh HEAD trước khi tiếp tục;
- coi GitHub + Issue/PR/Linear là nguồn trạng thái, không dùng lịch sử chat hoặc máy local làm canonical source.

Người dùng không phải tự chạy các thao tác Git thông thường trên nếu agent có quyền thực hiện. Chỉ hỏi người dùng khi cần quyền/xác nhận bắt buộc hoặc có xung đột nghiệp vụ không thể tự quyết an toàn.


## Resource-aware execution — bắt buộc

Trước mỗi work package, executor phải tối ưu context/test/review theo rủi ro:

- Không đọc toàn bộ Constitution lặp lại nếu version/hash không đổi; đọc full khi lần đầu vào repo/workspace, khi Constitution đổi, hoặc task liên quan governance/architecture/security/data/legal/production/cross-repo.
- Mặc định context theo tầng: metadata → file/symbol liên quan → module → toàn repo chỉ khi cần.
- Không quét toàn repo trước khi thử changed-files/file/symbol search.
- Dùng công cụ/script hoặc mức suy luận thấp hơn cho status/read-only/mechanical; mức cao chỉ cho task khó/rủi ro cao.
- Docs/governance-only dùng validation nhẹ; targeted tests trước; full regression ở gate cuối hoặc khi thay đổi shared-core/dependency/schema/auth/build/deploy.
- Chat Web review chỉ bắt buộc cho architecture, security/PII, schema/migration, production, cross-repo, CI không rõ/fail, thay đổi lớn hoặc khi người dùng yêu cầu.
- Linear quản lý portfolio/cross-repo; GitHub Issue/PR quản lý work package kỹ thuật. Không nhân đôi tracker.
- Handoff chỉ cần HEAD/branch, Changes, Tests/CI, Blockers, NEXT_SAFE_ACTION; không chép lại toàn bộ lịch sử chat.
