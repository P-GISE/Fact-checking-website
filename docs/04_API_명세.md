# 04. API 명세

> **최신 GTV 추출 수정 · 2026-10-21:** 원문에 없는 사건 metric/다른 구간 subject를 만드는 원인을 재현하고 생성 스키마 설명·프롬프트v4를 수정했다. 저장 전사 재생에서 GTV 유효 주장2개가 검색·검증·보고서까지 완료됐지만 유효 근거0으로 모두 INSUFFICIENT다. 실업률2.8 확인/2.9 반박·각 유효 근거2개를 유지했다. 원문 검증v2/전부 무효 실패 방어·운영 모델/예산은 유지한다. 안전 대담 전부 무효와 한국어 ASR/잡음/시간 정렬은 남는다. 새 ASR·공개 회원 업로드 재시험과 구분하며 [최신 추출 보고서](reports/2026-10-21-gtv-extraction.md)의 CI·배포 확정 상태를 우선한다. 아래 기록은 당시 이력이다.

> **추가 승인 모델 비교 · 2026-10-21:** 사용자 승인으로 gpt-transcribe를 격리 비교했다. 같은 입력에서 억원/회수/엘니뇨·대류·고기압은 개선됐지만 연도/문장 누락과 잡음 구간의 힌트 문구 혼입이 남았다. 운영 whisper-1·gpt-4.1-mini·Brave/비용 한도는 유지하며, 새 모델에 없는 구간 시간을 만들거나 운영 판정에 연결하지 않았다. 뉴스 직접 조사·실행별 비용/실패/정리·한계는 [모델 비교 보고서](reports/2026-10-21-transcription-model-comparison.md)를 우선한다. 아래 새 모델 승인 대기 기록은 해소된 이력이다.

> **실제 한국어 자료 진단 · 2026-10-21:** 실제 낭독8개/서로 다른 화자8명·정부 브리핑45초·안전 대담40초로 전사/추출/판정을 진단했다. 정상 주장까지 버리는 후보 처리와 마지막 시간0.12초 초과 중단을 수정했다. 실제 ASR 단위/명사/문장 누락·모두 무효 후보는 남아 있으며 일반 방송사 뉴스/대표성 있는 정확도 평가 완료가 아니다. 공개AI openai_brave/기존 모델·$0.20/건·$20/월 유지. 최종 코드·배포·기존 판정 회귀·비용·남은 일은 [실자료 진단 보고서](reports/2026-10-21-real-korean-diagnostics.md)를 우선한다. 아래 기록은 당시 이력이다.

> **최신 실검증 · 2026-10-21:** 실업률→실험률 전사 오인식을 진단하고 수치 없는 고용 통계 용어 힌트로 개선했다. 운영34ae4fa/공개AI openai_brave, 건당$0.20·월$20 유지. 공개 회원 업로드→보고서에서2.8% 확인/2.9% 반박·각 유효 공식근거2개·삭제404/물리 정리·탈퇴 확인. CI API97/Worker393 통과. 아래 disabled/429/근거0 대기는 이전 기록이며 [최신 실검증 보고서](reports/2026-10-21-public-live-verification.md)를 우선한다. 일반 정확도 검증은 아니다.

> **실AI·검토 근거 판정 · 2026-10-21:** Evidence의 선택적 meaningReview와 summary.reviewedEvidence를 추가하고 기존 결과는 null로 호환한다. 정책·문서 해시·관계·Unicode 인용 위치/길이를 검증하며 거짓 검토 표기는 거부한다. 신규 PROVIDER_QUOTA_EXCEEDED는 제공자가 명시한 잔액/조직·프로젝트 사용 제한을 일반429와 구분한다. 이번 실호출의 구체적429 원인은 아직 미확인이다. 상세 [진행 보고서](reports/2026-10-21-evidence-verdict.md).

## 최신 입력 오류·인증 실행 제한 (2026-10-20, TASK031)

업로드의 잘못된 파일 필드·초과 파일/텍스트 필드는400 INVALID_UPLOAD다. JSON 구문 오류는400 INVALID_INPUT, JSON32KiB/파일100MiB 초과는413 SIZE_LIMIT다. 본문·파일명·파서 원시 오류를 응답에 포함하지 않는다. 그 외 예상치 못한 서버 오류는 기존500 INTERNAL_ERROR다.

