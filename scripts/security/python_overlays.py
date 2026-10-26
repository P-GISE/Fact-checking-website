"""Derive explicitly identified security wheels from verified upstream artifacts."""
from __future__ import annotations

from dataclasses import dataclass
from contextlib import contextmanager
from copy import copy
from email import policy
from email.parser import BytesParser
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import stat
import sys
from tempfile import TemporaryDirectory
from typing import Final, Iterator, Mapping

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name, parse_wheel_filename
from packaging.version import Version
from wheel.wheelfile import WheelFile

from scripts.security.cache_io import CacheBoundaryError, atomic_bytes, checked_path, ensure_directory, new_file
from scripts.security.python_overlay_sources import NoRedirect, OverlayError, SourceArtifact, checked_source

MAX_ENTRY_BYTES: Final = 128 * 1024 * 1024
MAX_UNPACKED_BYTES: Final = 768 * 1024 * 1024
type Json = str | int | float | bool | None | list[Json] | dict[str, Json]


@dataclass(frozen=True, slots=True)
class RequirementPatch:
    previous: str
    replacement: str


@dataclass(frozen=True, slots=True)
class OverlaySpec:
    name: str
    upstream_version: str
    local_version: str
    requirements: tuple[RequirementPatch, ...]


@dataclass(frozen=True, slots=True)
class BuiltOverlay:
    path: Path
    sha256: str


SPECS: Final = (
    OverlaySpec('litellm', '1.106.4', '1.106.4+pgise.security1', (
        RequirementPatch('filelock>=3.16.1,<4.0', 'filelock>=4.2.1,<5.0'),
    )),
    OverlaySpec('strix-agent', '1.7.0', '1.7.0+pgise.security1', (
        RequirementPatch('cryptography<49,>=48.0.1', 'cryptography>=50.0.0,<51.0'),
        RequirementPatch('litellm>=1.101.0', 'litellm==1.106.4+pgise.security1'),
    )),
)


def repack_wheel(source: Path, destination: Path, spec: OverlaySpec, expected_sha256: str) -> BuiltOverlay:
    """Preserve verified code/ABI/licenses; replace only explicit distribution metadata."""
    if source.is_symlink() or digest_file(source) != expected_sha256:
        raise OverlayError('upstream_digest')
    name, version, _, _ = parse_wheel_filename(source.name)
    local = Version(spec.local_version)
    if (name != canonicalize_name(spec.name) or str(version) != spec.upstream_version
            or not local.local or local.base_version != version.base_version):
        raise OverlayError('distribution_identity')
    filename = source.name.split('-')
    filename[1] = spec.local_version
    derived_name = '-'.join(filename)
    ensure_directory(destination, destination)
    checked_path(destination, destination / derived_name)
    with WheelFile(source) as original:
        names = original.namelist()
        if len(names) != len(set(names)) or len(names) != len({n.casefold() for n in names}):
            raise OverlayError('duplicate_entry')
        total = 0
        for info in original.infolist():
            entry = PurePosixPath(info.filename)
            if (info.orig_filename != info.filename or entry.is_absolute() or '\\' in info.filename or ':' in info.filename
                    or '..' in entry.parts or str(entry) != info.filename.rstrip('/')
                    or stat.S_IFMT(info.external_attr >> 16) == stat.S_IFLNK):
                raise OverlayError('unsafe_archive')
            total += info.file_size
            if info.file_size > MAX_ENTRY_BYTES or total > MAX_UNPACKED_BYTES:
                raise OverlayError('archive_size')
        old_info = original.dist_info_path
        new_info = f'{filename[0]}-{spec.local_version}.dist-info'
        if (sum(n.endswith('.dist-info/METADATA') for n in names) != 1
                or any(n in names for n in (original.record_path + '.jws', original.record_path + '.p7s'))):
            raise OverlayError('metadata_or_signature')
        message = BytesParser(policy=policy.default).parsebytes(original.read(old_info + '/METADATA'))
        if canonicalize_name(message.get('Name', '')) != canonicalize_name(spec.name) or message.get('Version') != spec.upstream_version:
            raise OverlayError('metadata_identity')
        requirements = message.get_all('Requires-Dist', [])
        for patch in spec.requirements:
            Requirement(patch.replacement)
            if requirements.count(patch.previous) != 1:
                raise OverlayError('requirements_mismatch')
            requirements[requirements.index(patch.previous)] = patch.replacement
        del message['Requires-Dist']
        for requirement in requirements:
            message['Requires-Dist'] = requirement
        message.replace_header('Version', spec.local_version)
        metadata = message.as_bytes(policy=policy.default.clone(utf8=True, max_line_length=0, linesep='\n'))
        proof = {
            'schema': 1,
            'name': spec.name,
            'upstream_version': spec.upstream_version,
            'local_version': spec.local_version,
            'upstream_filename': source.name,
            'upstream_sha256': expected_sha256,
            'requirements_patch': [{'previous': p.previous, 'replacement': p.replacement} for p in spec.requirements],
            'preserved': 'all non-metadata payload bytes, WHEEL ABI/platform tags, archive modes and license files',
        }
        ensure_directory(destination, destination)
        with TemporaryDirectory(prefix='overlay-', dir=destination) as temporary:
            candidate = Path(temporary) / derived_name
            with new_file(destination, candidate):
                pass
            checked_path(destination, candidate)
            with fixed_zip_time(), WheelFile(candidate, 'w') as output:
                for info in sorted(original.infolist(), key=lambda value: value.filename):
                    if info.is_dir() or info.filename == original.record_path:
                        continue
                    renamed = info.filename
                    if renamed.startswith(old_info + '/'):
                        renamed = new_info + renamed[len(old_info):]
                    old_data = old_info.removesuffix('.dist-info') + '.data/'
                    if renamed.startswith(old_data):
                        renamed = new_info.removesuffix('.dist-info') + '.data/' + renamed[len(old_data):]
                    target = copy(info)
                    target.filename = renamed
                    output.writestr(target, metadata if info.filename == old_info + '/METADATA' else original.read(info.filename))
                from zipfile import ZipInfo
                provenance = ZipInfo(new_info + '/PGISE-SECURITY-OVERLAY.json', date_time=(1980, 1, 1, 0, 0, 0))
                provenance.external_attr = (stat.S_IFREG | 0o644) << 16
                output.writestr(provenance, json.dumps(proof, sort_keys=True, indent=2).encode())
            with WheelFile(candidate) as verified:
                for entry in verified.namelist():
                    verified.read(entry)
            digest = digest_file(candidate)
            target = destination / derived_name
            if target.exists():
                if target.is_symlink() or digest_file(target) != digest:
                    raise OverlayError('changed_output')
            else:
                checked_path(destination, target)
                os.link(candidate, target)
            return BuiltOverlay(target, digest)


