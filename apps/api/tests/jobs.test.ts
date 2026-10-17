import {beforeAll,afterAll,beforeEach,it,expect} from 'vitest';
import request from 'supertest';
import {mkdtemp,readFile,rm,symlink,rename,writeFile,access} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {execFileSync} from 'node:child_process';
import { createApp } from '../src/app.js';
import {pool,migrate} from '../src/db.js';
import { cleanup,eraseFiles } from '../src/cleanup.js';
let root:string, app:ReturnType<typeof createApp>, audio:Buffer;
beforeAll(async()=>{
 root=await mkdtemp(join(tmpdir(),'factlens-'));
 execFileSync('ffmpeg',['-v','error','-f','lavfi','-i','sine=duration=1',join(root,'sample.wav')]);
 audio=await readFile(join(root,'sample.wav'));await migrate();
 app=createApp({mediaRoot:root,enqueue:async()=>{},maxBytes:104857600});
});
beforeEach(async()=>{await pool.query('TRUNCATE media,jobs,claims,evidence,checks,verdicts,usage_reservations CASCADE');});
afterAll(async()=>{await pool.end();await rm(root,{recursive:true,force:true});});
async function upload(){return request(app).post('/api/media/upload').attach('file',audio,'sample.wav');}
it('streams uploaded media and preserves range responses',async()=>{
 const u=await upload();expect(u.status).toBe(201);
 const r=await request(app).get(`/api/media/${u.body.mediaId}`).set('Range','bytes=0-15');
 expect(r.status).toBe(206);expect(r.headers['content-range']).toMatch(/^bytes 0-15\//);
});
it('requires consent, creates idempotent job, deletes immediately',async()=>{
 const u=await upload();
 expect((await request(app).post('/api/analyses').send({mediaId:u.body.mediaId})).status).toBe(400);
 const body={mediaId:u.body.mediaId,externalProcessingConsent:true};
 const a=await request(app).post('/api/analyses').set('Idempotency-Key','one').send(body);
 expect(a.status).toBe(202);
 const again=await request(app).post('/api/analyses').set('Idempotency-Key','one').send(body);
 expect(again.body.id).toBe(a.body.id);
 expect((await request(app).get(`/api/analyses/${a.body.id}`)).body.scope).toBe('audio_only');
 await writeFile(join(root,u.body.mediaId,'audio.wav'),'derived audio');
 expect((await request(app).delete(`/api/analyses/${a.body.id}`)).status).toBe(204);
 await expect(access(join(root,u.body.mediaId))).rejects.toMatchObject({code:'ENOENT'});
 expect((await request(app).get(`/api/analyses/${a.body.id}`)).status).toBe(404);
 expect((await request(app).get(`/api/media/${u.body.mediaId}`)).status).toBe(404);
});
it('rejects excessive bytes without retaining files',async()=>{
 const small=createApp({mediaRoot:root,enqueue:async()=>{},maxBytes:10});
 expect((await request(small).post('/api/media/upload').attach('file',audio,'sample.wav')).status).toBe(413);
 expect((await pool.query('SELECT * FROM media')).rowCount).toBe(0);
});
it('rejects unknown types and path traversal identifiers',async()=>{
 expect((await request(app).post('/api/media/upload').attach('file',audio,'a.exe')).status).toBe(415);
 expect((await request(app).get('/api/media/not-an-id')).status).toBe(400);
});
it('expires orphan uploads and jobs',async()=>{
 const u=await upload();
 await pool.query("UPDATE media SET expires_at=now()-interval '1 second'");
 await cleanup(root);
 expect((await request(app).get(`/api/media/${u.body.mediaId}`)).status).toBe(404);
});
it('retains queued job when enqueue fails so recovery can find it',async()=>{
 const u=await upload();
 const offline=createApp({mediaRoot:root,enqueue:async()=>{throw new Error('redis down');}});
 const r=await request(offline).post('/api/analyses').send({mediaId:u.body.mediaId,externalProcessingConsent:true});
 expect(r.status).toBe(202);
 expect((await pool.query('SELECT status FROM jobs')).rows[0].status).toBe('queued');
});
it('blocks cross-site requests to an unauthenticated local API',async()=>{
 expect((await request(app).post('/api/analyses').set('Origin','https://evil.example').send({})).status).toBe(403);
});

it('does not serve a DB path outside its media directory',async()=>{
 const u=await upload();
 await pool.query('UPDATE media SET path=$1 WHERE id=$2',[join(root,'sample.wav'),u.body.mediaId]);
 const r=await request(app).get(`/api/media/${u.body.mediaId}`);
 expect(r.status).toBe(404);
});
it('does not serve a symlinked source file',async()=>{
 const u=await upload();const target=join(root,u.body.mediaId,'source.wav');
 await rm(target);await symlink(join(root,'sample.wav'),target);
 expect((await request(app).get(`/api/media/${u.body.mediaId}`)).status).toBe(404);
});
it('does not serve a symlinked media directory',async()=>{
 const u=await upload();const folder=join(root,u.body.mediaId),outside=join(root,'outside');
 await rename(folder,outside);await symlink(outside,folder);
 expect((await request(app).get(`/api/media/${u.body.mediaId}`)).status).toBe(404);
});
it('rejects deletion traversal and preserves external files',async()=>{
 const outside=await mkdtemp(join(tmpdir(),'factlens-outside-'));
 try{
  await writeFile(join(outside,'sentinel'),'keep');
  await expect(eraseFiles(root,'../'+outside.split('/').at(-1))).rejects.toThrow();
  expect(await readFile(join(outside,'sentinel'),'utf8')).toBe('keep');
 }finally{await rm(outside,{recursive:true,force:true});}
});

it('rejects absolute deletion IDs without deleting their targets',async()=>{
 const outside=await mkdtemp(join(tmpdir(),'factlens-absolute-'));
 try{
  await writeFile(join(outside,'sentinel'),'keep');
  await expect(eraseFiles(root,outside)).rejects.toThrow();
  expect(await readFile(join(outside,'sentinel'),'utf8')).toBe('keep');
 }finally{await rm(outside,{recursive:true,force:true});}
});
