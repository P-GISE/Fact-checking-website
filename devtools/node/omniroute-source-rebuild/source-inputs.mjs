import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { lstatSync, readFileSync } from 'node:fs';
import { dirname, join, resolve, sep } from 'node:path';
const sha = (bytes) => createHash('sha256').update(bytes).digest('hex');
export const gitBlob = (bytes) => createHash('sha1').update(`blob ${bytes.length}\0`).update(bytes).digest('hex');

export function verifyTrackedFiles(root, entries, patches) {
  const checked = [];
  for (const {path, blob, mode} of entries) {
    assert(['100644','100755'].includes(mode), 'unsupported_source_entry_mode');
    const target=resolve(root,path);assert(target.startsWith(resolve(root)+sep),'source_path_escape');
    for(let current=target;current!==resolve(root);current=dirname(current)) assert(!lstatSync(current).isSymbolicLink(),'source_symlink');
    const bytes=readFileSync(target);
    if(Object.hasOwn(patches,path)) assert.equal(sha(bytes),patches[path],'unexpected_dependency_overlay_bytes');
    else assert.equal(gitBlob(bytes),blob,'tracked_source_bytes_changed');
    checked.push([path,sha(bytes)]);
  }
  assert(Object.keys(patches).every((path)=>entries.some((entry)=>entry.path===path)),'overlay_target_not_tracked');
  return {files:checked.length,sha256:sha(JSON.stringify(checked))};
}

export function verifyUntrackedPaths(paths, sealedDirectories) {
  for(const path of paths) assert(Object.keys(sealedDirectories).some((dir)=>path===`${dir}/`||path.startsWith(`${dir}/`)),'unexpected_untracked_or_ignored_source_input');
}

export function verifySealBoundaries(seals) {
  assert(Object.hasOwn(seals,'node_modules'),'installed_dependencies_seal_required');
  for(const [directory,digest]of Object.entries(seals)) {
    assert(['node_modules','.source'].includes(directory),'unexpected_install_seal_boundary');
    assert(Number.isSafeInteger(digest.files)&&digest.files>0&&/^[a-f0-9]{64}$/.test(digest.sha256),'invalid_install_seal');
  }
}

export function verifySourceInputs(root, commit, patches, seals, treeDigest, env,generatedOutputs=[]) {
  assert(generatedOutputs.every(path=>['.build','dist'].includes(path)),'unexpected_generated_output_boundary');
  verifySealBoundaries(seals);
  const git=(args)=>execFileSync('git',['--no-replace-objects',...args],{cwd:root,env,windowsHide:true,maxBuffer:16*1024*1024});
  const entries=git(['ls-tree','-rz','--full-tree',commit]).toString('utf8').split('\0').filter(Boolean).map((line)=>{
    const tab=line.indexOf('\t');const [mode,type,blob]=line.slice(0,tab).split(' ');assert.equal(type,'blob','non_blob_source_entry');return{mode,blob,path:line.slice(tab+1)};
  });
  const tracked=verifyTrackedFiles(root,entries,patches);
  const paths=[...git(['ls-files','--others','--exclude-standard','--directory','-z']).toString('utf8').split('\0'),...git(['ls-files','--others','--ignored','--exclude-standard','--directory','-z']).toString('utf8').split('\0')].filter(Boolean);
  verifyUntrackedPaths(paths,{...seals,...Object.fromEntries(generatedOutputs.map(path=>[path,true]))});
  for(const [directory,expected]of Object.entries(seals)) assert.deepEqual(treeDigest(join(root,directory)),expected,'installed_input_tree_changed');
  return {tracked,untrackedBoundaries:Object.keys(seals),strictRawGitBlobBytes:true};
}