def digest_file(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


@contextmanager
def fixed_zip_time() -> Iterator[None]:
    """The wheel library uses SOURCE_DATE_EPOCH for its generated RECORD entry."""
    previous = os.environ.get('SOURCE_DATE_EPOCH')
    os.environ['SOURCE_DATE_EPOCH'] = '315532800'
    try:
        yield
    finally:
        if previous is None:
            del os.environ['SOURCE_DATE_EPOCH']
        else:
            os.environ['SOURCE_DATE_EPOCH'] = previous


def object_value(value: Json) -> Mapping[str, Json]:
    match value:
        case dict() as record:
            return record
        case _:
            raise OverlayError('manifest_object')


def string_value(value: Json) -> str:
    match value:
        case str() as text:
            return text
        case _:
            raise OverlayError('manifest_string')


def require_supported_host() -> None:
    if platform.machine().lower() not in ('amd64', 'x86_64'):
        raise OverlayError('unsupported_host')
    match sys.platform:
        case 'win32':
            return
        case 'linux':
            family, version = platform.libc_ver()
            parts = tuple(int(v) for v in version.split('.') if v.isdigit())
            if family != 'glibc' or parts < (2, 28):
                raise OverlayError('unsupported_libc')
        case _:
            raise OverlayError('unsupported_host')


def build_all(root: Path) -> Path:
    require_supported_host()
    manifest = root / 'devtools/python-security-overlays.json'
    document = object_value(json.loads(manifest.read_text(encoding='utf-8')))
    if type(document.get('schema')) is not int or document['schema'] != 1:
        raise OverlayError('manifest_schema')
    packages = object_value(document['packages'])
    directory = root / '.devtools'
    ensure_directory(root, directory)
    cache = directory / 'security-source-cache'
    destination = directory / 'patched-wheels'
    outputs = []
    for spec in SPECS:
        entry = object_value(packages[spec.name])
        if entry['upstream_version'] != spec.upstream_version:
            raise OverlayError('manifest_version')
        match entry['artifacts']:
            case list() as items:
                if len(items) != 2:
                    raise OverlayError('manifest_platforms')
                platforms: set[str] = set()
                for item in items:
                    fields = object_value(item)
                    artifact = SourceArtifact(string_value(fields['filename']), string_value(fields['url']), string_value(fields['sha256']))
                    _name, _version, _build, tags = parse_wheel_filename(artifact.filename)
                    platforms.update(tag.platform for tag in tags)
                    original = checked_source(artifact, cache)
                    built = repack_wheel(original, destination, spec, artifact.sha256)
                    outputs.append({'name': spec.name, 'version': spec.local_version, 'filename': built.path.name,
                                    'sha256': built.sha256, 'upstream_sha256': artifact.sha256})
                linux = 'manylinux_2_28_x86_64' if spec.name == 'litellm' else 'manylinux_2_17_x86_64'
                if platforms != {'win_amd64', linux}:
                    raise OverlayError('manifest_platforms')
            case _:
                raise OverlayError('manifest_artifacts')
    receipt = {'schema': 1, 'manifest_sha256': digest_file(manifest), 'builder_sha256': digest_file(Path(__file__)),
               'io_helpers_sha256': {name: digest_file(root / name) for name in ('scripts/security/cache_io.py', 'scripts/security/python_overlay_sources.py')},
               'wheels': outputs}
    receipt_path = destination / ('receipt-' + receipt['manifest_sha256'][:16] + '-' + receipt['builder_sha256'][:16] + '.json')
    content = json.dumps(receipt, indent=2, sort_keys=True) + '\n'
    if receipt_path.exists() and receipt_path.read_text(encoding='utf-8') != content:
        raise OverlayError('changed_receipt')
    if not receipt_path.exists():
        atomic_bytes(directory, receipt_path, content.encode('utf-8'))
    return receipt_path


if __name__ == '__main__':
    try:
        proof_path = build_all(Path(__file__).resolve().parents[2])
        print('python_security_overlay status=ready receipt=' + proof_path.name)
    except (OverlayError, CacheBoundaryError) as failure:
        print('python_security_overlay status=failed category=' + failure.category)
        raise SystemExit(1) from None
