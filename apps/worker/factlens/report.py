"""A transparent claim summary, never an overall video truth probability."""
from collections import Counter
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

SUMMARY_VERSION='claim-summary-v1'
REVIEWED_SUMMARY_VERSION='reviewed-summary-v1'


class ReviewedEvidenceSummary(BaseModel):
    model_config=ConfigDict(extra='forbid')
    version:Literal['reviewed-summary-v1']=REVIEWED_SUMMARY_VERSION
    claimIds:list[str]=Field(min_length=1,max_length=5)
    documentCount:int=Field(ge=1)
    originGroupCount:int=Field(ge=1)
    strength:Literal['low','moderate']
    reasons:list[str]=Field(max_length=10)


class ClaimSummary(BaseModel):
    version:Literal['claim-summary-v1']='claim-summary-v1'
    scope:Literal['claim_summary']='claim_summary'
    overall:Literal['review_required','insufficient','mixed','supported_claims','refuted_claims','no_checkable_claims']
    counts:dict[str,int]
    strength:Literal['not_assessed']='not_assessed'
    independenceVerified:Literal[False]=False
    crossModalReviewRequired:bool=False
    reviewedEvidence:ReviewedEvidenceSummary|None=None


def summarize(claims,modal_checks)->ClaimSummary:
    counts={name:0 for name in ('CONFIRMED','REFUTED','INSUFFICIENT','REVIEW_REQUIRED','EXCLUDED')}
    counts.update(Counter(c.verdict for c in claims))
    internal=any(c.status in ('possible_mismatch','review_required') for c in modal_checks)
    eligible=len(claims)-counts['EXCLUDED']
    if internal or counts['REVIEW_REQUIRED']:overall='review_required'
    elif not eligible:overall='no_checkable_claims'
    elif counts['INSUFFICIENT']:overall='insufficient'
    elif counts['CONFIRMED'] and counts['REFUTED']:overall='mixed'
    elif counts['REFUTED']:overall='refuted_claims'
    else:overall='supported_claims'
    selected=[c for c in claims if c.verdict!='EXCLUDED']
    reviewed=[e for c in selected for e in c.evidence if e.meaningReview and e.usable and not e.reasons]
    assessment=None
    if reviewed:
        # Overlapping document hashes and source groups merge transitively, never imply independence.
        groups=[]
        for evidence in reviewed:
            keys={('document',evidence.meaningReview.documentHash)}
            if evidence.lineage.startswith('reviewed-origin:'):keys.add(('reviewed-origin',evidence.lineage))
            if evidence.sourceReview:keys.add(('source',evidence.sourceReview.groupId))
            separate=[]
            for group in groups:
                if keys & group:keys.update(group)
                else:separate.append(group)
            groups=separate+[keys]
        unresolved=any(c.verdict not in ('CONFIRMED','REFUTED') or not any(
            e.meaningReview and e.usable and not e.reasons and
            e.meaningReview.relation==('SUPPORTED' if c.verdict=='CONFIRMED' else 'REFUTED')
            for e in c.evidence) for c in selected)
        reasons=['DIRECT_REVIEWED_EVIDENCE','INDEPENDENCE_UNVERIFIED']
        if unresolved:reasons.append('UNRESOLVED_CLAIMS')
        if internal:reasons.append('MODAL_UNCERTAINTY')
        if len(groups)<len(reviewed):reasons.append('SHARED_OR_DUPLICATE_ORIGIN')
        assessment=ReviewedEvidenceSummary(
            claimIds=[c.id for c in selected],documentCount=len({e.meaningReview.documentHash for e in reviewed}),
            originGroupCount=len(groups),strength='low' if unresolved or internal else 'moderate',reasons=reasons)
    return ClaimSummary(overall=overall,counts=counts,crossModalReviewRequired=internal,reviewedEvidence=assessment)
