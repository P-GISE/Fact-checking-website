from pathlib import Path
import os
import subprocess

import pytest

from scripts.security.cache_io import CacheBoundaryError, atomic_bytes, atomic_copy, ensure_directory, new_file


def directory_link(link: Path, target: Path) -> None:
    if os.name == 'nt':
        environment = dict(os.environ, PGISE_TEST_LINK=str(link), PGISE_TEST_TARGET=str(target))
        subprocess.run(['pwsh', '-NoProfile', '-NonInteractive', '-Command',
                        'New-Item -ItemType Junction -Path $env:PGISE_TEST_LINK -Target $env:PGISE_TEST_TARGET | Out-Null'],
                       env=environment, check=True, capture_output=True)
    else:
        link.symlink_to(target, target_is_directory=True)


@pytest.mark.parametrize('operation', ['exclusive', 'copy', 'bytes', 'mkdir'])
@pytest.mark.parametrize('placement', ['parent', 'above_anchor'])
def test_cache_write_operations_refuse_links_before_outside_mutation(tmp_path: Path, operation: str, placement: str) -> None:
    outside = tmp_path / 'outside'
    outside.mkdir()
    (outside / 'preserve.txt').write_bytes(b'preserve')
    source = tmp_path / 'input'
    source.write_bytes(b'synthetic payload')
    if placement == 'above_anchor':
        directory_link(tmp_path / 'alias', outside)
        anchor = tmp_path / 'alias/cache'
        target = anchor / 'new/output'
    else:
        anchor = tmp_path / 'cache'
        anchor.mkdir()
        directory_link(anchor / 'nested', outside)
        target = anchor / 'nested/new/output'
    with pytest.raises(CacheBoundaryError):
        match operation:
            case 'exclusive':
                with new_file(anchor, target) as output:
                    output.write(b'payload')
            case 'copy':
                atomic_copy(anchor, source, target)
            case 'bytes':
                atomic_bytes(anchor, target, b'payload')
            case 'mkdir':
                ensure_directory(anchor, target)
    assert sorted(path.relative_to(outside).as_posix() for path in outside.rglob('*')) == ['preserve.txt']
    assert (outside / 'preserve.txt').read_bytes() == b'preserve'


def test_atomic_replace_does_not_modify_outside_hardlink(tmp_path: Path) -> None:
    cache = tmp_path / 'cache'
    cache.mkdir()
    outside = tmp_path / 'outside-existing'
    outside.write_bytes(b'preserve')
    target = cache / 'target'
    os.link(outside, target)
    atomic_bytes(cache, target, b'new cache contents')
    assert outside.read_bytes() == b'preserve'
    assert target.read_bytes() == b'new cache contents'


def test_new_file_refuses_existing_leaf(tmp_path: Path) -> None:
    target = tmp_path / 'existing'
    target.write_bytes(b'preserve')
    with pytest.raises(FileExistsError):
        with new_file(tmp_path, target):
            pass
    assert target.read_bytes() == b'preserve'
