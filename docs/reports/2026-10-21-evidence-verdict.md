# 실AI·근거 판정 진행 기록

## 5달러 충전 후 실제 분석 완료 (2026-10-21)

사용자의 충전 완료 통보 후 기존 합성 한국어 음성으로 격리 실AI1건을 실행했다. 두 키 존재/환경 파일0600 확인, 전사→주장 추출→검색→근거 검증→AnalysisResult 생성까지 정상 반환했다. 오류null, 주장1개·근거0개·REVIEW_REQUIRED1개다. 계정 할당량 차단은 이번 실행에서 해소됐지만 사실 확인/반박 성공은 아니다. [비식별 실행 JSON](2026-10-21-funded-live-smoke.json)을 보존한다. 아래429/대기는 이전 단계 이력이다.

외부 호출6회, 요금표 기반 actualMicros7783/unknownUsageCalls1/보수적8383micros($0.008383). 전사는 미확인600 예약을 유지하며 actualMicros가 결제 명세서 확정액은 아니다. 이전 실패3회의1800을 포함한 누적 보수적 집계는10183micros($0.010183)다. 건당200000/월20000000micros 한도를 유지했다.

filesRemoved/jobTombstoned/mediaTombstoned/usageRetained 모두true, 별도 서버 입력/스테이징 디렉터리 제거. 실제 실행 소스da04741, 내부 health ready/providerConfigured:false. 공개 AI는 disabled를 유지했다. 이 검사는 격리 생산 파이프라인이며 공개 회원 업로드·큐·브라우저 전 과정 성공은 아니다.

추가 유료 호출 없이 현재 검색/판정 경로를 검토했다. 근거 없는 경우 보류하는 동작은 유지됐으나 이 도구의 집계에는 전사문/후보별 미채택 사유가 없으므로0건의 정확한 원인을 단정할 수 없다. 다음 제품 검증은 비밀/원문 노출 없는 진단을 보강해 검토된 근거가 실제 추출 주장과 연결되는지 확인하는 것이다. 연구 정확도/범용 판정 완료로 확대하지 않는다.

## 키 저장 후 재검증 (2026-10-21)

사용자의 키 저장 통보 후 서버 환경 파일0600/ubuntu와 격리 컨테이너의 OpenAI·Brave 키 존재를 값 노출 없이 확인했다. 동일한 직접 제작 음성으로 실제 전사1회를 재실행한 결과 `PROVIDER_QUOTA_EXCEEDED`로 중단됐다. 이전의 일반429와 달리 이번 제공자 분류는 할당량 부족이다. Billing 잔액/조직·프로젝트 한도 중 구체 원인은 아직 확인되지 않았다.

stages=[transcribing], claimsCount=0/evidenceCount=0, calls=1/unknownUsageCalls=1/conservativeMicros=600 USD. actualMicros=0은 무료 증명이 아니다. 이전2회와 합친 보수적 예약은1800micros($0.0018)다. filesRemoved/jobTombstoned/mediaTombstoned/usageRetained 모두true. 별도 서버 입력·스테이징 디렉터리도 제거했다. 내부 health ready/providerConfigured:false를 확인했고 공개 AI 활성화나 추가 반복 호출은 수행하지 않았다. 실제 전 과정 완료는 여전히 대기다.

실AI는429 차단 상태이며 제한된 검토 근거 판정의 구현/검증을 진행했다. 실AI 성공·제품 전체 판정 완료 보고서가 아니다. 사용자는 작성 설계를 승인하고 개발을 지시했다.

## 현재 외부 조건

초기 로컬/상시 Worker 키 미설정을 확인한 뒤 서버 .env.production의 두 키 존재와0600을 확인했다. 값은 출력하지 않았다. 공개 AI disabled를 유지한 별도 Compose 컨테이너에 키를 주입해 실제 전사 요청을 두 번 수행했고 모두429로 중단됐다. SDK max_retries=0이며 두 번째는 오류 분류 보완을 적용한 제어된 검증이었다. 계정 잔액·조직/프로젝트·모델 제한 원인은 아직 미확인이다. 사용자가 확인 방법 안내를 요청해 공식 Billing/Limits 절차를 전달했고 추가 반복 호출은 멈췄다.

