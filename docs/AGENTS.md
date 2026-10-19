# 프로젝트 가이드 — 공통 지침 (AGENTS.md)

> **현재 작업 기준 · 2026-10-19:** TASK-023 출처 등록 대조·중복/명시 인용 관계 검토를 결과/API/화면에 연결했다. 실제 등록 출처 목록은 비어 있으며 출처 인증/독립성·일반 문서 확정은 미완료다. 규칙v3는 유지한다. 재시작 후 환경 readiness는 unknown이며 개발 DB 복구 후 Python157/API24개가 통과했다. 최신 기록10 §40.

- 현재 상태 갱신: 2026-10-19 (Asia/Seoul)
> **이전 기준 · 2026-10-16 (이력):** 개발용 PoC 기반 구현. 실제 AI·시각/연구·운영은 미완료. 현재 작업은 TASK-016의 키/네트워크/실자료 검증과 전송 정책 확인이다. 과거 작업 기록은 당시 이력으로 보존한다.

순차 실행 기준: [00 통합 실행 순서](00_문서_가이드.md#통합-실행-순서). 현재 구현과 과거 이력을 구분하며 이번 결과는 10의 최신 기록을 따른다.

## 작업 시작·종료 규칙

사용자가 말하는 **프로젝트 가이드**는 저장소 `docs/` 폴더의 `AGENTS.md`와 아래 번호 문서 12개를 합친 **전체 13개 문서 세트**를 뜻한다. 개별 문서는 파일명 또는 역할로 구분하며 기존 파일명은 유지한다. 저장소 루트의 `AGENTS.md`는 이 공통 지침을 읽도록 연결하는 진입점이며 13개 본문에 포함하지 않는다.

- `AGENTS.md`: 공통 작업 지침
- `00_문서_가이드.md`: 문서 운영 규칙
- `01_시스템_개요.md`
- `02_기능_설계.md`
- `03_데이터베이스_설계.md`
- `04_API_명세.md`
- `05_업무_플로우.md`
- `06_프런트엔드_구조.md`
- `07_백엔드_구조.md`
- `08_운영_배포.md`
- `09_위험요소_및_개선포인트.md`
- `10_파일_점검_현황.md`
- `99_해야할일..md`

이 정의가 과거 작업 기록의 AGENTS.md 단독 호칭보다 우선한다. 과거 기록은 당시 이력으로 보존한다.

1. 모든 프로젝트 작업을 시작하기 전에 공통 지침(`AGENTS.md`)을 먼저 읽고 최신 지침과 현재 상태를 확인한다. 이어서 문서 가이드·작업 목록·관련 설계 문서를 확인한다.
2. 작업을 끝내기 전에 프로젝트 가이드 중 영향받은 문서와 `AGENTS.md`의 최근 작업 기록을 갱신한다. 변경된 구조·실행 방법·결정·제약·다음 작업을 관련 절에 반영한다.
3. 지침이나 구조 변경이 없는 작업도 아래 최근 작업 기록에 수행 내용·검증 결과·남은 일을 간단히 갱신한다. 실행하지 않은 검증은 통과로 쓰지 않는다.
4. 관련 설계 문서와 파일 점검 현황·작업 목록도 함께 갱신해 실제 상태와 일치시킨다. 기존 사용자 지침과 작업 이력을 임의로 삭제하지 않는다.

## FactLens AI 프로젝트 기준

- 제품명: **FactLens AI** — 멀티모달 인공지능 기반 영상 허위정보 탐지 및 근거 교차검증 플랫폼.
- 기준 자료: 사용자가 제공한 [FactLens AI 기획서 원문](../references/FactLens_AI_기획서_원문.md)(2026년 10월 작성, 졸업프로젝트 제안·개발 계획 초안). 2026-10-15 검토·반영. 원문은 변경하지 않고 보존하며, 후속 결정은 번호 문서에 기록한다.
- 목적: 영상의 개별 사실 주장과 맥락 왜곡 가능성을 외부 근거와 대조하고, 해당 영상 구간·인용문·근거 URL·판단 한계를 설명하는 의사결정 지원 서비스다. 절대적 진실 보증이나 딥페이크 판별기를 목표로 바꾸지 않는다.
- 대상 사용자군: 일반 뉴스/SNS 이용자, 대학생·연구자, 팩트체크 종사자, 미디어 리터러시 교육기관. MVP의 일차 사용자와 검증 주제는 후속 범위 검토에서 좁힌다.
- 현재 상태: 업로드·미디어 검사·작업/삭제·보고서 UI·제한적인 정형 수치 검증을 개발용 PoC 기반으로 구현했다. 실제 STT/검색/LLM 실호출 검증·시각 분석·연구 성능 평가·운영 배포는 미완료다. 아래 원칙은 최종 요구이며 구현 사실은 각 문서의 현재 구현 절과 10의 검증 기록을 따른다.

### 범위와 진행 순서

- 입력: 최종 MVP의 필수 입력은 MP4 및 MP3/WAV 직접 업로드다. 초기 평가 대상은 1~3분 한국어 뉴스형 영상이다. 개발용 구현의 제한은 100 MiB·180초다. 운영 제한과 연구 데이터 범위는 별도 검토한다.
- 지원 영상 URL·기사 URL·YouTube 등은 확장 범위다. 초기 업로드 경로보다 먼저 만들지 않으며 플랫폼 정책·접근 권한을 확인한다. 다국어·실시간 방송·일괄 처리·팀 검토·API 상품화·C2PA도 후속 제안이다.
- 기획 단계: 음성 팩트체크 PoC → 자막/화면 PoC → 근거 Validator·교차검증·판정 규칙 PoC → 웹 MVP와 비교 평가. 최종 MVP의 필수 항목을 단계 축소 과정에서 조용히 제외하지 않는다.
- 우선 기준 문서: [01 시스템 개요](01_시스템_개요.md), [02 기능 설계](02_기능_설계.md), [05 업무 플로우](05_업무_플로우.md). 다음 작업은 `99_해야할일..md`의 TASK-023 출처 신원/계보·일반 문서 의미 검증이다. 계약·유보 회귀·수집/구조/발행정보 관측 추적은 구현했다. TASK-016은 환경/SDK 연결 확인 후 Brave 계정 권한·사용/전송 권한 있는 미디어·근거 원문 접근 조건을 확인해 승인된 개발 예산으로 실제 분석을 검증한다. 이미 제공된 프로젝트 목적을 다시 처음부터 묻지 않는다.

### 분석과 판정의 필수 원칙

1. 음성 전사·자막/OCR·영상 프레임을 독립 처리하고 원본 타임스탬프·발화/자막 출처에 연결한다. 검증 가능한 원자적 주장과 의견·예측 등을 구분한다.
2. 근거 검색과 근거 검증(Evidence Validator)을 분리한다. URL 접근 가능만으로 신뢰를 인정하지 않는다. 원문 인용 위치, 발행 주체, 날짜/기간, 대상/지역, 수치/단위/분모, 맥락, 출처 독립성을 검증한다.
3. 음성·자막·영상의 내부 일치와 외부 사실성은 별개 결과다. 여러 Agent의 합의·공식 기관 이름·이미지 유사성만으로 사실 또는 최초 원본을 확정하지 않는다. 게시일과 촬영일을 구분한다.
4. 근거 없음·접근 실패·원문 인용 검증 실패·원본 영상 미발견은 거짓의 근거가 아니다. 불충분/충돌/처리 오류를 구분하고 판정을 유보한다. LLM의 단독 응답 대신 검증된 근거와 버전 관리한 규칙으로 최종 판정한다.
5. 근거 관계는 `SUPPORTED / REFUTED / INSUFFICIENT`, 주장 판정은 `근거로 확인됨 / 반박됨 / 검증 불충분 / 검토 필요 / 검증 대상 제외`로 구분한다. 종합 판정·작업 처리 상태·근거 강도를 같은 enum으로 합치지 않는다.
6. 근거 강도 `높음/보통/낮음`은 진실 확률이 아니다. 보정 실험 없이 0~100% 진실 점수를 표시하지 않는다. ‘허위 주장 확인’은 반박된 핵심 주장 범위로 한정한다.
7. 주장·프레임·타임스탬프·근거 원문/위치·출처/발행일·검사 결과·판정 이유·불확실성·모델/프롬프트/규칙 버전을 추적한다. Agent 간 입출력은 스키마로 검증하며 내부 비공개 추론을 사용자 설명의 필수 산출물로 요구하지 않는다.

### 제안 스택과 미결정 항목

원문 제안은 Vue 3 + TypeScript + Vite, Node.js API(Express **또는** NestJS), Python + FastAPI AI Worker, PostgreSQL, Redis/작업 큐, 로컬 **또는** S3 호환 스토리지, FFmpeg/OpenCV/PaddleOCR, OpenAI API, Google Fact Check Tools API·Cloud Vision Web Detection, Docker다. 원문 제안은 보존한다. 개발용 DEC-002는 Vue/Express/Python 프로세스 Worker/PostgreSQL/Redis/비공개 로컬 볼륨/Compose로 구체화했다. FastAPI 서버는 만들지 않았다. 개발용 API 계약과 기본 24시간 보관은 구현됐으며 개발 AI 제공자·월/건 예산은 승인됐으며 운영 인증/배포/백업은 미결정이다.

제품의 역할별 AI Agent는 설계 대상 모듈이다. 이 명칭이 개발 작업에서 서브에이전트를 자동 생성하라는 지시는 아니다. 개발용 OmniRoute·Headroom·Strix를 제품 필수 의존성으로 넣지 않는다.

### 연구 검증과 데이터 보호

- 연구 가설 H1~H3는 미검증이다. 같은 평가 데이터/주장 목록으로 A(전사·자막 텍스트 LLM), B(A+검색), C(전체 제안 시스템)를 비교한다. 평가 목표 90~120개 영상/구간과 12주 일정은 목표/예시이며 확보 실적·확정 기한이 아니다.
- Claim Recall, Evidence Precision@K, Evidence Validity, Verdict Macro-F1, Cross-modal F1, False Verdict Rate, Abstention Rate, 시간·비용을 함께 측정한다. 라벨 규칙·분모·K·분할·목표치·모델/검색 조건을 실험 전에 고정한다. 동일 원본의 변형을 개발/평가에 나눠 넣지 않는다. 유보율만 높여 성능을 부풀리지 않는다.
- A/B/C만으로 Validator와 시각 분석의 독립 기여를 분리할 수 없으므로 절제 실험 추가는 검토 제안으로 남긴다. 평가 결과가 가설을 지지하지 않아도 그대로 기록한다.
- 업로드 검증·미디어 처리 격리·자원 제한·분석/파일 접근 제어·외부 URL SSRF 방어·외부 전송 동의·보관/삭제 정책을 구현 전 정의한다. 검색된 근거 URL도 비신뢰 입력이다. 검색용 프레임의 공개 URL 제공은 자동 허용하지 않는다.
- 상세 검토 쟁점은 [09 위험요소 및 개선포인트](09_위험요소_및_개선포인트.md), 후속 작업은 [99 해야 할 일](99_해야할일..md)을 따른다.

## 기획서 기준 산출물과 시연

2026-10-15 재첨부한 `붙여넣은 텍스트.txt`를 기준 자료와 대조했다. 저장 원문과 42,951바이트 전체가 동일하다. SHA-256: `abb95ff2815b362784ebb80bf97c65eed013194b65c62d7f9a29911d030510f0`. 기존 원문을 유지하며 개정본으로 중복 등록하지 않는다.

- 개발 산출물(원문 16.1절): 웹 서비스, Node.js API, Python 미디어/AI 모듈, 근거 수집·검증, 멀티모달 교차검증, 판정 규칙, DB/이력, 결과 시각화/보고서. 해당 요구는 02~08에서 상세화하며 현재 구현 완료를 의미하지 않는다.
- 연구 산출물(16.2절): 데이터셋·라벨링 기준, PoC 실행 기록, A/B/C 비교 평가, 오류/한계 분석, 기술 보고서와 아키텍처 문서. TASK-014에서 평가 조건과 기록 방식을 정의한다.
- 시연 목표(16.3절): 사실 주장 일치, 잘못된 수치/날짜, 음성·자막·화면 맥락 불일치, 근거 부족으로 인한 판정 유보의 네 유형. 검증 가능한 입력과 정답 근거를 준비하며 가상 예시를 실제 검증 실적으로 표시하지 않는다.
- 원문은 기획 기준이다. 이 문서에 추가한 ‘대학생/연구자·공공 통계 중심 첫 PoC’는 별도 추천안이며 사용자가 확정한 범위로 취급하지 않는다.

## 이번 착수 기준 (2026-10-15)

- 사용자 요청: 기존 가이드를 기준으로 프로젝트 가이드를 정리하고 작업을 시작한다. 기존 기획을 보존하며 TASK-001부터 진행한다.
- 실행 순서: TASK-001 범위 검토 → TASK-002 사용자 여정/인수 조건 및 TASK-013 판정 계약 → TASK-014 평가 계획 → TASK-003/004 기술/데이터/API 선택 → TASK-005 첫 구현.
- 첫 검토안은 [01 시스템 개요의 TASK-001 착수안](01_시스템_개요.md#7-task-001-착수안)에 기록한다. 선택지를 문서에 제안했다고 사용자 확정으로 취급하지 않는다.
- 첫 PoC에서도 근거 검색과 원문 검증을 분리하고 인용 위치·출처·타임스탬프·판정 한계를 남긴다. 텍스트만 사용하는 단계에서 시각 검증까지 끝났다고 표시하지 않는다.
- 저장소 상태: 가이드·원문·개발 설정은 `c4a4c4e`로 반영했고, 가이드 13개를 `docs/`로 옮긴 `80c64ed`도 GitHub main 푸시와 원격 커밋 일치를 확인했다(이전 작업 기록). 현재 제품 구현·환경 게시·배포는 미실행이다. 이전 재조회는 인증 부재로 실패했으나 재시도에서 인증이 복구되어 원격 main `80c64ed`를 확인했다.

## 현재 개발 환경

The repository now has a private audio web PoC foundation in apps/. Live adapters are implemented and SDK model-list access was checked; the live worker is not running and media inference remains unverified; do not treat demo reports or passing fixture tests as real AI analysis or research validation.

Read `devtools/README.ko.md` for the installed tools and limitations. Run `bash devtools/install.sh` to refresh development tools, then `source devtools/activate.sh`. Tools and upstream source caches are retained under `/workspace/.devtools`, outside this checkout. Each cloud task is already isolated; use this checkout and do not create Git worktrees unless the user requests one.

## Workflow

- Use Superpowers for development workflow when applicable. It is already available as a session plugin here; project copies support future sessions that lack that plugin. Do not run duplicate workflow copies for the same task.
- Use PM Skills for product discovery, strategy, PRDs, prioritization, and delivery planning when relevant.
- Use Ponytail for explicit simplicity/review requests. Use LazyCodex skills for explicit LazyCodex planning/execution requests. Choose one lead workflow per task; do not stack competing autonomous loops.
- Use CodeGraph for code navigation after source files exist; use normal file tools when the graph is empty.
- Use Iron Laws for offline static security and quality checks. Preserve its exit code and report coverage limits.
- Use Strix only against user-authorized targets. It needs an LLM provider and Docker for local scans. No live scan has been validated against the product; offline findings remain unresolved as documented in 09/10.
- OmniRoute and Headroom are optional local services. Start them with `python3 devtools/start-services.py`. They are not the website server. Provider authentication and actual inference are separate from local readiness.

Project MCP settings are in `.codex/config.toml`; discovery requires a new Codex session and project trust. Installing CLI tools or linking skills does not activate lifecycle hooks. LazyCodex/Ponytail native lifecycle hooks have not been installed or trusted in this managed cloud instance. Do not bypass hook trust or change sandbox/approval settings to activate them.

## Documentation workflow

Start each project task by reading [00_문서_가이드.md](00_문서_가이드.md), [99_해야할일..md](99_해야할일..md), and the relevant design documents. The project guide files, including AGENTS.md, live in docs/. Run development commands from the repository root. Preserve the exact requested filename `99_해야할일..md`.

- Apply Superpowers to clarify intent, design, plan, implement, and verify as appropriate. This document setup authorizes documentation work; it does not approve undecided product architecture or start product implementation.
- Use 01 for purpose/scope/decisions, 02 for features/acceptance, 03 for data, 04 for API contracts, 05 for flows, 06 for frontend, 07 for backend, 08 for operations, 09 for risks, 10 for file checks, and 99 for actionable tasks. Follow the change-impact table in 00.
- Keep confirmed facts, proposals, undecided items, implementation status, and executed verification distinct. Do not invent product endpoints, tables, frameworks, or test results from the repository name.
- Use stable IDs defined in 00 to connect features, flows, contracts, files, risks, and tasks. Existing approvals remain valid within their scope; routine documentation edits do not require renewed approval.
- Before closing a task, update the affected design documents, 10_파일_점검_현황.md, and 99_해야할일..md. Update 09 when risks change. Record verification evidence and limitations; do not mark unrun checks as passed.
- Preserve user changes. No extra agents, worktrees, remote publication, or deployment are authorized merely by a documentation checklist. Follow the current user request and higher-priority instructions for those actions.

## 최근 작업 기록

- 2026-10-15: 사용자 지시에 따라 `AGENTS.md`의 호칭을 ‘프로젝트 가이드’로 정의하고, 모든 작업 시작 전 읽기·종료 전 갱신 규칙을 추가했다.
- 검증: 프로젝트 가이드 규칙과 관련 문서 연결의 정적 확인. 제품 실행 검증은 수행하지 않았다.
- 당시 다음 작업: TASK-001. 이후 아래 기획서 검토 기록을 기준으로 잔여 범위를 진행한다.

### FactLens AI 기획서 검토·반영

- 2026-10-15: 사용자 첨부 기획서 전체 18개 본문 절과 참고 자료를 읽고 원문을 references에 보존했다. 제품 목적·MVP/확장 경계·판정 원칙·후보 스택·PoC 평가 요구를 프로젝트 가이드와 번호 문서에 연결했다.
- 검토 결과: 핵심 주장 선정, 복합 종합 판정의 우선순위, 입력/비용 제한, 인증·삭제 정책, 평가 분할·목표치·절제 실험이 추가 설계 대상이다. 원문 가설과 성능 목표를 검증 결과로 승격하지 않았다.
- 검증: 원문 42,951바이트 보존, 상대 링크 130개, 식별자 정의/참조 98개, 파일 목록 22개 정적 확인 통과. 기존 비문서 파일 8개의 체크섬 일치를 확인했다. 제품 구현·외부 API 동작·성능 평가·배포는 수행하지 않았다.
- 다음 작업: TASK-001의 일차 사용자·검증 주제·자원 한도 확정, TASK-002·TASK-013·TASK-014의 인수 조건·판정 계약·평가 프로토콜 구체화. 구체적인 미결정 항목만 질문한다.

### 프로젝트 가이드 정리 및 TASK-001 착수

- 2026-10-15: 기존 가이드를 보존하고 사용자 요청·실행 순서·원격/작업 공간 차이를 명시했다. 01에 최초 PoC 대안과 추천 범위·인수 기준·잔여 결정을 작성하고 99/10에 연결했다.
- 검증 범위: 이번 변경 문서의 상대 링크와 필수 내용 정적 확인. 제품 실행·외부 API·성능 평가는 미실행이다.
- 다음 작업: 01의 일차 사용자/주제 추천안 검토 후 비용 한도와 입력 제한을 정하고 TASK-002/013/014로 진행한다. TASK-001은 진행 중이다.

### 문서별 작업 체계 정비 (2026-10-15)

- 사용자 요청의 정확한 파일명 12개를 유지하고 기존 기획·결정·작업 이력을 보존했다. 00에 실제 작업 진행표·Superpowers 적용 기준·공통 변경 기록을 추가하고 01~10/99에 시작 자료·작성 순서·인계 조건을 연결했다.
- 이후 작업은 00의 진행표와 각 문서의 ‘문서별 작업 절차’를 따른다. 문서 운영 준비와 제품 설계 승인/구현 완료를 구분한다.
- 검증 근거는 10의 문서 체계 정비 기록에 남기며, 다음 제품 작업은 TASK-001 잔여 결정이다.

### 첨부 기획서 재확인 및 가이드 갱신 (2026-10-15)

- 사용자 요청으로 재첨부 원문과 보존본을 대조했다. 두 파일이 동일하므로 기존 제품 기준과 번호 문서의 요구사항을 유지하고, 원문 16절의 개발/연구 산출물과 네 가지 시연 목표를 가이드에 명시했다.
- 검증: 파일 바이트·SHA-256 대조 및 변경 문서 상대 링크 확인. 제품 실행·성능 평가·외부 참고 URL 확인은 미실행이다.
- 다음 작업: TASK-001 잔여 범위 결정, TASK-002/013/014 상세화.

### 프로젝트 가이드 호칭 변경 (2026-10-15)

- 사용자 지시에 따라 프로젝트 가이드를 AGENTS.md와 번호 문서 12개의 전체 세트로 재정의했다. 개별 문서는 공통 지침·문서 운영 규칙 또는 파일명으로 구분한다.
- 00의 작업 시작/종료 표현과 문서 링크 표기를 맞추고 10/99에 기록했다. 파일명과 제품 설계는 유지한다.

### 기획서 문서별 배분 기준 (2026-10-15)

이번 재첨부 원문도 FILE-022와 동일한 42,951바이트다. 프로젝트 가이드 전체에 원문 요구를 역할별로 구체화한다. 원문 절별 배분표는 [00 문서 가이드](00_문서_가이드.md)의 ‘기획서 반영 추적표’를 기준으로 한다.

- 01은 목적·연구 질문·범위·산출물, 02는 기능과 판정 규칙, 03은 추적 가능한 데이터, 04는 API 책임과 계약 미결정을 관리한다.
- 05는 분석/유보 흐름, 06은 화면·결과 탐색, 07은 미디어/Agent/Validator 경계, 08은 단계별 운영·평가 실행 조건, 09는 한계와 개선 검증을 관리한다.
- 10은 원문/파일/검증 근거, 99는 단계별 실행 작업을 관리한다. 상세 요구는 담당 문서에 기록하고 다른 문서는 연결한다.
- 문서 수정 직전에 해당 문서에 반영할 내용을 사용자에게 알린다. 새 범위나 구현 사실을 원문에 임의로 추가하지 않는다.
- 다음 제품 작업은 TASK-001/002/013/014이며, 이번 분배 작업은 제품 구현·실험의 완료를 의미하지 않는다.

- 이번 분배 검증: 13개 문서의 기존 본문 보존, 18개 원문 절 및 참고 자료 추적표, 상대 링크·원문 동일성 정적 확인. 상세 결과는 10의 분배 점검 기록 참조. 제품 검증은 미실행이다.

### GitHub 반영 작업 (2026-10-15)

- 사용자 요청으로 프로젝트 가이드 13개, 보존 원문, 참조 개발 도구 및 설정을 GitHub main에 반영한다. 생성 캐시·환경 비밀 파일은 제외한다.
- 커밋 전 상대 링크·원문 해시·문서 구조와 설정/스크립트 정적 검사를 수행하고, 푸시 후 원격 main과 로컬 커밋의 일치를 확인한다. 제품 배포는 별도다.

### 프로젝트 가이드 폴더 정리 (2026-10-15)

- 사용자 요청으로 가이드 13개를 docs/로 이동했다. 문서 간 링크는 유지하고 저장소 루트의 references·devtools·설정 파일 링크는 상위 상대 경로로 수정했다.
- 루트 README에서 docs/00 문서 가이드로 진입한다. 개발 명령은 저장소 루트에서 실행한다.
- 파일명·원문·제품 설계는 보존하며 링크/배치 검증 후 GitHub main에 반영한다.

### 현재 상태 정합성 갱신 (2026-10-15)

- docs/ 이동과 기존 GitHub 반영 완료 사실을 현재 상태에 반영했다. 과거 작업 이력은 보존한다.
- 08의 게시 상태, 09의 RISK-002, 99의 TASK-009를 같은 근거로 정리했다. 현재 원격 재조회 실패와 과거 푸시 성공을 구분한다.
- 다음 제품 작업은 TASK-001의 사용자/주제·최초 입력·자원 한도 결정이다. 제안 스택·PoC 추천안·평가 목표를 새로 확정하지 않았다.

### GitHub 인증 재시도 (2026-10-15)

- 사용자 요청으로 재시도한 git ls-remote가 성공했고 원격 main 80c64ed를 확인했다. 이전 인증 실패는 과거 기록이며 현재 재시도에서는 재현되지 않았다. 정확한 인증 중단 원인은 확인하지 못했다.
- 상태 정리 문서 5개를 검증 후 커밋/푸시하고 원격 커밋 일치를 확인한다.

### 프로젝트 가이드 검토 (2026-10-15)

- 사용자 요청으로 13개 가이드의 요구 추적·문서 간 정합성·작업 선행 조건·지침 적용 범위를 검토했다.
- 수정 제안: docs/AGENTS의 저장소 전체 적용을 위한 루트 진입 지침, 부적합 근거와 반박 근거의 구분, TASK-005/006의 판정·평가·데이터 보호 선행 조건 명시.
- 이번 작업은 검토 기록만 추가했다. 설계/경로/작업 의존성 본문 수정 및 커밋/푸시는 수행하지 않았다.

### 검토 수정 반영 (2026-10-15)

- 사용자 승인에 따라 루트 AGENTS 연결, 01의 비교 적합성/단위 환산/반박 관계 구분, 99의 단계별 구현·평가·공개 선행 조건을 수정했다.
- 본문 13개는 docs/에 유지하며 루트 진입점은 안내만 제공한다. 제품 코드·기획서 원문·미결정 기술 선택은 변경하지 않는다.
- 관련 위험과 파일 점검 현황을 갱신하고 검증 후 GitHub main에 반영한다.

### 프로젝트 가이드 재독 (2026-10-15)

- 사용자 요청으로 docs/의 프로젝트 가이드 13개를 읽고 목적·필수 입력·분석/판정 원칙·후보 구조·작업 선행 조건을 확인했다.
- 설계와 제품 구현 상태는 변경하지 않았다. 다음 제품 작업은 TASK-001 잔여 범위/자원 결정이다. 읽기 확인 근거와 한계는 10의 재독 기록을 따른다.

### 제작 착수 설계 (2026-10-15)

- 사용자 제작 요청에 따라 01 §9에 첫 음성 검증 수직 기능의 접근 비교·구성·제약 제안·검증 기준을 작성했다. 검토 대기이며 제품 코드/배포는 미실행이다.

### 첫 구현 계획 작성 (2026-10-16)

- 사용자 진행 지시로 01 §9의 첫 설계안을 채택하고 구현 계획을 작성했다. 기존 기획을 보존하며 유료 제공자/예산과 운영 권한 미결정은 유지한다. 제품 코드는 아직 작성하지 않았다.

### 첫 음성 웹 PoC 구현 (2026-10-16)

- 사용자 구현 계획 승인으로 apps/api·apps/worker·apps/web과 Compose 개발 실행을 추가했다. 업로드·형식/시간 검사·작업/삭제·근거/판정 규칙·한국어 보고서 UI를 구현했다.
- 실제 STT/검색/LLM은 미설정으로 실패 처리한다. 가상 예시와 실제 분석을 구분하며 운영 인증/배포·연구 성능은 완료가 아니다.
- 상세 인터페이스·실행 명령은 구현 계획과 README, 검증 근거는 10, 남은 일은 99의 최신 기록을 따른다. 아래 이전 미구현 서술은 당시 기획 이력이다.

### 프로젝트 가이드 현재 상태 동기화 (2026-10-16)

- 사용자 요청에 따라 13개 문서의 상단 기준·본문 표·후속 TASK를 코드/기존 검증 기록과 맞췄다. 이전 기획/작업 이력은 보존하고 실제 AI·연구 성능·운영 미완료를 구분했다.
- 새 재개 지점은 TASK-016(실제 AI 연결), 운영 공개 준비는 TASK-017이다. 이번에는 문서 검증만 수행하며 제품 코드·외부 서비스 설정·원격 push는 변경하지 않는다.

### TASK-016 비용 호출 경계 준비 (2026-10-16)

- 사용자 재개 요청으로 승인된 구현 계획 Task 5를 이어갔다. 환경은 connected/running, 네트워크 정책 enforced였으나 secret/runtime variable/outbound identity 바인딩은 비어 있었다. 인증값은 읽거나 출력하지 않았다.
- metered.py의 BudgetedCall/BudgetedProviders를 구현하고 파이프라인에 사용량 전달을 연결했다. 예산 예약 전 외부 작업 호출 금지, 실패/미확인 사용량 예약 유지, 실제 비용 정산 및 초과시 후속 호출 차단을 검증한다.
- 실제 제공자·모델·가격/통화·월/건 한도는 사용자 답변 대기다. 이번 구현은 SDK/외부 유료 호출을 활성화하지 않는다.

### 제공자·예산 추천 (2026-10-16)

- 사용자 미정 답변에 따라 공식 가격/기능 자료를 조사하고 01 §11에 OpenAI whisper-1/gpt-4.1-mini + Brave Search, AI API 월 $20·건 $0.20 추천안을 기록했다. 미확정이며 실제 호출/키 설정은 하지 않았다.

## 승인된 실제 제공자 연결 후속 (2026-10-16)

사용자 승인에 따라 OpenAI whisper-1 / gpt-4.1-mini + Brave Search 어댑터를 구현했다. 월 USD $20, 건당 $0.20 상한은 확정했다. 기본 모드는 disabled이며 실제 키·아웃바운드 설정과 실자료 smoke는 미완료다. TASK-016은 진행 중으로 유지한다.

### 최근 작업 기록 — 승인 SDK 연결 (2026-10-16)

사용자 승인 프로필과 월/건 예산을 적용한 SDK 어댑터·오류 UI·회귀 테스트를 추가했다. 별도 리뷰의 원문 숫자 불일치를 수정했고 Python 76/API 12/브라우저 5개, 타입 검사·빌드·이미지 교체를 검증했다. 정적 점검 48건은 미해결이며 실키/네트워크/실자료·운영 공개는 미완료다. 상세는 10 §26, 설정은 08의 최신 절 참조.

### 최근 작업 기록 — 경로 보호·가이드 갱신 (2026-10-17)

13개 가이드의 현재 구현/승인 예산/실호출 미검증 상태를 맞췄다. TASK-018 파일 경계 4건을 재현 후 수정했고 API 16·Python 76·브라우저 5, 타입/빌드 및 Compose를 검증했다. 기존 정적 48건을 전부 분류했으며 최신 49건/종료 1을 그대로 기록했다. 같은 UID 파일 교체 경쟁과 리뷰의 추가 회귀 2개는 후속으로 남긴다. TASK-016 실키/네트워크/실자료, TASK-017 운영 인증/인가/백업·시각/연구 평가는 미완료다. 상세 10 §27 참조.

### 최근 작업 기록 — 가이드 본문 일관성 정리 (2026-10-17)

사용자 요청으로 13개 가이드의 이전 기준 표시와 상단 공백을 정리했다. 01의 제공자/예산 승인 상태와 02의 STT/추출/검색 구현 표, 04의 실호출 상태를 코드에 맞췄다. 00에 최신 코드/검증 요약, 99에 다음 실행 순서와 완료 조건을 추가했다. 문서만 변경했으며 제품 테스트·정적 스캔·외부 호출은 재실행하지 않았다. 이번 문서 검증은 10 §28 참조.

### 최근 작업 기록 — descriptor 고정과 삭제 검증 (2026-10-17)

계속 진행 요청에 따라 TASK-015/017 파일 보호 후속을 수행했다. Linux 디렉터리/source descriptor를 고정해 검사 후 경로 교체를 보완했고 추가 회귀를 검증했다. API 19/Python 76, 타입 검사·빌드 통과. 브라우저/이미지 결과와 정적 점검 48건 실패는 10 §29에 기록한다. 별도 리뷰 중요 결함 없음; 클라이언트 중단 후 descriptor 닫힘의 직접 테스트는 후속이다. 실키/두 AI 도메인 허용이 없어 실호출은 하지 않았다.

### 최근 작업 기록 — 응답 중단 파일 정리 (2026-10-17)

실제 HTTP 응답 중단 후 descriptor 닫힘을 직접 검증했다. GC 정리가 명시적 close 누락을 가리지 않도록 테스트를 보강했고 close 제거 변이에서 실패→원복 후 통과했다. 범위를 벗어난 Range의 404를 416으로 수정했다. API 21/Python 76, 타입/빌드 통과 및 새 이미지 브라우저 결과는 10 §30에 기록한다. 별도 리뷰 중요 결함 없음. 유료 호출/운영 공개는 수행하지 않았다.

### 최근 작업 기록 — 최신 가이드 요약 동기화 (2026-10-17)

사용자 요청으로 13개 가이드 상단을 코드 5c3ebd5/10 §30 기준으로 정리했다. 00에 구현·102개 이전 테스트·정적48건 실패·실호출 대기·다음 작업을 한 표로 연결했다. 99에서 승인된 제공자/예산과 완료된 파일 보호 후속을 명확히 했다. 과거 이력은 보존했고 제품 코드·테스트·실환경 관측은 변경/재실행하지 않았다. 문서 검증은 10 §31 참조.

### 최근 작업 기록 — 남은 평가 준비 구현 (2026-10-17)

남은 작업 진행 요청에 따라 TASK-014/019 오프라인 판정 채점 도구·strict 데이터 계약·합성 예시·실행 안내를 추가했다. 원본 계열 분할/ID/manifest 해시, 누락/실패 분모와 고정 지표를 검증했다. 생산 판정/API/DB/UI·제공자/예산은 변경하지 않았다. Python89/API21 및 타입/빌드 검증, 별도 리뷰 중요 결함 없음. 브라우저/실AI·연구 평가/운영 배포는 이번에 검증하지 않았다. 상세는 10 §32 참조.

### 최근 작업 기록 — 전체 가이드 대조·순차 실행표 (2026-10-17)

사용자 요청에 따라 전체13개를 대조하고 00에 통합 실행표, 99에 TASK-020~026을 추가했다. 현재형 모순을 고치고 완료된 파일 보호/채점 준비는 반복하지 않는다. 이번 구현 순서는 주장 맥락→복수 원문 후보→실제 규칙 회귀이며, 이후 실자료/시각/종합/연구/운영 보호를 유지한다. 가이드 정리 커밋 후 같은 요청에서 순차 구현한다.

### 순차 실행 1/3 — TASK-020 (2026-10-17)

가이드 커밋97f05a6 후 주장 맥락/지원 정형 구조/규칙 버전·UI 원문 확인을 구현했다. 리뷰의 부정/하한 필드 우회도 재현 후 수정했고 Python97/API22/브라우저5·타입/빌드/Compose를 검증했다. 일반 문장/실자료 성능으로 주장하지 않으며 다음은 복수 후보 수집이다.

### 순차 실행 2/3 — TASK-021 (2026-10-17)

첫 빈 인용 뒤 후보 탐색·최대3 최종 원문 수집·중복 구조화 차단과 모델/프롬프트/검색 버전 전달을 구현했다. 예산/호출 오류 전파는 유지했다. Python102개 및 독립 리뷰를 확인했고 다음은 실제 생산 규칙 회귀 연결이다.

### 순차 실행 3/3 — TASK-022와 인계 (2026-10-17)

합성 입력에서 실제 생산 규칙을 실행하는 RULES 회귀·전체 입력/소스 해시와 실패 분모를 연결했다. Python111/API22/브라우저5·타입/빌드 및 별도 리뷰를 확인했고 컨테이너 RULES9개 일치까지10 §36에 기록했다. 사용자 요청대로 전체 가이드→020→021→022 순차 진행했고 다음은023 일반 원문 계약이다. 실AI/시각/연구/운영 전체 완료로 표시하지 않는다.

### 재개 환경·TASK-023 계약 점검 (2026-10-18)

원격 work 게시 직후388050d 복구, 최신 Secret ready/정책 enforced·Worker SDK 모델 목록 연결 확인. 로컬 승인 설정에는 비밀값을 기록하지 않았다. TASK023 일반 원문 계약1차/합성 유보8개를 고정했으며 생산 규칙은 유지했다. Python112/API22/브라우저5=139개, RULES9+8개·타입/빌드 통과. 정적49파일/51건(종료1)은 유지한다. 실미디어 분석·잔액/한도·Brave 계정 저장 권한·provenance/시각/연구/운영 전체는 미완료이며 상세는10 §37이다. 새 작업 공간/서브에이전트/원격 게시/배포를 만들지 않았다.

### 프로젝트 가이드 13개 동기화 (2026-10-18, TASK-010)

사용자 요청에 따라 13개 문서의 현재 요약·재개 순서·작업 표를 직전 실행 근거(10 §37)에 맞췄다. TASK-023의 계약/유보 회귀와 검증 구현 잔여, TASK-016의 환경/SDK 확인과 실제 분석 잔여를 구분했다. 과거 이력과 앞선 미커밋 구현/회귀 변경은 보존한다. 이번은 문서 갱신이며 제품 테스트/유료 API/정적 보안 스캔/배포는 재실행하지 않았다. 문서 검증은 10 §38에 기록한다.

### TASK-023 원문 관측 추적 구현 (2026-10-18)

기존 가이드/사용자 진행 지시에 따라 직접 구현했다. 수집/정규화 구조/발행정보 관측의 sourceTrace를 Validator·API·Vue 근거 화면까지 연결하고 legacy null을 유지한다. 새 규칙v3는 기존 숫자 문법/전체 맥락을 유지하며 인증되지 않은 traced source를 유보한다. 파서/경계·API·화면 실패를 재현한 뒤 구현했고 독립 코드 리뷰의 P1 중첩 HTML 성능 문제를 실패 테스트/단일 순회/한도로 수정했다. 최종Python133/API23/브라우저5=161개, 타입/빌드·RULES9+8 통과. 정적55건(종료1)은09/10에 분류했다. 실제 AI/일반 문서 신원·의미/계보·시각/연구/운영은 미완료다. 이전 미커밋 변경을 보존했으며 이번 원격 푸시/배포는 하지 않았다. 상세10 §39.

### 출처 등록 대조·관계 후보 및 가이드 브리핑 (2026-10-19)

사용자 진행 지시에 따라 TASK-023 source-review-v1/static-text-v2의 등록 대조/중복·명시 인용 관계 후보를 구현했다. 빈 trusted 등록 정책·legacy null/v1 호환·인증 미확인 유보를 유지했다. 독립 리뷰의 URL/포트/그룹 문제는 실패 테스트 후 수정했다. 이후 환경 재시작으로 DB 연결 거부를 확인해 개발 DB를 복구했고, 현재 Secret/network 상태unknown을 과거 ready와 구분해 가이드13개에 반영했다. 최신 검증/브리핑은10 §40이다. 실제 유료 호출·운영 배포/새 원격 반영은 하지 않았고 기존 미커밋 변경은 보존한다.


> 아래 내용은 원격 인계 당시의 이력이며 현재 상태는 상단과 최신 실행 기록을 따른다.

### 최근 작업 기록 — API 설정 인계와 GitHub 반영 (2026-10-18)

사용자는 OpenAI/Brave 키를 환경 Secret으로 등록하고 대상 도메인을 허용했다고 보고했다. 이전 채팅의 마지막 현재 관측은 secrets/runtime_variables 빈 목록, 네트워크 enforced이나 두 API 호스트 미허용이었다. 저장 설정과 실행 환경을 구분하며 새 환경에서 준비 상태부터 재확인한다. 실제 API 호출은 미실행이다. 사용자 요청으로 구현 커밋388050d를 origin/work에 push하고 원격 해시 일치를 확인했다. main 병합/제품 배포는 하지 않았다. 이번 문서 갱신은08/09/10 §37/99에 반영하며 기존 테스트 결과는 재실행 결과가 아니다.
