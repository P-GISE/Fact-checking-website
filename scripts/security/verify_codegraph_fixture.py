"""Index only a disposable synthetic project, never the repository itself."""
from pathlib import Path
import os
import subprocess
from tempfile import TemporaryDirectory

root = Path(__file__).resolve().parents[2]
shim = root / 'devtools/node/node_modules/@colbymchenry/codegraph/npm-shim.js'
with TemporaryDirectory(prefix='pgise-fact-codegraph-') as folder:
    project = Path(folder) / 'project'
    project.mkdir()
    (project / 'sample.py').write_text('def synthetic_add(left: int, right: int) -> int:\n    return left + right\n', encoding='utf-8')
    environment = {key: value for key, value in os.environ.items() if key.upper() in ('PATH', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP')}
    environment.update(HOME=folder, USERPROFILE=folder, CODEGRAPH_NO_DOWNLOAD='1', DO_NOT_TRACK='1')
    initialized = subprocess.run(['node', str(shim), 'init', '--yes', str(project)], env=environment, cwd=project, capture_output=True, timeout=90)
    queried = subprocess.run(['node', str(shim), 'query', 'synthetic_add', '--path', str(project)], env=environment, cwd=project, capture_output=True, timeout=60)
    assert initialized.returncode == queried.returncode == 0 and b'synthetic_add' in queried.stdout
print('codegraph status=pass indexed_scope=synthetic_temp_only')
