import os
from uuid import uuid4
from datetime import datetime, timezone, timedelta
import psycopg
import pytest
from factlens.queue import claim_job, complete_job, fail_job, recover_expired
from factlens.contracts import AnalysisResult

@pytest.fixture
def db():
    conn=psycopg.connect(os.environ['DATABASE_URL'],autocommit=True)
    conn.execute('TRUNCATE media,jobs,claims,evidence,checks,verdicts,usage_reservations CASCADE')
    yield conn
    conn.close()

def job(db):
    m,j=uuid4(),uuid4()
    db.execute("INSERT INTO media(id,path,original_name,bytes,mime) VALUES(%s,%s,'a.wav',100,'audio/wav')",(m,f'/tmp/{m}/source.wav'))
    db.execute('INSERT INTO jobs(id,media_id,consent) VALUES(%s,%s,true)',(j,m))
    return j

def test_duplicate_claim_and_single_concurrency(db):
    a,b=job(db),job(db)
    claimed=claim_job(a)
    assert claimed['status']=='validating'
    assert claim_job(a) is None
    assert claim_job(b) is None

def test_delete_cannot_be_revived(db):
    j=job(db);claimed=claim_job(j)
    db.execute("UPDATE jobs SET status='deleted',version=version+1,result=NULL WHERE id=%s",(j,))
    assert not complete_job(j,claimed['version'],AnalysisResult(claims=[],limitations=['test']))
    assert db.execute('SELECT result FROM jobs WHERE id=%s',(j,)).fetchone()[0] is None

def test_timeout_fails_without_retry(db):
    j=job(db);claim_job(j)
    db.execute("UPDATE jobs SET started_at=now()-interval '601 seconds' WHERE id=%s",(j,))
    recover_expired()
    assert db.execute('SELECT status FROM jobs WHERE id=%s',(j,)).fetchone()[0]=='failed'
    assert claim_job(j) is None
