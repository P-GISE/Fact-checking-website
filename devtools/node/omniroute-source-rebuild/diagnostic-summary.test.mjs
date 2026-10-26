import test from 'node:test';
import assert from 'node:assert/strict';
import { diagnosticSummary,diagnosticCollector } from './guarded-linux-build.mjs';
import {contractDiagnostic} from './rebuild.mjs';
import {verifyTrackedFiles,gitBlob,verifyUntrackedPaths} from './source-inputs.mjs';
import {mkdtempSync,writeFileSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';

test('diagnostic retains fixed failure metadata while stripping unknown and sensitive text',()=>{
  assert.deepEqual(diagnosticSummary({omniroute_security_build:'fail',stage:'install',category:'dependency_resolution',code:1,token:'synthetic-not-a-credential',modules:['synthetic']}),{stage:'install',category:'dependency_resolution',code:1});
  assert.equal(diagnosticSummary({omniroute_security_build:'fail',stage:'untrusted-body',category:'runtime',code:1}),null);
  assert.equal(diagnosticSummary({omniroute_security_build:'fail',stage:'contract',category:'untrusted-body',code:1}),null);
  assert.equal(diagnosticSummary({omniroute_security_build:'fail',stage:'contract',category:'assertion',code:'untrusted-body'}),null);
  assert.deepEqual(diagnosticSummary({omniroute_security_build:'fail',stage:'contract',category:'assertion'}),{stage:'contract',category:'assertion',code:null});
});
test('actual raw-input assertion maps to a fixed source phase and reason without exposing values',()=>{
  const root=mkdtempSync(join(tmpdir(),'omni-diagnostic-'));
  try{writeFileSync(join(root,'a.js'),'changed-synthetic-marker');let failure;try{verifyTrackedFiles(root,[{path:'a.js',mode:'100644',blob:gitBlob(Buffer.from('original'))}],{});}catch(error){failure=error;}
    const fixed=contractDiagnostic(failure,'contract-source-inputs');assert.deepEqual(fixed,{stage:'contract-source-inputs',category:'assertion',assertionReason:'tracked_source_bytes_changed'});
    assert.deepEqual(diagnosticSummary({omniroute_security_build:'fail',...fixed}),{...fixed,code:null});assert(!JSON.stringify(fixed).includes('marker'));
  }finally{rmSync(root,{recursive:true,force:true});}
});
test('untracked boundary failures retain only known enum while arbitrary error text is discarded',()=>{
  let failure;try{verifyUntrackedPaths(['synthetic-private-path'],{node_modules:{}});}catch(error){failure=error;}
  assert.equal(contractDiagnostic(failure,'contract-source-inputs').assertionReason,'unexpected_untracked_or_ignored_source_input');
  assert.deepEqual(contractDiagnostic({code:'ERR_ASSERTION',message:'synthetic-secret-marker'},'contract-installed-seal'),{stage:'contract-installed-seal',category:'assertion'});
  assert.equal(diagnosticSummary({omniroute_security_build:'fail',stage:'contract-source-inputs',category:'assertion',assertionReason:'synthetic-secret-marker'}),null);
  assert.throws(()=>contractDiagnostic(failure,'synthetic-secret-marker'));
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
