#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
project_root="$PWD"
tool_root="$project_root/.devtools"
if [[ -L "$tool_root" ]]; then printf 'Refusing symbolic tool root\n' >&2; exit 1; fi
export UV_CACHE_DIR="$tool_root/cache/uv"
mkdir -p "$tool_root"/{sources,bin,logs,config,state/omniroute,cache}
python3 - <<'PY'
from pathlib import Path
import subprocess,json
base=Path.cwd()/'.devtools/sources'
owners={'pm-skills':'phuryn','ponytail':'DietrichGebert','superpowers':'obra','iron-laws':'JinHo-von-Choi','lazycodex':'code-yeongyu','strix':'usestrix'}
for name,sha in json.loads(Path('devtools/sources.lock.json').read_text()).items():
 p=base/name
 if not p.exists():
  subprocess.run(['git','clone','--filter=blob:none','--no-checkout',f'https://github.com/{owners[name]}/{name}.git',str(p)],check=True)
  subprocess.run(['git','-C',str(p),'checkout','--detach',sha],check=True)
 actual=subprocess.check_output(['git','-C',str(p),'rev-parse','HEAD'],text=True).strip()
 if actual!=sha: raise SystemExit(f'{name}: source pin mismatch; preserve local state and inspect before updating')
 if subprocess.check_output(['git','-C',str(p),'status','--porcelain'],text=True): raise SystemExit(f'{name}: dirty source cache; preserve and inspect')
PY
venv_python() {
  if [[ -x "$tool_root/$1/bin/python" ]]; then printf '%s' "$tool_root/$1/bin/python";
  elif [[ -x "$tool_root/$1/Scripts/python.exe" ]]; then printf '%s' "$tool_root/$1/Scripts/python.exe";
  else return 1; fi
}
for tool in security-builder headroom strix ironlaws; do
  if ! venv_python "$tool" >/dev/null; then uv venv --python 3.12 "$tool_root/$tool"; fi
done
builder_python="$(venv_python security-builder)"
uv pip install --python "$builder_python" --require-hashes -r devtools/security-builder.lock.txt
"$builder_python" -m scripts.security.python_overlays
"$builder_python" -m scripts.security.build_ironlaws
for tool in headroom strix ironlaws; do
  tool_python="$(venv_python "$tool")"
  uv pip install --python "$tool_python" --find-links "$tool_root/patched-wheels" --require-hashes -r "devtools/$tool.lock.txt"
  uv pip check --python "$tool_python"
done
"$(venv_python headroom)" scripts/security/verify_installed_overlays.py headroom
"$(venv_python strix)" scripts/security/verify_installed_overlays.py strix
"$(venv_python ironlaws)" scripts/security/verify_ironlaws.py
npm ci --prefix devtools/node --cache "$tool_root/npm-cache" --no-audit --no-fund
"$builder_python" devtools/lazycodex-source-rebuild/rebuild.py
"$builder_python" devtools/lazycodex-source-rebuild/install.py
for tool in headroom strix iron-laws codegraph omniroute lazycodex; do
  printf '#!/usr/bin/env bash\nexec %q %q %q "$@"\n' "$builder_python" "$project_root/devtools/run.py" "$tool" > "$tool_root/bin/$tool"
  chmod 700 "$tool_root/bin/$tool"
done
python3 - <<'PY'
from pathlib import Path
base=Path.cwd()/'.devtools/sources'; skills=Path('.agents/skills'); skills.mkdir(parents=True,exist_ok=True)
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
printf 'Isolated development tools installed. OmniRoute/LazyCodex remain blocked until source rebuild verification.\n'
printf 'CodeGraph indexing is optional: codegraph init --yes PATH\n'
