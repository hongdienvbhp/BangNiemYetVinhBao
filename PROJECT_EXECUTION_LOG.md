# PROJECT EXECUTION LOG — VB-TTHC Data Core

Last updated: 2026-10-13 (Asia/Ho_Chi_Minh)
Repository: https://github.com/hongdienvbhp/BangNiemYetVinhBao
Primary tracker: https://github.com/hongdienvbhp/BangNiemYetVinhBao/issues/162
Canonical TTHC data: `data/thu-tuc.json`
Execution workspace: `C:\Users\ADMIN\Documents\Codex\BangNiemYetVinhBao`

> This is a durable execution checkpoint, not an alternative issue tracker. GitHub Issue/PR state is authoritative; refresh it before each work package.

## 1. Required working rules

- Read and follow `AGENTS.md` and `00_AI_WORKING_CONSTITUTION_VINH_BAO.md` before relevant source changes.
- Use Issue → task branch → minimal change → tests → PR → review. Do not modify `main` directly.
- `data/thu-tuc.json` is the only canonical TTHC source. Do not create a parallel Master dataset.
- Preserve unverified legal/data candidates. Do not merge/publish PR #158 without evidence and explicit review.
- Never use a PAT fallback. Do not label an incomplete or failed routine as healthy.
- Never run `git reset --hard`, `git clean`, force push, or discard user changes to resolve a conflict.
- Prefer deterministic scripts/tests; no additional frameworks, databases, services, agents, or duplicate trackers without proven need.
- On Windows, run `scripts/ai-safe-start.ps1` before editing. In this environment, normal PowerShell invocation was blocked by ExecutionPolicy; this succeeded using process-only bypass:
  `Set-ExecutionPolicy -Scope Process Bypass -Force; .\scripts\ai-safe-start.ps1`
  It confirmed repo, branch, upstream aligned, and clean tree.

## 2. Current ChatCode project/workspace

- ChatCode project: `BangNiemYetVinhBao`, Git-backed project ID `98a8a6adb56d`.
- Active branch: `codex/issue-162-candidate-review-recovery`.
- HEAD before adding this log: `1cc3475b8d22564fc3ce678ce026d5858c466dba` — `fix: scan sources while candidate review is pending`.
- Upstream: `origin/codex/issue-162-candidate-review-recovery`.
- Last verified before adding this log: `Ahead 0 / Behind 0 / Dirty False`.
- Current code change against main: `.github/workflows/official-data-update.yml` and `tests/test_official_data_update_workflow.py`.
- This file is being added on the current PR #164 branch for durable handoff. Re-run safe-start/status after the remote commit to ensure local and upstream are aligned.
- A separate local-only commit `cf88456` exists on `work/vb-tthc-phase1-repair-20261010`; do not push it until reconciled with PR #161 because it overlaps official-source scanner changes.

## 3. PR / CI state verified 2026-10-13

### PR #158 — candidate data review
URL: https://github.com/hongdienvbhp/BangNiemYetVinhBao/pull/158
- State: OPEN, Draft.
- Candidate snapshot date: 2026-10-09; canonical public row count in PR: 536; 0 added, 0 removed, 1 changed record.
- Main data concern: decision `4123/QĐ-UBND`, explicit official effective date 2026-10-01 is represented in derived city updates using `effectiveDateSource: default_effective_from_signing_date`. Correct provenance is still required.
- Procedure `2.001576` remains provincial-level; official PDF shows time reduced from 20 working days to 11.5 working days. Commune service centre is a reception point, not proof of commune jurisdiction.
- Keep Draft; do not merge/publish until source evidence, provenance, classification, and candidate contract are reviewed.

### PR #161 — fail-closed official-source pagination
URL: https://github.com/hongdienvbhp/BangNiemYetVinhBao/pull/161
- State: OPEN, Draft.
- Branch: `fix/official-source-completeness-20261011`, head `634aacef40401358f634e9f456df961f5de42181`.
- Adds explicit next-link traversal, page bound/loop detection, ambiguous/cross-host-link rejection, per-page hashes/snapshot metadata, invalid-calendar-date rejection and pre-write blocking on incomplete source snapshots.
- CI run `38153206223` SUCCESS; Pages workflow `38153206246` SUCCESS.
- Remaining proof obligation: live official-source pagination completeness (actual pages, final-page termination, fetch errors/timeouts). CI/mocked tests alone do not prove this.
- PR is a prerequisite for PR #164. Do not merge based on CI alone if required live-source evidence is still missing.