인증 전역 동시 실행4개와 IP별 분당20회 제한을 구분한다. 연결 종료는 이미 시작한 해시/DB 작업의 종료가 아니므로 제한 슬롯은 실제 인증 핸들러 종료에 맞춰 반환한다. 검증/배포 결과는10 §70을 따른다.

> **관리자 생성 통합 검증 · 2026-10-19 (10 §60):** 별도 운영 Compose에서 실제 CLI 관리자 생성·중복 거부·보안 쿠키·관리자200/회원403/로그아웃401을 확인했다. Python211/API52/브라우저14개 고유 사례 검증. 실제 Lightsail 반영은 미완료이며 다음은 검증된 변경의 게시·서버 적용/공개 회귀다.

> **탈퇴·복구 보호 구현 · 2026-10-19 (10 §59):** 재인증·확인 기반 탈퇴, 작업/업로드 진행 중 차단·대기 작업 폐기·파일 정리·비용 보존을 구현했다. 복원 계정은 모두 비활성화한다. 실제 운영 적용/관리자 생성 통합 검증은 남아 있다.

> **계정 변경 구현 · 2026-10-19 (10 §58):** 내 계정 조회·이름/비밀번호 변경·현재 비밀번호 재확인·성공 시 전체 세션 폐기를 구현했다. API49개·계정/관리자 브라우저5개·타입/빌드 통과. 실패 시 롤백하며 운영 서버 적용/탈퇴/관리자 생성 통합 검증은 남아 있다.

> **운영 목록 개선 · 2026-10-19 (10 §57):** 관리자 목록의 작업 ID 앞부분 검색·상태 필터·페이지 이동·빈 결과/조회 상태를 구현했다. API46개·계정/관리자 브라우저4개·타입/빌드 통과. 실제 관리자 생성·공개 배포, 계정 수정/탈퇴와 최종 보안 검토는 남아 있다.

> **관리자 인증 구현 · 2026-10-19 (10 §56):** 관리자 API를 계정 세션·DB 역할 검사로 전환하고 토큰 입력/Bearer 인증을 제거했다. 서버 전용 신규 관리자 생성 도구를 추가했다. API45개·계정/관리자 브라우저3개·타입/빌드 통과. 실서버 관리자 생성·배포, 운영 목록 개선·계정 수정/탈퇴는 미완료다.

> **계정 개선 1차 · 2026-10-19 (10 §55):** 가입/로그인 화면 분리·확인 비밀번호·표시 전환·폼 검증을 구현했다. 타입/빌드와 격리 계정 브라우저2개 통과. 관리자 계정/CRUD/운영 화면은 계획의 다음 단계이며 운영 서버에는 아직 적용하지 않았다.

> **관리자 방식 확정 · 2026-10-19 (10 §54):** 관리자는 관리자 계정으로 로그인하고 서버가 역할을 확인한다. 최초 관리자는 서버 전용 명령으로 생성하며 일반 가입으로 관리자 권한을 부여하지 않는다. TASK-029에 운영 화면 개선·토큰 입력 제거·권한 회귀를 등록했다. 현재 제품은 아직 Bearer 토큰 방식이며 아래 계정 기반 방식은 구현 예정이다.

> **최신 상태 · 2026-10-19 (10 §53):** 사용자 서버 출력으로 Lightsail 전용 서버의 운영 Compose·Cloudflare 공개 HTTPS health200을 확인했고 사용자가 사이트 접속 성공을 확인했다. AI는 비활성화다. 사용자 피드백에 따라 계정 CRUD·가입/로그인 사용성 개선을 TASK-028 최우선 후속으로 등록했다. 아래 과거 미배포 기록은 당시 이력이며 현재는 공개 연결 확인/계정 기능 실운영 검증 미완료를 구분한다.


> **현재 작업 기준 · 2026-10-19:** 근거에 sourceReview|null, sourceTrace에 bounded sourceLinks/sourceLinksComplete를 추가했다. parser v1/v2와 과거 결과 null을 수용한다. identity는 등록 대조 상태이며 independence는 unverified만 허용한다. 기존 경로/인가 한계는 유지한다.

- 현재 상태 갱신: 2026-10-19 (Asia/Seoul)
- 문서 상태: 검토 중 — 개발용 API 구현, 운영 인증/공통 계약 후속
- 제품 구현: 개발용 업로드·작업·조회·삭제 API 구현; 실제 AI SDK 구현·모델 목록 연결 확인·실분석 미검증
- 관련: [기능](02_기능_설계.md), [DB](03_데이터베이스_설계.md), [프런트엔드](06_프런트엔드_구조.md), [백엔드](07_백엔드_구조.md)

