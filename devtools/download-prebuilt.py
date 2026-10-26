#!/usr/bin/env python3
"""Read authenticated Actions artifacts, validate identity and both digests before extraction."""
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile
from prebuilt_gate import validate_artifact,validate_artifact_zip,validate_archive,normalize_action_digest,GateError


def api(path):
    return json.loads(subprocess.check_output(['gh','api',path],stderr=subprocess.DEVNULL,text=True))


def main():
    os.umask(0o077)
    sha=os.environ['GITHUB_SHA'];run=int(os.environ['GITHUB_RUN_ID']);attempt=int(os.environ['GITHUB_RUN_ATTEMPT'])
    artifact_id=int(os.environ['ARTIFACT_ID']);digest=normalize_action_digest(os.environ['ARTIFACT_DIGEST'])
    prefix='repos/P-GISE/Fact-checking-website/'
    meta=api(prefix+f'actions/artifacts/{artifact_id}')
    validate_artifact(meta,artifact_id,run,sha,attempt,digest)
    pages=json.loads(subprocess.check_output(['gh','api','--paginate','--slurp',
        prefix+f'actions/runs/{run}/artifacts?per_page=100'],stderr=subprocess.DEVNULL,text=True))
    matches=[row for page in pages for row in page['artifacts'] if row.get('name')==meta['name']]
    if len(matches)!=1 or matches[0].get('id')!=artifact_id:raise GateError('Artifact name/ID not unique')
    folder=Path(os.environ['RUNNER_TEMP'])/'factlens-download';folder.mkdir(mode=0o700)
    archive=folder/'artifact.zip'
    with archive.open('xb') as output:
        subprocess.run(['gh','api',prefix+f'actions/artifacts/{artifact_id}/zip'],stdout=output,
                       stderr=subprocess.DEVNULL,check=True)
    manifest=validate_artifact_zip(archive,digest,sha,run,attempt)
    # Write only the already verified exact names into a fresh, private directory.
    with zipfile.ZipFile(archive) as bundle:
        for name in ('images.tar.gz','manifest.json'):
            with bundle.open(name) as source,(folder/name).open('xb') as target:
                while block:=source.read(1024**2):target.write(block)
    validate_archive(folder/'images.tar.gz',sha,manifest['image_ids'],manifest['expanded_limit_bytes'])


if __name__=='__main__':
    try:main()
    except Exception:
        raise SystemExit('Prebuilt artifact provenance/integrity rejected; no remote transfer performed')
