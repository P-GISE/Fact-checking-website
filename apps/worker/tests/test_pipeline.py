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
