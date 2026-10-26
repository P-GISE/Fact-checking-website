import test from 'node:test';import assert from 'node:assert/strict';import{mkdtempSync,writeFileSync}from'node:fs';import{join}from'node:path';import{tmpdir}from'node:os';import{verifyGuardAttestation,receiptBinding}from'./guard-attestation.mjs';
test('unresolved guard or late group candidate blocks smoke eligibility',()=>{
  const cache=mkdtempSync(join(tmpdir(),'omni-guard-proof-'));const path=join(cache,'attempt-linux-webpack-8192-20261026.json');
  const receipt={attempt:'linux-webpack-8192-20261026',executionId:'12345678-1234-1234-1234-123456789abc',profile:'linux-webpack-8192-20261026',platform:'linux',arch:'x64',node:'v24.20.0',sourceCommit:'a'.repeat(40),planSha256:'b'.repeat(64),dist:{files:1,sha256:'c'.repeat(64)},runtimeInputs:{files:2,sha256:'d'.repeat(64)}};
  const value={attempt:receipt.attempt,executionId:receipt.executionId,profile:receipt.profile,platform:receipt.platform,arch:receipt.arch,node:receipt.node,receiptBinding:receiptBinding(receipt),status:'build_pass_smoke_pending',cleanupUnresolved:false,remainingOwnedProcesses:0,initialUnrelatedNodeProcessesStillPresent:true,childReaped:true};
  writeFileSync(path,JSON.stringify(value));assert.equal(verifyGuardAttestation(cache,'linux',receipt).attempt,receipt.attempt);
  for(const change of [{status:'cleanup_unresolved'},{cleanupUnresolved:true},{remainingOwnedProcesses:1},{childReaped:false},{initialUnrelatedNodeProcessesStillPresent:false}]){writeFileSync(path,JSON.stringify({...value,...change}));assert.throws(()=>verifyGuardAttestation(cache,'linux',receipt));}
  writeFileSync(path,JSON.stringify(value));
  for(const change of [{executionId:'ffffffff-1234-1234-1234-123456789abc'},{profile:'different'},{planSha256:'e'.repeat(64)},{dist:{files:1,sha256:'f'.repeat(64)}},{runtimeInputs:{files:2,sha256:'f'.repeat(64)}},{lifecycle:{phase:'packaged',generatedCliSha256:'f'.repeat(64)}}])assert.throws(()=>verifyGuardAttestation(cache,'linux',{...receipt,...change}));
});
