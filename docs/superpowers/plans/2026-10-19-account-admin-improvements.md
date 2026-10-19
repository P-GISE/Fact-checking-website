# Account and administration improvement implementation plan

**Goal:** TASK028 계정 사용성과 CRUD, TASK029 관리자 계정 인증·운영 조회를 순차 개선한다.

**Architecture:** 기존 Vue/Express/PostgreSQL 계정 세션을 확장한다. 관리자도 같은 세션을 사용하고 서버가 DB 역할을 확인한다. 계정 생명주기와 미디어/작업·비용 보존을 함께 다룬다.

**Requirements:** docs/02_기능_설계.md와 docs/99_해야할일..md의 확정 요구.

## Constraints

- 사용자 승인에 따라 현재 세션에서 직접 구현한다. 운영 배포는 검증된 변경을 서버에 적용한 뒤 별도 확인한다.
- 비밀값 출력 금지, 공개 가입은 user, 역할 권한은 서버에서 검증.
- AI 비활성화/기존 예산·판정 유보 유지. 실제 제공자 호출 금지.
- 테스트는 factlens_table_context_test/Redis15를 사용하고 기존 서비스 데이터 보존.

## 1. 계정 진입 UX

- [x] AccountPanel.vue 로그인/가입 구분, native form 검증·확인 비밀번호·표시 토글·autocomplete·중복 제출 차단.
- [x] accounts.spec.ts에서 가입/로그인/로그아웃과 비어 있음·invalid username·확인 불일치 요청0건/모드 전환 비밀번호 초기화 검증.
- [x] 타입/빌드와 격리 브라우저 2개 통과.

## 2. 관리자 계정 및 최초 생성

- [x] 마이그레이션으로 app_users.role에 user/admin CHECK·기본 user. 세션 응답의 user.role은 DB 값으로만 제공.
- [x] auth.ts의 requireAdmin은 유효 세션 없음401/일반 회원403/관리자통과. 매 요청 DB 역할 확인으로 권한 회수 즉시 반영.
- [x] admin.ts의 Bearer 검사 제거 후 requireAdmin으로 보호. App.vue 운영 링크를 관리자에게만 표시, AdminDashboard.vue는 세션 로그인/권한 없음/만료 처리.
- [x] 서버 CLI는 숨김 비밀번호 확인 후 신규 관리자만 생성, 중복 계정 승격 금지. 명령 인자·로그·응답 비밀 출력 금지.
- [x] API 회귀: 일반 가입 role 주입 거부·기본 user·직접 관리자 호출401/403/200·로그아웃/권한 회수 후 거부·기존 Bearer 우회 불가.

## 3. 운영 조회 UX

- [x] overview API/화면에 status·조회 페이지·검색 계약과 상한을 정의하고 파라미터 SQL 사용. 작업 상태·오류·UTC 월 사용량을 별도 표시.
- [x] AdminDashboard.vue에 loading/empty/error/last updated·접근성 있는 필터와 페이지 이동. 민감 파일명·전사·원시 오류를 반환하지 않음.
- [x] 경계 페이지/부적절 필터·검색 이스케이프·권한 만료·화면 회귀 검증.

## 4. 계정 수정/탈퇴

- [x] 현재 비밀번호 재인증을 거친 이름/비밀번호 변경 계약, 중복409·실패 원자성·전체 세션 폐기(API48·계정 브라우저5).
- [x] 탈퇴 시 진행 중 작업 경합·개인 파일/파생물 정리·비용 기록 보존·복구 재노출 방지 계약을 먼저 고정.
- [x] 본인 조회/변경/탈퇴와 타 계정 차단·세션 만료·삭제 실패 회귀 검증.

## 5. 검증과 실제 적용

- [ ] 관련 API/브라우저 회귀·타입/빌드·독립 보안 검토 후 가이드/실행 기록 업데이트.
- [ ] private 최초 관리자 생성/마이그레이션/토큰 폐기·복구 절차를 새 서버에 적용, 공개 계정 흐름 검증.
- [ ] OpenAI429 원인/실AI와 실자료 연구 평가는 별도 후속 유지.

실제 컨테이너 관리자 생성/중복·권한 통합 검증 완료(10 §60). 운영 서버 적용과 공개 회귀는 아직 미완료.
