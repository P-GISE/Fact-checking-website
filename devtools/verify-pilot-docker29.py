#!/usr/bin/env python3
"""Verify immutable public tools in a private CI directory without executing them."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys


def verify(directory,profile,expected_kind='ci-pilot-only',expected_identity=None):
    if (expected_kind not in ('ci-pilot-only','ci-release-measurement-only')
            or profile.get('kind')!=expected_kind or profile.get('version')!='29.1.3'
            or profile.get('platform')!='linux/amd64' or profile.get('memory_max_bytes')!=3*1024**3):
        raise ValueError('Invalid pilot runtime profile')
    required={'docker','dockerd','containerd','containerd-shim-runc-v2','ctr','runc','docker-proxy','docker-init'}
    hashes=profile.get('binary_sha256',{})
    if set(hashes)!=required or directory.is_symlink() or not directory.is_dir():
        raise ValueError('Private verified tool directory required')
    if {path.name for path in directory.iterdir()}!=required:
        raise ValueError('Unexpected private runtime tool')
    identities={}
    def identity(value):return (value.st_dev,value.st_ino,stat.S_IMODE(value.st_mode))
    for name,expected in hashes.items():
        path=directory/name
        metadata=path.lstat()
        if (not re.fullmatch('[0-9a-f]{64}',expected) or not stat.S_ISREG(metadata.st_mode)
                or stat.S_IMODE(metadata.st_mode)!=0o700 or not os.access(path,os.X_OK)):
            raise ValueError('Invalid runtime tool metadata')
        hasher=hashlib.sha256()
        with path.open('rb') as stream:
            if identity(os.fstat(stream.fileno()))!=identity(metadata):
                raise ValueError('Private runtime tool inode changed before verification')
            for block in iter(lambda:stream.read(1024**2),b''):hasher.update(block)
        if hasher.hexdigest()!=expected or identity(path.lstat())!=identity(metadata):
            raise ValueError('Private runtime tool digest/inode mismatch')
        identities[name]={'device':metadata.st_dev,'inode':metadata.st_ino,
                          'mode':stat.S_IMODE(metadata.st_mode),'binary_sha256':hasher.hexdigest(),
                          'executable':True}
    if expected_identity is not None and identities!=expected_identity:
        raise ValueError('Private runtime tool identity changed')
    return identities


if __name__=='__main__':
    try:
        if len(sys.argv) not in (3,4,5):raise ValueError('Invalid verifier arguments')
        result=verify(Path(sys.argv[1]),json.loads(Path(sys.argv[2]).read_text()),
                      sys.argv[3] if len(sys.argv)>=4 else 'ci-pilot-only',
                      json.loads(Path(sys.argv[4]).read_text()) if len(sys.argv)==5 else None)
        print(json.dumps(result,sort_keys=True))
    except (OSError,ValueError,KeyError,TypeError):
        raise SystemExit('Private Docker29 pilot tools rejected')
