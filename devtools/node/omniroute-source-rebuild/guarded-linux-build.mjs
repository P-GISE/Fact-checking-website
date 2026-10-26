import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createHash,randomUUID } from 'node:crypto';
import { existsSync,mkdirSync,readFileSync,writeFileSync } from 'node:fs';
import { dirname,join,resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { setTimeout as delay } from 'node:timers/promises';
import { isolatedEnv,buildMode } from './rebuild.mjs';
import { assertPinnedNode,linuxProfile,resolveProfile } from './platform-profile.mjs';
import { linuxSnapshot,ownedLinuxAdapter,confirmReaped } from './linux-processes.mjs';
import { guardProcess } from './process-guard.mjs';
import { receiptBinding } from './guard-attestation.mjs';
const here=dirname(fileURLToPath(import.meta.url));const root=resolve(here,'../../..');
const cache=join(root,'.tools/omniroute-security-build');const attemptPath=join(cache,`attempt-${linuxProfile}.json`);
const GiB=1024**3;
const stages=new Set(['git-init','git-origin','git-fetch','git-checkout','source-pin','source-tree','source-archive','source-manifest','source-clean','source-lock','locked-patch-check','locked-patch','install','native-hydration','native-sqlite','runtime-audit','full-webpack-build','full-turbopack-build','postbuild-workers','package-cli','contract']);
const categories=new Set(['deadline','spawn','output_limit','terminated','module_resolution','dependency_resolution','heap_limit','command_failed','archive','assertion','runtime']);
export function diagnosticSummary(value) {
  if(value?.omniroute_security_build!=='fail'||!stages.has(value.stage)||!categories.has(value.category))return null;
  if(value.code!==undefined&&value.code!==null&&(!Number.isInteger(value.code)||value.code<0||value.code>255))return null;
  return {stage:value.stage,category:value.category,code:value.code??null};
}
export function diagnosticCollector(executionId){
  assert.match(executionId,/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
  let pending='';let dropping=false;let lastPassedStage=null;let buildFailure=null;
  return {push(chunk){for(const part of String(chunk).split(/(?<=\n)/)){
    if(!dropping){pending+=part;if(pending.length>4096){pending='';dropping=true;}}
    if(part.endsWith('\n')){if(!dropping){try{const value=JSON.parse(pending);if(value.executionId===executionId){const failure=diagnosticSummary(value);if(failure)buildFailure=failure;if(value.result==='pass'&&stages.has(value.stage))lastPassedStage=value.stage;}}catch{}}pending='';dropping=false;}
  }},summary(){return {lastPassedStage,buildFailure};}};
}
export function verifyLinuxEnv(env) {
  assert.equal(env.OMNIROUTE_REBUILD_PROFILE,linuxProfile);assert.equal(env.OMNIROUTE_REBUILD_HEAP_MB,'8192');
  assert.equal(env.OMNIROUTE_USE_TURBOPACK,'0');assert.equal(env.NODE_OPTIONS,'--max-old-space-size=8192');
  for(const key of ['OMNIROUTE_BUILD_PROFILE','OMNIROUTE_BUILD_BACKEND_ONLY','OMNIROUTE_SKIP_STANDALONE','OMNIROUTE_MITM_STUB','OMNIROUTE_BETTER_SQLITE3_STUB','OMNIROUTE_SKIP_NATIVE_DEP_CHECK'])assert.equal(env[key],undefined);
}
async function main() {
  assert.equal(process.platform,'linux');assertPinnedNode(process.version);assert.equal(buildMode,'webpack');
  const policy=resolveProfile(process.platform,process.env.OMNIROUTE_REBUILD_PROFILE,process.env.OMNIROUTE_REBUILD_HEAP_MB);
  assert.equal(policy.name,linuxProfile);assert.equal(process.argv.length,2);assert(!existsSync(attemptPath),'linux_attempt_already_recorded');
  assert(!existsSync(join(cache,'source')),'fresh_linux_source_required');
  const env=isolatedEnv();verifyLinuxEnv(env);const initial=linuxSnapshot();assert(initial.freeBytes>=12*GiB,'fresh_effective_free_below_12GiB');
  mkdirSync(cache,{recursive:true});
  const names=['rebuild.mjs','archive-policy.mjs','guarded-linux-build.mjs','source-inputs.mjs','installed-tree.mjs','platform-profile.mjs','linux-processes.mjs','process-guard.mjs','guard-attestation.mjs','smoke.mjs','tcp-refusal.mjs','plan.json','source-lock.patch'];
  const hashes=Object.fromEntries(names.map(name=>[name,createHash('sha256').update(readFileSync(join(here,name))).digest('hex')]));
  const record={attempt:linuxProfile,executionId:randomUUID(),profile:linuxProfile,platform:'linux',arch:process.arch,node:process.version,bundler:'webpack',heapMb:8192,startedAt:new Date().toISOString(),initialFreeBytes:initial.freeBytes,totalEffectiveBytes:initial.totalBytes,cgroupBudgetsChecked:initial.memoryBudgetsChecked,floorBytes:3*GiB,timeoutMinutes:30,hashes,status:'running',rawOutputSaved:false};
  writeFileSync(attemptPath,JSON.stringify(record,null,2)+'\n',{flag:'wx'});
  const child=spawn(process.execPath,[join(here,'rebuild.mjs')],{cwd:root,env:{...env,OMNIROUTE_REBUILD_ATTEMPT:record.attempt,OMNIROUTE_REBUILD_EXECUTION_ID:record.executionId},detached:true,stdio:['ignore','pipe','pipe']});
  let outputBytes=0;const stdoutDiagnostics=diagnosticCollector(record.executionId);const stderrDiagnostics=diagnosticCollector(record.executionId);
  child.stdout.on('data',chunk=>{outputBytes+=chunk.length;stdoutDiagnostics.push(chunk);});child.stderr.on('data',chunk=>{outputBytes+=chunk.length;stderrDiagnostics.push(chunk);});
  const adapter=ownedLinuxAdapter(child,process.pid);
  const result=await guardProcess({child,parentPid:process.pid,snapshot:adapter.snapshot,softTree:pid=>adapter.signal(pid,'SIGTERM'),hardTree:pid=>adapter.signal(pid,'SIGKILL'),delay,now:Date.now,signalBus:process,floorBytes:3*GiB,timeoutMs:30*60*1000,outputExceeded:()=>outputBytes>2*1024*1024});
  record.finishedAt=new Date().toISOString();record.minimumFreeBytes=result.minimumFree;record.status=result.status;record.primaryStopReason=result.reason??null;record.cleanupUnresolved=result.unresolved;record.remainingOwnedProcesses=result.remaining.length;record.remainingOwnedNodeProcesses=result.remaining.filter(r=>r.node).length;
  record.remainingUncertainGroupProcesses=result.remaining.filter(r=>r.ownership==='uncertain').length;
  try{record.childReaped=await confirmReaped(child);}catch{record.childReaped=false;record.status='child_not_reaped';}
  try{const final=linuxSnapshot();record.initialUnrelatedNodeProcessesStillPresent=initial.rows.filter(r=>r.node).every(old=>final.rows.some(r=>r.pid===old.pid&&r.born===old.born));}catch{record.initialUnrelatedNodeProcessesStillPresent=false;}
  if(!record.initialUnrelatedNodeProcessesStillPresent)record.status='unrelated_process_changed';record.exitCode=child.exitCode;record.exitSignal=child.signalCode;
  const failure=join(cache,'failure.json');if(existsSync(failure)){const error=JSON.parse(readFileSync(failure));record.buildFailure={stage:error.stage,category:error.category,code:error.code};}
  const receiptPath=join(cache,'receipt.json');if(existsSync(receiptPath)){try{record.receiptBinding=receiptBinding(JSON.parse(readFileSync(receiptPath)));for(const key of ['attempt','executionId','profile','platform','arch','node'])assert.equal(record.receiptBinding[key],record[key]);assert.equal(record.receiptBinding.planSha256,hashes['plan.json']);}catch{record.status='receipt_binding_invalid';}}
  if(record.status==='build_pass_smoke_pending'&&!record.receiptBinding)record.status='receipt_missing';
  const diagnostics={lastPassedStage:stdoutDiagnostics.summary().lastPassedStage,buildFailure:stderrDiagnostics.summary().buildFailure??stdoutDiagnostics.summary().buildFailure};
  record.diagnostics=diagnostics;
  writeFileSync(attemptPath,JSON.stringify(record,null,2)+'\n');process.stdout.write(JSON.stringify({attempt:record.attempt,status:record.status,remainingOwnedNodeProcesses:record.remainingOwnedNodeProcesses,...diagnostics})+'\n');
  assert.equal(record.status,'build_pass_smoke_pending');assert.equal(record.cleanupUnresolved,false);assert.equal(record.remainingOwnedProcesses,0);assert.equal(record.childReaped,true);assert.equal(record.initialUnrelatedNodeProcessesStillPresent,true);
}
if(process.argv[1]&&resolve(process.argv[1])===fileURLToPath(import.meta.url))main().catch(()=>{process.stderr.write('{"guarded_linux_build":"not_passed","rawOutputSaved":false}\n');process.exitCode=1;});
