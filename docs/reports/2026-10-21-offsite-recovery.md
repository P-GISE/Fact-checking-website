# 외부 백업·새 호스트 복구 검증 (2026-10-21)

대상은 FactLens 전용 Sydney `factlens-ai`이며 공개 주소/기존 DB·계정·미디어를 유지한다. 외부 보관은 다른 리전인 Seoul을 사용한다. 이전 같은 호스트의 격리 DB 드릴과 이번 새 호스트 재구축을 구분한다. 최종 운영 SHA는 `3a0cd28e79ed607d157d4292892549ffb75330d5`이며 문서 전용 후속 HEAD와 구분한다.

## 구현·검토

- `285a71b`: 기존 완료 백업/무결성 검사를 재사용하는 `disaster_recovery.py`와 아카이브 경계 회귀, S3 업로드 workflow를 추가했다.
- export는26시간 이내 정상 daily 백업·DB manifest·코드 SHA·배포 환경·터널 token/unit을 묶는다. 비밀값을 stdout 텍스트/로그에 출력하지 않으며 binary stdout은 비공개 임시 파일로만 받는다.
- prepare는 운영 표식·기존 환경/출력·잘못된 저장소/SHA·손상·링크/중복/경로/크기 초과를 거부하고 새 비공개 대상에만 저장한다. 자동 Docker 실행·터널 연결은 하지 않는다.
- 독립 리뷰의 두 결함을 수정했다: 복구는 보관 중7일 백업까지 허용하고, 복원한 환경의 마지막 AI 설정을 disabled로 강제한다. 보관 원본과 체크섬은 유지한다. 부모가 실패2개→수정 후13통과/1개 POSIX skip을 확인했고 재검토 APPROVE를 받았다.
- Iron Laws 해당1파일 완료/passed:true·REVIEW2개는 무효 후보 건너뛰기와 CLI 비밀값 차단 예외로 분류한다. 전체 앱 안전 보증이 아니다. actionlint/diff 검사 통과. Linux 전체 CI와 실제 복구는 아래 실행 결과로 구분한다.

## 외부 보관·권한

- S3: `factlens-backups-753805950222-ap-northeast-2`, Seoul. Block Public Access 전체 활성·BucketOwnerEnforced·버전 관리·TLS 전용·정확한 전용 KMS 키 사용 조건.
- KMS: `arn:aws:kms:ap-northeast-2:753805950222:key/0b7cf093-f6f0-46ee-ad42-c1a39b691bf1`, 자동 순환 활성. 키 삭제/예약 삭제는 하지 않는다.
- IAM: `FactLensBackupUpload`는 `daily/*`의 PutObject와 해당 S3 버킷 암호화 context의 GenerateDataKey만 허용한다. 읽기·삭제·Decrypt를 부여하지 않는다. IAM 시뮬레이션에서 GetObject/DeleteObject/Decrypt 모두 implicitDeny였다. 공개 접근 차단 전체true·IsPublic=false·versioning Enabled·KMS rotation=true를 실제 AWS API로 확인했다.
- `FactLensBackupInspect`는 정확한 `daily/` prefix의 ListBucket만 허용한다. 객체 내용과 KMS 복호화 권한은 없다. `3a0cd28`/main `a986eef`의 감시는 로컬 백업 나이와 별도로 S3 객체 업로드 나이26시간을 검사한다. 실제 workflow 검사문의 정상/빈 목록/오래됨/미래/크기 경계 회귀5개와 별도 리뷰8개를 통과했다. AWS 실패 코드가 export 명령에 가려지지 않도록 대입/export도 분리했다.
- GitHub OIDC subject는 API에서 확인한 immutable ID 형식 `repo:P-GISE@291131519/Fact-checking-website@1420151819:environment:production`으로 제한했다. production 접근 브랜치는 main/work만 허용한다. 서버에 장기 AWS 키를 설치하지 않았다.
- main의 동일 offsite workflow는 `e765b58`로 등록했다. 예약은 매일03:15 KST이며 GitHub 예약 지연 가능성이 있다. 현재 객체7일·이전 버전7일·미완료 multipart1일의 lifecycle이다. 삭제는 AWS 비동기 처리이므로 정확히168시간에 지워진다는 보장은 아니다.

