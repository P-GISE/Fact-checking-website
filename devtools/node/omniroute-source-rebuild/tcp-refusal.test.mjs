import test from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:net';
import { EventEmitter } from 'node:events';
import { confirmLoopbackRefused } from './tcp-refusal.mjs';
test('real loopback listener fails; confirmed closed port passes',async()=>{
  const server=createServer((socket)=>socket.destroy());await new Promise((r)=>server.listen(0,'127.0.0.1',r));
  const port=server.address().port;await assert.rejects(confirmLoopbackRefused(port));
  await new Promise((r)=>server.close(r));assert.equal(await confirmLoopbackRefused(port),true);
});
test('timeout and non-refusal socket errors fail closed',async()=>{
  for(const code of ['ETIMEDOUT','ECONNRESET']){
    const fake=()=>{const s=new EventEmitter();s.destroy=()=>{};s.setTimeout=()=>{};queueMicrotask(()=>s.emit('error',{code}));return s;};
    await assert.rejects(confirmLoopbackRefused(1,fake));
  }
});
