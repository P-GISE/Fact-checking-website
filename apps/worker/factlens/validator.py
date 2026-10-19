from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re
from urllib.parse import urlsplit
from factlens.contracts import Claim, EvidenceCheck
from factlens.source_document import SourceTrace, fingerprint

RULE_VERSION = 'audio-numeric-canonical-v3'
SUPPORTED_SUBJECTS = {'한국','대한민국'}
METRIC_UNITS = {'고용률':'%','실업률':'%','인구':'명'}

def supported_record(subject,period,metric,value,unit)->bool:
    # Finite equality-record vocabulary: free-form units/metrics can hide
    # negation or >= comparisons even when a canonical string matches.
    if subject not in SUPPORTED_SUBJECTS or metric not in METRIC_UNITS or unit!=METRIC_UNITS[metric]:return False
    if not re.fullmatch(r'(?:19|20)\d{2}년',period or '') or not re.fullmatch(r'(?:0|[1-9]\d*)(?:\.\d+)?',value or ''):return False
    number=Decimal(value)
    return number<=100 if unit=='%' else number==number.to_integral_value()

def claim_issues(claim:Claim)->list[str]:
    fields=(claim.period,claim.subject,claim.metric,claim.value,claim.unit)
    if not all(value and value.strip() for value in fields):return ['CLAIM_FIELDS_INCOMPLETE']
    canonical=f'{claim.period} {claim.subject} {claim.metric} {claim.value}{claim.unit}'
    reasons=[]
    if not supported_record(claim.subject,claim.period,claim.metric,claim.value,claim.unit):reasons.append('CLAIM_STRUCTURE_REVIEW_REQUIRED')
    if not claim.contextText or not claim.contextText.strip():reasons.append('CLAIM_CONTEXT_MISSING')
    if claim.text.strip()!=canonical or (claim.contextText and claim.contextText.strip()!=canonical):
        reasons.append('CLAIM_CONTEXT_REVIEW_REQUIRED')
    try:
        if not Decimal(claim.value).is_finite():raise InvalidOperation
    except InvalidOperation:reasons.append('CLAIM_VALUE_INVALID')
    return reasons

@dataclass
class Fact:
    subject:str
    period:str
    metric:str
    value:str
    unit:str

@dataclass
class EvidenceDocument:
    url:str
    title:str
    text:str
    quote:str
    position:int
    publisher:str|None
    publishedAt:str|None
    fact:Fact
    lineage:str|None=None
    sourceTrace:SourceTrace|None=None

def validate_evidence(claim:Claim,document:EvidenceDocument)->EvidenceCheck:
    d=document;f=d.fact;reasons=claim_issues(claim)
    if not supported_record(f.subject,f.period,f.metric,f.value,f.unit):reasons.append('FACT_STRUCTURE_REVIEW_REQUIRED')
    if not d.quote or d.position<0 or d.text[d.position:d.position+len(d.quote)]!=d.quote:reasons.append('QUOTE_NOT_VERIFIED')
    if not d.publisher or not d.publishedAt:reasons.append('PUBLICATION_METADATA_MISSING')
    for attr in ('subject','period','metric','unit'):
        candidate=getattr(f,attr);expected=getattr(claim,attr)
        if not candidate or candidate not in d.quote:reasons.append(f'{attr.upper()}_NOT_IN_QUOTE')
        if not expected or expected!=candidate:reasons.append(f'{attr.upper()}_MISMATCH')
    if not re.search(r'(?<![\d.])'+re.escape(f.value)+r'(?![\d.])',d.quote):reasons.append('VALUE_NOT_IN_QUOTE')
    # Initial PoC accepts only a canonical unambiguous numeric record.
    # Natural-language interpretation/negation needs a reviewed extraction contract.
    canonical=f'{f.period} {f.subject} {f.metric} {f.value}{f.unit}'
    if d.quote.strip()!=canonical or d.text.strip()!=canonical:reasons.append('CONTEXT_REVIEW_REQUIRED')
    trace=d.sourceTrace.model_copy(deep=True) if d.sourceTrace else None
    if trace is not None:
        # A page's metadata is a statement, not an authenticated issuer identity.
        reasons.append('SOURCE_AUTHENTICITY_UNVERIFIED')
        if trace.textSha256!=fingerprint(d.text.encode()) or trace.textLength!=len(d.text) or trace.finalUrl!=d.url:
            reasons.append('SOURCE_TRACE_MISMATCH')
        if not trace.structureComplete:reasons.append('SOURCE_STRUCTURE_INCOMPLETE')
        if trace.extractionTruncated:reasons.append('SOURCE_EXTRACTION_TRUNCATED')
        publication=trace.publication
        if any(field.state in ('conflicting','invalid') for field in (publication.publisher,publication.publishedAt,publication.modifiedAt)):
            reasons.append('PUBLICATION_METADATA_CONFLICT')
        if (publication.publisher.state!='observed' or publication.publishedAt.state!='observed'
                or d.publisher!=publication.publisher.value or d.publishedAt!=publication.publishedAt.value):
            reasons.append('PUBLICATION_METADATA_UNVERIFIED')
        trace.quoteOccurrences=sum(1 for _ in re.finditer('(?='+re.escape(d.quote)+')',d.text)) if d.quote else 0
        trace.quoteBlockIndexes=[]
        if trace.quoteOccurrences>1:reasons.append('QUOTE_AMBIGUOUS')
        elif trace.quoteOccurrences==1:
            trace.quoteBlockIndexes=[i for i,b in enumerate(trace.blocks) if b.position<=d.position and b.position+b.length>=d.position+len(d.quote)]
            if not trace.quoteBlockIndexes:reasons.append('QUOTE_CONTEXT_REVIEW_REQUIRED')
    relation='INSUFFICIENT'
    try:
        a,b=Decimal(claim.value or ''),Decimal(f.value)
        if not a.is_finite() or not b.is_finite():raise InvalidOperation
        if not reasons:
            if a==b:relation='SUPPORTED'
            elif '.' in (claim.value or '') or '.' in f.value:reasons.append('PRECISION_REVIEW_REQUIRED')
            else:relation='REFUTED'
    except InvalidOperation:reasons.append('INVALID_NUMERIC_VALUE')
    return EvidenceCheck(url=d.url,title=d.title,quote=d.quote,position=max(0,d.position),publisher=d.publisher,publishedAt=d.publishedAt,relation=relation,usable=not reasons,reasons=reasons,lineage=d.lineage or urlsplit(d.url).hostname or d.url,sourceTrace=trace)
