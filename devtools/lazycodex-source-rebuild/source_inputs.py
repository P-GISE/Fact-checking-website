"""Verify and extract official regular source inputs through the confined cache boundary."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path, PurePosixPath
import shutil
import tarfile

from scripts.security.cache_io import CacheBoundaryError as RebuildError, checked_path, ensure_directory, native, new_file, sha


def source_tree(plan: dict, archive: Path, base: Path) -> Path:
    source = base / 'source'
    ensure_directory(base, source)
    omitted = set(plan['omitted_documentation_symlinks'])
    seen: set[str] = set()
    count = 0
    expected_files: set[str] = set()
    with tarfile.open(archive) as original:
        members = original.getmembers()
        if sum(member.size for member in members) > 256 * 1024 * 1024 or len(members) > 20000:
            raise RebuildError('source_archive_size')
        for member in members:
            path = PurePosixPath(member.name)
            if (path.is_absolute() or str(path) != member.name.rstrip('/') or '..' in path.parts
                    or not path.parts or path.parts[0] != plan['source_prefix'] or '\\' in member.name or ':' in member.name
                    or member.name.casefold() in seen):
                raise RebuildError('source_archive_path')
            seen.add(member.name.casefold())
            relative = PurePosixPath(*path.parts[1:]).as_posix()
            if member.issym() and relative in omitted:
                continue  # These three documentation links are not installer build inputs.
            if not (member.isfile() or member.isdir()):
                raise RebuildError('source_archive_link')
            if member.mode & 0o7000:
                raise RebuildError('source_archive_mode')
            if member.isdir():
                continue
            count += 1
            expected_files.add(relative)
            output = checked_path(base, source / Path(relative))
            if native(output).exists() and relative == plan['bundle_relative']:
                continue  # The sole generated artifact is rewritten by the official build script.
            content = original.extractfile(member)
            if content is None:
                raise RebuildError('source_archive_member')
            if native(output).exists():
                if output.is_symlink() or sha(output) != hashlib.file_digest(content, 'sha256').hexdigest():
                    raise RebuildError('changed_source_file')
            else:
                with new_file(base, output) as target:
                    shutil.copyfileobj(content, target)
                checked_path(base, output)
                native(output).chmod(member.mode & 0o777)
        if count < 1000:
            raise RebuildError('source_archive_incomplete')
    actual_files: set[str] = set()
    for directory, folders, files in os.walk(source, followlinks=False):
        current = Path(directory)
        if current == source:
            folders[:] = [name for name in folders if name != 'node_modules']
        for name in folders:
            entry = current / name
            if entry.is_symlink() or entry.is_junction():
                raise RebuildError('unexpected_source_link')
        actual_files.update((current / name).relative_to(source).as_posix() for name in files)
    if actual_files != expected_files:
        raise RebuildError('unexpected_source_file')
    for name, digest in ((plan['official_build_script'], plan['official_build_script_sha256']),
                         (plan['official_license'], plan['official_license_sha256']),
                         (plan['wrapper_relative'], plan['wrapper_sha256'])):
        if sha(source / name) != digest:
            raise RebuildError('official_source_identity')
    return source

