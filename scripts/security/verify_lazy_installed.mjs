import assert from 'node:assert/strict';
import { mkdtemp, mkdir, writeFile, readdir, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { spawnSync } from 'node:child_process';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const wrapper = join(root, 'devtools/node/node_modules/lazycodex-ai/packages/omo-codex/scripts/install-local.mjs');
const temporary = await mkdtemp(join(tmpdir(), 'fact-installed-lazy-'));
try {
  const home = join(temporary, 'home');
  const project = join(temporary, 'synthetic-project');
  await mkdir(home); await mkdir(project);
  const guard = join(temporary, 'guard.mjs');
  await writeFile(guard, `
import http from 'node:http'; import https from 'node:https'; import net from 'node:net';
import dns from 'node:dns'; import child from 'node:child_process';
import {syncBuiltinESMExports} from 'node:module';
let network=0,spawn=0;
const denyNetwork=()=>{network++;throw Error('network_refused')};
const denySpawn=()=>{spawn++;throw Error('spawn_refused')};
globalThis.fetch=denyNetwork;
http.request=http.get=https.request=https.get=net.connect=net.createConnection=denyNetwork;
net.Socket.prototype.connect=denyNetwork; dns.lookup=dns.resolve=denyNetwork;
for(const name of ['spawn','spawnSync','exec','execSync','execFile','execFileSync','fork'])child[name]=denySpawn;
syncBuiltinESMExports();
process.on('exit',()=>{console.log('GUARD '+JSON.stringify({network,spawn}));if(network||spawn)process.exitCode=97;});
`);
  const environment = Object.fromEntries(Object.entries(process.env).filter(([key]) =>
    ['PATH', 'SYSTEMROOT', 'WINDIR', 'TMP', 'TEMP', 'TMPDIR'].includes(key.toUpperCase())));
  Object.assign(environment, { HOME: home, USERPROFILE: home, CODEX_HOME: join(home, 'codex'),
    DO_NOT_TRACK: '1', OMO_TELEMETRY_DISABLED: '1' });
  for (const [args, pattern] of [
    [['--version'], /lazycodex-ai 5\.1\.33/], [['--help'], /lazycodex/i],
    [['update', '--repo-root=' + project, '--dry-run'], /install --repo-root=/],
  ]) {
    const result = spawnSync(process.execPath, ['--max-old-space-size=128', '--import', pathToFileURL(guard).href, wrapper, ...args],
      { cwd: temporary, env: environment, encoding: 'utf8', timeout: 20000, maxBuffer: 1024 * 1024, windowsHide: true });
    assert.equal(result.error, undefined, 'guarded_process_error');
    assert.equal(result.status, 0, 'guarded_process_exit');
    assert.match(result.stdout, pattern);
    const guards = result.stdout.split('\n').filter(line => line.startsWith('GUARD '));
    assert.equal(guards.length, 1);
    assert.deepEqual(JSON.parse(guards[0].slice(6)), { network: 0, spawn: 0 });
  }
  assert.deepEqual(await readdir(home), []);
  assert.deepEqual(await readdir(project), []);
  console.log(JSON.stringify({ status: 'pass', installed_cli_checks: 3, network_api_attempts: 0,
    child_spawn_attempts: 0, home_writes: 0, project_writes: 0 }));
} finally {
  assert.equal(dirname(temporary), tmpdir());
  await rm(temporary, { recursive: true, force: true });
}
