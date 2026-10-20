#!/usr/bin/env python3
"""Bounded private disaster archive export and inactive clean-host preparation."""
import argparse
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tarfile
import tempfile
import threading

import operations
import recovery

ROOT = Path.home() / 'factlens'
OUTPUT = Path.home() / 'factlens-recovery'
MAX_TOTAL = 132 * 1024 * 1024
LIMITS = {'manifest.json': 8192, 'database/database.dump': recovery.MAX_DUMP,
          'database/manifest.json': 4096, 'config/production.env': 65536,
          'config/cloudflared.token': 8192, 'config/cloudflared.service': 65536}
ORIGINS = {'https://github.com/P-GISE/Fact-checking-website',
           'https://github.com/P-GISE/Fact-checking-website.git',
           'git@github.com:P-GISE/Fact-checking-website',
           'git@github.com:P-GISE/Fact-checking-website.git',
           'ssh://git@github.com/P-GISE/Fact-checking-website.git'}


def bounded_command(args, limit, *, cwd=None):
    # Drain at most limit+1 bytes; discard stderr without ever retaining secrets.
    with subprocess.Popen(args, cwd=cwd, stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as process:
        data = bytearray()
        def read():
            while len(data) <= limit:
                part = process.stdout.read(min(4096, limit + 1 - len(data)))
                if not part:
                    return
                data.extend(part)
            process.kill()
        reader = threading.Thread(target=read, daemon=True)
        reader.start()
        try:
            process.wait(timeout=10)
            reader.join(timeout=1)
            if reader.is_alive() or process.returncode or len(data) > limit:
                raise ValueError('COMMAND_FAILED')
        except BaseException:
            process.kill()
            process.wait()
            reader.join(timeout=1)
            raise
        return bytes(data)


def code_sha(root):
    origin = bounded_command(['git', 'remote', 'get-url', '--all', 'origin'], 512, cwd=root)
    if origin.decode('ascii').strip() not in ORIGINS:
        raise ValueError('WRONG_REPOSITORY')
    sha = bounded_command(['git', 'rev-parse', 'HEAD'], 128, cwd=root).decode('ascii').strip()
    if not re.fullmatch('[0-9a-f]{40}', sha):
        raise ValueError('INVALID_CODE_SHA')
    return sha


def read_private(path, limit):
    recovery.private_file(path)
    before = path.lstat()
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as source:
        after = os.fstat(source.fileno())
        if (before.st_ino, before.st_dev) != (after.st_ino, after.st_dev):
            raise ValueError('FILE_CHANGED')
        if after.st_size > limit:
            raise ValueError('SIZE_LIMIT')
        data = source.read(limit + 1)
    if not 0 < len(data) <= limit:
        raise ValueError('SIZE_LIMIT')
    return data


def write_private(path, data):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as out:
        out.write(data)


def fresh(created, now, max_age=timedelta(hours=26)):
    if created.utcoffset() != timedelta(0) or not timedelta(0) <= now-created <= max_age:
        raise ValueError('STALE_OR_FUTURE_ARCHIVE')


def validate_database(payloads, parent):
    with tempfile.TemporaryDirectory(prefix='.factlens-verify-', dir=parent) as name:
        folder = Path(name)
        for filename in ('database.dump', 'manifest.json'):
            write_private(folder / filename, payloads['database/' + filename])
        operations.database_backup(folder)


def export(root, backup_root, lock, *, now=None):
    with operations.deployment_lock(lock, 180):
        now = now or datetime.now(timezone.utc)
        operations.target(root)
        operations.private_directory(backup_root)
        candidates = []
        for folder in backup_root.iterdir():
            try:
                created = operations.completed(folder)
                fresh(created, now)
            except (OSError, ValueError, TypeError):
                continue
            candidates.append((created, folder))
        if not candidates:
            raise ValueError('NO_VALID_DAILY_BACKUP')
        created, folder = max(candidates)
        payloads = {name: read_private(folder / name, LIMITS[name])
                    for name in ('database/database.dump', 'database/manifest.json')}
        payloads['config/production.env'] = read_private(root / '.env.production', 65536)
        for name, path in [('cloudflared.token', '/etc/cloudflared/token'),
                           ('cloudflared.service', '/etc/systemd/system/cloudflared.service')]:
            key = 'config/' + name
            payloads[key] = bounded_command(['sudo', '-n', 'cat', path], LIMITS[key])
        validate_database(payloads, backup_root)
        manifest = {'version': 1, 'createdAt': created.isoformat().replace('+00:00', 'Z'),
                    'codeSha': code_sha(root), 'files': {
                        name: {'sha256': hashlib.sha256(body).hexdigest(), 'bytes': len(body)}
                        for name, body in payloads.items()}}
        payloads['manifest.json'] = json.dumps(manifest, separators=(',', ':')).encode()
        if sum(map(len, payloads.values())) > MAX_TOTAL:
            raise ValueError('SIZE_LIMIT')
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode='w:gz', format=tarfile.USTAR_FORMAT) as tar:
            for name, limit in LIMITS.items():
                body = payloads[name]
                if not 0 < len(body) <= limit:
                    raise ValueError('SIZE_LIMIT')
                member = tarfile.TarInfo(name)
                member.size, member.mode = len(body), 0o600
                tar.addfile(member, io.BytesIO(body))
        result = archive.getvalue()
        if len(result) > MAX_TOTAL:
            raise ValueError('SIZE_LIMIT')
        return result