### PR #164 — routine behaviour while candidate awaits review
URL: https://github.com/hongdienvbhp/BangNiemYetVinhBao/pull/164
- State: OPEN, Draft; branch `codex/issue-162-candidate-review-recovery`, head `1cc3475b8d22564fc3ce678ce026d5858c466dba`.
- Changes: continue safe source scan/validation while candidate PR remains open; never overwrite candidate branch; preserve changed-run delta as Actions artifact; record truthful `BLOCKED_HUMAN_APPROVAL` terminal status rather than skipping the scan then reporting `PARTIAL`.
- GitHub CI run `38195721722` SUCCESS; Pages workflow `38195721756` SUCCESS.
- Local targeted test `python -m unittest discover -s tests -p "test_official_data_update_workflow.py" -v`: 2 tests PASS; `git diff --check` PASS.
- Depends on #161. Do not merge #164 until #161 is reviewed/accepted and the workflow change is verified against the updated base.

### PR #163 — latest terminal routine-health status
URL: https://github.com/hongdienvbhp/BangNiemYetVinhBao/pull/163
- State: OPEN, Draft.
- Fixes a health evaluator flaw: any old `OK` on the same day could mask a later `PARTIAL`/`FAILED`. Latest run terminal status now determines the day's health; has regression tests for later failure and recovery.
- GitHub CI run `38194033261` SUCCESS; Pages workflow `38194033226` SUCCESS.
- Review independently; no merge performed.

## 4. Local scanner checkpoint from prior Windows work

- Branch: `work/vb-tthc-phase1-repair-20261010`.
- Local-only commit: `cf88456` — `fix: harden official TTHC source scan`; last screenshot showed one commit ahead of upstream and not pushed.
- At time of commit: Python syntax PASS; fail-closed targeted tests 2 passed; full suite 192 passed, 10 subtests; `git diff --check` PASS.
- The commit includes `scripts/update_official_sources.py`, `tests/test_update_official_sources.py`, and this type of log file was present in that branch. The scanner/test implementation overlaps PR #161; compare diffs before any push or cherry-pick.
- Do not reset/clean/force or blindly push across branches.

## 5. Routine deadlock and recovery

- Workflow: `.github/workflows/official-data-update.yml`, scheduled 07:30 Asia/Ho_Chi_Minh.
- Previous run `38117225200`: open automated PR caused scanning steps to skip, then terminal record `PARTIAL`; health check flagged it.
- PR #164 changes this: the scanner continues while candidate is open, never updates/deletes candidate branch, and stores any new delta as a 90-day artifact. The terminal record becomes `BLOCKED_HUMAN_APPROVAL` after successful scan/validation while waiting for human review.
- Do not call this healthy without a current-period terminal `OK`; a truthful human-approval block is expected until the candidate closes.
- Native GitHub Actions PR-create permission has previously failed. Do not add PAT fallback; use authorized repository permission configuration or a safe handoff path.

## 6. Fail-closed regression history

- Prior source patch tests had a pagination arrow issue because expected arrow labels were displayed/stored as `?`. Tests were corrected to use Unicode escapes.
- Full suite in the prior Windows work branch passed 192 tests and 10 subtests.
- Fail-closed tests now directly assert `write_json_if_changed` is not called when primary/mirror source errors block a scan.
- In the current ChatCode branch, source-scan fix lives separately in PR #161; keep work scoped and reconcile overlap.

## 7. NEXT_SAFE_ACTION (authoritative order)

1. Refresh PR #161, PR #158, PR #163, PR #164, Issue #162, and CI before further work.
2. Keep this branch clean except for this log. Confirm local/upstream are aligned after adding it.
3. Verify real pagination of configured primary official sources safely. Capture for each source: requested page URLs, per-page hashes, page count, termination evidence, candidates/links, HTTP errors/timeouts. Never use an incomplete scan to write index/manifest/canonical data.
4. Reconcile local-only commit `cf88456` with PR #161; do not push duplicate scanner changes.
5. Correct/verify PR #158 provenance using the explicit official evidence; retain provincial classification for `2.001576` and the 11.5-working-day period. Keep candidate Draft until reviewed.
6. After #161 is reviewed/accepted, rebase or verify #164 against the new base and rerun CI. No automatic merge.
7. Review #163 and its regression tests separately; keep Draft until accepted.
8. Run a controlled routine only after the source-scanner prerequisite is safely integrated. Inspect the routine artifact and health result before declaring recovery.
9. At each handoff, update this file and Issue #162 with only: Changes, Tests/CI, Blockers, NEXT_SAFE_ACTION.

