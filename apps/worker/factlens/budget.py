from uuid import UUID, uuid4
from factlens.queue import connection

def reserve_usage(job_id:UUID,max_cost_micros:int,*,job_limit:int,month_limit:int)->UUID|None:
    if max_cost_micros<=0 or job_limit<=0 or month_limit<=0:return None
    with connection() as conn:
        conn.execute('SELECT pg_advisory_xact_lock(615002)')
        if not conn.execute("SELECT id FROM jobs WHERE id=%s AND consent AND status NOT IN('deleted','cancelled','failed') AND expires_at>now()",(job_id,)).fetchone():return None
        month=conn.execute("SELECT to_char(now() AT TIME ZONE 'UTC','YYYY-MM') AS month").fetchone()['month']
        used=conn.execute('SELECT COALESCE(sum(COALESCE(actual_micros,reserved_micros)),0) AS total,COALESCE(sum(COALESCE(actual_micros,reserved_micros)) FILTER(WHERE job_id=%s),0) AS job FROM usage_reservations WHERE month=%s',(job_id,month)).fetchone()
        if used['total']+max_cost_micros>month_limit or used['job']+max_cost_micros>job_limit:return None
        rid=uuid4()
        conn.execute('INSERT INTO usage_reservations(id,job_id,month,reserved_micros) VALUES(%s,%s,%s,%s)',(rid,job_id,month,max_cost_micros))
        return rid

def settle_usage(reservation_id:UUID,actual_micros:int)->None:
    if actual_micros<0:raise ValueError('INVALID_COST')
    with connection() as conn:
        # Unknown usage must leave the conservative reservation intact.
        conn.execute('UPDATE usage_reservations SET actual_micros=%s WHERE id=%s AND actual_micros IS NULL',(actual_micros,reservation_id))
