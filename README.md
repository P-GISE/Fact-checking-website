# FactLens AI

멀티모달 영상 허위정보 탐지 및 근거 교차검증 플랫폼의 기획·설계 저장소입니다.

- [프로젝트 가이드 시작하기](docs/00_문서_가이드.md)
- [공통 작업 지침](docs/AGENTS.md)
- [해야 할 일](docs/99_해야할일..md)

프로젝트 가이드는 `docs/`의 13개 문서입니다. 개발 작업은 먼저 공통 작업 지침을 읽고 진행합니다.

## 개발용 웹 PoC 실행

현재 업로드·작업·삭제·시간축 보고서 UI와 검증 규칙이 구현돼 있습니다. **실제 STT/검색/LLM 제공자는 미설정**이며 정상 파일의 분석은 `PROVIDER_NOT_CONFIGURED`로 종료됩니다. ‘예시 보고서’는 가상 자료이며 실제 분석의 대체 결과가 아닙니다. 인증이 없는 로컬 개발용이므로 공개 배포하지 않습니다.

```bash
# Docker와 Compose v2 필요
# 관리 환경에서는 외부 시스템 CA 번들을 빌드/런타임에 전달
export PROXY_CA_FILE=/etc/ssl/certs/ca-certificates.crt
docker compose up -d --build --wait
# 실행 머신의 http://127.0.0.1:8080 에서 열기
```

정상 상태: `docker compose ps`에서 postgres/redis/api healthy, web/worker 실행. `media-init`의 종료코드 0은 정상입니다. 로그: `docker compose logs --tail=50 api worker`. 중지: `docker compose down` (볼륨 보존), 재시작: `docker compose up -d --wait`. 실행 중 작업이 Worker 중지로 끝나지 못하면 시작 후 watchdog이 원래 시작 시각 기준 10분에 실패로 전환합니다. 자동 유료 재시도는 없습니다.

웹만 `127.0.0.1:8080`에 노출하며 API/DB/Redis는 Compose 내부 통신을 사용합니다. 미디어 볼륨은 비공개 공유, 기본 보관 24시간/수동 삭제 지원. 삭제는 원본·음성·결과·근거를 정리하고 최소 tombstone/사용량 기록은 유지합니다. DB 백업과 외부 제공자 보관 정책은 아직 미구현입니다.

### 로컬 개발과 검증

```bash
npm ci
python3 -m venv .venv
.venv/bin/pip install -r apps/worker/requirements.lock
# 테스트 DB/Redis만 loopback에 열기
docker compose -f compose.yaml -f compose.test.yaml up -d --wait postgres redis
export DATABASE_URL=postgresql://factlens:development@127.0.0.1:55432/factlens
export REDIS_URL=redis://127.0.0.1:56379
npm run dev --workspace apps/api
# 별도 터미널 (동일 DATABASE_URL/REDIS_URL 상속)
PYTHONPATH=apps/worker .venv/bin/python -m factlens.main
npm run dev --workspace apps/web
```

로컬 서버는 `http://127.0.0.1:5173`. `.env.example`은 변수 예시이며 스크립트가 자동 로딩하지 않습니다. API가 저장한 절대 미디어 경로를 Worker가 읽으므로 같은 머신/공유 경로에서 실행합니다. Docker Worker와 로컬 Worker를 동일 DB에 동시에 붙이지 마세요.

```bash
# 주의: 테스트는 해당 DB의 제품 테이블을 비웁니다. 개발/테스트 전용 DB에서만 실행.
npm test
.venv/bin/pytest -q
npm run typecheck
npm run build
# 전체 Compose가 실행 중일 때 (실제 DB/API/Worker + 브라우저)
E2E_BASE_URL=http://127.0.0.1:8080 npm run test:e2e
```

브라우저 테스트는 시스템 `/usr/bin/chromium`을 기본 사용합니다. 다른 머신에서는 `CHROMIUM_PATH`로 설치된 Chromium 경로를 지정합니다. PostgreSQL 테스트와 E2E는 같은 DB에서 병렬 실행하지 않습니다. 전체 Compose가 실행 중이라면 단위/DB 테스트 전 `docker compose stop worker`로 소비자를 멈추고, 테스트 후 동일한 Compose 파일 조합의 `start worker`로 복구합니다. `up`에서 파일 조합을 바꾸면 DB 포트 매핑이 달라질 수 있습니다. 테스트 명령은 위 환경 변수와 FFmpeg/ffprobe가 필요합니다.

