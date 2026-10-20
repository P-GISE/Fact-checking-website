import json
from pathlib import Path
from uuid import uuid4
import httpx
import pytest
from factlens.live_providers import LiveProviders, build_providers, Settings
from factlens.pipeline import ProviderUnavailable
from factlens.metered import BudgetedCall
from test_metered import Accounting

class Model:
    def __init__(self,data):self.data=data
    def model_dump(self):return self.data

class SDK:
    def __init__(self,transcript=None,completion=None):
        self.transcript=transcript;self.completion=completion;self.requests=[]
        self.audio=self;self.transcriptions=self;self.chat=self;self.completions=self
    def create(self,**kw):
        self.requests.append(kw)
        if 'file' in kw:return Model(self.transcript)
        return Model(self.completion)

def response(content):return {'choices':[{'message':{'content':json.dumps(content),'refusal':None},'finish_reason':'stop'}],'usage':{'prompt_tokens':100,'completion_tokens':50}}

def make(sdk,transport=None,fetch=None):
    accounting=Accounting(limit=200000)
    billing=BudgetedCall(uuid4(),job_limit=200000,month_limit=20000000,reserve=accounting.reserve,settle=accounting.settle)
    client=httpx.Client(transport=httpx.MockTransport(transport or (lambda r:httpx.Response(500))))
    return LiveProviders(sdk,client,billing,duration=3,brave_key='test-key',fetch=fetch or (lambda u:None)),accounting

def test_missing_keys_rejected_before_clients_are_created():
    with pytest.raises(ProviderUnavailable,match='PROVIDER_NOT_CONFIGURED'):
        build_providers({'id':uuid4(),'duration':3},Settings(mode='openai_brave'))

@pytest.mark.parametrize('code,expected',[
    ('insufficient_quota','PROVIDER_QUOTA_EXCEEDED'),
    ('credit_balance_exhausted','PROVIDER_QUOTA_EXCEEDED'),
    ('organization_usage_limit_exceeded','PROVIDER_QUOTA_EXCEEDED'),
    ('organization_spend_limit_exceeded','PROVIDER_QUOTA_EXCEEDED'),
    ('project_spend_limit_exceeded','PROVIDER_QUOTA_EXCEEDED'),
    ('rate_limit_exceeded','PROVIDER_RATE_LIMITED'),
    ('untrusted-secret-error','PROVIDER_RATE_LIMITED')])
def test_quota_failure_is_distinguished_without_exposing_provider_body(code,expected):
    from openai import RateLimitError
    response=httpx.Response(429,request=httpx.Request('POST','https://api.openai.com/v1/audio/transcriptions'))
    def failed():raise RateLimitError('private provider message',response=response,body={'code':code})
    p,_=make(SDK())
    with pytest.raises(ProviderUnavailable) as error:p._invoke(failed)
    assert str(error.value)==expected

def test_billing_error_type_is_preserved_when_no_specific_code_is_given():
    from openai import RateLimitError
    response=httpx.Response(429,request=httpx.Request('POST','https://api.openai.com/v1/audio/transcriptions'))
    def failed():raise RateLimitError('private billing message',response=response,body={'code':None,'type':'insufficient_quota'})
    p,_=make(SDK())
    with pytest.raises(ProviderUnavailable) as error:p._invoke(failed)
    assert str(error.value)=='PROVIDER_QUOTA_EXCEEDED'

def test_settings_cannot_raise_approved_limits():
    with pytest.raises(ValueError):Settings(job_limit=200001)
    with pytest.raises(ValueError):Settings(month_limit=20000001)

def test_whisper_uses_real_segments_and_timestamp_options(tmp_path):
    sdk=SDK(transcript={'duration':3,'segments':[{'start':0,'end':2,'text':'2025년 한국 고용률 50%'}]})
    p,_=make(sdk);audio=tmp_path/'a.wav';audio.write_bytes(b'wave')
    segments=p.transcribe(audio)
    assert segments[0]['start']==0 and segments[0]['end']==2
    assert sdk.requests[0]['model']=='whisper-1'
    assert sdk.requests[0]['response_format']=='verbose_json'
    assert sdk.requests[0]['timestamp_granularities']==['segment']
    assert p.usage()['unknownUsageCalls']==1

