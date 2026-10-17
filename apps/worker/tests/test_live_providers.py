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

def test_extract_validates_quote_and_owns_ids():
    candidate={'quote':'2025년 한국 고용률 50%','segment_ids':[0],'subject':'한국','period':'2025년','metric':'고용률','value':'50','unit':'%','eligibility':'checkable'}
    sdk=SDK(completion=response({'claims':[candidate]}));p,a=make(sdk)
    claims=p.extract([{'id':0,'start':0,'end':2,'text':'2025년 한국 고용률 50%'}])
    assert claims[0].text=='2025년 한국 고용률 50%' and claims[0].startSeconds==0
    assert claims[0].verdict=='INSUFFICIENT'
    assert a.settled==[120]
    assert sdk.requests[0]['max_completion_tokens']==2048

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
