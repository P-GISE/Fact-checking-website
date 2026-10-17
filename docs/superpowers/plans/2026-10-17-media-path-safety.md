# 미디어 저장 경계 보완 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. 현재 사용자의 계속 진행 지시에 따라 기존 격리 체크아웃에서 직접 실행한다.

**Goal:** 승인된 파일 보호 요구를 유지하면서 DB 경로 변조·잘못된 삭제 ID·심볼릭 링크에 의한 미디어 폴더 이탈을 거부한다.
**Architecture:** API 저장 경계를 전용 storage.ts에서 검증한다. DB 경로를 그대로 전송하지 않고 UUID별 source 파일과 일치하는지 확인한다. 파일 삭제도 UUID 자식 경로로 제한한다.
**Tech Stack:** Node.js fs/path, Express, PostgreSQL, Vitest/Supertest.
**Spec:** [공통 지침](../../AGENTS.md), [백엔드](../../07_백엔드_구조.md), [위험 관리](../../09_위험요소_및_개선포인트.md).

## Global Constraints

- 기존 체크아웃 사용; worktree·외부 배포·유료 호출 없음.
- 웹은 loopback이며 운영 인증/백업은 별도 잔여 조건이다.
- 100 MiB·180초 제한, 외부 전송 동의, 삭제 tombstone 및 Range 응답을 유지한다.

## Review Focus

- DB의 외부 절대 경로 → 404, 내용 전송 없음.
- source 파일 심볼릭 링크 → 404.
- UUID 디렉터리 심볼릭 링크 → 404.
- 삭제 ID가 ../ 또는 절대 경로 → 삭제 거부, 외부 파일 보존.
- 정상 미디어 Range 읽기와 UUID 디렉터리 삭제 → 기존 동작 유지.

## Task 1: 미디어 읽기·삭제 경계

**Files:** Create apps/api/src/storage.ts; Modify apps/api/src/app.ts, cleanup.ts, tests/jobs.test.ts.
**Interfaces:** mediaDirectory(root,id): string, incomingFile(root,name): string, readableMedia(root,id,storedPath): Promise<string>. 허용 범위 이탈은 예외; 라우트는 404.

- [x] 실제 파일과 DB 경로를 이용해 위 다섯 경계의 실패 테스트 작성 및 실패 확인.
- [x] UUID·정해진 source 확장자·절대 경로 일치·realpath 경계를 검사하고 읽기/삭제에 연결.
- [x] API 전체, Python 전체, 타입/빌드, Compose 및 브라우저 검증.
- [x] 오철칙 전체 재점검과 지적별 근거 분류. 도구 버전 차이·잔여 지적을 명시하며 전체 보안 통과를 주장하지 않는다.
- [x] 영향받은 가이드와 10/99/AGENTS 갱신, 원문 해시·링크·diff 확인 후 로컬 커밋.

## 실행 근거

2026-10-17: API 4개 재현 RED→GREEN, 전체 API16/Python76/E2E5 통과. 타입 검사·빌드는 디스크 회복 후 통과, Compose 실행 검증. 별도 리뷰 중요 결함 없음. 정적 49건/종료1 유지, 수동 검토 보고서와 미완료 운영 조건은 10 §27 참조.
