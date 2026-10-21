# Windows 로컬 Aside 공개 UI·회원 흐름 검증

2026-10-21 KST. 사용자 요청으로 Windows 로컬 work를 c7c09a2에서 f74df60334c993c354088a316d73f34a8780940e으로 git fetch origin work / merge --ff-only origin/work로 동기화했다. 시작 작업 트리는 깨끗했으며 main은 체크아웃·생성·변경하지 않았다. docs/AGENTS.md와 최신 Aside 연결·홈 개편·접근성 보고서 및 관련 가이드를 읽었다.

## 로컬 연결과 실행

- Aside CLI 1.26.1020.1855의 guide/guide repl을 읽고 MCP listBrowserTabs 성공, 공개 https://factlens.pigs0516.com/ 탭 열기와 홈 snapshot 성공을 직접 확인했다. 기존 클라우드 원격 제어 PAYMENT_REQUIRED는 이번 로컬 경로의 차단이 아니다. 새 설치·인증 변경·요금제 변경은 없다.
- Aside 브라우저 에이전트 세션 18D3PaZIoZwLq9q5에 공개 UI 검증을 위임했다. exec 응답은300초 도구 타임아웃이었지만 세션은 계속 실행됐고, 내장 세션 조회로 관측·정리 증거를 회수했다. 타임아웃을 제품 실패로 해석하지 않는다.
- 주요 관측은17:25~17:31 KST. 모의 API가 아닌 공개 서비스 UI다. 기존 회원/관리자 계정은 사용하지 않았고 고유 임시 계정1개를 만들었다. 암호는 보고서에 기록하지 않는다.

## 확인 결과

| 흐름 | 관측 |
|---|---|
| 공개 홈→예시 보고서→홈 | 새 홈과 명시적 가상 보고서 표시 |
| 비로그인 새 분석/분석 이력 | 로그인 화면 안내 |
| 회원가입→새 분석 | 인증 후 작업 공간 진입, 파일 업로드 실행 없음 |
| 분석 이력 | 임시 회원의 빈 이력 |
| 프로필→계정 설정 | 독립 설정 화면과 재인증 안내 |
| 이름·암호 변경 | 변경 후 새 정보로 재로그인 성공 |
| 로그아웃→재로그인 | 공개 홈 복귀 후 재로그인 성공 |
| 탈퇴 동의/빈 암호 | 동의 전 버튼 비활성, 동의만 한 상태는 필수 암호 native validation으로 제출 차단 |
| 암호 재인증 탈퇴 | 회원 탈퇴 완료 안내 |
| 탈퇴 후 로그인 | 사용자 이름 또는 비밀번호 오류로 거부 |
| 키보드 메뉴 | Enter 열기·Escape 닫기, expanded=false 및 트리거 초점 복귀 |
| 데스크톱 레이아웃 |1425px 홈·설정 document/body scrollWidth1425, 관측된 가로 넘침0 |

DOM/스크린샷과 observations.json·keyboard-menu-result.json·deletion-gates.json을 직접 대조했다. 공개 홈 스크린샷도 직접 열어 확인했다. 전체 페이지 캡처만으로 sticky 영역의 중복 렌더를 제품 결함으로 단정하지 않는다.

## 증거와 정리

증거 폴더: C:/Users/HP/.aside/u/0/sessions/2026-10-21_18D3PaZIoZwLq9q5/artifacts/factlens-verification/

- 01-home.png / .dom.txt: 공개 홈.
- 14-change-account-result,15-new-credentials-login,18-logout-home: 변경·로그인·로그아웃.
- 24-deletion-result.dom.txt: 회원 탈퇴가 완료됐습니다.
- 25-deleted-login-rejected.dom.txt: 사용자 이름 또는 비밀번호가 올바르지 않습니다.
- keyboard-menu-result.json: focused=true / expanded=false.
- viewport-limitation.txt: page.setViewportSize TypeError: not a function.

임시 서비스 계정 탈퇴·이후 로그인 거부 확인. Aside 시험용 저장 로그인 암호는 제거됐고 탈퇴 표시는 남는다. 업로드0·분석 실행0. 기존 계정·서버 설정·모델·예산·배포 변경 없음. 증거는 로컬 Aside 폴더에 보존하며 Git에 암호/미디어를 추가하지 않는다.

## 검증 한계와 남은 일

390/320px 뷰포트 변경 기능이 이 Aside 표면에 없어 모바일 검사를 수행하지 못했다. CSS로 화면을 바꿔 실제 반응형 검증으로 대신하지 않았다. 실제 휴대폰·스크린리더·전체 WCAG 적합성, 관리자/타 계정 권한 전체·부하·업로드/AI 분석은 이번 미검증이다. 분석 개선 보류를 유지한다. 제품 코드 변경이 없어 전체 API/Worker/빌드/보안 검사는 재실행하지 않는다. 문서만 갱신하며 원격 push/추가 배포는 실행하지 않는다.