> **이전 기준 · 2026-10-16 (이력):** 8개 핵심 API와 목록/미디어/health를 개발용으로 구현. Origin 제한은 사용자 인증을 대체하지 않으며 운영 공개 금지다. 과거 작업 기록은 당시 이력으로 보존한다.

순차 실행 기준: [00 통합 실행 순서](00_문서_가이드.md#통합-실행-순서). 현재 구현과 과거 이력을 구분하며 이번 결과는 10의 최신 기록을 따른다.

## 제품 API 경로 — 개발용 구현

근거: [기획서 원문](../references/FactLens_AI_기획서_원문.md) 10.3절. 아래 8개 경로를 개발용으로 구현했다. 외부 AI 어댑터는 구현됐으나 실자료 결과 생성은 미검증이며 기본 모드는 disabled다. 현재 실행 계약은 §7과 최신 제공자 연결 기록을 따른다.

| ID | 메서드·경로 | 역할 | 연결 기능 |
|---|---|---|---|
| API-001 | `POST /api/analyses` | 비동기 분석 요청 | FEAT-001 |
| API-002 | `POST /api/media/upload` | MP4/MP3/WAV 업로드 | FEAT-001 |
| API-003 | `GET /api/analyses/:id` | 진행 상태·결과 조회 | FEAT-009 |
| API-004 | `GET /api/analyses/:id/claims` | 주장 목록 | FEAT-003/009 |
| API-005 | `GET /api/claims/:id/evidence` | 주장별 근거 | FEAT-004/005/009 |
| API-006 | `GET /api/analyses/:id/timeline` | 시간 구간별 검증 결과 | FEAT-007/009 |
| API-007 | `GET /api/analyses/:id/report` | 종합 보고서 | FEAT-008/009 |
| API-008 | `DELETE /api/analyses/:id` | 분석 데이터 삭제 | FEAT-010 |

개발용 파일 전송·작업 생성·JSON/오류·멱등 키·조회/삭제 계약은 §7과 코드에 있다. 운영 인증/인가·사용자별 목록·재분석/취소·버전 호환 계약은 후속이다. 삭제 API 존재만으로 모든 복제본과 외부 제공자 데이터가 삭제된다고 약속하지 않는다. URL 입력은 확장 범위이며 필수 body 필드로 고정하지 않는다.

## 1. 현재 API 구분

개발용 제품 API는 apps/api/src/app.ts에 구현돼 있다. Compose의 /api 경로는 http://127.0.0.1:8080/api에서 접근한다. 운영 base URL은 없다. 원문에 제안된 경로는 아래 초안 계약 목록에 분리해 기록한다. 아래는 기존 개발 도구의 내부 상태 점검 경로이며 제품 계약이 아니다.

| 소유 도구 | 내부 경로 | 확인 용도 | 근거 |
|---|---|---|---|
| OmniRoute | 포트 20128, `/api/health` | 도구 서비스 상태 | devtools/start-services.py |
| Headroom | 포트 8787, `/health` | 도구 프록시 `ready` 상태 | devtools/start-services.py |

이 경로를 제품 `/health` 또는 제품 API 구현으로 집계하지 않는다.

## 2. 공통 계약 — 결정할 항목

| 항목 | 결정 내용 | 현재 상태 |
|---|---|---|
| 통신 방식·버전·base path | 사용자 흐름과 배포 구조에 맞춰 선택 | 개발용 HTTP /api 구현; 운영 버전 후속 |
| 인증·인가 | 인증 수단, 자원 소유권, 역할별 접근 | loopback/Origin 제한만 구현; 사용자 인증/인가 미구현 |
| 직렬화 | 필드 표기, 시간/날짜/시간대, null, 식별자 | JSON/camelCase·UUID·UTC 날짜·초 단위 시간 구현 |
| 오류 | 공통 오류 구조, 상태 코드, 사용자 메시지, 추적 ID | error.code/message/requestId와 HTTP 오류 구현; 운영 메시지 후속 |
| 목록 | 필터·정렬·페이지네이션·최대 개수 | 최근 50건 구현; 사용자별 페이지/필터 후속 |
| 중복·동시 요청 | 멱등성, 충돌 탐지, 재시도 조건 | Idempotency-Key·DB 상태/version 구현; 재분석/취소 후속 |
| 제한 | 요청 크기, 타임아웃, 호출량, 비용 한도 | 파일 100 MiB·180초·동시 1건·600초; 승인 USD 월$20·건당$0.20; 실청구 검증 후속 |

## 3. 엔드포인트 목록 양식

| ID | 목적 | 메서드/경로 | 인증/권한 | 입력 | 성공 응답 | 오류 | 관련 ID | 상태 |
|---|---|---|---|---|---|---|---|---|
| API-NNN (양식) | 사용자 행동 | 결정 후 작성 | 공개 여부 포함 | 스키마 참조 | 코드·스키마 | 코드·조건 | FEAT-/FLOW-/BE- | 초안 |

## 4. 엔드포인트 상세 양식

1. 계약 ID·기능·소유 모듈.
2. path/query/header/body 필드별 타입·필수·제약·기본값.
3. 인증 및 자원 단위 인가 조건.
4. 성공·실패 응답의 정확한 코드와 JSON 등 선택한 형식의 예시.
5. 데이터가 없음/잘못된 입력/권한 없음/충돌/외부 장애의 구분.
6. 업무 상태와 트랜잭션 경계, 중복 요청 시 결과.
7. 호출 예시와 계약 테스트 경로. 예시 인증은 자리 표시자만 사용.
8. 호환성, 변경 이력, 폐기 또는 버전 전환 계획.

## 5. 완료 기준과 다음 작업

필수 흐름이 호출하는 모든 계약에 정상·오류·권한 사례가 있어야 한다. 명세와 구현 비교 및 필요한 계약 테스트 결과를 기록한다. API 명세 형식(OpenAPI 등)은 스택 선정 후 결정한다.

다음: [TASK-004](99_해야할일..md). 계약 변경 시 02/03/05/06/07의 영향을 검토한다.

## 문서별 작업 절차

- 연결 작업: TASK-004 / TASK-013 / TASK-015.
- 시작 자료: [02 기능](02_기능_설계.md), [03 데이터](03_데이터베이스_설계.md), [05 흐름](05_업무_플로우.md).
- 작성 순서: 공통 오류·인증·시간/ID 형식·제한부터 정한다. API별 요청/응답 스키마와 정상·오류·권한 예시를 작성한다. 업로드→작업 생성 연결, 중복·취소·재시도·부분 실패 계약을 확인한다.
- 인계 조건: [06 프런트엔드](06_프런트엔드_구조.md)와 [07 백엔드](07_백엔드_구조.md)가 같은 스키마를 사용하도록 연결하고 계약 테스트 위치를 정한다. 초안 URL은 실행 가능한 API로 표시하지 않는다.
- 공통 기록: 상태·근거·미결정·검증은 [00 문서 가이드](00_문서_가이드.md)의 표기 규칙을 따른다.

## 6. 기획서 API별 정보 책임과 미결정 계약

근거: [원문](../references/FactLens_AI_기획서_원문.md) 04·07.6·10.3·11·15절. 기존 8개 경로를 유지한다. 아래는 전달 정보의 요구이며 JSON 키·HTTP 코드·페이지/이벤트 스키마는 TASK-004에서 정한다.

| API | 제공/검증해야 할 정보 | 연결 | 남은 계약 |
|---|---|---|---|
| API-001 | 분석 대상 참조·분석 설정·작업 식별 정보 | FEAT-001, DB-001/002 | 업로드 선후관계·중복 요청·생성 실패 |
| API-002 | 직접 파일 업로드와 검증 결과 | FEAT-001, DB-002 | 전송 방식·형식/크기/길이·저장 참조·권한 |
| API-003 | 분석 단계·진행/오류·결과 가용 범위 | FEAT-009, DB-001 | 진행률 계산·부분 결과·조회/푸시·취소 정책 |
| API-004 | 원문/정규화 주장·시간 구간·출처·대상 여부 | FEAT-003/009, DB-003 | 목록/정렬·제외 이유·인식 불확실성 |
| API-005 | 근거 원문/위치/URL·발행 정보·검사·관계 | FEAT-004/005, DB-004/005 | 접근 실패 표시·원문 사본 노출 범위 |
| API-006 | 주장/모달 불일치의 유형·시작/종료 구간 | FEAT-007/009, DB-003/006 | 시간 단위·플레이어 연결·음성 전용 형태 |
| API-007 | 주장/종합 판정·근거 강도·이유·한계·버전 | FEAT-008/009, DB-007 | 복합 판정·보고서 형식·재분석 버전 |
| API-008 | 권한을 확인한 삭제 요청과 결과 | FEAT-010, DB-001~008 | 실행 중 취소·파생물/백업·완료 확인·멱등성 |

작업 오류, 근거 부족, 근거 충돌, 음성 파일의 시각 분석 해당 없음은 다른 의미로 표현한다. 분석 처리 완료를 사실 확인 성공으로 응답하지 않는다. 상세 오류/판정 스키마는 02/03/05/07과 함께 정한다.

지원 URL은 확장 요구이며 현재 필수 요청 필드로 만들지 않는다. 소유권·권한 없는 분석/미디어 접근의 거부 사례는 모든 자원 API 계약에서 검토한다.

## 7. 개발용 실행 계약 (2026-10-16)

- 구현: 기존 API-001~008 및 GET /api/analyses(최근 50건), GET /api/media/:id(Range 재생), GET /api/health. 운영 인증 없는 loopback 전용이며 동일 origin 및 허용된 localhost Origin만 허용한다.
- POST /api/media/upload: multipart file → 201 {mediaId}. POST /api/analyses: {mediaId,externalProcessingConsent:true}, 선택 Idempotency-Key → 202 {id}. 동일 미디어는 같은 작업을 반환한다. 재분석은 새 업로드다.
- 조회는 JSON AnalysisView(scope=audio_only, demo, status/stage, timestamps, claims, limitations, usage, error), 삭제 성공 204. 삭제/만료 조회 404, UUID/동의 오류 400, 크기 413, 확장자 415, 자원 충돌 409, 예상치 못한 오류 500.
- 실제 컨테이너/길이 검사는 비동기 Worker에서 수행한다. 제공자 미설정은 작업 failed/error.code=PROVIDER_NOT_CONFIGURED이며 API 자체 연결 실패와 구분한다.
- 정확한 타입과 오류 경계는 apps/api/src/contracts.ts·app.ts, Python 경계는 contracts.py. OpenAPI 및 운영 인증은 후속이다.

## 승인된 실제 제공자 연결 후속 (2026-10-16)

작업 실패 errorCode에 BUDGET_EXCEEDED, BILLING_REVIEW_REQUIRED, PROVIDER_AUTH_FAILED, PROVIDER_RATE_LIMITED, PROVIDER_MODEL_UNAVAILABLE, PROVIDER_INPUT_LIMIT, PROVIDER_RESPONSE_INVALID, PROVIDER_REQUEST_FAILED, PROVIDER_SEARCH_LIMIT를 연결했다. 작업 조회의 failed 상태이며 업로드 HTTP 응답과 구분한다. SDK 예외 원문·인증 키는 응답에 포함하지 않는다. health의 providerConfigured=false는 아직 준비 상태를 동적으로 확인하지 않는 보수적인 표시다.

## 2026-10-17 후속 구현 상태

GET /api/media/:id는 정상 Range(206)를 유지한다. DB 경로가 해당 UUID 디렉터리의 source 파일과 다르거나 realpath 경계를 벗어나면 404 NOT_FOUND로 거부한다. DELETE 분석의 실제 파일 삭제 경로도 UUID 검증을 통과해야 한다. API 주소/응답 구조 변경은 없다.

검증 근거: [10 최신 기록](10_파일_점검_현황.md#27-미디어-경로-보호와-전체-가이드-갱신-2026-10-17), [보안 지적 수동 검토](reports/2026-10-17-security-review.md).

## 파일 descriptor 보호 후속 (2026-10-17)

미디어 GET은 저장 경로를 검사한 뒤 다시 여는 대신 openMedia가 연 파일을 응답 종료/오류/중단 callback까지 유지한다. Linux /proc/self/fd로 Express의 기존 full/Range 처리를 사용하며 finally에서 닫는다. 주소·응답 구조·404 정책은 유지한다.

검증: [10 §29](10_파일_점검_현황.md#29-파일-descriptor-보호-후속-2026-10-17).

## 응답 중단 정리 검증 (2026-10-17)

GET /api/media/:id의 유효하지 않은 Range는 416을 보존하도록 수정했다. 정상 full/Range 제공과 파일 부재/거부의 404는 유지한다.

검증 근거: [10 §30](10_파일_점검_현황.md#30-응답-중단-파일-정리와-range-오류-검증-2026-10-17).

TASK-020 추가 필드: 주장 contextText는 서버가 보존한 전체 입력 전사(nullable legacy), 결과 versions는 문자열 record이며 신규 결과 ruleVersion=audio-numeric-canonical-v2다. 기존 결과에 버전/context를 소급 생성하지 않고 각각 {} / null로 읽는다.

## 2026-10-18 원문 추적 구현 전 계약 대조 (이력)

이번 갱신은 API 경로·응답 스키마를 바꾸지 않는다. TASK-023의 신규 원문/발행정보/출처 추적 필드는 아직 API에 없다. 직전 API 22개 통과와 Worker SDK 모델 목록 연결 근거는 [10 §37](10_파일_점검_현황.md#37-현재-환경-복구sdk-연결일반-원문-계약-2026-10-18)을 따르며 실제 분석 결과 생성 성공과 구분한다.

## TASK-023 sourceTrace 응답 계약

근거에 `sourceTrace: object | null`을 추가했다. 누락된 과거 필드는 null이다. parserVersion/static-text-v1, requestedUrl/finalUrl/retrievedAt/contentType, bodySha256/textSha256/textLength, blocks(kind/position/length), structureComplete, publication(publisher/publishedAt/modifiedAt의 state/value/candidates), quoteOccurrences/quoteBlockIndexes/extractionTruncated를 전달한다. hash64·블록2048·후보32/값500자 및 문서 범위 내 위치를 검증한다. 위치는 정규화 텍스트의 Python Unicode 문자 offset이며 HTML 바이트/JS UTF-16 offset이 아니다. 신규 버전은 audio-numeric-canonical-v3이며 저장된 v2 결과를 재라벨하지 않는다. 관측 metadata를 인증 완료로 표시하는 필드는 없다.

## 출처 검토 API 호환 계약 (2026-10-19)

sourceTrace.parserVersion은 static-text-v1/v2를 수용한다. sourceLinks(kind/url/locator) 최대32개·sourceLinksComplete를 추가했고 과거 누락은 []/false다. sourceReview는 nullable이며 version/registryVersion, identity(status/publisherId/registeredName), independence=unverified, groupId/groupSize(1~5)/relatedUrls(최대4)/signals를 보존한다. 인증 완료/독립 출처라고 쓰는 enum은 없다. Registry는 repository의 trusted 파일이며 API/모델 입력으로 교체하지 않는다.

결과 versions에 sourceReviewVersion/sourceRegistryVersion을 추가하고 제공자 반환값이 실제 버전을 덮어쓰지 못하게 한다. RULES execution은 검토 모듈/등록 JSON의 해시를 포함한다. 신규 API 경로는 없고 기존 운영 인증/인가 제약은 유지한다.


## API 브라우저 보호 보완 (2026-10-19)

모든 API 응답은 Origin 검사 이전 공통 미들웨어에서 X-Frame-Options DENY, Content-Security-Policy(default-src/frame-ancestors/base-uri/form-action none), Cross-Origin-Resource-Policy same-origin, Referrer-Policy no-referrer를 설정한다. 기존 nosniff/no-store와 비허용 Origin403을 유지한다. JSON 필드/상태 계약은 바꾸지 않는다. 정상206 미디어·400/403/404 오류 경계를 검증했고 기존 브라우저 재생/업로드/삭제 회귀를 유지한다. 인증·개별 데이터 소유권 대체가 아니며 운영 공개는 미완료다.


## TASK-027 읽기 전용 관리자 화면 (2026-10-19)

GET `/api/admin/overview`만 추가했다. 서버의 별도 `FACTLENS_ADMIN_TOKEN`은 32~256자 `[A-Za-z0-9._~-]` 토큰이며 무작위 32바이트 이상에서 생성한다. Authorization Bearer의 SHA-256 digest를 timingSafeEqual로 비교한다. 환경 미설정/형식 미달은 503 ADMIN_NOT_CONFIGURED, 인증 실패는 401 ADMIN_UNAUTHORIZED, 비허용 Origin은 403이다. 성공 응답은 version(admin-overview-v1), observedAt/windowStart, statusCounts, recentJobs[{id,status,createdAt,errorCode}], usage{month,settledMicros,reservedMicros,effectiveMicros,pendingReservations}다. 비용은 USD micros decimal 문자열이다. recentJobs는 최근 24시간 최대 20개이며 errorCode는 허용 코드 또는 UNCLASSIFIED_ERROR/null이다. 원시 오류·본문·토큰·미디어 ID는 반환하지 않는다. 관리자 변경 엔드포인트는 없으며 이 인증은 기존 제품 API 전체의 사용자 인증을 대신하지 않는다.


## TASK-023 표 구조 연결 (2026-10-19)

sourceTrace.parserVersion은 static-text-v3를 추가로 수용한다. blocks[].tableLocation은 nullable/default null이며 내부 객체는 strict다. tableIndex는0..99999, rowIndex/cellIndex는 같은 범위 또는null, rowSpan은0..1000 또는null, columnSpan은1..1000 또는null이다. 이전 v1/v2 블록은 자동으로 null을 받는다. 범위 밖/음수/columnSpan0은 거부한다. 구조 위치는 의미 검증 결과나 판정 등급이 아니다.


## TASK-023 표 설명 후보 연결 (2026-10-19)

sourceTrace.tableContext는 nullable/default null이다. version=table-context-v1, association=same_table_only, meaningVerified=false로 고정한다. fragments는최대16개, blockIndex0..2047, kind는table_header/caption/note, text는Unicode codepoint1..500, truncated는boolean이다. complete=true는 구조/추출이 완전하고 fragment가 절단되지 않은 경우만 허용한다. fragment의 kind/표 번호/블록 범위와 유일 인용의 표 번호가 일치해야 하며 quoteOccurrences!=1 또는 quoteBlockIndexes가 없으면 거부한다. UTF-16 길이 차이 때문에500개의 보조 평면 문자도 수용한다. 판정/독립성 인증을 뜻하지 않는다.


## 계정 API와 소유권 (2026-10-19)

| 경로 | 동작 |
| --- | --- |
| GET /api/auth/session | local/accounts 모드와 현재 사용자 또는 null |
| POST /api/auth/register | username/password로 계정 생성 및 세션 설정 |
| POST /api/auth/login | 비밀번호 확인·새 세션 설정 |
| POST /api/auth/logout | 현재 세션 폐기·쿠키 제거 |

공개 모드 쿠키는 __Host-factlens_session, Secure/HttpOnly/SameSite=Strict/Path=/,24시간이다. DB에는 토큰 SHA-256만 저장한다. 비밀번호는 임의16바이트 salt의 Node scrypt64바이트 해시로 보존한다. 인증 실패는401, 입력 오류400, 중복 이름409, 인증 시도/저장량 제한429다.

계정 모드의 모든 업로드/분석 생성·이력·단건·claims·timeline·report·evidence·media·삭제는 서버 세션 소유자를 사용한다. 미인증401, 타 계정/기존 소유자 NULL 자료404다. health와 별도 관리자 Bearer 인증은 예외이며 관리자 토큰은 일반 사용자의 미디어 접근을 허용하지 않는다.

결과 scope는 audio_only/audio_visual, visual/modalChecks/summary는 이전 결과와 호환되는 선택 필드다. visual-sampled-v1의 비공개 frameId/시간/관측/부분 상태, modal-record-review-v1 비교, claim-summary-v1 주장 집계를 검증한다. 원본 프레임 공개 URL이나 진실 확률은 제공하지 않는다.


### 선택 표 감사 DTO (2026-10-19)

SourceTrace.tableReferenceAudit는 version/meaningVerified=false/complete와 최대32개 references(cellBlockIndex,declaredId,status,headerBlockIndex|null)를 전달한다. resolved_same_table_header만 실제 같은 표의 table_header 블록 참조를 허용하고 다른 상태는 target을null로 제한한다. complete=true는 전체 구조가 추적된 경우에만 허용한다. 선언 ID는64유니코드 코드포인트로 Python/API 한도를 맞췄다.

TableContext.cueAudit는 version/meaningVerified=false/complete와최대32개 cues(blockIndex,kind,offset,text)를 전달한다. 종류는period/denominator/correction/unit, offset은 보존된 fragment의 코드포인트 기준이다. 서버/API는 fragment와 literal 일치·범위·완전성 조건을 확인한다. 의미 검증 true나 다른 표/없는 블록/위조 문자열은 거부한다. 기존 클라이언트는 선택 필드를 무시할 수 있고 예전 결과는 audit 없이 읽을 수 있다.


## TASK-028 계정 API 확장 상태

현재 제공하는 경로는 `/api/auth/register`, `/login`, `/logout`, `/session`이다(공통 접두사 `/api/auth`). 계정 수정·비밀번호 변경·탈퇴 API는 아직 없다. 후속 계약은 본인 세션·재인증·Origin 방어·횟수 제한·필드 오류·중복/만료 응답·세션 폐기와 함께 고정한다. 이 절의 요구를 이미 제공하는 엔드포인트로 해석하지 않는다.


## 관리자 계정·운영 화면 개선 — 확정 요구 (2026-10-19)

관리자 조회 API는 일반 계정 세션과 서버 역할 검사로 전환할 예정이다. 미로그인401/일반 회원403, 관리자200을 검증한다. 검색/필터/페이지 크기·정렬은 서버에서 검증하고 조회량을 제한한다. 현재 Bearer 토큰 계약이 아직 실행 중이며 신규 엔드포인트/응답 계약은 구현 전에 정의한다.


## 관리자 overview v2 조회 계약 (로컬 구현)

`GET /api/admin/overview`는 관리자 계정 세션을 요구한다. q는 작업 UUID 앞부분(0~36자, 16진수/하이픈만), status는 jobs의 허용 상태, page는1~1000(기본1), pageSize는1~50(기본20). 알 수 없는 키/중복 파라미터·잘못된 값은400 INVALID_ADMIN_QUERY다. 검색은 최근24시간 생성 작업의 ID prefix에만 적용한다. 개인정보/오류 원문 검색은 제공하지 않는다.

응답 version=admin-overview-v2, pagination={page,pageSize,total,hasNext}와 기존 recentJobs/statusCounts/usage/시각 필드를 제공한다. recentJobs만 필터링하며 요약은 전체24시간·비용은UTC 전체월 기준이다. 생성 시각/ID 내림차순이다. 각 응답은 한 SQL snapshot이지만 페이지 사이 작업 추가/삭제로 목록이 변할 수 있다.1000페이지를 넘는 운영 보관/내보내기 기능은 없다.


## 계정 정보 변경 계약 (로컬 구현)

현재 계정 정보는 GET /api/auth/session의 user.id/username/role로 읽는다. PATCH /api/auth/account는 로그인 계정만 변경하며 {username,currentPassword,newPassword?} strict body를 받는다. username은 소문자/숫자/_/- 3~32자, 비밀번호는12~128자다. 현재 비밀번호 확인 실패401 AUTH_FAILED, 미로그인401 AUTH_REQUIRED, 이름 충돌409 USERNAME_UNAVAILABLE, 형식 오류400, 과도한 시도429다. id/role 등 타깃·권한 필드는 허용하지 않는다.

성공204는 이름/비밀번호 변경 및 모든 세션 폐기를 동일 트랜잭션으로 완료하고 쿠키를 지운다. 새 이름/비밀번호로 다시 로그인한다. 사용자 이름 변경도 재인증/전체 세션 폐기를 적용한다. 실패 시 계정/세션은 그대로 보존한다. 로그인과 변경은 같은 계정 행 잠금을 사용하고 변경 시 잠금 후 유효 세션을 다시 확인한다.


## 계정 탈퇴 계약 (로컬 구현)

DELETE /api/auth/account는 로그인 세션과 strict body {currentPassword,confirmation:"DELETE"}를 요구한다. 재인증 실패401, 형식 오류400, 진행 중 분석/유효 업로드 예약409 ACCOUNT_BUSY, 관리자 자기 탈퇴409 ADMIN_CLOSURE_BLOCKED. 관리자 해제/복구 절차 없는 자기 탈퇴는 제공하지 않는다.

성공 시 사용자 이름/암호를 무효화·익명화하고 deleted_at을 기록한다. 소유 작업을deleted로 전환/버전 증가·결과/오류/주장·idempotency 정보를 제거하고 미디어 이름/경로를 폐기·만료시킨다. 비용 기록과 내부 연결 UUID는 남긴다. 모든 세션은 폐기한다. DB 처리 후 파일 정리가 끝나면204, 파일 정리 실패 시202 {cleanupPending:true}이며 계정 접근은 이미 차단되고 주기 cleanup이 재시도한다. 이미 전송/열린 파일의 회수나 제공자 측 데이터 삭제를 보장하는 API는 아니다.
