from factlens.contracts import Claim, EvidenceCheck, Verdict

def decide(claim:Claim,checks:list[EvidenceCheck])->Verdict:
    if claim.eligibility=='excluded':return 'EXCLUDED'
    relations={c.relation for c in checks if c.usable}
    if {'SUPPORTED','REFUTED'}<=relations:return 'REVIEW_REQUIRED'
    if any('PRECISION_REVIEW_REQUIRED' in c.reasons for c in checks):return 'REVIEW_REQUIRED'
    if 'REFUTED' in relations:return 'REFUTED'
    if 'SUPPORTED' in relations:return 'CONFIRMED'
    return 'INSUFFICIENT'
