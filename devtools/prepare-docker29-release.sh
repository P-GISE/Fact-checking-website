#!/usr/bin/env bash
# CI measurement only. This does not approve an import envelope or production runtime.
set -Eeuo pipefail
umask 077
[[ ${GITHUB_ACTIONS:-} == true && ${GITHUB_REPOSITORY:-} == P-GISE/Fact-checking-website ]]
[[ ${GITHUB_EVENT_NAME:-} == push && ${GITHUB_REF:-} == refs/heads/work ]]
[[ ${FACTLENS_PREBUILT_ENABLED:-} == true && ${ARTIFACT_STORAGE_APPROVED:-} == true ]]
[[ -n ${RUNNER_TEMP:-} && -n ${GITHUB_OUTPUT:-} ]]
python3 - <<'PY'
import json,sys
from pathlib import Path
sys.path.insert(0,'devtools')
from prebuilt_gate import validate_release_envelope
validate_release_envelope(json.loads(Path('devtools/import-resource-policy.json').read_text()),
                          json.loads(Path('devtools/docker29-release-profile.json').read_text()))
PY
unset DOCKER_CONTEXT DOCKER_TLS DOCKER_TLS_VERIFY DOCKER_CERT_PATH
export DOCKER_HOST=unix:///var/run/docker.sock
profile="$(realpath devtools/docker29-release-profile.json)"
image=$(python3 -c 'import json;print(json.load(open("devtools/docker29-release-profile.json"))["image"])')
[[ $image == docker.io/library/docker@sha256:64d6ee47ea821c986467199baa162f5ac8cde3f57b719f18e23f3ed7a7444131 ]]
tools=$(mktemp -d "$RUNNER_TEMP/factlens-docker29.XXXXXXXX")
cid=''
cleanup() { if [[ $cid =~ ^[0-9a-f]{64}$ ]]; then docker rm -v "$cid" >/dev/null; fi; }
trap cleanup EXIT
docker pull --platform linux/amd64 "$image"
cid=$(docker create --platform linux/amd64 --entrypoint /bin/true "$image")
[[ $cid =~ ^[0-9a-f]{64}$ ]]
for name in docker dockerd containerd containerd-shim-runc-v2 ctr runc docker-proxy docker-init; do
  docker cp "$cid:/usr/local/bin/$name" "$tools/$name"
  chmod 700 "$tools/$name"
done
python3 devtools/verify-pilot-docker29.py "$tools" "$profile" ci-release-measurement-only >/dev/null
printf 'tool-dir=%s\n' "$tools" >> "$GITHUB_OUTPUT"
