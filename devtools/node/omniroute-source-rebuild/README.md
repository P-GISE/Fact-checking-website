# OmniRoute 공식 소스 보안 재빌드 검증 후보

이 폴더는 공개 upstream OmniRoute v3.8.52의 고정 commit, lock patch와 일반 빌드·프로세스·receipt 검증 코드만 포함한다. FactLens 제품 코드나 비공개 프로젝트 자료를 가져오지 않았다. 기존 설치기·MCP·라우팅·운영 배포와 연결하지 않는다.

현재 상태는 **검토 대기**다. Windows full Webpack 4096/6144는 heap 부족, full Turbopack 4096은 메모리 하한에서 중단됐다. 다른 Node 종료와의 인과관계는 미확정이다. Linux 실제 빌드와 CLI 검증은 아직 실행하지 않았다. 기존 도구의 미완료 차단은 유지한다.

## 실행 경계

- 전용 일회성 공개 표준 ubuntu-24.04 runner, Node 24.20.0, Python 3.12, read-only GitHub token, checkout 자격증명 미보존. 사용자 secrets·모델 호출·cache upload·artifact upload 없음.
- workflow PR 경로 필터 또는 수동 실행만 사용한다. main push 배포나 기존 보안 gate는 변경하지 않는다. 실행 전 workflow 자체의 별도 검토가 필요하다.
- 명시 profile `linux-webpack-8192-20261026`: 공식 정상 full Webpack 8192MB. UI·instrumentation·standalone·trace·production guard를 제외하지 않는다. 기존 upstream typecheck 우회 설정 때문에 전체 타입검사 성공을 의미하지 않는다.
- host 및 cgroup 조상 한도를 반영한 실제 여유 12GiB 미만이면 시작하지 않는다. 실행 중 여유 3GiB 하한, 내부 30분·job 40분 제한. 새 session/group만 TERM→bounded KILL→reap 검사한다.
- 관측된 live birth anchor 없이 group 연속성이 끊기면 미확인 프로세스를 죽이지 않고 remaining/unresolved로 실패한다. persistent Linux에서 완전 정리를 보증하지 않으며 일회성 runner 폐기가 마지막 경계다.
- source/archive/lock·전체 runtime source와 dependency tree·dist를 hash 검증한다. 완료 guard attestation은 attempt/execution nonce/profile/Node/platform/plan/runtime/dist에 연결된다. builder 내부 pending 검사로 사용자 verify/smoke 승인을 대체할 수 없다.
- 원문 build/startup 로그를 저장·출력하지 않고 고정 결과 metadata만 출력한다. HOME/DATA_DIR·생성 키·소스·bundle·원문 receipt는 업로드하지 않는다. 성공해도 기존 설치 dist를 교체하지 않는다.

## 명령

저장소 루트에서 `node --test devtools/node/omniroute-source-rebuild/*.test.mjs`로 합성 회귀를 실행한다. Linux 실제 한 번의 빌드는 workflow의 profile 환경에서 `guarded-linux-build.mjs` → `smoke.mjs` → `rebuild.mjs --verify` 순서다. smoke는 실행 전에 완료 guard와 입력을 검증하고, 마지막 verify는 실제 smoke 통과까지 요구한다. fresh cache만 허용하고 실패 후 자동 재시도는 없다. 임시 cache는 저장소 루트 `.tools/omniroute-security-build`에 생긴다.

합성 회귀는 H1 orphan/late child/PID 재사용·불확실 ownership 차단, H2 CLI/import/dependency 변조와 stale receipt/attestation 거절, TCP ECONNREFUSED 확인을 포함한다. 전체 tree seal 검사 시간은 실제 큰 트리에서 미측정이며 source 내부 정상 쓰기도 보수적으로 거절한다. 동일 OS 관리자에 대한 불변 서명은 아니다. ONNX 추가 CUDA/TensorRT 다운로드는 공식 skip 정책 범위로 제한되며 모델 추론은 검증하지 않는다.

Windows 전용 과거 adapter와 시험은 재현·회귀용으로 포함하지만 추가 로컬 full build 실행 승인이 아니다. plan의 overlay 식별자는 기존 고정 공개 dependency patch 식별자이며 제품 설정을 담지 않는다.

