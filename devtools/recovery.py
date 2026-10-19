#!/usr/bin/env python3
"""Private database backup and recovery to a NEW database, with ephemeral data discarded.

Only use trusted operator-created backups. Media is deliberately not backed up.
AI must remain disabled after recovery until provider usage has been reconciled.
"""
import argparse,hashlib,json,os,re,stat,subprocess
from pathlib import Path

MAX_DUMP=128*1024*1024

def identifier(value):
 if not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}',value):raise ValueError('INVALID_IDENTIFIER')
 return value

def command(container,args,data=None,output=None):
 env=os.environ.copy()
 for key in ('DOCKER_HOST','DOCKER_CONTEXT','DOCKER_TLS','DOCKER_TLS_VERIFY','DOCKER_CERT_PATH'):env.pop(key,None)
 try:
  result=subprocess.run(['docker','--host=unix:///var/run/docker.sock','exec','-i',identifier(container),*args],env=env,input=data,stdout=output or subprocess.PIPE,stderr=subprocess.PIPE,timeout=60)
 except (OSError,subprocess.TimeoutExpired):raise RuntimeError('RECOVERY_COMMAND_FAILED') from None
 if result.returncode:raise RuntimeError('RECOVERY_COMMAND_FAILED')
 return result.stdout

def sql(container,database,statement):
 return command(container,['psql','-X','-U','factlens','-d',identifier(database),'-v','ON_ERROR_STOP=1','-At'],statement.encode())

def checksum(path):
 h=hashlib.sha256()
 with path.open('rb') as source:
  for part in iter(lambda:source.read(1024*1024),b''):h.update(part)
 return h.hexdigest()

def private_file(path):
 info=path.lstat()
 if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode)!=0o600 or info.st_uid!=os.getuid():raise ValueError('PRIVATE_BACKUP_REQUIRED')

def write_private(path,body):
 with os.fdopen(os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'w') as out:out.write(body)

def backup(container,database,folder):
 identifier(database);folder=Path(folder);folder.mkdir(mode=0o700)
 dump=folder/'database.dump'
 with os.fdopen(os.open(dump,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'wb') as out:
  command(container,['pg_dump','-U','factlens','-d',database,'-Fc','--no-owner','--no-acl','--exclude-table-data=public.app_sessions','--exclude-table-data=public.upload_leases'],output=out)
 if not 0<dump.stat().st_size<=MAX_DUMP:raise ValueError('BACKUP_SIZE_LIMIT')
 write_private(folder/'manifest.json',json.dumps({'version':1,'sha256':checksum(dump),'bytes':dump.stat().st_size,'scope':'database_only_ephemeral_media_not_backed_up'}))

def restore(container,target,folder):
 if not re.fullmatch(r'factlens_restore_[a-z0-9_]{1,40}',target):raise ValueError('RESTORE_TARGET_MUST_BE_NEW_ISOLATED_DATABASE')
 folder=Path(folder)
 if folder.is_symlink() or stat.S_IMODE(folder.stat().st_mode)!=0o700 or folder.stat().st_uid!=os.getuid():raise ValueError('PRIVATE_BACKUP_REQUIRED')
 dump=folder/'database.dump';manifest=folder/'manifest.json'
 private_file(dump);private_file(manifest)
 if manifest.stat().st_size>4096 or not 0<dump.stat().st_size<=MAX_DUMP:raise ValueError('BACKUP_SIZE_LIMIT')
 metadata=json.loads(manifest.read_text())
 if metadata.get('version')!=1 or metadata.get('bytes')!=dump.stat().st_size or metadata.get('sha256')!=checksum(dump):raise ValueError('BACKUP_CHECKSUM_INVALID')
 # createdb refuses existing databases. No DROP or overwrite path exists.
 command(container,['createdb','-U','factlens','-O','factlens',target])
 with dump.open('rb') as source:
  command(container,['pg_restore','-U','factlens','-d',target,'--no-owner','--no-acl','--single-transaction'],data=source.read())
 sql(container,target,"""BEGIN;
 ALTER TABLE app_users ADD COLUMN IF NOT EXISTS deleted_at timestamptz;
 UPDATE app_users SET username='restored_'||id::text,password_hash='!',deleted_at=now();
 DELETE FROM app_sessions;
 DELETE FROM upload_leases;
 UPDATE jobs SET status='deleted',deleted_at=now(),expires_at=now(),version=version+1,result=NULL,error=NULL;
 DELETE FROM claims;
 UPDATE media SET path='/discarded/'||id::text,original_name='discarded',expires_at=now();
 COMMIT;""")

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('action',choices=['backup','restore']);parser.add_argument('--container',required=True);parser.add_argument('--database',required=True);parser.add_argument('--directory',required=True,type=Path)
 args=parser.parse_args()
 try:
  if args.action=='backup':backup(args.container,args.database,args.directory)
  else:restore(args.container,args.database,args.directory)
 except Exception:
  raise SystemExit('Recovery operation failed; no credential or SQL output printed. Preserve the isolated target for inspection.')
 print('Operation completed. Media is not restored; keep AI disabled until billing reconciliation.')