@pytest.mark.parametrize('end',[3.0000001,3.119998931884766,3.25])
def test_transcription_clips_only_small_tail_overshoot_and_reports_it(tmp_path,end):
    sdk=SDK(transcript={'segments':[{'start':0,'end':1,'text':'앞 구간'},{'start':1,'end':end,'text':'실제 마지막 발화'}]})
    p,_=make(sdk);audio=tmp_path/'a.wav';audio.write_bytes(b'wave')
    segments=p.transcribe(audio)
    assert segments==[{'id':0,'start':0.0,'end':1.0,'text':'앞 구간'},{'id':1,'start':1.0,'end':3.0,'text':'실제 마지막 발화'}]
    assert any('시간' in item and '조정' in item for item in p.limitations)
    assert p.usage()['calls']==1 and p.usage()['unknownUsageCalls']==1


@pytest.mark.parametrize('start,end',[(0,3.250001),(3,3.12),(3.01,3.12),(2,1),(-.1,1),(0,float('nan')),(0,float('inf'))])
def test_transcription_rejects_large_or_invalid_time_bounds(tmp_path,start,end):
    sdk=SDK(transcript={'segments':[{'start':start,'end':end,'text':'원문'}]})
    p,_=make(sdk);audio=tmp_path/'a.wav';audio.write_bytes(b'wave')
    with pytest.raises(ProviderUnavailable,match='PROVIDER_RESPONSE_INVALID'):p.transcribe(audio)
    assert p.usage()['calls']==1


def test_transcription_does_not_clip_an_intermediate_out_of_range_segment(tmp_path):
    sdk=SDK(transcript={'segments':[{'start':0,'end':3.12,'text':'잘못된 중간 시간'},{'start':2,'end':3,'text':'마지막 구간'}]})
    p,_=make(sdk);audio=tmp_path/'a.wav';audio.write_bytes(b'wave')
    before=p.limitations[:]
    with pytest.raises(ProviderUnavailable,match='PROVIDER_RESPONSE_INVALID'):p.transcribe(audio)
    assert p.limitations==before and p.usage()['calls']==1


def test_extract_validates_quote_and_owns_ids():
    candidate={'quote':'2025년 한국 고용률 50%','segment_ids':[0],'subject':'한국','period':'2025년','metric':'고용률','value':'50','unit':'%','eligibility':'checkable'}
    sdk=SDK(completion=response({'claims':[candidate]}));p,a=make(sdk)
    claims=p.extract([{'id':0,'start':0,'end':2,'text':'2025년 한국 고용률 50%'}])
    assert claims[0].text=='2025년 한국 고용률 50%' and claims[0].startSeconds==0
    assert claims[0].verdict=='INSUFFICIENT'
    assert a.settled==[120]
    assert sdk.requests[0]['max_completion_tokens']==2048

@pytest.mark.parametrize('invalid_first',[False,True])
def test_extract_keeps_literal_candidate_from_observed_household_credit_response(invalid_first,caplog,capsys):
    quote='한국은행에 따르면 작년 말 현재 가계 신용 잔액은 1,344조 3천억 원으로 이 가운데 약 13%가 마이너스 통장 등 대출로 추산된다.'
    valid={'quote':quote,'segment_ids':[0],'subject':'가계 신용 잔액','period':'작년 말 현재','metric':'잔액','value':'1,344조 3천억','unit':'원','eligibility':'checkable'}
    invalid={**valid,'subject':'마이너스 통장 등 대출 비율','metric':'비율','value':'약 13%','unit':'%'}
    sdk=SDK(completion=response({'claims':[invalid,valid] if invalid_first else [valid,invalid]}))
    p,a=make(sdk)
    before=p.limitations[:]
    claims=p.extract([{'id':0,'start':0,'end':2,'text':quote}])
    assert len(claims)==1
    claim=claims[0]
    assert claim.text==quote and claim.contextText==quote
    assert (claim.subject,claim.period,claim.metric,claim.value,claim.unit)==('가계 신용 잔액','작년 말 현재','잔액','1,344조 3천억','원')
    assert (claim.startSeconds,claim.endSeconds,claim.eligibility,claim.verdict)==(0,2,'checkable','INSUFFICIENT')
    assert p.limitations==before+['일부 주장 후보가 원문 검증을 통과하지 못해 제외되었습니다.']
    assert p.versions()['claimValidationVersion']=='literal-candidates-v2'
    assert len(sdk.requests)==1 and a.settled==[120]
    assert caplog.text=='' and capsys.readouterr()==('','')


