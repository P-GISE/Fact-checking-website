import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { createHash } from 'node:crypto';
import { gitBlob, verifyTrackedFiles, verifyUntrackedPaths, verifySealBoundaries } from './source-inputs.mjs';
test('tracked source mutation and dependency overlay changes fail closed',()=>{
  const root=mkdtempSync(join(tmpdir(),'omniroute-source-input-'));const original=Buffer.from('export const value=1;\n');
  writeFileSync(join(root,'app.mjs'),original);const entries=[{path:'app.mjs',mode:'100644',blob:gitBlob(original)}];
  assert.equal(verifyTrackedFiles(root,entries,{}).files,1);
  writeFileSync(join(root,'app.mjs'),'export const value=2;\n');assert.throws(()=>verifyTrackedFiles(root,entries,{}));
  const patch=createHash('sha256').update('approved').digest('hex');assert.throws(()=>verifyTrackedFiles(root,entries,{'app.mjs':patch}));
});
test('raw CRLF mismatch is rejected rather than hidden by git normalization',()=>{
  const root=mkdtempSync(join(tmpdir(),'omniroute-source-eol-'));writeFileSync(join(root,'a.js'),'a\r\n');
  assert.throws(()=>verifyTrackedFiles(root,[{path:'a.js',mode:'100644',blob:gitBlob(Buffer.from('a\n'))}],{}));
});
test('untracked source, env, build leftovers and boundary-prefix confusion are rejected',()=>{
  const seals={'node_modules':{files:1,sha256:'example'}};verifyUntrackedPaths(['node_modules/'],seals);
  for(const path of ['src/evil.ts','.env','.build/','node_modules-evil/a.js']) assert.throws(()=>verifyUntrackedPaths([path],seals));
});
test('seal cannot authorize arbitrary ignored folders or traverse outside source',()=>{
  const good={files:1,sha256:'a'.repeat(64)};verifySealBoundaries({node_modules:good});
  assert.throws(()=>verifySealBoundaries({node_modules:good,'../outside':good}));
  assert.throws(()=>verifySealBoundaries({node_modules:good,'.build':good}));
  assert.throws(()=>verifySealBoundaries({}));
});
