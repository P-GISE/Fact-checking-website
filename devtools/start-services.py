#!/usr/bin/env python3
"""Start optional local development gateways; never replace existing listeners."""
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request

BASE = Path('/workspace/.devtools')
ROOT = Path(__file__).resolve().parent.parent

def probe(url):
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            return json.load(response)
    except (OSError, ValueError):
        return None

def start(name, command, url, ready, extra_env):
    data = probe(url)
    if data is not None:
        if not ready(data):
            raise SystemExit(f'{name}: existing endpoint is not ready; inspect before restarting')
        print(f'{name}: already ready')
        return
    env = dict(os.environ, **extra_env)
    with (BASE / 'logs' / f'{name}.log').open('a') as output:
        process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=output,
                                   stderr=subprocess.STDOUT, start_new_session=True)
    (BASE / 'state' / f'{name}.pid').write_text(str(process.pid) + '\n')
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise SystemExit(f'{name}: exited {process.returncode}; inspect {BASE}/logs/{name}.log')
        data = probe(url)
        if data is not None and ready(data):
            print(f'{name}: ready')
            return
        time.sleep(1)
    raise SystemExit(f'{name}: readiness timeout; inspect {BASE}/logs/{name}.log')

for directory in ['logs', 'state', 'state/omniroute', 'config', 'cache']:
    (BASE / directory).mkdir(parents=True, exist_ok=True)
common = {'XDG_CONFIG_HOME': str(BASE / 'config'), 'XDG_CACHE_HOME': str(BASE / 'cache'),
          'HF_HOME': str(BASE / 'huggingface'), 'HEADROOM_BEACON': 'off', 'DO_NOT_TRACK': '1'}
start('omniroute', [str(BASE / 'node/node_modules/.bin/omniroute'), 'serve', '--port', '20128',
                   '--no-open', '--no-tray', '--log'],
      'http://127.0.0.1:20128/api/health', lambda d: d.get('status') == 'ok',
      dict(common, DATA_DIR=str(BASE / 'state/omniroute'), HOSTNAME='127.0.0.1', NO_UPDATE_NOTIFIER='1'))
start('headroom', [str(BASE / 'python/bin/headroom'), 'proxy', '--host', '127.0.0.1', '--port', '8787',
                  '--stateless', '--lossless', '--disable-kompress', '--disable-kompress-fallback',
                  '--no-subscription-tracking', '--no-telemetry',
                  '--anthropic-api-url', 'http://127.0.0.1:20128',
                  '--openai-api-url', 'http://127.0.0.1:20128/v1'],
      'http://127.0.0.1:8787/health', lambda d: d.get('ready') is True,
      dict(common, HEADROOM_KOMPRESS_WARMUP='0'))
