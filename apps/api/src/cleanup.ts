import { rm } from 'node:fs/promises';
import path from 'node:path';
import {pool} from './db.js';
export async function eraseFiles(root:string,id:string){await rm(path.join(root,id),{recursive:true,force:true});}
export async function cleanup(root:string){
 // Mark deleted first: worker completion uses status/version and cannot revive a tombstone.
 await pool.query("UPDATE jobs SET status='deleted',deleted_at=now(),version=version+1,result=NULL,error=NULL WHERE expires_at<=now() AND status<>'deleted'");
 const stale=await pool.query("SELECT m.id FROM media m WHERE m.expires_at<=now() OR EXISTS(SELECT 1 FROM jobs j WHERE j.media_id=m.id AND j.status='deleted')");
 for(const row of stale.rows){await eraseFiles(root,row.id);}
 await pool.query("DELETE FROM claims WHERE job_id IN(SELECT id FROM jobs WHERE status='deleted')");
}
