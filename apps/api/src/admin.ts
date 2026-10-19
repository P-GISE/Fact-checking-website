import {Router} from 'express';
import {createHash,timingSafeEqual,randomUUID} from 'node:crypto';
import {pool} from './db.js';
const errorCodes=new Set(['PROVIDER_NOT_CONFIGURED','PROVIDER_AUTH_FAILED','PROVIDER_RATE_LIMITED','PROVIDER_MODEL_UNAVAILABLE','PROVIDER_INPUT_LIMIT','PROVIDER_RESPONSE_INVALID','PROVIDER_REQUEST_FAILED','PROVIDER_SEARCH_LIMIT','BUDGET_EXCEEDED','BILLING_REVIEW_REQUIRED','SIZE_LIMIT','DURATION_LIMIT','INVALID_MEDIA','FORMAT_MISMATCH','NO_AUDIO','TIMEOUT','INTERNAL_ERROR']);
const digest=(value:string)=>createHash('sha256').update(value).digest();
export function adminRouter(token:string|undefined){
 const router=Router();
 const expected=token&&/^[A-Za-z0-9._~-]{32,256}$/.test(token)?digest(token):undefined;
 router.get('/overview',async(req,res)=>{
  const fail=(status:number,code:string)=>res.status(status).json({error:{code,message:code,requestId:randomUUID()}});
  if(!expected)return fail(503,'ADMIN_NOT_CONFIGURED');
  const authorization=req.get('Authorization')??'';
  if(!authorization.startsWith('Bearer ')||authorization.length>263||!timingSafeEqual(expected,digest(authorization.slice(7)))){
   res.setHeader('WWW-Authenticate','Bearer realm="FactLens administration"');
   return fail(401,'ADMIN_UNAUTHORIZED');
  }
  // One SQL statement gives the dashboard a consistent database snapshot.
  // All money amounts remain decimal strings to avoid JavaScript bigint loss.
  const result=await pool.query(`SELECT now() AS "observedAt",now()-interval '24 hours' AS "windowStart",
   COALESCE((SELECT jsonb_object_agg(status,count) FROM
    (SELECT status,count(*)::int AS count FROM jobs WHERE created_at>=now()-interval '24 hours' GROUP BY status) states),'{}'::jsonb) AS "statusCounts",
   COALESCE((SELECT jsonb_agg(recent ORDER BY recent."createdAt" DESC,recent.id DESC) FROM
    (SELECT id,status,created_at AS "createdAt",error->>'code' AS "errorCode" FROM jobs
     WHERE created_at>=now()-interval '24 hours' ORDER BY created_at DESC,id DESC LIMIT 20) recent),'[]'::jsonb) AS "recentJobs",
   (SELECT jsonb_build_object('month',to_char(now() AT TIME ZONE 'UTC','YYYY-MM'),
    'settledMicros',COALESCE(sum(actual_micros),0)::text,
    'reservedMicros',COALESCE(sum(reserved_micros) FILTER (WHERE actual_micros IS NULL),0)::text,
    'effectiveMicros',COALESCE(sum(COALESCE(actual_micros,reserved_micros)),0)::text,
    'pendingReservations',count(*) FILTER (WHERE actual_micros IS NULL)::text)
    FROM usage_reservations WHERE month=to_char(now() AT TIME ZONE 'UTC','YYYY-MM')) AS usage`);
  const overview=result.rows[0];
  overview.recentJobs=overview.recentJobs.map((job:{errorCode:string|null})=>({...job,errorCode:job.errorCode?(errorCodes.has(job.errorCode)?job.errorCode:'UNCLASSIFIED_ERROR'):null}));
  res.json({version:'admin-overview-v1',...overview});
 });
 return router;
}
