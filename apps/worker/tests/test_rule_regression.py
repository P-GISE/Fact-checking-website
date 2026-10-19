import json
from dataclasses import asdict
import pytest
from factlens.rule_regression import RulesFixture, execute, fixture_fingerprint
from factlens.validator import RULE_VERSION
from test_validator import claim, document


def fixture():
    cases=[];gold=[]
    definitions=[('support','CONFIRMED',[document('50')],{}),('refute','REFUTED',[document('5')],{}),('conflict','REVIEW_REQUIRED',[document('50'),document('5')],{}),('absent','INSUFFICIENT',[],{}),('negative','REVIEW_REQUIRED',[document('50')],{'text':'2025년 한국 고용률 50%가 아니다.','contextText':'2025년 한국 고용률 50%가 아니다.'}),('excluded','EXCLUDED',[],{'eligibility':'excluded'}),('cropped','REVIEW_REQUIRED',[document('50')],{'contextText':'2025년 한국 고용률 50% 앞선 주장은 틀렸다. 실제 수치는 5%다.'})]
    for name,label,docs,changes in definitions:
        c=claim(id=name,**changes)
        cases.append({'claim':c.model_dump(),'documents':[asdict(d) for d in docs]})
        gold.append({'id':name,'originId':name,'split':'test','label':label})
    return RulesFixture.model_validate({'fixtureId':'rules-fixture','version':'1','dataset':{'datasetId':'rule-labels','version':'1','kind':'synthetic','annotationVersion':'manual-fixture-v1','claims':gold},'cases':cases})


def test_regression_executes_real_rules_with_distinct_provenance():
    f=fixture();report=execute(f,'test')
    assert report['regressionPassed'] is True
    assert report['researchValidation'] is False
    assert report['run']['system']=='RULES'
    assert report['run']['ruleVersion']==RULE_VERSION
    assert report['run']['modelVersion']=='not_applicable'
    assert report['metrics']['accuracy']==1 and report['counts']['cases']==7
    assert report['execution']['kind']=='production_rules'
    assert report['execution']['fixtureDigest']==fixture_fingerprint(f)
    assert all(len(digest)==64 for digest in report['execution']['sourceDigests'].values())
    assert {c['claimId']:c['verdict'] for c in report['cases']}=={'support':'CONFIRMED','refute':'REFUTED','conflict':'REVIEW_REQUIRED','absent':'INSUFFICIENT','negative':'REVIEW_REQUIRED','excluded':'EXCLUDED','cropped':'REVIEW_REQUIRED'}


def test_entire_inputs_are_hashed_even_if_gold_labels_stay_the_same():
    first=fixture();raw=first.model_dump();raw['cases'][0]['claim']['contextText']='앞선 수치는 틀렸다.'
    second=RulesFixture.model_validate(raw)
    a,b=execute(first,'test'),execute(second,'test')
    assert a['dataset']['digest']==b['dataset']['digest']
    assert a['execution']['fixtureDigest']!=b['execution']['fixtureDigest']
    assert b['regressionPassed'] is False and b['metrics']['accuracy']==pytest.approx(6/7)

@pytest.mark.parametrize('change',['missing','extra','duplicate','annotated'])
def test_fixture_rejects_unmatched_cases_or_research_data(change):
    raw=fixture().model_dump()
    if change=='missing':raw['cases'].pop()
    if change=='extra':raw['cases'][0]['claim']['id']='unknown'
    if change=='duplicate':raw['cases'].append(raw['cases'][0])
    if change=='annotated':raw['dataset']['kind']='annotated'
    with pytest.raises(ValueError):RulesFixture.model_validate(raw)


