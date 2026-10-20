#!/usr/bin/env bash
# External deployment commands are mocked; no network or Docker is used.
set -euo pipefail
script="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/deploy-production.sh"
real_python=${PYTHON3:-$(command -v python3)}
export REAL_PYTHON="$real_python"
evidence=${1:-$(mktemp -d "${TMPDIR:-/tmp}/factlens-deploy-test.XXXXXXXX")}
mkdir -p "$evidence"
evidence=$(cd "$evidence" && pwd)
fixture=$(mktemp -d "$evidence/fixture.XXXXXXXX")
mkdir -p "$fixture/bin" "$fixture/home/factlens"
export MOCK_HOME="$fixture/home" MOCK_LOG="$fixture/commands.log"
export SHA=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
export PATH="$fixture/bin:$PATH"

cat > "$fixture/bin/git" <<'MOCK'
#!/usr/bin/env bash
set -eu
printf 'git %s\n' "$*" >> "$MOCK_LOG"
case "$*" in
  'rev-parse --show-toplevel')
    if [[ $SCENARIO == wrong-root ]]; then echo /wrong-checkout
    else printf '%s\n' "$MOCK_HOME/factlens"; fi ;;
  'ls-files -- .factlens-deploy-target .env.production')
    [[ $SCENARIO != tracked-private ]] || echo .factlens-deploy-target ;;
  'remote get-url --all origin')
    if [[ $SCENARIO == wrong-origin ]]; then echo https://github.com/other/repo.git
    else echo git@github.com:P-GISE/Fact-checking-website.git; fi ;;
  'symbolic-ref --short HEAD')
    if [[ $SCENARIO == wrong-branch ]]; then echo main; else echo work; fi ;;
  'status --porcelain --untracked-files=no')
    [[ $SCENARIO != status-failure ]] || exit 1
    [[ $SCENARIO != dirty ]] || echo ' M compose.production.yaml' ;;
  'fetch --no-tags origin refs/heads/work:refs/remotes/origin/work')
    [[ $SCENARIO != fetch-failure ]] ;;
  'rev-parse refs/remotes/origin/work')
    if [[ $SCENARIO == stale ]]; then echo bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
    else echo "$SHA"; fi ;;
  cat-file*)
    [[ $SCENARIO == target-private ]] && exit 0
    exit 1 ;;
  "merge-base --is-ancestor HEAD $SHA") [[ $SCENARIO != diverged ]] ;;
  "merge --ff-only $SHA") [[ $SCENARIO != merge-failure ]] ;;
  'rev-parse HEAD') echo "$SHA" ;;
  *) echo "Unexpected git invocation: $*" >&2; exit 99 ;;
esac
MOCK
cat > "$fixture/bin/docker" <<'MOCK'
#!/usr/bin/env bash
set -eu
[[ ${DOCKER_HOST:-} == unix:///var/run/docker.sock && -z ${DOCKER_CONTEXT:-} ]]
if [[ $1 == --host=unix:///var/run/docker.sock ]]; then
  shift
  [[ "$*" == 'exec -i factlens-postgres-1 psql -X -U factlens -d factlens -v ON_ERROR_STOP=1 -At -c '* ]]
  sql=${!#}
  [[ "$sql" == *"SELECT 1 FROM jobs WHERE status IN"* &&
     "$sql" == *"('queued','validating','transcribing','extracting','retrieving','validating_evidence')"* &&
     "$sql" == *"OR EXISTS (SELECT 1 FROM upload_leases WHERE expires_at > now())"* &&
     "$sql" == *"THEN 'busy' ELSE 'idle' END;" ]]
  printf '%s\n' "$sql" > "$MOCK_HOME/$SCENARIO.sql"
  echo active-work-check >> "$MOCK_LOG"
  case "$SCENARIO" in
    active-jobs|active-uploads) echo busy ;;
    guard-failure) exit 1 ;;
    guard-invalid) echo unexpected ;;
    *) echo idle ;;
  esac
  exit 0
fi
[[ "$1 $2 $3 $4 $5 $6 $7" == 'compose --project-name factlens --env-file .env.production -f compose.production.yaml' ]]
shift 7
printf 'compose %s\n' "$*" >> "$MOCK_LOG"
case "$*" in
  build) [[ $SCENARIO != build-failure ]] ;;
  'ps -q postgres') echo factlens-postgres-1 ;;
  'stop web api worker') [[ $SCENARIO != stop-failure ]] ;;
  'start web api worker') [[ $SCENARIO != restart-failure ]] ;;
  'up -d --wait --wait-timeout 180') [[ $SCENARIO != up-failure ]] ;;
  *) echo "Unexpected compose invocation: $*" >&2; exit 99 ;;
esac
MOCK
cat > "$fixture/bin/python3" <<'MOCK'
#!/usr/bin/env bash
set -eu
case "$1" in
  devtools/production-preflight.py)
    echo preflight >> "$MOCK_LOG"
    [[ $SCENARIO != preflight-failure ]] ;;
  devtools/recovery.py)
    [[ "$2 $3 $4 $5 $6 $7" == 'backup --container factlens-postgres-1 --database factlens --directory' ]]
    [[ "$8" == "$MOCK_HOME"/factlens-backups/deploy-*/database && ! -e "$8" ]]
    [[ $(umask) == 0077 ]]
    echo backup >> "$MOCK_LOG"
    [[ $SCENARIO != backup-failure && $SCENARIO != restart-failure ]] || exit 1
    mkdir -m 700 "$8"
    printf 'mock dump\n' > "$8/database.dump" ;;
  -c)
    # Execute the actual JSON readiness assertion, rather than mocking its result.
    exec "$REAL_PYTHON" "$@" ;;
  *) exit 99 ;;
