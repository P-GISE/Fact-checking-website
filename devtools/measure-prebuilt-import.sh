#!/usr/bin/env bash
# Source-only benchmark. Run only on an approved disposable standard Linux CI runner.
# Never runs applications, publishes an artifact, or connects to an existing Docker daemon.
set -Eeuo pipefail
umask 077
if [[ ${1:-} != --inside ]]; then
  [[ ($# == 4 || $# == 5) && -n $4 && $2 =~ ^[0-9a-f]{64}$ && $3 =~ ^[0-9a-f]{40}$ ]] || exit 64
  [[ -n ${RUNNER_TEMP:-} && ${GITHUB_ACTIONS:-} == true && ${GITHUB_REPOSITORY:-} == P-GISE/Fact-checking-website ]]
  [[ ${GITHUB_RUN_ID:-} =~ ^[0-9]+$ && ${GITHUB_RUN_ATTEMPT:-} =~ ^[0-9]+$ ]]
  [[ -f $1 && ! -L $1 ]]
  tool_dir=$4
  [[ ! -L $tool_dir && $(realpath "$tool_dir") == "$RUNNER_TEMP"/factlens-docker29.* ]]
  tool_dir=$(realpath "$tool_dir")
  verifier=$(realpath devtools/verify-pilot-docker29.py)
  profile=$(realpath devtools/docker29-pilot-profile.json)
  profile_kind=ci-pilot-only
  if [[ $# == 5 ]]; then
    [[ ! -L $5 && $(realpath "$5") == "$(realpath devtools/docker29-release-profile.json)" ]]
    profile=$(realpath "$5")
    profile_kind=ci-release-measurement-only
  fi
  tool_identity=$(python3 "$verifier" "$tool_dir" "$profile" "$profile_kind")
  benchmark=$(mktemp -d "$RUNNER_TEMP/factlens-import-measure.XXXXXXXX")
  trap 'sudo rm -rf -- "$benchmark"' EXIT
  printf '%s\n' "$tool_identity" > "$benchmark/tool-identities.json"
  [[ $(sha256sum "$1" | cut -d' ' -f1) == "$2" ]]
  sudo systemd-run --quiet --wait --pipe \
    --unit="factlens-import-measure-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}" \
    --property=MemoryAccounting=yes --property=MemoryMax=3G \
    --property=TasksMax=1024 --property=KillMode=control-group \
    bash "$(realpath "${BASH_SOURCE[0]}")" --inside "$benchmark" "$2" "$3" \
    "https://github.com/P-GISE/Fact-checking-website/actions/runs/$GITHUB_RUN_ID" "$(realpath "$1")" "$tool_dir" "$verifier" "$profile" "$profile_kind" "$GITHUB_RUN_ATTEMPT"
  # No policy is auto-approved or checked in from this measurement.
  sudo cat -- "$benchmark/measurement.json"
  exit 0
fi
[[ $# == 11 && $EUID == 0 && $3 =~ ^[0-9a-f]{64}$ && $4 =~ ^[0-9a-f]{40}$ && ${11} =~ ^[0-9]+$ ]] || exit 64
benchmark=$2; digest=$3; sha=$4; run_url=$5
[[ $benchmark == /home/runner/work/_temp/factlens-import-measure.* ||
   $benchmark == /home/runner/work/_temp/*/factlens-import-measure.* ]] || exit 64
socket="unix://$benchmark/docker.sock"
unset DOCKER_CONTEXT DOCKER_TLS DOCKER_TLS_VERIFY DOCKER_CERT_PATH DOCKER_HOST
readonly tool_dir=$7 tool_verifier=$8 tool_profile=$9 tool_kind=${10}
[[ ! -L $tool_dir && $tool_dir == /home/runner/work/_temp/factlens-docker29.* ]]
verify_tools() { python3 "$tool_verifier" "$tool_dir" "$tool_profile" "$tool_kind" "$benchmark/tool-identities.json" >/dev/null; }
verify_tools
export PATH="$tool_dir:/usr/sbin:/usr/bin:/sbin:/bin"
readonly docker_cli="$tool_dir/docker" ctr_cli="$tool_dir/ctr" dockerd_bin="$tool_dir/dockerd" containerd_bin="$tool_dir/containerd"
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
verify_tools
PATH="$tool_dir" "$containerd_bin" --config "$benchmark/containerd.toml" --address "$benchmark/containerd.sock" \
  --root "$benchmark/containerd-root" --state "$benchmark/containerd-state" > "$benchmark/containerd.log" 2>&1 &
containerd_pid=$!
for _ in {1..60}; do
  if timeout 3s "$ctr_cli" --address "$benchmark/containerd.sock" version >/dev/null 2>&1; then break; fi
  kill -0 "$containerd_pid" 2>/dev/null || exit 1
  sleep 1
done
timeout 3s "$ctr_cli" --address "$benchmark/containerd.sock" version >/dev/null 2>&1
printf '{}\n' > "$benchmark/daemon-config.json"
verify_tools
PATH="$tool_dir" "$dockerd_bin" --config-file="$benchmark/daemon-config.json" --host="$socket" --data-root="$benchmark/data" --exec-root="$benchmark/exec" \
  --containerd="$benchmark/containerd.sock" --containerd-namespace=moby --containerd-plugins-namespace=plugins.moby \
  --pidfile="$benchmark/docker.pid" --bridge=none --iptables=false \
  --ip-forward=false --ip-masq=false > "$benchmark/daemon.log" 2>&1 &
daemon_pid=$!
for _ in {1..90}; do
  if "$docker_cli" --host="$socket" info >/dev/null 2>&1; then break; fi
  kill -0 "$daemon_pid" 2>/dev/null || exit 1
  sleep 1
done
verify_tools
"$docker_cli" --host="$socket" info >/dev/null 2>&1
isolation_checker="$(dirname "$(realpath "${BASH_SOURCE[0]}")")/check-import-isolation.py"
python3 "$isolation_checker" "$benchmark" "$daemon_pid" "$containerd_pid" \
  "$dockerd_bin" "$containerd_bin" > "$benchmark/isolation-before.json"
"$docker_cli" --host="$socket" info --format '{"server_version":"{{.ServerVersion}}","driver":"{{.Driver}}","driver_status":{{json .DriverStatus}}}' > "$benchmark/runtime.json"
"$docker_cli" --host="$socket" version --format '{{json .Server.Components}}' > "$benchmark/components.json"
# gzip, client, daemon and daemon-owned containerd share this measured cgroup.
verify_tools
gzip -dc "$benchmark/images.tar.gz" | "$docker_cli" --host="$socket" load >/dev/null
for component in api worker web; do
  verify_tools
  "$docker_cli" --host="$socket" image inspect "factlens-$component:$sha" >/dev/null
  # Force first-use snapshot unpack without starting the app or running a migration.
  cid=$("$docker_cli" --host="$socket" create --pull=never --network none --entrypoint /bin/true "factlens-$component:$sha")
  [[ $cid =~ ^[0-9a-f]{64}$ ]]
  "$docker_cli" --host="$socket" rm -v "$cid" >/dev/null
done
python3 "$tool_verifier" "$tool_dir" "$tool_profile" "$tool_kind" "$benchmark/tool-identities.json" > "$benchmark/tool-identities-after.json"
python3 "$isolation_checker" "$benchmark" "$daemon_pid" "$containerd_pid" \
  "$dockerd_bin" "$containerd_bin" > "$benchmark/isolation-after.json"
cgroup=$(awk -F: '$1=="0" {print $3}' /proc/self/cgroup)
[[ $cgroup == /* && -f /sys/fs/cgroup$cgroup/memory.peak ]]
python3 - "$benchmark/measurement.json" "$digest" "$run_url" \
  "/sys/fs/cgroup$cgroup" "$sha" "${11}" "$9" <<'PY'
import hashlib,json,sys,os
from pathlib import Path
out,digest,url,folder,source_sha,attempt,profile_path=sys.argv[1:]; group=Path(folder)
profile=json.loads(Path(profile_path).read_text()) if profile_path else None
profile_digest=hashlib.sha256(json.dumps(profile,sort_keys=True,separators=(',',':')).encode()).hexdigest() if profile else None
events={}
for line in (group/'memory.events').read_text().splitlines():
    fields=line.split()
    if len(fields)!=2 or fields[0] in events or not fields[1].isascii() or not fields[1].isdecimal():
        raise SystemExit('Invalid or duplicate memory event counter')
    events[fields[0]]=int(fields[1])
if not {'oom','oom_kill'}<=events.keys():
    raise SystemExit('Required OOM event counters missing')
peak=int((group/'memory.peak').read_text())
runtime=json.loads((Path(out).parent/'runtime.json').read_text())
before=json.loads((Path(out).parent/'isolation-before.json').read_text())
after=json.loads((Path(out).parent/'isolation-after.json').read_text())
if before.get('verified') is not True or after.get('verified') is not True:
    raise SystemExit('Private process isolation proof required')
if events['oom'] or events['oom_kill'] or peak<=0:
    raise SystemExit('Import measurement failed: OOM or invalid accounting')
Path(out).write_text(json.dumps({'schema':1,'status':'measurement-requires-review',
    'method':'isolated-daemon-stream-load-v1','platform':'linux/amd64',
    'image_archive_sha256':digest,'peak_total_bytes':peak,'oom_events':0,
    'measurement_run_url':url,'disk_reserve_bytes':10*1024**3,
    'source_sha':source_sha,'measurement_run_id':int(url.rsplit('/',1)[1]),'measurement_run_attempt':int(attempt),
    'runtime_profile_sha256':profile_digest,'runtime_profile_kind':profile['kind'] if profile else None,
    'docker_server_version':runtime['server_version'],'docker_driver':runtime['driver'],
    'docker_driver_status':runtime['driver_status'],
    'docker_server_components':json.loads((Path(out).parent/'components.json').read_text()),
    'isolation_verified':True,'isolation_version':2,'isolation_before':before,'isolation_after':after,
    'tool_identity_version':1,
    'tool_identity_before':json.loads((Path(out).parent/'tool-identities.json').read_text()),
    'tool_identity_after':json.loads((Path(out).parent/'tool-identities-after.json').read_text()),
    'measurement_scope':'fresh-copy + private dockerd/containerd + stream-load + create/unpack; no app start',
    'kernel_release':os.uname().release,'kernel_architecture':os.uname().machine},sort_keys=True)+'\n')
PY
