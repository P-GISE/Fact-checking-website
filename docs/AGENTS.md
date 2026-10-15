# 프로젝트 가이드 — 공통 지침 (AGENTS.md)

## 작업 시작·종료 규칙

사용자가 말하는 **프로젝트 가이드**는 저장소 `docs/` 폴더의 `AGENTS.md`와 아래 번호 문서 12개를 합친 **전체 13개 문서 세트**를 뜻한다. 개별 문서는 파일명 또는 역할로 구분하며 기존 파일명은 유지한다.

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
- 현재 상태: 기획 기준 자료와 개발 도구·문서만 존재한다. 아래 파이프라인·API·DB·화면은 **기획 요구 또는 제안이며 제품 구현·성능 검증은 아직 없다**. 원문 반영을 모든 기술 선택에 대한 승인으로 간주하지 않는다.

### 범위와 진행 순서

- 입력: 최종 MVP의 필수 입력은 MP4 및 MP3/WAV 직접 업로드다. 초기 평가 대상은 1~3분 한국어 뉴스형 영상이다. 이는 기획상 목표이며 파일 크기·최대 길이의 확정 제한값은 별도 결정한다.
- 지원 영상 URL·기사 URL·YouTube 등은 확장 범위다. 초기 업로드 경로보다 먼저 만들지 않으며 플랫폼 정책·접근 권한을 확인한다. 다국어·실시간 방송·일괄 처리·팀 검토·API 상품화·C2PA도 후속 제안이다.
- 기획 단계: 음성 팩트체크 PoC → 자막/화면 PoC → 근거 Validator·교차검증·판정 규칙 PoC → 웹 MVP와 비교 평가. 최종 MVP의 필수 항목을 단계 축소 과정에서 조용히 제외하지 않는다.
- 우선 기준 문서: [01 시스템 개요](01_시스템_개요.md), [02 기능 설계](02_기능_설계.md), [05 업무 플로우](05_업무_플로우.md). 다음 작업은 `99_해야할일..md`의 TASK-001 잔여 범위 정리다. 이미 제공된 프로젝트 목적을 다시 처음부터 묻지 않는다.

### 분석과 판정의 필수 원칙

1. 음성 전사·자막/OCR·영상 프레임을 독립 처리하고 원본 타임스탬프·발화/자막 출처에 연결한다. 검증 가능한 원자적 주장과 의견·예측 등을 구분한다.
2. 근거 검색과 근거 검증(Evidence Validator)을 분리한다. URL 접근 가능만으로 신뢰를 인정하지 않는다. 원문 인용 위치, 발행 주체, 날짜/기간, 대상/지역, 수치/단위/분모, 맥락, 출처 독립성을 검증한다.
3. 음성·자막·영상의 내부 일치와 외부 사실성은 별개 결과다. 여러 Agent의 합의·공식 기관 이름·이미지 유사성만으로 사실 또는 최초 원본을 확정하지 않는다. 게시일과 촬영일을 구분한다.
4. 근거 없음·접근 실패·원문 인용 검증 실패·원본 영상 미발견은 거짓의 근거가 아니다. 불충분/충돌/처리 오류를 구분하고 판정을 유보한다. LLM의 단독 응답 대신 검증된 근거와 버전 관리한 규칙으로 최종 판정한다.
5. 근거 관계는 `SUPPORTED / REFUTED / INSUFFICIENT`, 주장 판정은 `근거로 확인됨 / 반박됨 / 검증 불충분 / 검토 필요 / 검증 대상 제외`로 구분한다. 종합 판정·작업 처리 상태·근거 강도를 같은 enum으로 합치지 않는다.
6. 근거 강도 `높음/보통/낮음`은 진실 확률이 아니다. 보정 실험 없이 0~100% 진실 점수를 표시하지 않는다. ‘허위 주장 확인’은 반박된 핵심 주장 범위로 한정한다.
7. 주장·프레임·타임스탬프·근거 원문/위치·출처/발행일·검사 결과·판정 이유·불확실성·모델/프롬프트/규칙 버전을 추적한다. Agent 간 입출력은 스키마로 검증하며 내부 비공개 추론을 사용자 설명의 필수 산출물로 요구하지 않는다.

### 제안 스택과 미결정 항목

원문 제안은 Vue 3 + TypeScript + Vite, Node.js API(Express **또는** NestJS), Python + FastAPI AI Worker, PostgreSQL, Redis/작업 큐, 로컬 **또는** S3 호환 스토리지, FFmpeg/OpenCV/PaddleOCR, OpenAI API, Google Fact Check Tools API·Cloud Vision Web Detection, Docker다. 이는 검토 기준이며 설치·계약·제공자 인증·호환성은 미검증이다. `DEC-002`에서 대안과 PoC 비용을 비교해 구체화한다. Redis 큐 라이브러리·인증 방식·배포처·API 스키마·삭제/보관 기간은 미결정이다.

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
- 저장소 상태: 2026-10-15 GitHub 반영 전 확인한 원격 main은 `24a4428`(README만 존재)이었다. 사용자 요청에 따라 프로젝트 가이드·원문·참조 개발 도구/설정을 커밋하여 main에 반영한다. 푸시 결과는 실제 원격 커밋 대조로 확인하며 환경 게시/제품 배포와 구분한다.

## 현재 개발 환경

This repository currently has no application implementation. Do not interpret an empty index or a no-findings report as validation of a website.

Read `devtools/README.ko.md` for the installed tools and limitations. Run `bash devtools/install.sh` to refresh development tools, then `source devtools/activate.sh`. Tools and upstream source caches are retained under `/workspace/.devtools`, outside this checkout. Each cloud task is already isolated; use this checkout and do not create Git worktrees unless the user requests one.

## Workflow

- Use Superpowers for development workflow when applicable. It is already available as a session plugin here; project copies support future sessions that lack that plugin. Do not run duplicate workflow copies for the same task.
- Use PM Skills for product discovery, strategy, PRDs, prioritization, and delivery planning when relevant.
- Use Ponytail for explicit simplicity/review requests. Use LazyCodex skills for explicit LazyCodex planning/execution requests. Choose one lead workflow per task; do not stack competing autonomous loops.
- Use CodeGraph for code navigation after source files exist; use normal file tools when the graph is empty.
- Use Iron Laws for offline static security and quality checks. Preserve its exit code and report coverage limits.
- Use Strix only against user-authorized targets. It needs an LLM provider and Docker for local scans. No live scan has been validated in this empty repository.
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
