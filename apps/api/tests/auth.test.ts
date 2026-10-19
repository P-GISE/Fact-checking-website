import {beforeAll,beforeEach,afterAll,it,expect} from 'vitest';
import request from 'supertest';
import {mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {randomUUID} from 'node:crypto';
import {createApp} from '../src/app.js';
import {pool,migrate} from '../src/db.js';
let root:string,app:ReturnType<typeof createApp>;
const credentials=(username:string)=>({username,password:'correct-horse-927!'});
beforeAll(async()=>{root=await mkdtemp(join(tmpdir(),'factlens-auth-'));await migrate();app=createApp({mediaRoot:root,enqueue:async()=>{},authMode:'accounts',secureCookies:true});});
beforeEach(async()=>{await pool.query('TRUNCATE media,jobs CASCADE');if((await pool.query("SELECT to_regclass('app_users') AS name")).rows[0].name)await pool.query('TRUNCATE app_users CASCADE');});
afterAll(async()=>{await pool.end();await rm(root,{recursive:true,force:true});});
async function login(name:string){const r=await request(app).post('/api/auth/register').send(credentials(name));expect(r.status).toBe(201);return r.headers['set-cookie'][0].split(';')[0];}
it('requires authentication before accepting uploads or reading history',async()=>{expect((await request(app).get('/api/analyses')).status).toBe(401);expect((await request(app).post('/api/media/upload').attach('file',Buffer.from('audio'),'a.wav')).status).toBe(401);});
it('issues secure opaque sessions, hashes passwords and revokes logout',async()=>{
 const r=await request(app).post('/api/auth/register').send(credentials('alice'));expect(r.status).toBe(201);
 const cookie=r.headers['set-cookie'][0];expect(cookie).toContain('HttpOnly');expect(cookie).toContain('Secure');expect(cookie).toContain('SameSite=Strict');
 const u=await pool.query('SELECT password_hash FROM app_users');expect(u.rows[0].password_hash).not.toContain(credentials('alice').password);
 const c=cookie.split(';')[0];expect((await request(app).get('/api/auth/session').set('Cookie',c)).body.user.username).toBe('alice');
 expect((await request(app).post('/api/auth/logout').set('Cookie',c)).status).toBe(204);
 expect((await request(app).get('/api/analyses').set('Cookie',c)).status).toBe(401);
 expect((await request(app).post('/api/auth/login').send({...credentials('alice'),password:'wrong-password-123'})).status).toBe(401);
 expect((await request(app).post('/api/auth/login').send(credentials('alice'))).status).toBe(200);
});
it('isolates uploads, jobs, reports, evidence, media and deletion across accounts',async()=>{
 const a=await login('alice'),b=await login('bob');
 const u=await request(app).post('/api/media/upload').set('Cookie',a).attach('file',Buffer.from('audio'),'a.wav');expect(u.status).toBe(201);
 const body={mediaId:u.body.mediaId,externalProcessingConsent:true};
 expect((await request(app).post('/api/analyses').set('Cookie',b).send(body)).status).toBe(404);
 const j=await request(app).post('/api/analyses').set('Cookie',a).set('Idempotency-Key','shared').send(body);expect(j.status).toBe(202);
 const claimId=randomUUID();await pool.query('INSERT INTO claims(id,job_id,data) VALUES($1,$2,$3)',[claimId,j.body.id,JSON.stringify({evidence:[]})]);
 for(const url of [`/api/media/${u.body.mediaId}`,`/api/analyses/${j.body.id}`,`/api/analyses/${j.body.id}/claims`,`/api/analyses/${j.body.id}/timeline`,`/api/analyses/${j.body.id}/report`,`/api/claims/${claimId}/evidence`])expect((await request(app).get(url).set('Cookie',b)).status,url).toBe(404);
 expect((await request(app).get('/api/analyses').set('Cookie',b)).body).toEqual([]);
 expect((await request(app).delete(`/api/analyses/${j.body.id}`).set('Cookie',b)).status).toBe(404);
 expect((await request(app).get(`/api/media/${u.body.mediaId}`).set('Cookie',a)).status).toBe(200);
 const ub=await request(app).post('/api/media/upload').set('Cookie',b).attach('file',Buffer.from('audio'),'b.wav');
 expect((await request(app).post('/api/analyses').set('Cookie',b).set('Idempotency-Key','shared').send({...body,mediaId:ub.body.mediaId})).status).toBe(202);
 expect((await request(app).delete(`/api/analyses/${j.body.id}`).set('Cookie',a)).status).toBe(204);
});
it('rejects expired sessions and cross-site login and invalid registrations',async()=>{
 const c=await login('alice');await pool.query("UPDATE app_sessions SET expires_at=now()-interval '1 second'");
 expect((await request(app).get('/api/analyses').set('Cookie',c)).status).toBe(401);
 expect((await request(app).post('/api/auth/login').set('Origin','https://evil.example').send(credentials('alice'))).status).toBe(403);
 expect((await request(app).post('/api/auth/register').send({username:'x',password:'short'})).status).toBe(400);
});
it('rejects public startup without account mode and secure cookies',async()=>{
 const {authConfiguration}=await import('../src/auth-config.js');
 expect(()=>authConfiguration({FACTLENS_LOCAL_ONLY:'false'})).toThrow();
 expect(()=>authConfiguration({FACTLENS_LOCAL_ONLY:'false',FACTLENS_AUTH_MODE:'local'})).toThrow();
 expect(authConfiguration({FACTLENS_LOCAL_ONLY:'false',FACTLENS_AUTH_MODE:'accounts',ALLOWED_ORIGINS:'https://factlens.pigs0516.com'})).toEqual({authMode:'accounts',secureCookies:true});
 expect(()=>authConfiguration({FACTLENS_LOCAL_ONLY:'false',FACTLENS_AUTH_MODE:'accounts',ALLOWED_ORIGINS:'http://localhost:8080'})).toThrow();
});
it('keeps legacy unowned records out of account mode and bounds password attempts',async()=>{
 const c=await login('alice'),media=randomUUID();
 await pool.query("INSERT INTO media(id,path,original_name,bytes,mime) VALUES($1,$2,'legacy.wav',5,'audio/wav')",[media,join(root,'legacy')]);
 expect((await request(app).get(`/api/media/${media}`).set('Cookie',c)).status).toBe(404);
 const isolated=createApp({mediaRoot:root,enqueue:async()=>{},authMode:'accounts'});
 const statuses=[];for(let i=0;i<21;i++)statuses.push((await request(isolated).post('/api/auth/login').send({...credentials('unknown'),password:'wrong-password-123'})).status);
 expect(statuses.slice(0,20)).toEqual(Array(20).fill(401));expect(statuses[20]).toBe(429);
});
it('atomically reserves aggregate upload capacity and releases failed requests',async()=>{
 const limited=createApp({mediaRoot:root,enqueue:async()=>{},authMode:'accounts',maxBytes:6,uploadQuotaBytes:12,uploadAccountQuotaBytes:10});
 // This test owns its account independently of preceding tests.
 const reg=await request(limited).post('/api/auth/register').send(credentials('quotauser'));expect(reg.status).toBe(201);const c=reg.headers['set-cookie'][0].split(';')[0];
 const responses=await Promise.all([1,2].map(()=>request(limited).post('/api/media/upload').set('Cookie',c).attach('file',Buffer.from('12345'),'quota.wav')));
 expect(responses.map(r=>r.status).sort()).toEqual([201,429]);
 const fresh=await request(limited).post('/api/auth/register').send(credentials('failedquota'));const failedCookie=fresh.headers['set-cookie'][0].split(';')[0];
 const failed=await request(limited).post('/api/media/upload').set('Cookie',failedCookie).attach('file',Buffer.from('1234567'),'large.wav');
 expect(failed.status).toBe(413);
 expect((await request(limited).post('/api/media/upload').set('Cookie',failedCookie).attach('file',Buffer.from('1'),'small.wav')).status).toBe(201);
 expect(Number((await pool.query('SELECT count(*) FROM upload_leases')).rows[0].count)).toBe(0);
});
it('throttles trusted clients separately and ignores forwarded spoofing without proxy trust',async()=>{
 const trusted=createApp({mediaRoot:root,enqueue:async()=>{},authMode:'accounts',trustProxy:true});
 for(let i=0;i<20;i++)await request(trusted).post('/api/auth/login').set('X-Forwarded-For','198.51.100.1').send({...credentials('unknown'),password:'invalid-password-123'});
 expect((await request(trusted).post('/api/auth/login').set('X-Forwarded-For','198.51.100.1').send(credentials('unknown'))).status).toBe(429);
 expect((await request(trusted).post('/api/auth/register').set('X-Forwarded-For','198.51.100.2').send(credentials('separate'))).status).toBe(201);
 const direct=createApp({mediaRoot:root,enqueue:async()=>{},authMode:'accounts'});
 for(let i=0;i<20;i++)await request(direct).post('/api/auth/login').set('X-Forwarded-For',`198.51.100.${i+1}`).send({...credentials('unknown'),password:'invalid-password-123'});
 expect((await request(direct).post('/api/auth/register').set('X-Forwarded-For','203.0.113.1').send(credentials('spoofed'))).status).toBe(429);
});
it('releases upload reservations and partial files on client disconnect',async()=>{
 const {request:send}=await import('node:http');const {once}=await import('node:events');const {readdir}=await import('node:fs/promises');
 const limited=createApp({mediaRoot:root,enqueue:async()=>{},authMode:'accounts',maxBytes:100});
 const reg=await request(limited).post('/api/auth/register').send(credentials('disconnect'));const c=reg.headers['set-cookie'][0].split(';')[0];
 const server=limited.listen(0,'127.0.0.1');await once(server,'listening');const address=server.address() as {port:number};
 const outbound=send({hostname:'127.0.0.1',port:address.port,path:'/api/media/upload',method:'POST',headers:{Cookie:c,'Content-Type':'multipart/form-data; boundary=testboundary'}});
 outbound.on('error',()=>{});outbound.write('--testboundary\r\nContent-Disposition: form-data; name="file"; filename="partial.wav"\r\nContent-Type: audio/wav\r\n\r\npartial');
 try{
  for(let i=0;i<100;i++){if(Number((await pool.query('SELECT count(*) FROM upload_leases')).rows[0].count)>0)break;await new Promise(r=>setTimeout(r,10));}
  expect(Number((await pool.query('SELECT count(*) FROM upload_leases')).rows[0].count)).toBe(1);outbound.destroy();
  for(let i=0;i<100;i++){if(Number((await pool.query('SELECT count(*) FROM upload_leases')).rows[0].count)===0)break;await new Promise(r=>setTimeout(r,10));}
  expect(Number((await pool.query('SELECT count(*) FROM upload_leases')).rows[0].count)).toBe(0);
  expect(await readdir(join(root,'.incoming'))).toEqual([]);
 }finally{outbound.destroy();await new Promise<void>(resolve=>server.close(()=>resolve()));}
});
