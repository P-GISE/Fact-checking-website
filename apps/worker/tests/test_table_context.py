from factlens.validator import validate_evidence
from test_validator import claim
from test_source_trace import traced_document


def context_for(html):
    checked=validate_evidence(claim(),traced_document(html))
    context=getattr(checked.sourceTrace,'tableContext',None)
    assert context is not None
    assert not checked.usable and checked.relation=='INSUFFICIENT'
    assert 'TABLE_CONTEXT_UNVERIFIED' in checked.reasons
    return context


def test_table_quote_retains_same_table_header_caption_and_note_text_as_candidates():
    context=context_for('<table><caption>15세 이상 잠정 통계</caption><tr><th>전년 대비</th><td>2025년 한국 고용률 50%<aside>정정: 전체 고용률 아님</aside></td></tr></table>')
    assert [(f.kind,f.text) for f in context.fragments]==[('caption','15세 이상 잠정 통계'),('table_header','전년 대비'),('note','정정: 전체 고용률 아님')]
    assert context.version=='table-context-v1'
    assert context.association=='same_table_only' and context.meaningVerified is False
    assert context.complete is True


def test_different_and_nested_table_context_is_not_assigned_to_the_quote():
    context=context_for('<table><caption>outer caption</caption><tr><th>outer header</th><td>2025년 한국 고용률 50%<table><caption>inner caption</caption><tr><th>inner header</th></tr></table></td></tr></table><table><caption>other caption</caption><tr><th>other header</th></tr></table>')
    assert [f.text for f in context.fragments]==['outer caption','outer header']


def test_context_count_is_bounded_and_incompleteness_is_explicit():
    context=context_for('<table><tr>'+('<th>candidate</th>'*17)+'<td>2025년 한국 고용률 50%</td></tr></table>')
    assert len(context.fragments)==16 and context.complete is False


def test_long_context_is_bounded_with_a_truncation_marker():
    context=context_for('<table><tr><th>'+('긴 설명 '*200)+'</th><td>2025년 한국 고용률 50%</td></tr></table>')
    assert len(context.fragments[0].text)==500
    assert context.fragments[0].truncated is True and context.complete is False


def test_ambiguous_or_unverified_quote_cannot_select_table_context():
    duplicate=traced_document('<table><tr><th>header</th><td>2025년 한국 고용률 50%</td><td>2025년 한국 고용률 50%</td></tr></table>')
    assert getattr(validate_evidence(claim(),duplicate).sourceTrace,'tableContext',None) is None
    invalid=traced_document('<table><tr><th>header</th><td>2025년 한국 고용률 50%</td></tr></table>');invalid.text+=' changed'
    assert getattr(validate_evidence(claim(),invalid).sourceTrace,'tableContext',None) is None


def test_incomplete_source_structure_never_claims_complete_context():
    doc=traced_document('<table><tr><th>header</th><td>2025년 한국 고용률 50%</td></tr></table>');doc.sourceTrace.structureComplete=False
    doc.sourceTrace.tableReferenceAudit.complete=False
    context=getattr(validate_evidence(claim(),doc).sourceTrace,'tableContext',None)
    assert context is not None and context.complete is False


def test_context_version_is_server_controlled_and_regression_hashes_its_module(tmp_path):
    from factlens.pipeline import run_analysis
    from test_pipeline import TestProviders
    from test_rule_regression import fixture
    from factlens.rule_regression import execute
    class VersionProviders(TestProviders):
        def versions(self):return {'tableContextVersion':'untrusted'}
    result=run_analysis({'consent':True,'path':str(tmp_path/'audio.wav'),'duration':1},VersionProviders())
    assert result.versions['tableContextVersion']=='table-context-v1'
    report=execute(fixture(),'test')
    assert report['execution']['tableContextVersion']=='table-context-v1'
    assert len(report['execution']['sourceDigests']['table_context'])==64


