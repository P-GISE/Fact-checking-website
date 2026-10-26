from pathlib import Path
import importlib.util
import os
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('linux_consumers', ROOT / 'scripts/security/verify_linux_consumers.py')


def module():
    result = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(result)
    return result


def test_consumer_environment_drops_credentials(tmp_path):
    value = module().consumer_environment(tmp_path, {'PATH': 'synthetic-path', 'GITHUB_TOKEN': 'synthetic', 'OPENAI_API_KEY': 'synthetic'})
    assert 'GITHUB_TOKEN' not in value and 'OPENAI_API_KEY' not in value
    assert value['HOME'] == str(tmp_path) and value['CODEX_HOME'] == str(tmp_path / 'codex')


def test_refusal_is_exact_and_does_not_accept_other_failure():
    assert module().pending_refusal(1, b'devtools status=refused category=source_rebuild_pending tool=omniroute\n')
    assert not module().pending_refusal(0, b'devtools status=refused category=source_rebuild_pending tool=omniroute\n')
    assert not module().pending_refusal(1, b'secret or different error')


def test_failure_reports_category_without_raw_output():
    with pytest.raises(RuntimeError, match='consumer_failed:synthetic') as failure:
        module().run_checked('synthetic', ['synthetic'], {}, runner=lambda *a, **kw: subprocess.CompletedProcess(a, 1, b'synthetic raw private output', b'raw'))
    assert 'private' not in str(failure.value)


@pytest.mark.skipif(os.name == 'nt', reason='POSIX interpreter symlink behavior')
def test_fresh_venv_interpreter_symlink_is_not_cache_write_attack(tmp_path):
    venv = tmp_path / 'venv'
    subprocess.run([os.sys.executable, '-m', 'venv', '--without-pip', str(venv)], check=True)
    executable = venv / 'bin/python'
    assert executable.is_symlink()
    result = subprocess.run([str(executable), '-c', 'print("synthetic interpreter")'], capture_output=True, check=True)
    assert result.stdout.strip() == b'synthetic interpreter'
