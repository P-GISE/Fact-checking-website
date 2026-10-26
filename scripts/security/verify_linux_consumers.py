"""POSIX CI orchestration: fixed local consumers, captured logs, no provider calls."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]


def consumer_environment(home: Path, original: dict[str, str]) -> dict[str, str]:
    values = {key: value for key, value in original.items() if key.upper() in ('PATH', 'SYSTEMROOT', 'WINDIR', 'TMP', 'TEMP', 'TMPDIR')}
    values.update(HOME=str(home), USERPROFILE=str(home), CODEX_HOME=str(home / 'codex'),
                  XDG_CACHE_HOME=str(home / 'cache'), XDG_CONFIG_HOME=str(home / 'config'),
                  DO_NOT_TRACK='1', OMO_TELEMETRY_DISABLED='1', HF_HUB_OFFLINE='1',
                  LITELLM_LOCAL_MODEL_COST_MAP='True', HEADROOM_BEACON='off', CODEGRAPH_NO_DOWNLOAD='1')
    return values


def pending_refusal(code: int, output: bytes) -> bool:
    return code == 1 and output.strip() == b'devtools status=refused category=source_rebuild_pending tool=omniroute'


def run_checked(label: str, command: list[str], environment: dict[str, str], *, runner=subprocess.run, timeout=180) -> bytes:
    result = runner(command, cwd=ROOT, env=environment, capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError('consumer_failed:' + label)
    print(json.dumps({'check': label, 'status': 'pass'}), flush=True)
    return result.stdout


def verify() -> None:
    if sys.platform != 'linux' or sys.version_info[:2] != (3, 12):
        raise RuntimeError('platform_requires_linux_python312')
    base = ROOT / '.devtools'
    with TemporaryDirectory(prefix='fact-consumers-') as folder:
        environment = consumer_environment(Path(folder), dict(os.environ))
        for tool, script in (
            ('headroom', 'verify_installed_overlays.py'), ('strix', 'verify_installed_overlays.py'),
            ('ironlaws', 'verify_ironlaws.py'), ('headroom', 'verify_headroom_overlay.py'),
            ('headroom', 'verify_headroom_proxy.py'), ('strix', 'verify_overlay_compat.py'),
            ('ironlaws', 'verify_ironlaws_runtime.py')):
            args = [tool] if script == 'verify_installed_overlays.py' else []
            run_checked(tool + ':' + script, [str(base / tool / 'bin/python'),
                        str(ROOT / 'scripts/security' / script), *args], environment)
        builder = str(base / 'security-builder/bin/python')
        for script in ('verify_bundled_inventory.py', 'verify_codegraph_fixture.py', 'test-inputs.py'):
            run_checked(script, [builder, str(ROOT / 'scripts/security' / script)], environment)
        run_checked('lazy_installed_receipt', [builder, str(ROOT / 'devtools/lazycodex-source-rebuild/verify.py')], environment)
        run_checked('lazy_installed_guarded_cli', ['node', str(ROOT / 'scripts/security/verify_lazy_installed.mjs')], environment)
        refused = subprocess.run([builder, str(ROOT / 'devtools/run.py'), 'omniroute', '--version'],
                                 cwd=ROOT, env=environment, capture_output=True, timeout=20)
        if not pending_refusal(refused.returncode, refused.stdout) or refused.stderr:
            raise RuntimeError('omniroute_pending_boundary')
        print(json.dumps({'check': 'omniroute', 'status': 'pending_refused', 'actual_tool_runs': 0}))


if __name__ == '__main__':
    try:
        verify()
    except (RuntimeError, subprocess.TimeoutExpired, OSError) as failure:
        category = str(failure) if isinstance(failure, RuntimeError) else type(failure).__name__
        print(json.dumps({'status': 'failed', 'category': category}))
        raise SystemExit(1) from None
