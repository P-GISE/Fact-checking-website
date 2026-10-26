#!/usr/bin/env python3
"""Separate import gate. Does not lower or call the server build memory guard."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
from prebuilt_gate import validate_resources, validate_archive, GateError


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--archive',type=Path,required=True)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--policy',type=Path,required=True)
    parser.add_argument('--sha',required=True)
    args=parser.parse_args()
    try:
        for path in (args.archive,args.manifest,args.policy):
            if not path.is_file() or path.is_symlink(): raise GateError('Regular input files required')
        if args.archive.stat().st_size > 450*1024**2 or any(
                path.stat().st_size>1024**2 for path in (args.manifest,args.policy)):
            raise GateError('Input size limit exceeded')
        root=Path.cwd()
        env=root/'.env.production'
        if (not env.is_file() or env.is_symlink() or stat.S_IMODE(env.stat().st_mode)!=0o600
                or env.stat().st_uid!=os.getuid()): raise GateError('Private environment owner/mode required')
        manifest=json.loads(args.manifest.read_text());policy=json.loads(args.policy.read_text())
        if manifest.get('sha')!=args.sha or manifest.get('schema')!=1:
            raise GateError('Manifest source/schema mismatch')
        with args.archive.open('rb') as stream: digest=hashlib.file_digest(stream,'sha256').hexdigest()
        if digest!=manifest['archive_sha256']: raise GateError('Archive checksum mismatch')
        expanded=validate_archive(args.archive,args.sha,manifest['image_ids'],manifest['expanded_limit_bytes'])
        memory={line.split(':')[0]:int(line.split()[1])*1024
                for line in Path('/proc/meminfo').read_text().splitlines()}['MemAvailable']
        # Use only local daemon. Never honor externally provided Docker context/endpoint.
        observed=subprocess.run(['docker','--host=unix:///var/run/docker.sock','info','--format','{{.DockerRootDir}}'],
                                check=True,capture_output=True,text=True).stdout.strip()
        docker_root=Path(observed)
        if not docker_root.is_absolute() or not docker_root.is_dir(): raise GateError('Invalid Docker root')
        validate_resources(policy,digest,memory,shutil.disk_usage(args.archive.parent).free,
                           shutil.disk_usage(docker_root).free,args.archive.stat().st_size,expanded)
        subprocess.run(['docker','--host=unix:///var/run/docker.sock','compose','--env-file','.env.production',
                        '-f','compose.production.yaml','config','--quiet'],check=True,capture_output=True)
    except (GateError,OSError,ValueError,TypeError,KeyError,subprocess.CalledProcessError):
        print('Prebuilt import preflight rejected; no image import or service mutation performed.',file=sys.stderr)
        return 1
    print('Measured prebuilt import resources and archive verified; no service mutation performed.')
    return 0


if __name__=='__main__':sys.exit(main())