def unpack(data):
    with gzip.GzipFile(fileobj=io.BytesIO(data)) as source:
        raw = source.read(MAX_TOTAL + 1)
    if len(raw) > MAX_TOTAL or len(raw) % 512:
        raise ValueError('SIZE_LIMIT')
    payloads = {}
    offset = 0
    # Read raw headers so tarfile cannot silently consume PAX/GNU extensions.
    while offset + 512 <= len(raw) and raw[offset:offset+512] != bytes(512):
        member = tarfile.TarInfo.frombuf(raw[offset:offset+512], 'utf-8', 'strict')
        name = member.name
        if (name not in LIMITS or name in payloads or member.type not in (tarfile.REGTYPE, tarfile.AREGTYPE)
                or member.linkname or member.mode != 0o600 or not 0 < member.size <= LIMITS[name]):
            raise ValueError('INVALID_ARCHIVE_MEMBER')
        start = offset + 512
        end = start + member.size
        offset = start + (member.size + 511) // 512 * 512
        if offset > len(raw) or any(raw[end:offset]):
            raise ValueError('INVALID_ARCHIVE')
        payloads[name] = raw[start:end]
    if set(payloads) != set(LIMITS) or len(raw)-offset < 1024 or any(raw[offset:]):
        raise ValueError('INVALID_ARCHIVE')
    return payloads


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('DUPLICATE_JSON_KEY')
        result[key] = value
    return result


def prepare(root, archive, output, *, now=None):
    now = now or datetime.now(timezone.utc)
    if root.is_symlink() or not root.is_dir() or os.path.lexists(root / '.factlens-deploy-target'):
        raise ValueError('WRONG_TARGET')
    marker = read_private(root / '.factlens-recovery-target', 64)
    if marker.strip() != b'factlens-drill':
        raise ValueError('WRONG_TARGET')
    env = root / '.env.production'
    if os.path.lexists(output) or os.path.lexists(env):
        raise ValueError('TARGET_EXISTS')
    payloads = unpack(read_private(archive, MAX_TOTAL))
    manifest = json.loads(payloads['manifest.json'], object_pairs_hook=unique_object)
    if (not isinstance(manifest, dict) or set(manifest) != {'version', 'createdAt', 'codeSha', 'files'}
            or type(manifest['version']) is not int or manifest['version'] != 1
            or not isinstance(manifest['files'], dict)
            or set(manifest['files']) != set(LIMITS) - {'manifest.json'}):
        raise ValueError('INVALID_MANIFEST')
    fresh(datetime.fromisoformat(manifest['createdAt'].replace('Z', '+00:00')), now,
          max_age=timedelta(days=7))
    if manifest['codeSha'] != code_sha(root):
        raise ValueError('WRONG_CODE_SHA')
    for name, metadata in manifest['files'].items():
        body = payloads[name]
        if (not isinstance(metadata, dict) or set(metadata) != {'sha256', 'bytes'}
                or type(metadata['bytes']) is not int or metadata['bytes'] != len(body)
                or metadata['sha256'] != hashlib.sha256(body).hexdigest()):
            raise ValueError('CHECKSUM_INVALID')
    validate_database(payloads, root.parent)
    output.mkdir(mode=0o700)
    operations.private_directory(output)
    for name in ('database', 'config'):
        (output / name).mkdir(mode=0o700)
    for name, body in payloads.items():
        write_private(output / name, body)
    operations.database_backup(output / 'database')
    # Publish the environment last; keep any failed private target for inspection.
    write_private(env, payloads['config/production.env'] + b'\nFACTLENS_AI_MODE=disabled\n')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest='action', required=True)
    actions.add_parser('export')
    actions.add_parser('prepare').add_argument('--archive', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.action == 'export':
            data = export(ROOT, operations.BACKUP_ROOT, operations.LOCK)
            sys.stdout.buffer.write(data)
        else:
            prepare(ROOT, args.archive, OUTPUT)
            print('PREPARED')
    except Exception:
        print('DISASTER_RECOVERY_FAILED', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
