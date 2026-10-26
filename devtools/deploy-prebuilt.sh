#!/usr/bin/env bash
# Separate prebuilt path. Original deploy-production.sh/build guard remain unchanged.
main() {
set +x
set -Eeuo pipefail
umask 077

fail() { printf '%s\n' "$1" >&2; exit 1; }
[[ $# == 3 && $1 =~ ^[[:xdigit:]]{40}$ && $2 =~ ^[0-9]+$ && $3 =~ ^[0-9]+$ ]] || fail 'Expected one full 40-hex commit SHA.'
sha=${1,,}
incoming="$HOME/.factlens-incoming/$2-$3"
[[ ! -L $HOME/.factlens-incoming && -d $incoming && ! -L $incoming ]] || fail 'Private incoming directory required.'
[[ $(stat -c '%u:%a' "$incoming") == "$(id -u):700" ]] || fail 'Incoming owner/mode invalid.'
ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || fail 'Not a Git checkout.'
[[ "$ROOT" == "$(pwd -P)" && "$ROOT" == "$(cd "$HOME/factlens" && pwd -P)" ]] ||
  fail 'Run from the ~/factlens checkout root.'
cd "$ROOT"

exec 9>"$HOME/.factlens-deploy.lock"
flock -x 9 || fail 'Could not acquire deployment lock.'
state="$HOME/.factlens-deployed-sha"
recovery="$HOME/.factlens-recovery-required"
[[ ! -e $recovery ]] || fail 'Recovery required: verify app images and deployment state before retrying.'
[[ -f .factlens-deploy-target && ! -L .factlens-deploy-target &&
   $(<.factlens-deploy-target) == factlens-ai ]] || fail 'Wrong deployment target marker.'
tracked_private=$(git ls-files -- .factlens-deploy-target .env.production)
[[ -z "$tracked_private" ]] ||
  fail 'Host marker and production environment must be untracked.'
case "$(git remote get-url --all origin)" in
  https://github.com/P-GISE/Fact-checking-website|https://github.com/P-GISE/Fact-checking-website.git|git@github.com:P-GISE/Fact-checking-website|git@github.com:P-GISE/Fact-checking-website.git|ssh://git@github.com/P-GISE/Fact-checking-website.git) ;;
  *) fail 'Wrong repository origin.' ;;
esac
[[ $(git symbolic-ref --short HEAD) == work ]] || fail 'Current branch must be work.'
tracked_state=$(git status --porcelain --untracked-files=no) || fail 'Cannot inspect tracked Git state.'
[[ -z "$tracked_state" ]] || fail 'Tracked Git state must be clean.'

git fetch --no-tags origin refs/heads/work:refs/remotes/origin/work >/dev/null 2>&1 ||
  fail 'Fetching origin/work failed.'
[[ "$sha" == "$(git rev-parse refs/remotes/origin/work)" ]] || {
  printf '%s\n' 'Stale deployment skipped: requested SHA is not origin/work HEAD.'
  exit 0
}
for private_file in .factlens-deploy-target .env.production; do
  if git cat-file -e "$sha:$private_file" 2>/dev/null; then
    fail 'Target commit must not track host-private files.'
  fi
done
git merge-base --is-ancestor HEAD "$sha" || fail 'Local work cannot fast-forward to the requested SHA.'
previous_sha=$(git rev-parse HEAD)
if [[ -f $state ]]; then previous_sha=$(cat "$state"); fi
[[ $previous_sha =~ ^[0-9a-f]{40}$ ]] || fail 'Invalid deployed SHA state.'
git diff --quiet "$previous_sha" "$sha" -- apps/api/migrations apps/api/src/db.ts ||
  fail 'Schema change requires an explicitly approved migration.'

unset DOCKER_CONTEXT DOCKER_TLS DOCKER_TLS_VERIFY DOCKER_CERT_PATH COMPOSE_PROFILES
export DOCKER_HOST=unix:///var/run/docker.sock FACTLENS_DEPLOY_SHA=$sha
compose=(docker compose --project-name factlens --project-directory "$ROOT" --env-file "$ROOT/.env.production" -f "$ROOT/compose.production.yaml")
stage=preflight
switched=0
git_switched=0
scratch=$(mktemp -d "$HOME/.factlens-deploy.XXXXXXXX")
health() {
  local url
  for url in http://127.0.0.1:3300/api/health https://factlens.pigs0516.com/api/health; do
    curl --fail --silent --connect-timeout 5 --max-time 20 "$url" 2>/dev/null |
      python3 -c 'import json,sys; sys.exit(0 if json.load(sys.stdin).get("status") == "ready" else 1)' >/dev/null 2>&1 || return 1
  done
}
preserved() {
  [[ $("${compose[@]}" ps -q postgres 2>/dev/null) == "$database_container" &&
     $("${compose[@]}" ps -q redis 2>/dev/null) == "$redis_container" &&
     $(docker inspect --format '{{json .Mounts}}' "$database_container" "$redis_container" 2>/dev/null) == "$storage_identity" ]]
}
images_match() {
  local service cid actual expected
  for service in api worker web; do
    if [[ $1 == previous ]]; then expected=${previous_images[$service]}; else expected=${next_images[$service]}; fi
    cid=$("${compose[@]}" ps -q "$service" 2>/dev/null) || return 1
    actual=$(docker inspect --format '{{.Image}}' "$cid" 2>/dev/null) || return 1
    [[ $actual == "$expected" ]] || return 1
  done
}
image_gate() {
  [[ $(docker image inspect --format '{{index .Config.Labels "io.factlens.migration-control"}}' "$1" 2>/dev/null) == v1 ]] &&
    docker run --rm --network none --read-only --entrypoint node "$1" --check /app/apps/api/dist/server.js >/dev/null 2>&1
}
clear_recovery() {
  if rm -f "$recovery" && sync "$HOME"; then return 0; fi
  printf '%s\n' "$sha" > "$recovery"
  sync "$recovery" "$HOME"
  return 1
}
finish() {
  local rc=$? restored=1
  trap - EXIT
  if ((rc != 0 && switched)); then
    docker compose --project-name factlens --project-directory "$ROOT" --env-file "$ROOT/.env.production" \
      -f "$scratch/previous.yaml" -f "$scratch/rollback.yaml" \
      up -d --no-deps --no-build --pull never --wait --wait-timeout 180 api worker web >/dev/null 2>&1 || restored=0
    images_match previous || restored=0
    health || restored=0
    preserved || restored=0
    { printf '%s\n' "$previous_sha" > "$state.tmp" && mv "$state.tmp" "$state" && sync "$state"; } || restored=0
    if ((restored)); then clear_recovery || restored=0; fi
    if ((restored)); then printf 'Previous app images restored; database and Redis containers preserved.\n' >&2
    else printf 'Recovery required; next deployment blocked.\n' >&2; fi
  fi
  if ((rc != 0 && git_switched)); then
    git reset --hard "$previous_sha" >/dev/null 2>&1 || restored=0
    [[ $(git rev-parse HEAD) == "$previous_sha" ]] || restored=0
    if ((!restored)); then printf '%s\n' "$sha" > "$recovery"; sync "$recovery" "$HOME"; fi
  fi
  if [[ -f $scratch/private-env ]]; then cmp -s .env.production "$scratch/private-env" || {
    cp -p "$scratch/private-env" .env.production
    printf '%s\n' "$sha" > "$recovery"
    rc=1
  }; fi
  rm -rf -- "$scratch"
  # Numeric run/attempt and non-symlink parent were verified before acquiring the lock.
  rm -rf -- "$incoming"
  if ((rc != 0)); then printf 'Deployment failed at %s; no database restore or migration was run.\n' "$stage" >&2; fi
  exit "$rc"
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
[[ -f .env.production && ! -L .env.production ]] || fail 'Private environment required.'
cp -p .env.production "$scratch/private-env"
for helper in prebuilt-preflight.py prebuilt_gate.py; do
  git show "$sha:devtools/$helper" > "$scratch/$helper" || fail 'Missing reviewed source helper.'
done
python3 "$scratch/prebuilt-preflight.py" --archive "$incoming/images.tar.gz" \
  --manifest "$incoming/manifest.json" --policy "$incoming/manifest.json" \
  --sha "$sha" >/dev/null 2>&1
database_container=$("${compose[@]}" ps -q postgres 2>/dev/null)
redis_container=$("${compose[@]}" ps -q redis 2>/dev/null)
[[ $database_container =~ ^[a-zA-Z0-9_-]+$ && $redis_container =~ ^[a-zA-Z0-9_-]+$ ]] || fail 'Expected existing database and Redis containers.'
storage_identity=$(docker inspect --format '{{json .Mounts}}' "$database_container" "$redis_container")
[[ -n $storage_identity ]] || fail 'Storage identity unavailable.'
declare -gA previous_images next_images
for service in api worker web; do
  cid=$("${compose[@]}" ps -q "$service" 2>/dev/null)
  [[ $cid =~ ^[a-zA-Z0-9_-]+$ ]] || fail 'Expected existing application containers.'
  previous_images[$service]=$(docker inspect --format '{{.Image}}' "$cid" 2>/dev/null)
  [[ ${previous_images[$service]} =~ ^sha256:[0-9a-f]{64}$ ]] || fail 'Cannot establish previous image IDs.'
done
stage=rollback-gate
if ! image_gate "${previous_images[api]}"; then
  bridge="factlens-api:rollback-no-migrate-$previous_sha"
  [[ $(docker image inspect --format '{{index .Config.Labels "io.factlens.bridge-base"}}' "$bridge" 2>/dev/null) == "$previous_sha" ]] ||
    fail 'Reviewed migration-free bridge image required for the current deployment.'
  previous_images[api]=$(docker image inspect --format '{{.Id}}' "$bridge" 2>/dev/null)
  [[ ${previous_images[api]} =~ ^sha256:[0-9a-f]{64}$ ]] && image_gate "${previous_images[api]}" ||
    fail 'Bridge runtime validation failed.'
fi
git show "$previous_sha:compose.production.yaml" > "$scratch/previous.yaml"
printf 'services:\n  api:\n    image: "%s"\n    environment:\n      FACTLENS_AUTO_MIGRATE: "false"\n  worker:\n    image: "%s"\n  web:\n    image: "%s"\n' \
  "${previous_images[api]}" "${previous_images[worker]}" "${previous_images[web]}" > "$scratch/rollback.yaml"
printf '%s\n' "$previous_sha" > "$state.tmp"
mv "$state.tmp" "$state"
sync "$state" "$HOME"
git merge --ff-only "$sha" >/dev/null 2>&1 || fail 'Fast-forward update failed.'
git_switched=1
[[ $(git rev-parse HEAD) == "$sha" ]] || fail 'Checkout does not match requested SHA.'
stage=import
gzip -dc "$incoming/images.tar.gz" | docker load >/dev/null 2>&1
new_api=$(docker image inspect --format '{{.Id}}' "factlens-api:$sha" 2>/dev/null)
[[ $(docker image inspect --format '{{index .Config.Labels "org.opencontainers.image.revision"}}' "$new_api" 2>/dev/null) == "$sha" ]] ||
  fail 'Built API revision does not match requested SHA.'
image_gate "$new_api" || fail 'Built API runtime validation failed.'
printf 'services:\n' > "$scratch/rollout.yaml"
for service in api worker web; do
  image=$(docker image inspect --format '{{.Id}}' "factlens-$service:$sha" 2>/dev/null)
  [[ $image =~ ^sha256:[0-9a-f]{64}$ ]] || fail 'Built application image missing.'
  next_images[$service]=$image
  printf '  %s:\n    image: "%s"\n' "$service" "$image" >> "$scratch/rollout.yaml"
  if [[ $service == api ]]; then printf '    environment:
      FACTLENS_AUTO_MIGRATE: "false"
' >> "$scratch/rollout.yaml"; fi
done
for service in api worker web; do
  [[ $(docker image inspect --format '{{index .Config.Labels "org.opencontainers.image.revision"}}' "factlens-$service:$sha") == "$sha" ]] || fail 'Imported image revision mismatch.'
done
cmp -s .env.production "$scratch/private-env" || fail 'Private environment changed.'
stage=active-work-check
active_work=$(docker --host=unix:///var/run/docker.sock exec -i "$database_container" \
  psql -X -U factlens -d factlens -v ON_ERROR_STOP=1 -At -c \
  "SELECT CASE WHEN EXISTS (SELECT 1 FROM jobs WHERE status IN
  ('queued','validating','transcribing','extracting','retrieving','validating_evidence'))
  OR EXISTS (SELECT 1 FROM upload_leases WHERE expires_at > now())
  THEN 'busy' ELSE 'idle' END;" 2>/dev/null)
[[ $active_work == idle ]] || fail 'Active jobs or uploads detected; retry during maintenance.'
# shortcut: requests can arrive after this check; ingress draining needs a separate approved change.
preserved || fail 'Database or Redis container changed before deployment.'
printf '%s\n' "$sha" > "$recovery"
sync "$recovery" "$HOME"
stage=up
switched=1
"${compose[@]}" -f "$scratch/rollout.yaml" up -d --no-deps --no-build --pull never --wait --wait-timeout 180 api worker web >/dev/null 2>&1
stage=health
images_match next || fail 'Running application image does not match rollout.'
health
preserved || fail 'Database or Redis container changed during deployment.'
cmp -s .env.production "$scratch/private-env" || fail 'Private environment changed during deployment.'
stage=state
printf '%s\n' "$sha" > "$state.tmp"
mv "$state.tmp" "$state"
sync "$state"
clear_recovery || fail 'Cannot clear recovery marker.'
printf 'Deployed %s; loopback and public health ready; database and Redis containers preserved.\n' "$sha"
}
main "$@" </dev/null