[실행 JSON](2026-10-21-live-smoke.json)의 각 실행은 전사1회·미확인 예약600micros, 합계1200micros($0.0012)다. actualMicros=0을 청구0원으로 해석하지 않는다. 실제 DB에서 시험 작업2개 모두deleted/result·error null, 예약합계1200, 공개AI disabled를 대조했다. 임시 컨테이너/시험 파일과 서버의 전용 스테이징 디렉터리를 제거했다. 로컬 합성 원본은 재현용으로 Git 밖에 보존한다. 검색·생성·보고서 완주는 이번 호출에서 수행되지 않았다.

## 공식 출처 검토

- [2024 한국의 사회지표](https://mods.go.kr/board.es?act=view&bid=10820&list_no=435687&mid=a10301060500), 게시일2025-03-25, 담당사회통계기획과. 발표 당시 통계청과 현재 사이트 표기 국가데이터처를 구분한다.
- [KOSIS 고용 지표 정의](https://kosis.kr/visual/eRegionIndex/eRegionTheme.do?themeId=167): 고용률은15세이상 인구 대비 취업자, 실업률은 경제활동인구 대비 실업자다. 연간 한국2024년의15세이상 고용률62.7%와 실업률2.8%를 구분해 대조한다.
- 서버와 같은 fetch_evidence/static-text-v3로 실제 HTTPS 원문을 읽었다. sri.kostat.go.kr의 기존 주소는 mods.go.kr로 리디렉션된다. 정확한 최종 주소만 등록한다.
- 현재 페이지의 publisher/publishedAt/modifiedAt 자동 관측은 모두missing이다. 수동으로 확인한 발행 정보와 자동 관측을 합치지 않는다. 도메인 등록 후에도 기존 SourceReview는publisher_unverified를 유지하며, 별도 검토 정책이 범위 내 인용과 정의를 검사한다.
- 전체6805자 정규화 텍스트는 조회수/탐색 정보 때문에 수집마다 바뀐다. 본문 전체2010자 단일text블록은 두 실제 수집에서 동일했다. 정책은 이 전체 본문 해시를 고정하고, 매 실행의 전체 문서 해시도 원문과 대조해 보고서에 남긴다. 기사 일부만 떼어 전체 문맥 확인으로 표시하지 않는다.
- 본문 SHA256: `720b32278f378ad55320a0d611744272f510b5a0b07ed3ad92d47b34b0d6b0cc`. 두 수집UTC2026-10-20T16:12:07.538745+00:00/16:12:08.622306+00:00 모두 일치블록1개. 전체문서의 고정 위치가 아닌 본문 상대 위치848의 고용·실업 단락을 검토했다.
- 게시일은 본문 블록 밖의 `게시일 2025-03-25`도 별도로 대조해야 한다. 본문 밖의 수정/공지까지 해시가 인증한다고 주장하지 않는다. 지원 밖/새 내용은 재검토 또는 유보다.
- 별도 [국가지표체계 실제 통계표](https://www.index.go.kr/unity/potal/eNara/sub/showStblGams3.do?freq=Y&idx_cd=1063&period=N&stts_cd=106301)도 생산 수집기로 읽었다. 정규화915자 전체 해시 `f4b6a225608264d859b16710684ec90bc519023ba6b87db84344cccbee06adfa`, 실업률(%) 행/2024 열의 셀 위치565·블록88을 검토했다. 동일한2.8 문자열의 다른 셀은 행·열/위치로 구분한다. 병합/복잡한 표는 확정하지 않는다.
- 이 표는 별도 발행일 없는 갱신형 데이터다. live_dataset 정책의 publishedAt=null을 유지하며 검토일을 발행일로 바꾸지 않는다. 문서 내용·헤더가 바뀌면 재검토한다. 두 사이트는 같은 경제활동인구조사 자료를 전달하므로 명시적 originId로 같은 원출처 한 그룹에 묶는다. 독립 근거2개가 아니다.

## 판정·API·화면 검증

- 실제 새 수집 문단과 표에서 각각2.8%→CONFIRMED,2.9%→REFUTED를 생산 reviewed_document→validate_evidence→review_sources→decide로 확인했다. 합성 대체 원문이나 검색 스니펫을 이 증거로 사용하지 않았다. 실제 STT/LLM 실행과도 구분한다.
- 두 실제 수집 결과를 Python 모델에서 직렬화한 뒤 생산 TypeScript resultSchema로 직접 읽었다. 문단의2025-03-25와 표의null 발행일, 원문 해시·위치, 문서2/원출처 그룹1·independenceVerified=false를 보존했다.
- 직접 실행한 관련 Worker136개 통과, API 스키마36개·인증 중단13개 통과, 타입/빌드 통과. 별도 독립 검토는 차단 결함 없이 APPROVE였다. 파일 존재만 확인하는 중복 테스트1개는 비차단 유지보수 항목으로 보존했다.
- 실제 Chrome의 새 검토 보고서/기존 보고서/모달 분리3개 통과. 데스크톱·390px 캡처에서 주장의 범위·지지/반박·비교 정의/위치·보통/낮음 설명·HTML 이스케이프·가로 넘침 여부를 확인했다. 모의 화면 사례이며 실제 공개 AI 성공이 아니다.
- 로컬 전체 Worker는 DB/미디어 환경 부재와20초 실행 제한으로 완료되지 않았다. API security.test.ts는 DATABASE_URL_REQUIRED로 수집 실패했다. Linux CI에서 전체 DB/FFmpeg 검증을 확인해야 한다. 제어된 실AI의 추가 실제 PostgreSQL/FFmpeg 회귀2개를 CI 전용 DB의 무작위 격리 schema에서 실행하도록 연결했다.

## 시험 입력과 점검

직접 작성한 한국어 문장과 Windows Heami 음성4.8385초·213426byte를 생성했다. 입력은 제3자 녹음/개인정보가 없는 연결 시험용이다. [manifest](../../evaluation/smoke/owned-korean-2026-10-21.json)에 해시를 기록했고 음성파일은 Git에 넣지 않았다. 연구 라벨/성능평가가 아니다.

기존 관련 회귀는67통과·영상 통합1개 FFmpeg 미발견 실패였다. 실제 음성의 `퍼센트` 표기를 `%`와 동등한 단위 후보로 보존하지 못하는 문제를 새 테스트에서 실패 재현하고 수정했다. `퍼센트 포인트`는 변환하지 않는 경계와 기존 제공자 회귀를 포함해21개 통과했다. 이는 모의SDK 경계 검증이며 실제 STT 성공은 아니다.

현재 지원은 검토한2024년 한국 연간 실업률과 제한된 단일 문장/표다. 범용 주장·영상 전체 판정·독립 출처·연구 정확도로 완료 범위를 넓히지 않는다.

## 최종 게시·배포 검증

[Actions39462037590](https://github.com/P-GISE/Fact-checking-website/actions/runs/39462037590)는 verify/deploy 모두 성공했다. 전체 Linux API97개·Worker391개(DB/FFmpeg 격리 회귀 포함), 타입/빌드·배포 회귀가 통과했다. 최종 로컬 관련 Worker178통과/환경 의존2skip과 구분한다.

실제 서버 HEAD는 `da04741aba47060f22d26a836b09e45a8f0bf4cb`, 실행 Worker 규칙은 `audio-reviewed-numeric-v5`다. 내부127.0.0.1:3300/api/health와 공개 HTTPS /api/health 모두 ready/providerConfigured:false, Worker AI_MODE=disabled를 SSH로 확인했다. 처음 잘못 조회한 호스트3000포트 연결 실패는 실제3300 경로로 바로잡아 확인했다. 공개 AI 전 과정 성공으로 해석하지 않는다.

Iron Laws의 무기록 예외 지적은 고정 코드만 남기는 로그와 회귀로 수정했다. 해당 파일 재검사0지적/passed:true, 원문·비밀을 로그에 넣지 않는 회귀 통과. 전체 검사와 verify_patch는300초 시간 초과였으므로 전체 보안 통과나 패치 검증 성공으로 쓰지 않는다. Strix 유료 보안 엔진은 실행하지 않았다.

사용자 우선순위2번의 승인된 제한 지원은 배포됐다. 1번 실제 AI 전 과정은 계정 Billing/Limits 확인 후 재검증이 남았다. 나머지 네 분야는 사용자 요청대로 추후 개선한다.
