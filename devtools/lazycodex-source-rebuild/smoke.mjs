import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { mkdtemp, mkdir, readFile, readdir, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const plan = JSON.parse(await readFile(join(here, 'plan.json'), 'utf8'));
const [source, installed] = process.argv.slice(2).map(path => resolve(path));
const base = dirname(source);
const finalBundle = await readFile(join(source, plan.bundle_relative));
const originalCandidate = await readFile(join(installed, plan.bundle_relative));
const digest = bytes => createHash('sha256').update(bytes).digest('hex');
const baseline = join(base, 'verified-original-installer.mjs');
let original;
if (digest(originalCandidate) === plan.original_npm_bundle_sha256) {
  original = originalCandidate;
  await writeFile(baseline, original, { flag: 'wx' }).catch(async error => {
    if (error.code !== 'EEXIST') throw error;
    assert.equal(digest(await readFile(baseline)), plan.original_npm_bundle_sha256);
  });
} else {
  original = await readFile(baseline);
}
assert.equal(digest(original), plan.original_npm_bundle_sha256);
assert.equal(digest(await readFile(join(source, plan.wrapper_relative))), plan.wrapper_sha256);
const temporary = await mkdtemp(join(tmpdir(), 'pgise-lazy-installer-smoke-'));
const environment = Object.fromEntries(Object.entries(process.env).filter(([name]) =>
  ['PATH', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP'].includes(name.toUpperCase())));
const home = join(temporary, 'home');
await mkdir(home);
Object.assign(environment, { HOME: home, USERPROFILE: home, CODEX_HOME: join(home, 'codex'),
  DO_NOT_TRACK: '1', OMO_TELEMETRY_DISABLED: '1' });
const guard = join(temporary, 'no-network-no-spawn.mjs');
await writeFile(guard, `
import http from 'node:http'; import https from 'node:https'; import net from 'node:net';
import dns from 'node:dns'; import child from 'node:child_process';
import {syncBuiltinESMExports} from 'node:module';
let network=0,spawn=0;
const denyNetwork=()=>{network++;throw Error('synthetic_guard_network_refused')};
const denySpawn=()=>{spawn++;throw Error('synthetic_guard_spawn_refused')};
globalThis.fetch=denyNetwork;
http.request=http.get=https.request=https.get=net.connect=net.createConnection=denyNetwork;
net.Socket.prototype.connect=denyNetwork; dns.lookup=dns.resolve=denyNetwork;
for(const name of ['spawn','spawnSync','exec','execSync','execFile','execFileSync','fork'])child[name]=denySpawn;
syncBuiltinESMExports();
process.on('exit',()=>{console.log('PGISE_GUARD '+JSON.stringify({network,spawn}));if(network||spawn)process.exitCode=97;});
`);
function execute(path, args = []) {
  const result = spawnSync(process.execPath, ['--max-old-space-size=128', '--import', pathToFileURL(guard).href, path, ...args],
    { cwd: temporary, env: environment, encoding: 'utf8', timeout: 20000, maxBuffer: 1024 * 1024, windowsHide: true });
  assert.equal(result.error, undefined, 'isolated_process_error');
  assert.equal(result.status, 0, 'isolated_process_failed');
  const lines = result.stdout.trim().split('\n');
  const proof = lines.filter(line => line.startsWith('PGISE_GUARD '));
  assert.equal(proof.length, 1);
  assert.deepEqual(JSON.parse(proof[0].slice('PGISE_GUARD '.length)), { network: 0, spawn: 0 });
  return lines.filter(line => !line.startsWith('PGISE_GUARD ')).join('\n');
}
try {
  const wrapper = join(source, plan.wrapper_relative);
  assert.match(execute(wrapper, ['--version']), /lazycodex-ai 5\.1\.33/);
  assert.match(execute(wrapper, ['--help']), /lazycodex/i);
  const project = join(temporary, 'synthetic-project');
  await mkdir(project);
  assert.match(execute(wrapper, ['update', '--repo-root=' + project, '--dry-run']), /install --repo-root=/);
  assert.deepEqual(await readdir(home), []);
  assert.deepEqual(await readdir(project), []);
  const counts = {};
  for (const [phase, bytes] of [['before', original], ['after', finalBundle]]) {
    const text = bytes.toString('utf8');
    assert.match(text, /^function array\(element, params\)/m);
    assert.match(text, /^function string2\(params\)/m);
    // Test-only exposure calls the implementation already inside each exact bundle prefix.
    // The official generated artifact and its source/body marker are not modified.
    const probe = join(temporary, phase + '.mjs');
    const appended = Buffer.from('\nconst probe=array(string2()).max(1).safeParse(Array(1000).fill(0));console.log("PGISE_ARRAY "+probe.error.issues.length);\n');
    await writeFile(probe, Buffer.concat([bytes, appended]));
    assert.equal(digest((await readFile(probe)).subarray(0, bytes.length)), digest(bytes));
    const match = /PGISE_ARRAY (\d+)/.exec(execute(probe));
    assert.notEqual(match, null);
    counts[phase] = Number(match[1]);
  }
  assert.equal(counts.before, 1001);
  assert.equal(counts.after, 1);
  console.log(JSON.stringify({ status: 'pass', cli_version: true, cli_help: true, synthetic_update_dry_run: true,
    home_files_written: 0, project_files_written: 0, network_api_attempts: 0, child_spawn_attempts: 0,
    bundled_array_issues_before: counts.before, bundled_array_issues_after: counts.after,
    original_bundle_sha256: digest(original), tested_bundle_sha256: digest(finalBundle) }));
} finally {
  assert.equal(dirname(temporary), tmpdir());
  await rm(temporary, { recursive: true, force: true });
}
