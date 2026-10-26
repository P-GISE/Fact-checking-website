"""Reuse the established transaction scenarios with prebuilt-only mocks, never Docker/network."""
from pathlib import Path
import os
import subprocess
import sys
import re
import tempfile
import unittest


class PrebuiltTransactionTests(unittest.TestCase):
    def test_existing_transaction_scenarios_for_import_path(self):
        root=Path(__file__).resolve().parents[1]
        source=(root/'devtools/test-deploy-production.sh').read_text()
        source=source.replace('script="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/deploy-production.sh"',
                              'script="'+str(root/'devtools/deploy-prebuilt.sh').replace('\\','/')+'"')
        source=source.replace('bash -s -- "$requested" < "$script"','bash -s -- "$requested" 12 2 < "$script"')
        source=source.replace('  printf \'factlens-ai\\n\'', '''  mkdir -p "$MOCK_HOME/.factlens-incoming/12-2"
  printf 'synthetic environment\\n' > "$MOCK_HOME/factlens/.env.production"
  printf 'factlens-ai\\n' ''',1)
        source=source.replace('[[ "$1 $2 $3" == "-c %u:%a $MOCK_HOME/factlens-backups" ]]',
            '''if [[ "$*" == "-c %u:%a $MOCK_HOME/.factlens-incoming/12-2" ]]; then printf '%s:700\\n' "$(id -u)"; exit 0; fi
[[ "$1 $2 $3" == "-c %u:%a $MOCK_HOME/factlens-backups" ]]''')
        source=source.replace("  'diff --quiet '*)", '''  "reset --hard $OLD_SHA") rm -f "$MOCK_HOME/merged" ;;
  "show $SHA:devtools/"*) echo '# synthetic helper' ;;
  'diff --quiet '*)''')
        source=source.replace('if [[ $1 == inspect ]]; then', '''if [[ $1 == load ]]; then cat >/dev/null; [[ $SCENARIO != build-failure ]]; exit; fi
if [[ $1 == inspect && $3 == '{{json .Mounts}}' ]]; then echo '[{"Name":"synthetic-volume"}]'; exit 0; fi
if [[ $1 == inspect ]]; then''')
        source=source.replace('  devtools/production-preflight.py)', '  */prebuilt-preflight.py)')
        source=source.replace('chmod +x "$fixture/bin/"*', '''cat > "$fixture/bin/gzip" <<'MOCK_GZIP'
#!/usr/bin/env bash
printf 'synthetic image stream'
MOCK_GZIP
chmod +x "$fixture/bin/"*''')
        source=source.replace("assert_present '^compose build --no-cache api worker web$'", "assert_present '^docker load$'")
        source=source.replace("assert_absent 'reset|checkout|prune|down|restore'", "assert_absent 'checkout|prune|down|restore|compose build'")
        bash='C:/Program Files/Git/bin/bash.exe' if os.name=='nt' else 'bash'
        with tempfile.TemporaryDirectory() as directory:
            script=Path(directory)/'test.sh';script.write_text(source)
            result=subprocess.run([bash,str(script),str(Path(directory)/'evidence')],cwd=root,
                                  capture_output=True,text=True,timeout=240,
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
