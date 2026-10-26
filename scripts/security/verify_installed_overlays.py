"""Fail closed before running repository-local tools with derived vendor wheels."""
from __future__ import annotations

import base64
import hashlib
from importlib.metadata import PackageNotFoundError, distribution, version
import json
from pathlib import Path
import sys


def verify(root: Path, tool: str) -> None:
    if tool not in ('headroom', 'strix'):
        raise ValueError('unknown_tool')
    manifest = json.loads((root / 'devtools/python-security-overlays.json').read_text(encoding='utf-8'))
    required = {'litellm': '1.106.4+pgise.security1'}
    if tool == 'strix':
        required['strix-agent'] = '1.7.0+pgise.security1'
    for name, expected in required.items():
        dist = distribution(name)
        if dist.version != expected:
            raise ValueError('installed_version')
        files = dist.files or []
        proofs = [item for item in files if item.name == 'PGISE-SECURITY-OVERLAY.json']
        if len(proofs) != 1:
            raise ValueError('installed_provenance')
        proof = json.loads(dist.locate_file(proofs[0]).read_text(encoding='utf-8'))
        entry = manifest['packages'][name]
        permitted = {(item['filename'], item['sha256']) for item in entry['artifacts']}
        if (proof['upstream_filename'], proof['upstream_sha256']) not in permitted or proof['local_version'] != expected or proof['name'] != name:
            raise ValueError('installed_source_identity')
        # RECORD hashes include original native payload, LICENSE, metadata and provenance.
        for item in files:
            if item.hash is None:
                if not (item.name == 'RECORD' or str(item).endswith('.pyc')):
                    raise ValueError('installed_unhashed_file')
                continue
            if item.hash.mode != 'sha256':
                raise ValueError('installed_hash_algorithm')
            actual = base64.urlsafe_b64encode(hashlib.sha256(dist.locate_file(item).read_bytes()).digest()).rstrip(b'=').decode('ascii')
            if actual != item.hash.value:
                raise ValueError('installed_record_digest')
    if not version('filelock').startswith('4.') or tuple(int(value) for value in version('filelock').split('.')[:3]) < (4, 2, 1):
        raise ValueError('installed_filelock')
    if tool == 'strix' and not version('cryptography').startswith('50.'):
        raise ValueError('installed_cryptography')


if __name__ == '__main__':
    try:
        verify(Path(__file__).resolve().parents[2], sys.argv[1])
    except (ValueError, KeyError, OSError, IndexError, PackageNotFoundError):
        print('python_security_overlay status=refused reinstall_with_setup=true')
        raise SystemExit(1) from None
    print('python_security_overlay status=verified')
