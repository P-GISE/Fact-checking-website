#!/usr/bin/env bash
set -euo pipefail
umask 077
[[ "$GITHUB_SHA" =~ ^[0-9a-f]{40}$ ]]
[[ "$PILOT_HEAD_SHA" =~ ^[0-9a-f]{40}$ ]]
[[ "$PILOT_BASE_SHA" =~ ^[0-9a-f]{40}$ ]]
[[ "$(git rev-parse HEAD)" == "$GITHUB_SHA" ]]
[[ -s /etc/ssl/certs/ca-certificates.crt ]]
pilot_temp=$(mktemp -d "${RUNNER_TEMP:?}/factlens-image-size.XXXXXX")
trap 'rm -rf -- "$pilot_temp"' EXIT
images=()
for component in api web worker; do
  tag="factlens-${component}-ci-pilot:${GITHUB_SHA}"
  args=(--progress=plain --file "docker/${component}.Dockerfile" --tag "$tag"
        --label "org.opencontainers.image.revision=$GITHUB_SHA"
        --build-arg "FACTLENS_SOURCE_REVISION=$GITHUB_SHA"
        # Existing Dockerfiles require proxy_ca. This is the runner's PUBLIC CA trust bundle, not a credential.
        --secret id=proxy_ca,src=/etc/ssl/certs/ca-certificates.crt)
  if [[ "$component" == web ]]; then
    args+=(--build-arg NGINX_CONFIG=nginx.production.conf)
  fi
  docker build "${args[@]}" .
  images+=("$tag")
  metadata=$(docker image inspect --format '{{.Id}}|{{.Size}}|{{.Architecture}}|{{.Os}}' "$tag")
  printf '%s|%s\n' "$component" "$metadata" >> "$pilot_temp/images.txt"
done
# Local runner temporary file only: no upload-artifact, docker push, GHCR, SSH, app start, or deployment.
docker save "${images[@]}" | gzip -n -6 > "$pilot_temp/images.tar.gz"
gzip -t "$pilot_temp/images.tar.gz"
python3 - "$pilot_temp" "$GITHUB_SHA" "$PILOT_HEAD_SHA" "$PILOT_BASE_SHA" <<'PY'
from pathlib import Path
import hashlib
import json
import sys
import tarfile

folder = Path(sys.argv[1])
archive = folder / 'images.tar.gz'
images = []
for line in (folder / 'images.txt').read_text().splitlines():
    component, digest, size, architecture, operating_system = line.split('|')
    images.append({'component': component, 'image_id': digest, 'uncompressed_bytes': int(size),
                   'architecture': architecture, 'os': operating_system})
with tarfile.open(archive, 'r:gz') as bundle:
    manifest = json.load(bundle.extractfile('manifest.json'))
    tags = [tag for row in manifest for tag in row.get('RepoTags', [])]
expected = sorted(f"factlens-{row['component']}-ci-pilot:{sys.argv[2]}" for row in images)
if sorted(tags) != expected or len(images) != 3:
    raise SystemExit('Combined Docker archive does not contain exactly the three expected images')
with archive.open('rb') as stream:
    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
size = archive.stat().st_size
print('FACTLENS_IMAGE_PILOT_RESULT=' + json.dumps({
    'checkout_sha': sys.argv[2], 'head_sha': sys.argv[3], 'base_sha': sys.argv[4],
    'images': images, 'combined_gzip_bytes': size, 'combined_gzip_mib': round(size / 1024**2, 2),
    'sha256': digest, 'less_than_450_mib': size < 450 * 1024**2,
    'uploaded_artifacts': 0, 'published_packages': 0, 'deployment_performed': False,
    'production_credentials_used': False, 'temporary_bundle_cleanup': 'on-exit trap',
}, sort_keys=True))
PY
