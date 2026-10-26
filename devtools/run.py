#!/usr/bin/env python3
"""Launch only verified repository-local development tools."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '.devtools'


def python_for(tool: str) -> Path:
    return BASE / tool / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')


def launch(arguments: list[str]) -> int:
    if not arguments:
        print('Usage: python devtools/run.py {headroom|strix|iron-laws|codegraph|omniroute|lazycodex} [args]')
        return 2
    tool, *options = arguments
    if BASE.is_symlink():
        print('devtools status=refused category=owned_directory')
        return 1
    if tool in ('headroom', 'strix'):
        interpreter = python_for(tool)
        if not interpreter.is_file():
            print('devtools status=refused category=not_installed')
            return 1
        verification = subprocess.run([str(interpreter), str(ROOT / 'scripts/security/verify_installed_overlays.py'), tool], cwd=ROOT, stdout=sys.stderr)
        if verification.returncode:
            return 1
        executable = interpreter.parent / (tool + '.exe' if os.name == 'nt' else tool)
        return subprocess.call([str(executable), *options], cwd=ROOT)
    if tool == 'iron-laws':
        interpreter = python_for('ironlaws')
        if not interpreter.is_file():
            print('devtools status=refused category=not_installed')
            return 1
        verification = subprocess.run([str(interpreter), str(ROOT / 'scripts/security/verify_ironlaws.py')], cwd=ROOT, stdout=sys.stderr)
        if verification.returncode:
            return 1
        return subprocess.call([str(interpreter.parent / ('iron-laws.exe' if os.name == 'nt' else 'iron-laws')), *options], cwd=ROOT)
    if tool == 'codegraph':
        environment = dict(os.environ, CODEGRAPH_NO_DOWNLOAD='1')
        shim = ROOT / 'devtools/node/node_modules/@colbymchenry/codegraph/npm-shim.js'
        return subprocess.call(['node', str(shim), *options], cwd=ROOT, env=environment)
    if tool == 'lazycodex':
        interpreter = python_for('security-builder')
        verification = subprocess.run([str(interpreter), str(ROOT / 'devtools/lazycodex-source-rebuild/verify.py')], cwd=ROOT)
        if verification.returncode:
            return 1
        wrapper = ROOT / 'devtools/node/node_modules/lazycodex-ai/packages/omo-codex/scripts/install-local.mjs'
        return subprocess.call(['node', str(wrapper), *options], cwd=ROOT)
    if tool == 'omniroute':
        # Neither an old precompiled bundle nor a version string establishes compatibility.
        print('devtools status=refused category=source_rebuild_pending tool=' + tool)
        return 1
    print('devtools status=refused category=unknown_tool')
    return 2


if __name__ == '__main__':
    raise SystemExit(launch(sys.argv[1:]))
