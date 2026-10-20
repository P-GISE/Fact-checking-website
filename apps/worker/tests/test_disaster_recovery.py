import contextlib
import gzip
import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tarfile
import tempfile
import types
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[3]
NOW = datetime(2026, 10, 21, tzinfo=timezone.utc)
SHA = 'a' * 40


class DisasterRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue((REPO / 'devtools/disaster_recovery.py').is_file(),
                        'bounded disaster recovery tool is missing')
        self.enterContext(patch.object(sys, 'path', [str(REPO / 'devtools'), *sys.path]))
        self.dr = importlib.import_module('disaster_recovery')
        self.real_command = self.dr.bounded_command
        self.real_sha = self.dr.code_sha
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)
        self.root = self.home / 'factlens'
        self.root.mkdir(mode=0o700)
        self.backups = self.home / 'factlens-backups'
        self.backups.mkdir(mode=0o700)
        self.output = self.home / 'factlens-recovery'
        self.lock = self.home / '.factlens-deploy.lock'
        self.modes = {}
        self.owners = {}
        if os.name == 'nt':
            real_lstat = Path.lstat
            def lstat(path):
                info = real_lstat(path)
                mode = self.modes.get(path, 0o700 if stat.S_ISDIR(info.st_mode) else 0o600)
                return os.stat_result((stat.S_IFMT(info.st_mode) | mode, info.st_ino,
                    info.st_dev, info.st_nlink, self.owners.get(path, 1000), info.st_gid,
                    info.st_size, info.st_atime, info.st_mtime, info.st_ctime))
            self.enterContext(patch.object(Path, 'lstat', lstat))
            self.enterContext(patch.object(os, 'getuid', return_value=1000, create=True))
            self.enterContext(patch.object(os, 'O_NOFOLLOW', 0, create=True))
            self.enterContext(patch.dict(sys.modules, {'fcntl': types.SimpleNamespace(
                LOCK_EX=2, LOCK_NB=4, flock=lambda *_: None)}))
        self.write(self.root / '.factlens-deploy-target', b'factlens-ai\n')
        self.write(self.root / '.env.production', b'PASSWORD=synthetic-secret\n')
        self.enterContext(patch.object(self.dr, 'code_sha', return_value=SHA))
        self.enterContext(patch.object(self.dr, 'bounded_command', side_effect=lambda args, limit, **kw:
            b'synthetic-token' if args[-1] == '/etc/cloudflared/token' else b'[Service]\n'))
        self.daily(NOW - timedelta(hours=1))

    def write(self, path, data):
        path.write_bytes(data)
        path.chmod(0o600)
        return path

    def daily(self, when, dump=b'synthetic-dump'):
        folder = self.backups / ('daily-' + when.strftime(self.dr.operations.STAMP) + '-abcdefgh')
        folder.mkdir(mode=0o700)
        db = folder / 'database'
        db.mkdir(mode=0o700)
        self.write(db / 'database.dump', dump)
        self.write(db / 'manifest.json', json.dumps({'version': 1, 'bytes': len(dump),
            'sha256': hashlib.sha256(dump).hexdigest(),
            'scope': 'database_only_ephemeral_media_not_backed_up'}).encode())
        self.write(folder / 'complete', b'factlens-daily-v1\n')
        return folder

    def export(self):
        return self.dr.export(self.root, self.backups, self.lock, now=NOW)

    def clean(self):
        (self.root / '.factlens-deploy-target').unlink()
        (self.root / '.env.production').unlink()
        self.write(self.root / '.factlens-recovery-target', b'factlens-drill\n')

    def prepare(self, data):
        archive = self.write(self.home / 'archive.tar.gz', data)
        return self.dr.prepare(self.root, archive, self.output, now=NOW)

    def members(self, data):
        with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as tar:
            return [(m, tar.extractfile(m).read()) for m in tar]

    def repack(self, entries):
        out = io.BytesIO()
        with tarfile.open(fileobj=out, mode='w:gz', format=tarfile.USTAR_FORMAT) as tar:
            for member, data in entries:
                member.size = len(data)
                tar.addfile(member, io.BytesIO(data))
        return out.getvalue()

    def test_roundtrip_exact_members_and_private_inactive_output(self):
        data = self.export()
        self.assertEqual({m.name for m, _ in self.members(data)}, {'manifest.json',
            'database/database.dump', 'database/manifest.json', 'config/production.env',
            'config/cloudflared.token', 'config/cloudflared.service'})
        self.clean()
        self.prepare(data)
        self.assertEqual((self.root / '.env.production').read_bytes(),
                         b'PASSWORD=synthetic-secret\n\nFACTLENS_AI_MODE=disabled\n')
        self.assertEqual((self.output / 'database/database.dump').read_bytes(), b'synthetic-dump')
        self.dr.operations.database_backup(self.output / 'database')
        self.dr.operations.private_directory(self.output)
        for path in self.output.rglob('*'):
            if path.is_file(): self.dr.recovery.private_file(path)
        self.assertEqual((self.output / 'config/cloudflared.token').read_bytes(), b'synthetic-token')
        with self.assertRaises(Exception): self.prepare(data)

    def test_latest_valid_complete_skips_corrupt_newer_daily(self):
        bad = self.daily(NOW)
        (bad / 'database/database.dump').write_bytes(b'corrupt')
        self.assertEqual(dict((m.name, b) for m, b in self.members(self.export()))[
            'database/database.dump'], b'synthetic-dump')

    def test_rejects_bad_tar_and_metadata_before_writes(self):
        original = self.members(self.export())
        self.clean()
        variants = [b'garbage', self.repack(original)[:-8]]
        for field, value in [('version', 2), ('createdAt', (NOW-timedelta(days=8)).isoformat()),
                             ('createdAt', (NOW+timedelta(seconds=1)).isoformat()), ('codeSha', 'b'*40),
                             ('files', {})]:
            entries = self.members(self.repack(original))
            metadata = json.loads(entries[0][1]); metadata[field] = value
            entries[0] = (entries[0][0], json.dumps(metadata).encode())
            variants.append(self.repack(entries))
        variants.append(self.repack(original + [original[1]]))
        variants.append(self.repack(original[:-1]))
        for name, kind in [('../escape', tarfile.REGTYPE), ('unknown', tarfile.REGTYPE),
                           ('config/cloudflared.token', tarfile.SYMTYPE)]:
            entries = self.members(self.repack(original))
            entries[-2][0].name = name; entries[-2][0].type = kind
            variants.append(self.repack(entries))
        entries = self.members(self.repack(original)); entries[-1] = (entries[-1][0], b'changed')
        variants.append(self.repack(entries))
        for data in variants:
            with self.subTest(size=len(data)), self.assertRaises(Exception): self.prepare(data)
            self.assertFalse(self.output.exists())
            self.assertFalse((self.root / '.env.production').exists())

    def test_targets_existing_env_and_permissions_fail_closed(self):
        data = self.export()
        with self.assertRaises(Exception): self.prepare(data)
        self.clean()
        for path in [self.root / '.factlens-recovery-target', self.home / 'archive.tar.gz']:
            self.write(self.home / 'archive.tar.gz', data)
            path.chmod(0o644); self.modes[path] = 0o644
            with self.assertRaises(Exception): self.dr.prepare(self.root, self.home/'archive.tar.gz', self.output, now=NOW)
            path.chmod(0o600); self.modes[path] = 0o600
        self.write(self.root / '.env.production', b'preserve')
        with self.assertRaises(Exception): self.prepare(data)
        self.assertEqual((self.root / '.env.production').read_bytes(), b'preserve')
        self.assertFalse(self.output.exists())

    def test_export_limits_stale_future_public_env_and_no_partial_stdout(self):
        for now in [NOW + timedelta(hours=26), NOW - timedelta(hours=2)]:
            with self.assertRaises(Exception): self.dr.export(self.root,self.backups,self.lock,now=now)
        env = self.root / '.env.production'
        env.chmod(0o644); self.modes[env] = 0o644
        with self.assertRaises(Exception): self.export()
        env.chmod(0o600); self.modes[env] = 0o600
        with patch.object(self.dr, 'MAX_TOTAL', 10), self.assertRaises(Exception): self.export()
        output, errors = io.StringIO(), io.StringIO()
        with patch.object(self.dr, 'export', side_effect=RuntimeError('SQL password dump')), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            self.assertEqual(self.dr.main(['export']), 1)
        self.assertEqual(output.getvalue(), '')
        self.assertEqual(errors.getvalue(), 'DISASTER_RECOVERY_FAILED\n')

    def test_real_process_output_limit_failure_and_timeout(self):
        command = [sys.executable, '-c']
        self.assertEqual(self.real_command(command + ["print('ok', end='')"], 2), b'ok')
        for script in ["print('x'*10000)", "import sys; sys.stderr.write('secret'); sys.exit(1)",
                       "import time; time.sleep(20)"]:
            with self.subTest(script=script), self.assertRaises(Exception):
                self.real_command(command + [script], 10)

    def test_git_origin_and_sha_contract(self):
        for origin, sha, valid in [
                (b'https://github.com/P-GISE/Fact-checking-website.git\n', (SHA+'\n').encode(), True),
                (b'https://github.com/other/repo.git\n', SHA.encode(), False),
                (b'https://github.com/P-GISE/Fact-checking-website.git\n', b'bad', False)]:
            def command(args, limit, *, cwd=None):
                self.assertEqual(cwd, self.root)
                if args == ['git', 'remote', 'get-url', '--all', 'origin']:
                    return origin
                self.assertEqual(args, ['git', 'rev-parse', 'HEAD'])
                return sha
            with patch.object(self.dr, 'bounded_command', side_effect=command):
                if valid:
                    self.assertEqual(self.real_sha(self.root), SHA)
                else:
                    with self.assertRaises(ValueError): self.real_sha(self.root)

    def test_inner_database_manifest_and_extensions_rejected(self):
        entries = self.members(self.export())
        self.clean()
        metadata = json.loads(entries[0][1])
        for index, (member, body) in enumerate(entries):
            if member.name == 'database/manifest.json':
                inner = json.loads(body); inner['sha256'] = '0'*64
                body = json.dumps(inner).encode()
                entries[index] = (member, body)
                metadata['files'][member.name] = {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}
        entries[0] = (entries[0][0], json.dumps(metadata).encode())
        with self.assertRaises(Exception): self.prepare(self.repack(entries))
        self.assertFalse(self.output.exists())
        for kind in (tarfile.XHDTYPE, tarfile.GNUTYPE_LONGNAME, tarfile.LNKTYPE, tarfile.DIRTYPE):
            entries[1][0].type = kind
            with self.assertRaises(Exception): self.prepare(self.repack(entries))
        self.assertFalse((self.root / '.env.production').exists())

    def test_payload_compressed_and_expanded_size_bounds(self):
        data = self.export()
        entries = self.members(data)
        for member, body in entries:
            oversized = tarfile.TarInfo(member.name)
            oversized.mode = 0o600
            oversized.size = self.dr.LIMITS[member.name] + 1
            hostile = gzip.compress(oversized.tobuf() + bytes(1024))
            with self.subTest(name=member.name), self.assertRaises(Exception): self.dr.unpack(hostile)
        self.clean()
        with patch.object(self.dr, 'MAX_TOTAL', len(data)-1), self.assertRaises(Exception):
            self.prepare(data)
        with patch.object(self.dr, 'MAX_TOTAL', 1024), self.assertRaises(Exception):
            self.dr.unpack(gzip.compress(bytes(1025)))
        self.assertFalse(self.output.exists())
        self.write(self.root / '.factlens-deploy-target', b'factlens-ai')
        self.write(self.root / '.env.production', b'x' * 65537)
        with self.assertRaises(Exception): self.export()

    def test_export_lock_and_tunnel_command_boundaries(self):
        calls = []
        @contextlib.contextmanager
        def lock(path, timeout):
            self.assertEqual((path, timeout), (self.lock, 180))
            calls.append('locked')
            yield
        def command(args, limit, **kw):
            self.assertEqual(calls[0], 'locked')
            self.assertEqual(args[:3], ['sudo', '-n', 'cat'])
            expected = {'/etc/cloudflared/token': 8192,
                        '/etc/systemd/system/cloudflared.service': 65536}
            self.assertEqual(limit, expected[args[3]])
            calls.append(args[3])
            return b'x' * limit
        with patch.object(self.dr.operations, 'deployment_lock', lock), \
                patch.object(self.dr, 'bounded_command', side_effect=command):
            self.assertTrue(self.export().startswith(b'\x1f\x8b'))
        self.assertEqual(len(calls), 3)
        with patch.object(self.dr, 'bounded_command', return_value=b'x' * 65537), self.assertRaises(Exception):
            self.export()

    def test_cli_binary_export_prepared_and_fixed_paths(self):
        for name, value in [('ROOT', self.root), ('OUTPUT', self.output)]:
            self.enterContext(patch.object(self.dr, name, value))
        self.enterContext(patch.object(self.dr.operations, 'BACKUP_ROOT', self.backups))
        self.enterContext(patch.object(self.dr.operations, 'LOCK', self.lock))
        class Clock(datetime):
            @classmethod
            def now(cls, tz=None):
                return NOW
        self.enterContext(patch.object(self.dr, 'datetime', Clock))
        buffer = io.BytesIO()
        with patch.object(sys, 'stdout', types.SimpleNamespace(buffer=buffer)):
            self.assertEqual(self.dr.main(['export']), 0)
        self.assertEqual(len(self.members(buffer.getvalue())), 6)
        archive = self.write(self.home / 'archive.tar.gz', buffer.getvalue())
        self.clean()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(self.dr.main(['prepare', '--archive', str(archive)]), 0)
        self.assertEqual(output.getvalue(), 'PREPARED\n')
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.dr.main(['export', '--root', str(self.root)])

    def test_prepare_retained_two_day_backup_and_reject_over_seven_days(self):
        entries = self.members(self.export())
        self.clean()
        manifest = json.loads(entries[0][1])
        manifest['createdAt'] = (NOW-timedelta(days=7, seconds=1)).isoformat()
        entries[0] = (entries[0][0], json.dumps(manifest).encode())
        with self.assertRaises(Exception): self.prepare(self.repack(entries))
        self.assertFalse(self.output.exists())
        manifest['createdAt'] = (NOW-timedelta(days=2)).isoformat()
        entries[0] = (entries[0][0], json.dumps(manifest).encode())
        self.prepare(self.repack(entries))
        self.assertEqual((self.output / 'database/database.dump').read_bytes(), b'synthetic-dump')

    def test_prepare_disables_enabled_ai_and_preserves_archived_environment(self):
        original = b'PASSWORD=synthetic-secret\nFACTLENS_AI_MODE=enabled'
        self.write(self.root / '.env.production', original)
        archive = self.export()
        archived = {member.name: body for member, body in self.members(archive)}
        manifest = json.loads(archived['manifest.json'])
        self.clean()
        self.prepare(archive)
        effective = {}
        for line in (self.root / '.env.production').read_text().splitlines():
            if line and not line.startswith('#'):
                key, value = line.split('=', 1)
                effective[key] = value
        self.assertEqual(effective['FACTLENS_AI_MODE'], 'disabled')
        self.assertEqual(effective['PASSWORD'], 'synthetic-secret')
        preserved = (self.output / 'config/production.env').read_bytes()
        self.assertEqual(preserved, original)
        self.assertEqual(archived['config/production.env'], original)
        self.assertEqual(hashlib.sha256(preserved).hexdigest(),
                         manifest['files']['config/production.env']['sha256'])

    @unittest.skipUnless(os.name == 'posix', 'requires POSIX ownership, symlinks and flock')
    def test_posix_symlinks_owner_and_lock_contention(self):
        import fcntl
        data = self.export()
        env = self.root / '.env.production'
        env.rename(self.home / 'env')
        env.symlink_to(self.home / 'env')
        with self.assertRaises(Exception): self.export()
        env.unlink()
        (self.home / 'env').rename(env)
        with self.lock.open('w') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with patch.object(self.dr.operations.time, 'monotonic', side_effect=[0, 181]):
                with self.assertRaisesRegex(RuntimeError, 'BUSY'): self.export()
        with patch.object(os, 'getuid', return_value=os.getuid()+1), self.assertRaises(Exception):
            self.export()
        self.clean()
        archive = self.write(self.home / 'real.tar.gz', data)
        link = self.home / 'link.tar.gz'
        link.symlink_to(archive)
        with self.assertRaises(Exception): self.dr.prepare(self.root, link, self.output, now=NOW)
        (self.root / '.factlens-deploy-target').symlink_to(self.home / 'absent')
        with self.assertRaises(Exception): self.prepare(data)


if __name__ == '__main__':
    unittest.main()