## 8. Confirmed operational constraints

- Offline work may continue for code review, fixture tests, local validation, documentation and handoff.
- Live HTTP pagination and GitHub synchronization require network access.
- The project is not complete or production-ready yet: real-source pagination proof and legal/data review remain open.


## Live pagination investigation — 2026-10-13

### Changes / evidence
- Work is continuing in ChatCode project `BangNiemYetVinhBao`; primary tracker remains Issue #162.
- PR #161 AJAX-pagination changes are being validated in an isolated worktree based on head `634aacef40401358f634e9f456df961f5de42181`; not committed/pushed yet.
- Added an isolated `--scan-only` mode to the worktree scanner. It requires `--online`, cannot combine with `--initialize`, and is covered by a regression test proving it does not write snapshot, index, manifest or PDFs.
- Live scan-only returned `blocked_incomplete_source_snapshot`, 22 configured source listings, 388 page-response records and 388 valid SHA-256 hashes. Index, manifest, snapshot, PDF hashes, and isolated worktree remained unchanged.
- 21 sources completed current traversal logic; Vĩnh Bảo source `https://vinhbao.haiphong.gov.vn/thu-tuc-hanh-chinh` remains blocked. Browser-level Chrome DevTools inspection clicked page 2 as a user; the official page itself posts to `/DesktopModule/UIArticleInMenu/ArticleInMenuPagination.aspx/LoadArticle` with `page=2`, `page_size=15`, `site_id=3017`, `article_category_id=86962`, `no=-15` and the page's own category list, then receives HTTP 200 with empty body. The same issue occurs in direct HTTP tests. This is real source/endpoint behaviour, not a parser guess.
- Other portals also expose declared `maxPage` values larger than the last non-empty AJAX response. The scanner was further tightened to fail closed when an empty response occurs before a declared final page (except a server-rendered initial HTML page when following AJAX pages actually return data). This last refinement still requires re-running targeted/full tests and a live scan-only.
- Tests before the last early-empty-page refinement: scanner suite 23 passed; repository suite 184 passed; diff check passed. Do not claim those tests validate the newest refinement until re-run.

### Open risks / blockers
- Source snapshot remains incomplete. Do not merge PR #161 or write candidate/index/manifest data until every required source has reliable end-of-pagination evidence.
- Vĩnh Bảo page 2 endpoint is empty even when clicked in Chrome. Need an authorized, verified alternate official listing endpoint or upstream site fix; do not silently exclude the source or call the scan complete.
- Some pages may be returning empty responses before their declared final page; current fail-closed refinement must be tested and the affected source IDs reported.
- PR #158 remains Draft. Manifest for `4123/QĐ-UBND` now records explicit `effectiveDate: 2026-10-01`, but the derived `city-updates-current.json` still needs regeneration so `effectiveDateSource` becomes `manifest` instead of `default_effective_from_signing_date`. Keep procedure `2.001576` classified at provincial level; 20 days reduced to 11.5 working days; commune centres are reception points only.
- Local-only scanner commit `cf88456` still overlaps PR #161; do not push it without reconciling the diff.

### NEXT_SAFE_ACTION
1. Re-run Python syntax, scanner unit tests, full pytest, and `git diff --check` in the isolated PR #161 worktree after the new premature-empty-page guard.
2. Re-run `--online --scan-only`; record all configured sources, page counts, terminal evidence, hashes, empty-page errors, unique candidates, and write-safety hash comparison.
3. Keep all incomplete sources fail-closed. Resolve the Vĩnh Bảo source via a verified alternate official endpoint or keep the scan blocked.
4. Rebuild only the derived artifacts in PR #158 from the corrected manifest, inspect diff and CI, and keep PR Draft.
5. Update this log and Issue #162 at each handoff; no main merge or candidate publication.


## Authoritative follow-up — 2026-10-13 (refresh supersedes earlier pagination estimates)

