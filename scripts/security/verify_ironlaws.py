"""Verify the explicitly identified, source-pinned Iron Laws packaging overlay."""
from __future__ import annotations

import base64
import hashlib
from importlib.metadata import PackageNotFoundError, distribution
import json
from pathlib import Path


def verify(root: Path) -> None:
    manifest = json.loads((root / 'devtools/ironlaws-source.json').read_text(encoding='utf-8'))
    dist = distribution('iron-laws')
    if dist.version != '1.7.0+pgise.security1':
        raise ValueError('installed_version')
    files = dist.files or []
    receipts = [item for item in files if item.name == 'PGISE-SECURITY-OVERLAY.json']
    licenses = [item for item in files if str(item).endswith('.dist-info/licenses/LICENSE')]
    if len(receipts) != 1 or len(licenses) != 1:
        raise ValueError('installed_provenance')
    proof = json.loads(dist.locate_file(receipts[0]).read_text(encoding='utf-8'))
    if (proof['name'] != 'iron-laws' or proof['upstream_version'] != '1.7.0'
            or proof['source_commit'] != manifest['commit'] or proof['source_sha256'] != manifest['sha256']
            or proof['source_unchanged'] is not True or proof['local_version'] != dist.version
            or hashlib.sha256(dist.locate_file(licenses[0]).read_bytes()).hexdigest() != proof['license_sha256']):
        raise ValueError('installed_source_identity')
    for item in files:
        if item.hash is None:
            if not (item.name == 'RECORD' or str(item).endswith('.pyc')):
                raise ValueError('installed_unhashed_file')
            continue
        if item.hash.mode != 'sha256':
            raise ValueError('installed_hash_algorithm')
        digest = base64.urlsafe_b64encode(hashlib.sha256(dist.locate_file(item).read_bytes()).digest()).rstrip(b'=').decode('ascii')
        if digest != item.hash.value:
            raise ValueError('installed_record_digest')


if __name__ == '__main__':
    try:
        verify(Path(__file__).resolve().parents[2])
    except (ValueError, KeyError, OSError, PackageNotFoundError):
        print('ironlaws_security_overlay status=refused reinstall_with_setup=true')
        raise SystemExit(1) from None
    print('ironlaws_security_overlay status=verified')
