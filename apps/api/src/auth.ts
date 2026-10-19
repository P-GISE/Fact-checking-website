import {Router,type RequestHandler} from 'express';
import {randomBytes,randomUUID,createHash,scrypt,timingSafeEqual} from 'node:crypto';
import {promisify} from 'node:util';
import {z} from 'zod';
import {pool} from './db.js';
import {eraseFiles} from './cleanup.js';
export type AuthMode='local'|'accounts';
const derive=promisify(scrypt);
export const credentials=z.object({username:z.string().regex(/^[a-z0-9_-]{3,32}$/),password:z.string().min(12).max(128)}).strict();
const digest=(value:string)=>createHash('sha256').update(value).digest('hex');
function cookie(req:{headers:{cookie?:string}},secure:boolean){const name=secure?'__Host-factlens_session':'factlens_session';return (req.headers.cookie??'').split(';').map(v=>v.trim()).find(v=>v.startsWith(name+'='))?.slice(name.length+1)??'';}
export async function encode(password:string){const salt=randomBytes(16).toString('hex');return salt+':'+(await derive(password,salt,64) as Buffer).toString('hex');}
async function verify(password:string,encoded:string){const [salt,hex]=encoded.split(':');const expected=Buffer.from(hex,'hex');const actual=await derive(password,salt,64) as Buffer;return expected.length===actual.length&&timingSafeEqual(expected,actual);}
export function authentication(mode:AuthMode,secure:boolean,mediaRoot:string){
 const router=Router(),name=secure?'__Host-factlens_session':'factlens_session';
 // Bound password hashing work and unauthenticated attempt accounting per API process.
 const attempts=new Map<string,{count:number;until:number}>();let pending=0;
 const limit:RequestHandler=(req,res,next)=>{
  const now=Date.now();for(const [key,value] of attempts)if(value.until<=now)attempts.delete(key);
  const key=req.ip??'unknown',entry=attempts.get(key)??{count:0,until:now+60000};
  if(entry.count>=20||pending>=4||(!attempts.has(key)&&attempts.size>=10000)){res.status(429).json({error:{code:'AUTH_RATE_LIMITED'}});return;}
  entry.count++;attempts.set(key,entry);pending++;let released=false;const release=()=>{if(!released){pending--;released=true;}};res.once('finish',release);res.once('close',release);next();
 };
 const read:RequestHandler=async(req,res,next)=>{
  res.locals.ownerId=null;res.locals.user=null;
  if(mode==='accounts'){
   const token=cookie(req,secure);
   if(/^[a-f0-9]{64}$/.test(token)){
    const r=await pool.query('SELECT u.id,u.username,u.role FROM app_sessions s JOIN app_users u ON u.id=s.user_id WHERE s.token_hash=$1 AND s.expires_at>now() AND u.deleted_at IS NULL',[digest(token)]);
    if(r.rows[0]){res.locals.ownerId=r.rows[0].id;res.locals.user=r.rows[0];}
   }
  }next();
 };
 router.get('/session',read,(_req,res)=>res.json({mode,user:res.locals.user}));
 async function issue(res:any,user:{id:string;username:string;role:string},db:Pick<typeof pool,'query'>=pool){
  const token=randomBytes(32).toString('hex');await db.query('DELETE FROM app_sessions WHERE expires_at<=now()');
  await db.query('INSERT INTO app_sessions(token_hash,user_id) VALUES($1,$2)',[digest(token),user.id]);
  res.cookie(name,token,{httpOnly:true,secure,sameSite:'strict',path:'/',maxAge:86400000});return {mode,user};
 }
 router.post('/register',limit,async(req,res)=>{
  if(mode!=='accounts'){res.status(404).end();return;}
  const b=credentials.parse(req.body),passwordHash=await encode(b.password),user={id:randomUUID(),username:b.username,role:'user' as const};
  const r=await pool.query('INSERT INTO app_users(id,username,password_hash) VALUES($1,$2,$3) ON CONFLICT(username) DO NOTHING RETURNING id',[user.id,user.username,passwordHash]);
  if(!r.rowCount){res.status(409).json({error:{code:'USERNAME_UNAVAILABLE'}});return;}
  res.status(201).json(await issue(res,user));
 });
 router.post('/login',limit,async(req,res)=>{
  if(mode!=='accounts'){res.status(404).end();return;}
  const b=credentials.parse(req.body),client=await pool.connect();
  try{
   await client.query('BEGIN');
   const r=await client.query('SELECT id,username,password_hash,role FROM app_users WHERE username=$1 AND deleted_at IS NULL FOR UPDATE',[b.username]);
   const user=r.rows[0];const valid=await verify(b.password,user?.password_hash??('0'.repeat(32)+':'+ '0'.repeat(128)));
   if(!user||!valid){await client.query('ROLLBACK');res.status(401).json({error:{code:'AUTH_FAILED'}});return;}
   const old=cookie(req,secure);if(old)await client.query('DELETE FROM app_sessions WHERE token_hash=$1',[digest(old)]);
   const session=await issue(res,{id:user.id,username:user.username,role:user.role},client);
   await client.query('COMMIT');res.json(session);
  }catch(cause){await client.query('ROLLBACK');throw cause;}finally{client.release();}
 });
 router.post('/logout',async(req,res)=>{const token=cookie(req,secure);if(token)await pool.query('DELETE FROM app_sessions WHERE token_hash=$1',[digest(token)]);res.clearCookie(name,{httpOnly:true,secure,sameSite:'strict',path:'/'});res.status(204).end();});
 const requireUser:RequestHandler=async(req,res,next)=>{await read(req,res,()=>{});if(mode==='accounts'&&!res.locals.user){res.status(401).json({error:{code:'AUTH_REQUIRED'}});return;}next();};
 const changes=z.object({username:z.string().regex(/^[a-z0-9_-]{3,32}$/),currentPassword:z.string().min(12).max(128),newPassword:z.string().min(12).max(128).optional()}).strict();
 router.patch('/account',requireUser,limit,async(req,res)=>{
  if(mode!=='accounts'||!res.locals.user){res.status(401).json({error:{code:'AUTH_REQUIRED'}});return;}
  const body=changes.parse(req.body),client=await pool.connect();
  try{
   await client.query('BEGIN');
   const locked=await client.query('SELECT id,password_hash FROM app_users WHERE id=$1 AND deleted_at IS NULL FOR UPDATE',[res.locals.user.id]);
   const active=await client.query('SELECT 1 FROM app_sessions WHERE token_hash=$1 AND user_id=$2 AND expires_at>now()',[digest(cookie(req,secure)),res.locals.user.id]);
   if(!locked.rows[0]||!active.rowCount||!await verify(body.currentPassword,locked.rows[0].password_hash)){
    await client.query('ROLLBACK');res.status(401).json({error:{code:'AUTH_FAILED'}});return;
   }
   const passwordHash=body.newPassword?await encode(body.newPassword):locked.rows[0].password_hash;
   await client.query('UPDATE app_users SET username=$1,password_hash=$2 WHERE id=$3',[body.username,passwordHash,res.locals.user.id]);
   await client.query('DELETE FROM app_sessions WHERE user_id=$1',[res.locals.user.id]);
   await client.query('COMMIT');
   res.clearCookie(name,{httpOnly:true,secure,sameSite:'strict',path:'/'});res.status(204).end();
  }catch(cause){
   await client.query('ROLLBACK');
   if((cause as {code?:string}).code==='23505'){res.status(409).json({error:{code:'USERNAME_UNAVAILABLE'}});return;}
   throw cause;
  }finally{client.release();}
 });
 const closure=z.object({currentPassword:z.string().min(12).max(128),confirmation:z.literal('DELETE')}).strict();
 router.delete('/account',requireUser,limit,async(req,res)=>{
  if(mode!=='accounts'||!res.locals.user){res.status(401).json({error:{code:'AUTH_REQUIRED'}});return;}
  const body=closure.parse(req.body),client=await pool.connect();let mediaIds:string[]=[];
  try{
   await client.query('BEGIN');
   await client.query('SELECT pg_advisory_xact_lock(548871631)');
   const user=await client.query('SELECT id,password_hash,role FROM app_users WHERE id=$1 AND deleted_at IS NULL FOR UPDATE',[res.locals.user.id]);
   const active=await client.query('SELECT 1 FROM app_sessions WHERE token_hash=$1 AND user_id=$2 AND expires_at>now()',[digest(cookie(req,secure)),res.locals.user.id]);
   if(!user.rows[0]||!active.rowCount||!await verify(body.currentPassword,user.rows[0].password_hash)){
    await client.query('ROLLBACK');res.status(401).json({error:{code:'AUTH_FAILED'}});return;
   }
   // Administrators must keep an operator recovery route; self-deletion is not offered.
   if(user.rows[0].role==='admin'){await client.query('ROLLBACK');res.status(409).json({error:{code:'ADMIN_CLOSURE_BLOCKED'}});return;}
   const leases=await client.query('SELECT 1 FROM upload_leases WHERE owner_id=$1 AND expires_at>now()',[res.locals.user.id]);
   const media=await client.query('SELECT id FROM media WHERE owner_id=$1 FOR UPDATE',[res.locals.user.id]);
   const jobs=await client.query('SELECT status FROM jobs WHERE owner_id=$1 FOR UPDATE',[res.locals.user.id]);
   if(leases.rowCount||jobs.rows.some(j=>!['queued','completed','failed','cancelled','deleted'].includes(j.status))){
    await client.query('ROLLBACK');res.status(409).json({error:{code:'ACCOUNT_BUSY'}});return;
   }
   mediaIds=media.rows.map(row=>row.id);
   await client.query("UPDATE jobs SET status='deleted',deleted_at=now(),expires_at=now(),version=version+1,result=NULL,error=NULL,idempotency_key=NULL WHERE owner_id=$1",[res.locals.user.id]);
   await client.query('DELETE FROM claims WHERE job_id IN(SELECT id FROM jobs WHERE owner_id=$1)',[res.locals.user.id]);
   await client.query("UPDATE media SET original_name='',path='/discarded/'||id::text,expires_at=now() WHERE owner_id=$1",[res.locals.user.id]);
   await client.query('DELETE FROM app_sessions WHERE user_id=$1',[res.locals.user.id]);
   await client.query('DELETE FROM upload_leases WHERE owner_id=$1',[res.locals.user.id]);
   await client.query("UPDATE app_users SET username='deleted_'||id::text,password_hash='!',role='user',deleted_at=now() WHERE id=$1",[res.locals.user.id]);
   await client.query('COMMIT');
  }catch(cause){await client.query('ROLLBACK');throw cause;}finally{client.release();}
  let cleanupPending=false;
  for(const mediaId of mediaIds){try{await eraseFiles(mediaRoot,mediaId);}catch{cleanupPending=true;}}
  res.clearCookie(name,{httpOnly:true,secure,sameSite:'strict',path:'/'});
  if(cleanupPending){res.status(202).json({cleanupPending:true});return;}res.status(204).end();
 });
 const requireAdmin:RequestHandler=async(req,res,next)=>{await read(req,res,()=>{});if(!res.locals.user){res.status(401).json({error:{code:'AUTH_REQUIRED'}});return;}if(res.locals.user.role!=='admin'){res.status(403).json({error:{code:'ADMIN_REQUIRED'}});return;}next();};
 return {router,requireUser,requireAdmin};
}