esac
MOCK
cat > "$fixture/bin/curl" <<'MOCK'
#!/usr/bin/env bash
set -eu
url=${!#}
printf 'health %s\n' "$url" >> "$MOCK_LOG"
[[ "$1 $2 $3 $4 $5 $6 $7" == '--fail --silent --show-error --connect-timeout 5 --max-time 20' ]]
case "$url" in
  http://127.0.0.1:3300/api/health) [[ $SCENARIO != loopback-failure ]] || exit 22 ;;
  https://factlens.pigs0516.com/api/health)
    [[ $SCENARIO != public-failure ]] || exit 22
    if [[ $SCENARIO == not-ready ]]; then echo '{"status":"starting"}'; exit 0; fi
    if [[ $SCENARIO == invalid-json ]]; then echo '<html>error</html>'; exit 0; fi ;;
  *) exit 99 ;;
esac
echo '{"status":"ready"}'
MOCK
cat > "$fixture/bin/flock" <<'MOCK'
#!/usr/bin/env bash
set -eu
[[ "$*" == '-x 9' ]]
printf 'lock\n' >> "$MOCK_LOG"
[[ $SCENARIO != lock-failure ]]
MOCK
cat > "$fixture/bin/stat" <<'MOCK'
#!/usr/bin/env bash
set -eu
[[ "$1 $2 $3" == "-c %u:%a $MOCK_HOME/factlens-backups" ]]
echo private-backup-check >> "$MOCK_LOG"
if [[ $SCENARIO == unsafe-backup-root ]]; then printf '%s:755\n' "$(id -u)"
else printf '%s:700\n' "$(id -u)"; fi
MOCK
chmod +x "$fixture/bin/"*

assert_absent() { if grep -Eq "$1" "$MOCK_LOG"; then echo "FAIL $SCENARIO: unexpected $1" >&2; exit 1; fi; }
assert_present() { grep -Eq "$1" "$MOCK_LOG" || { echo "FAIL $SCENARIO: missing $1" >&2; exit 1; }; }
case_count=0
run_case() {
  export SCENARIO=$1
  local expected=$2 requested=${3:-$SHA} rc=0
  printf 'factlens-ai\n' > "$MOCK_HOME/factlens/.factlens-deploy-target"
  [[ $SCENARIO != wrong-marker ]] || printf 'other-host\n' > "$MOCK_HOME/factlens/.factlens-deploy-target"
  printf 'scenario %s\n' "$SCENARIO" > "$MOCK_LOG"
  (
    export HOME="$MOCK_HOME" DOCKER_CONTEXT=wrong-remote
    cd "$HOME/factlens"
    bash -s -- "$requested" < "$script"
  ) > "$evidence/$SCENARIO.output.log" 2>&1 || rc=$?
  printf '%s\n' "$rc" > "$evidence/$SCENARIO.exit"
  cp "$MOCK_LOG" "$evidence/$SCENARIO.commands.log"
  if [[ $expected == pass ]]; then
    [[ $rc == 0 ]] || { echo "FAIL $SCENARIO: exit $rc" >&2; exit 1; }
  else
    [[ $rc != 0 ]] || { echo "FAIL $SCENARIO: unexpectedly succeeded" >&2; exit 1; }
  fi
  case_count=$((case_count + 1))
}

run_case invalid-sha fail nope
assert_absent 'git |compose |backup'
for SCENARIO in wrong-root wrong-marker lock-failure wrong-origin wrong-branch dirty status-failure tracked-private fetch-failure target-private diverged merge-failure; do
  run_case "$SCENARIO" fail
  assert_absent '^compose |^backup$'
done
run_case stale pass
assert_absent '^git merge|^compose |^backup$'
assert_present '^git fetch '
for SCENARIO in preflight-failure build-failure unsafe-backup-root; do
  run_case "$SCENARIO" fail
  assert_absent '^compose (stop|up|start)|^backup$'
done
for SCENARIO in active-jobs active-uploads guard-failure guard-invalid; do
  run_case "$SCENARIO" fail
  assert_present '^active-work-check$'
  assert_absent '^compose (stop|up|start)|^backup$'
done
for SCENARIO in stop-failure backup-failure restart-failure; do
  run_case "$SCENARIO" fail
  assert_present '^compose start web api worker$'
  assert_absent '^compose up|^health '
done
for SCENARIO in up-failure loopback-failure public-failure not-ready invalid-json; do
  run_case "$SCENARIO" fail
  assert_present '^backup$'
  assert_present '^compose up -d --wait --wait-timeout 180$'
  assert_absent '^compose start'
done
run_case success pass
grep -E '^(lock|git fetch |git merge |preflight|compose |private-backup-check|active-work-check|backup$|health )' "$MOCK_LOG" > "$evidence/success.order.actual"
cat > "$evidence/success.order.expected" <<ORDER
lock
git fetch --no-tags origin refs/heads/work:refs/remotes/origin/work
git merge --ff-only $SHA
preflight
compose build
private-backup-check
compose ps -q postgres
active-work-check
compose stop web api worker
backup
compose up -d --wait --wait-timeout 180
health http://127.0.0.1:3300/api/health
health https://factlens.pigs0516.com/api/health
ORDER
diff -u "$evidence/success.order.expected" "$evidence/success.order.actual"
assert_absent 'reset|checkout|prune|down|restore'
printf 'PASS: %s mock scenarios; SSH stdin invocation and exact success ordering verified.\n' "$case_count"
printf 'Artifacts: %s\n' "$evidence"
