import {Router,type RequestHandler} from 'express';
import {randomBytes,randomUUID,createHash,scrypt,timingSafeEqual} from 'node:crypto';
import {promisify} from 'node:util';
import {z} from 'zod';
import {pool} from './db.js';
export type AuthMode='local'|'accounts';
const derive=promisify(scrypt);
const credentials=z.object({username:z.string().regex(/^[a-z0-9_-]{3,32}$/),password:z.string().min(12).max(128)}).strict();
const digest=(value:string)=>createHash('sha256').update(value).digest('hex');
function cookie(req:{headers:{cookie?:string}},secure:boolean){const name=secure?'__Host-factlens_session':'factlens_session';return (req.headers.cookie??'').split(';').map(v=>v.trim()).find(v=>v.startsWith(name+'='))?.slice(name.length+1)??'';}
async function encode(password:string){const salt=randomBytes(16).toString('hex');return salt+':'+(await derive(password,salt,64) as Buffer).toString('hex');}
async function verify(password:string,encoded:string){const [salt,hex]=encoded.split(':');const expected=Buffer.from(hex,'hex');const actual=await derive(password,salt,64) as Buffer;return expected.length===actual.length&&timingSafeEqual(expected,actual);}
export function authentication(mode:AuthMode,secure:boolean){
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
    const r=await pool.query('SELECT u.id,u.username FROM app_sessions s JOIN app_users u ON u.id=s.user_id WHERE s.token_hash=$1 AND s.expires_at>now()',[digest(token)]);
    if(r.rows[0]){res.locals.ownerId=r.rows[0].id;res.locals.user=r.rows[0];}
   }
  }next();
 };
 router.get('/session',read,(_req,res)=>res.json({mode,user:res.locals.user}));
 async function issue(res:any,user:{id:string;username:string}){
  const token=randomBytes(32).toString('hex');await pool.query('DELETE FROM app_sessions WHERE expires_at<=now()');
  await pool.query('INSERT INTO app_sessions(token_hash,user_id) VALUES($1,$2)',[digest(token),user.id]);
  res.cookie(name,token,{httpOnly:true,secure,sameSite:'strict',path:'/',maxAge:86400000});return {mode,user};
 }
 router.post('/register',limit,async(req,res)=>{
  if(mode!=='accounts'){res.status(404).end();return;}
  const b=credentials.parse(req.body),passwordHash=await encode(b.password),user={id:randomUUID(),username:b.username};
  const r=await pool.query('INSERT INTO app_users(id,username,password_hash) VALUES($1,$2,$3) ON CONFLICT(username) DO NOTHING RETURNING id',[user.id,user.username,passwordHash]);
  if(!r.rowCount){res.status(409).json({error:{code:'USERNAME_UNAVAILABLE'}});return;}
  res.status(201).json(await issue(res,user));
 });
 router.post('/login',limit,async(req,res)=>{
  if(mode!=='accounts'){res.status(404).end();return;}
  const b=credentials.parse(req.body);const r=await pool.query('SELECT id,username,password_hash FROM app_users WHERE username=$1',[b.username]);
  const user=r.rows[0];const valid=await verify(b.password,user?.password_hash??('0'.repeat(32)+':'+ '0'.repeat(128)));
  if(!user||!valid){res.status(401).json({error:{code:'AUTH_FAILED'}});return;}
  const old=cookie(req,secure);if(old)await pool.query('DELETE FROM app_sessions WHERE token_hash=$1',[digest(old)]);
  res.json(await issue(res,{id:user.id,username:user.username}));
 });
 router.post('/logout',async(req,res)=>{const token=cookie(req,secure);if(token)await pool.query('DELETE FROM app_sessions WHERE token_hash=$1',[digest(token)]);res.clearCookie(name,{httpOnly:true,secure,sameSite:'strict',path:'/'});res.status(204).end();});
 const requireUser:RequestHandler=async(req,res,next)=>{await read(req,res,()=>{});if(mode==='accounts'&&!res.locals.user){res.status(401).json({error:{code:'AUTH_REQUIRED'}});return;}next();};
 return {router,requireUser};
}
