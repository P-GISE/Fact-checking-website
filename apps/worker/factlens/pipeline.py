from pathlib import Path
from uuid import UUID
from factlens.contracts import Claim, AnalysisResult
from factlens.validator import validate_evidence, RULE_VERSION
from factlens.decision import decide
from factlens.source_review import review_sources, REVIEW_VERSION, DEFAULT_REGISTRY

class ProviderUnavailable(RuntimeError):pass

class Providers:
    """Fail closed until a provider, price schedule and budget are configured.

    Test doubles live in tests, never in this production adapter.
    """
    def transcribe(self,path):raise ProviderUnavailable('PROVIDER_NOT_CONFIGURED')
    def extract(self,segments):raise ProviderUnavailable('PROVIDER_NOT_CONFIGURED')
    def search(self,claim):raise ProviderUnavailable('PROVIDER_NOT_CONFIGURED')

def run_analysis(job:dict,providers,stage=lambda name:True)->AnalysisResult:
    if not job.get('consent'):raise ValueError('CONSENT_REQUIRED')
    def advance(name):
        if not stage(name):raise ValueError('JOB_CANCELLED')
    advance('transcribing')
    segments=providers.transcribe(Path(job['path']))
    advance('extracting')
    claims=[Claim.model_validate(c) for c in providers.extract(segments)]
    limitations=['음성만 분석했습니다. 자막·화면 맥락은 검증하지 않았습니다.','정형 수치 발화와 전체 전사 맥락이 일치하는 범위만 확정 비교합니다. 일반 발언은 검토 또는 유보합니다.']
    if len(claims)>5:limitations.append('최대 5개 주장만 검증했습니다.')
    claims=claims[:5]
    ids=set()
    for c in claims:
        UUID(c.id)
        if c.id in ids:raise ValueError('DUPLICATE_CLAIM_ID')
        ids.add(c.id)
        if c.endSeconds>job['duration']:raise ValueError('CLAIM_OUT_OF_RANGE')
        advance('retrieving')
        try:documents=providers.search(c)
        except (ValueError,OSError,TimeoutError):
            documents=[];limitations.append(f'{c.id}: 근거 검색에 실패했습니다.')
        advance('validating_evidence')
        c.evidence=[validate_evidence(c,d) for d in documents[:5]]
        for check,review in zip(c.evidence,review_sources(c.evidence)):
            check.sourceReview=review
        c.verdict=decide(c,c.evidence)
    limitations.extend(getattr(providers, 'limitations', []))
    limitations = list(dict.fromkeys(limitations))
    usage = providers.usage() if callable(getattr(providers, 'usage', None)) else {'billing':'not_configured'}
    provider_versions=providers.versions() if callable(getattr(providers,'versions',None)) else {}
    return AnalysisResult(claims=claims,limitations=limitations,usage=usage,versions={**provider_versions,'ruleVersion':RULE_VERSION,'sourceReviewVersion':REVIEW_VERSION,'sourceRegistryVersion':DEFAULT_REGISTRY.version})
