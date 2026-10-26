"""Pinned public archive and runtime intake, using the shared owned-cache boundary."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import platform
import sys
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zipfile import ZipFile

from scripts.security.cache_io import CacheBoundaryError as RebuildError, checked_path, ensure_directory, native, new_file, sha


class OfficialRedirects(HTTPRedirectHandler):
    def redirect_request(self, request: Request, response: object, code: int, message: str,
                         headers: object, url: str) -> Request | None:
        parts = urlsplit(url)
        if parts.scheme != 'https' or parts.username or parts.password or parts.hostname not in {
            'github.com', 'codeload.github.com', 'release-assets.githubusercontent.com',
            'objects.githubusercontent.com', 'github-releases.githubusercontent.com',
        }:
            raise RebuildError('download_redirect')
        return super().redirect_request(request, response, code, message, headers, url)


def download(base: Path, name: str, url: str, digest: str, limit: int) -> Path:
    ensure_directory(base, base)
    target = checked_path(base, base / name)
    if target.exists():
        if target.is_symlink() or sha(target) != digest:
            raise RebuildError('cached_artifact_digest')
        return target
    with TemporaryDirectory(prefix='download-', dir=base) as temporary:
        part = Path(temporary) / 'artifact'
        size = 0
        with build_opener(OfficialRedirects).open(Request(url), timeout=60) as response, new_file(base, part) as output:
            while chunk := response.read(1024 * 1024):
                size += len(chunk)
                if size > limit:
                    raise RebuildError('download_size')
                output.write(chunk)
        if sha(part) != digest:
            raise RebuildError('download_digest')
        checked_path(base, target)
        os.link(native(part), native(target))
    return target


def runtime(base: Path, plan: dict) -> Path:
    if platform.machine().lower() not in ('amd64', 'x86_64') or sys.platform not in plan['runtimes']:
        raise RebuildError('unsupported_platform')
    selected = plan['runtimes'][sys.platform]
    checksums = download(base, 'SHASUMS256.txt', plan['bun_checksums_url'], plan['bun_checksums_sha256'], 1024 * 1024)
    lines = checksums.read_text(encoding='utf-8').splitlines()
    if not any(line.split()[0] == selected['sha256'] and line.split()[-1].lstrip('*') == selected['archive'] for line in lines if line.split()):
        raise RebuildError('official_checksum_manifest')
    url = 'https://github.com/oven-sh/bun/releases/download/bun-v' + plan['bun_version'] + '/' + selected['archive']
    archive = download(base, selected['archive'], url, selected['sha256'], 128 * 1024 * 1024)
    with ZipFile(archive) as bundle:
        entry = bundle.getinfo(selected['member'])
        if entry.file_size > 256 * 1024 * 1024:
            raise RebuildError('runtime_size')
        content = bundle.read(entry)
    target = base / 'runtime' / ('bun.exe' if os.name == 'nt' else 'bun')
    ensure_directory(base, target.parent)
    checked_path(base, target)
    if target.exists():
        if target.is_symlink() or sha(target) != hashlib.sha256(content).hexdigest():
            raise RebuildError('runtime_digest')
    else:
        with new_file(base, target) as output:
            output.write(content)
        checked_path(base, target)
        native(target).chmod(0o700)
    return target

