# FactLens 운영 보호 검증 (2026-10-20)

대상은 `P-GISE/Fact-checking-website`, Sydney Lightsail `factlens-ai`다. 사용자 승인 정책은 매일 한국시간03:00 백업·7일 보관·AWS 계정 이메일 경보다.

최종 운영 코드는 `0fda3421500ba1ab5116f31ef6c590f595717cdd`다. [최종 CI/실제 배포39442027195](https://github.com/P-GISE/Fact-checking-website/actions/runs/39442027195)의 API72/Worker237·타입/빌드·배포 회귀가 성공했다. 별도 고정 지문 SSH로 SHA 일치·CHECK_OK·timer active·계정 모드 보안 smoke4/4를 확인했다. 최종 문서는 [skip ci]로 게시하므로 문서 HEAD와 운영 코드 SHA를 구분한다.

## 확인한 운영 변경

- `factlens-ai-static-ip`를 생성해 연결했다. 고정 IPv4는 `54.66.36.80`이다.
- 기존 인증 콘솔에서 대조한 Ed25519 지문을 유지해 새 주소로 StrictHostKeyChecking SSH 접속에 성공했다. GitHub 호스트 변수와 production known_hosts Secret을 갱신했다. 개인키는 변경하거나 출력하지 않았다.
- 공개 HTTPS와 내부 health는 ready였다. Cloudflare Tunnel의 공개 주소는 유지된다.
- CPU 경보: 80% 이상, 5분 단위4개 중3개. 상태 검사 실패 경보: 1 이상, 연속2개(10분), 누락 데이터는 장애로 처리한다.
- 두 경보 모두 Email·ALARM/OK·notificationEnabled=true를 AWS에서 조회했다. 이메일 연락처는 Valid이며 시험 ALARM 요청 Succeeded 후 사용자가 실제 이메일 수신을 확인했다. 시험은 실제 장애 유발과 구분한다.

## 구현과 검증 진행

독립 리뷰의 잠금 경합 문제2개는 백업1800초·검사180초 대기와 잠금 획득 후 시각 계산으로 보완해 APPROVE를 받았다. Windows21개 통과/1개 skip 후 첫 CI39440470407에서 Linux 테스트용 잠금 파일0644 문제가 드러나 배포가 차단됐다. 실제 서버 잠금은0600이었다. 테스트 파일 생성 권한을0600으로 고친887d401을 게시하고 별도 Linux 임시 폴더에서22개 전부 통과를 직접 확인했다. 임시 폴더는 제거했다. 재실행은 [Actions39440989534](https://github.com/P-GISE/Fact-checking-website/actions/runs/39440989534)다.

Iron Laws MCP는 operations.py1파일/완료/passed:true·REVIEW3개였다. 두 continue는 유효하지 않은 백업을 보존하거나 신선한 백업으로 인정하지 않는 의도된 흐름이며 CLI 포괄 예외는 비밀값/SQL 출력을 차단한다. 이 판정은 전체 앱 보안 통과가 아니다. actionlint 문법 검사와 diff 검사도 통과했다.

`devtools/operations.py`와 systemd timer/service로 일일 DB 백업·7일 보관·무결성/권한·26시간 신선도·2GiB 디스크 여유·loopback health를 검증한다. 기존 recovery.py를 재사용하고 배포와 같은 잠금을 사용한다. 유효하고 소유권/권한이 일치하는 완료 daily 백업만7일 후 삭제하며 deploy 백업·불완전/이상 파일은 보존한다.

GitHub 감시는 고정 지문 SSH와 공개 HTTPS를 검사한다. 예약 실행은 기본 브랜치 main의 workflow가 필요하므로 동일 monitor.yml만 main에도 ec2d545로 게시했다. main/work workflow SHA256 일치를 확인했다. 앱 자동 배포는 work를 유지한다.

## 실제 운영 적용과 복원 결과

- [Actions39440989534](https://github.com/P-GISE/Fact-checking-website/actions/runs/39440989534): API72/Worker233·타입/빌드·배포 회귀·실제 배포 성공. 새 고정 IP에서 운영 SHA `887d40103798b12908740ff239b111038eb64ac8` 일치를 별도 SSH로 확인했다.
- systemd unit을 설치하고 timer enable/active·service Result=success/ExecMainStatus=0을 확인했다. 다음 실행은2026-10-20 18:00 UTC, 즉2026-10-21 03:00 KST다. 매일03:00 KST와 Persistent=true다.
- 첫 완료 백업은 `daily-20261020T144059157351Z-wyi8rgw4`다. 운영 check가 권한/무결성·신선도·health·디스크 검사를 모두 통과했다.
- 같은 서버의 새 PostgreSQL 컨테이너에 network=none·ports={}·메모리256MiB·CPU0.5·데이터 tmpfs를 지정했다. 운영 볼륨을 마운트하거나 앱을 연결하지 않았다.
- 실제 백업 복원과 비식별화·집계 검사는0.79초였다. 사용자5/작업1건 보존, 활성 계정0·세션0·예약0·claim/evidence/check/verdict0·접근 가능한 작업/미디어0을 확인했다. 비용 기록은 운영 원본0건이므로 해시 일치는 빈 기록 검증이며 실비용이 있는 운영 데이터 보존까지 입증하지 않는다. 작은 DB 복원 시간이며 전체 장애 복구 RTO가 아니다.
- 복원 성공 후 생성 당시 컨테이너 ID를 대조해 드릴 컨테이너/임시 볼륨을 제거했다. 이후 CHECK_OK를 재확인했다.
- FACTLENS_MONITOR_ENABLED=true와 [첫 main 감시 실행39441559528](https://github.com/P-GISE/Fact-checking-website/actions/runs/39441559528)의 실제 check 단계 성공을 확인했다. 매시7/22/37/52분 실행은 GitHub 예약 실행이므로 지연될 수 있다. Actions 실패 상태와 AWS 이메일 경보는 별개다. GitHub 계정의 실패 이메일 전달 설정은 이번에 검증하지 않았다.

서버 수동 확인 명령은 `cd ~/factlens && python3 devtools/operations.py check`, 백업은 `sudo systemctl start factlens-backup.service`, 예약 상태는 `systemctl list-timers factlens-backup.timer`다. 백업 경로나 dump 내용을 공개 로그에 출력하지 않는다.

후속 보안 smoke에서 모든 필수 헤더는 일치했으나, 과거 도구가 계정 모드의 미인증401을404/400으로 기대해 실패했다. 제품 접근 제한은 정상이며 도구에 명시적인 `--auth-mode account` 기대값을 추가했다. 실제 HTTP 회귀4개로 계정401 성공·인증 누락404/400 실패·기존 local 호환·필수 헤더 누락 실패를 확인했다. 최종 운영 실행4/4도 통과했다. Iron Laws 해당 도구1파일/완료/passed:true·REVIEW4개는 loopback 기본값·검사용 비허용 Origin·잘못된 URL/연결 실패의 안전 종료로 분류했다. 스캐너 지적0으로 표시하지 않는다.

## 한계

백업은 DB 전용이며 임시 미디어·세션·업로드 예약을 복원하지 않는다. 복구 계정은 비활성화하며 작업·미디어는 폐기 상태다. 같은 서버 디스크 백업은 서버/디스크 전체 손실에 대비한 외부 백업이 아니다. S3 등 외부 보관·전체 서버 재구축 훈련은 별도 후속이다. Strix 자동 유료 스캔·전체 침투/부하 검증은 실행하지 않았다.

AWS 시험 경보 동작은 [공식 test-alarm 문서](https://docs.aws.amazon.com/cli/latest/reference/lightsail/test-alarm.html)를 따른다.
