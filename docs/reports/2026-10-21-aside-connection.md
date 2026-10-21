# Aside 연결 경로 재조사 — 2026-10-21 KST

> Windows 로컬 후속: 현재 채팅에서 로컬 MCP 탭 조회·공개 홈 읽기·임시 회원 흐름 검증 성공. 원격 요금제 차단은 아래 클라우드 당시 이력이며 [로컬 공개 검증](2026-10-21-local-aside-public-ui.md)을 우선한다. 모바일/스크린리더 미검증은 유지한다.

사용자가 Windows MCP 연결 기능을 직접 활성화하도록 재요청했다. 단순 도구 미노출만으로 설치/활성화가 불가능하다고 안내했던 접근을 재검토했다.

## 확인한 사실

- 데스크톱 현재터미널 조회는 연결된 터미널 세션없음을 반환했다. 실행 셸은Linux이며Windows디스크 마운트는없다.
- [공식개발문서](https://docs.aside.com/help/developers)는 CLI설치, 호스팅 환경에서 ASIDE_CLI_AUTH_PATH를 정해 로그인하는 절차, Aside계정의Devices에서코드승인, aside mcp/aside repl을 안내한다. 따라서Windows로컬전환만이유일한연결방법이라는단정은철회한다.
- 설치스크립트를실행하기전파일로받으려 `curl --fail --silent --show-error --max-time 20 https://releases.aside.com/install.sh -o /tmp/factlens-aside-install.sh`를실행했으나HTTP403/exit22였다. 설치스크립트를실행하지못했고 현재OS지원도검증하지못했다.
- 현재확인된직접설치차단은공식배포호스트에대한네트워크접근이다. 차단우회·미러다운로드·인증서검증해제·프록시해제는하지않았다.

## 다음 실행 순서

1. 현재관리형환경의네트워크허용목록에 releases.aside.com 을허용한다. 현재제공된환경도구는상태/진단조회이며설정변경을실행한것은아니다.
2. 공식설치스크립트를다운로드해지원OS/설치내용을검토하고실제설치한다. Linux설치성공을미리보장하지않는다.
3. 호환CLI가준비되면사설쓰기경로에권한을제한한인증파일경로를지정하고공식로그인을진행한다. 사용자는Aside Settings > Account > Devices에서승인코드만확인한다. 비밀번호/API키/인증파일을채팅으로요구하지않는다.
4. 로그인성공출력과계정상태·브라우저호스트연결을확인한뒤 MCP설정/초기화/도구목록/실제탭읽기를검증한다. 현재셸에파일을추가하는것과현재채팅에MCP도구가활성화되는것도구분한다.
5. 지원되지않는OS또는현재세션도구갱신이안되는경우에는확인된결과를근거로Windows로컬실행환경경로를택한다. 현재는그단계까지확인하지못했다.

## 상태

설치시도진행:다운로드에서차단. 설치완료아님, 계정인증완료아님, Windows MCP활성화/공개브라우저검증완료아님. 제품코드·모델·예산·운영배포는변경하지않았다. 이번은문서정정이며제품테스트는재실행하지않는다.

## Linux 설치와 MCP 검증 후속

2026-10-21 새 클라우드 환경에서 재시도했다. 시작 체크아웃은 a986eef였고 원격 FETCH_HEAD는 df42b37이었다. 깨끗한 작업 트리를 확인하고 기존 이력을 preserved-cloud-work-20261021에 보존한 뒤 work를 최신 원격으로 맞췄다. 예약 커밋 세 개를 제품 이력에 병합하지 않았고 main은 변경하지 않았다.

- 네트워크 정책의 releases.aside.com 허용 확인 후 공식 install.sh 다운로드 성공. 스크립트는 Linux arm64/x64를 지원하며 공식 호스트의 아카이브를 사용자 설치 경로로 풀고 실행 링크를 만든다. 읽고 검토한 뒤 실행했다. 프록시·TLS 검증은 유지했다.
- CLI 설치 성공, `aside --version`/`--help` 실행 가능: 1.26.1020.1855. 설치 프로그램은 libatomic 안내를 출력했으나 CLI 실행은 성공했다. 이것은 브라우저 앱 설치 또는 연결 성공이 아니다.
- CLI guide와 login/mcp 도움말 확인. 사설 디렉터리 `/workspace/.aside-private`를 0700으로 만들고 ASIDE_CLI_AUTH_PATH를 그 안의 auth.json으로 지정했다. 인증 파일은 읽거나 Git에 넣지 않았다.
- `aside login --device-code`의 Email 입력 후 fetch failed로 종료됐다. 사용자 제공 이메일로 --email 재시도도 실패했다. 비밀번호는 요구하지 않았다. 승인 코드 미발급·로그인 성공/인증 저장 미확인이다.
- `codex mcp add aside --env ASIDE_CLI_AUTH_PATH=/workspace/.aside-private/auth.json -- <사용자 설치 aside 경로> mcp` 성공. 현재 클라우드의 전역 Codex 설정이며 사용자 Windows 설정이나 저장소 설정을 변경한 것은 아니다.
- 별도 stdio 프로세스에서 initialize(version 2024-11-05)와 tools/list 성공: server aside 1.26.1020.1855, repl/memory_search/exec. 검증 프로세스는 종료했다. 현재 채팅 도구 목록 활성화·인증·실제 도구 브라우저 실행 성공은 별개다.
- 인증 전 `aside host list`는 로컬 daemon 127.0.0.1:21420 ECONNREFUSED 및 CLI login 필요를 반환했다. 원격 호스트나 탭을 읽지 못했다.
- 공개 https://factlens.pigs0516.com 직접 curl 재시도는 CONNECT403/HTTP000/exit56. 설치 호스트 허용이 공개 사이트 또는 Aside 인증 서비스 접근도 허용한다는 의미는 아니다.

네트워크 진단은 요청 대상 호스트 이름만 확인했다(NODE_DEBUG=net, 인증 헤더/본문 출력 없음). 대상은 api.aside.com이며 기본 실행과 NODE_USE_ENV_PROXY=1 실행 모두 fetch failed였다. 상속 프록시를 사용한 curl https://api.aside.com 역시 CONNECT403/HTTP000/exit56이었다. 인증 파일 생성 여부는 파일 내용 없이 확인한다.

다음은 기존 규칙을 유지하면서 api.aside.com을 네트워크 허용 목록에 추가·적용 → 로그인 재시도 → 공식 기기 승인 → 로그인 성공/인증 저장 확인 → host list/프로필 확인 → 실제 탭 읽기 → 새 UI 공개 회원 흐름이다. 실제 모바일/스크린리더는 별도 미완료다. 제품 코드·모델·예산은 유지했으며 새 AI 호출/제품 테스트/운영 배포는 하지 않았다. 문서 변경은 링크와 diff를 검증해 work에 게시한다.

## 인증 API 허용 후 재시도

2026-10-21 새 환경에서 원격 work의 4c57551을 확인했다. 시작 체크아웃 a986eef는 preserved-cloud-work-20261021에 보존하고 깨끗한 work를 FETCH_HEAD로 맞췄다. main과 보존 예약 커밋은 변경·병합하지 않았다.

- 네트워크 상태 API의 설정 목록에는 releases.aside.com/api.aside.com이 있으나 policy state는 unknown이다. 정책 적용 완료로 단정하지 않고 실제 요청을 검증했다. 공식 install.sh 다운로드와 검토 후 Linux CLI 설치·도움말 실행 성공(1.26.1020.1855), 인증 API 루트 curl HTTP200.
- 사용자 제공 이메일로 기본 기기 로그인은 fetch failed. 상속 프록시를 유지한 NODE_USE_ENV_PROXY=1 재시도에서 기기 승인 코드가 발급됐고 CLI가 승인을 기다리고 있다. 이메일·일회용 코드는 저장하지 않는다. 승인 요청을 사용자에게 안내했으며 로그인 성공이나 인증 저장 완료는 아직 아니다.
- /workspace/.aside-private는0700이며 인증 파일 내용은 읽지 않았다. 대기 시점 auth.json 미생성 확인. 로그인 후에는 존재·권한·CLI 성공만 확인한다.
- 전역 Codex MCP는 실제 command -v 결과인 /home/agent/.local/bin/aside, ASIDE_CLI_AUTH_PATH와 NODE_USE_ENV_PROXY=1로 등록했다. 처음 잘못 지정한 /root 경로는 별도 프로세스 PermissionError를 확인하고 즉시 정정했다. 정정한 실제 실행 파일로 별도 stdio initialize 및 tools/list 성공, repl/memory_search/exec 확인 후 프로세스 종료. 등록만으로 현재 채팅 도구 활성화나 브라우저 연결 성공으로 해석하지 않는다.
- 공개 사이트 직접 curl은 HTTP000/exit22로 실패했다. 공개 UI·회원 흐름/실제 단말/스크린리더 검증은 아직 수행하지 않았다. 제품 코드·모델·예산·운영 배포 변경 및 새 유료 AI 호출은 없다. 문서만 검증·게시하며 제품 테스트는 재실행하지 않는다.

다음 순서는 사용자 기기 승인 → CLI 로그인 완료/인증 파일 권한 확인 → host list/프로필 확인 → 실제 탭 읽기 → 공개 새 UI와 임시 회원 흐름 검증·정리다. 인증 승인 전에는 이 후속을 완료 처리하지 않는다.

## 기기 승인 완료와 원격 제어 권한 차단

사용자가 기기 승인을 완료했다고 알렸고, 대기 CLI의 exit0 및 Signed in 출력을 확인했다. 인증 파일은 존재하며0600이다. 내용은 읽거나 출력하지 않았다. 계정 이메일과 승인 코드는 문서에 저장하지 않는다.

- NODE_USE_ENV_PROXY=1과 사설 인증 경로를 유지한 aside host list는 Remote hosts lookup failed:403을 반환했다. 네트워크 메타데이터 진단은 프록시 경유 요청을 확인했다. 로컬21420 daemon 부재는 클라우드에서 예상되는 상태이며, CLI 인증 저장 실패로 해석하지 않는다.
- 배포 CLI에 포함된 fetchRemoteHosts는 https://api.aside.com/remote/hosts를 요청한다. 해당 경로의 비인증 curl은 실제 HTTP401/ACCESS_TOKEN_INVALID로 응답해 프록시 CONNECT 차단과 구분했다.
- 임시 Node preload로 CLI의 정상 인증 요청 응답에서 status와 허용된 오류 코드, 결제 관련 오류 여부 boolean만 관측했다. 인증 헤더/토큰/원문 응답은 출력하지 않았다. 결과 status403/code PAYMENT_REQUIRED/paymentRequired true. CLI 내 HOST_ERROR_HINTS도 PAYMENT_REQUIRED를 Remote Control requires the Pro plan으로 설명한다. 인증 파일을 직접 읽거나 CLI를 변조하지 않았다. 진단 파일은 제거한다.
- 따라서 현재 차단은 Aside 원격 제어의 요금제 권한이다. Pro 가입/결제나 사용자 요금제 변경은 실행하지 않았다. 로컬 브라우저 앱과 같은 환경에서 실행하는 경로는 별도 선택지이며, 현재 클라우드가 그 환경으로 전환된 것은 아니다.

CLI 로그인 완료와 원격 브라우저 연결 완료는 별개다. host/profile/실제 탭 읽기·새 UI 공개 회원 흐름·실제 단말/스크린리더 검증은 미완료다. 사용자에게 확인된 요금제 요구를 안내하고 경로 선택을 기다린다. 제품 코드/운영 배포/AI 모델·예산 변경·유료 AI 호출은 없다. 문서 diff/추가 참조 검증 후 work에 게시하며 main은 변경하지 않는다.
