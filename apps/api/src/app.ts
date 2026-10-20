import express, { type Request,type Response,type NextFunction } from 'express';
import multer from 'multer';
import { randomUUID } from 'node:crypto';
import { mkdir,rename,rm,chmod } from 'node:fs/promises';
import path from 'node:path';
import {z} from 'zod';
import {pool} from './db.js';
import {uploadReservation,UploadLimitError} from './upload-limits.js';
import {authentication,type AuthMode} from './auth.js';
import {adminRouter} from './admin.js';
import {eraseFiles} from './cleanup.js';
import {mediaDirectory,incomingFile,openMedia} from './storage.js';
import {resultSchema} from './contracts.js';
export type Options={mediaRoot:string;enqueue:(id:string)=>Promise<void>;maxBytes?:number;authMode?:AuthMode;secureCookies?:boolean;trustProxy?:boolean;uploadQuotaBytes?:number;uploadAccountQuotaBytes?:number};
class ApiError extends Error{constructor(public status:number,public code:string, message=code){super(message);}}
const uuid=z.string().uuid();
function id(value:unknown){return uuid.parse(value);}
function view(row:any){
 const r=row.result?resultSchema.parse(row.result):{scope:'audio_only',demo:false,claims:[],limitations:['이 버전은 음성만 검증하며 자막·화면 맥락을 분석하지 않습니다.'],usage:{}};
 return {id:row.id,status:row.status,stage:row.status,createdAt:row.created_at,expiresAt:row.expires_at,error:row.error,mediaId:row.media_id,...r};
}
async function getJob(jobId:string,ownerId:string|null){
 const r=await pool.query("SELECT * FROM jobs WHERE id=$1 AND owner_id IS NOT DISTINCT FROM $2::uuid AND status<>'deleted' AND expires_at>now()",[jobId,ownerId]);
 if(!r.rows[0])throw new ApiError(404,'NOT_FOUND');return r.rows[0];
}
export function createApp(options:Options){
 const app=express();app.disable('x-powered-by');if(options.trustProxy)app.set('trust proxy',1);
 app.use((req,res,next)=>{
  res.setHeader('X-Content-Type-Options','nosniff');res.setHeader('Cache-Control','no-store');
  res.setHeader('X-Frame-Options','DENY');
  res.setHeader('Content-Security-Policy',"default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'");
  res.setHeader('Cross-Origin-Resource-Policy','same-origin');
  res.setHeader('Referrer-Policy','no-referrer');
  const origin=req.get('Origin');
  const allowed=(process.env.ALLOWED_ORIGINS??'http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:8080,http://localhost:8080').split(',');
  if(req.get('Sec-Fetch-Site')==='cross-site'||(origin&&!allowed.includes(origin)))return next(new ApiError(403,'ORIGIN_DENIED'));
  next();
 });
 app.use(express.json({limit:'32kb'}));
 app.get('/api/health',async(_req,res)=>{await pool.query('SELECT 1');res.json({status:'ready',scope:'audio_only',providerConfigured:false});});
 const auth=authentication(options.authMode??'local',options.secureCookies??false,options.mediaRoot);
 app.use('/api/admin',auth.requireAdmin,adminRouter());
 app.use('/api/auth',auth.router);app.use('/api',auth.requireUser);
 const incoming=path.join(path.resolve(options.mediaRoot),'.incoming');
 const upload=multer({storage:multer.diskStorage({destination:async(_req,_file,cb)=>{try{await mkdir(incoming,{recursive:true,mode:0o700});cb(null,incoming);}catch(e){cb(e as Error,incoming);}},filename:(_req,_f,cb)=>{const name=randomUUID();(_req.res as Response).locals.incomingName=name;cb(null,name);}}),limits:{fileSize:options.maxBytes??104857600,files:1,fields:0},fileFilter:(_req,file,cb)=>{if(!['.mp4','.mp3','.wav'].includes(path.extname(file.originalname).toLowerCase()))cb(new ApiError(415,'UNSUPPORTED_FORMAT'));else cb(null,true);}});
 app.post('/api/media/upload',...(options.authMode==='accounts'?[uploadReservation(options)]:[]),upload.single('file'),async(req,res)=>{
  if(!req.file)throw new ApiError(400,'FILE_REQUIRED');
  const mediaId=randomUUID(),folder=mediaDirectory(options.mediaRoot,mediaId);
  try{
   if(req.file.size===0)throw new ApiError(400,'EMPTY_FILE');
   await mkdir(folder,{mode:0o700});
   const target=path.join(folder,'source'+path.extname(req.file.originalname).toLowerCase());
   await rename(req.file.path,target);await chmod(target,0o600);
   const type=target.endsWith('.mp4')?'video/mp4':target.endsWith('.mp3')?'audio/mpeg':'audio/wav';
   await pool.query('INSERT INTO media(id,path,original_name,bytes,mime,owner_id) VALUES($1,$2,$3,$4,$5,$6)',[mediaId,target,path.basename(req.file.originalname),req.file.size,type,res.locals.ownerId]);
   await res.locals.releaseUpload?.();res.status(201).json({mediaId});
  }catch(e){await rm(incomingFile(options.mediaRoot,req.file.filename),{force:true});await eraseFiles(options.mediaRoot,mediaId);throw e;}
 });
 app.post('/api/analyses',async(req,res)=>{
  const b=z.object({mediaId:uuid,externalProcessingConsent:z.literal(true)}).parse(req.body);
  const key=req.get('Idempotency-Key');if(key&&key.length>128)throw new ApiError(400,'INVALID_IDEMPOTENCY_KEY');
  const client=await pool.connect();let jobId:string;
  try{
   await client.query('BEGIN');
   if(res.locals.ownerId){const owner=await client.query('SELECT id FROM app_users WHERE id=$1 AND deleted_at IS NULL FOR UPDATE',[res.locals.ownerId]);if(!owner.rowCount)throw new ApiError(401,'AUTH_REQUIRED');}
   const m=await client.query('SELECT id FROM media WHERE id=$1 AND owner_id IS NOT DISTINCT FROM $2::uuid AND expires_at>now() FOR UPDATE',[b.mediaId,res.locals.ownerId]);
   if(!m.rows[0])throw new ApiError(404,'MEDIA_NOT_FOUND');
   const prev=await client.query('SELECT id,media_id,status FROM jobs WHERE owner_id IS NOT DISTINCT FROM $3::uuid AND (media_id=$1 OR ($2::text IS NOT NULL AND idempotency_key=$2))',[b.mediaId,key??null,res.locals.ownerId]);
   if(prev.rows[0]){
    if(prev.rows[0].media_id!==b.mediaId||prev.rows[0].status==='deleted')throw new ApiError(409,'ANALYSIS_CONFLICT');
    jobId=prev.rows[0].id;
   }else{
    jobId=randomUUID();await client.query('INSERT INTO jobs(id,media_id,consent,idempotency_key,owner_id) VALUES($1,$2,true,$3,$4)',[jobId,b.mediaId,key??null,res.locals.ownerId]);
   }
   await client.query('COMMIT');
  }catch(e){await client.query('ROLLBACK');throw e;}finally{client.release();}
  try{await options.enqueue(jobId!);}catch{/* Durable queued row is recovered by the worker. */}
  res.status(202).json({id:jobId!});
 });
 app.get('/api/analyses',async(_req,res)=>{const r=await pool.query("SELECT * FROM jobs WHERE owner_id IS NOT DISTINCT FROM $1::uuid AND status<>'deleted' AND expires_at>now() ORDER BY created_at DESC LIMIT 50",[res.locals.ownerId]);res.json(r.rows.map(view));});
 app.get('/api/analyses/:id',async(req,res)=>res.json(view(await getJob(id(req.params.id),res.locals.ownerId))));
 app.get('/api/analyses/:id/claims',async(req,res)=>res.json(view(await getJob(id(req.params.id),res.locals.ownerId)).claims));
 app.get('/api/analyses/:id/timeline',async(req,res)=>{const job=view(await getJob(id(req.params.id),res.locals.ownerId));res.json(job.claims.map(c=>({claimId:c.id,startSeconds:c.startSeconds,endSeconds:c.endSeconds,verdict:c.verdict})));});
 app.get('/api/analyses/:id/report',async(req,res)=>res.json(view(await getJob(id(req.params.id),res.locals.ownerId))));
 app.get('/api/claims/:id/evidence',async(req,res)=>{const r=await pool.query("SELECT c.data FROM claims c JOIN jobs j ON j.id=c.job_id WHERE c.id=$1 AND j.owner_id IS NOT DISTINCT FROM $2::uuid AND j.status<>'deleted' AND j.expires_at>now()",[id(req.params.id),res.locals.ownerId]);if(!r.rows[0])throw new ApiError(404,'NOT_FOUND');res.json(r.rows[0].data.evidence);});
 app.delete('/api/analyses/:id',async(req,res)=>{
  const jobId=id(req.params.id);
  const r=await pool.query("UPDATE jobs SET status='deleted',deleted_at=now(),version=version+1,result=NULL,error=NULL WHERE id=$1 AND owner_id IS NOT DISTINCT FROM $2::uuid RETURNING media_id",[jobId,res.locals.ownerId]);
  if(!r.rows[0])throw new ApiError(404,'NOT_FOUND');
  await pool.query('DELETE FROM claims WHERE job_id=$1',[jobId]);
  await eraseFiles(options.mediaRoot,r.rows[0].media_id);res.status(204).end();
 });
 app.get('/api/media/:id',async(req,res)=>{
  const r=await pool.query("SELECT * FROM media m WHERE id=$1 AND m.owner_id IS NOT DISTINCT FROM $2::uuid AND expires_at>now() AND NOT EXISTS(SELECT 1 FROM jobs j WHERE j.media_id=m.id AND j.status='deleted')",[id(req.params.id),res.locals.ownerId]);
  const m=r.rows[0];if(!m)throw new ApiError(404,'NOT_FOUND');
  let source;
  try{source=await openMedia(options.mediaRoot,m.id,m.path);}catch{throw new ApiError(404,'NOT_FOUND');}
  try{
   await new Promise<void>((resolve)=>{
    res.type(m.mime);res.sendFile(`/proc/self/fd/${source.fd}`,{dotfiles:'deny'},err=>{
     if(err&&!res.headersSent)res.status('status' in err&&err.status===416?416:404).end();
     resolve();
    });
   });
  }finally{await source.close();}
 });
 app.use((_req,_res,next)=>next(new ApiError(404,'NOT_FOUND')));
 app.use(async(err:any,_req:Request,res:Response,_next:NextFunction)=>{
  await res.locals.releaseUpload?.().catch(()=>{});
  const sizeLimit=err.code==='LIMIT_FILE_SIZE'||err.type==='entity.too.large';
  const invalidInput=err instanceof z.ZodError||err.type==='entity.parse.failed',invalidUpload=err instanceof multer.MulterError;
  const status=sizeLimit?413:invalidInput||invalidUpload?400:err.code==='23505'?409:err.status??500;
  const code=sizeLimit?'SIZE_LIMIT':invalidInput?'INVALID_INPUT':invalidUpload?'INVALID_UPLOAD':err.code==='23505'?'ANALYSIS_CONFLICT':(err instanceof ApiError||err instanceof UploadLimitError)?err.code:'INTERNAL_ERROR';
  res.status(status).json({error:{code,message:status===500?'서버 처리 중 오류가 발생했습니다.':code,requestId:randomUUID()}});
 });return app;
}
