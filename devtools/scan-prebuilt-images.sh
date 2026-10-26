#!/usr/bin/env bash
# Local daemon only; downloads public vulnerability databases, never uploads source/images.
set -Eeuo pipefail
umask 077
[[ $# == 1 && $1 =~ ^[0-9a-f]{40}$ ]]
scan=$(mktemp -d "${RUNNER_TEMP:?}/factlens-image-sca.XXXXXXXX")
trap 'rm -rf -- "$scan"' EXIT
curl --fail --silent --show-error --location --retry 3 --proto '=https' --tlsv1.2 \
  https://github.com/aquasecurity/trivy/releases/download/v0.76.1/trivy_0.76.1_Linux-64bit.tar.gz -o "$scan/tool.tar.gz"
printf '%s  %s\n' c7cbe3137fb8a48a17574bede3dd6beb16742d1e9772929940fc90082c39d9c0 "$scan/tool.tar.gz" | sha256sum --check --status
tar -xzf "$scan/tool.tar.gz" -C "$scan" trivy
overall=0
for component in api worker web; do
  status=0
  "$scan/trivy" image --image-src docker --config='' --ignorefile='' --scanners vuln \
    --pkg-types os,library --severity HIGH,CRITICAL --exit-code 1 --offline-scan \
    --disable-telemetry --skip-version-check --timeout 10m --no-progress \
    --format json --output "$scan/$component.json" "factlens-$component:$1" \
    > "$scan/$component.log" 2>&1 || status=$?
  if python3 - "$scan/$component.json" "$status" "$component" <<'PY'
import json,sys
from pathlib import Path
report,status,component=sys.argv[1:]
if int(status) not in (0,1) or not Path(report).is_file():raise SystemExit('Image scanner error')
rows=json.loads(Path(report).read_text()).get('Results',[])
os_packages=sum(len(row.get('Packages') or []) for row in rows if row.get('Class')=='os-pkgs')
libraries=sum(len(row.get('Packages') or []) for row in rows if row.get('Class')=='lang-pkgs')
findings=[entry for row in rows for entry in row.get('Vulnerabilities') or []]
print(json.dumps({'component':component,'os_packages':os_packages,'library_packages':libraries,
    'critical':sum(row.get('Severity')=='CRITICAL' for row in findings),
    'high':sum(row.get('Severity')=='HIGH' for row in findings)}))
for entry in findings:
    print(json.dumps({'component':component,**{key:entry.get(key) for key in
          ('VulnerabilityID','PkgName','InstalledVersion','FixedVersion','Severity')}}))
if not os_packages or (component in ('api','worker') and not libraries):
    raise SystemExit('Image package coverage UNASSESSED')
if int(status) or findings:raise SystemExit('Image High/Critical blocks publication')
PY
  then :
  else overall=1
  fi
done
exit "$overall"
