"""Run the real CLI/MCP against isolated synthetic safe and unsafe files."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def verify(folder: str) -> None:
    target = Path(folder)
    (target / 'safe').mkdir()
    (target / 'unsafe').mkdir()
    (target / 'safe/app.py').write_text('def add(left: int, right: int) -> int:\n    return left + right\n', encoding='utf-8')
    (target / 'unsafe/app.py').write_text('import hashlib\n\ndef digest_password(value: str) -> str:\n    return hashlib.md5(value.encode()).hexdigest()\n', encoding='utf-8')
    environment = {name: value for name, value in os.environ.items() if name.upper() in ('SYSTEMROOT', 'WINDIR', 'PATH', 'TEMP', 'TMP')}
    environment.update({'HOME': folder, 'USERPROFILE': folder, 'XDG_CONFIG_HOME': folder, 'DO_NOT_TRACK': '1'})
    wrapper = Path(__file__).resolve().parents[2] / 'devtools/run.py'
    results = {}
    for kind, expected in (('safe', 0), ('unsafe', 1)):
        result = subprocess.run([sys.executable, str(wrapper), 'iron-laws', 'check', str(target / kind)],
                                cwd=folder, env=environment, capture_output=True, timeout=60)
        assert result.returncode == expected, (kind, result.returncode)
        results[kind] = result.returncode
    params = StdioServerParameters(command=sys.executable, args=[str(wrapper), 'iron-laws', 'mcp', '--root', folder], env=environment, cwd=folder)
    with anyio.fail_after(90):
        async with stdio_client(params) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                tools = await session.list_tools()
                assert {'check', 'explain', 'verify_patch'} <= {item.name for item in tools.tools}
                for kind, passed in (('safe', True), ('unsafe', False)):
                    response = await session.call_tool('check', {'path': kind})
                    assert not response.isError
                    payload = response.structuredContent or json.loads(response.content[0].text)
                    assert payload['passed'] is passed and payload['files_scanned'] == 1
                    if not passed:
                        assert payload['findings_total'] >= 1
                rejected = await session.call_tool('check', {'path': '..'})
                assert rejected.isError
    print(json.dumps({'ironlaws_cli': results, 'mcp': 'pass', 'outside_root': 'refused', 'fixture': 'synthetic'}))


if __name__ == '__main__':
    with TemporaryDirectory(prefix='pgise-ironlaws-runtime-') as folder:
        anyio.run(verify, folder)
