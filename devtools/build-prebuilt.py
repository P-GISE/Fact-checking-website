#!/usr/bin/env python3
"""Build one bounded local bundle. Publication is a separate, disabled-by-default CI step."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from prebuilt_gate import validate_archive, GateError


def command(*args):
    return subprocess.check_output(args,text=True).strip()


def main():
    os.umask(0o077)
    sha=os.environ['GITHUB_SHA'];run=int(os.environ['GITHUB_RUN_ID']);attempt=int(os.environ['GITHUB_RUN_ATTEMPT'])
    if not re.fullmatch('[0-9a-f]{40}',sha) or command('git','rev-parse','HEAD')!=sha:
        raise GateError('Source checkout mismatch')
    policy=json.loads(Path('devtools/import-resource-policy.json').read_text())
    if policy.get('status')!='approved-measurement-envelope':raise GateError('Reviewed measured import envelope required before building/publishing')
    for field in ('max_import_peak_bytes','reserve_bytes'):
        if type(policy.get(field)) is not int or policy[field]<=0:raise GateError('Invalid reviewed measurement envelope')
    if not re.fullmatch(r'https://github\.com/P-GISE/Fact-checking-website/actions/runs/[0-9]+',policy.get('baseline_run_url','')):
        raise GateError('Actual baseline measurement evidence required')
    if os.environ.get('ARTIFACT_STORAGE_APPROVED')!='true':raise GateError('Artifact storage budget unapproved')
    output=Path(os.environ['RUNNER_TEMP'])/'factlens-release';output.mkdir(mode=0o700,exist_ok=False)
    ids={};tags=[]
    for component in ('api','web','worker'):
        tag=f'factlens-{component}:{sha}';tags.append(tag)
        args=['docker','build','--file',f'docker/{component}.Dockerfile','--tag',tag,
              '--label',f'org.opencontainers.image.revision={sha}',
              '--build-arg',f'FACTLENS_SOURCE_REVISION={sha}',
              '--secret','id=proxy_ca,src=/etc/ssl/certs/ca-certificates.crt']
        if component=='web':args+=['--build-arg','NGINX_CONFIG=nginx.production.conf']
        subprocess.run(args+['.'],check=True)
        ids[component]=command('docker','image','inspect','--format','{{.Id}}',tag)
    archive=output/'images.tar.gz'
    with archive.open('wb') as stream:
        save=subprocess.Popen(['docker','save',*tags],stdout=subprocess.PIPE)
        gzip=subprocess.run(['gzip','-n','-6'],stdin=save.stdout,stdout=stream)
        save.stdout.close()
        if save.wait()!=0 or gzip.returncode:raise GateError('Image archive failed')
    if archive.stat().st_size>450*1024**2:raise GateError('Combined image artifact exceeds reviewed size envelope')
    expanded=validate_archive(archive,sha,ids,8*1024**3)
    with archive.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
    measurement=json.loads(command('bash','devtools/measure-prebuilt-import.sh',str(archive),digest,sha))
    if (measurement.get('status')!='measurement-requires-review' or measurement.get('oom_events')!=0
            or measurement.get('image_archive_sha256')!=digest
            or not 0<measurement.get('peak_total_bytes',0)<=policy['max_import_peak_bytes']):
        raise GateError('Current exact-bundle import exceeds reviewed measured envelope')
    # Source-reviewed envelope authorizes the formula, while every build gets actual exact-bundle evidence.
    measured={**measurement,'status':'measured','reserve_bytes':policy['reserve_bytes']}
    manifest={'schema':1,'sha':sha,'run_id':run,'run_attempt':attempt,'archive_sha256':digest,
              'image_ids':ids,'expanded_limit_bytes':expanded,'platform':'linux/amd64','import_policy':measured}
    (output/'manifest.json').write_text(json.dumps(manifest,sort_keys=True)+'\n')
    (output/'checksums.sha256').write_text(digest+'  images.tar.gz\n')


if __name__=='__main__':
    try:main()
    except (GateError,KeyError,ValueError,OSError,subprocess.SubprocessError):
        raise SystemExit('Prebuilt bundle preparation rejected; no publication or deployment performed')
