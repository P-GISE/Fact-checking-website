"""Probe Headroom's real stdio MCP using synthetic content and no model credentials."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def verify(folder: str) -> None:
    environment = {name: value for name, value in os.environ.items() if name.upper() in ('SYSTEMROOT', 'WINDIR', 'PATH', 'TEMP', 'TMP')}
    environment.update({'HOME': folder, 'USERPROFILE': folder, 'HEADROOM_CONFIG_DIR': folder,
                        'HEADROOM_WORKSPACE_DIR': folder, 'XDG_CACHE_HOME': folder, 'DO_NOT_TRACK': '1',
                        'LITELLM_LOCAL_MODEL_COST_MAP': 'True'})
    wrapper = Path(__file__).resolve().parents[2] / 'devtools/run.py'
    params = StdioServerParameters(command=sys.executable, args=[str(wrapper), 'headroom', 'mcp', 'serve'], env=environment, cwd=folder)
    with anyio.fail_after(90):
        async with stdio_client(params) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                tools = await session.list_tools()
                assert {'headroom_compress', 'headroom_retrieve', 'headroom_stats'} <= {tool.name for tool in tools.tools}
                content = json.dumps([{'id': index, 'status': 'ok', 'message': 'synthetic routine request'} for index in range(250)]
                                     + [{'id': 250, 'status': 'FATAL', 'message': 'synthetic failure marker'}])
                compressed = await session.call_tool('headroom_compress', {'content': content})
                assert not compressed.isError
                payload = json.loads(compressed.content[0].text)
                assert payload['compressed_tokens'] < payload['original_tokens'] and 'FATAL' in payload['compressed']
                retrieved = await session.call_tool('headroom_retrieve', {'hash': payload['hash']})
                assert not retrieved.isError and json.loads(retrieved.content[0].text)['original_content'] == content
                print('headroom_mcp status=pass synthetic_roundtrip=exact')


if __name__ == '__main__':
    with TemporaryDirectory(prefix='pgise-headroom-overlay-mcp-') as temporary:
        anyio.run(verify, temporary)