### Changes / Tests/CI
- Current ChatCode executor project: `bangniemyetvinhbao-git`; main ChatCode checkout was fast-forwarded to PR #164 head `9b70d27f6f6383ab05dc329c1091c9daeaaa3dc1`. Only untracked `.chatcode/` is present; preserve it.
- On the isolated worktree `C:\Users\ADMIN\AppData\Local\Temp\VB-TTHC-PR161-empty-page-9c1e701`, after the empty-interior-page guard:
  - `py_compile`: PASS.
  - `tests/test_update_official_sources.py`: 28 passed.
  - full repository pytest: 189 passed.
  - `git diff --check`: PASS; tracked working tree clean.
- PR #161 head remains `18ca72b3c35d498bbcc32c7af4974e7c544c5140`; CI #38332983923 and Pages #38332984038 success. This is code/test evidence, not proof every live source is complete.
- Refreshed PR #161 body reports its exact-head live `--online --scan-only` result: **22 configured sources, 11 source errors**, status `blocked_incomplete_source_snapshot`, and no snapshot/index/manifest/PDF writes. The source list is explicit below. This supersedes the earlier shorthand “21 sources completed” unless reconciliation of the two run records proves the later run differs.
- PR #158 head is now `debc5c960f106dce2c999007d6973c4fcf0443e9`; open Draft. Its current diff includes the official explicit `effectiveDate: 2026-10-01`, detailed source reviewNote, and regenerated `city-updates-current.json` with `effectiveDateSource: manifest`. Row `2.001576` still has `levelHint: province`, commune-reception evidence true, and context showing 20 working days reduced to 11.5. PR #158 CI #38332105826, Pages #38332105993, and Google Sheets workflow #38332105802 all succeeded; the Sheets workflow's PR path runs validation only, while live sync requires push/workflow_dispatch on `main`. Keep PR #158 Draft: its current diff touches 24 files, so scope and canonical diff still need review.

### Live pagination failures confirmed by PR #161 scan-only
The exact-head scan-only run did not prove complete enumeration. It failed closed for 11 sources with empty AJAX responses before declared terminal pages or no follow-up data after server-rendered page 1:
1. City official TTHC listing: pages 2–30 empty; final page declared 31.
2. Vĩnh Bảo official TTHC listing: pages 2–31 empty after rendered page 1. Independent browser evidence: AJAX POST to `/DesktopModule/UIArticleInMenu/ArticleInMenuPagination.aspx/LoadArticle`, HTTP 200 with empty body on page 2.
3. Culture/Tourism department: pages 2–18 empty; final page 19.
4. Agriculture & Environment department: pages 30–42 empty; final page 43.
5. Construction department (commune TTHC): pages 3–9 empty; final page 10.
6. Nhi Chiều: pages 4–17 empty; final page 18.
7. An Dương: pages 3–23 empty; final page 24.
8. Ngô Quyền: pages 2–22 empty; final page 23.
9. Gia Viên: pages 2–12 empty; final page 13.
10. Bạch Long Vĩ: pages 2–54 empty; final page 55.
11. Cát Hải: pages 2–29 empty; final page 30.

An HTTP 200 empty response is not a verified final page. Do not infer removed TTHC from absent list pages, do not disable configured sources just to obtain a green run, and do not merge #161 while the completeness gate is unmet without an explicit owner acceptance of the remaining source limitation. The PR remains Draft and the canonical data was not changed by the scan-only validation.

### Additional scan attempt
- A later ChatCode scan-only rerun was interrupted/has not returned a terminal result; do not count it as evidence or launch another whole-repository scan blindly. The exact-head scan result recorded in PR #161 is currently the authoritative available evidence. If retrying, run one configured source per bounded scan-only process and record that process’s own terminal JSON and hash guard.

### NEXT_SAFE_ACTION
1. Resolve/verify an official source-specific pagination contract or independently verified alternative traversal for the 11 blocked sources; especially Vĩnh Bảo. Keep fail-closed while unresolved.
2. Review PR #158's full 24-file diff and tests, despite the effective-date provenance correction now being present; keep it Draft and do not merge/publish.
3. Reconcile local-only Windows commit `cf88456` with PR #161; do not push overlapping scanner changes.
4. Review #163 separately (latest-terminal health fix; CI/Pages green) and #164 after #161 acceptance.
5. Update this log and Issue #162 at the next package boundary. No merge, production write, Google Sheets live sync, or publication without the prescribed gates.

## Vĩnh Bảo AJAX request-contract verification — 2026-10-13

