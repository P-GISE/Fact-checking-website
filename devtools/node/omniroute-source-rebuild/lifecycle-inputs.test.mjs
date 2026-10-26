import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,mkdirSync,writeFileSync,readFileSync,cpSync,rmSync,symlinkSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join,dirname} from 'node:path';
import {execFileSync} from 'node:child_process';
import {verifyPristineSource,verifySourceInputs} from './source-inputs.mjs';
import {installedTreeDigest} from './installed-tree.mjs';
import {captureInstalledLifecycle,verifyInstalledLifecycle,authorizeBuildTransition,captureBuiltLifecycle,authorizeCliTransition,capturePackagedLifecycle,verifyLifecycle,nextEnvText,verifyLocalNodeGyp,offlineBuildEnv} from './lifecycle-inputs.mjs';
function fixture(){
  const root=mkdtempSync(join(tmpdir(),'omni-lifecycle-'));const write=(path,value)=>{mkdirSync(dirname(join(root,path)),{recursive:true});writeFileSync(join(root,path),value);};
  write('.gitignore','node_modules/\ndist/\n.build/\n.env\n');write('.env.example','DEFAULT=synthetic\nMACHINE_ID_SALT=\n');write('bin/omniroute.mjs','original-cli');write('bin/omniroute.ts','original-input');write('@omniroute/opencode-plugin/package-lock.json','original-lock');
  write('src/mitm/tproxy/native/binding.gyp','synthetic-native-input');
  const git=args=>execFileSync('git',['-c','core.autocrlf=false',...args],{cwd:root,encoding:'utf8',stdio:['ignore','pipe','pipe']});git(['init']);git(['add','.']);git(['-c','user.name=Synthetic','-c','user.email=synthetic@example.invalid','commit','-m','synthetic']);
  const commit=git(['rev-parse','HEAD']).trim();const binding={executionId:'00000000-0000-4000-8000-000000000001',sourceCommit:commit,planSha256:'b'.repeat(64)};
  const digest=path=>installedTreeDigest(path,root,[]);const clean=()=>rmSync(root,{recursive:true,force:true});
  const install=()=>{for(const name of ['sql.js','node-machine-id']){write(`node_modules/${name}/package.json`,JSON.stringify({name}));write(`node_modules/${name}/index.js`,'synthetic-package');cpSync(join(root,'node_modules',name),join(root,'dist/node_modules',name),{recursive:true});}write('.env','DEFAULT=synthetic\nMACHINE_ID_SALT=omniroute-0000000000000001');return {node_modules:digest(join(root,'node_modules'))};};
  const check=(seals,seal,outputs=['dist'])=>verifySourceInputs(root,commit,{},seals,digest,process.env,outputs,seal?{seal,binding}:null);
  const build=installed=>{const authorization=authorizeBuildTransition(root,installed,binding);for(const file of ['browser.ts','dynamic.ts','server.ts','source.config.mjs'])write(`.source/${file}`,'synthetic-mdx');write('next-env.d.ts',nextEnvText);write('src/mitm/tproxy/native/build/Release/transparent.node','synthetic-native');write('.build/next/standalone/src/mitm/tproxy/native/build/Release/transparent.node','synthetic-native');write('dist/server.js','synthetic-standalone');return captureBuiltLifecycle(root,installed,binding,authorization);};
  return {root,write,commit,binding,digest,clean,install,check,build};
}
test('deterministic lifecycle accepts only pristine→validated install→authorized CLI/plugin outputs',()=>{
  const f=fixture();try{
    verifyPristineSource(f.root,f.commit,{},process.env);const seals=f.install();assert.throws(()=>f.check(seals,null));
    const installed=captureInstalledLifecycle(f.root,f.binding);verifyInstalledLifecycle(f.root,installed,f.binding);f.check(seals,installed);
    assert.throws(()=>authorizeCliTransition(f.root,installed,f.binding));const built=f.build(installed);f.check(seals,built,['.build','dist']);
    const authorization=authorizeCliTransition(f.root,built,f.binding);f.write('bin/omniroute.mjs','generated-cli');
    assert.throws(()=>f.check(seals,built,['.build','dist']));
    f.write('@omniroute/opencode-plugin/dist/index.js','synthetic-plugin');f.write('@omniroute/opencode-plugin/dist/index.d.ts','synthetic-types');f.write('dist/src/mitm/tproxy/native/build/Release/transparent.node','synthetic-native');
    rmSync(join(f.root,'bin/omniroute.mjs'));assert.throws(()=>capturePackagedLifecycle(f.root,built,f.binding,authorization));f.write('bin/omniroute.mjs','generated-cli');
    assert.throws(()=>capturePackagedLifecycle(f.root,built,f.binding,{...authorization,originalCliSha256:'f'.repeat(64)}));
    const packaged=capturePackagedLifecycle(f.root,built,f.binding,authorization);assert.notEqual(packaged.originalCliSha256,packaged.generatedCliSha256);f.check(seals,packaged,['.build','dist']);
    f.write('bin/omniroute.mjs','generated-cli!');assert.throws(()=>f.check(seals,packaged,['.build','dist']));
  }finally{f.clean();}
});
test('compiler outputs are phase bound and immutable; external compiler links are not traversed',()=>{
  const f=fixture();const outside=mkdtempSync(join(tmpdir(),'omni-native-outside-'));try{f.install();const installed=captureInstalledLifecycle(f.root,f.binding);f.write('next-env.d.ts',nextEnvText);assert.throws(()=>authorizeBuildTransition(f.root,installed,f.binding));rmSync(join(f.root,'next-env.d.ts'));
    const built=f.build(installed);f.write('.source/server.ts','synthetic-mdx!');assert.throws(()=>verifyLifecycle(f.root,built,f.binding));f.write('.source/server.ts','synthetic-mdx');f.write('next-env.d.ts',nextEnvText+'//synthetic-extra');assert.throws(()=>verifyLifecycle(f.root,built,f.binding));f.write('next-env.d.ts',nextEnvText);
    f.write('src/mitm/tproxy/native/build/Release/transparent.node','synthetic-native!');assert.throws(()=>verifyLifecycle(f.root,built,f.binding));
    f.write('src/mitm/tproxy/native/build/Release/transparent.node','synthetic-native');symlinkSync(outside,join(f.root,'src/mitm/tproxy/native/build/node_gyp_bins'),'junction');assert.throws(()=>verifyLifecycle(f.root,built,f.binding),{message:'lifecycle_compiler_symlink'});
  }finally{f.clean();rmSync(outside,{recursive:true,force:true});}
});
test('native local pin and offline environment block remote fallback without disabling build features',()=>{
  const f=fixture();try{const policy={version:'12.4.0',integrity:'synthetic-integrity'};f.write('package-lock.json',JSON.stringify({packages:{'node_modules/node-gyp':policy}}));f.write('node_modules/node-gyp/package.json',JSON.stringify({version:'12.4.0',bin:{'node-gyp':'bin/node-gyp.js'}}));f.write('node_modules/node-gyp/bin/node-gyp.js','synthetic-tool');
    assert.throws(()=>verifyLocalNodeGyp(f.root,policy));verifyLocalNodeGyp(f.root,policy,()=>join(f.root,'node_modules/node-gyp/bin/node-gyp.js'));assert.throws(()=>verifyLocalNodeGyp(f.root,{...policy,version:'other'},()=>join(f.root,'node_modules/node-gyp/bin/node-gyp.js')));assert.throws(()=>verifyLocalNodeGyp(f.root,policy,()=>join(f.root,'outside-tool')));
    assert.deepEqual(offlineBuildEnv({SYNTHETIC:'value'}),{SYNTHETIC:'value',npm_config_offline:'true'});
  }finally{f.clean();}
});
test('preexisting env, arbitrary env content, copied package mutation and unexpected paths fail closed',()=>{
  const f=fixture();try{
    f.write('.env','synthetic-preexisting');assert.throws(()=>verifyPristineSource(f.root,f.commit,{},process.env));rmSync(join(f.root,'.env'));
    const seals=f.install();const installed=captureInstalledLifecycle(f.root,f.binding);
    const env=readFileSync(join(f.root,'.env'));f.write('.env',env.toString()+'EXTRA=synthetic\n');assert.throws(()=>captureInstalledLifecycle(f.root,f.binding));f.write('.env',env);
    f.write('.env',env.toString().replace('0000000000000001','0000000000000002'));assert.throws(()=>verifyLifecycle(f.root,installed,f.binding));f.write('.env',env);
    f.write('dist/node_modules/sql.js/index.js','synthetic-package!');assert.throws(()=>verifyInstalledLifecycle(f.root,installed,f.binding));f.write('dist/node_modules/sql.js/index.js','synthetic-package');
    f.write('dist/unexpected.js','synthetic');assert.throws(()=>captureInstalledLifecycle(f.root,f.binding));rmSync(join(f.root,'dist/unexpected.js'));
    f.write('unexpected.js','synthetic');assert.throws(()=>f.check(seals,installed));rmSync(join(f.root,'unexpected.js'));
    f.write('bin/omniroute.ts','original-input!');assert.throws(()=>f.check(seals,installed));
  }finally{f.clean();}
});
test('nonce, premature plugin outputs, unauthorized phase and tracked lock tampering are rejected',()=>{
  const f=fixture();try{
    const seals=f.install();const installed=captureInstalledLifecycle(f.root,f.binding);
    assert.throws(()=>verifyLifecycle(f.root,installed,{...f.binding,executionId:'00000000-0000-4000-8000-000000000002'}));
    f.write('@omniroute/opencode-plugin/dist/index.js','premature');assert.throws(()=>authorizeCliTransition(f.root,installed,f.binding));assert.throws(()=>f.check(seals,installed));rmSync(join(f.root,'@omniroute/opencode-plugin/dist'),{recursive:true});
    assert.throws(()=>capturePackagedLifecycle(f.root,installed,f.binding,{binding:f.binding,phase:'installed'}));
    f.write('bin/omniroute.mjs','premature-cli');assert.throws(()=>authorizeCliTransition(f.root,installed,f.binding));f.write('bin/omniroute.mjs','original-cli');
    f.write('@omniroute/opencode-plugin/package-lock.json','changed-lock');assert.throws(()=>f.check(seals,installed));
  }finally{f.clean();}
});
