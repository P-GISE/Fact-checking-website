#!/usr/bin/env python3
"""Read-only resource and configuration gate before touching existing services."""
import os,shutil,stat,subprocess,sys
from pathlib import Path

def check(root:Path,memory:int|None=None,disk:int|None=None)->list[str]:
 errors=[]
 if memory is None:
  values={line.split(':')[0]:int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines()}
  memory=values['MemAvailable']
 if disk is None:disk=shutil.disk_usage(root).free
 if memory<1536*1024*1024:errors.append('RESOURCE_MEMORY: at least 1.5 GiB available required; preserve existing services')
 if disk<10*1024**3:errors.append('RESOURCE_DISK: at least 10 GiB free required for images, database and bounded uploads')
 env=root/'.env.production'
 if not env.is_file() or env.is_symlink():errors.append('PRIVATE_ENV_REQUIRED')
 elif stat.S_IMODE(env.stat().st_mode)!=0o600 or env.stat().st_uid!=os.getuid():errors.append('PRIVATE_ENV_OWNER_MODE_REQUIRED')
 return errors

def main():
 root=Path(__file__).resolve().parents[1];errors=check(root)
 if not errors:
  result=subprocess.run(['docker','compose','--env-file','.env.production','-f','compose.production.yaml','config','--quiet'],cwd=root,capture_output=True)
  if result.returncode:errors.append('COMPOSE_CONFIG_INVALID: validate variable names locally; do not print resolved configuration')
 if errors:
  for error in errors:print(error)
  return 1
 print('Read-only preflight passed; this does not prove service or recovery readiness.');return 0
if __name__=='__main__':sys.exit(main())
