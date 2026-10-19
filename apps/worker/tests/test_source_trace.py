from copy import deepcopy
from factlens.retrieval import fetch_evidence
from factlens.source_document import SourceTrace
from factlens.validator import validate_evidence
from factlens.contracts import EvidenceCheck
from test_validator import claim, document
from test_evidence_candidates import SequenceSDK, fact, search_response
from test_live_providers import make


def fetched(body):
    return fetch_evidence('https://example.org/report',resolver=lambda h:['93.184.216.34'],
        transport=lambda *a:(200,{'content-type':'text/html'},body.encode()))


def traced_document(body):
    raw=fetched(body);d=document('50');d.text=raw['text'];d.position=d.text.index(d.quote)
    d.sourceTrace=SourceTrace.model_validate(raw['sourceTrace'])
    return d


def test_server_publication_observations_replace_model_guesses_and_reach_checks():
    raw=fetched('<meta name="publisher" content="직접 발행 기관"><meta property="article:published_time" content="2026-01-02"><p>2025년 한국 고용률 50%</p>')
    answer=fact();answer.update(publisher='모델이 만든 기관',publishedAt='1999-01-01')
    provider,_=make(SequenceSDK([answer]),search_response([raw['url']]),lambda url:deepcopy(raw))
    d=provider.search(claim())[0]
    assert d.publisher=='직접 발행 기관' and d.publishedAt=='2026-01-02'
    check=validate_evidence(claim(),d)
    assert check.sourceTrace is not None
    assert check.sourceTrace.quoteOccurrences==1
    assert check.sourceTrace.quoteBlockIndexes==[0]
    assert check.sourceTrace.bodySha256==raw['sourceTrace']['bodySha256']
    # Observation is not authentication; complete-source v2 rules are still applied.
    assert check.sourceTrace.publication.publisher.state=='observed'
    assert not check.usable and 'SOURCE_AUTHENTICITY_UNVERIFIED' in check.reasons


def test_repeated_quote_has_explicit_ambiguity_without_picking_a_single_source_location():
    d=traced_document('<p>2025년 한국 고용률 50%</p><p>2025년 한국 고용률 50%</p>')
    checked=validate_evidence(claim(),d)
    assert not checked.usable and 'QUOTE_AMBIGUOUS' in checked.reasons
    assert checked.sourceTrace.quoteOccurrences==2
    assert checked.sourceTrace.quoteBlockIndexes==[]


def test_changed_original_cannot_reuse_an_earlier_source_hash():
    d=traced_document('<p>2025년 한국 고용률 50%</p>')
    d.text+=' 정정'
    assert 'SOURCE_TRACE_MISMATCH' in validate_evidence(claim(),d).reasons


def test_incomplete_structure_and_extraction_are_explicitly_non_decisive():
    d=traced_document('<p>2025년 한국 고용률 50%</p>')
    d.sourceTrace.structureComplete=False;d.sourceTrace.extractionTruncated=True
    checked=validate_evidence(claim(),d)
    assert 'SOURCE_STRUCTURE_INCOMPLETE' in checked.reasons
    assert 'SOURCE_EXTRACTION_TRUNCATED' in checked.reasons
    assert not checked.usable


def test_free_form_publisher_cannot_authenticate_a_traced_plain_record():
    d=traced_document('<p>2025년 한국 고용률 50%</p>')
    checked=validate_evidence(claim(),d)
    assert 'PUBLICATION_METADATA_UNVERIFIED' in checked.reasons
    assert not checked.usable


def test_legacy_evidence_does_not_acquire_invented_source_trace():
    checked=validate_evidence(claim(),document('50'))
    assert checked.sourceTrace is None
    legacy=EvidenceCheck.model_validate(checked.model_dump(exclude={'sourceTrace'}))
    assert legacy.sourceTrace is None


def test_table_cell_quote_explicitly_requires_row_column_and_note_context():
    d=traced_document('<table><caption>잠정치, 전체가 아닌 특정 연령</caption><tr><th>전년 대비</th></tr><tr><td>2025년 한국 고용률 50%</td></tr></table>')
    checked=validate_evidence(claim(),d)
    assert 'TABLE_CONTEXT_UNVERIFIED' in checked.reasons
    assert not checked.usable and checked.relation=='INSUFFICIENT'


def test_table_header_quote_is_not_treated_as_an_observed_data_record():
    d=traced_document('<table><tr><th>2025년 한국 고용률 50%</th><td>해당 없음</td></tr></table>')
    assert 'TABLE_CONTEXT_UNVERIFIED' in validate_evidence(claim(),d).reasons


def test_unrelated_table_does_not_relabel_a_paragraph_quote():
    d=traced_document('<p>2025년 한국 고용률 50%</p><table><tr><td>다른 자료</td></tr></table>')
    assert 'TABLE_CONTEXT_UNVERIFIED' not in validate_evidence(claim(),d).reasons
