# 정적 보안 지적 수동 검토 — 2026-10-17

기준: 2026-10-16 SDK 보고서 48건을 현재 코드와 대조했다. 아래 번호는 그 보고서 순서이며 최신 보고서 순번과 다를 수 있다. 자동 승인/지적 억제 설정은 추가하지 않았다.

경로 보호 당시 전체 점검은 **43개 파일/49건(치명 0, 고위험 5, 중위험 23, 저위험 21), 종료코드 1**이다. 경로 검사 helper를 통해 taint 경로가 하나 더 관측되어 기존 48보다 늘었다. 새 보고서의 경로 지적 4개는 UUID·정확한 경로 일치·realpath 검사를 수동 확인했고 재현 테스트로 보호를 확인했다. 이것은 정적 검사 통과나 전체 보안 감사를 의미하지 않는다.

| 이전 번호 | 지적/위치 | 수동 분류 | 근거와 후속 |
|---|---|---|---|
| 1 | [IL-502] `api/src/app.ts:46` | 보완됨·도구 지적 유지 | storage.ts UUID/정해진 source/realpath 경계와 API 회귀 4건. 도구는 사용자 정의 검증을 정제 함수로 모델링하지 못해 계속 표시한다. 동시 파일 교체 경쟁은 별도 잔여 위험. |
| 2 | [IL-502] `api/src/app.ts:79` | 보완됨·도구 지적 유지 | storage.ts UUID/정해진 source/realpath 경계와 API 회귀 4건. 도구는 사용자 정의 검증을 정제 함수로 모델링하지 못해 계속 표시한다. 동시 파일 교체 경쟁은 별도 잔여 위험. |
| 3 | [IL-502] `api/src/app.ts:84` | 보완됨·도구 지적 유지 | storage.ts UUID/정해진 source/realpath 경계와 API 회귀 4건. 도구는 사용자 정의 검증을 정제 함수로 모델링하지 못해 계속 표시한다. 동시 파일 교체 경쟁은 별도 잔여 위험. |
| 4 | [AI-111] `worker/requirements.txt:2` | 이름 유사성 오탐 검토 | psycopg은 psycopg3 공식 패키지명이다. psycopg2 유사 철자라는 휴리스틱만으로 악성으로 판단하지 않는다. requirements.lock의 psycopg/psycopg-binary 버전을 사용한다. 공급망 무해성을 보증하지 않는다. |
| 5 | [AI-111] `api/package.json:1` | 공급망 잔여 점검 | manifest 범위 지정은 lock과 함께 사용한다. npm ci/고정 Python lock 빌드를 확인했으나 취약점/무결성 전수 감사는 별도다. |
| 6 | [ARC-202] `api/src/app.ts:19` | 구조 개선 대기 | 작은 Express 경로에서 DB 직접 접근한다. 쿼리는 바인딩 파라미터 사용. 서비스 계층 분리는 후속 품질 개선이며 인증을 대체하지 않는다. |
| 7 | [IL-525] `api/src/app.ts:35` | 운영 차단 조건 | 인증 없음은 실제 잔여 요구다. loopback 바인딩과 Origin 제한만 구현됐으며 TASK-017 공개 전 사용자별 인증/인가 검증이 필요하다. |
| 8 | [IL-525] `api/src/app.ts:48` | 운영 차단 조건 | 인증 없음은 실제 잔여 요구다. loopback 바인딩과 Origin 제한만 구현됐으며 TASK-017 공개 전 사용자별 인증/인가 검증이 필요하다. |
| 9 | [IL-525] `api/src/app.ts:74` | 운영 차단 조건 | 인증 없음은 실제 잔여 요구다. loopback 바인딩과 Origin 제한만 구현됐으며 TASK-017 공개 전 사용자별 인증/인가 검증이 필요하다. |
| 10 | [AI-111] `web/package.json:1` | 공급망 잔여 점검 | manifest 범위 지정은 lock과 함께 사용한다. npm ci/고정 Python lock 빌드를 확인했으나 취약점/무결성 전수 감사는 별도다. |
| 11 | [IL-301] `web/src/api.ts:4` | 검토됨·사용자 오류 전달 | JSON 오류 본문 해석 실패 시 NETWORK_ERROR를 throw한다. 성공으로 삼키는 경로는 아니다. |
| 12 | [AI-101] `worker/factlens/live_providers.py:165` | 고정 대상 의도 | 사용자 승인한 공식 API endpoint를 고정해 임의 주소/비밀 유출을 방지한다. 대체 제공자로 자동 전환하지 않는다. |
| 13 | [IL-301] `worker/factlens/live_providers.py:182` | 검토됨·제한 전달 | 검색 원문 접근 실패를 limitations에 기록하고 다른 후보를 확인한다. 실패를 반박으로 사용하지 않는다. |
| 14 | [AI-101] `worker/factlens/live_providers.py:198` | 고정 대상 의도 | 사용자 승인한 공식 API endpoint를 고정해 임의 주소/비밀 유출을 방지한다. 대체 제공자로 자동 전환하지 않는다. |
| 15 | [IL-301] `worker/factlens/main.py:28` | 검토됨·실패 상태 전달 | 외부 오류 원문은 노출하지 않고 통제된 errorCode로 fail_job한다. raw 예외 로깅은 비밀/문서 노출 위험 때문에 사용하지 않는다. 세부 관측 개선은 후속. |
| 16 | [IL-301] `worker/factlens/main.py:30` | 검토됨·실패 상태 전달 | 외부 오류 원문은 노출하지 않고 통제된 errorCode로 fail_job한다. raw 예외 로깅은 비밀/문서 노출 위험 때문에 사용하지 않는다. 세부 관측 개선은 후속. |
| 17 | [IL-301] `worker/factlens/main.py:36` | 검토됨·실패 상태 전달 | 외부 오류 원문은 노출하지 않고 통제된 errorCode로 fail_job한다. raw 예외 로깅은 비밀/문서 노출 위험 때문에 사용하지 않는다. 세부 관측 개선은 후속. |
| 18 | [IL-304] `worker/factlens/main.py:36` | 검토됨·실패 상태 전달 | 외부 오류 원문은 노출하지 않고 통제된 errorCode로 fail_job한다. raw 예외 로깅은 비밀/문서 노출 위험 때문에 사용하지 않는다. 세부 관측 개선은 후속. |
| 19 | [IL-301] `worker/factlens/main.py:48` | 관측성 개선 대기 | Redis 통신 실패는 지연 후 DB 복구, 잘못된 큐 ID는 건너뛴다. 운영 진단용 비밀 없는 이벤트/횟수 관측은 남아 있다. |
| 20 | [IL-301] `worker/factlens/main.py:49` | 관측성 개선 대기 | Redis 통신 실패는 지연 후 DB 복구, 잘못된 큐 ID는 건너뛴다. 운영 진단용 비밀 없는 이벤트/횟수 관측은 남아 있다. |
| 21 | [IL-301] `worker/factlens/pipeline.py:37` | 검토됨·유보 전달 | 검색 예외를 결과 제한에 반영한다. ProviderUnavailable은 작업 실패로 전파된다. |
| 22 | [ARC-212] `worker/factlens/queue.py:34` | 제한된 다중 쓰기·개선 대기 | 완료 트랜잭션 내 주장/근거별 INSERT이다. N+1 SELECT는 아니며 최대 5개 주장/제한된 근거 수를 유지한다. bulk 쓰기 성능 측정은 후속. |
| 23 | [ARC-212] `worker/factlens/queue.py:35` | 제한된 다중 쓰기·개선 대기 | 완료 트랜잭션 내 주장/근거별 INSERT이다. N+1 SELECT는 아니며 최대 5개 주장/제한된 근거 수를 유지한다. bulk 쓰기 성능 측정은 후속. |
| 24 | [ARC-212] `worker/factlens/queue.py:38` | 제한된 다중 쓰기·개선 대기 | 완료 트랜잭션 내 주장/근거별 INSERT이다. N+1 SELECT는 아니며 최대 5개 주장/제한된 근거 수를 유지한다. bulk 쓰기 성능 측정은 후속. |
| 25 | [ARC-212] `worker/factlens/queue.py:39` | 제한된 다중 쓰기·개선 대기 | 완료 트랜잭션 내 주장/근거별 INSERT이다. N+1 SELECT는 아니며 최대 5개 주장/제한된 근거 수를 유지한다. bulk 쓰기 성능 측정은 후속. |
| 26 | [IL-301] `worker/factlens/retrieval.py:22` | 정상 파싱 분기 | 숫자 IP 해석 실패 시 DNS resolver를 사용하며 이후 모든 주소의 public/IPv4 여부를 검사한다. |
| 27 | [IL-301] `worker/factlens/validator.py:48` | 유보 전달 | InvalidOperation은 INVALID_NUMERIC_VALUE 이유와 INSUFFICIENT로 반환한다. |
| 28 | [AI-114] `api/package.json:1` | 일부 보호·운영 후속 | nosniff/no-store/Origin/JSON 및 업로드 크기 제한 존재. 일반 호출률 제한과 운영 보안 헤더/인증은 미완료다. |
| 29 | [AI-120] `api/src/app.ts:1` | 휴리스틱 오탐 검토 | app.ts 마지막 app.use에 일관된 JSON 전역 오류 응답이 존재한다. |
| 30 | [TYP-301] `api/src/app.ts:14` | 타입 품질 후속 | DB 행/오류 등 일부 동적 타입과 비-null 단언이 남아 있다. 타입 검사는 통과하나 전수 스키마/타입 정밀화는 후속이다. |
| 31 | [ARC-205] `api/src/app.ts:15` | 품질 개선 대기 | enum/계약 문자열·오류 코드를 공통화할 수 있다. 이번 경로 보호 수정에서는 바꾸지 않았다. |
| 32 | [IL-301] `api/src/app.ts:65` | 의도된 큐 복구 | Redis enqueue 실패에도 durable queued DB 행을 유지한다. offline enqueue 회귀 테스트가 있으며 성공 분석으로 표시하지 않는다. |
| 33 | [TYP-301] `api/src/app.ts:65` | 타입 품질 후속 | DB 행/오류 등 일부 동적 타입과 비-null 단언이 남아 있다. 타입 검사는 통과하나 전수 스키마/타입 정밀화는 후속이다. |
| 34 | [TYP-301] `api/src/app.ts:66` | 타입 품질 후속 | DB 행/오류 등 일부 동적 타입과 비-null 단언이 남아 있다. 타입 검사는 통과하나 전수 스키마/타입 정밀화는 후속이다. |
| 35 | [TYP-301] `api/src/app.ts:87` | 타입 품질 후속 | DB 행/오류 등 일부 동적 타입과 비-null 단언이 남아 있다. 타입 검사는 통과하나 전수 스키마/타입 정밀화는 후속이다. |
| 36 | [ARC-205] `api/src/contracts.ts:2` | 품질 개선 대기 | enum/계약 문자열·오류 코드를 공통화할 수 있다. 이번 경로 보호 수정에서는 바꾸지 않았다. |
| 37 | [ARC-209] `api/src/db.ts:4` | 품질 개선 대기 | enum/계약 문자열·오류 코드를 공통화할 수 있다. 이번 경로 보호 수정에서는 바꾸지 않았다. |
| 38 | [AI-101] `web/vite.config.ts:3` | 개발용 고정 주소 | Vite 로컬 API 프록시 주소다. 운영 도메인 설정으로 간주하지 않는다. |
| 39 | [PERF-101] `worker/factlens/budget.py:7` | 트랜잭션 검토됨·성능 후속 | 예산 직렬화 및 원자적 claim을 위한 여러 SQL이다. 안전성 테스트 통과와 운영 부하 성능은 구분한다. |
| 40 | [TYP-302] `worker/factlens/live_providers.py:40` | 타입 품질 후속 | DB 행/오류 등 일부 동적 타입과 비-null 단언이 남아 있다. 타입 검사는 통과하나 전수 스키마/타입 정밀화는 후속이다. |
| 41 | [ARC-205] `worker/factlens/live_providers.py:109` | 품질 개선 대기 | enum/계약 문자열·오류 코드를 공통화할 수 있다. 이번 경로 보호 수정에서는 바꾸지 않았다. |
| 42 | [ARC-211] `worker/factlens/live_providers.py:199` | 프로세스 수명 경계 | SDK/HTTP 클라이언트는 작업 자식 프로세스 수명 내에서 사용한다. 공유 풀 도입은 프로세스 격리와 함께 재설계가 필요하다. |
| 43 | [IL-517] `worker/factlens/main.py:41` | 의도된 Worker 루프 | 상시 소비 루프이며 큐 대기/오류 sleep과 자식 실행 시간 제한이 있다. 서비스 종료는 프로세스 종료로 처리한다. |
| 44 | [TYP-302] `worker/factlens/metered.py:85` | 타입 품질 후속 | DB 행/오류 등 일부 동적 타입과 비-null 단언이 남아 있다. 타입 검사는 통과하나 전수 스키마/타입 정밀화는 후속이다. |
| 45 | [TYP-302] `worker/factlens/pipeline.py:14` | 타입 품질 후속 | DB 행/오류 등 일부 동적 타입과 비-null 단언이 남아 있다. 타입 검사는 통과하나 전수 스키마/타입 정밀화는 후속이다. |
| 46 | [PERF-101] `worker/factlens/queue.py:15` | 트랜잭션 검토됨·성능 후속 | 예산 직렬화 및 원자적 claim을 위한 여러 SQL이다. 안전성 테스트 통과와 운영 부하 성능은 구분한다. |
| 47 | [ARC-211] `worker/factlens/retrieval.py:33` | 프로세스 수명 경계 | SDK/HTTP 클라이언트는 작업 자식 프로세스 수명 내에서 사용한다. 공유 풀 도입은 프로세스 격리와 함께 재설계가 필요하다. |
| 48 | [AI-111] `worker/requirements.txt:1` | 공급망 잔여 점검 | manifest 범위 지정은 lock과 함께 사용한다. npm ci/고정 Python lock 빌드를 확인했으나 취약점/무결성 전수 감사는 별도다. |