def test_incoming_context_is_rebuilt_instead_of_reusing_a_previous_quote_context():
    doc=traced_document('<table><tr><th>original</th><td>2025년 한국 고용률 50%</td></tr></table>')
    checked=validate_evidence(claim(),doc)
    doc.sourceTrace=checked.sourceTrace
    doc.sourceTrace.tableContext.fragments[0].text='forged old context'
    current=validate_evidence(claim(),doc)
    assert current.sourceTrace.tableContext.fragments[0].text=='original'
    doc.position+=1
    assert validate_evidence(claim(),doc).sourceTrace.tableContext is None


def test_context_trace_roundtrip_rejects_dangling_and_cross_table_references():
    import pytest
    from factlens.source_document import SourceTrace
    doc=traced_document('<table><tr><th>header</th><td>2025년 한국 고용률 50%</td></tr></table>')
    trace=validate_evidence(claim(),doc).sourceTrace
    assert SourceTrace.model_validate(trace.model_dump()).tableContext==trace.tableContext
    raw=trace.model_dump();raw['tableContext']['fragments'][0]['blockIndex']=99
    with pytest.raises(ValueError,match='INVALID_TABLE_CONTEXT'):SourceTrace.model_validate(raw)
    raw=trace.model_dump();raw['tableContext']['tableIndex']=1
    with pytest.raises(ValueError,match='INVALID_TABLE_CONTEXT'):SourceTrace.model_validate(raw)


def test_unicode_context_limit_uses_codepoints_not_utf16_units():
    context=context_for('<table><tr><th>'+('😀'*600)+'</th><td>2025년 한국 고용률 50%</td></tr></table>')
    assert context.fragments[0].text=='😀'*500
    assert context.fragments[0].truncated and not context.complete


def test_serialized_context_must_match_a_single_verified_quote_table():
    import pytest
    from factlens.source_document import SourceTrace
    doc=traced_document('<table><tr><th>first</th><td>2025년 한국 고용률 50%</td></tr></table><table><tr><th>second</th></tr></table>')
    trace=validate_evidence(claim(),doc).sourceTrace
    wrong=trace.model_dump();wrong['tableContext']['tableIndex']=1
    wrong['tableContext']['fragments']=[{'blockIndex':2,'kind':'table_header','text':'second','truncated':False}]
    with pytest.raises(ValueError,match='INVALID_TABLE_CONTEXT'):SourceTrace.model_validate(wrong)
    for change in ({'quoteOccurrences':2},{'quoteOccurrences':0},{'quoteBlockIndexes':[]}):
        with pytest.raises(ValueError,match='INVALID_TABLE_CONTEXT'):SourceTrace.model_validate({**trace.model_dump(),**change})


def test_literal_period_denominator_correction_and_unit_cues_remain_unverified():
    context=context_for('<table><caption>2025년 / 단위: % / 분모: 15세 이상 / 정정 공지</caption><tr><td>2025년 한국 고용률 50%</td></tr></table>')
    audit=getattr(context,'cueAudit',None)
    assert audit is not None and audit.version=='table-cue-audit-v1' and audit.meaningVerified is False
    assert {cue.kind for cue in audit.cues}=={'period','denominator','correction','unit'}
    assert audit.complete
    for cue in audit.cues:
        assert cue.blockIndex==0 and context.fragments[0].text[cue.offset:cue.offset+len(cue.text)]==cue.text


def test_cue_audit_is_bounded_and_cannot_claim_complete_after_truncation():
    context=context_for('<table><tr>'+('<th>2025년 분모 정정 단위</th>'*16)+'<td>2025년 한국 고용률 50%</td></tr></table>')
    audit=getattr(context,'cueAudit',None)
    assert audit is not None and len(audit.cues)==32 and audit.complete is False


def test_serialized_cue_must_match_the_bounded_fragment():
    import pytest
    from factlens.source_document import SourceTrace
    doc=traced_document('<table><caption>정정 공지</caption><tr><td>2025년 한국 고용률 50%</td></tr></table>')
    trace=validate_evidence(claim(),doc).sourceTrace
    assert getattr(trace.tableContext,'cueAudit',None) is not None
    raw=trace.model_dump();raw['tableContext']['cueAudit']['cues'][0]['text']='forged'
    with pytest.raises(ValueError):SourceTrace.model_validate(raw)
