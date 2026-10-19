"""Conservative internal record comparison, separate from external fact verdicts."""
import re
from typing import Literal
from pydantic import BaseModel,Field
from factlens.visual import VisualAnalysis

MODAL_VERSION='modal-record-review-v1'
RECORD=re.compile(r'(19\d{2}|20\d{2})년 (한국|대한민국) (고용률|실업률|인구) ((?:0|[1-9]\d*)(?:\.\d+)?)(%|명)')

class ModalCheck(BaseModel):
    claimId:str
    source:Literal['subtitle','ocr']
    startSeconds:float=Field(ge=0,allow_inf_nan=False)
    endSeconds:float=Field(ge=0,allow_inf_nan=False)
    observedText:str=Field(min_length=1,max_length=2000)
    status:Literal['matching_record','possible_mismatch','review_required']
    reasons:list[str]
    frameId:str|None=None


def review_modalities(claims,visual:VisualAnalysis|None)->list[ModalCheck]:
    if visual is None or visual.status in ('not_applicable','unavailable'):return []
    output=[]
    for claim in claims[:5]:
        if claim.eligibility=='excluded':continue
        for record in visual.records:
            if record.endSeconds<=claim.startSeconds or record.startSeconds>=claim.endSeconds:continue
            if len(output)>=100:break
            status='review_required';reasons=['VISUAL_MEANING_UNVERIFIED']
            match=RECORD.fullmatch(record.text.strip())
            if match:
                year,subject,metric,value,unit=match.groups()
                expected=(claim.period,claim.subject,claim.metric,claim.unit)
                if expected==(year+'년',subject,metric,unit) and claim.text.strip()==f'{claim.period} {claim.subject} {claim.metric} {claim.value}{claim.unit}' and claim.contextText==claim.text:
                    status='matching_record' if value==claim.value else 'possible_mismatch'
                    reasons=['LITERAL_RECORD_MATCH' if status=='matching_record' else 'INTERNAL_NUMERIC_DIFFERENCE']
            if record.source=='ocr':reasons.append('OCR_UNCERTAIN')
            output.append(ModalCheck(claimId=claim.id,source=record.source,startSeconds=record.startSeconds,endSeconds=record.endSeconds,observedText=record.text,status=status,reasons=reasons,frameId=record.frameId))
    return output
