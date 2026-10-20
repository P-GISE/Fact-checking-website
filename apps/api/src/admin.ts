import {Router} from 'express';
import {z} from 'zod';
import {pool} from './db.js';
const errorCodes=new Set(['PROVIDER_NOT_CONFIGURED','PROVIDER_AUTH_FAILED','PROVIDER_RATE_LIMITED','PROVIDER_MODEL_UNAVAILABLE','PROVIDER_INPUT_LIMIT','PROVIDER_RESPONSE_INVALID','PROVIDER_REQUEST_FAILED','PROVIDER_SEARCH_LIMIT','BUDGET_EXCEEDED','BILLING_REVIEW_REQUIRED','SIZE_LIMIT','DURATION_LIMIT','INVALID_MEDIA','FORMAT_MISMATCH','NO_AUDIO','TIMEOUT','INTERNAL_ERROR']);
errorCodes.add('PROVIDER_QUOTA_EXCEEDED');
const querySchema=z.object({
 status:z.enum(['queued','validating','transcribing','extracting','retrieving','validating_evidence','completed','failed','cancelled','deleted']).optional(),
 q:z.string().regex(/^[a-fA-F0-9-]{0,36}$/).default(''),
 page:z.coerce.number().int().min(1).max(1000).default(1),
 pageSize:z.coerce.number().int().min(1).max(50).default(20)
}).strict();
export function adminRouter(){
 const router=Router();
 router.get('/overview',async(req,res)=>{
  const parsed=querySchema.safeParse(req.query);
  if(!parsed.success){res.status(400).json({error:{code:'INVALID_ADMIN_QUERY'}});return;}
  const {status,q,page,pageSize}=parsed.data;
  // One SQL statement gives the dashboard a consistent database snapshot.
  // All money amounts remain decimal strings to avoid JavaScript bigint loss.
  const result=await pool.query(`WITH matching AS (SELECT id,status,created_at,error FROM jobs WHERE created_at>=now()-interval '24 hours' AND ($1::text IS NULL OR status=$1) AND ($2::text='' OR id::text ILIKE $2||'%')) SELECT (SELECT count(*)::int FROM matching) AS total, now() AS "observedAt",now()-interval '24 hours' AS "windowStart",
   COALESCE((SELECT jsonb_object_agg(status,count) FROM
    (SELECT status,count(*)::int AS count FROM jobs WHERE created_at>=now()-interval '24 hours' GROUP BY status) states),'{}'::jsonb) AS "statusCounts",
   COALESCE((SELECT jsonb_agg(recent ORDER BY recent."createdAt" DESC,recent.id DESC) FROM
    (SELECT id,status,created_at AS "createdAt",error->>'code' AS "errorCode" FROM matching ORDER BY created_at DESC,id DESC LIMIT $3 OFFSET $4) recent),'[]'::jsonb) AS "recentJobs",
   (SELECT jsonb_build_object('month',to_char(now() AT TIME ZONE 'UTC','YYYY-MM'),
    'settledMicros',COALESCE(sum(actual_micros),0)::text,
    'reservedMicros',COALESCE(sum(reserved_micros) FILTER (WHERE actual_micros IS NULL),0)::text,
    'effectiveMicros',COALESCE(sum(COALESCE(actual_micros,reserved_micros)),0)::text,
    'pendingReservations',count(*) FILTER (WHERE actual_micros IS NULL)::text)
    FROM usage_reservations WHERE month=to_char(now() AT TIME ZONE 'UTC','YYYY-MM')) AS usage`,[status??null,q,pageSize,(page-1)*pageSize]);
  const overview=result.rows[0];
  overview.recentJobs=overview.recentJobs.map((job:{errorCode:string|null})=>({...job,errorCode:job.errorCode?(errorCodes.has(job.errorCode)?job.errorCode:'UNCLASSIFIED_ERROR'):null}));
  const {total,...data}=overview;
  res.json({version:'admin-overview-v2',...data,pagination:{page,pageSize,total,hasNext:page*pageSize<total}});
 });
 return router;
}
