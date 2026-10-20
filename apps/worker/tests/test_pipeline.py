from pathlib import Path
from uuid import uuid4
import pytest
from factlens.pipeline import run_analysis, Providers, ProviderUnavailable
from factlens.contracts import Claim

class TestProviders:
    def transcribe(self,path):return [{'text':'주장','start':0,'end':1}]
    def extract(self,segments):return [Claim(id=str(uuid4()),text='주장',startSeconds=0,endSeconds=1) for _ in range(7)]
    def search(self,claim):return []

def test_no_provider_never_falls_back(tmp_path):
    with pytest.raises(ProviderUnavailable,match='PROVIDER_NOT_CONFIGURED'):
        run_analysis({'consent':True,'path':str(tmp_path/'a.wav')},Providers())

def test_no_consent_never_calls_provider(tmp_path):
    with pytest.raises(ValueError,match='CONSENT_REQUIRED'):
        run_analysis({'consent':False,'path':str(tmp_path/'a.wav')},TestProviders())

def test_limits_claims_and_marks_insufficient(tmp_path):
    # Input validation precedes this internal orchestration boundary.
    r=run_analysis({'consent':True,'path':str(tmp_path/'a.wav'),'duration':1},TestProviders())
    assert len(r.claims)==5
    assert all(c.verdict=='INSUFFICIENT' for c in r.claims)
    assert any('5' in s for s in r.limitations)
    assert not r.demo

def test_out_of_media_timestamp_rejected(tmp_path):
    class WrongTime(TestProviders):
        def extract(self,segments):return [Claim(id=str(uuid4()),text='x',startSeconds=0,endSeconds=9)]
    with pytest.raises(ValueError,match='CLAIM_OUT_OF_RANGE'):
        run_analysis({'consent':True,'path':str(tmp_path/'a.wav'),'duration':1},WrongTime())

def test_pipeline_preserves_metered_provider_usage(tmp_path):
    from factlens.metered import BudgetedCall, BudgetedProviders, ChargedResult
    from test_metered import Accounting
    class Priced:
        def transcribe(self,path):return ChargedResult([{'text':'주장','start':0,'end':1}],10)
        def extract(self,segments):return ChargedResult([Claim(id=str(uuid4()),text='주장',startSeconds=0,endSeconds=1)],20)
        def search(self,claim):return ChargedResult([],5)
    accounting=Accounting()
    billing=BudgetedCall(uuid4(),job_limit=100,month_limit=100,reserve=accounting.reserve,settle=accounting.settle)
    providers=BudgetedProviders(Priced(),billing,max_call_micros={'transcribe':15,'extract':25,'search':10})
    result=run_analysis({'consent':True,'path':str(tmp_path/'a.wav'),'duration':1},providers)
    assert result.usage['actualMicros']==35
    assert result.usage['unknownUsageCalls']==0

def test_provider_limitations_are_preserved(tmp_path):
    class Restricted(TestProviders):
        limitations=['원문 접근 실패를 반박 근거로 쓰지 않습니다.']
    result=run_analysis({'consent':True,'path':str(tmp_path/'a.wav'),'duration':1},Restricted())
    assert '원문 접근 실패를 반박 근거로 쓰지 않습니다.' in result.limitations


def test_new_results_record_actual_rule_version_without_relabeling_old_results(tmp_path):
    from factlens.contracts import AnalysisResult
    result=run_analysis({'consent':True,'path':str(tmp_path/'a.wav'),'duration':1},TestProviders())
    assert result.versions['ruleVersion']=='audio-reviewed-numeric-v5'
    old=AnalysisResult(claims=[],limitations=[])
    assert old.versions=={}


def test_provider_versions_are_preserved_but_cannot_override_actual_rule_version(tmp_path):
    class Versioned(TestProviders):
        def versions(self):return {'languageModel':'fixture-model','ruleVersion':'incorrect-provider-rule'}
    result=run_analysis({'consent':True,'path':str(tmp_path/'a.wav'),'duration':1},Versioned())
    assert result.versions['languageModel']=='fixture-model'
    assert result.versions['ruleVersion']=='audio-reviewed-numeric-v5'
