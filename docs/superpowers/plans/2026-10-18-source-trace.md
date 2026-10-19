# TASK-023 원문 구조·발행정보 추적 구현 계획

> **For agentic workers:** Use superpowers:executing-plans. 사용자가 가이드 기반 진행을 지시한 기존 격리 work 체크아웃에서 직접 순차 실행한다. 이전 미커밋 변경을 보존한다.

**Goal:** 기존 판정을 완화하지 않고 수집 원문과 인용·발행정보의 관측 위치를 결과에 연결한다.
**Architecture:** 순수 parser가 정규화 텍스트·구조 offset·발행정보 관측을 생성한다. Retrieval은 요청/최종 URL·UTC·raw/text SHA-256을 추가한다. SDK 후보는 서버 원문에 재대조하고 Validator/API/UI는 nullable sourceTrace를 보존한다. 관측 metadata는 출처 인증이 아니다.
**Tech Stack:** 기존 Python/Pydantic/BeautifulSoup/httpx, Zod/Vue/TypeScript. 새 의존성 없음.
**Spec:** [02 TASK023 계약](../../02_기능_설계.md#task-023-일반-원문-계약-1차-고정-2026-10-18), [07 책임 계약](../../07_백엔드_구조.md#task-023-수집구조화검증-책임-계약-2026-10-18).

## Global Constraints

- 2 MB·공개 IPv4/DNS 고정·기존 리디렉션/TLS·프록시/CA 경계를 유지한다. MIME을 정확히 구분한다.
- 건당200000/月20000000 USD micros, 후보3개·검색5회·재시도0 유지. 유료 호출/실원문 저장 추가 없음.
- 정형v2 숫자 문법 및 전체 주장/원문 gate 유지. sourceTrace의 추가 유보 검사로 새 결과 RULE_VERSION은 audio-numeric-canonical-v3로 기록한다. metadata 관측은 인증/독립성 증명이 아니다.
- sourceTrace는 legacy null, 기존 결과를 소급 생성하지 않는다. 전문/HTML은 새로 영속 보관하지 않는다.

## Review Focus

- text/plain에 HTML 유사 문자가 있어도 원문을 문자로 보존한다.
- 반복 인용·문단/표/각주와 정정 문맥을 자르거나 첫 위치로 임의 확정하지 않는다.
- 무효/상충 발행일·모델이 만든 기관/날짜를 관측 metadata로 승격하지 않는다.
- 구조/metadata 수가 많으면 제한과 미완전 상태를 명시한다.
- legacy 결과 호환성과 UI 문자 렌더링·비신뢰 URL 보호를 유지한다.

## Task 1: 수집/파서 추적

Files: 새 factlens/source_document.py, contracts.py, retrieval.py, tests/test_source_document.py, tests/test_retrieval.py.
Interfaces: parse_document(body:bytes, content_type:str)->dict(title,text,blocks,publication,structureComplete); SourceTrace typed 모델.

- [x] 실제 HTML 문단/표/각주 offset·plain 문자 보존·정확한 MIME·meta/time 발행정보 상충/무효·크기/구조 상한·리디렉션 최종 URL/해시 실패 테스트 작성/실행.
- [x] 최소 parser/수집 provenance 구현. 발행정보는 meta/time의 관측만 지원하며 JSON-LD·페이지 신원 인증·독립성은 후속으로 명시.
- [x] parser/retrieval 및 전체 Python 테스트 실행, 결과 기록.

## Task 2: 인용/결과/API/UI 연결

Files: live_providers.py, validator.py, contracts.py, API contracts.ts, web types.ts/EvidencePanel.vue 및 각 경계 테스트/E2E.
Interfaces: EvidenceDocument.sourceTrace/EvidenceCheck.sourceTrace nullable SourceTrace, quote occurrence count/containing block refs; JSON sourceTrace 보존.

- [x] 실제 fetch parser→SDK 후보→Validator 및 API 스키마의 trace 유지/legacy null·중복 인용/metadata 상충·UI 비신뢰 관측 표시 실패 테스트 작성/실행.
- [x] SDK의 발행정보 후보 대신 parser 관측을 연결하고 중복 인용/불완전 구조는 확정 근거에서 제외. 관측 metadata/수집 provenance를 결과와 UI에 보존.
- [x] 전체 Python/API·타입/빌드·기존9/유보8 RULES·브라우저 검증과 정적 검사, 코드 리뷰 후 문서/실행 기록 갱신.

## 실행 기록

기존 작업 트리가 미커밋이므로 이번 변경과 함께 임의 커밋하지 않는다. 실행 ledger는 .superpowers/sdd/2026-10-18-source-trace/progress.md에 둔다. TASK023 전체 완료가 아니라 관측/구조 추적 증분이며 일반 문서 긍정/반박 허용은 후속 검증 전까지 금지한다.

최종 검증/리뷰 근거: [10 §39](../../10_파일_점검_현황.md#39-task-023-원문-구조발행정보-관측-추적-구현-2026-10-18). 기존 미커밋 작업과 함께 로컬 상태를 유지한다.
