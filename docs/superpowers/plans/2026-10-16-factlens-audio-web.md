# FactLens Audio Web Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** MP4/MP3/WAV를 업로드하고 음성의 주장·근거·판정·한계를 시간 구간별로 확인하는 비공개 개발용 웹 PoC.

**Architecture:** Vue 웹 → Express API → PostgreSQL 작업 기록/Redis ID 큐 → Python Worker. 미디어 파일은 공유 비공개 볼륨에 두며 검색·전사·모델은 제공자 어댑터로 분리한다. DB의 조건부 상태 변경으로 실행/삭제 경합을 제어한다.

**Tech Stack:** Vue 3, TypeScript, Vite, Express 5, PostgreSQL 17, Redis 7, Python 3.12, FFmpeg, Docker Compose, Vitest, pytest, Playwright.

**Spec:** ../../01_시스템_개요.md §9 (2026-10-16 사용자 진행 지시로 첫 설계안 승인).

## Global Constraints

- 파일 100 MiB 이하, 길이 180초 이하, 동시 처리 1건, 작업당 검증 주장 최대 5개, 작업 실행 10분 상한.
- 원본/파생물/전사/결과는 비공개 보관. 개발용 자동 삭제 기본값 24시간과 수동 삭제 제공.
- 유료 호출은 제공자·건당/월 예산·외부 전송 동의가 준비되기 전 비활성화. 인증 부재를 성공 결과로 대체하지 않음.
- 음성만 검증함을 결과에 표시. OCR/영상 맥락 분석과 공개 배포는 후속 단계.
- 프로젝트 기본 checkout 사용. 기존 사용자 변경 보존. 운영 계정·비밀값·추론 내용을 저장하지 않음.
- 연구 성능은 TASK-014의 별도 프로토콜 고정 후 평가. 기능 테스트를 연구 성능으로 표시하지 않음.

## Review Focus

- 파일 확장자와 실제 컨테이너 불일치: AI 호출 전에 거부 (Task 2).
- 작업 중 삭제와 늦게 도착한 Worker 결과: 파일/결과 재생성 금지 (Task 3).
- 리디렉션 또는 DNS로 사설 주소에 도달하는 근거 URL: 각 연결에서 차단 (Task 4).
- 원문 인용은 있으나 다른 기간/대상의 수치: 확정 판정 금지 (Task 4).
- 제공자 미설정/일부 호출 실패: 오류/한계를 표시하고 테스트 자료로 대체하지 않음 (Task 5/6).

## 파일 구조와 공통 계약

- `apps/api/src/{app,config,db,uploads,jobs,media,cleanup}.ts`: HTTP·입력·작업 상태·파일 수명주기.
- `apps/api/migrations/001_initial.sql`: media, jobs, claims, evidence, checks, verdicts, usage_reservations 테이블.
- `apps/worker/factlens/{main,queue,media,contracts,pipeline,retrieval,validator,decision,budget}.py`: 큐 소비·미디어·어댑터·검증·판정.
- `apps/web/src/{App.vue,api.ts,types.ts,components/*}`: 업로드·상태·결과 탐색.
- `compose.yaml`, `docker/{api,worker,web}.Dockerfile`, `.env.example`: 비밀 없는 loopback 개발 실행.
- `tests/e2e/analysis.spec.ts`, 각 앱 `tests/`: 계약·통합·브라우저 검증.
- 작업 상태: queued → validating → transcribing → extracting → retrieving → validating_evidence → completed; 중간 단계에서 failed/cancelled 전이 가능. deleted는 모든 공개 조회/파일 제공에서 접근 거부하는 tombstone.
- `AnalysisView`: id, status, stage, createdAt, expiresAt, error(null 또는 code/message), scope='audio_only', claims[], limitations[], usage. 시간은 원본 기준 초(number), 날짜는 UTC ISO 8601.
- `Claim`: id, text, startSeconds, endSeconds, subject, period, metric, value, unit, eligibility, verdict, evidence[]. 필수 속성 누락은 null; 추정값을 채우지 않음.
- 근거 관계 SUPPORTED/REFUTED/INSUFFICIENT와 주장 판정 CONFIRMED/REFUTED/INSUFFICIENT/REVIEW_REQUIRED/EXCLUDED 분리. 근거 강도 HIGH/MEDIUM/LOW는 확률이 아님.
- 최초 UI는 주장별 개수와 범위 요약을 제공하고 단일 종합 진실 점수를 만들지 않음.
- HTTP 오류 `{error:{code,message,requestId}}`. upload 201, 분석 생성 202, 목록/상세 200, 삭제 204, 입력 400/413/415, 없음 404, 중복 충돌 409, 제한 429, 제공자 준비 안 됨 503.
- 업로드 반환 `mediaId`; 분석 생성은 `{mediaId,externalProcessingConsent:true}`. 서버가 생성한 미디어 ID와 고정 루트 내 경로만 사용. API 주소는 loopback, 운영 인증이 없는 버전의 공개 배포 금지.

