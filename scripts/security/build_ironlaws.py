"""Build unchanged pinned Iron Laws source using a separately hash-locked backend."""
from __future__ import annotations

import hashlib
from email import policy
from email.parser import BytesParser
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile
from tempfile import TemporaryDirectory
from urllib.request import Request, build_opener

from wheel.wheelfile import WheelFile

from scripts.security.cache_io import CacheBoundaryError, atomic_bytes, checked_path, ensure_directory, new_file
from scripts.security.python_overlays import NoRedirect, OverlayError, OverlaySpec, digest_file, fixed_zip_time, repack_wheel


def package_license(original: Path, folder: Path, license_bytes: bytes, source_sha256: str, commit: str) -> Path:
    spec = OverlaySpec('iron-laws', '1.7.0', '1.7.0+pgise.security1', ())
    staged = repack_wheel(original, folder / 'identified', spec, digest_file(original))
    destination = folder / 'licensed' / staged.path.name
    ensure_directory(folder, destination.parent)
    checked_path(folder, destination)
    with WheelFile(staged.path) as incoming, fixed_zip_time(), WheelFile(destination, 'w') as output:
        for entry in incoming.infolist():
            if entry.filename == incoming.record_path:
                continue
            data = incoming.read(entry.filename)
            if entry.filename.endswith('.dist-info/METADATA'):
                metadata = BytesParser(policy=policy.default).parsebytes(data)
                metadata['License-File'] = 'licenses/LICENSE'
                data = metadata.as_bytes(policy=policy.default.clone(utf8=True, max_line_length=0, linesep='\n'))
            if entry.filename.endswith('/PGISE-SECURITY-OVERLAY.json'):
                proof = json.loads(data)
                proof.update({'source_sha256': source_sha256, 'source_commit': commit,
                              'license_sha256': hashlib.sha256(license_bytes).hexdigest(), 'source_unchanged': True})
                data = (json.dumps(proof, indent=2, sort_keys=True) + '\n').encode()
            output.writestr(entry, data)
        output.writestr(incoming.dist_info_path + '/licenses/LICENSE', license_bytes)
    return destination


def safe_members(archive: tarfile.TarFile, expected_root: str) -> list[tarfile.TarInfo]:
    members = archive.getmembers()
    if sum(member.size for member in members) > 64 * 1024 * 1024:
        raise OverlayError('iron_archive_size')
    names: set[str] = set()
    for member in members:
        path = PurePosixPath(member.name)
        if (path.is_absolute() or str(path) != member.name.rstrip('/') or not path.parts or path.parts[0] != expected_root or '..' in path.parts
                or '\\' in member.name or ':' in member.name or not (member.isfile() or member.isdir())
                or member.name.casefold() in names):
            raise OverlayError('iron_archive_path')
        names.add(member.name.casefold())
    return members


def build(root: Path) -> Path:
    manifest_path = root / 'devtools/ironlaws-source.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    commit = manifest['commit']
    expected_url = 'https://codeload.github.com/JinHo-von-Choi/iron-laws/tar.gz/' + commit
    if (manifest['url'] != expected_url or len(commit) != 40 or any(value not in '0123456789abcdef' for value in commit)
            or type(manifest['schema']) is not int or manifest['schema'] != 1 or manifest['version'] != '1.7.0'
            or len(manifest['sha256']) != 64 or any(value not in '0123456789abcdef' for value in manifest['sha256'])):
        raise OverlayError('iron_manifest')
    directory = root / '.devtools'
    ensure_directory(root, directory)
    destination = directory / 'patched-wheels'
    ensure_directory(directory, destination)
    with TemporaryDirectory(prefix='iron-source-', dir=directory) as temporary:
        folder = Path(temporary)
        source_tar = folder / 'source.tar.gz'
        size = 0
        with build_opener(NoRedirect).open(Request(expected_url), timeout=60) as response, new_file(directory, source_tar) as output:
            while chunk := response.read(1024 * 1024):
                size += len(chunk)
                if size > 8 * 1024 * 1024:
                    raise OverlayError('iron_download_size')
                output.write(chunk)
        if digest_file(source_tar) != manifest['sha256']:
            raise OverlayError('iron_source_digest')
        expected_root = 'iron-laws-' + commit
        with tarfile.open(source_tar, 'r:gz') as archive:
            archive.extractall(folder / 'source', members=safe_members(archive, expected_root), filter='data')
        source = folder / 'source' / expected_root
        license_digest = digest_file(source / 'LICENSE')
        environment = {key: value for key, value in os.environ.items()
                       if key.upper() in ('PATH', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP')}
        environment['SOURCE_DATE_EPOCH'] = '1700000000'
        ensure_directory(directory, folder / 'wheels')
        result = subprocess.run(['uv', 'build', '--wheel', '--no-build-isolation', '--python', sys.executable,
                                 '--out-dir', str(folder / 'wheels'), str(source)], env=environment,
                                capture_output=True, timeout=180)
        if result.returncode:
            raise OverlayError('iron_build')
        outputs = list((folder / 'wheels').glob('iron_laws-1.7.0-py3-none-any.whl'))
        if len(outputs) != 1:
            raise OverlayError('iron_wheel_identity')
        wheel = package_license(outputs[0], folder, (source / 'LICENSE').read_bytes(), manifest['sha256'], commit)
        with WheelFile(wheel) as checked:
            licenses = [name for name in checked.namelist() if name.endswith('/licenses/LICENSE')]
            if len(licenses) != 1 or hashlib.sha256(checked.read(licenses[0])).hexdigest() != license_digest:
                raise OverlayError('iron_license')
            for name in checked.namelist():
                checked.read(name)
        target = checked_path(directory, destination / wheel.name)
        wheel_digest = digest_file(wheel)
        if target.exists():
            if target.is_symlink() or digest_file(target) != wheel_digest:
                raise OverlayError('iron_existing_wheel')
        else:
            checked_path(directory, target)
            os.link(wheel, target)
        proof = {'schema': 1, 'source_commit': commit, 'source_sha256': manifest['sha256'], 'source_unchanged': True,
                 'manifest_sha256': digest_file(manifest_path), 'builder_sha256': digest_file(Path(__file__)),
                 'license_sha256': license_digest, 'wheel_filename': wheel.name, 'wheel_sha256': wheel_digest}
        proof_path = destination / ('ironlaws-receipt-' + proof['manifest_sha256'][:16] + '-' + proof['builder_sha256'][:16] + '.json')
        content = json.dumps(proof, indent=2, sort_keys=True) + '\n'
        if proof_path.exists() and proof_path.read_text(encoding='utf-8') != content:
            raise OverlayError('iron_changed_receipt')
        atomic_bytes(directory, proof_path, content.encode('utf-8'))
        return proof_path


if __name__ == '__main__':
    try:
        receipt = build(Path(__file__).resolve().parents[2])
        print('ironlaws_source_build status=ready receipt=' + receipt.name)
    except (OverlayError, CacheBoundaryError) as failure:
        print('ironlaws_source_build status=failed category=' + failure.category)
        raise SystemExit(1) from None
