from uuid import uuid4
import pytest
from factlens.metered import BudgetedCall, ChargedResult, BudgetDenied, InvalidUsage

class Accounting:
    """In-memory test boundary; production uses PostgreSQL reservation methods."""
    def __init__(self,limit=100):self.limit=limit;self.used=0;self.settled=[]
    def reserve(self,job_id,amount,*,job_limit,month_limit):
        if self.used+amount>min(self.limit,job_limit,month_limit):return None
        self.used+=amount
        return uuid4()
    def settle(self,rid,amount):self.settled.append(amount)

def executor(accounting,**kw):return BudgetedCall(uuid4(),job_limit=100,month_limit=100,reserve=accounting.reserve,settle=accounting.settle,**kw)

def test_reserves_before_the_operation():
    accounting=Accounting();calls=[]
    def external():
        assert accounting.used==40
        calls.append('called')
        return ChargedResult('transcript',actual_micros=25)
    call=executor(accounting)
    assert call.run('transcribe',40,external)=='transcript'
    assert calls==['called'] and accounting.settled==[25]
    assert call.usage()['actualMicros']==25

def test_denied_budget_never_invokes_external_operation():
    accounting=Accounting(limit=5);calls=[]
    with pytest.raises(BudgetDenied):executor(accounting).run('search',10,lambda:calls.append('called'))
    assert calls==[]

@pytest.mark.parametrize('amount',[0,-1,True,1.5])
def test_invalid_price_is_rejected_before_reservation(amount):
    accounting=Accounting()
    with pytest.raises(ValueError):executor(accounting).run('extract',amount,lambda:None)
    assert accounting.used==0

def test_unknown_usage_preserves_reservation_and_reports_unknown():
    accounting=Accounting();call=executor(accounting)
    assert call.run('search',40,lambda:ChargedResult([],actual_micros=None))==[]
    assert accounting.settled==[]
    assert call.usage()['unknownUsageCalls']==1
    assert call.usage()['conservativeMicros']==40

def test_exception_preserves_reservation_and_does_not_retry():
    accounting=Accounting();call=executor(accounting);attempts=[]
    def external():attempts.append(1);raise TimeoutError('provider timeout')
    with pytest.raises(TimeoutError):call.run('transcribe',40,external)
    assert attempts==[1] and accounting.settled==[]
    assert call.usage()['unknownUsageCalls']==1

@pytest.mark.parametrize('actual',[-1,True,1.5])
def test_invalid_usage_never_releases_reserved_budget(actual):
    accounting=Accounting();call=executor(accounting)
    with pytest.raises(InvalidUsage):call.run('extract',40,lambda:ChargedResult([],actual_micros=actual))
    assert accounting.settled==[]

def test_overrun_is_recorded_and_blocks_further_calls():
    accounting=Accounting();call=executor(accounting)
    with pytest.raises(InvalidUsage):call.run('extract',40,lambda:ChargedResult([],actual_micros=50))
    assert accounting.settled==[50]
    with pytest.raises(BudgetDenied):call.run('search',1,lambda:ChargedResult([],0))

def test_calls_are_disabled_without_positive_configured_limits():
    with pytest.raises(ValueError):BudgetedCall(uuid4(),job_limit=0,month_limit=100)

def test_known_overrun_blocks_calls_even_if_settlement_storage_fails():
    accounting=Accounting()
    def failing_settlement(rid,amount):raise ConnectionError('database offline')
    call=BudgetedCall(uuid4(),job_limit=100,month_limit=100,reserve=accounting.reserve,settle=failing_settlement)
    with pytest.raises(ConnectionError):call.run('extract',40,lambda:ChargedResult([],50))
    assert call.usage()['actualMicros']==50
    attempts=[]
    with pytest.raises(BudgetDenied):call.run('search',1,lambda:attempts.append(1))
    assert attempts==[]
