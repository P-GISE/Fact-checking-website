"""Exercise one synthetic proxy request through loopback with no provider credentials."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import socket
import signal
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from urllib.error import URLError
from urllib.request import Request, urlopen


class SyntheticUpstream(BaseHTTPRequestHandler):
    requests_seen = 0

    def do_POST(self) -> None:
        body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', '0'))))
        assert self.path == '/v1/chat/completions' and body['model'] == 'synthetic-fixture'
        SyntheticUpstream.requests_seen += 1
        data = json.dumps({'id': 'synthetic-1', 'object': 'chat.completion', 'created': 0, 'model': 'synthetic-fixture',
                           'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': 'synthetic-reply'}, 'finish_reason': 'stop'}],
                           'usage': {'prompt_tokens': 5, 'completion_tokens': 2, 'total_tokens': 7}}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *_arguments: object) -> None:
        pass


def verify(folder: str) -> None:
    environment = {name: value for name, value in os.environ.items() if name.upper() in ('SYSTEMROOT', 'WINDIR', 'PATH', 'TEMP', 'TMP')}
    environment.update({'HOME': folder, 'USERPROFILE': folder, 'HEADROOM_CONFIG_DIR': folder,
                        'HEADROOM_WORKSPACE_DIR': folder, 'XDG_CACHE_HOME': folder, 'DO_NOT_TRACK': '1',
                        'LITELLM_LOCAL_MODEL_COST_MAP': 'True', 'HEADROOM_BEACON': 'off', 'HEADROOM_KOMPRESS_WARMUP': '0',
                        'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1'})
    with socket.socket() as candidate:
        candidate.bind(('127.0.0.1', 0))
        port = candidate.getsockname()[1]
    upstream = ThreadingHTTPServer(('127.0.0.1', 0), SyntheticUpstream)
    wrapper = Path(__file__).resolve().parents[2] / 'devtools/run.py'
    command = [sys.executable, str(wrapper), 'headroom', 'proxy', '--host', '127.0.0.1', '--port', str(port),
               '--stateless', '--lossless', '--disable-kompress', '--disable-kompress-fallback',
               '--no-subscription-tracking', '--no-telemetry', '--openai-api-url',
               'http://127.0.0.1:' + str(upstream.server_port) + '/v1']
    process = subprocess.Popen(command, cwd=folder, env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
    with ThreadPoolExecutor(max_workers=2) as executor:
        server_future = executor.submit(upstream.serve_forever)
        # Consume output without persisting or displaying arbitrary service log content.
        output_future = executor.submit(process.communicate)
        try:
            ready = False
            for _attempt in range(80):
                if process.poll() is not None:
                    raise AssertionError('proxy_start_failed')
                try:
                    with urlopen('http://127.0.0.1:' + str(port) + '/health', timeout=1) as response:
                        ready = json.load(response).get('ready') is True
                except (URLError, OSError):
                    pass
                if ready:
                    break
                time.sleep(0.5)
            assert ready, 'proxy_readiness_timeout'
            request = Request('http://127.0.0.1:' + str(port) + '/v1/chat/completions',
                              data=json.dumps({'model': 'synthetic-fixture', 'messages': [{'role': 'user', 'content': 'synthetic hello'}]}).encode(),
                              headers={'Content-Type': 'application/json'})
            with urlopen(request, timeout=15) as response:
                result = json.load(response)
            assert result['choices'][0]['message']['content'] == 'synthetic-reply'
            assert SyntheticUpstream.requests_seen == 1
            print('headroom_proxy status=pass upstream_requests=1 provider_calls=0')
        finally:
            if process.poll() is None:
                if os.name == 'nt':
                    subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True, timeout=10)
                else:
                    os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
            upstream.shutdown()
            upstream.server_close()
            output_future.result(timeout=5)
            server_future.result(timeout=5)


if __name__ == '__main__':
    with TemporaryDirectory(prefix='pgise-headroom-proxy-') as folder:
        verify(folder)
