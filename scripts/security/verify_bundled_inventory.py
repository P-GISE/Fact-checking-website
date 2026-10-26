"""Verify the SBOM snapshot against the actual published installer bundle."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys


def verify(root: Path) -> None:
    document = json.loads((root / 'devtools/node/lazycodex-bundle.cdx.json').read_text(encoding='utf-8'))
    properties = {item['name']: item['value'] for item in document['metadata']['properties']}
    relative = properties['verified_bundle_relative_path']
    if relative != 'packages/omo-codex/scripts/install-dist/install-local.mjs':
        raise ValueError('bundle_path')
    package = root / 'devtools/node/node_modules/lazycodex-ai'
    if json.loads((package / 'package.json').read_text(encoding='utf-8'))['version'] != document['metadata']['component']['version']:
        raise ValueError('bundle_package_version')
    content = (package / relative).read_bytes()
    if hashlib.sha256(content).hexdigest() != properties['verified_bundle_sha256']:
        raise ValueError('bundle_digest')
    actual = set()
    if (package / 'PGISE-SECURITY-OVERLAY.json').exists():
        verifier = root / 'devtools/lazycodex-source-rebuild/verify.py'
        subprocess.run([sys.executable, str(verifier)], check=True)
        names = set(re.findall(r'^// node_modules/((?:@[^/]+/)?[^/]+)', content.decode('utf-8'), re.MULTILINE))
        receipt_path = root / '.devtools/lazycodex-security-build/artifact'
        proof = json.loads((package / 'PGISE-SECURITY-OVERLAY.json').read_text(encoding='utf-8'))
        receipts = [path for path in receipt_path.glob('receipt-*.json') if hashlib.sha256(path.read_bytes()).hexdigest() == proof['receipt_sha256']]
        if len(receipts) != 1:
            raise ValueError('bundle_receipt_identity')
        components = json.loads(receipts[0].read_text(encoding='utf-8'))['components']
        if names != {item['name'] for item in components}:
            raise ValueError('bundle_components')
        actual = {(item['name'], item['version']) for item in components}
    else:
        for bundled in re.findall(r'node_modules/\.bun/([^/]+)', content.decode('utf-8')):
            name, version = bundled.rsplit('@', 1)
            actual.add((name.replace('+', '/'), version))
    expected = {(item['name'], item['version']) for item in document['components']}
    if not actual or actual != expected:
        raise ValueError('bundle_components')
    print('bundle_inventory status=verified components=' + str(len(actual)))


if __name__ == '__main__':
    verify(Path(__file__).resolve().parents[2])
