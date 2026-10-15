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
