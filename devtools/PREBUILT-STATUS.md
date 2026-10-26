# FactLens prebuilt source: source integration, default off

This branch contains an unactivated prebuilt delivery source path. Existing
`deploy-production.sh`, `production-preflight.py` and their schema/build resource
guards remain unchanged. The original path runs while the prebuilt flag is off.
New build/publication/deploy jobs require an explicit prebuilt flag; the unmeasured
policy additionally rejects build/publication even if that flag is accidentally enabled.
No production flag, artifact publication or remote execution has been performed.

Implemented and tested:

- Exact repository/workflow/run/attempt/event/work source verification. The three
  prerequisite job names must each occur once and be completed successfully. The
  current deployment job and overall run may still be in progress.
- Read-only authenticated API evidence collection, complete attempt-specific job
  pagination and latest work ref check. Token remains in memory; redirects fail.
- Docker archive inspection without extraction: bounded expansion, no path escape,
  links, device entries or duplicate paths; exactly three source-specific tags;
  expected config IDs, linux/amd64, revision labels, runtime command/user contracts,
  and API migration-control marker.
- Artifact API identity and ZIP validators reject wrong repository/work/SHA/run/
  attempt/name/ID, expired artifacts, mismatched outer digest, extra ZIP entries,
  links/encryption/oversized files, wrong inner manifest and archive checksum. These
  are wired before pinned SSH preparation in the disabled deploy-prebuilt job.
- Import preflight validates checksum, archive and private environment ownership;
  observes available memory and both scratch/Docker disk free space. An exact-bundle
  measured policy with no OOM and reserve is mandatory. Disk floor remains 10 GiB,
  additionally reserving compressed/new/rollback image space.
- `import-resource-policy.json` deliberately remains **unmeasured** and rejects
  import. The existing 1.5 GiB server-build guard remains unchanged.
- A source-only isolated benchmark helper starts a private socket/data-root Docker
  daemon inside a bounded cgroup. Copy, decompressor, client, daemon and its child
  containerd share accounting. It inspects the three imported image tags and records
  peak/OOM metadata. A measured result is still `measurement-requires-review`, not
  an automatically trusted policy. The disabled build-publish path calls it for every exact bundle, subject to a source-reviewed measured envelope. It has not actually been executed.

Source integration now includes build-publish needs security+verify, one retention-one-day
artifact, exact API/ZIP/download verification before remote transfer, and a separate
app-only import transaction preserving schema/bridge/active-work/health/recovery gates.
Each built image additionally passes a fixed-SHA Trivy OS/library gate, rejecting
unrecognized OS packages, missing API/worker libraries, findings or tool errors.
It records DB/Redis mount identities, compares private environment in memory and restores
Git state/environment on failure. It never builds on the server, prunes images, changes
DB/Redis services, migrates data, or alters tunnel/cron/backup configuration.

Still required before publication or production activation:

1. Execute and independently review the isolated import measurement and a conservative
   envelope/margin on an approved standard runner; source policy remains unmeasured.
   Each future exact bundle is measured again within that reviewed envelope.
2. Confirm account artifact quota and overage protection before setting the storage
   approval variable. Public runner free usage is not artifact storage proof.
3. Complete independent source review and Linux transaction regressions, then verify
   real server available memory/disk and migration-free rollback bridge readiness.
4. Explicit activation approval. No variables are modified by this PR. The original
   1.5 GiB no-cache build preflight remains unchanged and is not a shortcut import gate.
5. The image OS/library gate is implemented but has not actually run while the new
   path is disabled. Its real findings remain unverified; do not claim image packages
   or production import are proven safe.

Local validation includes meaningful initial RED and adversarial provenance/resource/
archive/artifact/workflow tests plus reused app-only transaction rollback scenarios.
Actual Linux results and unmeasured constraints must be reported separately.
