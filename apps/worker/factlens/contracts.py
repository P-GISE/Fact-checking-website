from typing import Literal
from pydantic import BaseModel, Field, model_validator

Verdict = Literal['CONFIRMED','REFUTED','INSUFFICIENT','REVIEW_REQUIRED','EXCLUDED']
class EvidenceCheck(BaseModel):
    url: str
    title: str
    quote: str
    position: int = Field(ge=0)
    publisher: str | None = None
    publishedAt: str | None = None
    relation: Literal['SUPPORTED','REFUTED','INSUFFICIENT'] = 'INSUFFICIENT'
    usable: bool = False
    reasons: list[str] = Field(default_factory=list)
    lineage: str

class Claim(BaseModel):
    id: str
    text: str = Field(min_length=1)
    startSeconds: float = Field(ge=0, allow_inf_nan=False)
    endSeconds: float = Field(ge=0, allow_inf_nan=False)
    subject: str | None = None
    period: str | None = None
    metric: str | None = None
    value: str | None = None
    unit: str | None = None
    eligibility: Literal['checkable','excluded'] = 'checkable'
    verdict: Verdict = 'INSUFFICIENT'
    evidence: list[EvidenceCheck] = Field(default_factory=list)

    @model_validator(mode='after')
    def time_order(self):
        if self.endSeconds < self.startSeconds:
            raise ValueError('invalid time range')
        return self

class AnalysisResult(BaseModel):
    scope: Literal['audio_only'] = 'audio_only'
    demo: bool = False
    claims: list[Claim] = Field(max_length=5)
    limitations: list[str]
    usage: dict = Field(default_factory=dict)
