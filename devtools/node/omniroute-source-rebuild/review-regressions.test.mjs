import test from 'node:test';
import assert from 'node:assert/strict';
import { EventEmitter } from 'node:events';
import { createHash } from 'node:crypto';
import { mkdtempSync,mkdirSync,readFileSync,writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { guardProcess } from './process-guard.mjs';
import { ownedLinuxAdapter } from './linux-processes.mjs';
import { verifyReceipt,treeDigest } from './rebuild.mjs';
import { installedTreeDigest } from './installed-tree.mjs';
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');

async function lateGroup(mode) {
  const child=new EventEmitter();child.pid=10;child.exitCode=null;child.signalCode=null;child.kill=()=>assert.fail('held exited root killed');
  let rows=[{pid:10,parent:1,born:'root',node:true,group:10,session:10}];let time=0,delays=0;const sent=[];
  const adapter=ownedLinuxAdapter(child,1,()=>({freeBytes:100,rows}),(pid,signal)=>{sent.push([pid,signal]);rows=[];});
  const result=await guardProcess({child,parentPid:1,snapshot:adapter.snapshot,softTree:pid=>adapter.signal(pid,'SIGTERM'),hardTree:pid=>adapter.signal(pid,'SIGKILL'),signalBus:new EventEmitter(),now:()=>time,floorBytes:3,timeoutMs:30000,delay:async(ms)=>{
    time+=ms;delays++;
    if(delays===1){child.exitCode=0;child.emit('exit',0);rows=[{pid:20,parent:1,born:'late-worker',node:true,group:10,session:10}];}
    if(mode==='late-cleanup'&&delays===2)rows.push({pid:21,parent:1,born:'later-worker',node:true,group:10,session:10});
  }});
  return{result,sent,rows};
}
test('H1 actual adapter+guard never certify unanchored late orphan as cleaned',async()=>{
  const {result,sent,rows}=await lateGroup('after-root');assert.notEqual(result.status,'build_pass_smoke_pending');assert.equal(result.unresolved,true);assert(result.remaining.some(r=>r.pid===20));assert.equal(rows.length,1);assert.deepEqual(sent,[]);
});
test('H1 late member appearing during cleanup stays visible and fails closed',async()=>{
  const {result,sent}=await lateGroup('late-cleanup');assert.equal(result.unresolved,true);assert(result.remaining.some(r=>r.pid===21));assert.deepEqual(sent,[]);
});
test('H1 adapter+guard do not kill reused session identities',async()=>{
  const child=new EventEmitter();Object.assign(child,{pid:10,exitCode:null,signalCode:null});child.kill=()=>assert.fail('reused root kill');let rows=[{pid:10,parent:1,born:'original',node:true,group:10,session:10}];let time=0;const sent=[];
  const adapter=ownedLinuxAdapter(child,1,()=>({freeBytes:100,rows}),(pid,signal)=>sent.push([pid,signal]));
  const result=await guardProcess({child,parentPid:1,snapshot:adapter.snapshot,softTree:pid=>adapter.signal(pid,'SIGTERM'),hardTree:pid=>adapter.signal(pid,'SIGKILL'),signalBus:new EventEmitter(),now:()=>time,floorBytes:3,timeoutMs:30000,delay:async(ms)=>{time+=ms;if(child.exitCode===null){child.exitCode=0;child.emit('exit',0);rows=[{pid:10,parent:1,born:'reused',node:true,group:10,session:10},{pid:99,parent:1,born:'unrelated',node:true,group:99,session:99}];}}});
  assert.equal(result.unresolved,true);assert(result.remaining.some(r=>r.pid===10));assert.deepEqual(sent,[]);assert(rows.some(r=>r.pid===99));
});
test('H1 live birth anchor adopts late group members during cleanup and reaps the owned group',async()=>{
  const child=new EventEmitter();Object.assign(child,{pid:10,exitCode:null,signalCode:null});child.kill=()=>assert.fail('exited root handle');
  let rows=[{pid:10,parent:1,born:'root',node:true,group:10,session:10},{pid:11,parent:10,born:'anchor',node:true,group:10,session:10}];let calls=0,time=0;const sent=[];
  const adapter=ownedLinuxAdapter(child,1,()=>({freeBytes:100,rows}),(pid,signal)=>{sent.push([pid,signal]);if(signal==='SIGKILL')rows=[];});
  const result=await guardProcess({child,parentPid:1,snapshot:adapter.snapshot,softTree:pid=>adapter.signal(pid,'SIGTERM'),hardTree:pid=>adapter.signal(pid,'SIGKILL'),signalBus:new EventEmitter(),now:()=>time,floorBytes:3,timeoutMs:30000,delay:async(ms)=>{time+=ms;calls++;if(calls===1){child.exitCode=0;child.emit('exit',0);rows=rows.filter(r=>r.pid!==10);rows.push({pid:20,parent:1,born:'late',node:true,group:10,session:10});}if(calls===2)rows.push({pid:21,parent:1,born:'during-cleanup',node:true,group:10,session:10});}});
  assert.equal(result.status,'build_pass_smoke_pending');assert.equal(result.unresolved,false);assert.deepEqual(result.remaining,[]);assert.deepEqual(sent,[[-10,'SIGTERM'],[-10,'SIGKILL']]);
});

function receiptFixture() {
  const cache=mkdtempSync(join(tmpdir(),'omni-receipt-closure-'));const source=join(cache,'source');const dist=join(source,'dist');mkdirSync(dist,{recursive:true});mkdirSync(join(source,'bin'));mkdirSync(join(source,'node_modules','dep'),{recursive:true});
  writeFileSync(join(dist,'server.js'),'export const ready=true;');writeFileSync(join(source,'bin','omniroute.mjs'),'import "../node_modules/dep/index.mjs";');writeFileSync(join(source,'node_modules','dep','index.mjs'),'export const safe=true;');
  for(const path of ['bin/cli/commands/serve.mjs','scripts/build/runtime-env.mjs','open-sse/utils/setupPolyfill.ts','src/shared/platform/windowsProcess.ts','tsconfig.json']){mkdirSync(join(source,path,'..'),{recursive:true});writeFileSync(join(source,path),'synthetic runtime input');}
  const planBytes=readFileSync(new URL('./plan.json',import.meta.url));const plan=JSON.parse(planBytes);
  const receipt={schema:1,sourceCommit:plan.commit,overlay:plan.overlay,planSha256:sha(planBytes),nextVersion:plan.dependencies.next,patchedLockSha256:plan.patchedLockSha256,sourceArchiveSha256:plan.sourceArchiveSha256,platform:process.platform,arch:process.arch,node:process.version,dist:treeDigest(dist),runtimeInputs:installedTreeDigest(source,source,[])};
  writeFileSync(join(cache,'receipt.json'),JSON.stringify(receipt));return{cache,source,options:{cacheRoot:cache,sourceRoot:source,requireGuard:false}};
}
for(const path of ['bin/omniroute.mjs','node_modules/dep/index.mjs','bin/cli/commands/serve.mjs','scripts/build/runtime-env.mjs','open-sse/utils/setupPolyfill.ts','src/shared/platform/windowsProcess.ts','tsconfig.json'])test(`H2 actual receipt rejects changed executed input ${path}`,()=>{
  const fixture=receiptFixture();verifyReceipt(fixture.options);writeFileSync(join(fixture.source,path),'export const changed=true;');assert.throws(()=>verifyReceipt(fixture.options));
});
test('H2 source injection and receipt platform mismatch are rejected',()=>{
  let fixture=receiptFixture();verifyReceipt(fixture.options);writeFileSync(join(fixture.source,'new-input.mjs'),'injected');assert.throws(()=>verifyReceipt(fixture.options));
  fixture=receiptFixture();const path=join(fixture.cache,'receipt.json');const value=JSON.parse(readFileSync(path));value.platform='different';writeFileSync(path,JSON.stringify(value));assert.throws(()=>verifyReceipt(fixture.options));
});
test('pending builder receipt is not accepted by user-facing verification without its completed guard',()=>{
  const fixture=receiptFixture();verifyReceipt(fixture.options);assert.throws(()=>verifyReceipt({...fixture.options,requireGuard:true}));
});