- Fetched the official Vĩnh Bảo listing HTML successfully: 160,356 bytes, `text/html; charset=utf-8`, one inline script contains the pagination request.
- The actual script calls `POST /DesktopModule/UIArticleInMenu/ArticleInMenuPagination.aspx/LoadArticle` with `page=chosenPage`, `page_size=15`, `site_id=3017`, `article_category_id=86962`, and the listing page's own `categoryIds` plus other filters. It does not set a custom `contentType`; jQuery's default form encoding applies. Therefore the configured URL-encoded request shape is consistent with the actual inline JavaScript contract.
- A direct POST using the parsed form values/headers for page 2 returned HTTP 200 with a **zero-byte body**. An exploratory `application/json` request did not return within 20 seconds. This does not establish JSON as the correct contract. Together with the earlier browser DevTools page-2 observation, the configured endpoint currently provides no page-2 content to the scanner.
- This is an upstream source/endpoint behaviour or a still-unverified browser/session requirement, not demonstrated parser failure. Do not change the scanner to treat empty content as terminal, infer removal, or silently omit Vĩnh Bảo.
- A further all-sources per-source scan wrapper was interrupted without a terminal result; it is explicitly **not evidence** and should not be treated as a scan result. The exact-head scan-only result in PR #161 (22 sources, 11 errors, no writes) remains the authoritative live-scan evidence.

### NEXT_SAFE_ACTION
1. Find/verify an alternate official Vĩnh Bảo listing traversal or document the endpoint failure for the portal owner; require an independently verifiable complete set of article URLs before treating that source as complete.
2. Do not retry a large all-source scan until progress/terminal evidence is available. If needed, run one source per bounded scan-only job and preserve per-source terminal JSON plus source-data hash guard.
3. Preserve PR #161 fail-closed gate and keep the PR Draft until owner review of source completeness limitations.
## PR #158 canonical scope and test review — 2026-10-13

### Canonical row-level comparison against origin/main
- Candidate and baseline both contain 536 records; no added or removed codes.
- All 536 rows show snapshot/lifecycle date refresh from 2026-10-01 to 2026-10-09.
- Exactly one code, `2.001576`, has semantic fields beyond `sourceSnapshotDate`/`lifecycle` changed.
- For `2.001576`, the canonical legacy top-level `thoiHan` changes from `23 ngày làm việc` to `11,5 ngày làm việc`; `cap` remains `Cấp tỉnh - tiếp nhận tại Trung tâm PVHCC cấp xã`; the candidate lifecycle `effectiveFrom` is 2026-10-01. The updated field provenance has an official PDF evidence ID. The top-level legacy `huongDan.thoiHan` is absent in this record, so the canonical top-level `thoiHan` field is what controls the visible legacy duration.
- The date provenance mismatch is fixed: `official-decision-manifest.json` records the explicit official `effectiveDate` 2026-10-01, and `city-updates-current.json` now emits `effectiveDateSource: manifest` instead of defaulting to signing date.

### PR #158 local validation on exact open candidate branch
- Python syntax compilation: PASS.
- Focused regressions for guidance promotion and Google Sheets idempotency: 5 passed.
- Full repository pytest in candidate worktree: 175 passed in 1.43s.
- `validate_canonical_contract.py`: PASS, 536 procedures, v4 contract, dataset version 2026.10.13, 536 verified submission links, 49 official guidance records.
- `migrate_canonical_v4.py --check`: PASS.
- `validate_tthc_guidance.py`: PASS, 48 priority rows and 1 legacy override row.
- `git diff --check`: PASS; candidate worktree clean and aligned with remote candidate branch.

### Scope warning / disposition
- PR #158 currently includes 24 changed files. History shows commit `c3689a7 fix: make Google Sheets sync idempotent` (scripts/test) alongside the candidate data and provenance commits. This sync guard is useful but not strictly the same work unit as reviewing decision 4123; do not rewrite the existing draft branch blindly. Review whether to separate this follow-up before approval.
- PR #158 exact-head CI #38332105826, Pages #38332105993 and Sheets validation #38332105802 are green. The PR-triggered Sheets workflow validates/dry-runs only; the live sync job remains gated to pushes/dispatches on main.
- PR remains Draft. No merge, publication, live Google Sheets sync, or production write was performed.

