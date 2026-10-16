from uuid import uuid4
from factlens.budget import reserve_usage, settle_usage
from test_queue import db,job

def test_budget_atomic_cap(db):
    j=job(db)
    rid=reserve_usage(j,60,job_limit=100,month_limit=100)
    assert rid
    assert reserve_usage(j,50,job_limit=100,month_limit=100) is None
    settle_usage(rid,40)
    assert reserve_usage(j,60,job_limit=100,month_limit=100)
    assert reserve_usage(j,1,job_limit=100,month_limit=100) is None

def test_no_budget_means_no_spending(db):
    assert reserve_usage(job(db),1,job_limit=0,month_limit=0) is None

def test_failed_call_preserves_real_database_reservation(db):
    from factlens.metered import BudgetedCall
    import pytest
    j=job(db);call=BudgetedCall(j,job_limit=100,month_limit=100)
    def external():raise TimeoutError('possibly billed')
    with pytest.raises(TimeoutError):call.run('transcribe',40,external)
    stored=db.execute('SELECT reserved_micros,actual_micros FROM usage_reservations WHERE job_id=%s',(j,)).fetchone()
    assert stored==(40,None)
    assert reserve_usage(j,61,job_limit=100,month_limit=100) is None

def test_job_cap_survives_month_boundary(db):
    j=job(db)
    db.execute("INSERT INTO usage_reservations(id,job_id,month,reserved_micros,actual_micros) VALUES(%s,%s,'1999-12',40,40)",(uuid4(),j))
    assert reserve_usage(j,61,job_limit=100,month_limit=100) is None
    assert reserve_usage(j,60,job_limit=100,month_limit=100)
