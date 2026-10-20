import {beforeAll,afterAll,it,expect} from 'vitest';
import request from 'supertest';
import {mkdtemp,readdir,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createApp} from '../src/app.js';
import {pool} from '../src/db.js';

let root:string,app:ReturnType<typeof createApp>;
beforeAll(async()=>{root=await mkdtemp(join(tmpdir(),'factlens-input-'));app=createApp({mediaRoot:root,enqueue:async()=>{}});});
afterAll(async()=>{await pool.end();await rm(root,{recursive:true,force:true});});

it.each(['unexpected file field','extra text field','multiple files'])('rejects %s as an invalid upload without retaining files',async kind=>{
 const pending=request(app).post('/api/media/upload');
 const response=kind==='extra text field'?await pending.field('unexpected','private-value'):
  kind==='multiple files'?await pending.attach('file',Buffer.from('a'),'a.wav').attach('file',Buffer.from('b'),'b.wav'):
  await pending.attach('unexpected',Buffer.from('private-value'),'private.wav');
 expect(response.status).toBe(400);
 expect(response.body.error.code).toBe('INVALID_UPLOAD');
 expect(JSON.stringify(response.body)).not.toContain('private');
 expect(await readdir(join(root,'.incoming')).catch((error:NodeJS.ErrnoException)=>{if(error.code==='ENOENT')return [];throw error;})).toEqual([]);
});
it('rejects malformed JSON without echoing request content',async()=>{
 const response=await request(app).post('/api/auth/login').type('json').send('{"password":"private-value"');
 expect(response.status).toBe(400);
 expect(response.body.error.code).toBe('INVALID_INPUT');
 expect(JSON.stringify(response.body)).not.toContain('private-value');
});
it('reports the JSON size limit as a client error',async()=>{
 const response=await request(app).post('/api/auth/login').send({password:'x'.repeat(33000)});
 expect(response.status).toBe(413);
 expect(response.body.error.code).toBe('SIZE_LIMIT');
});
it('preserves the multipart file size limit',async()=>{
 const small=createApp({mediaRoot:root,enqueue:async()=>{},maxBytes:3});
 const response=await request(small).post('/api/media/upload').attach('file',Buffer.from('abcd'),'a.wav');
 expect(response.status).toBe(413);
 expect(response.body.error.code).toBe('SIZE_LIMIT');
});
