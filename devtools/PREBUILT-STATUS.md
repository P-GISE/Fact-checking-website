# FactLens prebuilt source: first verification boundary

This branch is not an operational prebuilt deployment implementation yet. Existing
`deploy-production.sh`, `production-preflight.py`, schema checks and production
deployment behavior are unchanged. The new helpers never import images or modify
services. No artifact publication step has been added.

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
  are validation helpers only: no artifact download/publication is wired yet.
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
  an automatically trusted policy. This helper is not connected to a CI run yet.

Still required before publication or production activation:

1. Isolated daemon+containerd+client+decompressor measured peak-memory/OOM benchmark;
   explicit baseline/evidence/margin review. The 358.99 MiB size pilot is not this.
2. Confirm account artifact quota and overage protection, then implement single
   retention-one-day artifact publication with inner/outer digest validation.
3. Wire exact prerequisite API validation into the existing push/work deploy job.
   Preserve security/verify/build-publish dependencies and reject partial reruns.
4. Implement app-only transactional import/rollout and test rollback, Git state,
   environment, DB/Redis container+volume identity, migration-free bridge and active
   work gates. Do not reuse the build entrypoint by weakening its memory threshold.
5. Independent review and explicit activation approval. Existing approved services,
   cron, tunnel and DB remain outside this source change.

Local validation: meaningful initial RED (missing implementation), then thirteen tests
with adversarial subcases GREEN; syntax compilation and diff whitespace checks.
Linux execution is supplied by the existing verify job, not claimed until observed.
