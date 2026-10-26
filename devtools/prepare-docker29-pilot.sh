#!/usr/bin/env bash
# CI-only: copy verified public static binaries; do not install or start the image/container.
set -Eeuo pipefail
umask 077
[[ ${GITHUB_ACTIONS:-} == true && ${GITHUB_REPOSITORY:-} == P-GISE/Fact-checking-website ]]
[[ ${GITHUB_EVENT_NAME:-} == pull_request && -n ${RUNNER_TEMP:-} && -n ${GITHUB_OUTPUT:-} ]]
unset DOCKER_CONTEXT DOCKER_TLS DOCKER_TLS_VERIFY DOCKER_CERT_PATH
export DOCKER_HOST=unix:///var/run/docker.sock
profile="$(realpath devtools/docker29-pilot-profile.json)"
image=$(python3 -c 'import json;print(json.load(open("devtools/docker29-pilot-profile.json"))["image"])')
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
python3 devtools/verify-pilot-docker29.py "$tools" "$profile"
printf 'tool-dir=%s\n' "$tools" >> "$GITHUB_OUTPUT"
printf '%s\n' 'Private Docker29 pilot binaries copied and SHA-verified; image/container not started; global PATH unchanged.'
