#!/usr/bin/env bash
# Run from ~/factlens: bash -s -- <commit-sha> < devtools/deploy-production.sh
set +x
set -Eeuo pipefail
umask 077

fail() { printf '%s\n' "$1" >&2; exit 1; }
[[ $# == 1 && $1 =~ ^[[:xdigit:]]{40}$ ]] || fail 'Expected one full 40-hex commit SHA.'
sha=${1,,}
ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || fail 'Not a Git checkout.'
[[ "$ROOT" == "$(pwd -P)" && "$ROOT" == "$(cd "$HOME/factlens" && pwd -P)" ]] ||
  fail 'Run from the ~/factlens checkout root.'
cd "$ROOT"

exec 9>"$HOME/.factlens-deploy.lock"
flock -x 9 || fail 'Could not acquire deployment lock.'
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
git merge --ff-only "$sha" >/dev/null 2>&1 || fail 'Fast-forward update failed.'
[[ $(git rev-parse HEAD) == "$sha" ]] || fail 'Checkout does not match requested SHA.'

# Both preflight and recovery must use the local production Docker daemon.
unset DOCKER_CONTEXT DOCKER_TLS DOCKER_TLS_VERIFY DOCKER_CERT_PATH COMPOSE_PROFILES
export DOCKER_HOST=unix:///var/run/docker.sock
compose=(docker compose --project-name factlens --env-file .env.production -f compose.production.yaml)
stage=preflight
resume_existing=0
finish() {
  rc=$?
  trap - EXIT
  if (( resume_existing )); then
    if ! "${compose[@]}" start web api worker >/dev/null 2>&1; then
      printf '%s\n' 'Existing containers could not restart; operator intervention required.' >&2
      rc=1
    fi
  fi
  if (( rc != 0 )); then
    printf 'Deployment failed at %s; no automatic database restore or schema rollback.\n' "$stage" >&2
  fi
  exit "$rc"
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
python3 devtools/production-preflight.py >/dev/null 2>&1
stage=build
"${compose[@]}" build >/dev/null 2>&1

stage=backup-preparation
backup_root="$HOME/factlens-backups"
[[ ! -L "$backup_root" ]] || fail 'Backup root must not be a symlink.'
mkdir -p -m 700 "$backup_root"
[[ -d "$backup_root" && $(stat -c '%u:%a' "$backup_root") == "$(id -u):700" ]] ||
  fail 'Backup root must be owned by this user with mode 0700.'
backup_run=$(mktemp -d "$backup_root/deploy-${sha:0:12}.XXXXXXXX")
database_container=$("${compose[@]}" ps -q postgres 2>/dev/null)
[[ "$database_container" =~ ^[a-zA-Z0-9_-]+$ ]] || fail 'Expected one existing PostgreSQL container.'
stage=active-work-check
active_work=$(docker --host=unix:///var/run/docker.sock exec -i "$database_container" \
  psql -X -U factlens -d factlens -v ON_ERROR_STOP=1 -At -c \
  "SELECT CASE WHEN EXISTS (SELECT 1 FROM jobs WHERE status IN
  ('queued','validating','transcribing','extracting','retrieving','validating_evidence'))
  OR EXISTS (SELECT 1 FROM upload_leases WHERE expires_at > now())
  THEN 'busy' ELSE 'idle' END;" 2>/dev/null)
[[ "$active_work" == idle ]] || fail 'Active jobs or uploads detected; retry during maintenance.'
# shortcut: requests can arrive after this check; add ingress draining for a race-free maintenance gate.
stage=stop
resume_existing=1
"${compose[@]}" stop web api worker >/dev/null 2>&1
stage=backup
python3 devtools/recovery.py backup --container "$database_container" --database factlens \
  --directory "$backup_run/database" >/dev/null 2>&1

# Once up can apply migrations, restarting old images is not a safe rollback.
resume_existing=0
stage=up
"${compose[@]}" up -d --wait --wait-timeout 180 >/dev/null 2>&1
stage=health
for url in http://127.0.0.1:3300/api/health https://factlens.pigs0516.com/api/health; do
  curl --fail --silent --show-error --connect-timeout 5 --max-time 20 "$url" 2>/dev/null |
    python3 -c 'import json,sys; sys.exit(0 if json.load(sys.stdin).get("status") == "ready" else 1)' \
      >/dev/null 2>&1
done
printf 'Deployed %s; loopback and public health are ready.\n' "$sha"
