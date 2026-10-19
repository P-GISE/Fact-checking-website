# FactLens remaining delivery implementation plan

> **For agentic workers:** Use superpowers:executing-plans in the existing isolated work checkout. Preserve existing local secrets/services/data. User authorized all remaining work and no repeated implementation permission requests.

**Goal:** Complete the independently implementable local product, security and operational flows; execute authorized real API verification and record genuine external blockers separately.
**Architecture:** Keep existing numeric verdict gates. Add local FFmpeg/Tesseract visual extraction and independent modal review; expose bounded provenance and a claim-summary report. Add opt-in account/session ownership across existing APIs, with fail-closed production configuration. Exercise all destructive checks only in the isolated test database/media directory. Deployment uses the user's existing target once identified.
**Tech Stack:** Existing Vue/TypeScript/Express/PostgreSQL/Python, FFmpeg, Tesseract kor+eng, Node crypto; no new hosted product dependency.
**Spec:** docs/00_문서_가이드.md, docs/02_기능_설계.md, docs/08_운영_배포.md and docs/99_해야할일..md. User confirmed Brave account terms checked and requested deployment to an existing cloud/domain; public hostname is factlens.pigs0516.com (user owns pigs0516.com); Actual target confirmed by user terminal: AWS ap-southeast-2 i-0b4a251ecd2f5bd3e, Tailscale100.97.248.52, existing Cloudflare Tunnel. User performs server commands; no agent browser control. Server resources fail preflight.

## Global constraints

- whisper-1/gpt-4.1-mini/Brave only; job200000/month20000000 USD micros. No secret values in files tracked by Git, logs or chat.
- No verdict expansion to general documents without validated provenance/meaning. Internal visual mismatch is independent of external truth.
- Input100MiB/180seconds; maximum12 frames, image edge960px, OCR records bounded, tool subprocess timeouts, private derived files removed with media.
- Legacy reports remain readable; new fields nullable/defaulted. No authentication bypass in public mode; local compatibility explicitly separate.
- Real API test uses self-authored generated media and the production budget wrapper. Paid outcomes, account quota and research accuracy remain distinct.

## Review focus

- Malformed/truncated subtitles, zero/NaN/reversed timestamps, OCR unavailable and oversized derived output fail explicitly.
- OCR uncertainty and negation never become verified factual disagreement; absent frames never imply agreement.
- Account A cannot read/delete/start B's media/jobs/claims; stale/deleted/expired sessions and CSRF denied.
- Backup/restore cannot revive deleted media or overwrite an unrelated database; restoration test uses a disposable isolated target.
- Deployment cannot silently publish local unauthenticated mode, secrets, default credentials, or unverified operational claims.

## Task 1: local visual extraction (TASK024)
Files: new worker visual.py/test_visual.py; worker Dockerfile.
Interface: extract_visual(path:Path,duration:float)->VisualAnalysis (private frame IDs, timed subtitle/OCR records, explicit coverage/status/limitations).
- [x] Write and observe failures for bounded VTT parsing, generated MP4 frame extraction/OCR and unsupported/audio-only inputs.
- [x] Implement12-frame/15second sampling, embedded text subtitles and local kor+eng OCR with timeouts and output limits.
- [x] Run pure and real FFmpeg/Tesseract tests; commit with documentation/evidence.

## Task 2: modal comparison and report integration (TASK025/026)
Files: contracts.py, pipeline.py/main.py, new multimodal.py/report.py/tests, API contracts, Vue report/types, E2E.
Interfaces: review_modalities(claims,visual)->checks; summarize(claims,checks)->claim summary; AnalysisResult.visual/modalChecks/summary.
- [x] RED for same-condition numeric mismatch, negation/period/unit uncertainty, missing visual sources, bounded summary.
- [x] Integrate after production transcription, keep external verdicts unchanged, render independent modal results/timestamps and limits.
- [x] Full Python/API/browser/type/build checks and legacy compatibility; commit.

## Task 3: account/session ownership (TASK015/017/027)
Files: API auth module/migration/routes/query ownership, web login/account controls, API/E2E tests, config/ops.
Interface: secure server sessions with hashed opaque cookie token, scrypt passwords, per-user media/job ownership; local legacy mode explicit and blocked for public startup.
- [x] RED for registration/login/logout, password/session expiry, cross-account upload/job/report/claims/media/delete access and cross-origin mutation.
- [x] Add account mode and server ownership; integrate login and preserve read-only separately authenticated admin.
- [x] Full API/browser integration in account mode; validate local mode and production startup safeguards; commit.

## Task 4: remaining source/meaning audit (TASK023)
Files: source parser/table context/validator and bounded regression fixtures.
Interface: explicit header/scope/reference observations and conservative meaning review diagnostics; never treat candidate context as verified semantics.
- [ ] RED for duplicate/missing/cross-table header references and correction/period/denominator cues.
- [ ] Preserve declared references, validate resolved same-table links and keep unsupported semantics/identity abstentions.
- [ ] Production RULES/hash/version and boundary regression checks; commit.

## Task 5: live AI verification and evaluation readiness (TASK016/014)
Files: reproducible smoke/evaluation tooling, owned Korean fixture manifest and sanitized run evidence.
- [x] Generate owned short Korean audio; validate no personal/third-party source content and record provenance.
- [x] Run production adapters under approved job/month budget (STT429, separate Brave200; full analysis remains blocked); record transcription/generation/search/source-access/usage/deletion independently, no secrets.
- [ ] Add rights/label/split run manifest and missing-provider/failure denominator checks. Real research performance requires real labeled data and cannot be fabricated.

## Task 6: backup/recovery and public deployment readiness (TASK017)
Files: backup/restore tools, compose/health/startup validation, operational documentation and tests.
- [x] Produce private database backup and restore into a new disposable target; verify manifest/checksums and tombstones. Ruling: ephemeral media/report recovery is deliberately excluded; all restored analyses expire, accounts/costs survive. Full media disaster recovery remains unimplemented.
- [x] Build/restart isolated services with proxy/CA; run browser→API→DB/worker checks.
- [ ] Inspect identified existing deployment target; prepare concrete reviewed configuration and deploy only within user's stated target/authorization. Record unavailable target/account/domain facts as blockers.

## Task 7: final whole-branch review and handoff
- [ ] Full sequential regression/type/build/security checks, fresh independent review and RED→GREEN critical/important fixes.
- [ ] Update guide13, task completion/partial/external-blocked distinctions, evidence and GitHub work commits. No invented accuracy, production readiness or finished tasks.
