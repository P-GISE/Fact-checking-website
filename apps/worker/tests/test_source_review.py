from copy import deepcopy
import pytest
from factlens.retrieval import fetch_evidence
from factlens.source_document import SourceTrace
from factlens.validator import validate_evidence
from test_validator import claim, document


def check(url='https://publisher.example/report',text='2025년 한국 고용률 50%',publisher='검토 기관',links=''):
    raw=fetch_evidence(url,resolver=lambda h:['93.184.216.34'],transport=lambda *a:(200,{'content-type':'text/html'},(f'<meta name="publisher" content="{publisher}"><p>{text}</p>'+links).encode()))
    d=document('50');d.url=url;d.text=raw['text'];d.publisher=publisher;d.sourceTrace=SourceTrace.model_validate(raw['sourceTrace'])
    return validate_evidence(claim(),d)


def policy():
    from factlens.source_review import SourceRegistry
    return SourceRegistry.model_validate({'version':'test-reviewed-v1','entries':[{'publisherId':'fixture-publisher','name':'검토 기관','hosts':['publisher.example'],'reviewedAt':'2026-10-19','reviewReference':'offline manually authored fixture, not actual publisher verification'}]})


def test_empty_production_registry_never_authenticates_a_page_claim():
    from factlens.source_review import review_sources
    result=review_sources([check()])[0]
    assert result.identity.status=='unregistered'
    assert result.independence=='unverified'
    assert result.identity.publisherId is None


@pytest.mark.parametrize('url,publisher,status',[
    ('https://publisher.example/report','검토 기관','registered_origin'),
    ('https://publisher.example.attacker.example/report','검토 기관','unregistered'),
    ('https://sub.publisher.example/report','검토 기관','unregistered'),
    ('http://publisher.example/report','검토 기관','insecure_origin'),
    ('https://publisher.example/report','사칭 기관','publisher_conflict')])
def test_reviewed_registry_uses_exact_https_origin_and_observed_publisher(url,publisher,status):
    from factlens.source_review import review_sources
    evidence=check(url,publisher=publisher)
    result=review_sources([evidence],policy())[0]
    assert result.identity.status==status
    assert result.registryVersion=='test-reviewed-v1'
    assert evidence.usable is False and 'SOURCE_AUTHENTICITY_UNVERIFIED' in evidence.reasons


def test_duplicates_and_declared_citation_are_one_possible_dependency_group():
    from factlens.source_review import review_sources
    a=check('https://a.example/a',links='<blockquote cite="https://c.example/c">ref</blockquote>')
    b=deepcopy(a);b.url='https://b.example/b';b.sourceTrace.finalUrl=b.url
    c=check('https://c.example/c',text='다른 원문')
    reviews=review_sources([a,b,c])
    assert len({r.groupId for r in reviews})==1
    assert all(r.groupSize==3 and r.independence=='unverified' for r in reviews)
    assert 'SAME_TEXT_HASH' in reviews[0].signals
    assert 'DECLARED_SOURCE_LINK' in reviews[0].signals
    assert set(reviews[0].relatedUrls)=={b.url,c.url}


def test_navigation_links_and_same_host_do_not_prove_republication_or_independence():
    from factlens.source_review import review_sources
    a=check('https://a.example/a',links='<a href="https://b.example/b">navigation</a>')
    b=check('https://b.example/b',text='다른 내용')
    c=check('https://a.example/other',text='또 다른 내용')
    reviews=review_sources([a,b,c])
    assert len({r.groupId for r in reviews})==3
    assert all(r.independence=='unverified' and r.groupSize==1 for r in reviews)


def test_registry_rejects_ambiguous_hosts_and_unreviewed_entries():
    from factlens.source_review import SourceRegistry
    raw=policy().model_dump();raw['entries'].append({**raw['entries'][0],'publisherId':'other'})
    with pytest.raises(ValueError):SourceRegistry.model_validate(raw)
    raw=policy().model_dump();raw['entries'][0]['reviewReference']=''
    with pytest.raises(ValueError):SourceRegistry.model_validate(raw)


def test_review_has_five_candidate_bound_and_does_not_change_verdict_fields():
    from factlens.source_review import review_sources
    evidence=check();original=evidence.model_dump()
    review_sources([evidence],policy())
    assert evidence.model_dump()==original
    with pytest.raises(ValueError,match='SOURCE_REVIEW_LIMIT'):review_sources([evidence]*6)


def test_pipeline_preserves_review_versions_and_dependency_results(tmp_path):
    from uuid import uuid4
    from factlens.pipeline import run_analysis
    from test_pipeline import TestProviders
    from test_validator import claim as numeric_claim
    class SourceProviders(TestProviders):
        def extract(self,segments):return [numeric_claim(id=str(uuid4()))]
        def search(self,c):
            a=document('50');b=document('50');b.url+='?second=1'
            return [a,b]
        def versions(self):return {'sourceReviewVersion':'untrusted-override'}
    result=run_analysis({'consent':True,'path':str(tmp_path/'audio.wav'),'duration':1},SourceProviders())
    assert result.versions['sourceReviewVersion']=='source-review-v1'
    assert result.versions['sourceRegistryVersion']=='source-registry-2026-10-21'
    assert result.claims[0].evidence[0].sourceReview.independence=='unverified'
    # Matching host alone never creates a shared-origin or independence claim.
    assert result.claims[0].evidence[0].sourceReview.groupSize==1


def test_invalid_urls_do_not_share_a_dependency_group_identifier():
    from factlens.source_review import review_sources
    a=validate_evidence(claim(),document('50'));b=deepcopy(a)
    a.url='javascript:one';b.url='javascript:two'
    reviews=review_sources([a,b])
    assert reviews[0].groupId!=reviews[1].groupId
    assert all(r.groupSize==1 and r.identity.status=='trace_unavailable' for r in reviews)


def test_registry_hosts_cannot_contain_ports_or_blank_review_provenance():
    from factlens.source_review import SourceRegistry
    raw=policy().model_dump();raw['entries'][0]['hosts']=['publisher.example:80']
    with pytest.raises(ValueError):SourceRegistry.model_validate(raw)
    raw=policy().model_dump();raw['entries'][0]['reviewReference']='   '
    with pytest.raises(ValueError):SourceRegistry.model_validate(raw)