## 실제 실행 기록

[전체 CI/배포39448192158](https://github.com/P-GISE/Fact-checking-website/actions/runs/39448192158)에서 API72/Worker251·타입/빌드·배포 회귀·실제 배포285a71b 성공. 감시 보완 후 [최종 CI/배포39449902132](https://github.com/P-GISE/Fact-checking-website/actions/runs/39449902132)도 같은 전체 검사와 실제 배포3a0cd28에 성공했다. 별도 고정 지문 SSH로 SHA·CHECK_OK·timer active를 확인했다.

[첫 S3 백업39448714820](https://github.com/P-GISE/Fact-checking-website/actions/runs/39448714820)이 단기 OIDC 인증과 KMS PutObject에 성공했다. 실제 객체는 `daily/20261020T152850Z-39448714820-1.tar.gz`, version `NtkWu7u83Q.6hwxChFSkPDr_AQYM1_Il`, 5152bytes다. 복구 운영자 권한으로 다시 다운로드해 KMS ARN·SHA-256 메타데이터와 AWS ChecksumSHA256을 검증했다. SHA256은 `f6dfc28dec041f054cb14caab20d712a26a4d61509f53628a46d42c9e92e7148`이다. backup 활성 변수true와 매일03:15 KST 예약을 등록했다. 예약 시각 도래를 기다려 실행한 결과와 수동 첫 실행을 혼동하지 않는다.

[외부 백업 감시39450037154](https://github.com/P-GISE/Fact-checking-website/actions/runs/39450037154)의 실제 check에서 CHECK_OK·OFFSITE_FRESH를 확인했다. main/work monitor.yml SHA256 일치도 확인했다. 이는 S3 업로드 최신성 검사이며 DB 스냅샷 생성 시각은 별도 로컬26시간 검사와 export 검사로 제한한다. GitHub 실패 이메일 전달 여부는 별도 계정 알림 설정이며 AWS 이메일 시험 수신 결과와 구분한다.

새 서버 `factlens-drill-20261021`는 Seoul Ubuntu24.04·4GiB다. SSH는 CloudShell 단일 IP와 Lightsail 인증 브라우저만 허용한다. AWS가 확인한 Ed25519 키를 고정하고 임시 인증 키를 메모리에서만 사용해 접속했다. Docker/Compose 설치와 GitHub 코드로 운영 이미지 재구축에 성공했다. 운영 터널은 새 서버에서 시작하지 않았다.

실제 새 호스트에서 아카이브 SHA285a71b checkout→prepare→유효 Compose AI disabled 확인→새 DB 복원→빈 bootstrap DB 보존/이름 전환→서비스 시작→보안 smoke4/4→새 로컬 백업/예약 CHECK_OK까지 성공했다. 원본 서버의 파일을 복구 중 다시 가져오지 않았다. 사용자5·작업1·비용0건, 활성 원복 계정/세션/예약/공개 작업/미디어/claim 모두0을 확인했다. 비용0건의 한계는 유지한다. 별도의 합성 관리자1개를 기존 대화형 CLI로 만들고 로그인200·관리자 overview200을 실제 확인했다. 암호는 임의 생성해 출력/저장소에 남기지 않았다.

Docker Compose2.40.3에서 `up --wait postgres redis media-init`는 정상 exit0의 일회성 media-init을 실패로 판정했다. 실패 대상을 보존하고 진단한 뒤 DB/Redis 대기와 일회성 초기화를 분리해 재개했다. 운영 Compose의 권한/의존성을 완화하지 않았다.

측정: 재개 시작 시 스냅샷 경과379.1초, 재개 다운로드→서비스/새 백업 검증12.61초, prepare 시작→최종167.38초(초기 실패·진단 포함), 인스턴스 생성→검증1331.9초(구현/대기 포함). 작은 데이터 드릴의 실측이며 보장 RPO/RTO 또는 실제 공개 전환 시간으로 쓰지 않는다. 목표 운영 주기는 일일 백업이며 검사 허용 나이는26시간이다.

마지막으로 서비스5개 실행·timer active·cloudflared inactive·복구 비밀 파일0600을 확인했다. 생성 이름/IP/용도 태그/비고정 주소를 대조한 뒤 임시 서버 삭제 API Succeeded를 확인했다. 이후 인스턴스 목록 부재와 기존 Sydney 서버 Running/54.66.36.80을 재확인했다. 임시 DB·추가 관리자·받아온 비밀 설정도 서버와 함께 제거됐다. S3/KMS와 IAM 역할은 실제 운영 설정으로 유지한다.

## 복구·전환 원칙

1. AWS 운영자 인증으로 S3 최신 유효 객체의 버전·KMS·크기·SHA를 확인하고 새 서버의0700 폴더/0600 파일로 전달한다. 원본 서버의 파일을 다시 읽어 복구에 보충하지 않는다.
2. 아카이브 SHA의 GitHub 코드를 checkout하고 새 recovery 표식에서 prepare한다. 원본 환경은 비공개로 보존하며 실행 환경은 AI disabled다.
3. PostgreSQL/Redis는 `up -d --wait postgres redis`로 대기하고 media-init은 `run --rm media-init`으로 별도 완료한다. 새 `factlens_restore_*` DB에 복구하고 계정 비활성·세션/예약 제거·결과/미디어 폐기와 비용 보존을 검사한다.
4. 새 호스트의 빈 bootstrap DB임을 확인한 뒤 이름을 보존해 바꾸고, 검증한 복구 DB를 `factlens`로 연결한다. 그 뒤에만 API/web/worker를 시작한다. 운영 호스트에서는 이 전환을 실행하지 않는다.
5. 실제 장애 전환 시 원본 호스트/터널을 먼저 격리해 서로 다른 두 DB로 트래픽이 분산되지 않게 한다. AWS 인증 SSH로 새 배포 공개키/지문·고정 IP·GitHub host/known_hosts·경보 대상/리전 연락처·백업 예약을 맞춘다. 리전이 다르면 기존 static IP를 옮길 수 없으므로 새 고정 IP와 GitHub 연결을 사용한다. 공개 도메인은 Cloudflare Tunnel을 사용하므로 SSH 주소 변경과 별개다.
6. [공식 설치 안내](https://developers.cloudflare.com/tunnel/features/locally-managed-tunnels/create-local-tunnel/)에 따라 cloudflared를 설치하고 보관한 token을 `/etc/cloudflared/token`에 root0600, unit을 `/etc/systemd/system/cloudflared.service`에 root0644로 설치한다. 현재 원본 버전은2026.10.1이다. 원본 격리·복구 검증 후에만 daemon-reload/enable/start하며 공개 health·실제 관리자 접근·감시를 재검증한다. 드릴에서는 바이너리 재설치/터널 활성화/공개 트래픽 전환을 실행하지 않았다. 복귀 시에도 새 터널을 먼저 멈추며 새 DB 쓰기가 있었다면 자동으로 과거 DB로 돌아가지 않는다.
7. 복구 계정은 모두 비활성이다. 신뢰된 운영자가 서버의 기존 `create-admin.py`를 대화형으로 실행해 새 관리자를 만든 뒤, 본인 확인 정책으로 기존 계정 복구를 진행한다. 비상 Bearer 우회는 만들지 않는다. 제공자 사용량/미정산 비용을 대조하기 전 AI를 켜지 않는다.

## 검증 범위와 잔여

DB 운영 상태와 배포 설정의 복구다. 삭제된 미디어·보고서가 돌아오는 무손실 미디어 복구가 아니다. AWS 계정/KMS 접근 상실, GitHub/이미지·패키지 저장소 동시 장애는 이번 단일 서버 장애 범위 밖이다. 실제 공개 트래픽 전환/원본 서버 중단은 드릴에서 하지 않는다. Strix 자동 유료 침투·전체 부하·실AI/연구 평가는 별도 후속이다.

추가 상시 과금 자원은 S3와 전용 KMS 키다. KMS 신규 키 기본 보관료는 월USD1이며 요청·향후 키 순환과 S3 사용량 과금은 별도다([AWS 가격](https://aws.amazon.com/kms/pricing/)). 청구 확정액 검증은 아니며 임시 서버는 위 삭제 결과로 정리했다.