def test_extract_all_invalid_candidates_fail_closed_without_exposing_validation_values(caplog,capsys):
    import traceback
    quote='2025년 한국 고용률 50%'
    candidate={'quote':quote,'segment_ids':[0],'subject':'한국','period':'2025년','metric':'고용률','value':'50','unit':'%','eligibility':'private-invalid-eligibility'}
    sdk=SDK(completion=response({'claims':[candidate,{**candidate,'subject':'private-invented-subject'}]}))
    p,a=make(sdk)
    before=p.limitations[:]
    with pytest.raises(ProviderUnavailable,match='^PROVIDER_RESPONSE_INVALID$') as error:
        p.extract([{'id':0,'start':0,'end':1,'text':quote}])
    formatted=''.join(traceback.format_exception(error.type,error.value,error.tb))
    assert 'private-invalid-eligibility' not in formatted
    assert 'private-invented-subject' not in formatted
    assert 'ValidationError' not in formatted
    assert p.limitations==before and a.settled==[120] and len(sdk.requests)==1
    assert caplog.text=='' and capsys.readouterr()==('','')


def test_extract_empty_model_claims_remain_legitimate_without_discard_limitation():
    sdk=SDK(completion=response({'claims':[]}));p,a=make(sdk)
    before=p.limitations[:]
    assert p.extract([{'id':0,'start':0,'end':1,'text':'인사말입니다.'}])==[]
    assert p.limitations==before and a.settled==[120]


def test_extract_sends_original_segments_without_rewriting_context():
    sdk=SDK(completion=response({'claims':[]}));p,_=make(sdk)
    segments=[{'id':0,'start':0,'end':1,'text':'원문 그대로'}]
    assert p.extract(segments)==[]
    request=sdk.requests[0]
    assert json.loads(request['messages'][1]['content'])=={'segments':segments}
    assert p.versions()['claimPromptVersion']=='claim-structured-v2'


@pytest.mark.parametrize('segments,candidates',[
    (
        [{'id':0,'start':0,'end':1,'text':'해수 대상은 2016년 10월 1일에서 2016년 11월 19일 내로 유통기한이 표시된 제품들이다.'}],
        [{'quote':'해수 대상은 2016년 10월 1일에서 2016년 11월 19일 내로 유통기한이 표시된 제품들이다.','segment_ids':[0],'subject':None,'period':None,'metric':'유통기한 표시','value':'2016년 10월 1일에서 2016년 11월 19일','unit':'날짜','eligibility':'checkable'}],
    ),
    (
        [{'id':0,'start':0,'end':1,'text':'조금만 해도 각 우주의 주요연령층은 30대와 40대가 존재의 과반이었지만,'},
         {'id':1,'start':1,'end':2,'text':'올해는 50대와 60대가 절반을 넘었다.'}],
        [{'quote':'올해는 50대와 60대가 절반을 넘었다.','segment_ids':[1],'subject':'주요연령층','period':'올해','metric':'과반','value':None,'unit':None,'eligibility':'checkable'}],
    ),
])
def test_extract_observed_nonliteral_fields_remain_fail_closed(segments,candidates):
    p,a=make(SDK(completion=response({'claims':candidates})))
    before=p.limitations[:]
    with pytest.raises(ProviderUnavailable,match='^PROVIDER_RESPONSE_INVALID$'):
        p.extract(segments)
    assert p.limitations==before and a.settled==[120]


@pytest.mark.parametrize('invalid',[
    {'segment_ids':[-1]}, {'segment_ids':[1]}, {'segment_ids':[0,0]},
    {'quote':'없는 인용'}, {'value':'5'}, {'unit':'명'},
    {'eligibility':'private-invalid-eligibility'},
])
def test_extract_partial_success_preserves_candidate_validation_guards(invalid):
    quote='2025년 한국 고용률 50%'
    valid={'quote':quote,'segment_ids':[0],'subject':'한국','period':'2025년','metric':'고용률','value':'50','unit':'%','eligibility':'checkable'}
    p,_=make(SDK(completion=response({'claims':[{**valid,**invalid},valid]})))
    claims=p.extract([{'id':0,'start':0,'end':1,'text':quote}])
    assert len(claims)==1 and claims[0].text==quote and claims[0].value=='50'
    assert p.limitations[-1]=='일부 주장 후보가 원문 검증을 통과하지 못해 제외되었습니다.'


