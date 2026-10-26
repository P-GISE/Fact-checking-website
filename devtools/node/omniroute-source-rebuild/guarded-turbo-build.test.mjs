import test from 'node:test';
import assert from 'node:assert/strict';
import { isolatedEnv } from './rebuild.mjs';
import { attemptPolicy, verifyMode } from './guarded-turbo-build.mjs';
test('approved mode is full Turbopack at 4096, rejecting webpack or increased heap',()=>{
  const env=isolatedEnv();verifyMode(env);assert.equal(attemptPolicy.attempt,'turbo-4096-20261026');
  assert.throws(()=>verifyMode({...env,OMNIROUTE_USE_TURBOPACK:'0'}));
  assert.throws(()=>verifyMode({...env,NODE_OPTIONS:'--max-old-space-size=6144'}));
  assert.throws(()=>verifyMode({...env,OMNIROUTE_BUILD_PROFILE:'contributor'}));
});
test('native and standalone security guards cannot be disabled',()=>{
  const env=isolatedEnv();assert.throws(()=>verifyMode({...env,OMNIROUTE_SKIP_NATIVE_DEP_CHECK:'1'}));assert.throws(()=>verifyMode({...env,OMNIROUTE_SKIP_STANDALONE:'1'}));
});
