"""Install exactly one reviewed rebuilt bundle, preserving upstream package and license identity."""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tarfile
import sys
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit
from urllib.request import urlopen

from verify import BASE, PROOF, ROOT, check_artifact, check_installed, check_installed_payload, sha, tree_digest

sys.path.insert(0, str(ROOT))
from scripts.security.cache_io import CacheBoundaryError, atomic_bytes, atomic_copy, checked_path, ensure_directory, new_file


def official_package(package: Path, lock_entry: dict) -> None:
    if lock_entry['version'] != '5.1.33' or not lock_entry['integrity'].startswith('sha512-'):
        raise ValueError('npm_source_identity')
    url = lock_entry['resolved']
    if url != 'https://registry.npmjs.org/lazycodex-ai/-/lazycodex-ai-5.1.33.tgz':
        raise ValueError('npm_source_origin')
    archive = checked_path(BASE, BASE / 'verified-original-npm.tgz')
    if not archive.exists():
        with TemporaryDirectory(prefix='npm-origin-', dir=BASE) as folder:
            part = Path(folder) / 'package.tgz'
            size = 0
            with urlopen(url, timeout=60) as response, new_file(BASE, part) as output:
                if urlsplit(response.url).hostname != 'registry.npmjs.org':
                    raise ValueError('npm_source_redirect')
                while chunk := response.read(1024 * 1024):
                    size += len(chunk)
                    if size > 64 * 1024 * 1024:
                        raise ValueError('npm_source_size')
                    output.write(chunk)
            with part.open('rb') as content:
                actual = 'sha512-' + base64.b64encode(hashlib.file_digest(content, 'sha512').digest()).decode()
            if actual != lock_entry['integrity']:
                raise ValueError('npm_source_integrity')
            checked_path(BASE, archive)
            os.link(part, archive)
    with archive.open('rb') as content:
        actual = 'sha512-' + base64.b64encode(hashlib.file_digest(content, 'sha512').digest()).decode()
    if actual != lock_entry['integrity']:
        raise ValueError('cached_npm_source_integrity')
    expected = set()
    with tarfile.open(archive) as original:
        for entry in original.getmembers():
            path = PurePosixPath(entry.name)
            if (path.is_absolute() or '..' in path.parts or '\\' in entry.name or ':' in entry.name
                    or not path.parts or path.parts[0] != 'package' or not (entry.isfile() or entry.isdir())):
                raise ValueError('npm_archive_path')
            if entry.isdir():
                continue
            relative = PurePosixPath(*path.parts[1:]).as_posix()
            if relative in expected:
                raise ValueError('npm_archive_duplicate')
            expected.add(relative)
            content = original.extractfile(entry)
            target = package / Path(relative)
            if content is None or target.is_symlink() or sha(target) != hashlib.file_digest(content, 'sha256').hexdigest():
                raise ValueError('changed_original_package')
    actual_files = {path.relative_to(package).as_posix() for path in package.rglob('*') if path.is_file()}
    if actual_files != expected:
        raise ValueError('unexpected_original_package_file')


def install(previous_receipt: Path | None = None) -> None:
    plan, receipt, receipt_path = check_artifact()
    package = checked_path(ROOT, ROOT / 'devtools/node/node_modules/lazycodex-ai', directory=True)
    if package.is_symlink() or package.is_junction():
        raise ValueError('installed_package_link')
    if (package / PROOF).exists():
        if previous_receipt is not None:
            checked_path(BASE, previous_receipt)
            if previous_receipt.resolve().parent != receipt_path.resolve().parent:
                raise ValueError('previous_receipt_scope')
            previous = json.loads(previous_receipt.read_text(encoding='utf-8'))
            if (previous['bundle_sha256'] != receipt['bundle_sha256']
                    or previous['source_sha256'] != receipt['source_sha256']
                    or previous['body_digest'] != receipt['body_digest']):
                raise ValueError('refresh_changed_compiled_payload')
            check_installed_payload(plan, previous, previous_receipt)
            proof_path = package / PROOF
            old_bytes = proof_path.read_bytes()
            proof = json.loads(old_bytes)
            proof['previous_receipt_sha256'] = sha(previous_receipt)
            proof['refreshed_from_proof_sha256'] = hashlib.sha256(old_bytes).hexdigest()
            proof['receipt_sha256'] = sha(receipt_path)
            atomic_bytes(ROOT, proof_path, (json.dumps(proof, indent=2, sort_keys=True) + '\n').encode('utf-8'))
        check_installed()
        print('lazycodex_overlay_install status=already_verified')
        return
    lock = json.loads((ROOT / 'devtools/node/package-lock.json').read_text(encoding='utf-8'))
    entry = lock['packages']['node_modules/lazycodex-ai']
    tree_digest(package)  # Reject internal links before any installed-package mutation.
    official_package(package, entry)
    if sha(package / plan['bundle_relative']) != plan['original_npm_bundle_sha256']:
        raise ValueError('original_bundle_identity')
    license_folder = package / 'PGISE-SECURITY-LICENSES'
    ensure_directory(ROOT, license_folder)
    atomic_copy(ROOT, BASE / 'artifact/UPSTREAM-LICENSE.md', license_folder / 'UPSTREAM-LICENSE.md')
    for component in receipt['components']:
        name = component['name']
        original = BASE / 'dependencies/node_modules' / name
        # Bind attribution to the exact dependency payload used for the real build.
        from rebuild import tree_digest as dependency_digest
        if dependency_digest(original) != receipt['dependency_payload_sha256'][name]:
            raise ValueError('license_dependency_payload')
        licenses = sorted({*original.glob('LICENSE*'), *original.glob('LICENCE*')})
        if not licenses:
            raise ValueError('missing_dependency_license')
        for source in licenses:
            if source.is_file():
                atomic_copy(ROOT, source, license_folder / (name.replace('@', '').replace('/', '-') + '-' + source.name))
    target = checked_path(ROOT, package / plan['bundle_relative'])
    with TemporaryDirectory(prefix='overlay-', dir=target.parent) as folder:
        staged = Path(folder) / 'install-local.mjs'
        atomic_copy(ROOT, BASE / 'artifact/install-local.mjs', staged)
        checked_path(ROOT, staged)
        staged.chmod(target.stat().st_mode)
        checked_path(ROOT, target)
        os.replace(staged, target)
    proof = {'schema': 1, 'derivative': plan['derivative'], 'upstream_npm_version': plan['upstream_version'],
             'upstream_npm_integrity': entry['integrity'], 'receipt_sha256': sha(receipt_path),
             'installed_tree_sha256': tree_digest(package), 'bundle_sha256': receipt['bundle_sha256'],
             'original_bundle_quarantined_sha256': plan['original_npm_bundle_sha256']}
    atomic_bytes(ROOT, package / PROOF, (json.dumps(proof, indent=2, sort_keys=True) + '\n').encode('utf-8'))
    check_installed()
    print('lazycodex_overlay_install status=verified')


if __name__ == '__main__':
    try:
        if len(sys.argv) == 3 and sys.argv[1] == '--refresh-receipt':
            install(Path(sys.argv[2]))
        elif len(sys.argv) == 1:
            install()
        else:
            raise ValueError('arguments')
    except (ValueError, KeyError, OSError, CacheBoundaryError):
        print('lazycodex_overlay_install status=refused')
        raise SystemExit(1) from None
