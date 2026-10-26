import assert from 'node:assert/strict';
import { spawn, spawnSync } from 'node:child_process';
import { EventEmitter } from 'node:events';
import { createServer } from 'node:net';
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { setTimeout as delay } from 'node:timers/promises';
import { isolatedEnv, verifyReceipt } from './rebuild.mjs';
import { guardProcess } from './process-guard.mjs';
import { confirmLoopbackRefused } from './tcp-refusal.mjs';
import { linuxProfile,assertPinnedNode } from './platform-profile.mjs';
import { ownedLinuxAdapter,confirmReaped } from './linux-processes.mjs';
import { verifyGuardAttestation } from './guard-attestation.mjs';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../../..');
const cache = join(root, '.tools/omniroute-security-build');
const source = join(cache, 'source');
const receiptPath = join(cache, 'receipt.json');
const cli = join(source, 'bin/omniroute.mjs');
const env = { ...isolatedEnv(), OMNIROUTE_SERVER_HOST: '127.0.0.1', HOSTNAME: '127.0.0.1', OMNIROUTE_NO_UPDATE_NOTIFIER: '1', OMNIROUTE_DISABLE_BACKGROUND_SERVICES: '1', APP_LOG_TO_FILE: 'false' };
const probes = [];
let child;
let output = '';
let stage = 'receipt';
let monitor;
let cleanup;
const signals = new EventEmitter();
let interrupted = false;
const forwardSignal = () => { interrupted = true; signals.emit('SIGTERM'); };
process.on('SIGTERM', forwardSignal); process.on('SIGINT', forwardSignal);

function snapshot() {
  const result = spawnSync('pwsh.exe', ['-NoProfile', '-NonInteractive', '-File', join(dirname(fileURLToPath(import.meta.url)), 'system-snapshot.ps1')], { encoding: 'utf8', windowsHide: true, timeout: 5000, maxBuffer: 2 * 1024 * 1024 });
  assert.equal(result.status, 0, 'snapshot_failed'); return JSON.parse(result.stdout);
}

function killTree(pid, force) {
  const result = spawnSync('taskkill.exe', ['/PID', String(pid), '/T', ...(force ? ['/F'] : [])], { stdio: 'ignore', windowsHide: true, timeout: 2000 });
  if (result.error) throw new Error('tree_stop_failed');
}

async function stop() {
  if (!monitor) return;
  if (!cleanup) { signals.emit('SIGTERM'); cleanup = await monitor; }
  assert.equal(cleanup.unresolved, false, 'cleanup_unresolved');
  assert.equal(cleanup.remaining.length, 0, 'owned_processes_remain');
}

