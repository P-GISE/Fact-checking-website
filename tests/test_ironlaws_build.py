"""Negative extraction boundaries and packaging-only provenance preservation."""
from __future__ import annotations

import io
from pathlib import Path
import tarfile

import pytest
from wheel.wheelfile import WheelFile

from scripts.security.build_ironlaws import package_license, safe_members
from scripts.security.python_overlays import OverlayError


@pytest.mark.parametrize('name', ['../escape', '/absolute', 'root/../escape', 'other/file', 'root/C:/drive', 'root//ambiguous', 'root/./ambiguous'])
def test_archive_rejects_escape_and_wrong_root(name: str) -> None:
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w') as archive:
        info = tarfile.TarInfo(name)
        info.size = 1
        archive.addfile(info, io.BytesIO(b'x'))
    stream.seek(0)
    with tarfile.open(fileobj=stream, mode='r') as archive, pytest.raises(OverlayError):
        safe_members(archive, 'root')


def test_archive_rejects_symbolic_link() -> None:
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w') as archive:
        info = tarfile.TarInfo('root/link')
        info.type = tarfile.SYMTYPE
        info.linkname = '/outside'
        archive.addfile(info)
    stream.seek(0)
    with tarfile.open(fileobj=stream, mode='r') as archive, pytest.raises(OverlayError):
        safe_members(archive, 'root')


def test_packaging_overlay_keeps_original_code_and_adds_license(tmp_path: Path) -> None:
    original = tmp_path / 'iron_laws-1.7.0-py3-none-any.whl'
    with WheelFile(original, 'w') as output:
        output.writestr('iron_laws/__init__.py', b'ORIGINAL_PAYLOAD = True\n')
        output.writestr('iron_laws-1.7.0.dist-info/METADATA', 'Metadata-Version: 2.4\nName: iron-laws\nVersion: 1.7.0\n\n')
        output.writestr('iron_laws-1.7.0.dist-info/WHEEL', 'Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n')
    derived = package_license(original, tmp_path, b'Synthetic original license\n', 'a' * 64, 'b' * 40)
    with WheelFile(derived) as checked:
        assert checked.read('iron_laws/__init__.py') == b'ORIGINAL_PAYLOAD = True\n'
        assert checked.read(checked.dist_info_path + '/licenses/LICENSE') == b'Synthetic original license\n'
        metadata = checked.read(checked.dist_info_path + '/METADATA')
        assert b'Version: 1.7.0+pgise.security1\n' in metadata
        assert b'License-File: licenses/LICENSE\n' in metadata
        for name in checked.namelist():
            checked.read(name)
