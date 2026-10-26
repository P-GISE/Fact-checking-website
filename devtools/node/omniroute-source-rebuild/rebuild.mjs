import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { spawn, spawnSync } from 'node:child_process';
import { existsSync, lstatSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { basename, dirname, join, relative, resolve, sep } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { verifySourceInputs } from './source-inputs.mjs';
import { resolveNpmEntry, resolveProfile, assertPinnedNode } from './platform-profile.mjs';
import { installedTreeDigest } from './installed-tree.mjs';
import { verifyGuardAttestation } from './guard-attestation.mjs';
import { canonicalArchiveArgs,canonicalGitEnv,verifyCommitTree } from './archive-policy.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const project = resolve(here, '../../..');
const buildRoot = join(project, '.tools/omniroute-security-build');
const source = join(buildRoot, 'source');
const planPath = join(here, 'plan.json');
const plan = JSON.parse(readFileSync(planPath, 'utf8'));
const deadline = Date.now() + 30 * 60 * 1000;
const npm = resolveNpmEntry(process.execPath);
const heapMb = process.env.OMNIROUTE_REBUILD_HEAP_MB || '4096';
const profile=resolveProfile(process.platform,process.env.OMNIROUTE_REBUILD_PROFILE,heapMb);
export const buildMode = profile.bundler;

export class RebuildFailure extends Error {
  constructor(stage, category, code = null) { super(`${stage}:${category}`); this.stage = stage; this.category = category; this.code = code; }
}

function sha(bytes) { return createHash('sha256').update(bytes).digest('hex'); }

export function confined(root, candidate) {
  const location = resolve(candidate);
  assert(location.startsWith(resolve(root) + sep), 'output_outside_private_build_root');
  for (let current = location; current !== resolve(root); current = dirname(current)) {
    if (existsSync(current)) assert(!lstatSync(current).isSymbolicLink(), 'symlink_in_build_path');
  }
  return location;
}

export function patchManifest(original, policy = plan) {
  assert.equal(original.name, 'omniroute');
  assert.equal(original.version, policy.upstreamVersion);
  assert.equal(original.dependencies.next, '16.3.8');
  const result = structuredClone(original);
  Object.assign(result.dependencies, policy.dependencies);
  Object.assign(result.overrides, policy.overrides);
  // A nested upstream override would otherwise retain DOMPurify's vulnerable range.
  result.overrides['monaco-editor'] = { ...result.overrides['monaco-editor'], dompurify: policy.dependencies.dompurify };
  return result;
}

export function isolatedEnv() {
  const env = {};
  for (const key of ['PATH', 'Path', 'SystemRoot', 'SYSTEMROOT', 'ComSpec', 'PATHEXT', 'TEMP', 'TMP', 'NUMBER_OF_PROCESSORS']) {
    if (process.env[key]) env[key] = process.env[key];
  }
  const home = join(buildRoot, 'home');
  for (const path of [home, join(home, 'roaming'), join(home, 'local'), join(buildRoot, 'data')]) mkdirSync(path, { recursive: true, mode: 0o700 });
  const nativeCache = process.env.OMNIROUTE_REBUILD_NATIVE_CACHE || (process.platform === 'win32' ? join(process.env.USERPROFILE, '.pocketbook-security-swc-20261026') : join(buildRoot, 'swc-native-cache'));
  if (process.platform === 'win32') {
    assert.equal(basename(nativeCache), '.pocketbook-security-swc-20261026');
    assert(existsSync(nativeCache) && !lstatSync(nativeCache).isSymbolicLink(), 'existing_private_native_cache_required');
  } else mkdirSync(nativeCache, { recursive: true, mode: 0o700 });
  return { ...env, HOME: home, USERPROFILE: home, APPDATA: join(home, 'roaming'), LOCALAPPDATA: join(home, 'local'),
    DATA_DIR: join(buildRoot, 'data'), CODEX_HOME: join(home, 'codex'), XDG_CONFIG_HOME: join(home, 'config'),
    XDG_CACHE_HOME: join(home, 'cache'), npm_config_cache: join(buildRoot, 'npm-cache'), SWC_NATIVE_BINDING_CACHE: nativeCache, OMNIROUTE_REBUILD_NATIVE_CACHE: nativeCache,
    CI: 'true', HUSKY: '0', DO_NOT_TRACK: '1', NEXT_TELEMETRY_DISABLED: '1',
    PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD: '1', ONNXRUNTIME_NODE_INSTALL: 'skip', OMNIROUTE_USE_TURBOPACK: buildMode==='webpack'?'0':'1',
    ...(process.env.OMNIROUTE_REBUILD_PROFILE?{OMNIROUTE_REBUILD_PROFILE:process.env.OMNIROUTE_REBUILD_PROFILE,OMNIROUTE_REBUILD_HEAP_MB:heapMb}:{}),
    ...(process.env.OMNIROUTE_REBUILD_ATTEMPT?{OMNIROUTE_REBUILD_ATTEMPT:process.env.OMNIROUTE_REBUILD_ATTEMPT,OMNIROUTE_REBUILD_EXECUTION_ID:process.env.OMNIROUTE_REBUILD_EXECUTION_ID}:{}),
    NODE_OPTIONS: `--max-old-space-size=${profile.heapMb}` };
}

async function run(stage, command, args, options = {}) {
  const remaining = deadline - Date.now();
  if (remaining <= 0) throw new RebuildFailure(stage, 'deadline');
  return new Promise((accept, reject) => {
    const child = spawn(command, args, { cwd: source, env: isolatedEnv(), windowsHide: true, ...options });
    let output = '';
    let stdout = '';
    let overflow = false;
    const collect = (chunk) => { if (output.length < 32 * 1024 * 1024) output += chunk; else { overflow = true; child.kill(); } };
    child.stdout.on('data', (chunk) => { collect(chunk); if (stdout.length < 32 * 1024 * 1024) stdout += chunk; }); child.stderr.on('data', collect);
    const timer = setTimeout(() => {
      if (process.platform === 'win32') spawn('taskkill', ['/PID', String(child.pid), '/T', '/F'], { windowsHide: true, stdio: 'ignore' });
      else child.kill('SIGTERM');
    }, remaining);
    child.on('error', () => { clearTimeout(timer); reject(new RebuildFailure(stage, 'spawn')); });
    child.on('close', (code, signal) => {
      clearTimeout(timer);
      if (code !== 0 || signal || overflow) {
        const category = overflow ? 'output_limit' : signal ? 'terminated' : /Module not found|Cannot find module|Cannot resolve|Can't resolve/.test(output) ? 'module_resolution' : /ERESOLVE|EOVERRIDE/.test(output) ? 'dependency_resolution' : /heap out of memory|Allocation failed/i.test(output) ? 'heap_limit' : 'command_failed';
        const modules = [...output.matchAll(/(?:Cannot find module|Can't resolve) ['"]([@a-zA-Z0-9_.\/-]{1,160})['"]/g)].map((match) => match[1]);
        writeFileSync(join(buildRoot, 'failure.json'), JSON.stringify({ stage, category, code, signal, modules: [...new Set(modules)].slice(0, 20), rawOutputSaved: false }, null, 2));
        reject(new RebuildFailure(stage, category, code));
      } else { process.stdout.write(JSON.stringify({ stage, result: 'pass',executionId:diagnosticExecutionId() }) + '\n'); accept(stdout); }
    });
  });
}

export function treeDigest(root) {
  const entries = [];
  function walk(folder) {
    for (const entry of readdirSync(folder, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
      const path = join(folder, entry.name);
      assert(!entry.isSymbolicLink(), 'bundle_symlink');
      if (entry.isDirectory()) walk(path);
      else { assert(entry.isFile(), 'bundle_special_file'); entries.push([relative(root, path).split(sep).join('/'), sha(readFileSync(path))]); }
    }
  }
  walk(root);
  return { files: entries.length, sha256: sha(JSON.stringify(entries)) };
}

export function verifyReceipt({cacheRoot=buildRoot,sourceRoot=source,requireGuard=true}={}) {
  const receipt = JSON.parse(readFileSync(join(cacheRoot, 'receipt.json'), 'utf8'));
  assert.equal(receipt.schema, 1);
  assert.equal(receipt.platform,process.platform,'receipt_platform_mismatch');assert.equal(receipt.arch,process.arch,'receipt_arch_mismatch');assert.equal(receipt.node,process.version,'receipt_node_mismatch');
  assert.equal(receipt.sourceCommit, plan.commit);
  assert.equal(receipt.overlay, plan.overlay);
  assert.equal(receipt.planSha256, sha(readFileSync(planPath)));
  assert.equal(receipt.nextVersion, plan.dependencies.next);
  assert.equal(receipt.patchedLockSha256, plan.patchedLockSha256);
  assert.equal(receipt.sourceArchiveSha256, plan.sourceArchiveSha256);
  assert.deepEqual(receipt.dist, treeDigest(confined(cacheRoot, join(sourceRoot, 'dist'))));
  assert.deepEqual(receipt.runtimeInputs,installedTreeDigest(confined(cacheRoot,sourceRoot),sourceRoot,[]),'runtime_execution_inputs_changed');
  if(requireGuard){const guard=verifyGuardAttestation(cacheRoot,process.platform,receipt);if(receipt.cliAndHttpSmoke==='pass')assert.equal(receipt.guardAttestationSha256,guard.sha256,'guard_attestation_changed');}
  return receipt;
}

async function main() {
  assertPinnedNode(process.version);
  assert.equal(plan.schema, 1);
  assert.equal(plan.repository, 'https://github.com/cheaper-inference/OmniRoute.git');
  assert.equal(plan.commit, 'ad6f33f66bda34eba98645d3bfdabbde294bc843');
  if (process.argv[2] === '--verify') {
    const receipt = verifyReceipt();
    assert.equal(receipt.cliAndHttpSmoke, 'pass', 'runtime_smoke_not_passed');
    process.stdout.write('omniroute_security_receipt=verified\n'); return;
  }
  const resume = process.argv[2] === '--resume-installed';
  assert(process.argv.length === 2 || (resume && process.argv.length === 3), 'unexpected_arguments');
  mkdirSync(buildRoot, { recursive: true, mode: 0o700 });
  confined(project, buildRoot); confined(buildRoot, source);
  assert(existsSync(npm), 'npm_js_entry_required');
  if (existsSync(join(buildRoot, 'receipt.json'))) { verifyReceipt(); return; }
  if (!existsSync(source)) {
    mkdirSync(source, { mode: 0o700 });
    await run('git-init', 'git', ['init']);
    await run('git-origin', 'git', ['remote', 'add', 'origin', plan.repository]);
    await run('git-fetch', 'git', ['fetch', '--depth', '1', 'origin', plan.commit]);
    await run('git-checkout', 'git', ['-c', 'core.autocrlf=false', '-c', 'core.eol=lf', 'checkout', '--detach', 'FETCH_HEAD']);
  }
  const actualCommit=(await run('source-pin', 'git', ['--no-replace-objects','rev-parse', 'HEAD'],{env:canonicalGitEnv(isolatedEnv())})).trim();
  const actualTree=(await run('source-tree', 'git', ['--no-replace-objects','rev-parse', `${plan.commit}^{tree}`],{env:canonicalGitEnv(isolatedEnv())})).trim();
  verifyCommitTree(actualCommit,actualTree,plan);
  const archiveHash = await new Promise((accept, reject) => {
    const hash = createHash('sha256');
    const archive = spawn('git', canonicalArchiveArgs(plan.commit), { cwd: source, env: canonicalGitEnv(isolatedEnv()), windowsHide: true });
    archive.stdout.on('data', (chunk) => hash.update(chunk)); archive.stderr.on('data', () => {});
    archive.once('error', () => reject(new RebuildFailure('source-archive', 'spawn')));
    archive.once('close', (code) => code === 0 ? accept(hash.digest('hex')) : reject(new RebuildFailure('source-archive', 'archive', code)));
  });
  assert.equal(archiveHash, plan.sourceArchiveSha256, 'unexpected_source_archive');
  const original = await run('source-manifest', 'git', ['show', `${plan.commit}:package.json`]);
  const patched = JSON.stringify(patchManifest(JSON.parse(original)), null, 2) + '\n';
  const lockPatch = join(here, 'source-lock.patch');
  assert.equal(sha(readFileSync(lockPatch)), plan.lockPatchSha256, 'lock_patch_changed');
  if (!resume) {
    assert.equal((await run('source-clean', 'git', ['status', '--porcelain', '--untracked-files=no'])).trim(), '', 'source_has_existing_edits');
    writeFileSync(join(source, 'package.json'), patched);
    // Git's Windows autocrlf checkout must not change the pinned npm lock bytes.
    writeFileSync(join(source, 'package-lock.json'), await run('source-lock', 'git', ['show', `${plan.commit}:package-lock.json`]));
    await run('locked-patch-check', 'git', ['apply', '--check', lockPatch]);
    await run('locked-patch', 'git', ['apply', lockPatch]);
  }
  assert.equal(readFileSync(join(source, 'package.json'), 'utf8'), patched, 'unexpected_manifest_overlay');
  assert.equal(sha(readFileSync(join(source, 'package-lock.json'))), plan.patchedLockSha256, 'unexpected_lock_overlay');
  if (!resume) await run('install', process.execPath, [npm, 'ci', '--no-audit', '--no-fund']);
  if (!existsSync(join(source, 'node_modules/better-sqlite3/package.json'))) {
    // Upstream's preflight recommendation: explicitly install the locked optional package.
    // Keep its real native prebuild and all checks; do not substitute a stub or skip the gate.
    await run('native-hydration', process.execPath, [npm, 'install', '--no-save', '--package-lock=false', '--foreground-scripts', '--no-audit', '--no-fund', 'better-sqlite3@13.0.3']);
  }
  assert.equal(sha(readFileSync(join(source, 'package-lock.json'))), plan.patchedLockSha256, 'lock_changed_during_install');
  await run('native-sqlite', process.execPath, ['--input-type=module', '-e', "import Database from 'better-sqlite3';const db=new Database(':memory:');if(db.prepare('SELECT 1 AS n').get().n!==1)process.exit(1);db.close();"]);
  const installSealPath = join(buildRoot, 'installed-inputs-seal.json');
  const workspacePaths=['open-sse','packages/browser-pool'];
  const inputDigest=folder=>installedTreeDigest(folder,source,workspacePaths);
  if (!resume) {
    const directories = {};
    for (const directory of ['node_modules', '.source']) if (existsSync(join(source, directory))) directories[directory] = inputDigest(join(source, directory));
    writeFileSync(installSealPath, JSON.stringify({ sourceCommit: plan.commit, planSha256: sha(readFileSync(planPath)),platform:process.platform,arch:process.arch,node:process.version,directories }, null, 2) + '\n', { flag: 'wx' });
  }
  // A pre-seal old cache is deliberately ineligible for resume. Re-clone/reinstall is required.
  const installSeal = JSON.parse(readFileSync(installSealPath, 'utf8'));
  assert.equal(installSeal.sourceCommit, plan.commit);
  assert.equal(installSeal.planSha256, sha(readFileSync(planPath)));
  assert.equal(installSeal.platform,process.platform);assert.equal(installSeal.arch,process.arch);assert.equal(installSeal.node,process.version);
  const sourceInputs = verifySourceInputs(source, plan.commit, { 'package.json': sha(patched), 'package-lock.json': plan.patchedLockSha256 }, installSeal.directories, inputDigest, isolatedEnv());
  const audit = JSON.parse(await run('runtime-audit', process.execPath, [npm, 'audit', '--omit=dev', '--json']));
  assert.equal(audit.metadata.vulnerabilities.total, 0, 'runtime_advisories_remain');
  await run(`full-${buildMode}-build`, process.execPath, [npm, 'run', 'build']);
  await run('postbuild-workers', process.execPath, ['scripts/build/colocate-standalone.mjs']);
  await run('package-cli', process.execPath, [npm, 'run', 'build:cli']);
  const dist = confined(buildRoot, join(source, 'dist'));
  assert(existsSync(join(dist, 'server.js')), 'missing_standalone_server');
  const standaloneNext = JSON.parse(readFileSync(join(dist, 'node_modules/next/package.json'), 'utf8'));
  assert.equal(standaloneNext.version, plan.dependencies.next);
  // Recheck source/dependency inputs after trusted build scripts, before sealing what the CLI executes.
  const finalSourceInputs=verifySourceInputs(source,plan.commit,{ 'package.json':sha(patched),'package-lock.json':plan.patchedLockSha256 },installSeal.directories,inputDigest,isolatedEnv(),['.build','dist']);
  const receipt = { schema: 1, overlay: plan.overlay, sourceCommit: plan.commit, sourceRepository: plan.repository,
    attempt:process.env.OMNIROUTE_REBUILD_ATTEMPT??'unattested-direct-build',executionId:process.env.OMNIROUTE_REBUILD_EXECUTION_ID??null,profile:profile.name,
    sourceArchiveSha256: archiveHash, sourceInputs,finalSourceInputs,runtimeInputs:installedTreeDigest(source,source,[]),
    sourceManifestSha256: sha(original), patchedManifestSha256: sha(patched), patchedLockSha256: sha(readFileSync(join(source, 'package-lock.json'))),
    planSha256: sha(readFileSync(planPath)), nextVersion: standaloneNext.version, build: `full upstream build; ${buildMode}; no contributor/backend profile`,
    node: process.version, platform:process.platform,arch:process.arch,dist: treeDigest(dist), cliAndHttpSmoke: 'pending; not inferred from build', rawOutputSaved: false };
  writeFileSync(join(buildRoot, 'receipt.json'), JSON.stringify(receipt, null, 2) + '\n');
  verifyReceipt({requireGuard:false});
  process.stdout.write(JSON.stringify({ omniroute_security_build: 'pass', distFiles: receipt.dist.files, next: receipt.nextVersion, smoke: 'pending' }) + '\n');
}

function diagnosticExecutionId(){const id=process.env.OMNIROUTE_REBUILD_EXECUTION_ID;return typeof id==='string'&&/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(id)?id:null;}
if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  main().catch((error) => {
    const result = error instanceof RebuildFailure ? { stage: error.stage, category: error.category, code: error.code } : { stage: 'contract', category: error.code === 'ERR_ASSERTION' ? 'assertion' : 'runtime' };
    process.stderr.write(JSON.stringify({ omniroute_security_build: 'fail', ...result, executionId:diagnosticExecutionId(),rawOutputSaved: false }) + '\n');
    process.exitCode = 1;
  });
}
