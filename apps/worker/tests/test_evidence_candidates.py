from uuid import uuid4
import httpx
import pytest
from factlens.contracts import Claim
from factlens.metered import BudgetDenied
from test_live_providers import SDK, Model, response, make

class SequenceSDK(SDK):
    def __init__(self,facts):
        super().__init__();self.answers=iter(response(fact) for fact in facts)
    def create(self,**kwargs):
        self.requests.append(kwargs)
        return Model(next(self.answers))

def fact(value='50',quote=None):
    return {'quote':quote if quote is not None else f'2025년 한국 고용률 {value}%','subject':'한국','period':'2025년','metric':'고용률','value':value,'unit':'%','publisher':None,'publishedAt':None}
def claim():return Claim(id=str(uuid4()),text='2025년 한국 고용률 50%',contextText='2025년 한국 고용률 50%',startSeconds=0,endSeconds=1,subject='한국',period='2025년',metric='고용률',value='50',unit='%')
def search_response(urls):
    return lambda request:httpx.Response(200,json={'web':{'results':[{'url':url} for url in urls]}})
def document(url,value='50'):return {'url':url,'title':'원문','text':f'2025년 한국 고용률 {value}%','lineage':'example.org'}

def test_missing_quote_in_first_candidate_does_not_hide_later_source():
    urls=['https://example.org/empty','https://example.org/useful']
    sdk=SequenceSDK([fact(quote=''),fact()]);p,_=make(sdk,search_response(urls),document)
    docs=p.search(claim())
    assert [doc.url for doc in docs]==[urls[1]]
    assert len(sdk.requests)==2
    assert any('인용' in limitation for limitation in p.limitations)

def test_multiple_candidates_retain_different_values_for_later_conflict_checks():
    urls=['https://example.org/a','https://other.example/b']
    sdk=SequenceSDK([fact('50'),fact('5')])
    p,_=make(sdk,search_response(urls),lambda url:document(url,'50' if url==urls[0] else '5'))
    docs=p.search(claim())
    assert [doc.fact.value for doc in docs]==['50','5']
    assert [doc.url for doc in docs]==urls
    # Literal publication metadata is absent here; collection alone is not valid evidence.
    assert all(doc.publisher is None for doc in docs)

def test_duplicate_final_urls_are_not_structured_twice_and_limit_is_three_candidates():
    urls=['https://example.org/alias-a','https://example.org/alias-b','https://other.example/final','https://ignored.example/fourth']
    fetched=[]
    def fetch(url):
        fetched.append(url)
        return document('https://example.org/final' if url in urls[:2] else url)
    sdk=SequenceSDK([fact(),fact()]);p,a=make(sdk,search_response(urls),fetch)
    docs=p.search(claim())
    assert fetched==urls[:3]
    assert [doc.url for doc in docs]==['https://example.org/final',urls[2]]
    assert len(sdk.requests)==2 and len(a.settled)==3

def test_evidence_extraction_budget_denial_propagates_without_paid_sdk_call():
    sdk=SequenceSDK([fact()]);p,a=make(sdk,search_response(['https://example.org/a']),document)
    a.limit=5000
    with pytest.raises(BudgetDenied):p.search(claim())
    assert sdk.requests==[] and a.settled==[5000]
