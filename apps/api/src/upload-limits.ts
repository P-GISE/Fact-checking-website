import type {RequestHandler} from 'express';
import {randomUUID} from 'node:crypto';
import {mkdir,rm,statfs} from 'node:fs/promises';
import path from 'node:path';
import {pool} from './db.js';
export class UploadLimitError extends Error{status=429;code='STORAGE_QUOTA';}
export interface UploadLimits{mediaRoot:string;maxBytes?:number;uploadQuotaBytes?:number;uploadAccountQuotaBytes?:number;}
export function uploadReservation(options:UploadLimits):RequestHandler{
 return async(req,res,next)=>{
  try{
   await mkdir(options.mediaRoot,{recursive:true,mode:0o700});const disk=await statfs(options.mediaRoot);
   if(disk.bavail*disk.bsize<2*1024**3)throw new UploadLimitError('DISK_RESERVE_REQUIRED');
   const client=await pool.connect(),lease=randomUUID();
   try{
    await client.query('BEGIN');await client.query('SELECT pg_advisory_xact_lock(548871631)');
    const owner=await client.query('SELECT id FROM app_users WHERE id=$1 AND deleted_at IS NULL',[res.locals.ownerId]);
    if(!owner.rowCount)throw Object.assign(new Error('AUTH_REQUIRED'),{status:401,code:'AUTH_REQUIRED'});
    await client.query('DELETE FROM upload_leases WHERE expires_at<=now()');
    const r=await client.query(`SELECT count(*)::int AS count,COALESCE(sum(bytes),0) AS bytes,
     count(*) FILTER(WHERE owner_id IS NOT DISTINCT FROM $1::uuid)::int AS owner_count,
     COALESCE(sum(bytes) FILTER(WHERE owner_id IS NOT DISTINCT FROM $1::uuid),0) AS owner_bytes
     FROM(SELECT m.bytes,m.owner_id FROM media m WHERE m.expires_at>now() AND NOT EXISTS(SELECT 1 FROM jobs j WHERE j.media_id=m.id AND j.status='deleted')
     UNION ALL SELECT reserved_bytes,owner_id FROM upload_leases) q`,[res.locals.ownerId]);
    const usage=r.rows[0],reserved=options.maxBytes??104857600;
    const active=Number((await client.query('SELECT count(*) FROM upload_leases')).rows[0].count);
    if(active>=4||usage.count>=20||usage.owner_count>=2||Number(usage.bytes)+reserved>(options.uploadQuotaBytes??1024**3)||Number(usage.owner_bytes)+reserved>(options.uploadAccountQuotaBytes??209715200))throw new UploadLimitError('STORAGE_QUOTA');
    await client.query('INSERT INTO upload_leases(id,owner_id,reserved_bytes) VALUES($1,$2,$3)',[lease,res.locals.ownerId,reserved]);
    await client.query('COMMIT');
   }catch(e){await client.query('ROLLBACK');throw e;}finally{client.release();}
   let release:Promise<void>|undefined;
   const deadline=setTimeout(()=>{req.destroy();},120000);deadline.unref();
   res.locals.releaseUpload=()=>release??=(async()=>{
    clearTimeout(deadline);
    if(res.locals.incomingName)await rm(path.join(options.mediaRoot,'.incoming',res.locals.incomingName),{force:true});
    await pool.query('DELETE FROM upload_leases WHERE id=$1',[lease]);
   })();
   const cleanup=()=>{void res.locals.releaseUpload().catch(()=>{});};
   req.once('aborted',cleanup);res.once('close',cleanup);res.once('finish',cleanup);
   next();
  }catch(e){next(e);}
 };
}
