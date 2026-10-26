#!/usr/bin/env bash
# Source-only benchmark. Run only on an approved disposable standard Linux CI runner.
# Never runs applications, publishes an artifact, or connects to an existing Docker daemon.
set -Eeuo pipefail
umask 077
if [[ ${1:-} != --inside ]]; then
  [[ ($# == 3 || $# == 4) && $2 =~ ^[0-9a-f]{64}$ && $3 =~ ^[0-9a-f]{40}$ ]] || exit 64
  [[ -n ${RUNNER_TEMP:-} && ${GITHUB_ACTIONS:-} == true && ${GITHUB_REPOSITORY:-} == P-GISE/Fact-checking-website ]]
  [[ ${GITHUB_RUN_ID:-} =~ ^[0-9]+$ && ${GITHUB_RUN_ATTEMPT:-} =~ ^[0-9]+$ ]]
  [[ -f $1 && ! -L $1 ]]
  tool_dir=${4:-}; verifier=''; profile=''
  if [[ -n $tool_dir ]]; then
    [[ ! -L $tool_dir && $(realpath "$tool_dir") == "$RUNNER_TEMP"/factlens-docker29.* ]]
    tool_dir=$(realpath "$tool_dir")
    verifier=$(realpath devtools/verify-pilot-docker29.py)
    profile=$(realpath devtools/docker29-pilot-profile.json)
    python3 "$verifier" "$tool_dir" "$profile"
  fi
  benchmark=$(mktemp -d "$RUNNER_TEMP/factlens-import-measure.XXXXXXXX")
  trap 'sudo rm -rf -- "$benchmark"' EXIT
  [[ $(sha256sum "$1" | cut -d' ' -f1) == "$2" ]]
  sudo systemd-run --quiet --wait --pipe \
    --unit="factlens-import-measure-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}" \
    --property=MemoryAccounting=yes --property=MemoryMax=3G \
    --property=TasksMax=1024 --property=KillMode=control-group \
    bash "$(realpath "${BASH_SOURCE[0]}")" --inside "$benchmark" "$2" "$3" \
    "https://github.com/P-GISE/Fact-checking-website/actions/runs/$GITHUB_RUN_ID" "$(realpath "$1")" "$tool_dir" "$verifier" "$profile"
  # No policy is auto-approved or checked in from this measurement.
  sudo cat -- "$benchmark/measurement.json"
  exit 0
fi
[[ $# == 9 && $EUID == 0 && $3 =~ ^[0-9a-f]{64}$ && $4 =~ ^[0-9a-f]{40}$ ]] || exit 64
benchmark=$2; digest=$3; sha=$4; run_url=$5
[[ $benchmark == /home/runner/work/_temp/factlens-import-measure.* ||
   $benchmark == /home/runner/work/_temp/*/factlens-import-measure.* ]] || exit 64
socket="unix://$benchmark/docker.sock"
unset DOCKER_CONTEXT DOCKER_TLS DOCKER_TLS_VERIFY DOCKER_CERT_PATH DOCKER_HOST
if [[ -n $7 ]]; then
  [[ ! -L $7 && $7 == /home/runner/work/_temp/factlens-docker29.* ]]
  python3 "$8" "$7" "$9"
  export PATH="$7:/usr/sbin:/usr/bin:/sbin:/bin"
fi
# Copy inside the measured cgroup: fresh output page cache is included conservatively.
cp --reflink=never -- "$6" "$benchmark/images.tar.gz"
[[ $(sha256sum "$benchmark/images.tar.gz" | cut -d' ' -f1) == "$digest" ]]
daemon_pid=''
containerd_pid=''
cleanup() {
  if [[ -n $daemon_pid ]]; then kill "$daemon_pid" 2>/dev/null || true; wait "$daemon_pid" 2>/dev/null || true; fi
  if [[ -n $containerd_pid ]]; then kill "$containerd_pid" 2>/dev/null || true; wait "$containerd_pid" 2>/dev/null || true; fi
}
trap cleanup EXIT
printf 'version = 2\ndisabled_plugins = ["io.containerd.grpc.v1.cri", "io.containerd.nri.v1.nri"]\n' > "$benchmark/containerd.toml"
containerd --config "$benchmark/containerd.toml" --address "$benchmark/containerd.sock" \
  --root "$benchmark/containerd-root" --state "$benchmark/containerd-state" > "$benchmark/containerd.log" 2>&1 &
containerd_pid=$!
for _ in {1..60}; do
  if timeout 3s ctr --address "$benchmark/containerd.sock" version >/dev/null 2>&1; then break; fi
  kill -0 "$containerd_pid" 2>/dev/null || exit 1
  sleep 1
done
timeout 3s ctr --address "$benchmark/containerd.sock" version >/dev/null 2>&1
printf '{}\n' > "$benchmark/daemon-config.json"
dockerd --config-file="$benchmark/daemon-config.json" --host="$socket" --data-root="$benchmark/data" --exec-root="$benchmark/exec" \
  --containerd="$benchmark/containerd.sock" --containerd-namespace=moby --containerd-plugins-namespace=plugins.moby \
  --pidfile="$benchmark/docker.pid" --bridge=none --iptables=false \
  --ip-forward=false --ip-masq=false > "$benchmark/daemon.log" 2>&1 &
daemon_pid=$!
for _ in {1..90}; do
  if docker --host="$socket" info >/dev/null 2>&1; then break; fi
  kill -0 "$daemon_pid" 2>/dev/null || exit 1
  sleep 1
done
docker --host="$socket" info >/dev/null 2>&1
isolation_checker="$(dirname "$(realpath "${BASH_SOURCE[0]}")")/check-import-isolation.py"
python3 "$isolation_checker" "$benchmark" "$daemon_pid" "$containerd_pid" \
  "$(command -v dockerd)" "$(command -v containerd)" > "$benchmark/isolation-before.json"
docker --host="$socket" info --format '{"server_version":"{{.ServerVersion}}","driver":"{{.Driver}}","driver_status":{{json .DriverStatus}}}' > "$benchmark/runtime.json"
docker --host="$socket" version --format '{{json .Server.Components}}' > "$benchmark/components.json"
# gzip, client, daemon and daemon-owned containerd share this measured cgroup.
gzip -dc "$benchmark/images.tar.gz" | docker --host="$socket" load >/dev/null
for component in api worker web; do
  docker --host="$socket" image inspect "factlens-$component:$sha" >/dev/null
  # Force first-use snapshot unpack without starting the app or running a migration.
  cid=$(docker --host="$socket" create --pull=never --network none --entrypoint /bin/true "factlens-$component:$sha")
  [[ $cid =~ ^[0-9a-f]{64}$ ]]
  docker --host="$socket" rm -v "$cid" >/dev/null
done
python3 "$isolation_checker" "$benchmark" "$daemon_pid" "$containerd_pid" \
  "$(command -v dockerd)" "$(command -v containerd)" > "$benchmark/isolation-after.json"
cgroup=$(awk -F: '$1=="0" {print $3}' /proc/self/cgroup)
[[ $cgroup == /* && -f /sys/fs/cgroup$cgroup/memory.peak ]]
python3 - "$benchmark/measurement.json" "$digest" "$run_url" \
  "/sys/fs/cgroup$cgroup" <<'PY'
import json,sys,os
from pathlib import Path
out,digest,url,folder=sys.argv[1:]; group=Path(folder)
events=dict(line.split() for line in (group/'memory.events').read_text().splitlines())
peak=int((group/'memory.peak').read_text())
runtime=json.loads((Path(out).parent/'runtime.json').read_text())
before=json.loads((Path(out).parent/'isolation-before.json').read_text())
after=json.loads((Path(out).parent/'isolation-after.json').read_text())
if before.get('verified') is not True or after.get('verified') is not True:
    raise SystemExit('Private process isolation proof required')
if int(events.get('oom',0)) or int(events.get('oom_kill',0)) or peak<=0:
    raise SystemExit('Import measurement failed: OOM or invalid accounting')
Path(out).write_text(json.dumps({'schema':1,'status':'measurement-requires-review',
    'method':'isolated-daemon-stream-load-v1','platform':'linux/amd64',
    'image_archive_sha256':digest,'peak_total_bytes':peak,'oom_events':0,
    'measurement_run_url':url,'disk_reserve_bytes':10*1024**3,
    'docker_server_version':runtime['server_version'],'docker_driver':runtime['driver'],
    'docker_driver_status':runtime['driver_status'],
    'docker_server_components':json.loads((Path(out).parent/'components.json').read_text()),
    'isolation_verified':True,'isolation_version':2,'isolation_before':before,'isolation_after':after,
    'measurement_scope':'fresh-copy + private dockerd/containerd + stream-load + create/unpack; no app start',
    'kernel_release':os.uname().release,'kernel_architecture':os.uname().machine},sort_keys=True)+'\n')
PY