OpenAI whisper-1/gpt-4.1-mini + Brave 어댑터와 월 $20·건당 $0.20 예산 경계를 구현했습니다. 실제 호출은 키·네트워크·전송/보관 정책 확인 후 검증해야 합니다. API 키를 Git이나 채팅에 넣지 않습니다. AWS·Cloudflare·Tailscale의 실제 배포/접속은 아직 검증하지 않았습니다.

제공자 연결 준비용 비용 경계는 `apps/worker/factlens/metered.py`에 있습니다. 선택된 SDK의 가격 기반 호출 상한·동일 통화 예산과 `ChargedResult` 사용량 영수증이 필요하며, 이 모듈만으로 제공자나 청구가 활성화되지는 않습니다. 실패/사용량 미확인 시 예약은 유지되고 월 경계에서도 건당 한도는 초기화되지 않습니다.

## 승인 프로필 설정

기본 `FACTLENS_AI_MODE=disabled`입니다. 안전한 로컬 `.env`에 `FACTLENS_AI_MODE=openai_brave`, `OPENAI_API_KEY`, `BRAVE_SEARCH_API_KEY`를 설정하고 동일한 Compose 파일 조합으로 Worker를 재생성하세요. 예산 변수 기본값은 `FACTLENS_JOB_BUDGET_MICROS=200000`, `FACTLENS_MONTH_BUDGET_MICROS=20000000`이며 승인 상한을 높일 수 없습니다. 키는 Worker에만 전달합니다.

현재 환경에는 키와 `api.openai.com`/`api.search.brave.com` 아웃바운드 허용이 없어 실제 유료 호출은 검증하지 않았습니다. 근거 원문 접근 정책도 필요합니다. 프록시/CA는 유지합니다. [운영 설정과 실자료 검증 절차](docs/08_운영_배포.md)를 따르세요. 정형 원문만 인정하는 현재 Validator 때문에 일반 웹문서는 검증 불충분이 될 수 있습니다.

2026-10-17: 미디어 읽기/삭제 경계에 UUID·정해진 source 파일명·realpath 검사를 추가했습니다. 최신 검증과 운영 잔여 조건은 [프로젝트 가이드](docs/10_파일_점검_현황.md#27-미디어-경로-보호와-전체-가이드-갱신-2026-10-17), 정적 지적별 근거는 [수동 검토표](docs/reports/2026-10-17-security-review.md)에 있습니다.

## 오프라인 판정 평가 준비

실제 모델 호출 없이 수동 대응한 정답/예측 라벨을 채점하는 도구를 추가했습니다. 원본 계열의 dev/test 혼입·manifest 해시·누락/실패 분모를 검사합니다. [평가 실행 안내](evaluation/README.md)의 예시는 합성 자료이며 실제 제품/연구 성능이 아닙니다. 생산 Validator는 변경하지 않았습니다.

```bash
PYTHONPATH=apps/worker .venv/bin/python -m factlens.evaluation score evaluation/example-dataset.json evaluation/example-run.json --split test
```

## 실제 규칙 회귀

```bash
PYTHONPATH=apps/worker .venv/bin/python -m factlens.rule_regression evaluation/rules-fixture.json --split test
```

생산 Validator/Decision을 합성9개 사례에서 실행하며 전체 입력/규칙/소스 해시를 기록합니다. RULES 결과는 모델·실자료 연구 성능이 아닙니다. 현재 v2의 확정 비교는 한국/대한민국의 연 단위 고용률%·실업률%·인구명 등 제한된 정형 기록뿐이며, 표시 주장·전체 전사·근거 전체 맥락을 확인합니다. 일반 발언과 문서의 지원 확장은 [통합 실행 순서](docs/00_문서_가이드.md#통합-실행-순서)를 따릅니다.
