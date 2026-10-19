"""Execute production numeric rules on synthetic inputs; never invokes a model."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit
from pydantic import ConfigDict, Field, field_validator, model_validator
from typing import Self
from factlens import contracts, decision, evaluation, validator, source_document, source_review, table_context
from factlens.contracts import Claim
from factlens.evaluation import Dataset, Run, Strict, Name, Split, fingerprint, score, load_input

class InputClaim(Claim):
    model_config=ConfigDict(strict=True,extra='forbid')

class InputFact(Strict):
    subject:str
    period:str
    metric:str
    value:str
    unit:str

class InputDocument(Strict):
    url:str=Field(max_length=2000)
    title:str=Field(max_length=2000)
    text:str=Field(max_length=20000)
    quote:str=Field(max_length=2000)
    position:int=Field(ge=0)
    publisher:str|None
    publishedAt:str|None
    fact:InputFact
    lineage:Name|None=None
    sourceTrace:source_document.SourceTrace|None=None

    @field_validator('url')
    @classmethod
    def document_url(cls,value:str)->str:
        parsed=urlsplit(value)
        if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
            raise ValueError('INVALID_DOCUMENT_URL')
        return value

class RuleCase(Strict):
    claim:InputClaim
    documents:list[InputDocument]=Field(max_length=5)

class RulesFixture(Strict):
    fixtureId:Name
    version:Name
    dataset:Dataset
    cases:list[RuleCase]=Field(min_length=1,max_length=10000)

    @model_validator(mode='after')
    def matching_cases(self)->Self:
        ids=[case.claim.id for case in self.cases]
        if self.dataset.kind!='synthetic':raise ValueError('SYNTHETIC_FIXTURE_REQUIRED')
        if len(ids)!=len(set(ids)):raise ValueError('DUPLICATE_RULE_CASE')
        if set(ids)!={claim.id for claim in self.dataset.claims}:raise ValueError('RULE_CASE_ID_MISMATCH')
        return self

def fixture_fingerprint(fixture:RulesFixture)->str:
    canonical=json.dumps(fixture.model_dump(),sort_keys=True,ensure_ascii=False,separators=(',',':'))
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()

def execute(fixture:RulesFixture,split:Split)->dict:
    selected={claim.id:claim for claim in fixture.dataset.claims if claim.split==split}
    predictions=[];diagnostics=[]
    for case in fixture.cases:
        if case.claim.id not in selected:continue
        try:
            documents=[validator.EvidenceDocument(**{**doc.model_dump(),'fact':validator.Fact(**doc.fact.model_dump()),'sourceTrace':doc.sourceTrace}) for doc in case.documents]
            checks=[validator.validate_evidence(case.claim,document) for document in documents]
            for check,review in zip(checks,source_review.review_sources(checks)):
                check.sourceReview=review
            verdict=decision.decide(case.claim,checks)
            predictions.append({'claimId':case.claim.id,'status':'completed','verdict':verdict})
            diagnostics.append({'claimId':case.claim.id,'status':'completed','verdict':verdict,
                                'expected':selected[case.claim.id].label,'claimIssues':validator.claim_issues(case.claim),
                                'checks':[check.model_dump() for check in checks]})
        except Exception:
            # An execution failure remains in the evaluator denominator. Never
            # expose exception text that might contain a document or credentials.
            predictions.append({'claimId':case.claim.id,'status':'failed','verdict':None})
            diagnostics.append({'claimId':case.claim.id,'status':'failed','verdict':None,'error':'RULE_EXECUTION_FAILED'})
    run=Run(runId=fixture.fixtureId,system='RULES',datasetDigest=fingerprint(fixture.dataset),
            modelVersion='not_applicable',promptVersion='not_applicable',ruleVersion=validator.RULE_VERSION,
            predictions=predictions)
    report=score(fixture.dataset,run,split)
    modules={'validator':validator.__file__,'decision':decision.__file__,'contracts':contracts.__file__,
             'evaluation':evaluation.__file__,'table_context':table_context.__file__,'source_document':source_document.__file__,'source_review':source_review.__file__,'source_registry':str(Path(source_review.__file__).with_name('source_registry.json')),'rule_regression':__file__}
    report['execution']={'kind':'production_rules','fixtureId':fixture.fixtureId,'fixtureVersion':fixture.version,
                         'fixtureDigest':fixture_fingerprint(fixture),
                         'sourceDigests':{name:hashlib.sha256(Path(path).read_bytes()).hexdigest() for name,path in modules.items()},
                         'modelsInvoked':False,'tableContextVersion':table_context.CONTEXT_VERSION,'sourceReviewVersion':source_review.REVIEW_VERSION,'sourceRegistryVersion':source_review.DEFAULT_REGISTRY.version}
    report['scope']='synthetic_numeric_rule_regression_only'
    report['metadataProvenance']='local_rule_execution_and_caller_supplied_fixture'
    report['notMeasured']+=['STTQuality','SourceAuthenticity']
    report['cases']=diagnostics
    report['regressionPassed']=report['counts']['failed']==0 and report['metrics']['accuracy']==1
    return report

def main(argv=None)->int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('fixture');parser.add_argument('--split',choices=('dev','test'),required=True)
    args=parser.parse_args(argv)
    try:
        report=execute(load_input(args.fixture,RulesFixture),args.split)
    except (OSError,ValueError):
        print('RULE_REGRESSION_INPUT_INVALID',file=sys.stderr)
        return 2
    print(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False))
    return 0 if report['regressionPassed'] else 1

if __name__=='__main__':sys.exit(main())
