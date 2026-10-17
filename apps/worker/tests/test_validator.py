from factlens.contracts import Claim
from factlens.validator import EvidenceDocument, Fact, validate_evidence
from factlens.decision import decide

def claim(**kw):
    values=dict(id='c',text='2025년 한국 고용률 50%',contextText='2025년 한국 고용률 50%',startSeconds=0,endSeconds=1,subject='한국',period='2025년',metric='고용률',value='50',unit='%')
    values.update(kw)
    return Claim(**values)
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

def test_cropped_quote_cannot_hide_correction_context():
    d=document('50');d.text=d.quote+'라는 주장은 잘못됐다. 실제 고용률은 5%다.'
    assert not validate_evidence(claim(),d).usable


def test_negative_claim_cannot_be_confirmed_by_positive_evidence():
    c=claim(text='2025년 한국 고용률 50%가 아니다.',contextText='2025년 한국 고용률 50%가 아니다.')
    e=validate_evidence(c,document('50'))
    assert not e.usable and 'CLAIM_CONTEXT_REVIEW_REQUIRED' in e.reasons
    assert decide(c,[e])=='REVIEW_REQUIRED'
    assert decide(c,[])=='REVIEW_REQUIRED'

def test_cropped_claim_cannot_hide_adjacent_transcript_correction():
    c=claim(contextText='2025년 한국 고용률 50% 실제 수치는 5%이며 앞선 주장은 틀렸다.')
    assert decide(c,[validate_evidence(c,document('50'))])=='REVIEW_REQUIRED'

def test_claim_attributes_cannot_rewrite_displayed_number():
    c=claim(value='5')
    assert decide(c,[validate_evidence(c,document('5'))])=='REVIEW_REQUIRED'

def test_claim_without_preserved_transcript_context_is_not_decisive():
    c=claim(contextText=None)
    e=validate_evidence(c,document('50'))
    assert 'CLAIM_CONTEXT_MISSING' in e.reasons and not e.usable
    assert decide(c,[e])=='INSUFFICIENT'


def test_unit_cannot_absorb_negation_to_create_a_false_refutation():
    text='2025년 한국 고용률 50%가 아니다.'
    c=claim(text=text,contextText=text,unit='%가 아니다.')
    d=document('5');d.fact.unit='%가 아니다.';d.text=d.quote='2025년 한국 고용률 5%가 아니다.'
    assert decide(c,[validate_evidence(c,d)])=='REVIEW_REQUIRED'


def test_metric_cannot_turn_an_equality_record_into_a_lower_bound():
    text='2025년 한국 고용률은 적어도 50%'
    c=claim(text=text,contextText=text,metric='고용률은 적어도')
    d=document('5');d.fact.metric='고용률은 적어도';d.text=d.quote='2025년 한국 고용률은 적어도 5%'
    assert decide(c,[validate_evidence(c,d)])=='REVIEW_REQUIRED'
