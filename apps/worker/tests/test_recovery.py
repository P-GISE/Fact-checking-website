"""Operational recovery retains accounts/costs but never revives expiring media."""
import importlib.util
import json
import os
import subprocess
from pathlib import Path
from uuid import uuid4
import pytest

ROOT=Path(__file__).resolve().parents[3]

def module():
 spec=importlib.util.spec_from_file_location('recovery',ROOT/'devtools/recovery.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def test_restore_rejects_existing_live_database_and_modified_backup(tmp_path):
 m=module()
 with pytest.raises(ValueError,match='RESTORE_TARGET'):m.restore('factlens-postgres-1','factlens',tmp_path)


def test_real_database_recovery_discards_sessions_reports_and_preserves_costs(tmp_path):
 m=module();source='factlens_table_context_test';target='factlens_restore_'+uuid4().hex[:12]
 # The test source is disposable; production database factlens is never mutated.
 user,media,job,reservation=[str(uuid4()) for _ in range(4)]
 sql=f"""INSERT INTO app_users(id,username,password_hash) VALUES('{user}','recovery_{uuid4().hex[:8]}','test-hash');
 INSERT INTO app_sessions(token_hash,user_id) VALUES('recovery-test-{user}','{user}');
 INSERT INTO media(id,path,original_name,bytes,mime,owner_id) VALUES('{media}','/data/media/{media}/source.wav','owned.wav',5,'audio/wav','{user}');
 INSERT INTO jobs(id,media_id,consent,owner_id,status,result) VALUES('{job}','{media}',true,'{user}','completed','{{"private":"must not revive"}}');
 INSERT INTO usage_reservations(id,job_id,month,reserved_micros,actual_micros) VALUES('{reservation}','{job}','2026-10',100,50);"""
 m.sql('factlens-postgres-1',source,sql)
 try:
  bundle=tmp_path/'backup';m.backup('factlens-postgres-1',source,bundle)
  assert bundle.stat().st_mode&0o777==0o700
  assert (bundle/'database.dump').stat().st_mode&0o777==0o600
  m.restore('factlens-postgres-1',target,bundle)
  assert m.sql('factlens-postgres-1',target,f"SELECT count(*) FROM app_users WHERE id='{user}'").strip()==b'1'
  assert m.sql('factlens-postgres-1',target,'SELECT count(*) FROM app_sessions').strip()==b'0'
  assert m.sql('factlens-postgres-1',target,f"SELECT status||':'||(result IS NULL)::text FROM jobs WHERE id='{job}'").strip()==b'deleted:true'
  assert m.sql('factlens-postgres-1',target,f"SELECT actual_micros FROM usage_reservations WHERE id='{reservation}'").strip()==b'50'
  with pytest.raises(RuntimeError,match='RECOVERY_COMMAND_FAILED'):m.restore('factlens-postgres-1',target,bundle)
  (bundle/'database.dump').write_bytes(b'tampered')
  with pytest.raises(ValueError,match='CHECKSUM'):m.restore('factlens-postgres-1',target+'_bad',bundle)
 finally:
  m.sql('factlens-postgres-1','postgres',f'DROP DATABASE IF EXISTS {target}')
