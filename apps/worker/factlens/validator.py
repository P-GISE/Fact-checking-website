from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re
from urllib.parse import urlsplit
from factlens.contracts import Claim, EvidenceCheck

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

def validate_evidence(claim:Claim,document:EvidenceDocument)->EvidenceCheck:
    d=document;f=d.fact;reasons=[]
    if not d.quote or d.position<0 or d.text[d.position:d.position+len(d.quote)]!=d.quote:reasons.append('QUOTE_NOT_VERIFIED')
    if not d.publisher or not d.publishedAt:reasons.append('PUBLICATION_METADATA_MISSING')
    for attr in ('subject','period','metric','unit'):
        candidate=getattr(f,attr);expected=getattr(claim,attr)
        if not candidate or candidate not in d.quote:reasons.append(f'{attr.upper()}_NOT_IN_QUOTE')
        if not expected or expected!=candidate:reasons.append(f'{attr.upper()}_MISMATCH')
    if not re.search(r'(?<![\d.])'+re.escape(f.value)+r'(?![\d.])',d.quote):reasons.append('VALUE_NOT_IN_QUOTE')
    relation='INSUFFICIENT'
    try:
        a,b=Decimal(claim.value or ''),Decimal(f.value)
        if not a.is_finite() or not b.is_finite():raise InvalidOperation
        if not reasons:
            if a==b:relation='SUPPORTED'
            elif '.' in (claim.value or '') or '.' in f.value:reasons.append('PRECISION_REVIEW_REQUIRED')
            else:relation='REFUTED'
    except InvalidOperation:reasons.append('INVALID_NUMERIC_VALUE')
    return EvidenceCheck(url=d.url,title=d.title,quote=d.quote,position=max(0,d.position),publisher=d.publisher,publishedAt=d.publishedAt,relation=relation,usable=not reasons,reasons=reasons,lineage=d.lineage or urlsplit(d.url).hostname or d.url)
