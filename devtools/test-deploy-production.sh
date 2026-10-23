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
export OLD_SHA=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
export OLD_API=sha256:$(printf '1%.0s' {1..64}) OLD_WORKER=sha256:$(printf '2%.0s' {1..64}) OLD_WEB=sha256:$(printf '3%.0s' {1..64})
export NEW_API=sha256:$(printf '4%.0s' {1..64}) NEW_WORKER=sha256:$(printf '5%.0s' {1..64}) NEW_WEB=sha256:$(printf '6%.0s' {1..64})
export BRIDGE_API=sha256:$(printf '7%.0s' {1..64})
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
  "merge --ff-only $SHA") [[ $SCENARIO != merge-failure ]] || exit 1; touch "$MOCK_HOME/merged" ;;
  'diff --quiet '*) [[ $SCENARIO != schema-change ]] ;;
  'rev-parse HEAD') if [[ -f $MOCK_HOME/merged ]]; then echo "$SHA"; else echo "$OLD_SHA"; fi ;;
  "show $OLD_SHA:compose.production.yaml") printf 'services: {}
' ;;
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
printf 'docker %s\n' "$*" >> "$MOCK_LOG"
if [[ $1 == inspect ]]; then
  case ${!#} in
    factlens-api-1)
      if [[ -f $MOCK_HOME/switched && ! -f $MOCK_HOME/rolled-back && $SCENARIO != image-mismatch ]]; then echo "$NEW_API"
      elif [[ -f $MOCK_HOME/rolled-back && $SCENARIO == bridge-failure ]]; then echo "$BRIDGE_API"
      else echo "$OLD_API"; fi;;
    factlens-worker-1) if [[ -f $MOCK_HOME/switched && ! -f $MOCK_HOME/rolled-back ]]; then echo "$NEW_WORKER"; else echo "$OLD_WORKER"; fi;;
    factlens-web-1) if [[ -f $MOCK_HOME/switched && ! -f $MOCK_HOME/rolled-back ]]; then echo "$NEW_WEB"; else echo "$OLD_WEB"; fi;;
    *) exit 99;;
  esac
  exit 0
fi
if [[ "$1 $2" == 'image inspect' ]]; then
  case $4 in
    *migration-control*)
      if [[ ( $SCENARIO == legacy || $SCENARIO == bridge* ) && ${!#} == "$OLD_API" ]]; then exit 1; fi
      echo v1;;
    *bridge-base*) [[ $SCENARIO == bridge* ]] || exit 1; echo "$OLD_SHA";;
    *revision*) if [[ $SCENARIO == revision-failure ]]; then echo wrong; else echo "$SHA"; fi;;
    '{{.Id}}')
      case ${!#} in
        factlens-api:rollback-no-migrate-*) echo "$BRIDGE_API";;
        factlens-api:*) echo "$NEW_API";;
        factlens-worker:*) echo "$NEW_WORKER";;
        factlens-web:*) echo "$NEW_WEB";;
        *) exit 99;;
      esac;;
    *) exit 99;;
  esac
  exit 0
fi
if [[ $1 == run ]]; then
  [[ "$1 $2 $3 $4 $5 $6 $7" == 'run --rm --network none --read-only --entrypoint node' ]]
  [[ "$9 ${10}" == '--check /app/apps/api/dist/server.js' ]]
  [[ $SCENARIO != runtime-failure || $8 != "$NEW_API" ]]
  exit
fi
[[ "$1 $2 $3 $4 $5 $6 $7 $8" == "compose --project-name factlens --project-directory $MOCK_HOME/factlens --env-file $MOCK_HOME/factlens/.env.production -f" ]]
shift 9
rollback=0
if [[ $1 == -f ]]; then
  case $2 in
    */rollback.yaml)
      rollback=1
      grep -q 'FACTLENS_AUTO_MIGRATE: "false"' "$2"
      cat "$2" >> "$MOCK_LOG"
      ;;
    */rollout.yaml) cat "$2" >> "$MOCK_LOG";;
    *) exit 99;;
  esac
  shift 2
fi
printf 'compose %s\n' "$*" >> "$MOCK_LOG"
case "$*" in
  'build --no-cache api worker web') [[ $SCENARIO != build-failure ]] ;;
  'ps -q postgres') if [[ $SCENARIO == database-changed && -f $MOCK_HOME/switched ]]; then echo changed; else echo factlens-postgres-1; fi;;
  'ps -q redis') echo factlens-redis-1;;
  'ps -q api') echo factlens-api-1;;
  'ps -q worker') echo factlens-worker-1;;
  'ps -q web') echo factlens-web-1;;
  'up -d --no-deps --no-build --pull never --wait --wait-timeout 180 api worker web')
    if ((rollback)); then touch "$MOCK_HOME/rolled-back"; [[ $SCENARIO != rollback-failure ]]
    else touch "$MOCK_HOME/switched"; [[ $SCENARIO != up-failure ]]; fi;;
  *) echo "Unexpected compose invocation: $*" >&2; exit 99 ;;
