from pathlib import Path
import hashlib
import json

import pytest

from scripts.security.verify_bundled_inventory import verify


def inventory(root: Path) -> Path:
    folder = root / 'devtools/node'
    package = folder / 'node_modules/lazycodex-ai'
    package.mkdir(parents=True)
    (package / 'package.json').write_text('{"version":"5.1.33"}', encoding='utf-8')
    relative = 'packages/omo-codex/scripts/install-dist/install-local.mjs'
    bundle = package / relative
    bundle.parent.mkdir(parents=True)
    content = b'// node_modules/.bun/zod@4.6.5/node_modules/zod/index.js\n'
    bundle.write_bytes(content)
    document = {'metadata': {'component': {'version': '5.1.33'}, 'properties': [
        {'name': 'verified_bundle_relative_path', 'value': relative},
        {'name': 'verified_bundle_sha256', 'value': hashlib.sha256(content).hexdigest()}]},
        'components': [{'name': 'zod', 'version': '4.6.5'}]}
    (folder / 'lazycodex-bundle.cdx.json').write_text(json.dumps(document), encoding='utf-8')
    return bundle


def test_inventory_describes_actual_bundle_and_refuses_changed_content(tmp_path: Path) -> None:
    bundle = inventory(tmp_path)
    verify(tmp_path)
    bundle.write_bytes(b'changed bundle')
    with pytest.raises(ValueError, match='bundle_digest'):
        verify(tmp_path)


def test_inventory_refuses_missing_component_even_when_digest_matches(tmp_path: Path) -> None:
    inventory(tmp_path)
    target = tmp_path / 'devtools/node/lazycodex-bundle.cdx.json'
    document = json.loads(target.read_text(encoding='utf-8'))
    document['components'] = []
    target.write_text(json.dumps(document), encoding='utf-8')
    with pytest.raises(ValueError, match='bundle_components'):
        verify(tmp_path)
