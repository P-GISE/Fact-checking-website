"""Rebuild the official installer only; never install a Codex harness or change routing."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = ROOT / '.devtools/lazycodex-security-build'


# Helpers are repository-local; this changes only this process's import search path.
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
from scripts.security.cache_io import CacheBoundaryError as RebuildError, atomic_bytes, atomic_copy, checked_mutable_tree, checked_path, ensure_directory, sha
from source_inputs import source_tree as extract_source_tree
from signed_inputs import download, runtime


def clean_environment(home: Path) -> dict[str, str]:
    environment = {key: value for key, value in os.environ.items()
                   if key.upper() in ('PATH', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP')}
    environment.update(HOME=str(home), USERPROFILE=str(home), CODEX_HOME=str(home / 'codex'),
                       DO_NOT_TRACK='1', BUN_TELEMETRY_DISABLE='1', OMO_TELEMETRY_DISABLED='1',
                       npm_config_cache=str(BASE / 'npm-cache'))
    return environment


def run(command: list[str], cwd: Path, environment: dict[str, str], category: str, timeout: int = 180) -> bytes:
    result = subprocess.run(command, cwd=cwd, env=environment, capture_output=True, timeout=timeout)
    if result.returncode:
        raise RebuildError(category)
    return result.stdout


def source_tree(plan: dict, archive: Path) -> Path:
    return extract_source_tree(plan, archive, BASE)


def tree_digest(root: Path) -> str:
    checked_path(root, root, directory=True)
    digest = hashlib.sha256()
    for directory, folders, files in os.walk(root, followlinks=False):
        folders.sort()
        current = Path(directory)
        for folder in folders:
            entry = current / folder
            checked_path(root, entry, directory=True)
        for name in sorted(files):
            entry = current / name
            checked_path(root, entry)
            digest.update(entry.relative_to(root).as_posix().encode())
            digest.update(bytes.fromhex(sha(entry)))
    return digest.hexdigest()


def dependencies(source: Path, plan: dict, environment: dict[str, str], install: bool) -> tuple[Path, dict[str, str]]:
    target = BASE / 'dependencies'
    ensure_directory(BASE, target)
    for name in ('package.json', 'package-lock.json'):
        cached = checked_path(BASE, target / name)
        if install:
            atomic_copy(BASE, HERE / 'build-deps' / name, cached)
        elif sha(HERE / 'build-deps' / name) != sha(cached):
            raise RebuildError('resume_lock_identity')
    if install:
        checked_mutable_tree(BASE, target, npm_bin=True)
        checked_mutable_tree(BASE, BASE / 'npm-cache')
        run(['npm.cmd' if os.name == 'nt' else 'npm', 'ci', '--ignore-scripts', '--no-audit', '--no-fund',
             '--registry=https://registry.npmjs.org', '--prefix', str(target)], ROOT, environment, 'locked_dependencies')
    lock = json.loads((target / 'package-lock.json').read_text(encoding='utf-8'))
    payloads = {}
    for package, details in lock['packages'].items():
        if not package:
            continue
        if not package.startswith('node_modules/') or not details.get('integrity', '').startswith('sha512-'):
            raise RebuildError('dependency_lock_identity')
        relative = package.removeprefix('node_modules/')
        original = checked_path(BASE, target / package, directory=True)
        destination = checked_path(BASE, source / package, directory=True)
        before = tree_digest(original)
        if destination.exists():
            if tree_digest(destination) != before:
                raise RebuildError('changed_source_dependency')
        else:
            ensure_directory(BASE, destination.parent)
            shutil.copytree(original, destination)
        payloads[relative] = before
    scope = source / 'node_modules/@oh-my-opencode'
    ensure_directory(BASE, scope)
    for name in plan['workspace_packages']:
        link, destination = scope / name, source / 'packages' / name
        if not (link.exists() or link.is_symlink() or link.is_junction()):
            checked_path(BASE, link)
            checked_path(BASE, destination, directory=True)
            try:
                link.symlink_to(destination, target_is_directory=True)
            except OSError:
                if os.name != 'nt':
                    raise
                link_environment = dict(environment, PGISE_LINK=str(link), PGISE_TARGET=str(destination))
                run(['pwsh', '-NoProfile', '-NonInteractive', '-Command',
                     'New-Item -ItemType Junction -Path $env:PGISE_LINK -Target $env:PGISE_TARGET | Out-Null'],
                    ROOT, link_environment, 'workspace_link')
        if link.resolve() != destination.resolve() or not destination.resolve().is_relative_to(source.resolve()):
            raise RebuildError('workspace_link_target')
    return target, payloads


def build(resume: Path | None = None) -> Path:
    plan = json.loads((HERE / 'plan.json').read_text(encoding='utf-8'))
    if (ROOT.joinpath('.devtools').is_symlink() or ROOT.joinpath('.devtools').is_junction()
            or BASE.is_symlink() or BASE.is_junction()):
        raise RebuildError('owned_cache')
    ensure_directory(ROOT, ROOT / '.devtools')
    ensure_directory(ROOT / '.devtools', BASE)
    for name in ('runtime', 'source', 'dependencies', 'artifact'):
        if (BASE / name).is_symlink() or (BASE / name).is_junction():
            raise RebuildError('owned_cache_child')
    with TemporaryDirectory(prefix='pgise-lazy-build-home-') as temporary:
        environment = clean_environment(Path(temporary))
        node_version = run(['node', '--version'], ROOT, environment, 'node_runtime').decode().strip()
        if not re.fullmatch(r'v24\.(?:2[0-9]|[3-9][0-9])\.\d+', node_version):
            raise RebuildError('unsupported_node_runtime')
        compiler = runtime(BASE, plan)
        if run([str(compiler), '--version'], ROOT, environment, 'bun_runtime').decode().strip() != plan['bun_version']:
            raise RebuildError('bun_runtime_version')
        archive = download(BASE, 'source.tar.gz', plan['source_url'], plan['source_sha256'], 128 * 1024 * 1024)
        source = source_tree(plan, archive)
        _dependency_root, payloads = dependencies(source, plan, environment, install=resume is None)
        checkpoint = None
        if resume is None:
            run([str(compiler), '--no-install', plan['official_build_script']], source, environment, 'official_build')
        else:
            if resume.resolve().parent != (BASE / 'artifact').resolve() or resume.is_symlink():
                raise RebuildError('resume_receipt_path')
            checkpoint = json.loads(resume.read_text(encoding='utf-8'))
            if (checkpoint['source_sha256'] != plan['source_sha256'] or checkpoint['source_code_unchanged'] is not True
                    or checkpoint['lock_sha256'] != sha(HERE / 'build-deps/package-lock.json')
                    or checkpoint['dependency_payload_sha256'] != payloads
                    or checkpoint['bundle_sha256'] != sha(source / plan['bundle_relative'])
                    or checkpoint['smoke']['status'] != 'pass'):
                raise RebuildError('resume_build_attestation')
        # The official API computes its own source and body digests; no marker is invented here.
        marker_command = "const a=await import(process.argv[1]);const t=await Bun.file(process.argv[2]).text();const p=a.parseCodexInstallerArtifact(t);if(!p||p.sourceDigest!==await a.digestCodexInstallerSources(a.bundledWorkspaceSources(p.body)))process.exit(1);console.log(JSON.stringify(p));"
        generated = source / plan['bundle_relative']
        marker = json.loads(run([str(compiler), '--no-install', '-e', marker_command,
                                 (source / plan['official_build_script']).as_uri(), str(generated)], source, environment, 'official_marker'))
        if hashlib.sha256(marker['body'].encode()).hexdigest() != marker['bodyDigest']:
            raise RebuildError('official_body_digest')
        if checkpoint and (marker['sourceDigest'] != checkpoint['source_marker'] or marker['bodyDigest'] != checkpoint['body_digest']):
            raise RebuildError('resume_official_marker')
        artifact = BASE / 'artifact'
        ensure_directory(BASE, artifact)
        atomic_copy(BASE, generated, artifact / 'install-local.mjs')
        atomic_copy(BASE, source / plan['official_license'], artifact / 'UPSTREAM-LICENSE.md')
        smoke = json.loads(run(['node', str(HERE / 'smoke.mjs'), str(source), str(ROOT / 'devtools/node/node_modules/lazycodex-ai')],
                               ROOT, environment, 'actual_bundle_smoke', 90))
        if smoke.get('status') != 'pass':
            raise RebuildError('smoke_result')
        components = []
        text = generated.read_text(encoding='utf-8')
        for name in sorted(set(re.findall(r'^// node_modules/((?:@[^/]+/)?[^/]+)', text, re.MULTILINE))):
            package = source / 'node_modules' / name
            metadata = json.loads((package / 'package.json').read_text(encoding='utf-8'))
            components.append({'type': 'library', 'name': name, 'version': metadata['version'],
                               'purl': 'pkg:npm/' + name.replace('@', '%40') + '@' + metadata['version']})
        if {item['name'] for item in components} != {'@posthog/core', 'posthog-node', 'jsonc-parser', 'zod'}:
            raise RebuildError('unexpected_bundle_components')
        if next(item['version'] for item in components if item['name'] == 'zod') != '4.6.6':
            raise RebuildError('bundled_zod_version')
        receipt = {'schema': 1, 'upstream_version': plan['upstream_version'], 'derivative': plan['derivative'],
                   'source_commit': plan['source_commit'], 'source_sha256': plan['source_sha256'],
                   'source_license_sha256': plan['official_license_sha256'], 'source_code_unchanged': True,
                   'plan_sha256': sha(HERE / 'plan.json'), 'recipe_sha256': sha(Path(__file__)),
                   'smoke_sha256': sha(HERE / 'smoke.mjs'), 'lock_sha256': sha(HERE / 'build-deps/package-lock.json'),
                   'bun_version': plan['bun_version'], 'bun_archive_sha256': plan['runtimes'][sys.platform]['sha256'],
                   'bun_binary_sha256': sha(compiler), 'node_version': node_version, 'platform': sys.platform,
                   'bundle_sha256': sha(generated), 'source_marker': marker['sourceDigest'], 'body_digest': marker['bodyDigest'],
                   'dependency_payload_sha256': payloads, 'components': components, 'smoke': smoke}
        receipt['io_helpers_sha256'] = {name: sha(ROOT / name) for name in (
            'scripts/security/cache_io.py', 'devtools/lazycodex-source-rebuild/source_inputs.py',
            'devtools/lazycodex-source-rebuild/signed_inputs.py')}
        if resume:
            receipt['resumed_compile_attestation_sha256'] = sha(resume)
            receipt['compile_repeated'] = False
    # A ready receipt is published only after isolated HOME cleanup succeeds.
    path = artifact / ('receipt-' + receipt['recipe_sha256'][:16] + '-' + receipt['lock_sha256'][:16] + '.json')
    content = json.dumps(receipt, indent=2, sort_keys=True) + '\n'
    if path.exists() and path.read_text(encoding='utf-8') != content:
        raise RebuildError('changed_receipt')
    atomic_bytes(BASE, path, content.encode('utf-8'))
    return path


if __name__ == '__main__':
    try:
        if len(sys.argv) == 3 and sys.argv[1] == '--finalize-existing':
            proof = build(Path(sys.argv[2]))
        elif len(sys.argv) == 1:
            proof = build()
        else:
            raise RebuildError('arguments')
        print('lazycodex_source_rebuild status=ready receipt=' + proof.name)
    except (RebuildError, subprocess.TimeoutExpired) as failure:
        print('lazycodex_source_rebuild status=failed category=' + str(failure).split()[0])
        raise SystemExit(1) from None
