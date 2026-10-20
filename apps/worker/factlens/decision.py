from factlens.contracts import Claim, EvidenceCheck, Verdict
from factlens.validator import claim_issues
from factlens.meaning_review import claim_matches

def decide(claim:Claim,checks:list[EvidenceCheck])->Verdict:
    if claim.eligibility=='excluded':return 'EXCLUDED'
    issues=claim_issues(claim)
    reviewed=[c for c in checks if c.usable and c.meaningReview is not None
              and claim_matches(claim) and c._validatedMeaningScope==(
                  claim.model_dump_json(exclude={'evidence','verdict'}),c.model_dump_json(exclude={'sourceReview'}))]
    if reviewed:issues=[]
    if any(reason in issues for reason in ('CLAIM_CONTEXT_REVIEW_REQUIRED','CLAIM_STRUCTURE_REVIEW_REQUIRED')):return 'REVIEW_REQUIRED'
    if issues:return 'INSUFFICIENT'
    relations={c.relation for c in checks if c.usable and (c.meaningReview is None or c in reviewed)}
    if {'SUPPORTED','REFUTED'}<=relations:return 'REVIEW_REQUIRED'
    if any('PRECISION_REVIEW_REQUIRED' in c.reasons for c in checks):return 'REVIEW_REQUIRED'
    if 'REFUTED' in relations:return 'REFUTED'
    if 'SUPPORTED' in relations:return 'CONFIRMED'
    return 'INSUFFICIENT'
