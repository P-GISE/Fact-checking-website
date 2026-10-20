# Evidence Verdict Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans for the parent integration; assign disjoint bounded source implementation to a worker. Steps use checkboxes and record RED/GREEN evidence. User approved the written design and instructed development on2026-10-21.

**Goal:** Verify the real AI pipeline and enable traceable, limited reviewed-source sentence/table verdicts with a separate modal/summary report.
**Architecture:** Preserve existing numeric gates for legacy results. A versioned reviewed-document policy pins exact public source URL, normalized document hash, reviewed fact/quote positions and comparison definition. A separate meaningReview records deterministic validation; only complete matching policy/context can remove the old abstention. Existing unreviewed documents remain abstentions. General prose is limited to a complete single factual sentence; ambiguous/negated/corrected context is never accepted by merely finding a matching substring.
**Tech Stack:** Existing Python/Pydantic, TypeScript/Zod/Vue, PostgreSQL budget wrapper and OpenAI/Brave; no new production dependency.
**Spec:** ../specs/2026-10-21-evidence-verdict-design.md

## Global Constraints

- whisper-1/gpt-4.1-mini/Brave; job200000/month20000000 USD micros. Never print keys or raw provider errors.
- Do not enable public AI before controlled live verification. Source facts must be primary-source reviewed, not search snippets or model assertions.
- Preserve existing sourceTrace/tableContext observation meaningVerified:false. New meaningReview is separate and nullable for legacy.
- A reviewed document hash is deliberately narrow: changed pages require renewed review, never automatic trust.
- Reuse current work checkout as requested ongoing project; no main/master edits. User requested speed and existing session uses disjoint agent work.

## Review Focus

- A modified/redirected/forged source cannot inherit approval: exact normalized URL, full-text hash and source trace must match.
- Truncated/corrected/conditional input cannot become confirmation through a substring quote.
- A different denominator/period/unit cannot become a refutation.
- Copied evidence cannot increase strength through counting URLs; independence stays unverified unless actually established.
- Legacy reports and nullable new contracts must remain readable through API and UI.

### Task1: reviewed meaning and verdict gate
Files: worker meaning_review.py, reviewed_sources.json, contracts.py, validator.py, decision.py and tests/test_meaning_review.py.
Interface: review_meaning(claim,document) -> MeaningReview|None; verified review includes policyId/sourceKind/documentHash/relation/reasons/definition/quote positions. Nullable EvidenceCheck.meaningReview.
- [ ] RED: paragraph/explicit simple table support/refutation, changed hash/URL/claim context/precision/denominator/truncation/duplicate quote/unsafe source refusal.
- [ ] Implement narrow deterministic policy/context checks and new version gate without relaxing unreviewed legacy input.
- [ ] GREEN: focused worker tests plus previous validator/source/contract regressions.

### Task2: source policy and real evidence
Files: reviewed_sources.json, source_registry.json, review report/fixtures and policy tests.
- [ ] Verify exact official static HTML and definition/publication/identity; fetch via existing production parser, record full normalized hash and exact quote.
- [ ] Register only reviewed source/fact with source reference and review timestamp; support a simple table only if actual structure is verified.
- [ ] Exercise the actual fetched document, including adversarial mutations; distinguish synthetic boundaries from real source evidence.

### Task3: API/report integration
Files: API contracts.ts/visual-contracts.ts/tests, web types.ts/components EvidencePanel/AnalysisReport/VisualReview and Worker report.py/tests.
- [ ] RED: new meaning data survives API, rejects malformed verification, accepts legacy null; summary distinguishes conflicts/insufficient/internal mismatch and explains strength without independence claims.
- [ ] Integrate optional reviewed evidence with policy/comparison definition/position explanation. Keep internal modal result separate.
- [ ] GREEN: Worker/API tests, typecheck/build, actual report UI and legacy UI checks.

### Task4: live run, review and publish
Files: sanitized execution report and affected guide sections.
- [ ] User saves keys into existing server0600 env. Verify only presence, controlled test uses production budget wrapper and owned Korean media.
- [ ] Record actual stages/source/decision/report/cost/deletion or concrete provider blocker; do not label lack of evidence false.
- [ ] Whole change review and necessary fixes; relevant full checks and work push/actual deployment verification. Update guide with completed/pending distinction.

## Evidence ledger

- Baseline: local/production keys absent, production disabled; focused67passed/1FFmpeg-missing failure. Source unchanged at baseline d27ca3a.
- Ruling: exact reviewed document snapshots are the first safe implementation of the approved limited source semantics. It requires re-review on content change and does not imply universal language understanding.
- Live task depends on user key setup; Tasks1–3 can proceed independently.
