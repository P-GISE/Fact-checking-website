from __future__ import annotations

import hashlib
import importlib.util
import io
from pathlib import Path
import tarfile

import pytest


def load(name: str, file: str):
    path = Path(__file__).resolve().parents[1] / 'devtools/lazycodex-source-rebuild' / file
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_official_body_marker_rejects_changed_executable_bytes() -> None:
    verification = load('lazy_verify_marker', 'verify.py')
    body = 'export const fixture = true;\n'
    digest = hashlib.sha256(body.encode()).hexdigest()
    text = '#!/usr/bin/env node\n// omo-codex-install:' + 'a' * 64 + ':' + digest + '\n' + body
    assert verification.marker(text) == ('a' * 64, digest)
    with pytest.raises(ValueError, match='bundle_body_digest'):
        verification.marker(text.replace('true', 'false'))


def test_whole_installed_tree_seal_includes_nonbundle_cli_files(tmp_path: Path) -> None:
    verification = load('lazy_verify_tree', 'verify.py')
    (tmp_path / 'bundle.mjs').write_text('original bundle', encoding='utf-8')
    (tmp_path / 'cli.mjs').write_text('original launcher', encoding='utf-8')
    original = verification.tree_digest(tmp_path)
    (tmp_path / 'cli.mjs').write_text('changed launcher', encoding='utf-8')
    assert verification.tree_digest(tmp_path) != original
    (tmp_path / 'cli.mjs').write_text('original launcher', encoding='utf-8')
    (tmp_path / 'extra.mjs').write_text('unexpected executable', encoding='utf-8')
    assert verification.tree_digest(tmp_path) != original


def test_source_tree_refuses_new_module_shadowing_original_imports(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rebuild = load('lazy_rebuild_source', 'rebuild.py')
    monkeypatch.setattr(rebuild, 'BASE', tmp_path)
    archive = tmp_path / 'source.tar.gz'
    contents = {'file-' + str(index): b'synthetic' for index in range(1000)}
    contents.update({'build.ts': b'official build', 'LICENSE.md': b'original license', 'wrapper.mjs': b'original launcher', 'bundle.mjs': b'generated output'})
    with tarfile.open(archive, 'w:gz') as output:
        for name, data in contents.items():
            info = tarfile.TarInfo('fixture/' + name)
            info.size = len(data)
            output.addfile(info, io.BytesIO(data))
    plan = {'source_prefix': 'fixture', 'omitted_documentation_symlinks': [], 'bundle_relative': 'bundle.mjs',
            'official_build_script': 'build.ts', 'official_build_script_sha256': hashlib.sha256(contents['build.ts']).hexdigest(),
            'official_license': 'LICENSE.md', 'official_license_sha256': hashlib.sha256(contents['LICENSE.md']).hexdigest(),
            'wrapper_relative': 'wrapper.mjs', 'wrapper_sha256': hashlib.sha256(contents['wrapper.mjs']).hexdigest()}
    source = rebuild.source_tree(plan, archive)
    (source / 'unexpected-shadow.ts').write_text('unapproved source', encoding='utf-8')
    with pytest.raises(rebuild.RebuildError, match='unexpected_source_file'):
        rebuild.source_tree(plan, archive)
