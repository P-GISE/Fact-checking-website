import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import threading
import time
import types
import unittest
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch


REPO = Path(__file__).resolve().parents[3]
NOW = datetime(2026, 10, 20, 9, tzinfo=timezone.utc)


class OperationsTests(unittest.TestCase):
    def setUp(self):
        source = REPO / "devtools/operations.py"
        self.assertTrue(source.is_file(), "scheduled backup/check CLI is missing")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.root = self.home / "factlens"
        self.root.mkdir()
        (self.root / ".factlens-deploy-target").write_text("factlens-ai\n")
        self.backups = self.home / "factlens-backups"
        self.backups.mkdir(mode=0o700)
        self.lock = self.home / ".factlens-deploy.lock"
        self.modes = {}
        self.owners = {}
        if os.name == "nt":
            # Windows has no POSIX modes/uid/flock; emulate only that OS boundary.
            real_lstat = Path.lstat

            def lstat(path):
                info = real_lstat(path)
                mode = stat.S_IMODE(info.st_mode)
                if path.is_relative_to(self.home):
                    mode = self.modes.get(path, 0o700 if stat.S_ISDIR(info.st_mode) else 0o600)
                return os.stat_result((stat.S_IFMT(info.st_mode) | mode, info.st_ino,
                                      info.st_dev, info.st_nlink, self.owners.get(path, 1000),
                                      info.st_gid, info.st_size, info.st_atime,
                                      info.st_mtime, info.st_ctime))

            self.enterContext(patch.object(Path, "lstat", lstat))
            self.enterContext(patch.object(os, "getuid", return_value=1000, create=True))
            self.enterContext(patch.object(os, "O_NOFOLLOW", 0, create=True))
            self.enterContext(patch.dict(sys.modules, {
                "fcntl": types.SimpleNamespace(LOCK_EX=2, LOCK_NB=4,
                                               flock=lambda *_: None),
            }))
        self.enterContext(patch.dict(sys.modules))
        spec = importlib.util.spec_from_file_location("operations", source)
        self.ops = importlib.util.module_from_spec(spec)
        self.enterContext(patch.object(sys, "path", [str(REPO / "devtools"), *sys.path]))
        spec.loader.exec_module(self.ops)
        self.calls = []
        self.process_failure = None

        def run(args, **kwargs):
            self.calls.append((args, kwargs))
            if self.process_failure:
                raise self.process_failure
            self.assertEqual(args[0:2], ["docker", "--host=unix:///var/run/docker.sock"])
            self.assertEqual(kwargs["stderr"], subprocess.PIPE)
            self.assertLessEqual(kwargs["timeout"], 60)
            for key in ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS",
                        "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH"):
                self.assertNotIn(key, kwargs["env"])
            if args[2] == "compose":
                self.assertNotIn("COMPOSE_PROFILES", kwargs["env"])
                self.assertEqual(args[3:], [
                    "--project-name", "factlens", "--env-file", ".env.production",
                    "-f", "compose.production.yaml", "ps", "-q", "postgres"])
                self.assertEqual(Path(kwargs["cwd"]), self.root)
                return subprocess.CompletedProcess(args, 0, b"factlens-postgres-1\n", b"")
            self.assertEqual(args[2:8], ["exec", "-i", "factlens-postgres-1",
                                       "pg_dump", "-U", "factlens"])
            self.assertIn("--exclude-table-data=public.app_sessions", args)
            self.assertIn("--exclude-table-data=public.upload_leases", args)
            kwargs["stdout"].write(b"synthetic-private-dump")
            return subprocess.CompletedProcess(args, 0, None, b"")

        self.enterContext(patch.object(subprocess, "run", run))
        self.enterContext(patch.dict(os.environ, {
            "DOCKER_HOST": "tcp://invalid", "DOCKER_CONTEXT": "wrong",
            "DOCKER_TLS": "1", "DOCKER_TLS_VERIFY": "1",
            "DOCKER_CERT_PATH": "private", "COMPOSE_PROFILES": "wrong",
        }))
        self.enterContext(patch.object(self.ops.shutil, "disk_usage",
                                      return_value=types.SimpleNamespace(free=10 * 1024**3)))

    def mode(self, path, mode):
        path.chmod(mode)
        self.modes[path] = mode

    def backup(self, now=NOW):
        return self.ops.backup(self.root, self.backups, self.lock, now=now)

    def check(self, now=NOW):
        self.ops.check(self.root, self.backups, self.lock, now=now)

    def healthy(self):
        self.enterContext(patch.object(self.ops, "health", return_value=None))

    @contextlib.contextmanager
    def fast_clock(self):
        elapsed = [0]

        def sleep(seconds):
            elapsed[0] += seconds

        with patch.object(time, "monotonic", side_effect=lambda: elapsed[0]), \
                patch.object(time, "sleep", side_effect=sleep):
            yield elapsed

    def test_backup_reuses_recovery_and_creates_unique_private_complete_bundles(self):
        first, second = self.backup(), self.backup()
        self.assertNotEqual(first, second)
        self.assertRegex(first.name, r"^daily-20261020T090000000000Z-[a-z0-9_]{8}$")
        for directory in (self.backups, first, first / "database"):
            self.assertEqual(stat.S_IMODE(directory.lstat().st_mode), 0o700)
        for name in ("database/database.dump", "database/manifest.json", "complete"):
            self.assertEqual(stat.S_IMODE((first / name).lstat().st_mode), 0o600)
        self.assertEqual((first / "complete").read_text(), "factlens-daily-v1\n")
        self.healthy()
        self.check()

    def test_partial_output_never_becomes_fresh(self):
        with patch.object(self.ops.recovery, "backup", side_effect=RuntimeError("secret SQL")):
            with self.assertRaises(Exception):
                self.backup()
        self.assertFalse(any(self.backups.glob("*/complete")))
        self.healthy()
        with self.assertRaisesRegex(RuntimeError, "BACKUP"):
            self.check()

    def test_corruption_is_rejected_before_completion(self):
        real_backup = self.ops.recovery.backup

        def corrupt(*args):
            real_backup(*args)
            (args[2] / "database.dump").write_bytes(b"corrupt")

        with patch.object(self.ops.recovery, "backup", corrupt):
            with self.assertRaises(Exception):
                self.backup()
        self.assertFalse(any(self.backups.glob("*/complete")))

    def test_recent_partial_does_not_hide_stale_complete_backup(self):
        self.backup(NOW - timedelta(hours=27))
        partial = self.backups / "daily-20261020T090000000000Z-partial1"
        partial.mkdir(mode=0o700)
        self.healthy()
        with self.assertRaisesRegex(RuntimeError, "BACKUP"):
            self.check()

    def test_freshness_boundary_and_future_timestamp(self):
        self.backup()
        self.healthy()
        self.check(NOW + timedelta(hours=26))
        for moment in (NOW + timedelta(hours=26, seconds=1), NOW - timedelta(seconds=1)):
            with self.subTest(moment=moment):
                with self.assertRaisesRegex(RuntimeError, "BACKUP"):
                    self.check(moment)

    def test_corrupt_dump_manifest_or_completion_fails_check(self):
        folder = self.backup()
        self.healthy()
        for name, body in (("database/database.dump", b"bad"),
                           ("database/manifest.json", b"[]"),
                           ("database/manifest.json", b"{" * 5000),
                           ("complete", b"partial")):
            with self.subTest(name=name, body_size=len(body)):
                path = folder / name
                original = path.read_bytes()
                path.write_bytes(body)
                with self.assertRaisesRegex(RuntimeError, "BACKUP"):
                    self.check()
                path.write_bytes(original)

    def test_public_modes_and_wrong_owner_fail_closed(self):
        folder = self.backup()
        self.healthy()
        for path in (self.backups, folder, folder / "database",
                     folder / "database/database.dump", folder / "database/manifest.json",
                     folder / "complete"):
            with self.subTest(path=path.name):
                original = stat.S_IMODE(path.lstat().st_mode)
                self.mode(path, 0o755 if path.is_dir() else 0o644)
                with self.assertRaises((RuntimeError, ValueError)):
                    self.check()
                self.mode(path, original)
        with patch.object(os, "getuid", return_value=os.getuid() + 1):
            with self.assertRaises((RuntimeError, ValueError)):
                self.check()

    def test_retention_deletes_only_valid_old_owned_daily_bundles(self):
        old = self.backup(NOW - timedelta(days=8))
        boundary = self.backup(NOW - timedelta(days=7))
        malformed = self.backups / "daily-unrelated"
        malformed.mkdir()
        unrelated = self.backups / "deploy-abc"
        unrelated.mkdir()
        unsafe = self.backup(NOW - timedelta(days=8))
        (unsafe / "keep.txt").write_text("unrelated")
        corrupt = self.backup(NOW - timedelta(days=8))
        (corrupt / "database/database.dump").write_bytes(b"bad")
        partial = self.backups / "daily-20261001T090000000000Z-partial1"
        partial.mkdir(mode=0o700)
        self.backup()
        self.assertFalse(old.exists())
        for kept in (boundary, malformed, unrelated, unsafe, corrupt, partial):
            self.assertTrue(kept.exists(), kept.name)

    def test_retention_keeps_nonprivate_and_foreign_owned_bundles(self):
        old = self.backup(NOW - timedelta(days=8))
        self.mode(old, 0o755)
        self.backup()
        self.assertTrue(old.exists())
        self.mode(old, 0o700)
        real_lstat = Path.lstat

        def foreign(path):
            info = real_lstat(path)
            if path == old:
                values = list(info)
                values[4] = os.getuid() + 1
                return os.stat_result(values)
            return info

        with patch.object(Path, "lstat", foreign):
            self.backup()
        self.assertTrue(old.exists())

    def test_failed_backup_never_prunes_old_backup(self):
        old = self.backup(NOW - timedelta(days=8))
        self.process_failure = subprocess.TimeoutExpired("secret", 30, stderr=b"password")
        with self.assertRaises(Exception):
            self.backup()
        self.assertTrue(old.exists())

    def test_backup_creates_missing_private_root(self):
        self.backups.rmdir()
        folder = self.backup()
        self.assertEqual(stat.S_IMODE(self.backups.lstat().st_mode), 0o700)
        self.assertTrue((folder / "complete").is_file())

    def test_wrong_marker_blocks_backup_and_check(self):
        (self.root / ".factlens-deploy-target").write_text("other-server")
        for action in (self.backup, self.check):
            with self.assertRaisesRegex(RuntimeError, "TARGET"):
                action()
        self.assertEqual(list(self.backups.iterdir()), [])

    def test_compose_bad_output_and_process_exit_fail_closed(self):
        for result in (subprocess.CompletedProcess([], 1, b"", b"password"),
                       subprocess.CompletedProcess([], 0, b"one\ntwo\n", b""),
                       subprocess.CompletedProcess([], 0, b"", b"")):
            with self.subTest(result=result.returncode, output=result.stdout):
                with patch.object(subprocess, "run", return_value=result):
                    with self.assertRaises(Exception):
                        self.backup()
        self.assertFalse(any(self.backups.glob("*/complete")))

    def test_disk_reserve_boundary(self):
        self.backup()
        self.healthy()
        with patch.object(self.ops.shutil, "disk_usage",
                          return_value=types.SimpleNamespace(free=2 * 1024**3)):
            self.check()
        with patch.object(self.ops.shutil, "disk_usage",
                          return_value=types.SimpleNamespace(free=2 * 1024**3 - 1)):
            for action in (self.check, self.backup):
                with self.assertRaisesRegex(RuntimeError, "DISK"):
                    action()

    def test_health_reads_real_loopback_http_and_rejects_bad_responses(self):
        class Handler(BaseHTTPRequestHandler):
            status = 200
            body = b'{"status":"ready"}'

            def do_GET(self):
                self.send_response(self.status)
                self.end_headers()
                self.wfile.write(self.body)

            def log_message(self, *_):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        with patch.dict(os.environ, {"http_proxy": "http://127.0.0.1:1", "no_proxy": ""}):
            self.ops.health(server.server_port)
        for status, body in ((302, b'{"status":"ready"}'), (503, b"secret"),
                             (200, b'{"status":"starting"}'),
                             (200, b"[]"), (200, b"not json"), (200, b"x" * 5000)):
            Handler.status, Handler.body = status, body
            with self.subTest(status=status, size=len(body)):
                with self.assertRaisesRegex(RuntimeError, "HEALTH"):
                    self.ops.health(server.server_port)

    def test_health_connection_error_and_timeout_fail_closed(self):
        for error in (ConnectionRefusedError("secret"), TimeoutError("secret")):
            with self.subTest(error=type(error).__name__):
                with patch.object(self.ops.http.client.HTTPConnection, "request", side_effect=error):
                    with self.assertRaisesRegex(RuntimeError, "^HEALTH_NOT_READY$"):
                        self.ops.health()

    def test_check_cli_exit_status_and_secret_redaction(self):
        self.backup(datetime.now(timezone.utc))
        self.healthy()
        for name, value in (("ROOT", self.root), ("BACKUP_ROOT", self.backups),
                            ("LOCK", self.lock)):
            self.enterContext(patch.object(self.ops, name, value))
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            self.assertEqual(self.ops.main(["check"]), 0)
            with patch.object(self.ops, "health", side_effect=RuntimeError("password SQL dump")):
                self.assertEqual(self.ops.main(["check"]), 1)
        self.assertNotIn("password", output.getvalue() + errors.getvalue())
        self.assertNotIn("SQL", output.getvalue() + errors.getvalue())
        self.assertLess(len(errors.getvalue()), 200)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as result:
            self.ops.main(["check", "--root", str(self.root)])
        self.assertEqual(result.exception.code, 2)

    def test_backup_cli_redacts_process_errors_and_returns_nonzero(self):
        for name, value in (("ROOT", self.root), ("BACKUP_ROOT", self.backups),
                            ("LOCK", self.lock)):
            self.enterContext(patch.object(self.ops, name, value))
        for error in (FileNotFoundError("password"), subprocess.TimeoutExpired(
                "private SQL", 30, output=b"dump", stderr=b"password")):
            self.process_failure = error
            output, errors = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                self.assertEqual(self.ops.main(["backup"]), 1)
            self.assertEqual(output.getvalue(), "")
            self.assertEqual(errors.getvalue(), "OPERATION_FAILED\n")
        self.assertFalse(any(self.backups.glob("*/complete")))

    def test_lock_contention_fails_without_touching_backups(self):
        import fcntl
        for action, timeout in ((self.backup, 1800), (self.check, 180)):
            with self.subTest(timeout=timeout), self.fast_clock() as elapsed:
                with patch.object(fcntl, "flock", side_effect=BlockingIOError):
                    with self.assertRaisesRegex(RuntimeError, "BUSY"):
                        action()
                self.assertEqual(elapsed[0], timeout)
        self.assertEqual(list(self.backups.iterdir()), [])

    def test_lock_waits_then_runs_backup_and_check_after_release(self):
        import fcntl
        self.healthy()
        for action in (self.backup, self.check):
            with self.subTest(action=action.__name__), self.fast_clock() as elapsed:
                with patch.object(fcntl, "flock",
                                  side_effect=[BlockingIOError, BlockingIOError, None]):
                    action()
                self.assertEqual(elapsed[0], 2)
        self.assertEqual(len(list(self.backups.glob("*/complete"))), 1)

    def test_check_measures_freshness_after_waiting_for_lock(self):
        import fcntl
        self.backup()
        self.healthy()
        with self.fast_clock() as elapsed:
            class ClockDateTime(datetime):
                @classmethod
                def now(cls, tz=None):
                    return NOW - timedelta(seconds=2 - elapsed[0])

            with patch.object(self.ops, "datetime", ClockDateTime), \
                    patch.object(fcntl, "flock",
                                 side_effect=[BlockingIOError, BlockingIOError, None]):
                self.ops.check(self.root, self.backups, self.lock)

    @unittest.skipUnless(os.name == "posix", "requires Linux symlink permissions and flock")
    def test_real_flock_and_symlink_safety(self):
        import fcntl
        with self.lock.open("w") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.fast_clock(), self.assertRaisesRegex(RuntimeError, "BUSY"):
                self.backup()
        old = self.backup(NOW - timedelta(days=8))
        outside = self.home / "outside"
        old.rename(outside)
        old.symlink_to(outside, target_is_directory=True)
        fresh = self.backup()
        self.assertTrue(old.is_symlink())
        self.assertTrue((outside / "complete").exists())
        (fresh / "database/database.dump").unlink()
        (fresh / "database/database.dump").symlink_to(outside / "database/database.dump")
        self.healthy()
        with self.assertRaisesRegex(RuntimeError, "BACKUP"):
            self.check()
        self.backups.rename(self.home / "real-backups")
        self.backups.symlink_to(self.home / "real-backups", target_is_directory=True)
        with self.assertRaises((RuntimeError, ValueError)):
            self.backup()
        self.backups.unlink()
        (self.home / "real-backups").rename(self.backups)
        marker = self.root / ".factlens-deploy-target"
        saved_marker = self.home / "saved-marker"
        marker.rename(saved_marker)
        marker.symlink_to(saved_marker)
        with self.assertRaisesRegex(RuntimeError, "TARGET"):
            self.backup()
        marker.unlink()
        saved_marker.rename(marker)
        self.lock.unlink()
        self.lock.symlink_to(marker)
        with self.assertRaises(OSError):
            self.backup()
        self.assertEqual(marker.read_text(), "factlens-ai\n")


if __name__ == "__main__":
    unittest.main()
