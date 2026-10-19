# Independent delivery security review — 2026-10-19

Reviewed current worktree againstde33ebb, read-only, with a fresh reviewer under executing-plans/requesting-code-review. No secret files or environment dumps were read by the reviewer.

- Critical:0. Important:2. Minor:1.
- P1 aggregate upload exhaustion: initially two parallel uploads both succeeded beyond a small account quota. Added PostgreSQL advisory-lock reservations, aggregate byte/count/concurrency limits, free-disk floor, upload deadline and success/error/disconnect cleanup. Regression RED→GREEN; failed request and client disconnect release leases and partial files.
- P2 proxy shared login bucket: clientA exhaustion also blocked clientB. Added explicit loopback cloudflared/private-nginx/API one-hop trust; nginx overwrites X-Forwarded-For using Cloudflare client identity. Separate-client/forwarded spoof tests RED→GREEN and isolated production proxy path passed. Actual Cloudflare edge path remains to verify after deployment.
- Deferred minor: zero-duration subtitle cues can currently become observations. No extension to factual verdict scope; source authenticity/meaning and OCR uncertainty remain unverified.

Final verified suite: Python198/API42/browser9=249 passed, typecheck/build passed, RULES9/9 and boundaries8/8, separate production-container checks22/22. Static apps scan remains74 findings, exit1; independent review is not a complete security audit.

Rulings carried from the implementation ledger:

1. Local Tesseract kor+eng replaces proposed PaddleOCR for this bounded extractor. Cost if wrong: engine adapter replacement; accuracy equivalence is not claimed.
2. Preserve existing local services/secrets/data; build deploy configuration while actual target access was unavailable. Cost if wrong: provider-specific deployment adjustment. User later confirmed Sydney AWS/Tunnel and excluded Codex Cloud access setup.
3. Recovery deliberately restores operational accounts/costs while discarding all ephemeral media/report access and sessions. Cost: media/report content cannot be recovered; full disaster recovery remains outstanding. This prevents old deleted data from being revived.
4. Require available RAM1.5GiB/disk10GiB before new services instead of altering existing services or purchasing upgrades. Cost: current AWS target cannot run this delivery until resources are arranged.
