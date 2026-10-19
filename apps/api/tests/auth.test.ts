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
beforeEach(async()=>{app=createApp({mediaRoot:root,enqueue:async()=>{},authMode:'accounts',secureCookies:true});await pool.query('TRUNCATE media,jobs CASCADE');if((await pool.query("SELECT to_regclass('app_users') AS name")).rows[0].name)await pool.query('TRUNCATE app_users CASCADE');});
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
it('authorizes administrators by current database role and rejects bearer bypass',async()=>{
 const c=await login('operator');
 expect((await request(app).get('/api/admin/overview')).status).toBe(401);
 expect((await request(app).get('/api/admin/overview').set('Cookie',c)).status).toBe(403);
 expect((await request(app).get('/api/auth/session').set('Cookie',c)).body.user.role).toBe('user');
 expect((await request(app).post('/api/auth/register').send({...credentials('intruder'),role:'admin'})).status).toBe(400);
 await pool.query("UPDATE app_users SET role='admin' WHERE username='operator'");
 expect((await request(app).get('/api/admin/overview').set('Cookie',c)).status).toBe(200);
 await pool.query("UPDATE app_users SET role='user' WHERE username='operator'");
 expect((await request(app).get('/api/admin/overview').set('Cookie',c)).status).toBe(403);
 expect((await request(app).get('/api/admin/overview').set('Authorization','Bearer '+ 'a'.repeat(64))).status).toBe(401);
});
it('bounds administrator searches and paginates only matching metadata',async()=>{
 const c=await login('operator');await pool.query("UPDATE app_users SET role='admin' WHERE username='operator'");
 const ids=[];
 for(let i=0;i<3;i++){
  const mid=randomUUID(),jid=randomUUID();ids.push(jid);
  await pool.query("INSERT INTO media(id,path,original_name,bytes,mime) VALUES($1,$2,'private.wav',1,'audio/wav')",[mid,join(root,mid)]);
  await pool.query('INSERT INTO jobs(id,media_id,status,consent) VALUES($1,$2,$3,true)',[jid,mid,i<2?'failed':'completed']);
 }
 const get=(query:string)=>request(app).get('/api/admin/overview'+query).set('Cookie',c);
 const first=await get('?status=failed&pageSize=1');expect(first.status).toBe(200);
 expect(first.body.pagination).toMatchObject({page:1,pageSize:1,total:2,hasNext:true});
 expect(first.body.recentJobs).toHaveLength(1);
 const second=await get('?status=failed&pageSize=1&page=2');expect(second.body.recentJobs[0].id).not.toBe(first.body.recentJobs[0].id);
 expect(second.body.pagination.hasNext).toBe(false);
 const search=await get('?q='+ids[2]);expect(search.body.recentJobs.map((j:any)=>j.id)).toEqual([ids[2]]);
 expect((await get('?q=ffffffff')).body.recentJobs).toEqual([]);
 for(const q of ['?page=0','?pageSize=51','?status=invalid','?q=%25','?page=1001','?page=1&page=2'])expect((await get(q)).status,q).toBe(400);
 expect(JSON.stringify(first.body)).not.toContain('private.wav');
});
it('reauthenticates account changes and revokes every existing session atomically',async()=>{
 const c=await login('alice');
 const other=await request(app).post('/api/auth/login').send(credentials('alice'));const second=other.headers['set-cookie'][0].split(';')[0];
 const change=(body:any)=>request(app).patch('/api/auth/account').set('Cookie',c).send(body);
 expect((await change({username:'renamed',currentPassword:'wrong-password-123'})).status).toBe(401);
 expect((await change({username:'renamed',currentPassword:credentials('alice').password,role:'admin'})).status).toBe(400);
 const result=await change({username:'renamed',currentPassword:credentials('alice').password,newPassword:'new-correct-password-789!'});
 expect(result.status).toBe(204);
 for(const cookie of [c,second])expect((await request(app).get('/api/analyses').set('Cookie',cookie)).status).toBe(401);
 expect((await request(app).post('/api/auth/login').send(credentials('alice'))).status).toBe(401);
 expect((await request(app).post('/api/auth/login').send({username:'renamed',password:'new-correct-password-789!'})).status).toBe(200);
 expect((await pool.query("SELECT role FROM app_users WHERE username='renamed'")).rows[0].role).toBe('user');
});
it('preserves credentials and sessions when an account rename conflicts',async()=>{
 const c=await login('alice');await login('bob');
 const result=await request(app).patch('/api/auth/account').set('Cookie',c).send({username:'bob',currentPassword:credentials('alice').password,newPassword:'new-correct-password-789!'});
 expect(result.status).toBe(409);
 expect((await request(app).get('/api/auth/session').set('Cookie',c)).body.user.username).toBe('alice');
 expect((await request(app).post('/api/auth/login').send(credentials('alice'))).status).toBe(200);
 expect((await request(app).patch('/api/auth/account').send({username:'other',currentPassword:credentials('alice').password})).status).toBe(401);
});
it('permits only one concurrent credential change from a revoked session',async()=>{
 const c=await login('alice');
 const changes=['changed_one','changed_two'].map(username=>request(app).patch('/api/auth/account').set('Cookie',c).send({username,currentPassword:credentials('alice').password}));
 const responses=await Promise.all(changes);expect(responses.map(r=>r.status).sort()).toEqual([204,401]);
 expect((await pool.query('SELECT count(*)::int AS count FROM app_sessions')).rows[0].count).toBe(0);
});
it('closes only the reauthenticated account, erases media and keeps cost records',async()=>{
 const a=await login('alice'),b=await login('bob');
 const u=await request(app).post('/api/media/upload').set('Cookie',a).attach('file',Buffer.from('audio'),'private.wav');
 const j=await request(app).post('/api/analyses').set('Cookie',a).send({mediaId:u.body.mediaId,externalProcessingConsent:true});
 const mid=u.body.mediaId;const before=await pool.query('SELECT path FROM media WHERE id=$1',[mid]);
 await pool.query("INSERT INTO usage_reservations(id,job_id,month,reserved_micros) VALUES($1,$2,'2026-10',123)",[randomUUID(),j.body.id]);
 const close=(body:any)=>request(app).delete('/api/auth/account').set('Cookie',a).send(body);
 expect((await close({currentPassword:credentials('alice').password})).status).toBe(400);
 expect((await close({currentPassword:'wrong-password-123',confirmation:'DELETE'})).status).toBe(401);
 expect((await close({currentPassword:credentials('alice').password,confirmation:'DELETE'})).status).toBe(204);
 expect((await request(app).get('/api/analyses').set('Cookie',a)).status).toBe(401);
 expect((await request(app).get('/api/analyses').set('Cookie',b)).status).toBe(200);
 expect((await request(app).post('/api/auth/login').send(credentials('alice'))).status).toBe(401);
 expect((await pool.query('SELECT status,result FROM jobs WHERE id=$1',[j.body.id])).rows[0]).toEqual({status:'deleted',result:null});
 expect((await pool.query('SELECT reserved_micros FROM usage_reservations WHERE job_id=$1',[j.body.id])).rows[0].reserved_micros).toBe('123');
 const {access}=await import('node:fs/promises');await expect(access(before.rows[0].path)).rejects.toThrow();
 const row=(await pool.query('SELECT username,password_hash,deleted_at FROM app_users WHERE deleted_at IS NOT NULL')).rows[0];expect(row.username).not.toBe('alice');expect(row.password_hash).toBe('!');
});
it('blocks closure during running work and prevents administrator self-deletion',async()=>{
 const c=await login('alice');
 const u=await request(app).post('/api/media/upload').set('Cookie',c).attach('file',Buffer.from('audio'),'a.wav');
 const j=await request(app).post('/api/analyses').set('Cookie',c).send({mediaId:u.body.mediaId,externalProcessingConsent:true});
 await pool.query("UPDATE jobs SET status='transcribing' WHERE id=$1",[j.body.id]);
 const body={currentPassword:credentials('alice').password,confirmation:'DELETE'};
 expect((await request(app).delete('/api/auth/account').set('Cookie',c).send(body)).status).toBe(409);
 expect((await request(app).get('/api/auth/session').set('Cookie',c)).body.user.username).toBe('alice');
 await pool.query("UPDATE jobs SET status='completed' WHERE id=$1",[j.body.id]);await pool.query("UPDATE app_users SET role='admin' WHERE username='alice'");
 expect((await request(app).delete('/api/auth/account').set('Cookie',c).send(body)).body.error.code).toBe('ADMIN_CLOSURE_BLOCKED');
});
it('orders upload reservation and closure locks consistently',async()=>{
 const c=await login('alice');const uid=(await pool.query("SELECT id FROM app_users WHERE username='alice'")).rows[0].id;
 const uploadClient=await pool.connect();let closing:Promise<any>|undefined;
 try{
  await uploadClient.query('BEGIN');await uploadClient.query('SELECT pg_advisory_xact_lock(548871631)');
  closing=request(app).delete('/api/auth/account').set('Cookie',c).send({currentPassword:credentials('alice').password,confirmation:'DELETE'}).then(r=>r);
  let waiting=false;
  for(let attempt=0;attempt<50;attempt++){
   const r=await pool.query("SELECT 1 FROM pg_locks WHERE locktype='advisory' AND NOT granted AND objid=548871631::oid");
   if(r.rowCount){waiting=true;break;}await new Promise(resolve=>setTimeout(resolve,10));
  }
  expect(waiting).toBe(true);
  await uploadClient.query("SET LOCAL lock_timeout='500ms'");
  await uploadClient.query('INSERT INTO upload_leases(id,owner_id,reserved_bytes) VALUES($1,$2,1)',[randomUUID(),uid]);
  await uploadClient.query('COMMIT');
  expect((await closing).body.error.code).toBe('ACCOUNT_BUSY');
 }finally{await uploadClient.query('ROLLBACK');uploadClient.release();if(closing)await closing;}
});
