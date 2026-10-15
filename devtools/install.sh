#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
project_root="$PWD"
tool_root=/workspace/.devtools
mkdir -p "$tool_root"/{sources,bin,logs,config,state/omniroute,cache}
python3 - <<'PY'
from pathlib import Path
import subprocess,json
base=Path('/workspace/.devtools/sources')
owners={'pm-skills':'phuryn','ponytail':'DietrichGebert','superpowers':'obra','iron-laws':'JinHo-von-Choi','lazycodex':'code-yeongyu','strix':'usestrix'}
for name,sha in json.loads(Path('devtools/sources.lock.json').read_text()).items():
 p=base/name
 if not p.exists():
  subprocess.run(['git','clone','--filter=blob:none','--no-checkout',f'https://github.com/{owners[name]}/{name}.git',str(p)],check=True)
  subprocess.run(['git','-C',str(p),'checkout','--detach',sha],check=True)
 actual=subprocess.check_output(['git','-C',str(p),'rev-parse','HEAD'],text=True).strip()
 if actual!=sha: raise SystemExit(f'{name}: source pin mismatch; preserve local state and inspect before updating')
PY
if [ ! -x "$tool_root/python/bin/python" ]; then
  UV_CACHE_DIR="$tool_root/uv-cache" uv venv "$tool_root/python"
fi
UV_CACHE_DIR="$tool_root/uv-cache" uv pip install --python "$tool_root/python/bin/python" \
  'strix-agent==1.7.0' 'headroom-ai[proxy]==0.41.0' "$tool_root/sources/iron-laws[mcp]"
UV_CACHE_DIR="$tool_root/uv-cache" uv pip check --python "$tool_root/python/bin/python"
npm install --prefix "$tool_root/node" --cache "$tool_root/npm-cache" --save-exact --no-audit --no-fund \
  '@colbymchenry/codegraph@1.6.2' 'omniroute@3.8.51' 'lazycodex-ai@5.1.33'
python3 - <<'PY'
from pathlib import Path
base=Path('/workspace/.devtools/sources'); skills=Path('.agents/skills'); skills.mkdir(parents=True,exist_ok=True)
patterns={'pm-skills':'*/skills/*/SKILL.md','ponytail':'skills/*/SKILL.md','superpowers':'skills/*/SKILL.md','lazycodex':'plugins/omo/skills/*/SKILL.md','strix':'skills/*/SKILL.md'}
for name,pattern in patterns.items():
 for src in sorted((base/name).glob(pattern)):
  dst=skills/f'{name}-{src.parent.name}'
  if dst.is_symlink() and dst.resolve()==src.parent.resolve(): continue
  if dst.exists() or dst.is_symlink(): raise SystemExit(f'Preserving conflicting skill: {dst}')
  dst.symlink_to(src.parent)
print('Project skill links:',len(list(skills.iterdir())))
PY
source devtools/activate.sh
codegraph init --yes "$project_root"
strix --version
headroom --version