## 별도 코드 리뷰와 남은 경계

읽기 전용 리뷰에서 이번 수정 범위의 중요 결함은 발견되지 않았다. 다만 realpath 검사 뒤 sendFile이 파일을 여는 사이에 같은 UID의 쓰기 권한을 가진 프로세스가 파일을 교체하는 경쟁은 막지 않는다. 업로드 요청만으로 파일/심볼릭 링크를 임의 생성할 수 있는 기능은 없지만, 운영 프로세스/파일 권한 격리나 descriptor 기반 파일 제공은 후속 검토다.

리뷰가 제안한 추가 회귀 두 가지(절대 경로 삭제 ID, 물리적 삭제 여부 직접 확인)는 후속으로 남긴다. 이번 테스트는 상대 경로 이탈 거부와 정상 API 삭제/접근 차단을 확인했다.

[최신 정적 점검 원문](2026-10-17-path-iron-laws.txt). 키/실제 외부 AI 호출/운영 인증·백업·부하 평가 완료 근거는 없다.

## descriptor 후속의 최신 상태

이후 openMedia에서 디렉터리와 파일을 descriptor로 고정했다. 위의 경로 재열기 경쟁과 절대 삭제 ID/물리 삭제 테스트 2개는 후속에서 보완·검증했다. 같은 UID로 파일 내용 자체를 수정할 수 있는 프로세스에 대한 격리 요구는 유지한다. 별도 리뷰의 새 소규모 후속은 클라이언트 중단 후 descriptor 닫힘 직접 테스트다. 최신 전체 스캔은 44파일/48건(치명0·고위험4·중위험23·저위험21), 종료1이다. [최신 원문](2026-10-17-descriptor-iron-laws.txt). 기존 표 번호는 이전 48건 기준 그대로이며 새 스캔과 순번이 같다는 뜻은 아니다.