def test_misheard_statistical_term_cannot_inherit_reviewed_policy(tmp_path):
    text='2024년 한국실험률은 2.8%입니다.'
    sdk=SDK(transcript={'segments':[{'start':0,'end':2,'text':text}]})
    p,_=make(sdk);audio=tmp_path/'owned.wav';audio.write_bytes(b'wave')
    segments=p.transcribe(audio)
    assert segments[0]['text']==text
    candidate={'quote':text,'segment_ids':[0],'subject':'한국','period':'2024년','metric':'실험률','value':'2.8','unit':'%','eligibility':'checkable'}
    sdk.completion=response({'claims':[candidate]})
    claim=p.extract(segments)[0]
    from factlens.meaning_review import matching_policies
    from factlens.decision import decide
    assert matching_policies(claim)==[]
    assert decide(claim,[])=='REVIEW_REQUIRED'

def test_transcription_uses_fact_free_labour_vocabulary(tmp_path):
    sdk=SDK(transcript={'segments':[{'start':0,'end':2,'text':'실험률'}]})
    p,_=make(sdk);audio=tmp_path/'owned.wav';audio.write_bytes(b'wave')
    assert p.transcribe(audio)[0]['text']=='실험률'
    assert sdk.requests[0].get('prompt')=='경제활동인구조사, 취업자, 실업자, 실업률, 고용률, 경제활동인구'
    assert p.versions()['speechPromptVersion']=='ko-labour-vocabulary-v1'

def test_extract_preserves_spoken_percent_without_rejecting_equivalent_unit():
    quote='2024년 한국 실업률은 2.8퍼센트입니다.'
    candidate={'quote':quote,'segment_ids':[0],'subject':'한국','period':'2024년','metric':'실업률','value':'2.8','unit':'%','eligibility':'checkable'}
    p,_=make(SDK(completion=response({'claims':[candidate]})))
    c=p.extract([{'id':0,'start':0,'end':2,'text':quote}])[0]
    assert c.unit=='%' and c.text==quote and c.contextText==quote

def test_extract_does_not_convert_percentage_points_into_percent():
    quote='2024년 한국 실업률은 2.8퍼센트 포인트 상승했습니다.'
    candidate={'quote':quote,'segment_ids':[0],'subject':'한국','period':'2024년','metric':'실업률','value':'2.8','unit':'%','eligibility':'checkable'}
    p,_=make(SDK(completion=response({'claims':[candidate]})))
    with pytest.raises(ProviderUnavailable,match='PROVIDER_RESPONSE_INVALID'):
        p.extract([{'id':0,'start':0,'end':2,'text':quote}])

def test_hallucinated_source_quote_is_rejected_after_usage_recorded():
    candidate={'quote':'없는 말','segment_ids':[0],'subject':None,'period':None,'metric':None,'value':None,'unit':None,'eligibility':'excluded'}
    p,a=make(SDK(completion=response({'claims':[candidate]})))
    with pytest.raises(ProviderUnavailable,match='PROVIDER_RESPONSE_INVALID'):p.extract([{'id':0,'start':0,'end':1,'text':'원본'}])
    assert a.settled==[120]

def test_search_uses_brave_and_fetches_original_not_snippet():
    seen=[]
    def transport(r):
        seen.append(r)
        return httpx.Response(200,json={'web':{'results':[{'url':'https://example.org/report','description':'가짜 스니펫'}]}})
    def fetch(url):return {'url':url,'title':'원문','text':'2025년 한국 고용률 5%','lineage':'example.org'}
    fact={'quote':'2025년 한국 고용률 5%','subject':'한국','period':'2025년','metric':'고용률','value':'5','unit':'%','publisher':None,'publishedAt':None}
    p,a=make(SDK(completion=response(fact)),transport,fetch)
    from factlens.contracts import Claim
    docs=p.search(Claim(id=str(uuid4()),text='한국 고용률 50%',startSeconds=0,endSeconds=1))
    assert len(docs)==1 and docs[0].text=='2025년 한국 고용률 5%'
    assert seen[0].url.host=='api.search.brave.com'
    assert seen[0].headers['X-Subscription-Token']=='test-key'
    assert len(a.settled)==2 and a.settled[0]==5000

