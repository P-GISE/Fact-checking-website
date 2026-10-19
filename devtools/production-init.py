#!/usr/bin/env python3
"""Generate a new private deployment environment without printing its values."""
import os,secrets
from pathlib import Path
root=Path(__file__).resolve().parents[1]
path=root/'.env.production'
body='\n'.join(['# Private runtime settings; never commit or paste this file.',
 'FACTLENS_DB_PASSWORD='+secrets.token_hex(32),
 'FACTLENS_AI_MODE=disabled','OPENAI_API_KEY=','BRAVE_SEARCH_API_KEY=',''])
try:
 fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
except FileExistsError:
 raise SystemExit('Existing .env.production preserved; no values were read or changed.')
with os.fdopen(fd,'w') as output:output.write(body)
print('Created private .env.production (0600). AI remains disabled.')
