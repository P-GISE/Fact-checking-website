import { spawnSync } from 'node:child_process';
import { isolatedEnv } from './rebuild.mjs';
const script = `
try { await import('@swc/core');console.log(JSON.stringify({swc:'pass'})); }
catch(error) { const classify=(e)=>({code:e.code??'unknown',cachePermissionFailure:/DACL|permission|writable|SWC_NATIVE_BINDING_CACHE/i.test(e.message)}); console.log(JSON.stringify({swc:'fail',...classify(error),causes:(Array.isArray(error.cause)?error.cause:[error.cause]).filter(Boolean).map(classify),rawOutputSaved:false})); }
`;
const result = spawnSync(process.execPath, ['--input-type=module', '-e', script], { cwd: new URL('../../../.tools/omniroute-security-build/source/', import.meta.url), env: isolatedEnv(), encoding: 'utf8', windowsHide: true });
process.stdout.write(result.stdout || JSON.stringify({swc:'spawn_failed'}));
