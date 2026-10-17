# 판정 경로와 실제 규칙 회귀의 순차 실행 계획

> **For agentic workers:** Use superpowers:executing-plans. 사용자 요청에 따라 가이드 정리 후 같은 격리 체크아웃에서 직접 순차 실행한다.

**Goal:** TASK-020→021→022 순서로 원문 맥락 왜곡의 확정 판정을 막고, 복수 후보 수집과 실제 규칙 회귀를 연결한다.
**Architecture:** 전체 전사 contextText를 서버가 보존한다. v2 규칙은 표시 주장과 전체 전사·근거 전체 텍스트가 정형 계약을 만족할 때만 수치 확정을 허용한다. 검색은 최대3 후보의 서로 다른 최종 원문을 수집한다. 별도 RULES 회귀 CLI가 실제 Validator/Decision을 호출하고 기존 평가 분모를 재사용한다.
**Tech Stack:** 기존 Python/Pydantic/pytest/OpenAI, Express/Zod/Vue. 신규 서비스·라이브러리 없음.
**Spec:** [00 통합 순서](../../00_문서_가이드.md#통합-실행-순서), [02](../../02_기능_설계.md), [07](../../07_백엔드_구조.md), [99](../../99_해야할일..md).

## 공통 제약과 검토 초점

- 기존 전체 근거 문맥 gate를 완화하지 않는다. 일반 발언/인접 구간 정정은 확정 대신 검토로 남긴다.
- 전체 전사를 contextText로 보존하므로 여러 주장/비정형 전사는 보수적으로 유보된다. 의미 이해 완료로 주장하지 않는다.
- 규칙 버전만 새 결과에 기록한다. 과거 결과의 누락 버전/context는 임의 채우지 않는다.
- 검색은 최대5회/작업, 후보 최대3개/주장, 원문 추출 각 호출의 사전 예약·월/건 한도·재시도0 유지. auth/rate/budget 실패를 빈 근거로 숨기지 않는다.
- 같은 최종 URL은 재구조화하지 않는다. host/lineage는 독립 출처 인증이 아니며 근거 강도 확률을 만들지 않는다.
- RULES는 A/B/C 연구 시스템과 구분하며 전체 fixture(문서/맥락 포함) 해시와 실제 규칙 버전을 기록한다.
- source context·금액·버전 메타데이터는 기존 삭제/24시간 보관 경계를 따른다. 실키·유료 호출·배포는 이번 단계에서 변경하지 않는다.

## Task 1 / TASK-020: 주장 맥락과 버전

Files: contracts.py, validator.py, decision.py, live_providers.py, pipeline.py, API contracts.ts, web types/EvidencePanel 및 테스트.
Interfaces: Claim.contextText nullable legacy; AnalysisResult.versions defaults empty; rule constant RULE_VERSION; claim_issues(claim)->list[str].

- [x] 부정/정정 주장·잘린 구간/인접 정정의 잘못된 확정을 재현해 RED 확인.
- [x] 완전한 정형 주장/전체 전사 context가 없으면 확정 금지. 맥락 불명은 REVIEW_REQUIRED, 필드/출처 누락은 INSUFFICIENT. EXCLUDED 우선 유지.
- [x] SDK가 전체 입력 전사로 contextText를 채우고 파이프라인 새 결과에 ruleVersion을 기록한다. API는 기존 결과에 versions={}를 기본값으로 둔다.
- [x] UI에서 원문 맥락을 문자로 확인할 수 있게 하고 관련 회귀/타입/API/Python 검증.

## Task 2 / TASK-021: 복수 검색 후보

Files: live_providers.py/test_live_providers.py.
Interfaces: search(claim)->최대3 EvidenceDocument. 각 구조화 호출은 기존 BudgetedCall을 통한다.

- [x] 첫 후보 인용 부재 뒤 유효 후보·복수 충돌·최종URL 중복 재현 RED.
- [x] 첫 빈 인용에서 계속 순회하고 서로 다른 최종 문서를 모두 반환. 접근/인용 실패 limitation 유지.
- [x] 후보 수/중복 호출/실패 전파/예산 경계를 테스트하고 전체 suite 확인.

## Task 3 / TASK-022: 실제 규칙 회귀

Files: rule_regression.py/test_rule_regression.py, evaluation.py의 RULES 식별자, evaluation/rules-fixture.json·README.
Interfaces: strict RulesFixture(Dataset + case Claim/documents), execute(fixture,split)->보고서. 예측은 생산 validate_evidence/decide로 내부 생성한다.

- [x] 실제 지지/반박/충돌/제외/부족/맥락 fixture의 실행·입력 해시·ID 대응·런타임 실패 분모 RED.
- [x] fixture 전체와 label manifest를 별도로 해시하고 RULE_VERSION·생산 소스 해시를 기록. model/prompt=not_applicable, researchValidation=false.
- [x] synthetic fixture의 CLI/회귀와 전체 검증·별도 리뷰 후 수정은 재현 테스트로 확인.
- [x] 완료 근거를 10/99/관련 가이드에 갱신하고 순서별 로컬 커밋.

## 순차 실행 근거

가이드97f05a6 후 TASK020 dca733d, TASK021 e2d44df, TASK022 실제 규칙 회귀 순서로 구현했다. 리뷰의 자유 필드 의미 우회는 단위만 검사해 해결되지 않아 subject/metric/unit/year/number의 좁은 지원 구조로 제한하고 재현했다. 일반 문서 계약 확장은 TASK023이며 production whole-document gate는 유지했다. 실행별 상세는10 §34~36을 따른다.
