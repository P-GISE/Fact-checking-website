"""Exercise real extraction against existing Windows junctions/Linux directory links."""
from __future__ import annotations

import hashlib
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import tarfile

import pytest


def fixture_archive(folder: Path) -> tuple[Path, dict]:
    archive = folder / 'synthetic.tar.gz'
    contents = {'nested/deeper/escape.txt': b'synthetic outside-write probe'}
    contents.update({'file-' + str(index): b'synthetic' for index in range(1000)})
    contents.update({'build.ts': b'build', 'LICENSE.md': b'license', 'wrapper.mjs': b'wrapper', 'bundle.mjs': b'bundle'})
    with tarfile.open(archive, 'w:gz') as output:
        for name, content in contents.items():
            entry = tarfile.TarInfo('fixture/' + name)
            entry.size = len(content)
            output.addfile(entry, io.BytesIO(content))
    plan = {'source_prefix': 'fixture', 'omitted_documentation_symlinks': [], 'bundle_relative': 'bundle.mjs',
            'official_build_script': 'build.ts', 'official_build_script_sha256': hashlib.sha256(contents['build.ts']).hexdigest(),
            'official_license': 'LICENSE.md', 'official_license_sha256': hashlib.sha256(contents['LICENSE.md']).hexdigest(),
            'wrapper_relative': 'wrapper.mjs', 'wrapper_sha256': hashlib.sha256(contents['wrapper.mjs']).hexdigest()}
    return archive, plan


def directory_link(link: Path, target: Path) -> None:
    if os.name == 'nt':
        environment = dict(os.environ, PGISE_TEST_LINK=str(link), PGISE_TEST_TARGET=str(target))
        subprocess.run(['pwsh', '-NoProfile', '-NonInteractive', '-Command',
                        'New-Item -ItemType Junction -Path $env:PGISE_TEST_LINK -Target $env:PGISE_TEST_TARGET | Out-Null'],
                       env=environment, check=True, capture_output=True)
    else:
        link.symlink_to(target, target_is_directory=True)


@pytest.mark.parametrize('placement', ['nested', 'deeper', 'source', 'cache'])
def test_actual_source_extraction_rejects_parent_links_before_any_outside_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, placement: str,
) -> None:
    path = Path(__file__).resolve().parents[1] / 'devtools/lazycodex-source-rebuild/rebuild.py'
    spec = importlib.util.spec_from_file_location('lazy_parent_' + placement, path)
    assert spec and spec.loader
    rebuild = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rebuild)
    base, outside = tmp_path / 'cache', tmp_path / 'outside'
    outside.mkdir()
    (outside / 'preserve.txt').write_bytes(b'preserve synthetic existing data')
    archive, plan = fixture_archive(tmp_path)
    if placement == 'cache':
        directory_link(base, outside)
    else:
        base.mkdir()
        source = base / 'source'
        if placement == 'source':
            directory_link(source, outside)
        else:
            source.mkdir()
            parent = source / 'nested'
            if placement == 'deeper':
                parent.mkdir()
                parent = parent / 'deeper'
            directory_link(parent, outside)
    monkeypatch.setattr(rebuild, 'BASE', base)
    with pytest.raises(rebuild.RebuildError):
        rebuild.source_tree(plan, archive)
    assert sorted(item.relative_to(outside).as_posix() for item in outside.rglob('*')) == ['preserve.txt']
    assert (outside / 'preserve.txt').read_bytes() == b'preserve synthetic existing data'


def test_dependency_installer_refuses_nested_link_before_external_installer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = Path(__file__).resolve().parents[1] / 'devtools/lazycodex-source-rebuild/rebuild.py'
    spec = importlib.util.spec_from_file_location('lazy_dependency_parent', path)
    assert spec and spec.loader
    rebuild = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rebuild)
    base = tmp_path / 'cache'
    scope = base / 'dependencies/node_modules/@posthog'
    scope.mkdir(parents=True)
    outside = tmp_path / 'outside'
    outside.mkdir()
    (outside / 'preserve.txt').write_bytes(b'preserve')
    directory_link(scope / 'core', outside)
    source = base / 'source'
    source.mkdir()
    calls = []
    monkeypatch.setattr(rebuild, 'BASE', base)
    monkeypatch.setattr(rebuild, 'run', lambda *args, **kwargs: calls.append(args))
    with pytest.raises(rebuild.RebuildError):
        rebuild.dependencies(source, {'workspace_packages': []}, {}, install=True)
    assert calls == []
    assert sorted(path.relative_to(outside).as_posix() for path in outside.rglob('*')) == ['preserve.txt']
    assert (outside / 'preserve.txt').read_bytes() == b'preserve'


