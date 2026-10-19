# TASK-023 출처 등록 대조·재인용 관계 검토 계획

> **For agentic workers:** Use superpowers:executing-plans. 기존 격리 work에서 직접 실행하며 앞선 미커밋 변경을 보존한다.

**Goal:** 출처 등록 대조와 후보 간 중복/명시적 재인용 관계를 추적해 독립 출처로 과대 해석하지 않게 한다.
**Architecture:** static-text-v2가 bounded canonical/cite 링크 관측을 추가한다. 서버 final URL 기준으로 안전하게 해석하되 새 요청은 하지 않는다. 별도 source_review-v1이 버전 관리한 신뢰 등록 파일과 HTTPS exact host/publisher 표기를 대조하고 후보 최대5개의 URL/hash/명시 링크 관계를 감사한다. 결과/API/화면에 nullable sourceReview를 보존한다.
**Tech Stack:** 기존 Python/Pydantic/BeautifulSoup/Zod/Vue. 새 의존성·외부 호출 없음.
**Spec:** [02 원문 계약](../../02_기능_설계.md#task-023-일반-원문-계약-1차-고정-2026-10-18), [07 책임](../../07_백엔드_구조.md#task-023-수집구조화검증-책임-계약-2026-10-18).

## Global Constraints / Review Focus

- production registry는 검토된 실제 출처가 없어 빈 목록으로 시작. 모델/페이지/사용자 요청이 registry를 바꿀 수 없다. 검토일/근거가 있는 버전 파일만 운영자가 관리한다.
- 등록 도메인/페이지 발행자 표기의 일치는 사실성·최초 원본·독립성 인증이 아니다. SOURCE_AUTHENTICITY_UNVERIFIED와 규칙v3 gate를 제거하지 않는다.
- canonical/cite는 페이지 주장이다. 최대32개·URL2000자, 자격증명/비HTTP/사설 literal/위험 포트 거부, HTML base가 있으면 상대링크는 미해석. 링크를 fetch하지 않는다.
- exact host/HTTPS만 등록 대조. 유사 suffix·하위도메인·서로 다른 query/path를 임의 동일시하지 않는다.
- 관계는 최대5개 후보 내 가능성 그룹. transitive 중복/명시링크·공통원출처도 독립성 미확인. 오래된 결과 null/v1 parser 호환.

## Task 1: 링크 관측과 출처 검토 모듈

Files: source_document.py/retrieval.py, 새 source_review.py/source_registry.json, test_source_document.py/test_source_review.py.
Interfaces: SourceTrace.sourceLinks(종류/url/서버locator), sourceLinksComplete; review_sources(checks,registry=None)->list[SourceReview]. Registry는 trusted 코드 데이터이며 evidence 입력과 분리.

- [x] 링크 제한/상대주소/HTML base/비신뢰scheme·host spoof/발행자충돌/빈 registry·중복 hash/인용 edge/transitive 그룹 실패 테스트 실행.
- [x] 최소 구현 후 parser/review와 전체 Python 회귀.

## Task 2: 파이프라인/API/UI·회귀 연결

Files: contracts.py/pipeline.py/rule_regression.py, API contracts.ts, web types/EvidencePanel, 관련 Python/API/E2E 테스트.
Interfaces: EvidenceCheck.sourceReview|null, 결과 sourceReviewVersion/sourceRegistryVersion; legacy sourceTrace v1/sourceReview null.

- [x] 생산 pipeline/RULES review 일치·API 보존·근거 화면 비신뢰 값 표시 실패를 확인.
- [x] 관측/등록대조·그룹 후보를 결과와 화면에 연결. 판정/출처 독립성은 승격하지 않음.
- [x] Python/API/브라우저·타입/빌드·RULES9+8·정적 검사·독립 리뷰 후 지적 수정 및 가이드 갱신.

## 실행

기존 작업과 합쳐 임의 커밋/푸시/배포하지 않는다. ledger는 .superpowers/sdd/2026-10-19-source-relations/progress.md. 실출처 등록·일반 문서 의미 검증·실미디어 분석은 이번 관측/대조 증분의 성공과 구분한다.
