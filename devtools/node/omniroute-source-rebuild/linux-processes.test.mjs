import test from 'node:test';
import assert from 'node:assert/strict';
import { EventEmitter } from 'node:events';
import { posix } from 'node:path';
import { parseStat,effectiveMemory,signalOwnedGroup,confirmReaped,ownedLinuxAdapter } from './linux-processes.mjs';
import { resolveProfile,resolveNpmEntry,assertPinnedNode,linuxProfile } from './platform-profile.mjs';
import { verifyLinuxEnv } from './guarded-linux-build.mjs';
test('Linux profile is explicit, platform bound, and exactly webpack/8192',()=>{
  assert.equal(resolveProfile('linux',linuxProfile,'8192').bundler,'webpack');
  assert.throws(()=>resolveProfile('win32',linuxProfile,'8192'));
  assert.throws(()=>resolveProfile('linux',linuxProfile,'6144'));
  assert.throws(()=>resolveProfile('linux',undefined,'8192'));
  assertPinnedNode('v24.20.0');assert.throws(()=>assertPinnedNode('v24.19.0'));
});
test('Linux launch environment rejects altered engine, heap and feature stubs',()=>{
  const env={OMNIROUTE_REBUILD_PROFILE:linuxProfile,OMNIROUTE_REBUILD_HEAP_MB:'8192',OMNIROUTE_USE_TURBOPACK:'0',NODE_OPTIONS:'--max-old-space-size=8192'};
  verifyLinuxEnv(env);assert.throws(()=>verifyLinuxEnv({...env,OMNIROUTE_USE_TURBOPACK:'1'}));assert.throws(()=>verifyLinuxEnv({...env,NODE_OPTIONS:'--max-old-space-size=4096'}));assert.throws(()=>verifyLinuxEnv({...env,OMNIROUTE_BUILD_PROFILE:'contributor'}));
});
test('npm entry supports Linux setup-node prefix and rejects absent entry',()=>{
  assert.equal(resolveNpmEntry('/opt/node/bin/node',p=>p==='/opt/node/lib/node_modules/npm/bin/npm-cli.js',posix),'/opt/node/lib/node_modules/npm/bin/npm-cli.js');
  assert.throws(()=>resolveNpmEntry('/opt/node/bin/node',()=>false,posix));
});
test('proc parser handles spaces and parentheses in process name',()=>{
  const fields=['S','2','10','10',...Array(15).fill('0'),'123'];
  assert.deepEqual(parseStat(`10 (node (worker)) ${fields.join(' ')}`),{pid:10,parent:2,group:10,session:10,born:'123'});
});
test('effective memory respects finite cgroup budget and fails closed on unknown data',()=>{
  const mem='MemTotal: 16000000 kB\nMemAvailable: 13000000 kB\n';
  assert.equal(effectiveMemory(mem,'8000000000','7000000000').freeBytes,1000000000);
  assert.equal(effectiveMemory(mem,'max','0').freeBytes,13000000*1024);
  assert.throws(()=>effectiveMemory('missing','max','0'));assert.throws(()=>effectiveMemory(mem,'8','unknown'));
});
test('signals only the own new session group, never an unrelated group',()=>{
  const sent=[];const snap=()=>({rows:[{pid:20,group:10,session:10}]});
  signalOwnedGroup(10,20,'SIGTERM',snap,(...args)=>sent.push(args));assert.deepEqual(sent,[[-10,'SIGTERM']]);
  assert.throws(()=>signalOwnedGroup(11,20,'SIGKILL',snap,()=>assert.fail('unrelated kill')));
});
test('reap timeout blocks success',async()=>{
  const child=new EventEmitter();child.exitCode=null;child.signalCode=null;
  await assert.rejects(confirmReaped(child,async()=>{}));child.signalCode='SIGTERM';assert.equal(await confirmReaped(child),true);
});
test('Linux group adapter rejects a PID reused after its observed birth',()=>{
  let rows=[{pid:10,parent:1,node:true,born:'old',group:10,session:10}];const sent=[];
  const adapter=ownedLinuxAdapter({pid:10},1,()=>({rows}),(pid,signal)=>sent.push([pid,signal]));
  adapter.snapshot();rows=[{pid:10,parent:1,node:true,born:'new',group:10,session:10}];
  assert.throws(()=>adapter.signal(10,'SIGKILL'));assert.deepEqual(sent,[]);
});
