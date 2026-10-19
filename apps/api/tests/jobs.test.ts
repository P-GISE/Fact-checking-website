import {beforeAll,afterAll,beforeEach,it,expect} from 'vitest';
import request from 'supertest';
import {mkdtemp,readFile,rm,symlink,rename,writeFile,access,readdir,readlink,truncate} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {createServer,get as httpGet} from 'node:http';
import {once} from 'node:events';
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
 expect(r.headers['cross-origin-resource-policy']).toBe('same-origin');
 expect(r.headers['cache-control']).toBe('no-store');
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

async function mediaDescriptors(source:string){
 const descriptors=await readdir('/proc/self/fd');
 const targets=await Promise.all(descriptors.map(async fd=>{
  try{return await readlink(`/proc/self/fd/${fd}`);}catch(error){
   if((error as NodeJS.ErrnoException).code==='ENOENT')return '';
   throw error;
  }
 }));
 return targets.filter(target=>target===source||target===source+' (deleted)').length;
}
async function waitForMediaClose(source:string){
 const deadline=Date.now()+2000;
 while(await mediaDescriptors(source)){
  if(Date.now()>=deadline)throw new Error('Media descriptor retained after response ended');
  await new Promise(resolve=>setTimeout(resolve,10));
 }
}
it('closes source descriptors after an actual client abort',async()=>{
 const u=await upload(),source=join(root,u.body.mediaId,'source.wav');
 await truncate(source,64*1024*1024);
 const server=createServer(app);server.listen(0,'127.0.0.1');await once(server,'listening');
 const address=server.address();if(!address||typeof address==='string')throw new Error('Missing server port');
 let client:ReturnType<typeof httpGet>|undefined;
 const warnings:Error[]=[];
 const warning=(value:Error)=>{if(value.message.includes('Closing file descriptor')||('code' in value&&value.code==='DEP0137'))warnings.push(value);};
 process.on('warning',warning);
 try{
  const response=await new Promise<import('node:http').IncomingMessage>((resolve,reject)=>{
   client=httpGet(`http://127.0.0.1:${address.port}/api/media/${u.body.mediaId}`,resolve);
   client.on('error',reject);
  });
  expect(response.statusCode).toBe(200);
  await once(response,'data');response.pause();
  expect(await mediaDescriptors(source)).toBeGreaterThan(0);
  response.destroy();client.destroy();
  await waitForMediaClose(source);
  await new Promise(resolve=>setImmediate(resolve));
  expect(await mediaDescriptors(source)).toBe(0);
  expect(warnings).toEqual([]);
 }finally{
  process.off('warning',warning);
  client?.destroy();server.closeAllConnections();await new Promise<void>(resolve=>server.close(()=>resolve()));
 }
});
it('closes source descriptors after full and rejected Range responses',async()=>{
 const u=await upload(),source=join(root,u.body.mediaId,'source.wav');
 expect((await request(app).get(`/api/media/${u.body.mediaId}`)).status).toBe(200);
 await waitForMediaClose(source);
 expect((await request(app).get(`/api/media/${u.body.mediaId}`).set('Range','bytes=999999999-')).status).toBe(416);
 await waitForMediaClose(source);
 expect(await mediaDescriptors(source)).toBe(0);
});

it('keeps admin overview closed without an account session',async()=>{
 const unavailable=createApp({mediaRoot:root,enqueue:async()=>{}});
 expect((await request(unavailable).get('/api/admin/overview')).status).toBe(401);
});
it('rejects bearer access and retains origin protection',async()=>{
 const {randomBytes}=await import('node:crypto');const token=randomBytes(32).toString('hex');
 const admin=createApp({mediaRoot:root,enqueue:async()=>{}});
 expect((await request(admin).get('/api/admin/overview')).status).toBe(401);
 expect((await request(admin).get('/api/admin/overview').set('Authorization','Bearer wrong')).status).toBe(401);
 expect((await request(admin).get('/api/admin/overview').set('Authorization',`Bearer ${token}`).set('Origin','https://untrusted.example')).status).toBe(403);
 expect((await request(admin).post('/api/admin/overview').set('Authorization',`Bearer ${token}`)).status).toBe(401);
});
it('shows bounded admin job metadata and separates settled costs from reservations',async()=>{
 const {randomBytes,randomUUID}=await import('node:crypto');const token=randomBytes(32).toString('hex');
 const u=await upload();const job=await request(app).post('/api/analyses').send({mediaId:u.body.mediaId,externalProcessingConsent:true});
 await pool.query("UPDATE jobs SET status='failed',error=$2 WHERE id=$1",[job.body.id,{code:'PROVIDER_RATE_LIMITED',message:'private transcript must stay hidden'}]);
 const month=(await pool.query("SELECT to_char(now() AT TIME ZONE 'UTC','YYYY-MM') AS month")).rows[0].month;
 for(const [reserved,actual] of [[100,30],[200,null]])await pool.query('INSERT INTO usage_reservations(id,job_id,month,reserved_micros,actual_micros) VALUES($1,$2,$3,$4,$5)',[randomUUID(),job.body.id,month,reserved,actual]);
 const admin=createApp({mediaRoot:root,enqueue:async()=>{},authMode:'accounts'});
 const {createHash}=await import('node:crypto');const uid=randomUUID();
 await pool.query("INSERT INTO app_users(id,username,password_hash,role) VALUES($1,$2,'unusable','admin')",[uid,'admin_'+uid.slice(0,8)]);
 await pool.query('INSERT INTO app_sessions(token_hash,user_id) VALUES($1,$2)',[createHash('sha256').update(token).digest('hex'),uid]);
 const response=await request(admin).get('/api/admin/overview').set('Cookie',`factlens_session=${token}`);
 expect(response.status).toBe(200);expect(response.body.statusCounts.failed).toBe(1);
 expect(response.body.usage).toEqual({month,settledMicros:'30',reservedMicros:'200',effectiveMicros:'230',pendingReservations:'1'});
 expect(response.body.recentJobs).toHaveLength(1);
 expect(response.body.recentJobs[0]).toMatchObject({id:job.body.id,status:'failed',errorCode:'PROVIDER_RATE_LIMITED'});
 expect(Object.keys(response.body.recentJobs[0]).sort()).toEqual(['createdAt','errorCode','id','status']);
 expect(JSON.stringify(response.body)).not.toContain('private transcript');
 expect(JSON.stringify(response.body)).not.toContain(token);
 expect(response.headers['cache-control']).toBe('no-store');
 await pool.query('UPDATE jobs SET error=$2 WHERE id=$1',[job.body.id,{code:'private exception content',message:'secret'}]);
 const masked=await request(admin).get('/api/admin/overview').set('Cookie',`factlens_session=${token}`);
 expect(masked.body.recentJobs[0].errorCode).toBe('UNCLASSIFIED_ERROR');
});