esac
MOCK
cat > "$fixture/bin/python3" <<'MOCK'
#!/usr/bin/env bash
set -eu
case "$1" in
  devtools/production-preflight.py)
    echo preflight >> "$MOCK_LOG"
    if [[ $SCENARIO == stdin-consumer ]]; then cat >/dev/null; fi
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
[[ "$1 $2 $3 $4 $5 $6" == '--fail --silent --connect-timeout 5 --max-time 20' ]]
if [[ -f $MOCK_HOME/rolled-back && $SCENARIO != rollback-health && $SCENARIO != state-health ]]; then echo '{"status":"ready"}'; exit 0; fi
if [[ $SCENARIO == rollback-health || $SCENARIO == state-health && -f $MOCK_HOME/rolled-back ]]; then echo '{"status":"bad"}'; exit 0; fi
case "$url" in
  http://127.0.0.1:3300/api/health) [[ $SCENARIO != loopback-failure ]] || exit 22 ;;
  https://factlens.pigs0516.com/api/health)
    [[ $SCENARIO != public-failure && $SCENARIO != rollback-failure && $SCENARIO != bridge-failure ]] || exit 22
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
cat > "$fixture/bin/sync" <<'MOCK'
#!/usr/bin/env bash
exit 0
MOCK
cat > "$fixture/bin/mv" <<'MOCK'
#!/usr/bin/env bash
set -eu
if [[ $SCENARIO == state-health && -f $MOCK_HOME/switched && ! -f $MOCK_HOME/state-failed ]]; then
  touch "$MOCK_HOME/state-failed"
  exit 1
fi
exec /usr/bin/mv "$@"
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
  rm -f "$MOCK_HOME"/{merged,switched,rolled-back,state-failed,.factlens-deployed-sha,.factlens-recovery-required}
  if [[ $SCENARIO == recovery-blocked ]]; then echo pending > "$MOCK_HOME/.factlens-recovery-required"; fi
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
for SCENARIO in wrong-root wrong-marker lock-failure wrong-origin wrong-branch dirty status-failure tracked-private fetch-failure target-private diverged recovery-blocked; do
  run_case "$SCENARIO" fail
  assert_absent '^compose |^backup$'
done
run_case stale pass
assert_absent '^git merge|^compose |^backup$'
assert_present '^git fetch '
for SCENARIO in schema-change preflight-failure build-failure legacy runtime-failure revision-failure merge-failure; do
  run_case "$SCENARIO" fail
  assert_absent '^compose (stop|up|start)|^backup$'
done
for SCENARIO in active-jobs active-uploads guard-failure guard-invalid; do
  run_case "$SCENARIO" fail
  assert_present '^active-work-check$'
  assert_absent '^compose (stop|up|start)|^backup$'
done
for SCENARIO in up-failure loopback-failure public-failure not-ready invalid-json image-mismatch bridge-failure; do
  run_case "$SCENARIO" fail
  assert_absent '^backup$|^compose (stop|start)'
  assert_present '^compose up -d --no-deps --no-build --pull never --wait --wait-timeout 180 api worker web$'
  grep -q 'Previous app images restored' "$evidence/$SCENARIO.output.log"
  [[ $(<"$MOCK_HOME/.factlens-deployed-sha") == "$OLD_SHA" && ! -e $MOCK_HOME/.factlens-recovery-required ]]
done
for SCENARIO in rollback-failure rollback-health state-health database-changed; do
  run_case "$SCENARIO" fail
  [[ -f $MOCK_HOME/.factlens-recovery-required && $(<"$MOCK_HOME/.factlens-deployed-sha") == "$OLD_SHA" ]]
  grep -q 'Recovery required' "$evidence/$SCENARIO.output.log"
done
for SCENARIO in stdin-consumer success bridge; do
  run_case "$SCENARIO" pass
  assert_absent '^backup$|^compose (stop|start)|npm run migrate|recovery.py'
  assert_present '^compose build --no-cache api worker web$'
  assert_present '^health https://factlens.pigs0516.com/api/health$'
  [[ $(<"$MOCK_HOME/.factlens-deployed-sha") == "$SHA" && ! -e $MOCK_HOME/.factlens-recovery-required ]]
done
assert_absent 'reset|checkout|prune|down|restore'
success_matcher=$(grep -F 'grep -Fx "Deployed $DEPLOY_SHA;' "$(dirname "$script")/../.github/workflows/deploy.yml" | cut -d '"' -f2)
[[ -n $success_matcher ]]
success_matcher=${success_matcher/\$DEPLOY_SHA/$SHA}
grep -Fx "$success_matcher" "$evidence/success.output.log"
printf 'PASS: %s mock scenarios; app-only rollout, rollback, schema and recovery gates verified.\n' "$case_count"
printf 'Artifacts: %s\n' "$evidence"
