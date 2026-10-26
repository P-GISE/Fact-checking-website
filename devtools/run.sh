#!/usr/bin/env bash
set -euo pipefail
fact_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
for executable in "$fact_root/.devtools/security-builder/bin/python" "$fact_root/.devtools/security-builder/Scripts/python.exe"; do
  if [[ -x "$executable" ]]; then exec "$executable" "$fact_root/devtools/run.py" "$@"; fi
done
printf 'devtools status=refused category=not_installed\n' >&2
exit 1
