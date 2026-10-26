"""Immutable PyPI intake policy and source identity, separate from wheel derivation."""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from typing import Final
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from packaging.utils import parse_wheel_filename
from scripts.security.cache_io import CacheBoundaryError, checked_path, ensure_directory, new_file, sha

MAX_DOWNLOAD_BYTES: Final = 80 * 1024 * 1024

class OverlayError(Exception):
    """A fixed category suitable for output without vendor data or credentials."""

    def __init__(self, category: str) -> None:
        self.category = category
        super().__init__(category)


@dataclass(frozen=True, slots=True)
class SourceArtifact:
    filename: str
    url: str
    sha256: str


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args: object, **_kwargs: object) -> None:
        return None


def checked_source(artifact: SourceArtifact, cache: Path) -> Path:
    """Fetch immutable PyPI bytes only; no credential, redirect or overwrite path."""
    uri = urlparse(artifact.url)
    if (uri.scheme != 'https' or uri.netloc != 'files.pythonhosted.org'
            or uri.query or uri.fragment or uri.username or uri.password
            or '/' in artifact.filename or '\\' in artifact.filename or ':' in artifact.filename
            or not artifact.filename.endswith('.whl')
            or not re.fullmatch('[a-f0-9]{64}', artifact.sha256)):
        raise OverlayError('source_manifest')
    parse_wheel_filename(artifact.filename)
    ensure_directory(cache, cache)
    target = checked_path(cache, cache / artifact.filename)
    if target.exists():
        if target.is_symlink() or sha(target) != artifact.sha256:
            raise OverlayError('cache_digest')
        return target
    with TemporaryDirectory(prefix='download-', dir=cache) as temporary:
        part = Path(temporary) / 'artifact.download'
        total = 0
        with build_opener(NoRedirect).open(Request(artifact.url), timeout=60) as response, new_file(cache, part) as output:
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_DOWNLOAD_BYTES:
                    raise OverlayError('download_size')
                output.write(chunk)
        if sha(part) != artifact.sha256:
            raise OverlayError('download_digest')
        checked_path(cache, target)
        os.link(part, target)
    return target

