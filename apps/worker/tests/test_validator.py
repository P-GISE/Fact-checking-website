from factlens.contracts import Claim
from factlens.validator import EvidenceDocument, Fact, validate_evidence
from factlens.decision import decide

def claim(**kw):return Claim(id='c',text='2025년 한국 고용률 50%',startSeconds=0,endSeconds=1,subject='한국',period='2025년',metric='고용률',value='50',unit='%',**kw)
def document(value='5',**kw):
    text=f'2025년 한국 고용률 {value}%'
    return EvidenceDocument(url='https://example.org/report',title='통계',text=text,quote=text,position=0,publisher='통계 기관',publishedAt='2026-01-01',fact=Fact(subject='한국',period='2025년',metric='고용률',value=value,unit='%'),**kw)

def test_direct_same_conditions_refutes():
    c=claim();e=validate_evidence(c,document())
    assert e.usable and e.relation=='REFUTED'
    assert decide(c,[e])=='REFUTED'

def test_support_and_conflict():
    c=claim();support=validate_evidence(c,document('50'));refute=validate_evidence(c,document('5'))
    assert decide(c,[support])=='CONFIRMED'
    assert decide(c,[support,refute])=='REVIEW_REQUIRED'

def test_period_mismatch_and_missing_quote():
    c=claim();d=document();d.fact.period='2024년'
    assert decide(c,[validate_evidence(c,d)])=='INSUFFICIENT'
    d=document();d.quote='존재하지 않는 인용'
    assert not validate_evidence(c,d).usable

def test_absent_or_opinion_not_false():
    assert decide(claim(),[])=='INSUFFICIENT'
    assert decide(claim(eligibility='excluded'),[])=='EXCLUDED'

def test_number_must_exist_in_quote():
    d=document();d.fact.value='9'
    assert not validate_evidence(claim(),d).usable

def test_percent_and_percentage_points_not_interchangeable():
    d=document();d.fact.unit='퍼센트포인트'
    assert not validate_evidence(claim(),d).usable

def test_ambiguous_precision_abstains():
    assert decide(claim(),[validate_evidence(claim(),document('49.99'))])=='REVIEW_REQUIRED'

def test_multiple_percent_values_in_quote_are_ambiguous():
    d=document('50');d.text=d.quote='2025년 한국 고용률은 5%에서 50%로 변했다'
    assert not validate_evidence(claim(),d).usable