def test_runtime_failure_is_recorded_without_dropping_case_or_leaking_exception(monkeypatch):
    from factlens import validator
    original=validator.validate_evidence
    def failing(c,d):
        if c.id=='support':raise ValueError('sensitive external document')
        return original(c,d)
    monkeypatch.setattr(validator,'validate_evidence',failing)
    report=execute(fixture(),'test')
    assert report['counts']['cases']==7 and report['counts']['failed']==1
    assert report['counts']['missing']==0 and report['regressionPassed'] is False
    assert report['metrics']['accuracy']==pytest.approx(6/7)
    assert 'sensitive external document' not in json.dumps(report)


def test_cli_reports_match_failure_and_invalid_input_with_distinct_exits(tmp_path):
    import os,subprocess,sys
    from pathlib import Path
    path=tmp_path/'rules.json';path.write_text(fixture().model_dump_json())
    env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[1])}
    command=[sys.executable,'-m','factlens.rule_regression',str(path),'--split','test']
    good=subprocess.run(command,env=env,capture_output=True,text=True)
    assert good.returncode==0 and json.loads(good.stdout)['regressionPassed'] is True
    raw=fixture().model_dump();raw['dataset']['claims'][0]['label']='REFUTED';path.write_text(json.dumps(raw))
    mismatch=subprocess.run(command,env=env,capture_output=True,text=True)
    assert mismatch.returncode==1 and json.loads(mismatch.stdout)['regressionPassed'] is False
    path.write_text('{"secret":"do-not-print"}')
    invalid=subprocess.run(command,env=env,capture_output=True,text=True)
    assert invalid.returncode==2 and invalid.stdout==''
    assert invalid.stderr=='RULE_REGRESSION_INPUT_INVALID\n'


def test_valid_max_length_fixture_identifier_is_accepted_by_execution():
    raw=fixture().model_dump();raw['fixtureId']='f'*120
    report=execute(RulesFixture.model_validate(raw),'test')
    assert report['regressionPassed'] is True
    assert report['run']['runId']=='f'*120


def test_general_document_contract_keeps_uncertain_sources_non_decisive():
    from pathlib import Path
    path=Path(__file__).resolve().parents[3]/'evaluation/general-document-boundaries.json'
    f=RulesFixture.model_validate_json(path.read_text())
    report=execute(f,'test')
    assert report['regressionPassed'] is True
    assert report['counts']['cases']==8 and report['counts']['decisive']==0
    assert report['researchValidation'] is False
    cases={case['claimId']:case for case in report['cases']}
    for name in ('article-with-publication','adjacent-correction','two-periods','body-instruction','repeated-quote'):
        assert 'CONTEXT_REVIEW_REQUIRED' in cases[name]['checks'][0]['reasons']
    assert 'PUBLICATION_METADATA_MISSING' in cases['metadata-missing']['checks'][0]['reasons']
    assert 'QUOTE_NOT_VERIFIED' in cases['quote-not-present']['checks'][0]['reasons']
    assert cases['cropped-transcript']['verdict']=='REVIEW_REQUIRED'


def test_rule_runner_preserves_nested_source_trace_and_hashes_parser_code():
    from factlens.retrieval import fetch_evidence
    raw=fixture().model_dump()
    source=fetch_evidence('https://example.org/report',resolver=lambda h:['93.184.216.34'],transport=lambda *a:(200,{'content-type':'text/plain'},b'2025\xeb\x85\x84 \xed\x95\x9c\xea\xb5\xad \xea\xb3\xa0\xec\x9a\xa9\xeb\xa5\xa0 50%'))
    raw['cases'][0]['documents'][0]['sourceTrace']=source['sourceTrace']
    raw['dataset']['claims'][0]['label']='INSUFFICIENT'
    report=execute(RulesFixture.model_validate(raw),'test')
    checked=report['cases'][0]['checks'][0]
    assert report['regressionPassed'] is True
    assert checked['sourceTrace']['quoteOccurrences']==1
    assert 'SOURCE_AUTHENTICITY_UNVERIFIED' in checked['reasons']
    assert len(report['execution']['sourceDigests']['source_document'])==64
