import {it,expect} from 'vitest';
import {spawnSync} from 'node:child_process';
it('requires explicit database configuration instead of a built-in password',()=>{
 const env={...process.env};delete env.DATABASE_URL;
 const p=spawnSync(process.execPath,['--import','tsx','--input-type=module','-e',"await import('./src/db.ts')"],{env,encoding:'utf8'});
 expect(p.status).not.toBe(0);expect(p.stderr).toContain('DATABASE_URL_REQUIRED');
});
it('handles idle connection errors without crashing or dumping connection secrets',()=>{
 const p=spawnSync(process.execPath,['--import','tsx','--input-type=module','-e',"const {pool}=await import('./src/db.ts');pool.emit('error',new Error('sensitive connection detail'));await pool.end()"],{encoding:'utf8'});
 expect(p.status).toBe(0);expect(p.stderr).not.toContain('sensitive connection detail');
});
