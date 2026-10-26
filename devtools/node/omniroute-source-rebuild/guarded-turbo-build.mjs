import assert from 'node:assert/strict';
import { spawn, spawnSync } from 'node:child_process';
import { createHash,randomUUID } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { setTimeout as delay } from 'node:timers/promises';
import { buildMode, isolatedEnv } from './rebuild.mjs';
import { guardProcess } from './process-guard.mjs';
import { receiptBinding } from './guard-attestation.mjs';
export { descendants } from './process-guard.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '../../..');
const cache = join(root, '.tools/omniroute-security-build');
const attemptPath = join(cache, 'attempt-turbo-4096-20261026.json');
const GiB = 1024 ** 3;
export const attemptPolicy = { attempt: 'turbo-4096-20261026', heapMb: 4096, bundler: 'turbopack' };
export function verifyMode(env, policy = attemptPolicy) {
  assert.equal(buildMode, 'turbopack'); assert.equal(policy.bundler, 'turbopack');
  assert.equal(policy.heapMb, 4096); assert.equal(env.OMNIROUTE_USE_TURBOPACK, '1');
  assert.equal(env.NODE_OPTIONS, '--max-old-space-size=4096');
  for (const key of ['OMNIROUTE_BUILD_PROFILE','OMNIROUTE_BUILD_BACKEND_ONLY','OMNIROUTE_SKIP_STANDALONE','OMNIROUTE_MITM_STUB','OMNIROUTE_BETTER_SQLITE3_STUB','OMNIROUTE_SKIP_NATIVE_DEP_CHECK']) assert.equal(env[key], undefined);
}
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
  assert(!existsSync(attemptPath), 'turbo_4096_attempt_already_recorded');
  mkdirSync(cache, { recursive: true });
  const initial = snapshot();
  assert(initial.freeBytes >= 10 * GiB, 'fresh_free_memory_below_10GiB');
  const failure = join(cache, 'failure.json');
  const priorFailureSha = existsSync(failure) ? createHash('sha256').update(readFileSync(failure)).digest('hex') : null;
  if (existsSync(failure)) writeFileSync(join(cache, 'attempt-turbo-4096-prior-failure.json'), readFileSync(failure), { flag: 'wx' });
  const buildEnv = isolatedEnv(); verifyMode(buildEnv);
  const hashes = Object.fromEntries(['rebuild.mjs', 'guarded-turbo-build.mjs', 'process-guard.mjs', 'system-snapshot.ps1', 'plan.json', 'source-lock.patch'].map((name) => [name, createHash('sha256').update(readFileSync(join(here, name))).digest('hex')]));
  const record = { ...attemptPolicy,executionId:randomUUID(),profile:'legacy-local-turbopack',platform:process.platform,arch:process.arch, startedAt: new Date().toISOString(), node: process.version, timeoutMinutes: 30, initialFreeBytes: initial.freeBytes, floorBytes: 3 * GiB, hashes, status: 'running', rawOutputSaved: false, aclChanges: 0, providerCalls: 0 };
  writeFileSync(attemptPath, JSON.stringify(record, null, 2) + '\n', { flag: 'wx' });
  const child = spawn(process.execPath, [join(here, 'rebuild.mjs'), '--resume-installed'], { cwd: root, env: { ...buildEnv, OMNIROUTE_REBUILD_HEAP_MB: '4096',OMNIROUTE_REBUILD_ATTEMPT:record.attempt,OMNIROUTE_REBUILD_EXECUTION_ID:record.executionId }, windowsHide: true });
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
  if (existsSync(failure)) { const bytes = readFileSync(failure); const old = JSON.parse(bytes); record.lastBuildFailure = { stage: old.stage, category: old.category, code: old.code, origin: createHash('sha256').update(bytes).digest('hex') === priorFailureSha ? 'preserved_prior_attempt_or_identical_failure' : 'changed_during_this_attempt' }; }
  const receiptPath=join(cache,'receipt.json');if(existsSync(receiptPath)){try{record.receiptBinding=receiptBinding(JSON.parse(readFileSync(receiptPath)));for(const key of ['attempt','executionId','profile','platform','arch','node'])assert.equal(record.receiptBinding[key],record[key]);assert.equal(record.receiptBinding.planSha256,hashes['plan.json']);}catch{record.status='receipt_binding_invalid';}}
  if(record.status==='build_pass_smoke_pending'&&!record.receiptBinding)record.status='receipt_missing';
  writeFileSync(attemptPath, JSON.stringify(record, null, 2) + '\n');
  process.stdout.write(JSON.stringify({ attempt: record.attempt, status: record.status, exitCode: record.exitCode, remainingOwnedNodeProcesses: record.remainingOwnedNodeProcesses, rawOutputSaved: false }) + '\n');
  assert.equal(record.status, 'build_pass_smoke_pending', 'guarded_build_not_passed');
  assert.equal(record.cleanupUnresolved, false); assert.equal(record.remainingOwnedProcesses, 0);
  assert.equal(record.initialUnrelatedNodeProcessesStillPresent, true);
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) main().catch(() => { process.stderr.write('{"guarded_local_build":"not_passed","rawOutputSaved":false}\n'); process.exitCode = 1; });
