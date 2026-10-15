# 개발 도구 설정

`Fact-checking-website` 개발을 위한 도구 모음입니다. 웹사이트 코드는 아직 없습니다.

```bash
cd /workspace/Fact-checking-website
bash devtools/install.sh
source devtools/activate.sh
python3 devtools/start-services.py
```

설치 경로는 `/workspace/.devtools`입니다. 저장소의 `.agents/skills/`에는 외부 소스 캐시를 가리키는 링크 126개가 생성되며 Git에서는 제외합니다. `sources.lock.json`은 실제로 읽고 설치한 upstream 커밋을 기록합니다. 기존 소스 캐시의 커밋이 다르면 설치 스크립트는 덮어쓰지 않고 중단합니다. npm 도구와 Python 상위 패키지는 명시한 버전으로 설치하며 전이 의존성은 도구 저장소의 npm lock 및 현재 환경 스냅샷으로 유지합니다. 완전히 새로운 머신에서 전이 의존성까지 동일함을 보장하는 잠금 구성은 아닙니다.

| 프로젝트 | 설치/연결 | 사용 및 한계 |
|---|---|---|
| [Strix](https://github.com/usestrix/strix) | CLI 1.7.0 + 스킬 9개 | `strix --help`; 실제 스캔은 Docker 이미지와 선택한 모델 인증 필요. 미실행 |
| [OmniRoute](https://github.com/diegosouzapw/OmniRoute) | CLI/서비스 3.8.51 | 포트 20128, `/api/health` 정상. 모델 API는 인증 필요 |
| [PM Skills](https://github.com/phuryn/pm-skills) | 스킬 69개 | PRD·기획·전략 요청에 사용. Claude 전용 슬래시 명령은 Codex 명령으로 변환하지 않음 |
| [Ponytail](https://github.com/DietrichGebert/ponytail) | 스킬 6개 | 간결성 및 리뷰. 네이티브 플러그인과 lifecycle hook은 미활성화 |
| [CodeGraph](https://github.com/colbymchenry/codegraph) | CLI/MCP 1.6.2 | `codegraph init --yes .`, `codegraph query NAME --path .`. 앱 소스가 없으므로 현재 인덱스는 비어 있음 |
| [LazyCodex](https://github.com/code-yeongyu/lazycodex) | CLI 5.1.33 + 스킬 27개 | 전체 harness·역할·hook 자동 설치는 미적용. 현재 npm installer dry-run은 autonomous 플래그를 추가하므로 실행하지 않음 |
| [Superpowers](https://github.com/obra/superpowers) | 스킬 15개, 현재 세션 플러그인도 제공됨 | 개발 워크플로. 동일 작업에 플러그인/로컬 스킬을 중복 실행하지 않음 |
| [Headroom](https://github.com/headroomlabs-ai/headroom) | CLI/MCP/프록시 0.41.0 | 포트 8787, OmniRoute 로컬 upstream. 구조 기반 lossless 모드, ML Kompress 비활성화 |
| [Iron Laws](https://github.com/JinHo-von-Choi/iron-laws) | CLI/MCP 1.7.0 | `iron-laws check .`; HIGH 이상이면 종료코드 1. 미확정 분석과 미검증 규칙 조합을 확인할 것 |

## Codex 연결

`.codex/config.toml`에 CodeGraph, Iron Laws, Headroom MCP 서버를 등록했습니다. 실제 stdio 초기화와 도구 목록 조회를 검증했습니다. 현재 채팅에 도구가 자동 추가되는 것은 아니며, 프로젝트를 신뢰한 새 Codex 세션에서 다시 발견됩니다. 읽기 전용 관리 Codex 홈을 수정하지 않았습니다.

Ponytail과 LazyCodex는 프로젝트 스킬 사용과 네이티브 harness 설치가 다릅니다. 후자는 쓰기 가능한 일반 Codex 설치에서 upstream 안내대로 설치하고 hook을 직접 신뢰해야 합니다. 현재 클라우드에서는 설치/신뢰가 끝났다고 간주하지 않습니다.

## 서비스 및 인증

서비스는 loopback에 바인딩하며 `start-services.py`는 기존 정상 서비스를 재사용합니다. 로그는 `/workspace/.devtools/logs`에 있습니다. 저장소에 생성된 키나 인증 정보를 넣지 마세요. OmniRoute의 영속 상태는 `/workspace/.devtools/state/omniroute`에 보관합니다.

Headroom의 OpenAI 호환 upstream은 OmniRoute의 `/v1`입니다. 로컬 상태 검사는 통과했지만 실제 모델 추론, 비용 절감률, 외부 제공자 연결은 검증하지 않았습니다. 사용할 제공자를 선택한 후 환경 설정에서 인증을 추가하고 해당 제공자 도메인을 허용해야 합니다. 현재 Codex 자체의 인증/모델 경로는 변경하지 않았습니다.

Strix는 앱 코드와 선택한 모델이 준비된 뒤 허가된 대상에 실행하세요. 현재는 CLI와 스킬만 준비했으며 sandbox 이미지 다운로드나 유료 호출은 하지 않았습니다.

## 검증 기록

- Python 의존성 검사 정상.
- 임시 Python 샘플을 CodeGraph로 인덱싱하고 함수 검색 성공.
- Iron Laws에서 정상 샘플 통과, MD5 취약 암호 샘플 실패(종료코드 1) 확인. 처음 사용한 호출자 없는 command 샘플은 `unresolved`로 보고되었으므로 탐지 성공으로 세지 않음.
- MCP 초기화: CodeGraph 1개(빈 프로젝트용), Iron Laws 5개, Headroom 3개 도구 조회 성공.
- OmniRoute 대시보드 HTTP 200 및 상태 API 정상; 인증 없는 모델 목록 요청은 HTTP 401.
- Headroom `ready: true`; Kompress는 명시적으로 비활성화. 외부 모델 호출은 미검증.
- 클라우드 설치·시작 지침의 저장은 환경 게시나 GitHub push와 별개입니다.
