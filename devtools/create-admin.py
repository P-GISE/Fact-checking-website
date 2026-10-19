#!/usr/bin/env python3
"""Create a new administrator on the local production Compose stack; never promote an existing user."""
import getpass
import json
import re
import subprocess
import sys
from pathlib import Path


def main():
    if not sys.stdin.isatty():
        raise SystemExit("Interactive terminal required for hidden password input")
    username = input("New administrator username: ").strip()
    if not re.fullmatch(r"[a-z0-9_-]{3,32}", username):
        raise SystemExit("Invalid username")
    password = getpass.getpass("New password (12-128 characters): ")
    if not 12 <= len(password.encode('utf-16-le')) // 2 <= 128:
        raise SystemExit("Invalid password length")
    if password != getpass.getpass("Confirm password: "):
        raise SystemExit("Passwords do not match")
    script = """import {encode,credentials} from './apps/api/dist/auth.js';
import {pool} from './apps/api/dist/db.js';
import {randomUUID} from 'node:crypto';
try {
 let raw='';for await (const chunk of process.stdin)raw+=chunk;
 const {username,password}=credentials.parse(JSON.parse(raw));
 const result=await pool.query("INSERT INTO app_users(id,username,password_hash,role) VALUES($1,$2,$3,'admin') ON CONFLICT(username) DO NOTHING",[randomUUID(),username,await encode(password)]);
 if(!result.rowCount)process.exitCode=2;
} catch {process.exitCode=1;} finally {await pool.end();}
"""
    result = subprocess.run(["docker", "compose", "--env-file", ".env.production", "-f", "compose.production.yaml", "exec", "-T", "api", "node", "--input-type=module", "-e", script], input=json.dumps({"username": username, "password": password}), text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=Path(__file__).resolve().parents[1])
    if result.returncode:
        raise SystemExit("Administrator not created. Check service readiness and use a new username; existing users are never promoted.")
    print("Administrator created. Sign in at /admin. Password was not printed.")


if __name__ == "__main__":
    main()
