"""Compile strict universal locks including both verified derived platform wheels."""
from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import sys

from scripts.security.python_overlays import OverlayError, SPECS, build_all, digest_file


def include_platform_hashes(text: str, wheels: list[dict[str, str]]) -> str:
    for spec in SPECS:
        rows = [row for row in wheels if row['name'] == spec.name and row['version'] == spec.local_version]
        if not rows:
            continue
        hashes = sorted({row['sha256'] for row in rows})
        if len(rows) != 2 or len(hashes) != 2 or any(not re.fullmatch(r'[0-9a-f]{64}', value) for value in hashes):
            raise OverlayError('lock_platform_hashes')
        pattern = re.compile(r'^' + re.escape(spec.name + '==' + spec.local_version) + r'(?: \\\n(?:    --hash=sha256:[0-9a-f]{64})(?: \\\n    --hash=sha256:[0-9a-f]{64})*)?$', re.MULTILINE)
        replacement = spec.name + '==' + spec.local_version + ' \\\n' + ' \\\n'.join('    --hash=sha256:' + value for value in hashes)
        text, count = pattern.subn(lambda _match: replacement, text)
        if count != 1:
            raise OverlayError('lock_package_count')
    return text


def main(root: Path) -> None:
    receipt_path = build_all(root)
    receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
    wheels = receipt['wheels']
    for row in wheels:
        if digest_file(receipt_path.parent / row['filename']) != row['sha256']:
            raise OverlayError('lock_wheel_digest')
    for tool in ('headroom', 'strix'):
        target = root / 'devtools' / (tool + '.lock.txt')
        subprocess.run(['uv', 'pip', 'compile', '--no-config', '--index-url', 'https://pypi.org/simple',
                        '--find-links', str(receipt_path.parent), '--python', sys.executable,
                        '--custom-compile-command', 'python -m scripts.security.compile_overlay_locks',
                        '--python-version', '3.12', '--universal', '--generate-hashes', '--upgrade',
                        str(root / 'devtools' / (tool + '-requirements.txt')), '-o', str(target)], check=True,
                       stdout=subprocess.DEVNULL, cwd=root)
        selected = wheels if tool == 'strix' else [row for row in wheels if row['name'] == 'litellm']
        result = include_platform_hashes(target.read_text(encoding='utf-8'), selected)
        target.write_text(result, encoding='utf-8', newline='\n')
    print('python_overlay_locks status=ready')


if __name__ == '__main__':
    main(Path(__file__).resolve().parents[2])
