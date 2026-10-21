# Windows 개발 도구 설정 — 2026-10-20

> **최신 클라우드 후속 · 2026-10-21:** Linux CLI 1.26.1020.1855 설치/실행·전역 MCP 등록·별도 초기화와 도구 목록 확인 성공. 기기 로그인은 api.aside.com CONNECT403/fetch failed로 차단됐으며 실제 호스트/탭 연결은 미검증이다. Windows 설정 변경이 아니며 [최신 기록](../docs/reports/2026-10-21-aside-connection.md#linux-설치와-mcp-검증-후속)을 따른다.

> **2026-10-21 연결 경로 정정:** Windows 로컬 전환이 반드시 필요하다는 이전 문구는 단정하지 않는다. 공식 Aside 문서는 호스팅 환경의 CLI 로그인도 안내한다. 현재 Linux에서 공식 설치 스크립트 다운로드는HTTP403으로 차단됐으며 설치·OS호환성·계정 인증/MCP를 검증하지 못했다. 공식배포호스트 허용 후 설치경로부터 확인한다. [조사 보고서](../docs/reports/2026-10-21-aside-connection.md).


> **2026-10-21 클라우드 재개 시 연결 구분:** 현재 채팅은 Linux /workspace에서 실행되며 Aside CLI/MCP 도구가 노출되지 않는다. 사용자 연결 요청 후 도구·CLI·플러그인 검색에서도 활성화 수단을 찾지 못했다. 아래 Windows 설치/로그인 기록은 현재 연결 증거가 아니다. Windows 설정을 원격 변경하지 않았고 공개 검증에는 Aside가 활성화된 로컬 실행 환경이 필요하다. [UI 후속 보고서](../docs/reports/2026-10-21-ui-accessibility.md).


후속 확인: Aside 앱이 설치됐고 CLI account status에서 로그인 상태를 확인했다. 다만 Work 브라우저 도구는 사용자 활성화 답변 후에도 disabled로 응답했으며 메모리 검색 unavailable/remote hosts403이므로 AWS 콘솔 접근은 미검증이다. 아래 앱 설치 대기 항목은 최초 설치 시점의 기록이다. 자동 배포 후속은 docs/08 상단 절을 따른다.

대상은 `P-GISE/Fact-checking-website`의 `work` 브랜치다. 로컬 저장소는 `C:/코덱스/졸업프로젝트 중간고사 V2/Fact-checking-website`이며 기준 커밋은 `671f737`이다. 다른 EventOps 저장소와 `lostark-party-vps`는 이 프로젝트 배포 대상이 아니다. 기존 README의 `/workspace/.devtools` 설치·검증은 이전 클라우드 환경 기록이며 아래 Windows 관측과 구분한다.

## 설치와 검증

| 도구 / upstream | 현재 Windows 상태 | 이번 검증과 남은 조건 |
|---|---|---|
| [Strix](https://github.com/usestrix/strix) | 기존 CLI 1.6.2, 보안 스킬 9개 | 버전 확인. Docker 기반 실제 스캔·모델 인증은 미검증 |
| [OmniRoute](https://github.com/diegosouzapw/OmniRoute) | 기존 3.8.50, 로컬 서비스 시작 | `127.0.0.1:20128/api/health` HTTP200·status ok, loopback 수신 확인. 초기 시작 중 요청 timeout 후 정상 응답. 공급자 인증·모델 호출 미검증 |
| [PM Skills](https://github.com/phuryn/pm-skills) | 기존 9개 플러그인 활성 설정·스킬 카탈로그 확인 | 필요한 기획·분석 스킬을 요청별 선택. 모든 스킬을 실행한 의미가 아님 |
| [Ponytail](https://github.com/DietrichGebert/ponytail) | 기존 5.3.2 플러그인·6개 스킬 | 현재 세션 full 지침 활성 |
| [CodeGraph](https://github.com/colbymchenry/codegraph) | 기존 CLI 1.6.0·MCP | 올바른 저장소에 init: 85파일·1,118노드·2,791간선. `adminRouter` 실제 소스/호출자 탐색 성공 |
| [LazyCodex](https://github.com/code-yeongyu/lazycodex) | 기존 OMO 5.1.35 플러그인·스킬/역할·hook | 현재 세션 지침과 Git Bash MCP 사용, 독립 에이전트의 OmniRoute 설치 조사 결과를 상태 API로 확인 |
| [Superpowers](https://github.com/obra/superpowers) | 공식 Codex 플러그인 6.4.2 신규 설치 | `codex plugin add superpowers@openai-curated-remote --json` 설치 성공. using-superpowers와 Codex 참조 읽음. 새 세션 hook 자동 작동은 미검증 |
| [Headroom](https://github.com/headroomlabs-ai/headroom) | 기존 CLI 0.38.0·MCP | MCP stats 응답 성공. 프록시8787 unreachable. 백그라운드 시작은 자동 승인 정책이 차단해 미실행, 압축/복원·절감률 미검증 |
| [Iron Laws](https://github.com/JinHo-von-Choi/iron-laws) | 기존 1.7.0·신규 MCP 등록 | FactLens 루트 제한. stdio 초기화·tools/list에서 check/explain/fix_prompt/verify_patch/deps 5개 확인. 이번 제품 보안 검사 미실행 |
| [Aside 공식 개발 문서](https://docs.aside.com/help/developers) | CLI 1.26.1020.1855·공식 aside-browser v3 스킬·MCP 신규 설치 | 서명·해시 검증 공식 installer 사용. MCP repl/memory_search/exec 3개 확인. 브라우저 앱 부재로 계정 상태 조회 실패. 앱 설치·로그인 필요 |
| [insane-search](https://github.com/fivetaku/insane-search) | Codex 스킬 신규 설치, 별도 Python3.12 환경 | upstream `33efae832d48670a09bb1d2329a8505963ff7e74` 고정. example.com 읽기 ok/weak_ok, markdown·trace·untrusted 경계 확인. 브라우저 fallback 미검증 |

설치와 런타임 연결은 구분한다. 새 스킬은 다음 턴부터 발견되며 MCP와 플러그인 hook은 Codex 재시작 후 확인한다. 개발 도구 설치가 제품 배포나 보안 검토 완료를 의미하지 않는다.

## 실행 경로와 제약

- 저장소 `.codex/config.toml`의 이전 클라우드 절대 경로를 PATH 명령으로 교체했다. Codex에서 **이 저장소 루트**를 열고 `codegraph`, `iron-laws`, `headroom`을 PATH에 둔다. Iron Laws의 프로젝트 설정 `--root .`는 실행 작업 폴더 기준이다. 현재 전역 MCP에는 위 FactLens 절대 경로로 루트를 제한했다.
- Aside 공식 installer가 만든 `current` junction으로 실행하면 경로 없음 오류가 발생했다. 버전 디렉터리의 서명 검증된 exe는 버전/도움말/guide/MCP가 정상이다. MCP와 `C:/Users/HP/.local/bin/aside.cmd`는 해당 버전 exe를 직접 사용한다. 업데이트 후 이 직접 경로도 갱신해야 한다.
- Aside 브라우저 공식 설치 파일: `C:/Users/HP/Downloads/AsideInstaller-1.0.928.2-win-x64.exe`. Authenticode Valid 및 AT YOUR SIDE INC 발행자를 확인하고 설치 프로그램을 사용자 화면에 실행했다. 현재 앱 exe는 없으며 설치 완료·로그인이 필요하다. 이후 account status를 확인한다. Work의 로컬 브라우저 비활성화 설정은 우회하지 않는다.
- insane-search 실행: `C:/Users/HP/.local/bin/insane-search.cmd https://example.com --json-content`. wrapper가 격리 Python과 스킬 폴더를 선택하며 자동 추가 설치·유료 xAI 검색을 끈다. Claude 전용 setup hook·GitHub star 요청은 실행하지 않았다.
- OmniRoute 대시보드: `http://localhost:20128`. 이번에 기존 사용자 상태를 재사용해 daemon으로 시작했다. 자동 부팅 등록은 하지 않았다. 기존 Codex 모델/인증 경로를 변경하지 않았다.
- Headroom 프록시 시작은 정책 차단 상태다. 단순 MCP 등록을 압축 작동이나 자동 모델 라우팅으로 표현하지 않는다.

## 대화·작업 기준

사용자 전역 `C:/Users/HP/.codex/AGENTS.md`에 도구 선택·전문 에이전트·Aside·insane-search·OmniRoute 지침을 반영했다. 매 요청에서 관련 기능을 먼저 검토하고 실제 필요한 것을 사용한다. 사용하지 않은 도구를 사용했다고 보고하지 않으며 같은 작업에 여러 자동 실행 워크플로를 중복 적용하지 않는다.

GitHub→AWS 자동 배포는 별도 미완료 작업이다. FactLens 전용 Lightsail `factlens-ai` 접속 대상·인증을 확인한 뒤 workflow/배포 권한/복구·health 확인을 구성해야 한다. 이번 도구 설정에서 AWS나 운영 제품은 변경하지 않았다.
