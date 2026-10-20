from factlens.table_references import REFERENCE_VERSION
from factlens.visual import extract_visual,VISUAL_VERSION
from factlens.multimodal import review_modalities,MODAL_VERSION
from factlens.report import summarize,SUMMARY_VERSION
from pathlib import Path
from uuid import UUID
from factlens.contracts import Claim, AnalysisResult
from factlens.validator import validate_evidence, RULE_VERSION
from factlens.decision import decide
from factlens.source_review import review_sources, REVIEW_VERSION, DEFAULT_REGISTRY
from factlens.table_context import CONTEXT_VERSION,CUE_VERSION

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
    visual=extract_visual(Path(job['sourcePath']),job['duration']) if job.get('sourcePath') else None
    advance('extracting')
    claims=[Claim.model_validate(c) for c in providers.extract(segments)]
    limitations=['음성만 분석했습니다. 자막·화면 맥락은 검증하지 않았습니다.','정형 기록 또는 검토된 출처 정책에 맞는 단일 수치 발화만 확정 비교합니다. 다른 문장·정의·맥락은 검토 또는 유보합니다.']
    if visual is not None and visual.status!='not_applicable':
        limitations[0]='음성과 자막·화면 표본을 별도로 확인했습니다. 전체 영상의 시각적 의미를 검증하지는 않았습니다.'
        limitations.extend(visual.limitations)
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
    checks=review_modalities(claims,visual)
    return AnalysisResult(scope='audio_visual' if visual is not None and visual.status!='not_applicable' else 'audio_only',visual=visual,modalChecks=checks,summary=summarize(claims,checks),claims=claims,limitations=limitations,usage=usage,versions={**provider_versions,'ruleVersion':RULE_VERSION,'sourceReviewVersion':REVIEW_VERSION,'sourceRegistryVersion':DEFAULT_REGISTRY.version,'tableContextVersion':CONTEXT_VERSION,'tableCueVersion':CUE_VERSION,'tableReferenceVersion':REFERENCE_VERSION,'visualVersion':VISUAL_VERSION,'modalVersion':MODAL_VERSION,'summaryVersion':SUMMARY_VERSION})