## 첫 실제 Linux CI 결과와 진단 보완 후보

2026-10-26 PR16의 run40341107075는 Linux 합성 회귀40/40을 통과했지만 실제 build step26초 후 `build_failed`, 소유 Node잔류0, exit1로 실패했다. smoke는 실행되지 않았다. 원래 guard는 child 출력을 폐기하고 stage/category를 ephemeral 파일에만 보관했으므로 이 실행의 구체 실패 지점은 확인할 수 없다. 이를 heap/전체 compile 실패로 추정하지 않는다. 보안 gate run40341106954 성공은 OmniRoute build 성공과 별개다.

후속 후보는 guard의 원문 미보존 정책을 유지하면서 고정 allowlist의 마지막 통과 stage와 실패 stage/category/0~255 exitcode만 출력한다. 줄4096자를 넘거나 파싱/enum 검증에 실패한 내용은 버리고 독립 stdout/stderr 경계를 유지한다. 기존 메모리·heap·timeout·소유권·완료 검증 경계는 바꾸지 않았다. 추가 빌드/CI 재실행은 없으며 workflow/수정본 검토를 기다린다. 진단 합성3개를 추가한 Windows 회귀43/43 통과는 Linux 실제 빌드 성공을 의미하지 않는다.

진단은 builder가 출력한 UUIDv4 executionId가 현재 guard attempt nonce와 일치할 때만 채택한다. stale/missing/partial/악성 enum JSON과 비밀 marker가 요약에 들어오지 않는 회귀를 포함하며 기존 failure.json을 출력하지 않는다. nonce는 진단 연결용이며 악의적인 동일 프로세스에 대한 암호학적 신뢰 경계는 아니다.

## Archive 원본 내용 동등성 확인과 canonical 후보

두 번째 Linux CI40342761651은 source-pin 다음 contract assertion에서 중단됐다. 코드는 이 구간의 archive SHA 검사를 지목하며 전체 compile 진입 증거는 없다. 같은 shallow 공식 commit에서 ambient autocrlf=true는 기존 Windows archive SHA3d8ff6...9395/843151360bytes를 재현하고 false는53b014...e4ec/834549760bytes를 만들었다. Git의 archive 변환은 [공식 archive.c](https://github.com/git/git/blob/v2.55.0/archive.c)의 convert_to_working_tree 경로와 [공식 설정 문서](https://git-scm.com/book/en/v2/Customizing-Git-Git-Configuration)에 근거한다. [archive 문서](https://git-scm.com/docs/git-archive)는 tar.umask 및 export 속성 영향을 설명한다.

독립 Python 표준 tarfile streaming 감사 `audit-archive-content.py SOURCE`는 canonical tar의 원본26001개 파일을 fixed Git tree의 mode/path/blob 원문과 모두 비교했다. 활성 export-ignore/export-subst는0, 추출/원문 출력0이다. canonical tar SHA는53b014bcf694e1d8416b792d0304f3411598141dcd60f51fdb0f7d891fe0e4ec, raw-content manifest SHA는7bb6c2bed545b7b844854a382b6825cebdbe32b8c5a2957fa1a10f6a2ae15098이다.

새 후보는 command-local core.autocrlf=false/core.eol=lf/tar.umask=0002와 replacement objects 금지를 강제하고 고정 commit/tree b2f3332f645ad60de52f12a4a484eb288693f0ea를 확인한 뒤 canonical SHA 하나만 허용한다. 이전 Windows SHA는 plan의 historical 필드와 이전 commit/evidence에 보존한다. 기존 tracked raw bytes·허용2개 overlay·설치 seal·plan/receipt/attempt 연결은 그대로다. 다양한 ambient autocrlf/eol/umask에서도 synthetic canonical archive 동일, commit/tree 변조 거절과 기존 파일1byte변조·stale plan/receipt 거절을 포함한45/45 회귀가 Windows에서 통과했다. 실제 source build·추가 Linux CI는 실행하지 않았으며 root 검토 대기다.
