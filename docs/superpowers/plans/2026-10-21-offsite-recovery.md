# FactLens offsite backup and clean-host recovery

User-authorized scope: extend the existing private daily database backup to independent S3 storage and prove recovery on a new server. Preserve production availability, all existing data and public routing. Existing03KST/7day policy remains the baseline. No real AI calls.

## Design

Seoul S3/KMS stores versioned, private, encrypted recovery archives independently of the Sydney host. GitHub OIDC uses the immutable repository/environment subject and short-lived upload-only credentials. No AWS long-lived credentials on the production host. Archives include validated DB dump/manifest, pinned code SHA, deployment environment and inactive tunnel recovery files. All secret bytes stay out of logs.

Clean-host preparation rejects production markers, existing config, unsafe tar paths/links/duplicates, wrong code SHA, stale data and corrupt payloads. Recovery initially has no Cloudflare tunnel, disabled AI and disabled recovered accounts. Start PostgreSQL/Redis, restore into a new DB, validate sanitization, rename databases only on the marked new host, then start the application. Never switch the production tunnel/static IP during the drill.

## Acceptance checklist

- [x] Verify existing guides, server health and backup status.
- [x] Create separate-region S3 with public access blocked, ownership enforced, KMS encryption/rotation, versioning, lifecycle and TLS/key policy.
- [x] Configure GitHub OIDC trust using actual immutable repository IDs and limited upload permissions.
- [x] Test archive export/preparation and unsafe input rejection; independent security review.
- [x] Publish code/workflow, pass CI/deployment, enable schedule on main, run a real encrypted upload.
- [x] Download and verify S3 bytes/checksum independently using authorized AWS operator credentials; verify uploader denial with IAM policy simulation.
- [x] Rebuild a fresh, temporary host from GitHub and S3 without reading original-host files; validate restored service, account isolation and backup scheduling.
- [x] Record measured RPO/RTO scope, cutover/recovery access runbook and remaining policy limits; remove only the drill server.
- [x] Update affected project guides and current remaining-work summary; commit/push results.

## Evidence and rulings

See docs/reports/2026-10-21-offsite-recovery.md and guide10 section72. Export is limited to26h snapshots; clean-host prepare accepts retained7day archives. Restored execution config forces AI disabled while preserving the archived original. New-host bootstrap waits for PostgreSQL/Redis separately from the one-shot media init. Full service/authentication/backup recovery was observed, but production traffic was not switched. S3 freshness inspection received a separate metadata-only OIDC role. No long-lived AWS keys were installed. New synthetic admin and all recovery data were removed with the guarded temporary-instance deletion.