try {
  assertPinnedNode(process.version);
  assert(process.platform==='win32'||(process.platform==='linux'&&process.env.OMNIROUTE_REBUILD_PROFILE===linuxProfile),'unsupported_or_unreviewed_smoke_platform');
  const before = verifyReceipt();
  const guardAttestation=verifyGuardAttestation(cache,process.platform,before);
  stage = 'cli-help';
  const help = spawn(process.execPath, [cli, '--help'], { cwd: source, env, windowsHide: true,detached:process.platform==='linux' });
  const helpDone=new Promise((accept, reject) => {
    let text = '';
    help.stdout.on('data', (chunk) => { if (text.length < 1024 * 1024) text += chunk; });
    help.stderr.on('data', () => {});
    const timer = setTimeout(() => help.kill(), 30000);
    help.once('error', reject);
    help.once('close', (code) => { clearTimeout(timer); code === 0 && /serve/.test(text) ? accept() : reject(new Error('cli-help')); });
  });
  const helpAdapter=process.platform==='linux'?ownedLinuxAdapter(help,process.pid):undefined;
  const helpMonitor=helpAdapter?guardProcess({child:help,parentPid:process.pid,snapshot:helpAdapter.snapshot,softTree:pid=>helpAdapter.signal(pid,'SIGTERM'),hardTree:pid=>helpAdapter.signal(pid,'SIGKILL'),delay,now:Date.now,signalBus:signals,floorBytes:3*1024**3,timeoutMs:30000}):undefined;
  try { await helpDone; } finally {
    if(helpMonitor){const result=await helpMonitor;await confirmReaped(help);assert.equal(result.unresolved,false,'help_cleanup_unresolved');assert.equal(result.remaining.length,0,'help_processes_remain');}
  }
  stage = 'reserve-loopback';
  const port = await new Promise((accept, reject) => {
    const listener = createServer(); listener.once('error', reject);
    listener.listen(0, '127.0.0.1', () => { const port = listener.address().port; listener.close(() => accept(port)); });
  });
  stage = 'cli-serve';
  child = spawn(process.execPath, [cli, 'serve', '--port', String(port), '--no-open', '--no-tray', '--no-recovery', '--ready-timeout', '60000'], { cwd: source, env: { ...env, PORT: String(port) }, windowsHide: true,detached:process.platform==='linux' });
  child.on('error', () => {});
  const collect = (chunk) => { if (output.length < 4 * 1024 * 1024) output += chunk; };
  child.stdout.on('data', collect); child.stderr.on('data', collect);
  const adapter=process.platform==='linux'?ownedLinuxAdapter(child,process.pid):undefined;
  monitor = guardProcess({ child, parentPid: process.pid, snapshot:adapter?.snapshot??snapshot, softTree: (pid) => adapter?adapter.signal(pid,'SIGTERM'):killTree(pid, false), hardTree: (pid) => adapter?adapter.signal(pid,'SIGKILL'):killTree(pid, true), delay, now: Date.now, signalBus: signals, floorBytes: 3 * 1024 ** 3, timeoutMs: 120000 });
  let ready = false;
  for (let attempt = 0; attempt < 90 && child.exitCode === null && !interrupted; attempt++) {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/healthz`, { redirect: 'manual', signal: AbortSignal.timeout(1000) });
      if (response.status === 200 && (await response.text()).trim() === 'ok') { ready = true; break; }
    } catch {}
    await delay(1000);
  }
  assert(ready && !interrupted, 'health_not_ready');
  stage = 'http-routes';
  for (const path of ['/healthz', '/readyz', '/login']) {
    const response = await fetch(`http://127.0.0.1:${port}${path}`, { redirect: 'manual', signal: AbortSignal.timeout(10000) });
    await response.arrayBuffer();
    probes.push({ path, status: response.status });
    assert.equal(response.status, 200, 'http_route_failed');
  }
  assert(!/preview-props\.json.*ENOENT|Failed to load instrumentation hook/.test(output), 'boot_error');
  await stop();
  if(process.platform==='linux')await confirmReaped(child);
  await confirmLoopbackRefused(port);
  stage = 'artifact-unchanged';
  const after = verifyReceipt();
  assert.deepEqual(after.dist, before.dist);
  after.cliAndHttpSmoke = 'pass';
  after.guardAttestationSha256=guardAttestation.sha256;
  after.smoke = { platform:process.platform,cliHelp: 'pass', cliServe: 'pass', bind: '127.0.0.1', randomPort: true, probes, processTreeStopped: true, remainingOwnedNodeProcesses: cleanup.remaining.filter((row) => row.node).length, cleanupUnresolved: cleanup.unresolved, providerCalls: 0, rawOutputSaved: false };
  writeFileSync(receiptPath, JSON.stringify(after, null, 2) + '\n');
  process.stdout.write(JSON.stringify({ omniroute_security_smoke: 'pass', probes, processTreeStopped: true, rawOutputSaved: false }) + '\n');
} catch {
  try { await stop();if(process.platform==='linux'&&child)await confirmReaped(child); } catch { stage = 'cleanup_unresolved'; }
  const modules = [...output.matchAll(/(?:Cannot find module|Can't resolve) ['"]([@a-zA-Z0-9_.\/-]{1,160})['"]/g)].map((match) => match[1]);
  const result = { omniroute_security_smoke: 'fail', stage, modules: [...new Set(modules)].slice(0, 20), rawOutputSaved: false };
  writeFileSync(join(cache, 'smoke-failure.json'), JSON.stringify(result, null, 2) + '\n');
  process.stderr.write(JSON.stringify(result) + '\n'); process.exitCode = 1;
} finally {
  process.off('SIGTERM', forwardSignal); process.off('SIGINT', forwardSignal);
}
