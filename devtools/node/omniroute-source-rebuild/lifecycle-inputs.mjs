import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {existsSync,lstatSync,readFileSync,readdirSync,realpathSync} from 'node:fs';
import {join,resolve} from 'node:path';
import {installedTreeDigest} from './installed-tree.mjs';
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const plugin='@omniroute/opencode-plugin';
const cli='bin/omniroute.mjs';
const native='src/mitm/tproxy/native/build';
export const nextEnvText=['/// <reference types="next" />','/// <reference types="next/image-types/global" />','import "./.build/next/types/routes.d.ts";','import "./.build/next/types/root-params.d.ts";','','// NOTE: This file should not be edited','// see https://nextjs.org/docs/app/api-reference/config/typescript for more information.',''].join('\n');
export const lifecycleAssertionReasons=['lifecycle_regular_file_required','lifecycle_regular_directory_required','lifecycle_env_template_ambiguous','lifecycle_env_salt_invalid','lifecycle_env_template_changed','lifecycle_package_name_invalid','lifecycle_install_dist_shape','lifecycle_unexpected_install_package','lifecycle_install_package_missing','lifecycle_install_copy_changed','lifecycle_binding_changed','lifecycle_phase_invalid','lifecycle_env_seal_changed','lifecycle_cli_changed','lifecycle_plugin_seal_missing','lifecycle_plugin_changed','lifecycle_plugin_output_shape','lifecycle_install_dist_changed','lifecycle_plugin_exists_before_packaging','lifecycle_cli_phase_invalid','lifecycle_compiler_symlink','lifecycle_compiler_special_file','lifecycle_node_gyp_pin','lifecycle_node_gyp_bin','lifecycle_next_env_changed','lifecycle_compiler_changed','lifecycle_mdx_shape','lifecycle_native_changed','lifecycle_native_copy_changed','lifecycle_plugin_dependencies_remaining','lifecycle_output_exists_before_phase'];
function regular(root,path){assert(lstatSync(join(root,path)).isFile()&&!lstatSync(join(root,path)).isSymbolicLink(),'lifecycle_regular_file_required');return readFileSync(join(root,path));}
function directory(root,path){assert(lstatSync(join(root,path)).isDirectory()&&!lstatSync(join(root,path)).isSymbolicLink(),'lifecycle_regular_directory_required');}
function noLinks(path){for(const entry of readdirSync(path,{withFileTypes:true})){assert(!entry.isSymbolicLink(),'lifecycle_compiler_symlink');if(entry.isDirectory())noLinks(join(path,entry.name));else assert(entry.isFile(),'lifecycle_compiler_special_file');}}
export function offlineBuildEnv(env){return {...env,npm_config_offline:'true'};}
export function verifyLocalNodeGyp(root,policy,resolveBin=realpathSync){
  const lock=JSON.parse(regular(root,'package-lock.json'));const pinned=lock.packages['node_modules/node-gyp'];const installed=JSON.parse(regular(root,'node_modules/node-gyp/package.json'));
  assert.equal(pinned.version,policy.version,'lifecycle_node_gyp_pin');assert.equal(pinned.integrity,policy.integrity,'lifecycle_node_gyp_pin');assert.equal(installed.version,pinned.version,'lifecycle_node_gyp_pin');assert.equal(installed.bin['node-gyp'],'bin/node-gyp.js','lifecycle_node_gyp_pin');
  const entry=join(root,'node_modules/node-gyp/bin/node-gyp.js');regular(root,'node_modules/node-gyp/bin/node-gyp.js');assert.equal(resolve(resolveBin(join(root,'node_modules/.bin/node-gyp'))),resolve(entry),'lifecycle_node_gyp_bin');
}
function bind(binding){assert.match(binding.executionId,/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);assert.match(binding.sourceCommit,/^[a-f0-9]{40}$/);assert.match(binding.planSha256,/^[a-f0-9]{64}$/);}
export function validateGeneratedEnv(root){
  const template=regular(root,'.env.example').toString('utf8');const actual=regular(root,'.env').toString('utf8');
  const blanks=[...template.matchAll(/^MACHINE_ID_SALT=\s*$/gm)];assert(blanks.length<=1,'lifecycle_env_template_ambiguous');
  if(blanks.length){const salts=[...actual.matchAll(/^MACHINE_ID_SALT=(omniroute-[a-f0-9]{16})$/gm)];assert.equal(salts.length,1,'lifecycle_env_salt_invalid');assert.equal(actual,template.replace(/^MACHINE_ID_SALT=\s*$/m,`MACHINE_ID_SALT=${salts[0][1]}`),'lifecycle_env_template_changed');}
  else assert.equal(actual,template,'lifecycle_env_template_changed');
  return sha(Buffer.from(actual));
}
function packages(root){
  const base=join(root,'node_modules');const allowed=new Set(['sql.js','node-machine-id']);const seeds=['@atjsh/llmlingua-2','js-tiktoken'];
  const queue=seeds.every(name=>existsSync(join(base,name)))?[...seeds]:[];
  while(queue.length){const name=queue.shift();assert(/^(?:@[a-z0-9_.-]+\/)?[a-z0-9_.-]+$/i.test(name),'lifecycle_package_name_invalid');if(allowed.has(name)||!existsSync(join(base,name)))continue;allowed.add(name);const manifest=JSON.parse(readFileSync(join(base,name,'package.json'),'utf8'));queue.push(...Object.keys({...manifest.dependencies,...manifest.optionalDependencies}));}
  return allowed;
}
function copiedInstallDist(root){
  directory(root,'dist');assert.deepEqual(readdirSync(join(root,'dist')).sort(),['node_modules'],'lifecycle_install_dist_shape');directory(root,'dist/node_modules');
  const actual=[];for(const name of readdirSync(join(root,'dist/node_modules'))){if(name.startsWith('@')){directory(root,`dist/node_modules/${name}`);for(const child of readdirSync(join(root,'dist/node_modules',name)))actual.push(`${name}/${child}`);}else actual.push(name);}
  const allowed=packages(root);assert(actual.every(name=>allowed.has(name)),'lifecycle_unexpected_install_package');
  for(const name of allowed){assert(actual.includes(name),'lifecycle_install_package_missing');directory(root,`dist/node_modules/${name}`);assert.deepEqual(installedTreeDigest(join(root,'dist/node_modules',name),root,[]),installedTreeDigest(join(root,'node_modules',name),root,[]),'lifecycle_install_copy_changed');}
  return installedTreeDigest(join(root,'dist'),root,[]);
}
export function captureInstalledLifecycle(root,binding){bind(binding);for(const path of ['.source','next-env.d.ts',native,'.build',`${plugin}/node_modules`,`${plugin}/dist`])assert(!existsSync(join(root,path)),'lifecycle_output_exists_before_phase');return {schema:1,phase:'installed',binding:{...binding},originalCliSha256:sha(regular(root,cli)),envSha256:validateGeneratedEnv(root),installDist:copiedInstallDist(root)};}
export function verifyLifecycle(root,seal,binding){
  bind(binding);assert.equal(seal.schema,1);assert.deepEqual(seal.binding,binding,'lifecycle_binding_changed');assert(['installed','built','packaged'].includes(seal.phase),'lifecycle_phase_invalid');assert.equal(validateGeneratedEnv(root),seal.envSha256,'lifecycle_env_seal_changed');
  const exactFiles={'.env':seal.envSha256};const directories={};const patches={};
  if(seal.phase!=='installed'){
    assert.deepEqual(Object.keys(seal.compilerOutputs??{}),['.source',native],'lifecycle_compiler_changed');
    assert.equal(regular(root,'next-env.d.ts').toString('utf8'),nextEnvText,'lifecycle_next_env_changed');assert.equal(sha(regular(root,'next-env.d.ts')),seal.nextEnvSha256,'lifecycle_next_env_changed');exactFiles['next-env.d.ts']=seal.nextEnvSha256;
    for(const path of ['.source',native]){directory(root,path);noLinks(join(root,path));assert.deepEqual(installedTreeDigest(join(root,path),root,[]),seal.compilerOutputs?.[path],'lifecycle_compiler_changed');directories[path]=seal.compilerOutputs[path];}
    assert.deepEqual(readdirSync(join(root,'.source')).sort(),['browser.ts','dynamic.ts','server.ts','source.config.mjs'],'lifecycle_mdx_shape');
    assert.equal(sha(regular(root,`${native}/Release/transparent.node`)),seal.nativeRuntimeSha256,'lifecycle_native_changed');
    const destination=seal.phase==='packaged'?`dist/${native}/Release/transparent.node`:`.build/next/standalone/${native}/Release/transparent.node`;
    assert.equal(sha(regular(root,destination)),seal.nativeRuntimeSha256,'lifecycle_native_copy_changed');
  }
  if(seal.phase==='packaged'){
    assert.deepEqual(Object.keys(seal.pluginOutputs??{}),[`${plugin}/dist`],'lifecycle_plugin_output_shape');assert(!existsSync(join(root,plugin,'node_modules')),'lifecycle_plugin_dependencies_remaining');
    assert.match(seal.originalCliSha256,/^[a-f0-9]{64}$/);assert.equal(sha(regular(root,cli)),seal.generatedCliSha256,'lifecycle_cli_changed');patches[cli]=seal.generatedCliSha256;
    for(const path of [`${plugin}/dist`]){assert(seal.pluginOutputs?.[path],'lifecycle_plugin_seal_missing');directory(root,path);assert.deepEqual(installedTreeDigest(join(root,path),root,[]),seal.pluginOutputs[path],'lifecycle_plugin_changed');directories[path]=seal.pluginOutputs[path];}
    assert.deepEqual(readdirSync(join(root,plugin,'dist')).sort(),['index.d.ts','index.js'],'lifecycle_plugin_output_shape');
  }
  return {exactFiles,directories,patches};
}
export function verifyInstalledLifecycle(root,seal,binding){assert.equal(seal.phase,'installed','lifecycle_phase_invalid');verifyLifecycle(root,seal,binding);assert.deepEqual(copiedInstallDist(root),seal.installDist,'lifecycle_install_dist_changed');}
export function authorizeBuildTransition(root,seal,binding){verifyInstalledLifecycle(root,seal,binding);for(const path of ['.source','next-env.d.ts',native,'.build',`${plugin}/node_modules`,`${plugin}/dist`])assert(!existsSync(join(root,path)),'lifecycle_output_exists_before_phase');return {phase:'full-build-authorized',binding:{...binding}};}
export function captureBuiltLifecycle(root,seal,binding,authorization){assert.equal(authorization.phase,'full-build-authorized','lifecycle_phase_invalid');assert.deepEqual(authorization.binding,binding,'lifecycle_binding_changed');verifyLifecycle(root,seal,binding);assert.equal(sha(regular(root,cli)),seal.originalCliSha256,'lifecycle_cli_changed');const compilerOutputs={};for(const path of ['.source',native]){directory(root,path);noLinks(join(root,path));compilerOutputs[path]=installedTreeDigest(join(root,path),root,[]);}const result={...seal,phase:'built',compilerOutputs,nextEnvSha256:sha(regular(root,'next-env.d.ts')),nativeRuntimeSha256:sha(regular(root,`${native}/Release/transparent.node`))};verifyLifecycle(root,result,binding);return result;}
export function authorizeCliTransition(root,seal,binding){verifyLifecycle(root,seal,binding);assert.equal(seal.phase,'built','lifecycle_phase_invalid');assert.equal(sha(regular(root,cli)),seal.originalCliSha256,'lifecycle_cli_changed');assert(!existsSync(join(root,plugin,'node_modules'))&&!existsSync(join(root,plugin,'dist')),'lifecycle_plugin_exists_before_packaging');return {binding:{...binding},originalCliSha256:seal.originalCliSha256,phase:'package-cli-authorized'};}
export function capturePackagedLifecycle(root,seal,binding,authorization){
  assert.equal(authorization.phase,'package-cli-authorized','lifecycle_cli_phase_invalid');assert.deepEqual(authorization.binding,binding,'lifecycle_binding_changed');assert.equal(authorization.originalCliSha256,seal.originalCliSha256,'lifecycle_cli_changed');verifyLifecycle(root,seal,binding);
  assert.equal(seal.phase,'built','lifecycle_phase_invalid');const pluginOutputs={};for(const path of [`${plugin}/dist`]){directory(root,path);pluginOutputs[path]=installedTreeDigest(join(root,path),root,[]);}
  const result={...seal,phase:'packaged',originalCliSha256:authorization.originalCliSha256,generatedCliSha256:sha(regular(root,cli)),pluginOutputs};verifyLifecycle(root,result,binding);return result;
}