### Task 1: 작업·근거 데이터 계약과 개발 실행 기반

**Files:** root package.json, tsconfig.json, compose.yaml, docker/*, .env.example; apps/api/src/{config,db}.ts; migrations/001_initial.sql; apps/worker/factlens/contracts.py; apps/api/tests/schema.test.ts; apps/worker/tests/test_contracts.py.

**Interfaces:** PostgreSQL `jobs(id,status,version,deleted_at,expires_at,...)`; `AnalysisView`와 `Claim`은 위 계약. Redis 키 `factlens:jobs`의 메시지는 UUID 문자열. 저장 실패 후 큐 전송되지 않은 queued 작업은 DB 스캐너로 복구.

- [ ] 계약 테스트 작성: startSeconds > endSeconds, 알 수 없는 enum, 누락된 근거 참조 거부; job/media FK와 중복 실행 소유권 제약 확인.
- [ ] `npm test --workspace apps/api -- schema` 및 `pytest apps/worker/tests/test_contracts.py` 실행해 구현 부재 실패 확인.
- [ ] 스키마·런타임 경계 검증·환경 설정·마이그레이션과 health/readiness 구현. DB/Redis/미디어 볼륨은 외부 포트 노출하지 않음. 사용량 정수 마이크로 통화 단위 저장.
- [ ] 위 테스트와 `docker compose config` 실행. 실제 DB 마이그레이션 및 재실행 검증.
- [ ] 관련 03/04/07/08/10/99 계약 기록 후 해당 파일만 커밋.

### Task 2: 비공개 업로드와 미디어 검증

**Files:** apps/api/src/{app,uploads,media}.ts; apps/worker/factlens/media.py; apps/api/tests/uploads.test.ts; apps/worker/tests/test_media.py.

**Interfaces:** `probe_media(path: Path, timeout_seconds: int) -> MediaInfo`; `extract_audio(path: Path, target: Path) -> None`. `POST /api/media/upload` multipart `file` 반환 `{mediaId}`; 외부 파일명은 경로로 사용하지 않음.

- [ ] 테스트: 100 MiB+1바이트 거부, 길이 180.001초 거부, 확장자/실제 형식 불일치 거부, 손상 파일 거부, 180초 경계 허용; 거부 시 외부 호출 0회·임시파일 삭제.
- [ ] `pytest apps/worker/tests/test_media.py`와 API upload 테스트 실행해 실패 확인.
- [ ] 스트리밍 바이트 상한·허용 MP4/MP3/WAV 실제 컨테이너 검사·ffprobe/ffmpeg subprocess timeout 구현. shell=False, 비루트 Worker, 읽기 전용 컨테이너 루트/제한 볼륨·CPU/메모리/PID·네트워크 프로토콜 제한 적용.
- [ ] 실제 FFmpeg로 생성한 짧은 각 형식의 미디어 통합 테스트 실행. `.exe.mp4`, 경로 구분자 파일명, 음성 없는 MP4, 잘린 파일도 거부 확인.
- [ ] 02/04/07/10/99에 실제 인수 조건과 결과 기록 후 커밋.

### Task 3: 작업 상태·큐·조회·취소 및 삭제

**Files:** apps/api/src/{jobs,cleanup,media}.ts; apps/worker/factlens/{main,queue}.py; apps/api/tests/jobs.test.ts; apps/worker/tests/test_queue.py.

**Interfaces:** `claim_job(job_id: UUID) -> Job | None`, `complete_job(job_id: UUID, expected_version: int, result: AnalysisView) -> bool`. API는 가이드의 분석/주장/근거/타임라인/보고서/삭제 8개 경로를 구현; media 스트리밍은 등록된 ID만 허용하고 Range 요청 지원.

- [ ] 테스트: 큐 메시지 2회에도 실행 1회, DB commit 후 enqueue 실패 복구, 삭제 후 완료 결과 저장 거부, queued/running 삭제에서 파일·파생물 제거, 24시간 만료 조회 거부.
- [ ] API/Worker 작업 테스트 실행해 실패 확인.
- [ ] DB 조건부 상태 갱신·실행 lease·단일 소비자·10분 watchdog·삭제 tombstone·정리 루프 구현. 상태별 재시도는 삭제/만료 확인 후 수행하고 제한시간/예산 누적 유지. AI 단계 자동 재시도는 최초 버전에서 비활성화.
- [ ] 실제 PostgreSQL/Redis 통합 테스트 및 Worker 강제 중지 후 복구/삭제 테스트 실행. API 요청 중복은 Idempotency-Key를 자원과 결합해 처리.
- [ ] 03/04/05/08/10/99 갱신 후 커밋.

### Task 4: 원문 검증과 판정 규칙

**Files:** apps/worker/factlens/{retrieval,validator,decision}.py; apps/worker/tests/{test_retrieval,test_validator,test_decision}.py.

**Interfaces:** `fetch_evidence(url: str) -> EvidenceDocument`, `validate_evidence(claim: Claim, document: EvidenceDocument) -> EvidenceCheck`, `decide(claim: Claim, checks: list[EvidenceCheck]) -> Verdict`.

- [ ] 고정 자료 테스트: 동일 기간/대상/단위의 5%와 주장 50%는 REFUTED 후보; 기간/분모 불일치·인용 부재·미접근은 확정 금지; 지지/반박 직접 근거 충돌은 REVIEW_REQUIRED; 의견은 EXCLUDED; 근거 없음은 INSUFFICIENT.
- [ ] 위 pytest 실행해 실패 확인.
- [ ] 공개 HTTP(S) 수집에 각 hop·실제 연결 IP 검사, DNS rebinding 방지, TLS 검증, 제한 리디렉션/바이트/시간 구현. localhost/사설/링크로컬/메타데이터 및 Tailscale 주소 거부. 검증 가능한 HTML/text 근거만 허용하고 미지원 원문은 제한 표시.
- [ ] 원문 인용 exact match와 위치, 발행 정보/기간/대상/통계 정의/단위/출처 계보 검사 구현. 비교 속성 누락과 오차 미정은 유보. 수치 연산은 Decimal, 모델 단독 판단으로 검사 통과 금지.
- [ ] 리디렉션 사설 주소·DNS 교체·중복 출처·반올림 불명·퍼센트포인트 혼동 테스트 추가 후 전체 관련 pytest 통과 확인.
- [ ] 02/03/05/07/09/10/99에 판정 계약과 잔여 한계 기록 후 커밋.

### Task 5: 제공자 어댑터와 음성 분석 파이프라인

**Files:** apps/worker/factlens/{pipeline,budget,providers}.py; apps/worker/tests/{test_pipeline,test_budget}.py; .env.example.

**Interfaces:** `Transcriber.transcribe(path: Path) -> list[Segment]`, `ClaimExtractor.extract(segments: list[Segment]) -> list[Claim]`, `Retriever.search(claim: Claim) -> list[EvidenceCandidate]`, `run_analysis(job: Job, providers: Providers) -> AnalysisView`. 제공자 호출 전 `reserve_usage(job_id, max_cost_micros)`가 원자적으로 월/건 한도 확인.

- [ ] 테스트: 미설정은 PROVIDER_NOT_CONFIGURED, 동의 없음은 외부 호출 0회, 주장 5개 초과 절단/한계 표시, timeout/잘못된 JSON은 실패/불확실성 보존, 지출 예약 경쟁 시 한도 초과 거부.
- [ ] pipeline/budget pytest 실행해 실패 확인.
- [ ] 우선 어댑터 계약·명시적 disabled 제공자·테스트 전용 fixture 제공자와 실제 제공자 설정 경계를 구현. fixture 제공자는 테스트/명시적 데모에서만 활성화하고 응답에 demo=true 및 UI 데모 배지 필수. 일반 분석 요청에서 fixture fallback 금지.
- [ ] 유료 제공자·정확한 모델·검색 API·가격 기준이 정해지면 SDK 연결, 타임스탬프 지원·스키마 검증·사용량/예약 해제/실패 호출 정산·10분 전체 예산 검증 추가. 미설정일 때는 이 단계 실제 연결 검증 미완료로 남김.
- [ ] 고정 자료 통합 테스트 통과; 실제 미디어 제공자 smoke는 인증/예산/동의 준비 후만 실행. 결과를 연구 성능으로 보고하지 않음.
- [ ] 07/08/09/10/99에 연결 상태와 남은 설정 기록 후 커밋.

### Task 6: 업로드·진행·시간축 근거 보고서 웹과 전체 검증

**Files:** apps/web/{package.json,index.html,vite.config.ts}; apps/web/src/{main.ts,App.vue,api.ts,types.ts,style.css,components/UploadPanel.vue,components/AnalysisProgress.vue,components/AnalysisReport.vue,components/EvidencePanel.vue}; tests/e2e/analysis.spec.ts; README.md.

**Interfaces:** API 클라이언트 `upload(file: File): Promise<{mediaId:string}>`, `createAnalysis(mediaId: string, consent: boolean): Promise<{id:string}>`, `getAnalysis(id: string): Promise<AnalysisView>`, `deleteAnalysis(id: string): Promise<void>`; 모든 예외는 code/message 유지.

- [ ] 브라우저 테스트: 업로드→진행→시간 구간 선택→재생 위치/근거 연결, 음성 파일 UI, 삭제 후 결과 접근 불가, 미설정 제공자 안내, 데모 결과 배지, 네트워크 오류 복구. 비신뢰 근거 HTML을 문자로 표시하는 테스트 포함.
- [ ] `npx playwright test tests/e2e/analysis.spec.ts` 실행해 실패 확인.
- [ ] 한국어 반응형 UI·단계명 상태·타임라인·주장/근거 비교·접근 가능한 입력/오류·처리 취소/삭제·인증 전 비공개 안내 구현. 진실 확률/가짜 통계/가짜 진행률은 표시하지 않음. API는 동일 origin reverse proxy 사용.
- [ ] `npm run typecheck`, `npm test`, `pytest apps/worker/tests`, `npm run build`, 실제 Compose E2E 실행. 키보드/모바일 레이아웃·재생 Range·삭제·프로세스 복구 검증.
- [ ] README 실행 절차와 env 이름, 06/08의 실제 구조·실행/중지/복구, 10의 파일 ID/검증 및 99의 완료/미완료를 갱신. AWS/Cloudflare/Tailscale 연결은 준비된 접근권한으로 별도 검증 전 미완료 유지.
- [ ] 변경 범위 리뷰와 `git diff --check` 후 커밋. 원격 push/공개 배포는 별도 사용자 지시 범위에 따름.

## 자체 검토와 실행 인계

- 설계 §9의 입력·큐·근거·판정·UI·삭제·비용·보호·검증은 Task 1~6에 연결했다.
- 실제 제공자·예산과 운영 접근은 미확정이다. 개발용 경로와 테스트는 구현 가능하지만 실제 AI 분석/배포 완료 주장 조건은 충족되지 않는다.
- 사용자 계획 검토 후 같은 세션에서 직접 순차 구현을 추천한다. 밀접한 공통 데이터 계약을 공유하므로 서브에이전트는 기본 사용하지 않는다.

## 실행 상태 (2026-10-16)

- Task 1~4 및 Task 6의 개발용 기반을 구현했다. 실제 PostgreSQL/Redis/FFmpeg/브라우저/Compose 실행 기록은 프로젝트 가이드 10의 최신 검증 절을 따른다.
- Task 5는 disabled 제공자 경계·테스트 주입·최대 주장·시간 경계·비용 예약까지 구현했다. 실제 유료 제공자 선택/SDK 어댑터/청구 정산 결합/실제 추론 smoke는 미완료다.
- 직접 구현 후 별도 코드 리뷰에서 MOV 확장자 위장, 원문 정정 맥락을 숨기는 잘린 인용, 늦은 polling 응답의 화면 복원 문제를 확인해 각각 실패 재현 테스트 후 수정했다.
- 기존 단계 체크박스는 미실행된 세부 검증까지 통과로 바꾸지 않도록 보존한다. 운영 배포/인증/백업·연구 성능 평가는 별도 잔여 작업이다.

### Task 5 후속 (2026-10-16)

- metered.py의 제공자 공통 호출 예약/정산 경계와 pipeline의 usage 전달을 추가했다. 실제 SDK 선택·상한 산정·실사용 청구 검증은 아직 없다. 기본 Worker는 유료 호출을 활성화하지 않는다. 검증 기록은 10 §24 참조.
