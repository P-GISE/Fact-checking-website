# FactLens bounded import 후보 — CI/운영 실행 전

## 확인됨

- 기준 운영 소스 `work/50881500256af0f20e707b313abf8d9a556d1fc8`; 격리 작업 트리에서 후보만 준비했다. commit/push/CI trigger/운영 변경은 하지 않았다.
- 기존 실제 운영 앱은 `7dda00cd…`다. 기존 guard는1536MiB 가용 메모리를 요구하며 이번 후보에서 바꾸지 않았다. import policy는 `unmeasured`, prebuilt 활성화는 OFF다.
- 기존 유효 CI40289571843은 fresh-copy+private Docker/containerd+stream load+3image create/unpack의 peak1,683,787,776bytes/OOM0을 관측했다. MemoryMax3GiB에서 얻은 값이며 필요한 resident memory의 하한으로 단정하지 않는다. 과거 격리 증명 없는 낮은 측정값은 재사용하지 않는다.
- 2026-10-26 10:46:41 UTC 기존 pinned SSH 읽기 전용 관측: S2 MemAvailable1,441,071,104bytes, MemTotal4,018,421,760bytes, swap0, disk free53,988,569,088bytes. 원래 build guard에 못 미친다. 이후 다른 검사 중의 메모리 수치를 이 baseline에 섞지 않는다.

## 추정 / 단일 후보의 목적

기존 peak에는 새 archive copy와 layer write의 file cache가 포함된다. 더 작은 cgroup 상한에서 커널 reclaim과 함께 같은 import가 성공할 수 있다는 **가설**을 시험한다. [Linux cgroup v2 공식 문서](https://docs.kernel.org/admin-guide/cgroup-v2.html#memory-interface-files)는 memory.max 도달 시 줄일 수 없으면 해당 cgroup의 OOM을 유발하며 memory.peak가 하위 프로세스까지 포함함을 설명한다. 실제 성공은 아직 관측하지 않았다.

## 후보 변경

1. 기존 source-only CI 측정 unit만 MemoryMax768MiB, MemorySwapMax0, RuntimeMaxSec600s로 제한한다. 생산 서버/일반 daemon/DB/앱의 자원 설정은 변경하지 않는다.
2. fresh archive copy **전** 실제 memory.max와 memory.swap.max를 확인하고 기록한다. 끝에서도 같은 limit·swap peak0·OOM0·total peak≤768MiB를 확인한다. memory.events와 선택한 anon/file/kernel 통계를 숫자로 남긴다.
3. private config/root/state/socket, daemon PID/exe hash/동일 cgroup 전후 증명, stream load, 세 이미지의 첫-use unpack, app start0은 유지한다. host containerd를 재사용하지 않는다.
4. CI profile/verifier와 결과 요약은 새 상한에 맞춘다. 누락/다른 cap/상한 초과/swap 사용 또는 증거 부재는 실패한다. 요약이 성공해도 full runtime equivalence와 production envelope approval은 false다.
5. Dockerfiles·앱 의존성·DB/migration·Compose·원본 build guard·publisher·배포 flags·정책 파일은 변경하지 않는다. 기존 PR-only workflow가 검토 후 이 후보를 한 번 실행할 수 있다. artifact/package 발행·운영 접속은 없다.

## 로컬 검증

- 수정 전 새 bounded 검증은 잘못된 입력7종을 성공으로 받아 실패했다(RED).
- 수정 후 import/isolation10개 중9통과·Linux scanner aggregation1skip, private Docker profile3통과, 기존 prebuilt gate18개 중17통과·Linux root ownership1skip이다.
- Bash 구문·git diff --check 통과. Windows 로컬에서는 실제 Linux cgroup/Docker import를 실행하지 않았다.
- Iron Laws MCP는 상대 `devtools/summarize-import-pilot.py`를 찾지 못했다. 현재 서버 mapping이 이 격리 checkout에 연결돼 있지 않아 스캔 완료로 기록하지 않는다. 새 도구 설치/서버 mapping 변경은 하지 않았다.

## CI 결과에 따라 가능한 판단

- 실패/OOM/swap/시간 초과/격리 불일치: 후보 실패로 기록하고 운영 경로는 그대로 둔다. 자동 상한 재시도·guard 축소·swap 추가·다른 서비스 중단은 없다.
- 성공: 해당 runner/profile/정확 archive가 관측한 cap에서 import를 완료했다는 근거만 된다. 커널/vendor/component 차이와 자원 reclaim 성능 차이는 남는다. 현재 S2에서 바로 배포 가능하다는 결론이 아니다.
- 768MiB+512MiB reserve=1,342,177,280bytes는 위 baseline보다98,893,824bytes만 작다. 이 계산에는 전환 중 새 앱/기존 앱의 중첩 사용량, migration/backup, 압축 해제 외 자원과 전체 runtime 교체의 여유를 아직 검증하지 않았다. 잔여 여유를 예약 용량처럼 취급하지 않는다.

## 운영 활성화 전 필수 후속

- 정확 CI source/profile/isolationV2/actual limits/OOM/swap/bundle provenance 독립 검토.
- `build-prebuilt.py`의 현재3args 호출과 pilot4번째 private tool 경로 미연결을 별도 연결·검증. 무효 과거 측정이나 status 문자열만 통과하지 않도록 production validator 강화.
- 실제 import 직전 MemAvailable·disk·기존 앱 증분·전체 stack 전환과 rollback 자원 검증. 기존 DB/volume/environment·migration bridge·보호 source 승인 경계 유지.
- 새 유료 자원 없이 해결할 수 없으면 service 이동/기존 자원 조정/용량 증설의 정확 영향·비용·rollback을 별도 제시한다. 이번 후보는 이를 승인하지 않는다.

## 영향·롤백

현재 후보는 로컬 source와 문서만 바꾼 상태다. 검토 전 push/CI 실행/발행/운영 반영은 하지 않는다. 향후 PR-only CI에서는 bounded unit 실패 시 자기 private 프로세스와 임시 폴더만 정리한다. 서버 rollback은 필요 없다. 후보 소스는 해당 diff를 되돌릴 수 있고 운영 앱/DB는 그대로 남는다. 이전 benchmark·운영 실패·과거 bundle/manifest 기록은 보존한다.
