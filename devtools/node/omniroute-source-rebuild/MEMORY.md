# Linux 메모리 하한 중단과 직렬 module 빌드 후보

CI40360711740은 runtime-audit까지 통과한 뒤 free_memory_floor로 중단됐고 소유 Node 잔류0을 보고했다. 고정 출력에 정확한 최소 수치나 host/cgroup 분기가 없으므로 원인과 compile 진입 시점은 미확인이다. 이 실패를 heap OOM이나 guard 오탐으로 기록하지 않는다. 추가 빌드·CI는 실행하지 않았다.

## 읽기 전용 대조

- guard는 `/proc/meminfo`의 MemAvailable와 현재 cgroup 및 조상의 `memory.max - memory.current` 중 작은 값을 쓴다. MemFree만 보는 계산이 아니다.
- [Linux 공식 proc 문서](https://www.kernel.org/doc/html/latest/filesystems/proc.html)는 MemAvailable을 swap 없이 새 작업에 쓸 수 있는 메모리의 추정치로 설명하며 회수 가능한 cache 일부를 반영한다.
- [cgroup 공식 문서](https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html)는 memory.current에 descendant·page cache·anonymous·kernel 등의 사용이 포함된다고 설명한다. current 전체를 차감하는 쪽은 cache 회수를 미리 인정하지 않는 보수적인 경계다. 실제 실패가 이 분기였다는 증거는 아직 없다.
- [Node24.20.0 libuv Linux 소스](https://raw.githubusercontent.com/nodejs/node/v24.20.0/deps/uv/src/unix/linux.c)의 uv_get_free_memory도 MemAvailable을 우선 사용한다. uv_get_available_memory도 cgroup limit-current를 이용한다. guard의 계산을 잘못된 os.freemem 사용으로 단정할 근거는 없다.
- upstream은 이미 webpackMemoryOptimizations와 webpackBuildWorker를 켠다. [공식 메모리 문서](https://nextjs.org/docs/app/guides/memory-usage)의 이 두 권고를 다시 적용하는 것은 새 해결책이 아니다.
- [고정 Next16.4.1 build/index.ts](https://raw.githubusercontent.com/vercel/next.js/v16.4.1/packages/next/src/build/index.ts)의 experimental.cpus는 page-data/static worker 수를 정한다. 그 단계를 지나지 않았다면 cpus1의 효과를 보장할 수 없다. compiler worker도 각 compiler당1개를 순서대로 사용하며 parallel server compile/trace 기본값은 false다.

## 승인된 최소 후보

[고정 Next16.4.1 webpack-config.ts](https://raw.githubusercontent.com/vercel/next.js/v16.4.1/packages/next/src/build/webpack-config.ts)는 NEXT_WEBPACK_PARALLELISM을 읽어 Webpack module parallelism에 전달한다. 문서화된 안정 public API와는 구분하며 정확한 Next 버전에 근거한 빌드 전용 환경 설정으로 취급한다.

plan의 buildWebpackParallelism은 양의 정수1만 허용하고 full build 호출에만 NEXT_WEBPACK_PARALLELISM=1을 추가하는 후보를 준비한다. source/lock 추가 overlay나 runtime 코드 변경 없이 동시 module 작업을 제한한다. UI·native·trace·standalone·instrumentation·전체 production build를 유지하며 npm offline, heap8192, 사전12GiB, 하한3GiB, 내부30분은 그대로다. 빌드 시간이 늘 수 있으며 단일 heap의 최대 사용량을 줄인다고 보장하지 않는다.

새 trace나 raw 로그 대신 기존 sampling에서 초기/최소 여유 바이트·최소 시점 host/cgroup enum·관측된 소유 process 수만 고정 숫자로 보고한다. 관측하지 못한 값은 null/unverified로 표시하고,3초 sampling의 peak가 순간 실제 최고치라는 주장은 하지 않는다. 이 진단은 floor 계산이나 정리 결정을 바꾸지 않는다. Windows full build 동등 검증과 tool-ready는 여전히 미완료다.

후보 구현 검증: Windows Node24.20.0에서 기존53개와 추가2개를 포함한55/55 회귀 통과. 정확한 concurrency1 정책·잘못된 정책 거절과 host/cgroup/tie attribution·cache 회수 미선반영·기존 최소값 유지를 검사했다. process-guard의 중단·정리 구현, heap/floor/timeout과 lifecycle 소스는 수정하지 않았다. 수치 출력은 기존 memory 샘플을 재사용하며 실제 최소 수치·효과·Linux 전체 빌드 성공은 여전히 미확인이다. source override·의존성 변경·추가 CI·compile·push는 없다.
