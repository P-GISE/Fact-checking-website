import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,writeFileSync,rmSync,readFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {canonicalArchiveArgs,canonicalGitEnv,verifyCommitTree} from './archive-policy.mjs';
test('canonical archive ignores ambient CRLF, eol, tar umask without modifying Git configuration',()=>{
  const root=mkdtempSync(join(tmpdir(),'omni-archive-'));const git=args=>execFileSync('git',args,{cwd:root,env:canonicalGitEnv(process.env),stdio:['ignore','pipe','pipe']});
  try{git(['init']);writeFileSync(join(root,'a.txt'),'one\ntwo\n');git(['-c','core.autocrlf=false','add','a.txt']);git(['-c','user.name=Synthetic','-c','user.email=synthetic@example.invalid','commit','-m','synthetic']);
    const commit=git(['rev-parse','HEAD']).toString().trim();let expected;
    for(const mode of ['true','false'])for(const mask of ['0077','0022']){
      git(['config','core.autocrlf',mode]);git(['config','core.eol','crlf']);git(['config','tar.umask',mask]);
      const before=readFileSync(join(root,'.git/config'));const archive=git(canonicalArchiveArgs(commit));const digest=createHash('sha256').update(archive).digest('hex');expected??=digest;assert.equal(digest,expected);assert.deepEqual(readFileSync(join(root,'.git/config')),before);
    }
  }finally{rmSync(root,{recursive:true,force:true});}
});
test('fixed commit/tree mismatch is rejected and plan remains bound to receipt',()=>{
  const policy={commit:'a'.repeat(40),sourceTree:'b'.repeat(40)};verifyCommitTree(policy.commit,policy.sourceTree,policy);
  assert.throws(()=>verifyCommitTree('c'.repeat(40),policy.sourceTree,policy));assert.throws(()=>verifyCommitTree(policy.commit,'c'.repeat(40),policy));
  assert.equal(canonicalGitEnv({GIT_NO_REPLACE_OBJECTS:'0'}).GIT_NO_REPLACE_OBJECTS,'1');
});