### NEXT_SAFE_ACTION
1. Keep PR #158 Draft; source/legal review and scope review remain mandatory even though local tests/CI are green.
2. Review whether the Google Sheets idempotency commit should be isolated rather than carried as unrelated scope in the candidate data PR.
3. Continue the 11-source live pagination blocker from PR #161. The current exact-head scan-only result remains blocked; no source snapshot is complete until all required endpoints have reliable terminal-page evidence.
4. Reconcile the local-only Windows commit `cf88456` with PR #161 before any push.
## Vĩnh Bảo non-AJAX fallback probe — 2026-10-13

- Tested the plausible read-only fallback URL `https://vinhbao.haiphong.gov.vn/thu-tuc-hanh-chinh?page=2` against the official listing. It returned HTTP 200, `text/html; charset=utf-8`, 160,356 bytes, SHA-256 `e6e4430bfbf41de041e60e18281155dac29f16f0a110d01900f6aa692125ba03`, title `Thủ tục hành chính - Xã Vĩnh Bảo`, 192 links and 22 candidate-shaped links.
- Its response size/hash/title matched the server-rendered initial listing, so `?page=2` did not produce a distinct page. The 22 candidate-shaped links include internal-process links and related-site widgets; they are not evidence of complete listing coverage. Do not substitute this GET parameter for the AJAX page sequence.
- This fallback experiment made no repository/data writes. Vĩnh Bảo remains incomplete; the authoritative exact-head scan-only result remains blocked.

### NEXT_SAFE_ACTION
Find a genuine official archive/category/sitemap or working page traversal that demonstrates all relevant public decision article URLs. Require distinct page hashes/URLs and a verifiable terminal condition; otherwise retain the source blocker and document the portal-side AJAX issue.
## Vĩnh Bảo sitemap/robots fallback check — 2026-10-13

- Read-only GET `https://vinhbao.haiphong.gov.vn/robots.txt`: HTTP 200, 42 bytes, content `User-agent: facebookexternalhit\r\nAllow: /`; no sitemap location declared.
- Read-only GET `https://vinhbao.haiphong.gov.vn/sitemap.xml`: HTTP 404.
- Read-only GET `https://vinhbao.haiphong.gov.vn/sitemap_index.xml`: HTTP 404.
- Combined with the earlier `?page=2` GET returning the same initial-page SHA, these common alternatives do not provide a distinct complete listing traversal. No project/source data files were changed by these probes.

### Current fallback decision
Do not scrape related widgets or treat a search-engine index as a complete source substitute. Keep the source blocked until an official category/archive/feed or source-owner-provided endpoint can demonstrate complete article URL coverage and terminal pagination.

## PR #164 artifact hardening — 2026-10-13

- Commit pushed to `codex/issue-162-candidate-review-recovery`: `447788f fix: include untracked evidence in pending review artifact`.
- Workflow now applies NUL-safe `git ls-files --others --exclude-standard -z` plus `git add -N` to untracked files under `data`/`js/master-data-fallback.js` before `git diff --binary`. This means the 90-day pending-review artifact includes newly downloaded PDF evidence and other untracked source artifacts, while leaving contents unstaged for commit and preserving the open candidate branch.
- Regression test added in `tests/test_official_data_update_workflow.py`.
- Validation: targeted workflow tests 3 passed; full repository pytest 173 passed in 1.09s; `git diff --check` PASS. At log time, exact-head CI #38335659748 was still running; Pages workflow #38335659740 succeeded.

### NEXT_SAFE_ACTION
1. Verify CI on PR #164 head `447788f51cb013706d1c609c053c5a27ec8000e6` completes successfully.
2. Continue source-completeness blockage; no alternate complete official route is proven for Vĩnh Bảo or the other 10 incomplete sources.
3. Keep PRs #158/#161/#163/#164 Draft. Reconcile Windows-only `cf88456` with #161 before push; no merge/publish.
## Final checkpoint — pagination contract and PR164 CI — 2026-10-13

### Vĩnh Bảo pagination index mapping
- The live HTML emits numeric list items with `data-page="1"` for page 1 and `data-page="2"` for page 2; it does not use zero-based indices.
- Inline jQuery uses `var chosenPage = $parent.data('page')` and posts `page: chosenPage`; the request is one-based. The scanner sending `page=2` is therefore aligned with the observed UI mapping; no off-by-one patch is justified.
- This does not explain the blank response: the actual page-2 form-urlencoded POST still returned HTTP 200 with zero bytes, matching separate browser DevTools evidence. Treat it as unresolved upstream endpoint/session behaviour, not proof of a parser offset bug.
- Other official route probes: `/thu-tuc-hanh-chinh?page=2` returns identical initial-page bytes/hash; `/cong-khai-tthc` returns maxPage=1 and only 4 candidate-shaped links, so it is not a complete source substitute; `/phong-van-van-hoa-xa-hoi` timed out; robots.txt has no sitemap declaration and standard sitemap endpoints return 404.

