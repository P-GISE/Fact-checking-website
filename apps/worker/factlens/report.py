"""A transparent claim summary, never an overall video truth probability."""
from collections import Counter
from typing import Literal
from pydantic import BaseModel

SUMMARY_VERSION='claim-summary-v1'
class ClaimSummary(BaseModel):
    version:Literal['claim-summary-v1']='claim-summary-v1'
    scope:Literal['claim_summary']='claim_summary'
    overall:Literal['review_required','insufficient','mixed','supported_claims','refuted_claims','no_checkable_claims']
    counts:dict[str,int]
    strength:Literal['not_assessed']='not_assessed'
    independenceVerified:Literal[False]=False
    crossModalReviewRequired:bool=False


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
    return ClaimSummary(overall=overall,counts=counts,crossModalReviewRequired=internal)