@pytest.mark.parametrize('kind', ['hardlink', 'privileged_mode'])
def test_source_intake_still_refuses_unsafe_archive_members(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str) -> None:
    path = Path(__file__).resolve().parents[1] / 'devtools/lazycodex-source-rebuild/rebuild.py'
    spec = importlib.util.spec_from_file_location('lazy_archive_' + kind, path)
    assert spec and spec.loader
    rebuild = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rebuild)
    base = tmp_path / 'cache'
    base.mkdir()
    monkeypatch.setattr(rebuild, 'BASE', base)
    archive, plan = fixture_archive(tmp_path)
    with tarfile.open(archive, 'w:gz') as output:
        member = tarfile.TarInfo('fixture/unsafe')
        if kind == 'hardlink':
            member.type, member.linkname = tarfile.LNKTYPE, '../../outside'
            output.addfile(member)
        else:
            member.mode, member.size = 0o4755, 9
            output.addfile(member, io.BytesIO(b'synthetic'))
    with pytest.raises(rebuild.RebuildError):
        rebuild.source_tree(plan, archive)
    assert not (base / 'source/unsafe').exists()


def test_matching_partial_source_is_verified_without_replacing_existing_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = Path(__file__).resolve().parents[1] / 'devtools/lazycodex-source-rebuild/rebuild.py'
    spec = importlib.util.spec_from_file_location('lazy_partial_source', path)
    assert spec and spec.loader
    rebuild = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rebuild)
    base = tmp_path / 'cache'
    source = base / 'source'
    source.mkdir(parents=True)
    existing = source / 'build.ts'
    existing.write_bytes(b'build')
    previous = existing.stat()
    monkeypatch.setattr(rebuild, 'BASE', base)
    archive, plan = fixture_archive(tmp_path)
    assert rebuild.source_tree(plan, archive) == source
    assert existing.read_bytes() == b'build'
    assert existing.stat().st_ino == previous.st_ino
    assert existing.stat().st_mtime_ns == previous.st_mtime_ns


def test_installed_overlay_refuses_node_modules_parent_before_mutation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = Path(__file__).resolve().parents[1] / 'devtools/lazycodex-source-rebuild/install.py'
    monkeypatch.syspath_prepend(str(path.parent))
    spec = importlib.util.spec_from_file_location('lazy_install_parent', path)
    assert spec and spec.loader
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)
    root = tmp_path / 'project'
    (root / 'devtools/node').mkdir(parents=True)
    outside = tmp_path / 'outside'
    (outside / 'lazycodex-ai').mkdir(parents=True)
    (outside / 'lazycodex-ai/preserve.txt').write_bytes(b'preserve')
    directory_link(root / 'devtools/node/node_modules', outside)
    monkeypatch.setattr(installer, 'ROOT', root)
    monkeypatch.setattr(installer, 'check_artifact', lambda: ({}, {}, tmp_path / 'fixture-receipt'))
    from scripts.security.cache_io import CacheBoundaryError
    with pytest.raises(CacheBoundaryError):
        installer.install()
    assert sorted(path.relative_to(outside).as_posix() for path in outside.rglob('*')) == ['lazycodex-ai', 'lazycodex-ai/preserve.txt']
    assert (outside / 'lazycodex-ai/preserve.txt').read_bytes() == b'preserve'


@pytest.mark.parametrize('placement', ['cache', 'parent'])
def test_actual_python_wheel_intake_refuses_link_parents_before_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, placement: str,
) -> None:
    from scripts.security import python_overlay_sources as python_overlays
    from scripts.security.cache_io import CacheBoundaryError
    outside = tmp_path / 'outside'
    outside.mkdir()
    (outside / 'preserve.txt').write_bytes(b'synthetic existing file')
    link = tmp_path / 'link'
    directory_link(link, outside)
    cache = link if placement == 'cache' else link / 'cache'
    payload = b'synthetic public package fixture bytes'
    class SyntheticOpener:
        def open(self, *_args, **_kwargs):
            return io.BytesIO(payload)
    monkeypatch.setattr(python_overlays, 'build_opener', lambda *_args: SyntheticOpener())
    artifact = python_overlays.SourceArtifact('fixture-1.0.0-py3-none-any.whl',
        'https://files.pythonhosted.org/fixture-1.0.0-py3-none-any.whl', hashlib.sha256(payload).hexdigest())
    with pytest.raises(CacheBoundaryError):
        python_overlays.checked_source(artifact, cache)
    assert sorted(item.relative_to(outside).as_posix() for item in outside.rglob('*')) == ['preserve.txt']
