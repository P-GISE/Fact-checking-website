import {it, expect} from 'vitest';
import {spawnSync} from 'node:child_process';

const boot = `
import {registerHooks} from 'node:module';
registerHooks({load(url, context, nextLoad) {
  if (url.endsWith('/src/db.ts') || url.endsWith('/src/db.js')) return {format:'module',shortCircuit:true,
    source:'export const pool={}; export async function migrate(){throw Error("MIGRATION_CALLED");}'};
  if (url.endsWith('/src/app.ts') || url.endsWith('/src/app.js')) return {format:'module',shortCircuit:true,
    source:'export function createApp() { throw Error("UNEXPECTED_HTTP"); }'};
  if (url.includes('/node_modules/redis/')) return {format:'module',shortCircuit:true,
    source:'export const createClient=()=>({on(){}, async connect(){throw Error("STARTUP_WITHOUT_MIGRATION");}})'};
  return nextLoad(url, context);
}});
try { await import('./src/server.ts'); } catch(error) { console.log(error.message); }
`;
for (const [mode, expected] of [['false','STARTUP_WITHOUT_MIGRATION'], ['true','MIGRATION_CALLED'], [undefined,'MIGRATION_CALLED']] as const) {
  it(`startup migration setting ${mode ?? 'default'} has the explicit database boundary`, () => {
    const env={...process.env, NODE_ENV:'production', FACTLENS_LOCAL_ONLY:'true', FACTLENS_AUTH_MODE:'local'};
    if (mode === undefined) delete env.FACTLENS_AUTO_MIGRATE;
    else env.FACTLENS_AUTO_MIGRATE=mode;
    const result=spawnSync(process.execPath,['--import','tsx','--input-type=module','-e',boot],{env,encoding:'utf8'});
    expect(result.status).toBe(0);
    expect(result.stdout.trim()).toBe(expected);
    if (mode==='false') expect(result.stdout).not.toContain('MIGRATION_CALLED');
  });
}

it('explicit migration CLI still migrates and closes the pool when startup migration is disabled', () => {
  const explicit=boot.replace('export const pool={};', 'export const pool={end:async()=>console.log("POOL_CLOSED")};')
    .replace("./src/server.ts", "./src/migrate.ts");
  const result=spawnSync(process.execPath,['--import','tsx','--input-type=module','-e',explicit],{
    env:{...process.env,FACTLENS_AUTO_MIGRATE:'false'},encoding:'utf8'
  });
  expect(result.status).toBe(0);
  expect(result.stdout.trim().split(/\r?\n/)).toEqual(['POOL_CLOSED','MIGRATION_CALLED']);
});
