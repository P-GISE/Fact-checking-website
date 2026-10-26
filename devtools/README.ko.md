# 기본 브랜치 개발도구 보안 구성

이 폴더는 default main의 개발도구 설정입니다. 운영 work 브랜치와 AWS 서비스·DB·DNS는 변경하지 않습니다. 2026-10-26 로컬 수정 후보이며 GitHub 반영·Linux CI 실행 전입니다.

## 현재 상태

| 도구 | 실행 경계 | 검증 상태 |
|---|---|---|
| Headroom0.41.0 [proxy,mcp] | repo .devtools/headroom + hash lock | Windows 실제 stdio 압축/정확복원, loopback proxy 합성 upstream1회 PASS |
| Strix1.7.0+pgise.security1 | 별도 .devtools/strix + hash lock | 실제 help/version·crypto/filelock 소비API PASS, 유료 보안검사 미실행 |
| Iron Laws1.7.0+pgise.security1 | 고정 공식source→별도 hash-locked build→별도 env | CLI 안전/MD5 취약fixture, MCP check·폴더밖거부 PASS |
| CodeGraph1.6.2 | npm lock의 플랫폼패키지 + bundled Node24 | 별도 임시 합성project index/query PASS, 저장소인덱스 생성0 |
| OmniRoute3.8.52 | 검증된 전체source build가 있어야 실행 | 아직 미완료, wrapper가 source_rebuild_pending으로 거부 |
| LazyCodex5.1.33 + 명시 security overlay | 공식 source/Bun/독립 build lock/설치 전체tree 검증 | 실제 bundle 재빌드·guarded help/version/합성 dry-run·Zod1001→1 PASS, harness 설치 미실행 |

전이 graph는 builder/headroom/strix/ironlaws의 *.lock.txt와 node/package-lock.json으로 고정합니다. 실제 hash-locked 환경 설치는 검사했지만 전체 install.sh의 외부 스킬 링크 설치와 Linux 런타임은 아직 검증하지 않았습니다. 과거 공유경로 /workspace/.devtools의 정상 기록을 현재 후보의 성공으로 간주하지 않습니다.

## 설치와 실행

Linux에서 Python3.12·uv0.12.9·Node24.20이 있는 환경을 사용합니다.

```bash
bash devtools/install.sh
source devtools/activate.sh
headroom --help
iron-laws check path/to/synthetic-project
```

기본 설치 경로는 이 저장소의 `.devtools`입니다. 기존 공유 `/workspace/.devtools`나 전역 Codex/LazyCodex 설정을 수정·삭제하지 않습니다. 도구별 venv를 나누고 builder도 별도로 잠급니다. npm은 npm ci를 사용합니다. CodeGraph 저장소 인덱스는 자동 생성하지 않습니다.

`.codex/config.toml`의 MCP 명령은 `devtools/run.sh`를 거칩니다. Headroom/Strix/Iron Laws는 명시 파생version·원본식별·전체설치 RECORD 해시를 확인한 후 실행합니다. 모델·provider·auth 설정은 추가하지 않습니다.

`start-services.py`는 OmniRoute 전체source build 검증 전에는 서비스 시작을 거부합니다. 기존 프로세스를 종료하지 않습니다. 새 프로세스의 원문 stdout·생성 키는 로그에 저장하지 않습니다. 키·state·env·rawlog를 artifact로 올리지 마세요.

## 명시적 Python 패키징 overlay

공식 PyPI 원본4wheel의 URL/SHA는 python-security-overlays.json에 있습니다. LiteLLM1.106.4의 FileLock<4 상한과 Strix1.7의 Crypto<49 상한은 검증된 플랫폼에서 명시 local-version으로 패치합니다. 원본code/native payload/ABI/플랫폼tag/기존LICENSE는 보존하고 metadata/RECORD/provenance만 바꿉니다. 도구가 원래 upstream version과 동일한 것처럼 표시하지 않습니다.

