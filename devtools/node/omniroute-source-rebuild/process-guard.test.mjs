import test from 'node:test';
import assert from 'node:assert/strict';
import { EventEmitter } from 'node:events';
import { guardProcess } from './process-guard.mjs';

async function scenario(mode) {
  const child = new EventEmitter(); child.pid = 10; child.exitCode = null;
  const bus = new EventEmitter();
  const killed = []; let held = 0; let tick = 0; let calls = 0; let delays = 0;
  let rows = [{pid:10,parent:1,born:'original',node:true},{pid:20,parent:10,born:'worker',node:true},{pid:99,parent:0,born:'unrelated',node:true}];
  child.kill = () => { held++; child.exitCode = 143; child.emit('exit',143); rows = rows.filter((r)=>r.pid!==10); };
  const result = await guardProcess({ child, parentPid:1, signalBus:bus, now:()=>tick, floorBytes:3,timeoutMs:20000,
    snapshot:()=>{ calls++; if(mode==='snapshot-fails' && calls>1) throw Error('injected'); return {freeBytes:mode==='floor'?2:11,rows}; },
    softTree:(pid)=>{killed.push(['soft',pid]);},
    hardTree:(pid)=>{killed.push(['hard',pid]); rows=rows.filter((r)=>r.pid!==pid);},
    delay:async(ms)=>{tick+=ms;delays++;
      if(delays===1 && mode==='signal') bus.emit('SIGINT');
      if(delays===1 && ['normal','root-reused'].includes(mode)) { child.exitCode=0;child.emit('exit',0);rows=mode==='root-reused'?[{pid:10,parent:999,born:'reused',node:true},{pid:99,parent:0,born:'unrelated',node:true}]:[{pid:99,parent:0,born:'unrelated',node:true}]; }
    }
  });
  return {result,killed,held,bus};
}
test('normal exit verifies cleanup and preserves unrelated processes', async()=>{
  const {result,killed}=await scenario('normal');assert.equal(result.status,'build_pass_smoke_pending');assert.equal(result.unresolved,false);assert.deepEqual(killed,[]);
});
test('reused root is neither seeded nor killed', async()=>{
  const {result,killed}=await scenario('root-reused');assert.equal(result.status,'build_pass_smoke_pending');assert.deepEqual(killed,[]);
});
test('snapshot exception still terminates held handle, never kills unverified PID, and blocks success',async()=>{
  const {result,killed,held}=await scenario('snapshot-fails');assert.equal(result.status,'monitor_failed');assert.equal(result.unresolved,true);assert(held>0);assert.deepEqual(killed,[]);
});
test('signal forwards held TERM and finally reaps observed descendants',async()=>{
  const {result,killed,held,bus}=await scenario('signal');assert.equal(result.status,'signal');assert(held>0);assert(killed.some(([kind,pid])=>kind==='hard'&&pid===20));assert(!killed.some(([,pid])=>pid===99));assert.equal(bus.listenerCount('SIGINT'),0);
});
test('memory floor scopes TERM and forced cleanup to owned identities',async()=>{
  const {result,killed}=await scenario('floor');assert.equal(result.status,'free_memory_floor');assert(killed.some(([kind,pid])=>kind==='soft'&&pid===10));assert(!killed.some(([,pid])=>pid===99));assert.equal(result.remaining.length,0);
});
