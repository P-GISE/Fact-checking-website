#!/usr/bin/env bash
# Disposable, offline containers and synthetic fixtures only. Never runs the app server/DB.
set -Eeuo pipefail
[[ $# == 2 && $1 =~ ^[0-9a-f]{40}$ && ($2 == true || $2 == false) ]]
tag() { if [[ $2 == true ]]; then printf 'factlens-%s:%s' "$1" "$3"; else printf 'factlens-%s-ci-pilot:%s' "$1" "$3"; fi; }
api=$(tag api "$2" "$1"); worker=$(tag worker "$2" "$1"); web=$(tag web "$2" "$1")
options=(--rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges:true)
docker run "${options[@]}" --entrypoint node "$api" --check /app/apps/api/dist/server.js
docker run "${options[@]}" --entrypoint node "$api" --input-type=module \
  -e "await Promise.all(['express','multer','pg','redis','zod'].map(name=>import(name))); if(process.getuid()!==1000) process.exit(1)"
docker run "${options[@]}" --entrypoint sh "$api" -ec \
  'for tool in npm npx yarn; do if command -v "$tool" >/dev/null; then exit 1; fi; done; test ! -d /usr/local/lib/node_modules; test ! -d /app/node_modules/typescript; test ! -d /app/node_modules/vitest; test -f /app/apps/api/migrations/005_account_deletion.sql'
docker run "${options[@]}" --tmpfs /tmp:rw,noexec,nosuid,size=32m,mode=1777 --entrypoint nginx "$web" -t
docker run "${options[@]}" --entrypoint python "$worker" -c \
  'import os,ssl,sqlite3,psycopg,pydantic_core,jiter; assert os.getuid()==1000; assert ssl.OPENSSL_VERSION'
docker run "${options[@]}" --entrypoint sh "$worker" -ec \
  'tesseract --list-langs 2>/dev/null | grep -qx eng; tesseract --list-langs 2>/dev/null | grep -qx kor'
docker run "${options[@]}" --tmpfs /tmp:rw,noexec,nosuid,size=256m,mode=1777 \
  --mount "type=bind,source=$PWD/apps/worker/tests,target=/tests,readonly" -e PYTHONPATH=/app \
  --entrypoint python "$worker" -m pytest -q -p no:cacheprovider --basetemp=/tmp/pytest \
  /tests/test_media.py /tests/test_visual.py /tests/test_contracts.py
printf '%s\n' 'FACTLENS_RUNTIME_SMOKE=PASS: nonroot API imports/no npm, nginx config, worker native wheels/media/OCR/contracts; network disabled.'
