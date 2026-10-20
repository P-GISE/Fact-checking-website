#!/usr/bin/env python3
import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import http.client
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time

import recovery


ROOT = Path.home() / "factlens"
BACKUP_ROOT = Path.home() / "factlens-backups"
LOCK = Path.home() / ".factlens-deploy.lock"
STAMP = "%Y%m%dT%H%M%S%fZ"
DAILY = re.compile(r"daily-(\d{8}T\d{12}Z)-[a-z0-9_]{8}")
COMPLETE = "factlens-daily-v1\n"


def private_directory(path):
    info = path.lstat()
    if (not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o700
            or info.st_uid != os.getuid()):
        raise ValueError("PRIVATE_BACKUP_REQUIRED")


@contextmanager
def deployment_lock(path, timeout):
    import fcntl

    with os.fdopen(os.open(path, os.O_CREAT | os.O_WRONLY | os.O_NOFOLLOW, 0o600), "w") as handle:
        recovery.private_file(path)
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise RuntimeError("DEPLOYMENT_BUSY") from None
                time.sleep(min(1, remaining))
        yield


def target(root):
    marker = root / ".factlens-deploy-target"
    info = marker.lstat()
    if (root.is_symlink() or not root.is_dir() or not stat.S_ISREG(info.st_mode)
            or info.st_size > 64 or marker.read_text().strip() != "factlens-ai"):
        raise RuntimeError("WRONG_TARGET")


def disk_reserve(*paths):
    if any(shutil.disk_usage(path).free < 2 * 1024**3 for path in paths):
        raise RuntimeError("DISK_RESERVE_LOW")


def database_backup(folder):
    private_directory(folder)
    if {item.name for item in folder.iterdir()} != {"database.dump", "manifest.json"}:
        raise ValueError("INVALID_BACKUP")
    dump, manifest = folder / "database.dump", folder / "manifest.json"
    recovery.private_file(dump)
    recovery.private_file(manifest)
    if not 0 < dump.stat().st_size <= recovery.MAX_DUMP or manifest.stat().st_size > 4096:
        raise ValueError("INVALID_BACKUP")
    metadata = json.loads(manifest.read_text())
    if (not isinstance(metadata, dict) or metadata.get("version") != 1
            or metadata.get("bytes") != dump.stat().st_size
            or metadata.get("scope") != "database_only_ephemeral_media_not_backed_up"
            or metadata.get("sha256") != recovery.checksum(dump)):
        raise ValueError("INVALID_BACKUP")


def completed(folder):
    match = DAILY.fullmatch(folder.name)
    if not match:
        raise ValueError("INVALID_BACKUP")
    created = datetime.strptime(match[1], STAMP).replace(tzinfo=timezone.utc)
    private_directory(folder)
    if {item.name for item in folder.iterdir()} != {"database", "complete"}:
        raise ValueError("INVALID_BACKUP")
    marker = folder / "complete"
    recovery.private_file(marker)
    if marker.stat().st_size > 32 or marker.read_text() != COMPLETE:
        raise ValueError("INVALID_BACKUP")
    database_backup(folder / "database")
    return created


def retain(backup_root, now):
    private_directory(backup_root)
    for folder in backup_root.iterdir():
        try:
            created = completed(folder)
        except (OSError, ValueError):
            continue
        if now - created > timedelta(days=7):
            (folder / "database/database.dump").unlink()
            (folder / "database/manifest.json").unlink()
            (folder / "database").rmdir()
            (folder / "complete").unlink()
            folder.rmdir()


def backup(root, backup_root, lock, *, now=None):
    with deployment_lock(lock, 1800):
        now = now or datetime.now(timezone.utc)
        target(root)
        backup_root.mkdir(mode=0o700, exist_ok=True)
        private_directory(backup_root)
        disk_reserve(root, backup_root)
        env = os.environ.copy()
        for key in ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS",
                    "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH", "COMPOSE_PROFILES"):
            env.pop(key, None)
        result = subprocess.run(
            ["docker", "--host=unix:///var/run/docker.sock", "compose",
             "--project-name", "factlens", "--env-file", ".env.production",
             "-f", "compose.production.yaml", "ps", "-q", "postgres"],
            cwd=root, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
        if result.returncode:
            raise RuntimeError("BACKUP_COMMAND_FAILED")
        container = recovery.identifier(result.stdout.decode("ascii").strip())
        folder = Path(tempfile.mkdtemp(prefix="daily-" + now.astimezone(timezone.utc).strftime(STAMP) + "-",
                                       dir=backup_root))
        private_directory(folder)
        recovery.backup(container, "factlens", folder / "database")
        database_backup(folder / "database")
        disk_reserve(root, backup_root)
        recovery.write_private(folder / "complete", COMPLETE)
        completed(folder)
        retain(backup_root, now)
        return folder


def health(port=3300):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        connection.request("GET", "/api/health")
        with connection.getresponse() as response:
            body = response.read(4097)
            if response.status != 200 or len(body) > 4096:
                raise ValueError
            data = json.loads(body)
            if not isinstance(data, dict) or data.get("status") != "ready":
                raise ValueError
    except (OSError, ValueError, http.client.HTTPException):
        raise RuntimeError("HEALTH_NOT_READY") from None
    finally:
        connection.close()


def check(root, backup_root, lock, *, now=None):
    with deployment_lock(lock, 180):
        now = now or datetime.now(timezone.utc)
        target(root)
        private_directory(backup_root)
        disk_reserve(root, backup_root)
        fresh = False
        for folder in backup_root.iterdir():
            try:
                created = completed(folder)
            except (OSError, ValueError):
                continue
            if timedelta(0) <= now - created <= timedelta(hours=26):
                fresh = True
                break
        if not fresh:
            raise RuntimeError("BACKUP_MISSING_STALE_OR_INVALID")
        health()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Private daily DB backup and operational check.")
    parser.add_argument("action", choices=("backup", "check"))
    args = parser.parse_args(argv)
    try:
        {"backup": backup, "check": check}[args.action](ROOT, BACKUP_ROOT, LOCK)
    except Exception as error:
        code = str(error)
        safe = {"DEPLOYMENT_BUSY", "WRONG_TARGET", "DISK_RESERVE_LOW",
                "PRIVATE_BACKUP_REQUIRED", "BACKUP_COMMAND_FAILED",
                "BACKUP_MISSING_STALE_OR_INVALID", "HEALTH_NOT_READY"}
        print(code if code in safe else "OPERATION_FAILED", file=sys.stderr)
        return 1
    print("BACKUP_COMPLETE" if args.action == "backup" else "CHECK_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