### PR #164 exact-head result
- Latest head at this checkpoint: `a95958f734d74e732ae3880fbc57d05f5ae84744`.
- CI run `38335772560`: SUCCESS (static-site job completed with no failed steps). Pages workflow `38335772523`: SUCCESS.
- The actual workflow/code change is commit `447788f fix: include untracked evidence in pending review artifact`; it adds NUL-safe intent-to-add for untracked files before binary diff generation so newly discovered PDFs/evidence appear in the pending-review artifact. Targeted workflow tests: 3 passed; full repository pytest: 173 passed; diff check: PASS.
- PR #164 remains Draft and depends on #161. No merge, production update, or candidate branch overwrite occurred.

### Current authoritative blockers
- Eleven configured official sources still fail complete pagination on PR #161 exact-head scan-only; no alternative complete traversal has been proven. Do not classify the source snapshot as complete or merge #161 merely for CI green.
- PR #158 source provenance/date and duration have been corrected and tests pass (candidate canonical: 536 rows, no additions/removals, only `2.001576` semantic change beyond snapshot/lifecycle); keep Draft due official/legal scope review and the extra Google Sheets idempotency commit in the 24-file diff.
- Windows-only `cf88456` remains unpushed and overlaps PR #161; reconcile before any push.

### NEXT_SAFE_ACTION
1. Keep PRs #158/#161/#163/#164 Draft. Review current live state before each work package.
2. For the 11 blocked sources, require either a verified official traversal with complete page/hash/termination evidence or explicit source-owner/ project-owner resolution; do not weaken fail-closed and do not infer removals from missing pages.
3. Reconcile local Windows commit `cf88456` with PR #161 before push.
4. After source completeness is accepted, rebase/verify PR #164 against #161 and rerun CI. Do not merge automatically.
5. Continue updating this file and Issue #162 at work-package boundaries.
## PR #161 Unicode pagination-label fix — 2026-10-13

- Read-only differential review of Windows-only commit `cf88456` against its parent showed it must not be pushed as a branch because the branch diff includes candidate data; only small parser/test behaviors were considered for selective porting.
- A concrete gap was reproduced in the current PR #161 parser: Unicode arrow-only labels `➜`, `❯`, and `>>` were not recognized, even though `›`, `»`, and `→` worked. The cause was matching only the normalized `fold()` label set, which omitted the three variants.
- Selective fix pushed to the existing PR #161 branch from its exact previous head `18ca72b3c35d498bbcc32c7af4974e7c544c5140`: commit `0691599ff0f13159449faac6bd633a78cb8b9f7d` (`fix: recognize Unicode pagination arrow labels`). It preserves a `raw_label` before folding, recognizes six explicit arrow-only labels via Unicode escapes, and adds `test_page_parser_detects_unicode_arrow_next_labels`. Existing hash-only carousel arrows remain rejected because non-navigable hrefs are filtered before next-link acceptance.
- Validation before commit/push on the exact PR #161 worktree: `py_compile` PASS; `tests/test_update_official_sources.py`: 29 passed, 6 subtests; full repository pytest: 190 passed, 6 subtests in 1.04s; `git diff --check`: PASS. These are local results; exact-head CI for `0691599` was still running when checkpointed.
- PR #161 remains Draft. This is parser hardening only; it does not remove the 11 live-source pagination blockers, and it does not establish that the live Vĩnh Bảo endpoint returns page 2. No snapshot/index/manifest/PDF/canonical data was changed by this patch.

### NEXT_SAFE_ACTION
1. Refresh CI on PR #161 head `0691599ff0f13159449faac6bd633a78cb8b9f7d`.
2. Keep the source-snapshot guard fail-closed for the 11 sources with empty pages before their declared terminal page; seek a genuine official pagination endpoint or portal-owner resolution.
3. Keep PR #158/#161/#163/#164 Draft; reconcile local-only Windows `cf88456` by selective code comparison only, never push the candidate-containing branch wholesale.