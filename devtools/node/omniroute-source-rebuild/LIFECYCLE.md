# 고정 upstream lifecycle 입력과 생성물 경계

상태: 로컬 합성 회귀 후보, root 검토 대기. 실제 추가 빌드·Linux CI·배포는 실행하지 않았다. 앞선 CI40347550728의 native-sqlite 이후 assertion 원인을 해결했다고 확정하지 않는다.

| 단계와 고정 hook | 원본 입력 | 생성물·검증 |
|---|---|---|
| pristine | canonical commit/tree의 모든 tracked raw bytes와 package.json/package-lock.json overlay 두 개 | npm 실행 전에 기존 `.env`, `.build`, `dist`, 임의 ignored/untracked 파일 모두 거절 |
| npm ci → postinstall | `.env.example`, 고정 native/module 설치와 postinstall 스크립트 | `.env`는 전체 template와 일치하며 blank MACHINE_ID_SALT 한 줄의 정해진 생성 형식만 허용. 값은 출력하지 않고 hash 봉인 |
| postinstall runtime copies | root node_modules의 sql.js·node-machine-id 및 두 SLM seed가 모두 설치된 경우 해당 manifest dependency closure | `dist/node_modules`에 지정된 package만 허용하고 원본 package tree와 복제본 digest 일치 요구. 임의 dist 파일 거절 |
| installed | 전체 node_modules의 설치 직후 seal, 원본 CLI digest | source 원본·설치 seal·복제본·환경 파일과 attempt nonce/plan 연결 검증. `.source` 등 compiler 출력은 이 단계에서 부재 요구. 재사용 cache의 임의 env 허용 없음 |
| prebuild → check-native-deps | 설치된 native 의존성 | 검사만 수행 |
| full build → build-next-isolated | 고정 Next/MDX·config·docs·원본 source | `.build/next` 출력, `.source`의 browser.ts/dynamic.ts/server.ts/source.config.mjs 네 파일, pinned Next의 정확한 next-env.d.ts 선언을 새 built 단계에서 봉인 |
| generate-global-error-messages | config/i18n.json과 원본 locale JSON | tracked 67개 JSON은 독립 재계산에서 Git 원문과 모두 동일했다. 생성물 예외로 처리하지 않고 byte 불변 검증 유지 |
| Linux native build | 고정 node-gyp12.4.0·lock integrity·binding.gyp·transparent.c | native/build 전용 출력에 symlink/special file은 거절한다. Release/transparent.node runtime hash와 compiler auxiliary tree digest를 구분하며 standalone 복제본 일치 요구 |
| postbuild/colocate | standalone·고정 worker/module | `.build/next/standalone` 안의 복제·esbuild 결과만 기존 빌드 영역으로 취급 |
| package-cli/prepublish | 검사된 원본 bin/omniroute.ts·원본 CLI·esbuild·plugin source/config/lock | 원본 CLI는 cache에 배타적으로 보존. tracked bin/omniroute.mjs 한 파일만 generated digest로 인계. plugin/dist는 index.js/index.d.ts 두 파일만 허용; plugin/node_modules는 upstream이 제거하므로 최종 부재 요구. 다른 tracked/lock 변경은 계속 거절 |
| prepublish assemble | standalone·고정 MITM/worker/docs/native 복제 | 최종 dist와 native runtime 복제본을 검증. root와 plugin의 lock 기반 production audit 각각 통과해야 함 |
| final | 위 원본 및 생성물 전체 | source 전체·dist·lifecycle metadata digest를 attempt/platform/Node/plan과 guard attestation에 연결. 사용자 verify와 smoke는 lifecycle receipt 필수 |

node-gyp은 루트 lock의 12.4.0 및 integrity를 사용한다. full build 직전 설치 package version/bin과 실제 `.bin/node-gyp` 경로가 그 고정 package 안인지 검사하고 기존 전체 node_modules seal을 유지한다. full build 명령에만 `npm_config_offline=true`를 더해 npx의 registry fallback을 막는다. Next 기능·native 기능·UI·instrumentation·trace·standalone을 제외하지 않는다. npm 오프라인 설정은 node-gyp 자체의 고정 Node 헤더 다운로드나 Next의 비 npm 네트워크 접근을 차단하는 방화벽이 아니다. plugin packaging 설치에는 이 설정을 확장하지 않는다.

[공식 node-gyp12.4.0](https://raw.githubusercontent.com/nodejs/node-gyp/v12.4.0/lib/build.js)은 Python symlink를 build/node_gyp_bins에 만들고 make 종료 후 제거한다. 잔존 외부 symlink를 따라 읽거나 예외로 허용하지 않는다. Makefile에 들어간 절대경로도 내용은 출력하지 않고 digest만 취급한다. 정상 Linux native 결과가 없거나 복제본이 다르면 후보는 실패한다.

합성 fixture는 pristine→installed→built→packaged를 순서대로 검증하고 기존 guard의 정당 생성물 거절과 인계 후 통과를 함께 확인한다. 기존 env, 임의 key/파일, 1byte 변경, valid salt의 사후 변경, 조기 compiler/CLI/plugin 출력, 원본 lock 변경, nonce 변경, CLI 원본 metadata 변조, 외부 compiler symlink, local node-gyp 경로/버전 변경은 거절한다. 동일 OS 관리자가 코드와 증거를 함께 바꾸는 공격에 대한 불변 서명은 아니다.
