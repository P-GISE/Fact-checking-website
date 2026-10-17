# 오프라인 판정 평가 실행기 계획

> **For agentic workers:** Use superpowers:executing-plans for native execution. 사용자의 남은 작업 진행 요청에 따라 기존 체크아웃에서 수행한다.

**Goal:** TASK-014의 데이터/라벨·분할·분모 계약을 실행 가능한 오프라인 도구로 준비한다.
**Architecture:** 생산 판정은 변경하지 않는다. 외부 호출 없는 Python CLI가 데이터 manifest와 버전/해시를 지정한 예측 run을 검사하고 동일 split의 5종 판정 지표를 JSON으로 계산한다.
**Tech Stack:** 기존 Python/Pydantic/pytest, 신규 의존성 없음.
**Spec:** [평가 원칙](../../AGENTS.md#연구-검증과-데이터-보호), [시스템 개요](../../01_시스템_개요.md), TASK-014.

## 제약과 검토 기준

- 같은 originId의 dev/test 혼입·중복 ID·알 수 없는 예측 ID·다른 데이터 해시는 오류다.
- 누락/실패 예측도 전체 분모와 해당 정답 클래스 FN에 포함한다. 실패를 유보로 세지 않는다.
- Macro-F1은 고정 5종 클래스 평균이며 support 없는 클래스 F1=0을 명시한다.
- wrong decisive/all cases와 wrong decisive/decisive를 별도 보고한다. 후자 분모0은 null이다.
- Claim Recall/근거 Precision·Validity/시각 F1/시간·비용은 이 단계에서 측정하지 않는다.
- 합성 예시·수동 라벨/예측의 점수는 실제 모델 호출이나 연구 검증 성과가 아니다.
- 생산 Validator·보고서 API·DB·모델/예산·외부 환경을 변경하지 않는다.

## Task 1: 평가 계약과 실행기

Files: apps/worker/factlens/evaluation.py, apps/worker/tests/test_evaluation.py, evaluation/README.md, evaluation/example-dataset.json, evaluation/example-run.json.
Interfaces: Dataset/Run(strict Pydantic), fingerprint(dataset)->str, score(dataset,run,split)->dict. CLI fingerprint DATASET 및 score DATASET RUN --split dev|test.

- [x] 고정 라벨의 수계산 점수, 누락/실패, 데이터 누출·해시·중복·외부 ID·빈 split 실패 테스트 작성 후 RED 확인.
- [x] strict 스키마·SHA-256 연결·분모/혼동행렬·지표/명시적 미측정 목록과 CLI 구현 후 GREEN.
- [x] 합성 예시 파일/운영 안내 작성, 실제 CLI 성공·실패·전체 회귀 검증, 별도 리뷰.
- [x] 01/07/08/09/10/99 및 AGENTS 갱신. TASK-014는 도구 준비 진행 중이며 연구 평가 완료로 표시하지 않는다.

## 실행 상태

핵심11개 테스트는 모듈 미구현 RED 후 구현 GREEN, CLI/선택 split 추가2개 포함13개 통과. Python전체89/API21 및 타입/빌드 검증. 합성 예시CLI 산술값 확인, 별도 리뷰 중요 결함 없음. 실자료 연구/브라우저/유료 호출/배포 검증은 이번 범위가 아니다. 상세 10 §32.