Iron Laws는 source commit2b98ecd687ed1e2aaedc13ff243f9a9a401fa4fa·tar SHA를 ironlaws-source.json에 고정했습니다. 원본source와 API는 바꾸지 않습니다. upstream wheel에 LICENSE가 누락돼 explicit local-version 패키징 overlay에 실제 source LICENSE·provenance를 포함합니다. build backend uv_build0.11.11도 hash lock으로 고정합니다. 파생wheel 바이너리는 Git에 커밋하지 않습니다.

`python -m scripts.security.compile_overlay_locks`는 builder 환경에서 실행해 Headroom/Strix lock을 갱신합니다. uv universal이 로컬wheel 한 플랫폼 hash만 넣는 문제를 보완해 실제검증한 Windows/Linux 두 hash를 기록합니다. hash검사를 끄거나 no-deps로 우회하지 않습니다.

## 실제 검사와 남은 문제

- 기본 security gate는 모든 devtools *.lock.txt와 npm lock을 검사합니다. 별도 bundled SBOM도 Trivy sbom으로 검사해 결과에 합칩니다.
- lazycodex-bundle.cdx.json은 실제 npm installer bundle SHA와 4개 내장component를 기록합니다. verify_bundled_inventory.py가 설치bundle과 일치하는지 확인합니다. 과거 Zod4.6.5/CVE-2023-54404 HIGH를 실제 검출했고, 공식 소스 재빌드 후 실제 번들 Zod4.6.6 및 전체 4개 component의 최종 SCA는 0입니다. npm audit0만으로 완료라 하지 않습니다.
- devtools-platform.yml은 공개 표준 Ubuntu24.04 runner에서 엄격설치/실제synthetic 소비검증을 준비한 후보입니다. 아직 trigger하지 않았습니다. 기존 앱 deploy flags는 유지합니다.
- Linux 파생wheel hash 설치·실제 MCP/CLI는 독립 CI 검증이 남았습니다. OmniRoute 전체sourcebuild는 아직 미완료입니다. LazyCodex의 Windows 소스 재빌드는 검증했으며 Linux 재빌드·동일지문 검증은 남아 있습니다.
- Headroom actual proxy test는 외부provider 대신 loopback 합성서버를 사용합니다. 실제 모델 추론·절감률은 검증하지 않았습니다. Strix 유료scan·Docker 모델·실제계정키 사용0입니다.

롤백은 default 개발도구 파일을 함께 revert하고 새 repo-local 환경만 재생성하는 것입니다. 기존 공유환경/운영서비스/데이터를 지우지 않습니다. 취약한 이전 도구를 안전하다고 복원실행하지 않습니다.

## LazyCodex 실제 소스 재빌드

`lazycodex-source-rebuild/plan.json`은 공식 source tag/commit7a752…와 tar SHA, 공식 Bun1.4.4의 Windows/Linux ZIP 및 공식 SHASUMS를 고정합니다. global Bun/Node 설치나 기존 harness/auth/model 경로는 바꾸지 않습니다. 공식 installer-only Bun.build script와 공식 source/body marker를 그대로 사용합니다.

원본 TS 소스는 수정하지 않았습니다. 별도 installer-only build-deps/package-lock.json이 실제 해석된 전이 7개를 고정합니다. Zod4.6.6을 포함하며 upstream full-workspace Bun lock을 소비했다고 가장하지 않습니다. 원본 regular source 파일 전체를 공식 tar와 비교하며, Windows 복사에서 제외한 문서 symlink3개는 plan에 명시했습니다. 허용되지 않은 추가 소스·외부 연결·변조 입력은 거부합니다.

실제 번들 안의 array 파서를 test-only exact-prefix copy에서 합성 입력으로 실행한 결과 기존 issues1001→수정후1이었습니다. 별도 Node API guard 아래 actual CLI help/version/합성 update--dry-run은 network/spawn 시도0, HOME/project 파일쓰기0으로 통과했습니다. 이 테스트는 실제 harness 설치나 유료 모델 호출을 하지 않습니다.

`install.py`는 기존 npm package 전체를 원래 tar의 SHA512·모든 파일과 비교한 후 bundle1개와 명시 provenance/license만 연결합니다. `verify.py`는 official body marker, receipt/input hashes, 원본 npm identity, CLI wrapper와 전체 설치tree까지 실행 전 확인합니다. 표시되는 upstream version5.1.33은 유지하되 stderr와 metadata에 security derivative를 명시합니다. upstream 원본인 척하지 않습니다.

