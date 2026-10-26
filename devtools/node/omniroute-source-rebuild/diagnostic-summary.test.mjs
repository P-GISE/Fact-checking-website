import test from 'node:test';
import assert from 'node:assert/strict';
import { diagnosticSummary,diagnosticCollector } from './guarded-linux-build.mjs';

test('diagnostic retains fixed failure metadata while stripping unknown and sensitive text',()=>{
  assert.deepEqual(diagnosticSummary({omniroute_security_build:'fail',stage:'install',category:'dependency_resolution',code:1,token:'synthetic-not-a-credential',modules:['synthetic']}),{stage:'install',category:'dependency_resolution',code:1});
  assert.equal(diagnosticSummary({omniroute_security_build:'fail',stage:'untrusted-body',category:'runtime',code:1}),null);
  assert.equal(diagnosticSummary({omniroute_security_build:'fail',stage:'contract',category:'untrusted-body',code:1}),null);
  assert.equal(diagnosticSummary({omniroute_security_build:'fail',stage:'contract',category:'assertion',code:'untrusted-body'}),null);
  assert.deepEqual(diagnosticSummary({omniroute_security_build:'fail',stage:'contract',category:'assertion'}),{stage:'contract',category:'assertion',code:null});
});
test('chunked and oversized output never leaks raw text into the diagnostic summary',()=>{
  const nonce='00000000-0000-4000-8000-000000000001';const collector=diagnosticCollector(nonce);collector.push(JSON.stringify({stage:'git-fetch',result:'pass',executionId:nonce})+'\n');
  collector.push('{"omniroute_security_build":"fail","stage":"contract",');collector.push('"category":"assertion","secret":"synthetic","executionId":"'+nonce+'"}\n');
  collector.push('x'.repeat(5000));collector.push('{"stage":"install","result":"pass"}\n');
  assert.deepEqual(collector.summary(),{lastPassedStage:'git-fetch',buildFailure:{stage:'contract',category:'assertion',code:null}});
  assert(!JSON.stringify(collector.summary()).includes('synthetic'));
});
test('stale other-attempt, malicious, missing and partial JSON cannot authorize current diagnostic',()=>{
  const nonce='00000000-0000-4000-8000-000000000001';const collector=diagnosticCollector(nonce);
  collector.push(JSON.stringify({omniroute_security_build:'fail',stage:'install',category:'runtime',executionId:'00000000-0000-4000-8000-000000000002'})+'\n');
  collector.push('{"omniroute_security_build":"fail","stage":"install","category":"runtime"}\n');
  collector.push(JSON.stringify({omniroute_security_build:'fail',stage:'synthetic-secret-marker',category:'runtime',executionId:nonce})+'\n');
  collector.push('{"omniroute_security_build":"fail","stage":"install"');
  assert.deepEqual(collector.summary(),{lastPassedStage:null,buildFailure:null});
});
