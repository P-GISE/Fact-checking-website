"""Confine owned-cache I/O before writes; not a lock against concurrent administrators."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import io
import os
from pathlib import Path
import shutil
import stat
from tempfile import TemporaryDirectory
from typing import BinaryIO, Iterator


class CacheBoundaryError(Exception):
    def __init__(self, category: str) -> None:
        self.category = category
        super().__init__(category)


def native(path: Path) -> Path:
    absolute = path.absolute()
    return Path('\\\\?\\' + str(absolute)) if os.name == 'nt' else absolute


def sha(path: Path) -> str:
    with native(path).open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def checked_path(anchor: Path, target: Path, *, directory: bool = False) -> Path:
    if '..' in anchor.parts or '..' in target.parts:
        raise CacheBoundaryError('cache_path_escape')
    anchor, target = anchor.absolute(), target.absolute()
    if not target.is_relative_to(anchor):
        raise CacheBoundaryError('cache_path_escape')
    # Include existing ancestors of the anchor: an intermediate .devtools link is
    # equally dangerous even if the anchor/leaf themselves are ordinary objects.
    for entry in reversed((target, *target.parents)):
        try:
            metadata = native(entry).lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(metadata.st_mode) or getattr(metadata, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0):
            raise CacheBoundaryError('cache_parent_link')
        if entry != target or directory:
            if not stat.S_ISDIR(metadata.st_mode):
                raise CacheBoundaryError('cache_parent_not_directory')
        elif not stat.S_ISREG(metadata.st_mode):
            raise CacheBoundaryError('cache_target_not_regular')
    if not target.resolve(strict=False).is_relative_to(anchor.resolve(strict=False)):
        raise CacheBoundaryError('cache_resolved_escape')
    return target


def ensure_directory(anchor: Path, target: Path) -> None:
    target = checked_path(anchor, target, directory=True)
    anchor = anchor.absolute()
    if not native(anchor).exists():
        native(anchor).mkdir(mode=0o700)
    checked_path(anchor, anchor, directory=True)
    current = anchor
    for part in target.relative_to(anchor).parts:
        current /= part
        checked_path(anchor, current, directory=True)
        try:
            native(current).mkdir(mode=0o700)
        except FileExistsError:
            pass
        checked_path(anchor, current, directory=True)


@contextmanager
def new_file(anchor: Path, target: Path) -> Iterator[BinaryIO]:
    ensure_directory(anchor, target.parent)
    checked_path(anchor, target)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
    descriptor = os.open(native(target), flags, 0o600)
    with os.fdopen(descriptor, 'wb') as output:
        if not stat.S_ISREG(os.fstat(output.fileno()).st_mode):
            raise CacheBoundaryError('cache_created_not_regular')
        checked_path(anchor, target)
        yield output


def atomic_stream(anchor: Path, target: Path, content: BinaryIO) -> None:
    ensure_directory(anchor, target.parent)
    checked_path(anchor, target)
    with TemporaryDirectory(prefix='stage-', dir=target.parent) as folder:
        staged = Path(folder) / 'payload'
        with new_file(anchor, staged) as output:
            shutil.copyfileobj(content, output)
        checked_path(anchor, target)
        os.replace(native(staged), native(target))


def atomic_copy(anchor: Path, source: Path, target: Path) -> None:
    checked_path(anchor, target)
    if native(target).exists() and sha(target) == sha(source):
        return
    with native(source).open('rb') as content:
        atomic_stream(anchor, target, content)


def atomic_bytes(anchor: Path, target: Path, content: bytes) -> None:
    checked_path(anchor, target)
    if native(target).exists() and sha(target) == hashlib.sha256(content).hexdigest():
        return
    atomic_stream(anchor, target, io.BytesIO(content))


def checked_mutable_tree(anchor: Path, root: Path, *, npm_bin: bool = False) -> None:
    """Reject pre-existing link parents before an external installer mutates a cache."""
    checked_path(anchor, root, directory=True)
    if not native(root).exists():
        return
    for directory, folders, files in os.walk(root, followlinks=False):
        current = Path(directory)
        for name in (*folders, *files):
            path = current / name
            metadata = native(path).lstat()
            linked = stat.S_ISLNK(metadata.st_mode) or getattr(metadata, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0)
            if linked:
                # npm's one legitimate executable link is internal to the owned
                # dependency tree; arbitrary cache or directory links stay refused.
                if (npm_bin and path.relative_to(root).as_posix() == 'node_modules/.bin/js-yaml'
                        and path.resolve().is_file()
                        and path.resolve() == (root / 'node_modules/js-yaml/bin/js-yaml.js').resolve()
                        and path.resolve().is_relative_to(root.resolve())):
                    continue
                raise CacheBoundaryError('cache_mutable_tree_link')
            if stat.S_ISREG(metadata.st_mode) and metadata.st_nlink > 1:
                raise CacheBoundaryError('cache_mutable_hardlink')
