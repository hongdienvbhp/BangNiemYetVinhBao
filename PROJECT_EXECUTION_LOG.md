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
