# FactLens Operations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the authorized static-IP, backup/isolated-restore and alarm setup, while checking operational security and updating GitHub/guides.

**Architecture:** Existing Sydney factlens-ai only. Pin the authenticated SSH host key when moving to a static IP. Reuse recovery.py for private online database backups and restore into a disposable network-isolated PostgreSQL container; preserve all production volumes. Use systemd for daily backups and GitHub Actions/native Lightsail metrics for monitoring, with email confirmation tracked separately.

**Tech Stack:** Lightsail console/Aside, OpenSSH, Docker/PostgreSQL17, Python standard library, systemd, GitHub Actions.

**Spec:** docs/08_운영_배포.md; docs/99_해야할일..md; user request of2026-10-20.

## Global Constraints

- Only P-GISE/Fact-checking-website and factlens-ai; no unrelated servers.
- Preserve .env.production, current accounts, production DB/media and pinned SSH fingerprint.
- No real AI calls. No secret/dump contents in logs, chat or Git.
- Confirmed schedule03:00 Asia/Seoul and7-day daily-backup retention; user preferences take precedence.
- No default-branch change. GitHub schedules require a workflow on the existing default branch; publish only that monitor configuration there if used.
- Backup scope remains database-only with accounts disabled and ephemeral reports/media discarded on restoration. Remote off-host copies are separate from local backup/restore success.

## Review Focus

- New static IP must match the existing authenticated server key before changing deployment host/known_hosts.
- Backup completion requires private ownership/modes and matching manifest/hash; partial output must not become fresh backup evidence.
- Retention must never delete deployment backups, symlinks or unrelated paths.
- Restore must have no published ports, no shared production volumes and no application connections; remove only its uniquely named container after aggregate checks.
- Alert creation, confirmed subscription and tested delivery are separate states; no outage is induced to test an alarm.

### Task1: Stable host and native alarms (parent)

- [x] Confirm AWS identity/instance, attach a named static IP, verify key/SSH/HTTPS, update GitHub host/known_hosts.
- [x] Add instance-status/CPU alarms and confirm email subscription/delivery where the user can complete the confirmation.

### Task2: Scheduled private backups and check command (worker)

**Files:** devtools/operations.py; devtools/systemd/factlens-backup.service; devtools/systemd/factlens-backup.timer; apps/worker/tests/test_operations.py.

- [x] Add failing tests for partial/corrupt/stale backups, safe retention, process failures and check exit status.
- [x] Implement bounded standard-library backup/check CLI reusing recovery.py and the deployment lock.
- [x] Validate tests; parent installs units as ubuntu and runs a real successful backup.

### Task3: Isolated restore and ongoing monitor (parent)

- [x] Run a bounded disposable PostgreSQL container with network none/no ports/no production volume, restore the new backup to a new isolated database and check only aggregate sanitization/cost counts.
- [x] Configure monitor job using existing pinned SSH credentials, check failure behavior without breaking production, and enable its real scheduler on the default branch.
- [x] Independent code/security review, CI/deploy checks and real timer/backup/restore/alarm verification; publish result and residual limitations to project guides.

## Execution record

See docs/reports/2026-10-20-operations.md and guide10 section71 for commit/run links, Linux fixture correction, actual restore aggregates and limitations. User confirmed03KST/7days/email policy and actual alarm email delivery. A post-deploy smoke exposed old local-auth expectations; account-mode checking was added with real HTTP regression coverage. No production outage was induced, and no external/S3 backup was claimed.
