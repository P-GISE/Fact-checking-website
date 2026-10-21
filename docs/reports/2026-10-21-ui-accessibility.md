# UI 접근성 후속과 공개 검증 차단 — 2026-10-21 KST

## 사용자 요청과 결과 구분

사용자는 직전 브리핑1번(새 UI 공개 사이트·회원 흐름 재확인, 실제 모바일/접근성 점검)을 진행하고 가이드·GitHub 반영 및 남은 상황 보고를 요청했다. 이어 Aside 브라우저 도구 연결도 요청했다. 기존 UI 배포b219d79와 문서6f5e7c8를 기준으로 재개했다.

**이번에 로컬 접근성 문제를 수정·검증했으나, 공개 사이트/실제 휴대폰/스크린리더/Aside 연결은 미완료다.**1번 전체를 완료 처리하지 않는다.

## Aside 연결 조사와 실제 차단

- 현재 실행 환경은 Linux /workspace/Fact-checking-website이며 사용자의 Windows 프로젝트/Aside 앱을 직접 제어하는 실행 도구가 없다.
- 현재/지연 도구 목록에서 Aside repl/memory/exec와 Browser js·CUA 연결 도구를 찾지 못했다. `command -v aside`도 미발견이다.
- browser:control-browser와 plugin-management 스킬을 읽고 플러그인 검색query=Aside/limit5를 실제 실행했으며 plugins=[]였다. 설치 가능한 Aside 플러그인이나 현재 세션 MCP 활성화 도구를 찾지 못했다. 다른 브라우저를 Aside라고 표시하지 않는다.
- devtools/WINDOWS_SETUP.ko.md는 Windows 설치/로그인·과거 disabled/연결 이력을 담는다. 현재 Linux 연결 증거가 아니며 Windows 경로만 클라우드 설정에 넣어 연결 완료로 기록하지 않았다.
- cloud environment는connected/current·network enforced다. 공개HTTPS curl 재시도는CONNECT tunnel403/HTTP000/exit56. 허용 정책을 바꾸거나 프록시를 우회하지 않았다.
- 공개 검증을 재개하려면 **Aside MCP가 활성화된 Windows 로컬 환경에서 이 작업을 이어야 한다.** 현재 세션에서 직접 연결을 켤 수 있는 기능이 없다는 한계를 사용자에게 알렸다. 앱 로그인·확장 연결·도구 응답 성공을 아직 확인하지 않았다.

## 재현과 수정

axe-core4.14.0의WCAG2/2.1 A·AA 태그로 로컬 화면을 진단했다. 최초 홈 데스크톱의color-contrast23개 노드와label-content-name-mismatch1개를 확인했고, 로그인/가입·모바일도 위반을 보였다. 자동 테스트를 추가해 기존 화면에서 실패함을 확인한 뒤 수정했다.

- 밝은 배경의 보조 문구/메뉴/배지/보고서 문구 대비를 보완했다. 어두운 미디어 미리보기 글자는 밝게 유지한다. 보조 문구 일부와 상단 터치 영역도 키웠다.
- 로고에 실제 보이는FactLens AI를 접근 이름에 포함한다. 프로필은 사용자 이름+화면에는 숨긴 계정 메뉴 문구를 사용하며 장식 아바타를 숨긴다.
- 첫 키보드Tab에서 본문 바로가기 제공. 화면 이동/인증 완료/로그아웃·예시/이력 최초 열기에서 렌더 후 본문으로 초점 이동.1.2초 자동 폴링에서는 초점을 이동하지 않는다.
- 독립 리뷰가 지적한 이력 최초 열기 초점과 변경된 보고서 색상 검증을 추가 반영했다. 모델·권한·API/DB 계약·예산은 변경하지 않았다.

## 실행한 검증

- `E2E_BASE_URL=http://127.0.0.1:5173 npx playwright test tests/e2e/accessibility.spec.ts tests/e2e/navigation.spec.ts`: **15 passed**. 새 접근성9개와 기존내비게이션6개다.
- 새9개:1280/390px 홈·로그인·가입, 로그인된 프로필/설정/탈퇴/새 분석/빈 이력, 예시 보고서, 키보드본문 이동/메뉴Escape 초점 복귀,320px reflow/메뉴 키보드, 최초 이력 열기 초점/자동 갱신 초점 보존. 검사한 상태의 자동 규칙 위반0이며, 모든 장애/보조기술·WCAG 전체 적합성을 뜻하지 않는다. API는 모의 응답이며 실제 공개 회원 흐름이 아니다.
- `DATABASE_URL=<격리 DB> npm test --workspace apps/api -- --no-file-parallelism`: **API97 passed**.
- `FACTLENS_AUTH_MODE=accounts E2E_BASE_URL=http://127.0.0.1:5173 npx playwright test tests/e2e/accounts.spec.ts`: **6 passed**. 격리PostgreSQL/Redis/API의 가입/로그인/변경/탈퇴 및 일반회원 관리자403을 재검증했다. 관리자 목록1개는 모의 응답이며 실제 관리 자료가 아니다.
- 로컬 브라우저 합계21개. `npm run typecheck`, `npm run build` API/웹 전체 통과. 코드 diff형식과 문서 링크도 확인한다.
- 로컬Playwright/Chromium은Aside 연결 대체 완료가 아니라 제품 테스트 용도다. 실제 단말·공개 로그인·스크린리더 청취 검증은 하지 않았다. 새 유료 AI 호출0.
- 로컬1280/390/320px 홈 캡처는 /workspace/FactLens-preview/a11y-home-<폭>.png에 보존한다. 미디어/계정 비밀번호/비밀값은Git에 넣지 않는다.

## 게시와 다음 작업

work에 코드와 영향 가이드를 게시하고 기존 자동CI/배포 결과를 확인한다. main은 변경하지 않는다. 배포 성공이Aside 연결 또는 공개 회원UI 검증 성공을 뜻하지 않는다. 최종CI/배포 결과는 아래에 보완한다.

1번 잔여는Aside가 활성화된 로컬 환경 연결→공개홈/로그인/가입·설정·로그아웃/탈퇴·모바일 새UI 확인 및 실제 단말·스크린리더 점검이다. 현재 분석 개선(안전 대담/GTV 잔여 후보·한국어ASR·새 모델 시간 정렬·실자료 평가)은사용자 요청대로 보류한다. 일반 의미/복잡한 표/출처 독립성/영상 전체 진위 및 계정 복구/추가 권한/운영 정책도미완료를 유지한다.