def reviewed_source(monkeypatch):
    from factlens import meaning_review
    from factlens.retrieval import fetch_evidence
    from factlens.contracts import Claim
    quote='2024년 한국 실업률은 2.8%입니다.'
    html=('<meta name="publisher" content="시험기관"><meta name="datepublished" content="2025-03-25"><p>'+quote+'</p>').encode()
    source=fetch_evidence('https://example.org/reviewed',resolver=lambda h:['93.184.216.34'],transport=lambda *args:(200,{'content-type':'text/html; charset=utf-8'},html))
    policy=meaning_review.ReviewedPolicy.model_validate({'policyId':'reviewed-test','url':source['url'],'documentHash':source['sourceTrace']['textSha256'],'sourceKind':'paragraph','quote':quote,'quotePosition':source['text'].index(quote),'publisher':'시험기관','publishedAt':'2025-03-25','subject':'한국','period':'2024년','metric':'실업률','value':'2.8','unit':'%','definition':'연간 경제활동인구 대비 실업자 비율, 공표 소수 한 자리','precision':1,'reviewReference':source['url'],'reviewedAt':'2026-10-21'})
    monkeypatch.setattr(meaning_review,'DEFAULT_POLICIES',[policy])
    claim=Claim(id=str(uuid4()),text=quote,contextText=quote,startSeconds=0,endSeconds=1,subject='한국',period='2024년',metric='실업률',value='2.8',unit='%')
    return source,claim

def test_reviewed_primary_source_is_fetched_after_search_without_llm_inventing_fact(monkeypatch):
    source,claim=reviewed_source(monkeypatch)
    fetched=[]
    def fetch(url):
        fetched.append(url)
        return source
    sdk=SDK()
    p,accounting=make(sdk,lambda r:httpx.Response(200,json={'web':{'results':[]}}),fetch)
    documents=p.search(claim)
    assert len(documents)==1 and fetched==['https://example.org/reviewed']
    from factlens.validator import validate_evidence
    assert validate_evidence(claim,documents[0]).usable is True
    assert sdk.requests==[] and accounting.settled==[5000]

def test_unverified_claim_context_does_not_seed_reviewed_primary_sources(monkeypatch):
    source,claim=reviewed_source(monkeypatch)
    claim.contextText+=' 앞의 발언은 틀렸습니다.'
    def fetch(url):raise AssertionError('unverified claim must not seed a source')
    p,_=make(SDK(),lambda r:httpx.Response(200,json={'web':{'results':[]}}),fetch)
    assert p.search(claim)==[]

def test_search_errors_are_not_interpreted_as_no_evidence():
    p,_=make(SDK(),lambda r:httpx.Response(401,json={'error':'bad key'}))
    from factlens.contracts import Claim
    with pytest.raises(ProviderUnavailable,match='PROVIDER_AUTH_FAILED'):p.search(Claim(id=str(uuid4()),text='x',startSeconds=0,endSeconds=1))

def test_oversized_prompt_never_invokes_sdk():
    sdk=SDK();p,a=make(sdk)
    with pytest.raises(ProviderUnavailable,match='PROVIDER_INPUT_LIMIT'):p.extract([{'id':0,'start':0,'end':1,'text':'x'*100000}])
    assert sdk.requests==[] and a.used==0

def test_sdk_contract_serializes_requests_without_network(tmp_path):
    from openai import OpenAI
    requests=[]
    def transport(request):
        requests.append(request)
        if request.url.path.endswith('/audio/transcriptions'):
            return httpx.Response(200,json={'task':'transcribe','language':'korean','duration':3.0,'text':'원문','segments':[{'id':0,'seek':0,'start':0.0,'end':1.0,'text':'원문','tokens':[1],'temperature':0.0,'avg_logprob':-.1,'compression_ratio':1.0,'no_speech_prob':.1}]})
        return httpx.Response(200,json={'id':'chatcmpl-test','object':'chat.completion','created':1,'model':'gpt-4.1-mini','choices':[{'index':0,'message':{'role':'assistant','content':'{"claims":[]}','refusal':None},'finish_reason':'stop'}],'usage':{'prompt_tokens':100,'completion_tokens':50,'total_tokens':150}})
    sdk=OpenAI(api_key='test',base_url='https://api.openai.com/v1',max_retries=0,http_client=httpx.Client(transport=httpx.MockTransport(transport)))
    p,_=make(sdk);f=tmp_path/'a.wav';f.write_bytes(b'wave')
    assert p.transcribe(f)[0]['text']=='원문'
    assert p.extract([{'id':0,'start':0,'end':1,'text':'원문'}])==[]
    assert len(requests)==2
    assert b'timestamp_granularities' in requests[0].content
    assert json.loads(requests[1].content)['response_format']['json_schema']['strict'] is True


