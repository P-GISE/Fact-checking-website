import os
from uuid import UUID, uuid4
from psycopg import connect
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from factlens.contracts import AnalysisResult

RUNNING=('validating','transcribing','extracting','retrieving','validating_evidence')
def connection():
    return connect(os.environ['DATABASE_URL'],row_factory=dict_row)

def claim_job(job_id: UUID | None = None) -> dict | None:
    with connection() as conn:
        # Global transaction lock serializes claims across worker processes.
        conn.execute('SELECT pg_advisory_xact_lock(615001)')
        if conn.execute('SELECT id FROM jobs WHERE status=ANY(%s)',(list(RUNNING),)).fetchone():return None
        row=conn.execute("SELECT j.*,m.path FROM jobs j JOIN media m ON m.id=j.media_id WHERE j.status='queued' AND j.expires_at>now() AND m.expires_at>now() AND (%s::uuid IS NULL OR j.id=%s::uuid) ORDER BY j.created_at FOR UPDATE OF j LIMIT 1",(job_id,job_id)).fetchone()
        if not row:return None
        updated=conn.execute("UPDATE jobs SET status='validating',started_at=now(),version=version+1 WHERE id=%s RETURNING *",(row['id'],)).fetchone()
        return {**updated,'path':row['path']}

def set_stage(job_id:UUID,version:int,stage:str)->bool:
    if stage not in RUNNING:raise ValueError('invalid stage')
    with connection() as conn:
        r=conn.execute("UPDATE jobs SET status=%s WHERE id=%s AND version=%s AND status=ANY(%s) AND expires_at>now() AND started_at>now()-interval '10 minutes'",(stage,job_id,version,list(RUNNING)))
        return r.rowcount==1

def complete_job(job_id:UUID, expected_version:int, result:AnalysisResult)->bool:
    with connection() as conn:
        updated=conn.execute("UPDATE jobs SET status='completed',result=%s WHERE id=%s AND version=%s AND status=ANY(%s) AND expires_at>now() AND started_at>now()-interval '10 minutes' RETURNING id",(Jsonb(result.model_dump()),job_id,expected_version,list(RUNNING))).fetchone()
        if not updated:return False
        for claim in result.claims:
            cid=UUID(claim.id)
            conn.execute('INSERT INTO claims(id,job_id,data) VALUES(%s,%s,%s)',(cid,job_id,Jsonb(claim.model_dump())))
            conn.execute('INSERT INTO verdicts(claim_id,data) VALUES(%s,%s)',(cid,Jsonb({'verdict':claim.verdict})))
            for evidence in claim.evidence:
                eid=uuid4()
                conn.execute('INSERT INTO evidence(id,claim_id,data) VALUES(%s,%s,%s)',(eid,cid,Jsonb(evidence.model_dump())))
                conn.execute('INSERT INTO checks(id,evidence_id,data) VALUES(%s,%s,%s)',(uuid4(),eid,Jsonb({'usable':evidence.usable,'reasons':evidence.reasons})))
        return True

def fail_job(job_id:UUID,version:int,code:str)->None:
    with connection() as conn:
        conn.execute('UPDATE jobs SET status=\'failed\',error=%s WHERE id=%s AND version=%s AND status=ANY(%s)',(Jsonb({'code':code,'message':code}),job_id,version,list(RUNNING)))

def recover_expired()->None:
    with connection() as conn:
        conn.execute("UPDATE jobs SET status='failed',version=version+1,error=%s WHERE status=ANY(%s) AND started_at<=now()-interval '10 minutes'",(Jsonb({'code':'TIMEOUT','message':'작업 실행 제한 시간을 초과했습니다.'}),list(RUNNING)))
