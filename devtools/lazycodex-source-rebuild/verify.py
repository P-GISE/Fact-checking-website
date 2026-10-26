"""Verify explicit local derivative provenance, complete package tree and actual bundle bytes."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = ROOT / '.devtools/lazycodex-security-build'
PROOF = 'PGISE-SECURITY-OVERLAY.json'
sys.path.insert(0, str(ROOT))
from scripts.security.cache_io import CacheBoundaryError, checked_path


def sha(path: Path) -> str:
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def tree_digest(root: Path) -> str:
    rows = []
    if root.is_symlink() or root.is_junction():
        raise ValueError('installed_package_link')
    for directory, folders, files in os.walk(root, followlinks=False):
        current = Path(directory)
        for name in folders:
            if (current / name).is_symlink() or (current / name).is_junction():
                raise ValueError('installed_directory_link')
        for name in files:
            path = current / name
            relative = path.relative_to(root).as_posix()
            if relative == PROOF:
                continue
            if path.is_symlink():
                raise ValueError('installed_file_link')
            rows.append((relative, sha(path), stat.S_IMODE(path.stat().st_mode)))
    return hashlib.sha256(json.dumps(sorted(rows), separators=(',', ':')).encode()).hexdigest()


def marker(text: str) -> tuple[str, str]:
    lines = text.replace('\r\n', '\n').split('\n')
    if len(lines) < 3 or lines[0] != '#!/usr/bin/env node':
        raise ValueError('bundle_header')
    header = re.fullmatch(r'// omo-codex-install:([a-f0-9]{64}):([a-f0-9]{64})', lines[1])
    if not header or hashlib.sha256('\n'.join(lines[2:]).encode()).hexdigest() != header[2]:
        raise ValueError('bundle_body_digest')
    return header[1], header[2]


def check_artifact() -> tuple[dict, dict, Path]:
    checked_path(ROOT, BASE / 'artifact', directory=True)
    for directory in (ROOT / '.devtools', BASE, BASE / 'artifact'):
        if directory.is_symlink() or directory.is_junction():
            raise ValueError('artifact_directory_link')
    plan = json.loads((HERE / 'plan.json').read_text(encoding='utf-8'))
    if plan['bundle_relative'] != 'packages/omo-codex/scripts/install-dist/install-local.mjs':
        raise ValueError('bundle_path')
    recipe, lock = sha(HERE / 'rebuild.py'), sha(HERE / 'build-deps/package-lock.json')
    receipt_path = BASE / 'artifact' / ('receipt-' + recipe[:16] + '-' + lock[:16] + '.json')
    if receipt_path.is_symlink() or receipt_path.parent.is_symlink() or receipt_path.parent.is_junction():
        raise ValueError('artifact_receipt_link')
    receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
    expected_helpers = {name: sha(ROOT / name) for name in (
        'scripts/security/cache_io.py', 'devtools/lazycodex-source-rebuild/source_inputs.py',
        'devtools/lazycodex-source-rebuild/signed_inputs.py')}
    if receipt.get('io_helpers_sha256') != expected_helpers:
        raise ValueError('artifact_io_helpers_identity')
    for field, expected in {
        'recipe_sha256': recipe, 'lock_sha256': lock, 'plan_sha256': sha(HERE / 'plan.json'),
        'smoke_sha256': sha(HERE / 'smoke.mjs'), 'platform': sys.platform,
        'source_commit': plan['source_commit'], 'source_sha256': plan['source_sha256'],
        'source_license_sha256': plan['official_license_sha256'], 'source_code_unchanged': True,
    }.items():
        if receipt.get(field) != expected:
            raise ValueError('artifact_input_identity')
    bundle = BASE / 'artifact/install-local.mjs'
    checked_path(BASE, bundle)
    if bundle.is_symlink() or sha(bundle) != receipt['bundle_sha256']:
        raise ValueError('artifact_bundle_digest')
    if marker(bundle.read_text(encoding='utf-8')) != (receipt['source_marker'], receipt['body_digest']):
        raise ValueError('artifact_official_marker')
    smoke = receipt['smoke']
    expected_smoke = {'status': 'pass', 'cli_version': True, 'cli_help': True, 'synthetic_update_dry_run': True,
                      'home_files_written': 0, 'project_files_written': 0, 'network_api_attempts': 0, 'child_spawn_attempts': 0,
                      'bundled_array_issues_before': 1001, 'bundled_array_issues_after': 1,
                      'original_bundle_sha256': plan['original_npm_bundle_sha256'], 'tested_bundle_sha256': receipt['bundle_sha256']}
    if smoke != expected_smoke or sha(BASE / 'artifact/UPSTREAM-LICENSE.md') != plan['official_license_sha256']:
        raise ValueError('artifact_smoke_or_license')
    return plan, receipt, receipt_path


def check_installed() -> None:
    plan, receipt, receipt_path = check_artifact()
    check_installed_payload(plan, receipt, receipt_path)


def check_installed_payload(plan: dict, receipt: dict, receipt_path: Path) -> None:
    package = checked_path(ROOT, ROOT / 'devtools/node/node_modules/lazycodex-ai', directory=True)
    for directory in (package.parent, package):
        if directory.is_symlink() or directory.is_junction():
            raise ValueError('installed_directory_link')
    runtime = subprocess.run(['node', '--version'], capture_output=True, timeout=10, check=True).stdout.decode().strip()
    if not re.fullmatch(r'v24\.(?:2[0-9]|[3-9][0-9])\.\d+', runtime):
        raise ValueError('unsupported_node_runtime')
    proof = json.loads((package / PROOF).read_text(encoding='utf-8'))
    if proof['receipt_sha256'] != sha(receipt_path) or proof['derivative'] != plan['derivative']:
        raise ValueError('installed_receipt')
    metadata = json.loads((package / 'package.json').read_text(encoding='utf-8'))
    if metadata['name'] != 'lazycodex-ai' or metadata['version'] != plan['upstream_version']:
        raise ValueError('installed_version')
    lock = json.loads((ROOT / 'devtools/node/package-lock.json').read_text(encoding='utf-8'))
    if proof['upstream_npm_integrity'] != lock['packages']['node_modules/lazycodex-ai']['integrity']:
        raise ValueError('installed_upstream_identity')
    if (sha(package / plan['bundle_relative']) != receipt['bundle_sha256']
            or sha(package / plan['wrapper_relative']) != plan['wrapper_sha256']
            or tree_digest(package) != proof['installed_tree_sha256']):
        raise ValueError('installed_tree_digest')


if __name__ == '__main__':
    try:
        check_installed()
    except (ValueError, KeyError, OSError, CacheBoundaryError):
        print('lazycodex_security_overlay status=refused', file=sys.stderr)
        raise SystemExit(1) from None
    print('lazycodex_security_overlay status=verified derivative=pgise.security1-zod4.6.6', file=sys.stderr)
