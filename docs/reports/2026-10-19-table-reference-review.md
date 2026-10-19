# Table reference/cue audit review — 2026-10-19

Fresh read-only reviewer inspected changes against62949a4. Critical0/Important0/Minor2. No credentials or environment files read by reviewer; no DB tests run by reviewer.

Coverage: bounded ID lookup (including excluded-node duplicates), missing/cross-table/nonheader resolution, fragmented/nested cells, provenance/Unicode parity, complete flags, cue locations, literal UI rendering, server-owned versions/module hashes and unchanged factual gates.

Minor followups:

- A manually supplied duplicate context fragment blockIndex can select the last fragment in Python and the first in API. The production builder emits unique block indexes; contract alignment is deferred.
- Cue observations are representative first matches per kind/fragment. This scope is explicitly documented in02/04; complete does not claim every occurrence or semantic validation.

Verification: Python211/API44/browser9=264 passed; typecheck/build; RULES9/9 and abstention boundaries8/8. apps static scan74files75findings(C0/H10/M32/L33), exit1. No new paid API requests. Public deployment remains incomplete.

Ruling: preserve static-text-v3 normalization/block version while independently versioning table-reference-audit-v1/table-cue-audit-v1 and hashing module sources in regression runs. Cost if wrong: downstream version policy may require adjustment; no factual verdict expansion.
