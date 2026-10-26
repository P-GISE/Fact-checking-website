import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { linuxProfile } from './platform-profile.mjs';
export function receiptBinding(receipt) {
  const keys=['attempt','executionId','profile','platform','arch','node','sourceCommit','planSha256','dist','runtimeInputs'];
  return Object.fromEntries(keys.map(key=>{assert(receipt[key]!==undefined,`missing_receipt_binding_${key}`);return[key,receipt[key]];}));
}
export function verifyGuardAttestation(cache,platform,receipt) {
  const name=platform==='linux'?linuxProfile:'turbo-4096-20261026';
  assert(['linux','win32'].includes(platform),'unsupported_guard_platform');
  const bytes=readFileSync(join(cache,`attempt-${name}.json`));const value=JSON.parse(bytes);
  assert.equal(receipt.attempt,name);assert.equal(receipt.platform,platform);assert.equal(receipt.node,'v24.20.0');
  assert.equal(receipt.profile,platform==='linux'?linuxProfile:'legacy-local-turbopack');
  assert(/^[a-f0-9-]{36}$/.test(receipt.executionId),'execution_id_required');
  assert.equal(value.attempt,name);assert.equal(value.executionId,receipt.executionId);assert.equal(value.platform,platform);assert.equal(value.arch,receipt.arch);assert.equal(value.node,receipt.node);assert.equal(value.profile,receipt.profile);
  assert.deepEqual(value.receiptBinding,receiptBinding(receipt),'guard_receipt_binding_changed');
  assert.equal(value.status,'build_pass_smoke_pending','build_guard_not_passed');
  assert.equal(value.cleanupUnresolved,false);assert.equal(value.remainingOwnedProcesses,0);assert.equal(value.initialUnrelatedNodeProcessesStillPresent,true);
  if(platform==='linux')assert.equal(value.childReaped,true);
  return {sha256:createHash('sha256').update(bytes).digest('hex'),attempt:name};
}
