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

실제 AI 연결의 다음 단계는 제공자·모델·가격/예산·전송/보관 정책 선택과 어댑터 구현입니다. API 키를 Git이나 채팅에 넣지 않습니다. AWS·Cloudflare·Tailscale의 실제 배포/접속은 아직 검증하지 않았습니다.