최초 prototype은 컴파일/회귀는 통과했으나 Windows 임시 npm cache cleanup에서 exit1이었습니다. 원본/source/성공bundle/receipt를 보존하고 자기 임시cache만 정리한 뒤, full compile 반복 없이 전체 source·기존 compiled bundle·marker·실행 검증을 재확인하여 finalize했습니다. 새 receipt는 compile_repeated:false와 이전 attestation SHA를 명시합니다. 신규 recipe는 임시 HOME과 별도 repo cache를 나누고 cleanup 성공 뒤에만 ready receipt를 기록합니다.

일반 설치는 rebuild.py→install.py 순서입니다. 소스 재빌드 또는 build lock을 바꾸면 실제 bundle SBOM도 재생성·검토해야 합니다. byte/component 지문이 맞지 않는 SBOM은 검사에서 거부합니다. 생성 bundle·cache·원문로그는 Git에 올리지 않습니다. 공식 source LICENSE와 최종 dependency licenses는 로컬 derivative에 보존합니다.

## 2026-10-27 캐시 쓰기 경계 보완

독립 검토에서 기존 캐시의 junction/symlink 부모를 따라 외부에 먼저 쓰고 나중에 거부하는 결함을 실제 synthetic fixture로 확인했습니다. source/cache anchor·nested parent와 wheel intake에서도 재현했습니다. 수정 전 검토된50개 파일은 정확한 SHA whitelist로 별도 보존했습니다.

공통 cache_io는 cache anchor의 기존 상위 경로까지 lstat/reparse·containment를 확인한 뒤 mkdir/파일쓰기/atomic rename을 진행합니다. 새 파일은 O_EXCL과 가능한 플랫폼의 O_NOFOLLOW를 사용합니다. 캐시 안의 정상 파일과 기존 성공 bundle/receipt는 지우지 않았습니다. matching partial source는 기존 inode/mtime를 유지합니다. 같은 OS 계정/관리자가 동시에 경로를 교체하는 공격을 완전히 막는 lock이나 OS sandbox는 아닙니다.

실제 Windows junction negative 시험에서 외부 신규 파일·폴더0, 기존 sentinel 내용보존을 확인했습니다. source/dependency/artifact/installed parent와 wheel producer/intake가 같은 bounded I/O를 사용합니다. 분리된 source intake와 runtime intake helper의 SHA도 receipt에 묶습니다. 기존 bundle을 재컴파일하지 않고 전체 cached source·공식 marker·같은 실제 bundle·guarded CLI/dry-run을 다시 검증해 새 receipt에 연결했습니다. Linux 실제 CI는 독립 재검토 전 계속 보류합니다.


### 플랫폼 간 파생 wheel 재현성

파생 wheel은 원본 코드·native payload·LICENSE·WHEEL 태그와 복사한 ZIP entry 메타데이터를 보존합니다. 새 provenance, RECORD와 Iron Laws에 추가하는 LICENSE entry만 ZIP `create_system=0`, 1980-01-01 시각, 명시한 mode로 고정합니다. RECORD/LICENSE는 기존 wheel의 생성 방식과 같은 0664, provenance는 0644를 사용합니다. `create_system=0`은 ZIP 생성 메타데이터이며 실행 대상 OS나 wheel ABI 태그를 바꾸지 않습니다.

운영체제의 ZIP 기본값 0/3을 바꾸는 실제 repack/package_license 회귀시험이 있습니다. 실제 Windows·Linux upstream wheel 네 개에서도 두 기본값으로 생성한 여덟 결과가 모두 기존 lock의 SHA256과 같았습니다. 따라서 이 수정으로 패키지 버전·원본 payload·양 플랫폼 lock hash는 바뀌지 않습니다. 첫 Linux CI는 Headroom hashlock 단계에서 실패했지만 원문 오류를 저장하지 않았으므로, 재현된 메타데이터 결함을 그 실패의 유일 원인으로 단정하지 않습니다. 수정 후 실제 Linux 설치는 별도 검토·실행 결과로 확인합니다.
