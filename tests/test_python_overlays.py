"""Exercise derived-wheel integrity without executing a vendor tool or using credentials."""
from __future__ import annotations

import hashlib
import json
import stat
from pathlib import Path
from zipfile import ZipFile, ZipInfo

import pytest
from wheel.wheelfile import WheelFile

from scripts.security.python_overlays import OverlayError, OverlaySpec, RequirementPatch, SourceArtifact, checked_source, repack_wheel
from scripts.security.compile_overlay_locks import include_platform_hashes


def test_lock_includes_both_verified_platform_hashes() -> None:
    rows = [{'name': 'litellm', 'version': '1.106.4+pgise.security1', 'sha256': value * 64} for value in ('a', 'b')]
    result = include_platform_hashes('litellm==1.106.4+pgise.security1 \\\n    --hash=sha256:' + 'a' * 64 + '\n', rows)
    assert result.count('--hash=sha256:') == 2
    assert 'b' * 64 in result
    assert include_platform_hashes(result, rows) == result


def test_lock_refuses_missing_platform() -> None:
    with pytest.raises(OverlayError, match='lock_platform_hashes'):
        include_platform_hashes('litellm==1.106.4+pgise.security1\n', [{'name': 'litellm', 'version': '1.106.4+pgise.security1', 'sha256': 'a' * 64}])


def original_wheel(folder: Path, *, dangerous_name: str | None = None, symlink: bool = False) -> Path:
    source = folder / 'sample-1.0.0-py3-none-any.whl'
    with WheelFile(source, 'w') as wheel:
        wheel.writestr('sample/__init__.py', b'BASE_CODE = True\n')
        wheel.writestr('sample-1.0.0.dist-info/METADATA', 'Metadata-Version: 2.4\nName: sample\nVersion: 1.0.0\nRequires-Dist: filelock<4,>=3\n\nDescription preserved.\n')
        wheel.writestr('sample-1.0.0.dist-info/WHEEL', 'Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n')
        wheel.writestr('sample-1.0.0.dist-info/licenses/LICENSE', b'Original license\n')
        if dangerous_name:
            info = ZipInfo(dangerous_name)
            info.filename = dangerous_name
            if symlink:
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
            wheel.writestr(info, b'synthetic')
    return source


def specification() -> OverlaySpec:
    return OverlaySpec('sample', '1.0.0', '1.0.0+pgise.security1', (RequirementPatch('filelock<4,>=3', 'filelock>=4.2.1,<5'),))


def test_repack_preserves_payload_license_and_abi_and_rebuilds_verified_record(tmp_path: Path) -> None:
    source = original_wheel(tmp_path)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()

    built = repack_wheel(source, tmp_path / 'new', specification(), digest)

    with WheelFile(built.path) as wheel:
        assert wheel.read('sample/__init__.py') == b'BASE_CODE = True\n'
        assert wheel.read('sample-1.0.0+pgise.security1.dist-info/licenses/LICENSE') == b'Original license\n'
        assert wheel.read('sample-1.0.0+pgise.security1.dist-info/WHEEL').endswith(b'Tag: py3-none-any\n')
        metadata = wheel.read('sample-1.0.0+pgise.security1.dist-info/METADATA').decode()
        assert 'Version: 1.0.0+pgise.security1\n' in metadata
        assert 'Requires-Dist: filelock>=4.2.1,<5\n' in metadata
        proof = json.loads(wheel.read('sample-1.0.0+pgise.security1.dist-info/PGISE-SECURITY-OVERLAY.json'))
        assert proof['upstream_sha256'] == digest
        for name in wheel.namelist():
            wheel.read(name)


@pytest.mark.parametrize('name', ['../outside', '/absolute', 'C:/outside', 'sample/../outside', 'sample\\outside'])
def test_repack_rejects_ambiguous_or_escaping_archive_entries(tmp_path: Path, name: str) -> None:
    source = original_wheel(tmp_path, dangerous_name=name)
    with pytest.raises(OverlayError):
        repack_wheel(source, tmp_path / 'new', specification(), hashlib.sha256(source.read_bytes()).hexdigest())


def test_repack_rejects_symlink_entries(tmp_path: Path) -> None:
    source = original_wheel(tmp_path, dangerous_name='sample/link', symlink=True)
    with pytest.raises(OverlayError):
        repack_wheel(source, tmp_path / 'new', specification(), hashlib.sha256(source.read_bytes()).hexdigest())


