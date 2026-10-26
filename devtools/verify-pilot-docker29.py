#!/usr/bin/env python3
"""Verify immutable public tools in a private CI directory without executing them."""
import hashlib
import json
from pathlib import Path
import re
import sys


def verify(directory,profile):
    if (profile.get('kind')!='ci-pilot-only' or profile.get('version')!='29.1.3'
            or profile.get('platform')!='linux/amd64' or profile.get('memory_max_bytes')!=768*1024**2):
        raise ValueError('Invalid pilot runtime profile')
    required={'docker','dockerd','containerd','containerd-shim-runc-v2','ctr','runc','docker-proxy','docker-init'}
    hashes=profile.get('binary_sha256',{})
    if set(hashes)!=required or directory.is_symlink() or not directory.is_dir():
        raise ValueError('Private verified tool directory required')
    if {path.name for path in directory.iterdir()}!=required:
        raise ValueError('Unexpected private runtime tool')
    for name,expected in hashes.items():
        path=directory/name
        if not re.fullmatch('[0-9a-f]{64}',expected) or path.is_symlink() or not path.is_file():
            raise ValueError('Invalid runtime tool metadata')
        hasher=hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda:stream.read(1024**2),b''):hasher.update(block)
        if hasher.hexdigest()!=expected:raise ValueError('Private runtime tool digest mismatch')


if __name__=='__main__':
    try:verify(Path(sys.argv[1]),json.loads(Path(sys.argv[2]).read_text()))
    except (OSError,ValueError,KeyError,TypeError):
        raise SystemExit('Private Docker29 pilot tools rejected')