def test_model_refusal_is_invalid_but_usage_still_accounted():
    raw=response({'claims':[]});raw['choices'][0]['message']['refusal']='Cannot comply'
    p,a=make(SDK(completion=raw))
    with pytest.raises(ProviderUnavailable,match='PROVIDER_RESPONSE_INVALID'):p.extract([])
    assert a.settled==[120]

@pytest.mark.parametrize('indices',[[1,0],[0,2],[0,0]])
def test_claim_cannot_reorder_skip_or_duplicate_transcript_segments(indices):
    segments=[{'id':i,'start':i,'end':i+1,'text':str(i)} for i in range(3)]
    candidate={'quote':' '.join(str(i) for i in indices),'segment_ids':indices,'subject':None,'period':None,'metric':None,'value':None,'unit':None,'eligibility':'checkable'}
    p,_=make(SDK(completion=response({'claims':[candidate]})))
    with pytest.raises(ProviderUnavailable,match='PROVIDER_RESPONSE_INVALID'):p.extract(segments)

@pytest.mark.parametrize('field,value',[('value','5'),('subject','미국'),('period','2024년'),('metric','실업률'),('unit','명')])
def test_structured_claim_attributes_must_match_quote(field,value):
    candidate={'quote':'2025년 한국 고용률 50%','segment_ids':[0],'subject':'한국','period':'2025년','metric':'고용률','value':'50','unit':'%','eligibility':'checkable'}
    candidate[field]=value
    p,_=make(SDK(completion=response({'claims':[candidate]})))
    with pytest.raises(ProviderUnavailable,match='PROVIDER_RESPONSE_INVALID'):
        p.extract([{'id':0,'start':0,'end':1,'text':'2025년 한국 고용률 50%'}])


def test_extract_preserves_entire_transcript_including_adjacent_correction():
    candidate={'quote':'2025년 한국 고용률 50%','segment_ids':[0],'subject':'한국','period':'2025년','metric':'고용률','value':'50','unit':'%','eligibility':'checkable'}
    p,_=make(SDK(completion=response({'claims':[candidate]})))
    segments=[{'id':0,'start':0,'end':1,'text':'2025년 한국 고용률 50%'},{'id':1,'start':1,'end':2,'text':'이 주장은 틀렸다. 실제 수치는 5%다.'}]
    c=p.extract(segments)[0]
    assert c.contextText=='2025년 한국 고용률 50% 이 주장은 틀렸다. 실제 수치는 5%다.'
    from factlens.validator import validate_evidence
    from factlens.decision import decide
    from test_validator import document
    assert decide(c,[validate_evidence(c,document('50'))])=='REVIEW_REQUIRED'


def test_extract_discarding_candidates_keeps_correction_context_and_one_visible_limitation():
    candidate={'quote':'2025년 한국 고용률 50%','segment_ids':[0],'subject':'한국','period':'2025년','metric':'고용률','value':'50','unit':'%','eligibility':'checkable'}
    invalid={**candidate,'subject':'원문에 없는 대상'}
    sdk=SDK(completion=response({'claims':[invalid,candidate,invalid,invalid,invalid]}))
    p,_=make(sdk)
    before=p.limitations[:]
    segments=[{'id':0,'start':0,'end':1,'text':'2025년 한국 고용률 50%'},{'id':1,'start':1,'end':2,'text':'이 주장은 틀렸다. 실제 수치는 5%다.'}]
    claims=p.extract(segments)
    assert len(claims)==1
    c=claims[0]
    assert c.contextText=='2025년 한국 고용률 50% 이 주장은 틀렸다. 실제 수치는 5%다.'
    assert (c.startSeconds,c.endSeconds)==(0,1)
    assert p.limitations==before+['일부 주장 후보가 원문 검증을 통과하지 못해 제외되었습니다.']
    from factlens.validator import validate_evidence
    from factlens.decision import decide
    from test_validator import document
    assert decide(c,[validate_evidence(c,document('50'))])=='REVIEW_REQUIRED'
