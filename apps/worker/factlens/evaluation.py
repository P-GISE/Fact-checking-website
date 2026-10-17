"""Offline label scoring only: never invokes providers or validates research claims."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Annotated, Literal, Self
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from factlens.contracts import Verdict

LABELS=('CONFIRMED','REFUTED','INSUFFICIENT','REVIEW_REQUIRED','EXCLUDED')
Split=Literal['dev','test']
Name=Annotated[str,StringConstraints(strip_whitespace=True,min_length=1,max_length=120)]

class Strict(BaseModel):
    model_config=ConfigDict(strict=True,extra='forbid')

class GoldClaim(Strict):
    id:Name
    originId:Name
    split:Split
    label:Verdict

class Dataset(Strict):
    datasetId:Name
    version:Name
    kind:Literal['synthetic','annotated']
    annotationVersion:Name
    claims:list[GoldClaim]=Field(min_length=1,max_length=10000)

    @model_validator(mode='after')
    def validate_partition(self)->Self:
        identifiers=set();origins={}
        for claim in self.claims:
            if claim.id in identifiers:raise ValueError('DUPLICATE_CLAIM_ID')
            identifiers.add(claim.id)
            if claim.originId in origins and origins[claim.originId]!=claim.split:
                raise ValueError('ORIGIN_SPLIT_LEAKAGE')
            origins[claim.originId]=claim.split
        return self

class Prediction(Strict):
    claimId:Name
    status:Literal['completed','failed']
    verdict:Verdict|None

    @model_validator(mode='after')
    def validate_status(self)->Self:
        if (self.status=='completed')!=(self.verdict is not None):
            raise ValueError('INVALID_PREDICTION_STATUS')
        return self

class Run(Strict):
    runId:Name
    system:Literal['A','B','C']
    datasetDigest:Annotated[str,StringConstraints(pattern=r'^[0-9a-f]{64}$')]
    modelVersion:Name
    promptVersion:Name
    ruleVersion:Name
    predictions:list[Prediction]=Field(max_length=10000)

    @model_validator(mode='after')
    def validate_ids(self)->Self:
        ids=[item.claimId for item in self.predictions]
        if len(set(ids))!=len(ids):raise ValueError('DUPLICATE_PREDICTION_ID')
        return self

def fingerprint(dataset:Dataset)->str:
    canonical=json.dumps(dataset.model_dump(),ensure_ascii=False,sort_keys=True,separators=(',',':'))
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()

def score(dataset:Dataset,run:Run,split:Split)->dict:
    if split not in ('dev','test'):raise ValueError('INVALID_SPLIT')
    digest=fingerprint(dataset)
    if run.datasetDigest!=digest:raise ValueError('DATASET_DIGEST_MISMATCH')
    known={claim.id for claim in dataset.claims}
    if any(p.claimId not in known for p in run.predictions):raise ValueError('UNKNOWN_PREDICTION_ID')
    gold=[claim for claim in dataset.claims if claim.split==split]
    if not gold:raise ValueError('EMPTY_SPLIT')
    predictions={item.claimId:item for item in run.predictions}
    matrix={label:{column:0 for column in (*LABELS,'MISSING')} for label in LABELS}
    counts=dict(cases=len(gold),completed=0,missing=0,failed=0,decisive=0,wrongDecisive=0,abstained=0)
    for claim in gold:
        prediction=predictions.get(claim.id)
        if prediction is None:counts['missing']+=1
        elif prediction.status=='failed':counts['failed']+=1
        else:counts['completed']+=1
        verdict=prediction.verdict if prediction is not None else None
        matrix[claim.label][verdict or 'MISSING']+=1
        if verdict in ('CONFIRMED','REFUTED'):
            counts['decisive']+=1
            if verdict!=claim.label:counts['wrongDecisive']+=1
        if verdict in ('INSUFFICIENT','REVIEW_REQUIRED'):counts['abstained']+=1
    per_class={}
    for label in LABELS:
        tp=matrix[label][label]
        fp=sum(matrix[other][label] for other in LABELS if other!=label)
        fn=sum(matrix[label][other] for other in (*LABELS,'MISSING') if other!=label)
        per_class[label]={'support':sum(matrix[label].values()),'tp':tp,'fp':fp,'fn':fn,
                          'f1':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0.0}
    n=counts['cases'];correct=sum(matrix[label][label] for label in LABELS)
    return {
        'protocolVersion':'verdict-offline-v1','researchValidation':False,
        'scope':'manually_aligned_claim_labels_only',
        'dataset':{'id':dataset.datasetId,'version':dataset.version,'digest':digest,'kind':dataset.kind,
                   'annotationVersion':dataset.annotationVersion,'split':split},
        'run':run.model_dump(exclude={'predictions'}),'metadataProvenance':'caller_declared',
        'counts':counts,'labels':list(LABELS),'confusionMatrix':matrix,'perClass':per_class,
        'metrics':{'accuracy':correct/n,'macroF1':sum(c['f1'] for c in per_class.values())/len(LABELS),
                   'completionRate':counts['completed']/n,'abstentionRate':counts['abstained']/n,
                   'falseVerdictRate':counts['wrongDecisive']/n,
                   'decisiveErrorRate':counts['wrongDecisive']/counts['decisive'] if counts['decisive'] else None},
        'definitions':{'macroF1':'fixed five-label average; absent-class F1=0',
                       'missingAndFailed':'included in all-case denominators and gold-label false negatives',
                       'abstention':'completed INSUFFICIENT or REVIEW_REQUIRED; failures and EXCLUDED are separate',
                       'falseVerdictRate':'wrong CONFIRMED/REFUTED divided by all selected gold cases',
                       'decisiveErrorRate':'wrong CONFIRMED/REFUTED divided by completed decisive predictions; zero denominator=null'},
        'notMeasured':['ClaimRecall','EvidencePrecisionAtK','EvidenceValidity','CrossModalF1','Latency','Cost'],
    }

def _load(path:str,schema:type[BaseModel]):
    with Path(path).open('rb') as stream:data=stream.read(2097153)
    if len(data)>2097152:raise ValueError('INPUT_TOO_LARGE')
    return schema.model_validate_json(data)

def main(argv=None)->int:
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    digest=commands.add_parser('fingerprint');digest.add_argument('dataset')
    evaluate=commands.add_parser('score');evaluate.add_argument('dataset');evaluate.add_argument('run')
    evaluate.add_argument('--split',choices=('dev','test'),required=True)
    args=parser.parse_args(argv)
    try:
        dataset=_load(args.dataset,Dataset)
        result=fingerprint(dataset) if args.command=='fingerprint' else score(dataset,_load(args.run,Run),args.split)
    except (OSError,ValueError):
        print('EVALUATION_INPUT_INVALID',file=sys.stderr)
        return 2
    print(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False) if isinstance(result,dict) else result)
    return 0

if __name__=='__main__':sys.exit(main())
