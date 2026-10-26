"""Reuse the established transaction scenarios with prebuilt-only mocks, never Docker/network."""
from pathlib import Path
import os
import subprocess
import sys
import re
import tempfile
import unittest


def replace_required(source, old, new, count=None):
    if count not in (None, 1) or source.count(old)!=1:
        raise AssertionError('Required transaction fixture boundary must occur exactly once: '+old[:100])
    return source.replace(old,new,1)


class PrebuiltTransactionTests(unittest.TestCase):
    def test_fixture_replacement_rejects_missing_or_duplicate_boundaries(self):
        self.assertEqual(replace_required('one boundary','boundary','check'),'one check')
        for drift in ('no match','boundary boundary'):
            with self.assertRaises(AssertionError):replace_required(drift,'boundary','check')

    def test_existing_transaction_scenarios_for_import_path(self):
        root=Path(__file__).resolve().parents[1]
        source=(root/'devtools/test-deploy-production.sh').read_text()
        source=replace_required(source,'script="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/deploy-production.sh"',
                              'script="'+str(root/'devtools/deploy-prebuilt.sh').replace('\\','/')+'"')
        source=replace_required(source,'bash -s -- "$requested" < "$script"','bash -s -- "$requested" 12 2 < "$script"')
        source=replace_required(source,'  printf \'factlens-ai\\n\'', '''  mkdir -p "$MOCK_HOME/.factlens-incoming/12-2"
  printf 'synthetic environment\\n' > "$MOCK_HOME/factlens/.env.production"
  printf 'factlens-ai\\n' ''',1)
        source=replace_required(source,'[[ "$1 $2 $3" == "-c %u:%a $MOCK_HOME/factlens-backups" ]]',
            '''if [[ "$*" == "-c %u:%a $MOCK_HOME/.factlens-incoming/12-2" ]]; then printf '%s:700\\n' "$(id -u)"; exit 0; fi
[[ "$1 $2 $3" == "-c %u:%a $MOCK_HOME/factlens-backups" ]]''')
        source=replace_required(source,"  'diff --quiet '*)", '''  "reset --hard $OLD_SHA") [[ $SCENARIO != git-reset-failure ]] || exit 1; rm -f "$MOCK_HOME/merged" ;;
  "show $SHA:devtools/"*) echo '# synthetic helper' ;;
  'diff --quiet '*)''')
        source=replace_required(source,'if [[ $1 == inspect ]]; then', '''if [[ $1 == load ]]; then cat >/dev/null; [[ $SCENARIO != build-failure ]]; exit; fi
if [[ $1 == inspect && $3 == '{{json .Mounts}}' ]]; then
  if [[ $SCENARIO == volume-changed && -f $MOCK_HOME/switched ]]; then echo '[{"Name":"changed-volume"}]'
  else echo '[{"Name":"synthetic-volume"}]'; fi; exit 0
fi
if [[ $1 == inspect ]]; then''')
        source=replace_required(source,'  devtools/production-preflight.py)', '  */prebuilt-preflight.py)')
        source=replace_required(source,'merged,switched,rolled-back', 'merged,imported,switched,rolled-back')
        source=replace_required(source,'if [[ $SCENARIO == stale ]]; then',
            '''if [[ $SCENARIO == stale || $SCENARIO == stale-before-import && -f $MOCK_HOME/merged || $SCENARIO == stale-before-rollout && -f $MOCK_HOME/imported ]]; then''')
        source=replace_required(source,'if [[ $1 == load ]]; then cat >/dev/null;',
                              'if [[ $1 == load ]]; then touch "$MOCK_HOME/imported"; cat >/dev/null;')
        source=replace_required(source,'run_case invalid-sha fail nope', '''run_case stale-before-import fail
assert_absent '^docker load$|^compose up'
run_case stale-before-rollout fail
assert_present '^docker load$'
assert_absent '^compose up'
run_case invalid-sha fail nope''')
        source=replace_required(source,'else touch "$MOCK_HOME/switched"; [[ $SCENARIO != up-failure ]]',
            '''else touch "$MOCK_HOME/switched"; if [[ $SCENARIO == environment-mutated ]]; then printf 'synthetic changed environment\\n' > "$MOCK_HOME/factlens/.env.production"; fi; [[ $SCENARIO != up-failure ]]''')
        source=replace_required(source,'for SCENARIO in up-failure loopback-failure',
                              'for SCENARIO in environment-mutated up-failure loopback-failure')
        source=replace_required(source,'for SCENARIO in rollback-failure rollback-health',
                              'for SCENARIO in git-reset-failure volume-changed rollback-failure rollback-health')
        source=replace_required(source,'$SCENARIO != public-failure && $SCENARIO != rollback-failure',
                              '$SCENARIO != git-reset-failure && $SCENARIO != public-failure && $SCENARIO != rollback-failure')
        source=replace_required(source,'  case_count=$((case_count + 1))', '''  if [[ $expected == fail && $SCENARIO != git-reset-failure && -f $MOCK_HOME/merged ]]; then
    echo "Git state was not restored" >&2; exit 1
  fi
  grep -qx 'synthetic environment' "$MOCK_HOME/factlens/.env.production"
  case_count=$((case_count + 1))''')
        source=replace_required(source,'chmod +x "$fixture/bin/"*', '''cat > "$fixture/bin/gzip" <<'MOCK_GZIP'
#!/usr/bin/env bash
printf 'synthetic image stream'
MOCK_GZIP
chmod +x "$fixture/bin/"*''')
        source=replace_required(source,"assert_present '^compose build --no-cache api worker web$'", "assert_present '^docker load$'")
        source=replace_required(source,"assert_absent 'reset|checkout|prune|down|restore'", "assert_absent 'checkout|prune|down|restore|compose build'")
        bash='C:/Program Files/Git/bin/bash.exe' if os.name=='nt' else 'bash'
        with tempfile.TemporaryDirectory() as directory:
            script=Path(directory)/'test.sh';script.write_text(source)
            result=subprocess.run([bash,str(script),str(Path(directory)/'evidence')],cwd=root,
                                  capture_output=True,text=True,timeout=360 if os.name=='nt' else 120,
                                  env={**os.environ,'PYTHON3':sys.executable.replace('\\','/')})
            logs=sorted((Path(directory)/'evidence').glob('*.output.log'),key=lambda path:path.stat().st_mtime)
            detail=(logs[-1].name+'\n'+logs[-1].read_text()[-2500:]
                    +'\n'+logs[-1].with_name(logs[-1].name.replace('.output.log','.commands.log')).read_text()[-2500:]) if logs else 'No scenario reached'
            self.assertEqual(result.returncode,0,result.stdout+result.stderr+detail)
            count=re.search(r'PASS: ([0-9]+) mock scenarios',result.stdout)
            self.assertIsNotNone(count)
            self.assertGreaterEqual(int(count.group(1)),35)
            print('Prebuilt import transaction scenarios passed: '+count.group(1))


if __name__=='__main__':unittest.main()
