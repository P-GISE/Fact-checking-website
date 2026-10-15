import pytest
from pydantic import ValidationError
from factlens.contracts import Claim, EvidenceCheck

def test_reversed_time_rejected():
    with pytest.raises(ValidationError):
        Claim(id='c', text='주장', startSeconds=3, endSeconds=1)

def test_unknown_verdict_rejected():
    with pytest.raises(ValidationError):
        Claim(id='c', text='주장', startSeconds=0, endSeconds=1, verdict='TRUE')

def test_evidence_requires_source_and_quote():
    with pytest.raises(ValidationError):
        EvidenceCheck(relation='SUPPORTED', usable=True)
