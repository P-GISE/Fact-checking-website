import pytest
from test_source_trace import fetched,traced_document
from test_validator import claim
from factlens.validator import validate_evidence


def audit(html):
    raw=fetched(html)
    assert raw['sourceTrace'].get('tableReferenceAudit') is not None
    return raw['sourceTrace']['tableReferenceAudit']


def test_explicit_unique_same_table_header_is_only_a_structural_reference():
    result=audit('<table><tr><th id="rate">고용률</th><td headers="rate">2025년 한국 고용률 50%</td></tr></table>')
    assert result['version']=='table-reference-audit-v1' and result['meaningVerified'] is False
    assert result['complete'] is True
    assert result['references']==[{'cellBlockIndex':1,'declaredId':'rate','status':'resolved_same_table_header','headerBlockIndex':0}]


@pytest.mark.parametrize('html,status',[
 ('<th id="rate">첫째</th><th id="rate">둘째</th><td headers="rate">value</td>','duplicate_id'),
 ('<td headers="missing">value</td>','missing_id'),
 ('<td id="value">value</td><td headers="value">other</td>','not_header'),
])
def test_ambiguous_missing_and_non_header_ids_are_not_resolved(html,status):
    r=audit('<table><tr>'+html+'</tr></table>')
    assert r['references'][0]['status']==status and r['references'][0]['headerBlockIndex'] is None


def test_cross_table_and_excluded_node_duplicate_ids_do_not_resolve():
    r=audit('<table><tr><th id="other">other</th></tr></table><table><tr><td headers="other">value</td></tr></table>')
    assert r['references'][0]['status']=='cross_table'
    r=audit('<script id="rate">ignored</script><table><tr><th id="rate">rate</th><td headers="rate">value</td></tr></table>')
    assert r['references'][0]['status']=='duplicate_id'


def test_reference_volume_and_invalid_identifiers_mark_partial_observation():
    r=audit('<table><tr><th id="rate">rate</th>'+('<td headers="rate">value</td>'*33)+'</tr></table>')
    assert len(r['references'])==32 and r['complete'] is False
    r=audit('<table><tr><td headers="'+('a'*100)+'">value</td></tr></table>')
    assert r['complete'] is False and r['references']==[]


def test_header_reference_cannot_change_external_truth_or_unverified_table_gate():
    checked=validate_evidence(claim(),traced_document('<table><tr><th id="rate">2025년 한국 고용률</th><td headers="rate">2025년 한국 고용률 50%</td></tr></table>'))
    assert checked.relation=='INSUFFICIENT' and not checked.usable
    assert 'TABLE_CONTEXT_UNVERIFIED' in checked.reasons


def test_reference_trace_rejects_forged_cross_table_and_non_header_resolution():
    from factlens.source_document import SourceTrace
    raw=fetched('<table><tr><th id="rate">rate</th><td headers="rate">value</td></tr></table><table><tr><th>other</th></tr></table>')['sourceTrace']
    assert raw.get('tableReferenceAudit') is not None
    for index in [1,2,99]:
        altered={**raw,'tableReferenceAudit':{**raw['tableReferenceAudit'],'references':[{**raw['tableReferenceAudit']['references'][0],'headerBlockIndex':index}]}}
        with pytest.raises(ValueError):SourceTrace.model_validate(altered)


def test_reference_and_cue_versions_are_server_owned_and_hashed(tmp_path):
    from factlens.pipeline import run_analysis
    from test_pipeline import TestProviders
    from test_rule_regression import fixture
    from factlens.rule_regression import execute
    class Versions(TestProviders):
        def versions(self):return {'tableReferenceVersion':'forged','tableCueVersion':'forged'}
    result=run_analysis({'consent':True,'path':str(tmp_path/'audio.wav'),'duration':1},Versions())
    assert result.versions['tableReferenceVersion']=='table-reference-audit-v1'
    assert result.versions['tableCueVersion']=='table-cue-audit-v1'
    report=execute(fixture(),'test')
    assert len(report['execution']['sourceDigests']['table_references'])==64
    assert report['execution']['tableReferenceVersion']=='table-reference-audit-v1'


def test_partial_structure_cannot_claim_complete_reference_audit():
    from factlens.source_document import SourceTrace
    raw=fetched('<table><tr><th id="rate">rate</th><td headers="rate">value</td></tr></table>')['sourceTrace']
    raw['structureComplete']=False
    with pytest.raises(ValueError):SourceTrace.model_validate(raw)