def test_repack_rejects_changed_original_bytes_before_writing(tmp_path: Path) -> None:
    source = original_wheel(tmp_path)
    with pytest.raises(OverlayError):
        repack_wheel(source, tmp_path / 'new', specification(), '0' * 64)
    assert not (tmp_path / 'new').exists()


def test_repack_rejects_unexpected_dependency_metadata(tmp_path: Path) -> None:
    source = original_wheel(tmp_path)
    wrong = OverlaySpec('sample', '1.0.0', '1.0.0+pgise.security1', (RequirementPatch('filelock<3', 'filelock>=4.2.1,<5'),))
    with pytest.raises(OverlayError):
        repack_wheel(source, tmp_path / 'new', wrong, hashlib.sha256(source.read_bytes()).hexdigest())


def test_repack_is_deterministic_and_does_not_replace_changed_existing_output(tmp_path: Path) -> None:
    source = original_wheel(tmp_path)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    first = repack_wheel(source, tmp_path / 'first', specification(), digest)
    second = repack_wheel(source, tmp_path / 'second', specification(), digest)
    assert first.path.read_bytes() == second.path.read_bytes()
    first.path.write_bytes(b'tampered')
    with pytest.raises(OverlayError):
        repack_wheel(source, tmp_path / 'first', specification(), digest)
    assert first.path.read_bytes() == b'tampered'


def test_repack_refuses_signed_archive_instead_of_dropping_signature(tmp_path: Path) -> None:
    source = original_wheel(tmp_path)
    with ZipFile(source, 'a') as wheel:
        wheel.writestr('sample-1.0.0.dist-info/RECORD.jws', b'synthetic-signature')
    with pytest.raises(OverlayError, match='metadata_or_signature'):
        repack_wheel(source, tmp_path / 'new', specification(), hashlib.sha256(source.read_bytes()).hexdigest())


@pytest.mark.parametrize('url', ['http://files.pythonhosted.org/a', 'https://example.invalid/a',
                               'https://user:password@files.pythonhosted.org/a', 'https://files.pythonhosted.org/a?token=synthetic'])
def test_sources_refuse_unsafe_origin_before_network(tmp_path: Path, url: str) -> None:
    with pytest.raises(OverlayError):
        checked_source(SourceArtifact('sample-1.0.0-py3-none-any.whl', url, 'a' * 64), tmp_path)


def test_installed_verifier_refuses_original_vendor_version(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from scripts.security import verify_installed_overlays
    (tmp_path / 'devtools').mkdir()
    (tmp_path / 'devtools/python-security-overlays.json').write_text('{"packages":{}}')
    class OriginalDistribution:
        version = '1.106.4'
    monkeypatch.setattr(verify_installed_overlays, 'distribution', lambda _name: OriginalDistribution())
    with pytest.raises(ValueError, match='installed_version'):
        verify_installed_overlays.verify(tmp_path, 'headroom')

def test_repack_generated_zip_metadata_is_independent_of_host_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = original_wheel(tmp_path)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    original_init = ZipInfo.__init__
    results = []
    for host_default in (0, 3):
        def initialize(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            self.create_system = host_default
        monkeypatch.setattr(ZipInfo, '__init__', initialize)
        results.append(repack_wheel(source, tmp_path / str(host_default), specification(), digest))
    assert results[0].sha256 == results[1].sha256
    with ZipFile(source) as original, ZipFile(results[1].path) as derived:
        for entry in original.infolist():
            if entry.filename.endswith('/RECORD'):
                continue
            name = entry.filename.replace('sample-1.0.0.dist-info/', 'sample-1.0.0+pgise.security1.dist-info/')
            actual = derived.getinfo(name)
            assert (actual.create_system, actual.external_attr, actual.date_time) == (entry.create_system, entry.external_attr, entry.date_time)
        for name, mode in (('PGISE-SECURITY-OVERLAY.json', 0o644), ('RECORD', 0o664)):
            actual = derived.getinfo('sample-1.0.0+pgise.security1.dist-info/' + name)
            assert actual.create_system == 0 and actual.external_attr == (stat.S_IFREG | mode) << 16
            assert actual.date_time == (1980, 1, 1, 0, 0, 0)
