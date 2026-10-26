import assert from 'node:assert/strict';
import { spawn, spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { setTimeout as delay } from 'node:timers/promises';
import { isolatedEnv } from './rebuild.mjs';
import { guardProcess } from './process-guard.mjs';
export { descendants } from './process-guard.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '../../..');
const cache = join(root, '.tools/omniroute-security-build');
const attemptPath = join(cache, 'attempt-6144-20261026.json');
const GiB = 1024 ** 3;
function snapshot() {
  const result = spawnSync('pwsh.exe', ['-NoProfile', '-NonInteractive', '-File', join(here, 'system-snapshot.ps1')], { encoding: 'utf8', windowsHide: true, timeout: 5000, maxBuffer: 2 * 1024 * 1024 });
  assert.equal(result.status, 0, 'snapshot_failed');
  return JSON.parse(result.stdout);
}
const killTree = (pid, force) => {
  const result = spawnSync('taskkill.exe', ['/PID', String(pid), '/T', ...(force ? ['/F'] : [])], { stdio: 'ignore', windowsHide: true, timeout: 2000 });
  if (result.error) throw new Error('tree_stop_failed');
};
async function main() {
  assert.equal(process.platform, 'win32'); assert.equal(process.version, 'v24.20.0');
  assert.equal(process.argv.length, 2);
  assert(!existsSync(attemptPath), '6144_attempt_already_recorded');
  mkdirSync(cache, { recursive: true });
  const initial = snapshot();
  assert(initial.freeBytes >= 10 * GiB, 'fresh_free_memory_below_10GiB');
  const failure = join(cache, 'failure.json');
  if (existsSync(failure)) writeFileSync(join(cache, 'attempt-4096-failure-preserved.json'), readFileSync(failure), { flag: 'wx' });
  const hashes = Object.fromEntries(['rebuild.mjs', 'guarded-local-build.mjs', 'process-guard.mjs', 'system-snapshot.ps1', 'plan.json', 'source-lock.patch'].map((name) => [name, createHash('sha256').update(readFileSync(join(here, name))).digest('hex')]));
  const record = { attempt: 'local-6144-20261026', startedAt: new Date().toISOString(), node: process.version, heapMb: 6144, timeoutMinutes: 30, initialFreeBytes: initial.freeBytes, floorBytes: 3 * GiB, hashes, status: 'running', rawOutputSaved: false, aclChanges: 0, providerCalls: 0 };
  writeFileSync(attemptPath, JSON.stringify(record, null, 2) + '\n', { flag: 'wx' });
  const child = spawn(process.execPath, [join(here, 'rebuild.mjs'), '--resume-installed'], { cwd: root, env: { ...isolatedEnv(), OMNIROUTE_REBUILD_HEAP_MB: '6144' }, windowsHide: true });
  let outputBytes = 0;
  const discard = (chunk) => { outputBytes += chunk.length; };
  child.stdout.on('data', discard); child.stderr.on('data', discard);
  const result = await guardProcess({ child, parentPid: process.pid, snapshot,
    softTree: (pid) => killTree(pid, false), hardTree: (pid) => killTree(pid, true), delay, now: Date.now,
    signalBus: process, floorBytes: 3 * GiB, timeoutMs: 30 * 60 * 1000, outputExceeded: () => outputBytes > 2 * 1024 * 1024 });
  record.finishedAt = new Date().toISOString(); record.minimumFreeBytes = result.minimumFree;
  record.status = result.status; record.exitCode = child.exitCode; record.cleanupUnresolved = result.unresolved;
  record.remainingOwnedProcesses = result.remaining.length; record.remainingOwnedNodeProcesses = result.remaining.filter((row) => row.node).length;
  try {
    const final = snapshot();
    record.initialUnrelatedNodeProcessesStillPresent = initial.rows.filter((row) => row.node).every((row) => final.rows.some((item) => item.pid === row.pid && item.born === row.born));
  } catch { record.initialUnrelatedNodeProcessesStillPresent = false; record.status = 'final_snapshot_failed'; }
  if (!record.initialUnrelatedNodeProcessesStillPresent) record.status = 'unrelated_process_changed';
  if (existsSync(failure)) { const old = JSON.parse(readFileSync(failure)); record.lastBuildFailure = { stage: old.stage, category: old.category, code: old.code }; }
  writeFileSync(attemptPath, JSON.stringify(record, null, 2) + '\n');
  process.stdout.write(JSON.stringify({ attempt: record.attempt, status: record.status, exitCode: record.exitCode, remainingOwnedNodeProcesses: record.remainingOwnedNodeProcesses, rawOutputSaved: false }) + '\n');
  assert.equal(record.status, 'build_pass_smoke_pending', 'guarded_build_not_passed');
  assert.equal(record.cleanupUnresolved, false); assert.equal(record.remainingOwnedProcesses, 0);
  assert.equal(record.initialUnrelatedNodeProcessesStillPresent, true);
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) main().catch(() => { process.stderr.write('{"guarded_local_build":"not_passed","rawOutputSaved":false}\n'); process.exitCode = 1; });
