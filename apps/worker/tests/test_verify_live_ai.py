"""Offline smoke regressions; PostgreSQL/FFmpeg integration is explicitly opt-in."""
import importlib.util
import json
import logging
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import sys
from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4
import wave

import httpx
import pytest

from factlens import budget, live_providers
from factlens.media import MediaInfo

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / 'devtools/verify-live-ai.py'
PRIVATE = 'private-transcript-never-print'


def test_explicit_smoke_entrypoint_exists():
    assert SCRIPT.is_file(), 'Missing controlled live smoke entrypoint'


@pytest.fixture
def smoke():
    assert SCRIPT.is_file(), 'The explicit controlled live smoke CLI is not implemented'
    spec = importlib.util.spec_from_file_location('verify_live_ai', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    # Never inherit real provider credentials or allow a test to open a network socket.
    monkeypatch.setenv('FACTLENS_AI_MODE', 'openai_brave')
    monkeypatch.setenv('OPENAI_API_KEY', 'test-openai-secret')
    monkeypatch.setenv('BRAVE_SEARCH_API_KEY', 'test-brave-secret')
    monkeypatch.setenv('FACTLENS_JOB_BUDGET_MICROS', '200000')
    monkeypatch.setenv('FACTLENS_MONTH_BUDGET_MICROS', '20000000')
    def denied(*args, **kwargs):
        raise AssertionError('Unexpected network access')
    monkeypatch.setattr(socket.socket, 'connect', denied)


@pytest.fixture
def source(tmp_path):
    path = tmp_path / 'private-original.wav'
    with wave.open(str(path), 'wb') as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(b'\0\0' * 16000)
    path.chmod(0o600)
    return path


@pytest.fixture
def local_db(smoke, monkeypatch):
    """SQLite executes scoped SQL/constraints; PostgreSQL syntax is tested separately."""
    db = sqlite3.connect(':memory:')
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.executescript("""
        CREATE TABLE media(id TEXT PRIMARY KEY,path TEXT UNIQUE,original_name TEXT,
          bytes INTEGER,mime TEXT,owner_id TEXT,expires_at TEXT);
        CREATE TABLE jobs(id TEXT PRIMARY KEY,media_id TEXT UNIQUE REFERENCES media(id),
          status TEXT DEFAULT 'queued',consent BOOLEAN CHECK(consent),owner_id TEXT,
          expires_at TEXT,idempotency_key TEXT UNIQUE,result TEXT,error TEXT,
          deleted_at TEXT,version INTEGER DEFAULT 0);
        CREATE TABLE usage_reservations(id TEXT PRIMARY KEY,job_id TEXT REFERENCES jobs(id),
          month TEXT,reserved_micros INTEGER,actual_micros INTEGER);
    """)
    statements = []

    class Connection:
        def execute(self, sql, args=()):
            statements.append((sql, args))
            if 'pg_advisory_xact_lock' in sql:
                return db.execute('SELECT 1')
            if 'to_char' in sql:
                return db.execute("SELECT strftime('%Y-%m','now') AS month")
            sql = sql.replace("now()+interval '1 hour'", "datetime('now','+1 hour')")
            sql = sql.replace('now()', "datetime('now')")
            sql = sql.replace('%s', '?')
            return db.execute(sql, tuple(str(a) if hasattr(a, 'hex') else a for a in args))

    @contextmanager
    def connect():
        with db:
            yield Connection()

    monkeypatch.setattr(smoke, 'connection', connect)
    monkeypatch.setattr(budget, 'connection', connect)
    yield db, statements
    db.close()


@pytest.fixture
def media_helpers(smoke, monkeypatch):
    copies = []
    def probe(path):
        assert path.name == 'controlled-live-smoke.wav'
        assert path.is_file()
        if os.name == 'posix':
            assert path.parent.stat().st_mode & 0o777 == 0o700
        copies.append(path.parent)
        return MediaInfo(1, 'wav')
    monkeypatch.setattr(smoke, 'probe_media', probe)
    monkeypatch.setattr(smoke, 'extract_audio', lambda path, target: shutil.copyfile(path, target))
    return copies


@pytest.fixture
def provider_double(monkeypatch):
    """Only external SDK/client boundaries are replaced; builder/pipeline/budget stay real."""
    state = SimpleNamespace(calls=[], error=None, closed=[])

    class SDK:
        def __init__(self, **kwargs):
            assert kwargs['max_retries'] == 0
            assert kwargs['api_key'] == 'test-openai-secret'
            self.audio = self.transcriptions = self.chat = self.completions = self

        def create(self, **kwargs):
            state.calls.append('transcribe' if 'file' in kwargs else 'extract')
            if state.error:
                print(PRIVATE)
                print('test-openai-secret', file=sys.stderr)
                logging.error(PRIVATE)
                raise state.error
            if 'file' in kwargs:
                data = {'segments': [{'start': 0, 'end': 1, 'text': PRIVATE}]}
            else:
                candidate = dict(quote=PRIVATE, segment_ids=[0], subject=None, period=None,
                                 metric=None, value=None, unit=None, eligibility='checkable')
                data = {'choices': [{'message': {'content': json.dumps({'claims': [candidate]}),
                                                'refusal': None}, 'finish_reason': 'stop'}],
                        'usage': {'prompt_tokens': 100, 'completion_tokens': 50}}
            return SimpleNamespace(model_dump=lambda: data)

        def close(self):
            state.closed.append('sdk')

    class Search:
        def __init__(self, **kwargs):
            pass

        def get(self, url, **kwargs):
            assert url == 'https://api.search.brave.com/res/v1/web/search'
            state.calls.append('search')
            return httpx.Response(200, json={'web': {'results': []}})

        def close(self):
            state.closed.append('search')

    monkeypatch.setattr(live_providers, 'OpenAI', SDK)
    monkeypatch.setattr(live_providers.httpx, 'Client', Search)
    return state


def assert_private(report):
    text = json.dumps(report)
    for value in (PRIVATE, 'test-openai-secret', 'test-brave-secret', 'private-original'):
        assert value not in text


def test_real_pipeline_builder_and_budget_leave_only_tombstones(
        smoke, local_db, source, media_helpers, provider_double):
    original = source.read_bytes()
    report = smoke.run(source, consent=True)
    assert report['status'] == 'completed'
    assert report['stages'] == ['transcribing', 'extracting', 'retrieving', 'validating_evidence']
    assert report['claimsCount'] == 1
    assert report['verdictCounts'] == {'INSUFFICIENT': 1}
    assert report['evidenceCount'] == 0
    assert report['versions']['providerProfile'] == 'openai_brave'
    assert report['usage']['calls'] == 3
    assert report['usage']['actualMicros'] == 5120
    assert report['usage']['unknownUsageCalls'] == 1
    assert report['cleanup'] == dict(filesRemoved=True, jobTombstoned=True,
                                     mediaTombstoned=True, usageRetained=True)
    assert source.read_bytes() == original
    assert not media_helpers[0].exists()
    db, statements = local_db
    job = dict(db.execute('SELECT * FROM jobs').fetchone())
    media = dict(db.execute('SELECT * FROM media').fetchone())
    assert job['status'] == 'deleted' and job['consent'] == 1
    assert job['owner_id'] is None and media['owner_id'] is None
    assert job['result'] is None and job['error'] is None
    assert media['path'] == f"deleted:{media['id']}" and media['original_name'] == 'deleted'
    assert 'queued' not in repr(statements)
    assert len(db.execute('SELECT * FROM usage_reservations').fetchall()) == 3
    assert sorted(provider_double.closed) == ['sdk', 'search']
    assert_private(report)


@pytest.mark.parametrize('error,code', [
    (RuntimeError(PRIVATE + ' test-openai-secret'), 'ANALYSIS_FAILED'),
    (ValueError(PRIVATE), 'ANALYSIS_FAILED'),
    (KeyboardInterrupt(), 'INTERRUPTED'),
    (live_providers.ProviderUnavailable('PROVIDER_AUTH_FAILED'), 'PROVIDER_AUTH_FAILED'),
])
def test_failure_cleans_copy_preserves_unknown_charge_without_raw_error(
        smoke, local_db, source, media_helpers, provider_double, error, code):
    provider_double.error = error
    original = source.read_bytes()
    report = smoke.run(source, consent=True)
    assert report['status'] == 'failed' and report['error'] == code
    assert report['usage']['calls'] == 1 and report['usage']['unknownUsageCalls'] == 1
    assert report['versions']['providerProfile'] == 'openai_brave'
    assert all(report['cleanup'].values())
    assert source.read_bytes() == original and not media_helpers[0].exists()
    assert tuple(local_db[0].execute(
        'SELECT reserved_micros,actual_micros FROM usage_reservations').fetchone()) == (200, None)
    assert_private(report)


@pytest.mark.parametrize('change,code', [
    ({'FACTLENS_AI_MODE': 'disabled'}, 'LIVE_MODE_REQUIRED'),
    ({'FACTLENS_AI_MODE': PRIVATE}, 'INVALID_PROVIDER_MODE'),
    ({'OPENAI_API_KEY': ''}, 'PROVIDER_NOT_CONFIGURED'),
    ({'BRAVE_SEARCH_API_KEY': ' '}, 'PROVIDER_NOT_CONFIGURED'),
    ({'FACTLENS_JOB_BUDGET_MICROS': '200001'}, 'INVALID_JOB_BUDGET'),
])
def test_readiness_fails_before_media_database_or_provider(
        smoke, local_db, source, media_helpers, provider_double, monkeypatch, change, code):
    for key, value in change.items():
        monkeypatch.setenv(key, value)
    report = smoke.run(source, consent=True)
    assert report['error'] == code
    assert not provider_double.calls and not local_db[1] and not media_helpers
    assert_private(report)


def test_consent_required_before_any_processing(smoke, source, local_db, provider_double):
    report = smoke.run(source, consent=False)
    assert report['error'] == 'CONSENT_REQUIRED'
    assert not local_db[1] and not provider_double.calls


def test_invalid_media_never_inserts_or_spends(
        smoke, source, local_db, provider_double, monkeypatch, media_helpers):
    def invalid(path):
        media_helpers.append(path.parent)
        raise ValueError('INVALID_MEDIA')
    monkeypatch.setattr(smoke, 'probe_media', invalid)
    report = smoke.run(source, consent=True)
    assert report['error'] == 'INVALID_MEDIA'
    assert not local_db[1] and not provider_double.calls
    assert report['cleanup']['filesRemoved'] is True
    assert not media_helpers[0].exists()


def test_repeated_runs_preserve_prior_costs_and_global_monthly_cap(
        smoke, source, local_db, provider_double, media_helpers, monkeypatch):
    first = smoke.run(source, consent=True)
    assert first['status'] == 'completed'
    calls = len(provider_double.calls)
    monkeypatch.setenv('FACTLENS_MONTH_BUDGET_MICROS', '5400')
    second = smoke.run(source, consent=True)
    assert second['error'] == 'BUDGET_EXCEEDED'
    assert len(provider_double.calls) == calls
    assert all(second['cleanup'].values())
    assert local_db[0].execute('SELECT count(*) FROM usage_reservations').fetchone()[0] == 3
    assert local_db[0].execute("SELECT count(*) FROM jobs WHERE status='deleted'").fetchone()[0] == 2


def test_cleanup_failure_is_reported_and_does_not_prevent_file_removal(
        smoke, source, local_db, provider_double, media_helpers, monkeypatch):
    def broken(*args):
        raise RuntimeError(PRIVATE)
    monkeypatch.setattr(smoke, 'tombstone', broken)
    report = smoke.run(source, consent=True)
    assert report['status'] == 'failed' and report['error'] == 'CLEANUP_FAILED'
    assert report['cleanup']['filesRemoved'] is True
    assert report['cleanup']['jobTombstoned'] is False
    assert not media_helpers[0].exists() and source.exists()
    assert_private(report)


def test_cli_emits_only_json_and_requires_input_and_consent(smoke, capsys):
    assert smoke.main([]) != 0
    report = json.loads(capsys.readouterr().out)
    assert report['error'] == 'INPUT_REQUIRED'
    assert smoke.main(['--input', 'missing.wav']) != 0
    assert json.loads(capsys.readouterr().out)['error'] == 'CONSENT_REQUIRED'
    assert smoke.main(['--api-key', 'test-openai-secret']) != 0
    captured = capsys.readouterr()
    assert 'test-openai-secret' not in captured.out + captured.err


def test_cli_success_reports_actual_pipeline_and_no_private_output(
        smoke, source, local_db, provider_double, media_helpers, capsys):
    assert smoke.main(['--input', str(source), '--consent']) == 0
    captured = capsys.readouterr()
    report = json.loads(captured.out)
    assert report['claimsCount'] == 1 and report['usage']['calls'] == 3
    assert not captured.err
    assert_private(report)


def test_cli_failure_suppresses_provider_output(
        smoke, source, local_db, provider_double, media_helpers, capsys):
    provider_double.error = RuntimeError(PRIVATE)
    assert smoke.main(['--input', str(source), '--consent']) == 1
    captured = capsys.readouterr()
    report = json.loads(captured.out)
    assert report['error'] == 'ANALYSIS_FAILED'
    assert not captured.err
    assert_private(report)


def test_tombstone_does_not_touch_another_label(smoke, local_db, source):
    job = dict(id=uuid4(), media_id=uuid4(), idempotency_key='other-label', sourcePath=str(source))
    smoke.register(job, source)
    flags, usage = smoke.tombstone({**job, 'idempotency_key': 'controlled-live-smoke:wrong'})
    assert flags['jobTombstoned'] is False and flags['mediaTombstoned'] is False
    assert local_db[0].execute('SELECT status FROM jobs').fetchone()[0] == 'completed'
    assert local_db[0].execute('SELECT path FROM media').fetchone()[0] == str(source)


def test_extraction_failure_cleans_copy_before_registration(
        smoke, source, local_db, provider_double, media_helpers, monkeypatch):
    def fail(*args):
        raise RuntimeError(PRIVATE)
    monkeypatch.setattr(smoke, 'extract_audio', fail)
    report = smoke.run(source, consent=True)
    assert report['error'] == 'ANALYSIS_FAILED'
    assert report['cleanup']['filesRemoved'] is True
    assert not local_db[1] and not provider_double.calls and not media_helpers[0].exists()
    assert source.exists()


@pytest.mark.skipif(not os.environ.get('FACTLENS_SMOKE_TEST_DATABASE_URL'),
                    reason='Set FACTLENS_SMOKE_TEST_DATABASE_URL to an isolated PostgreSQL test DB')
@pytest.mark.parametrize('failure', [False, True])
def test_postgres_and_ffmpeg_integration(smoke, source, provider_double, monkeypatch, failure):
    """Real production schema, media helpers and reserve/settle; no provider network."""
    import psycopg
    from psycopg import sql
    from psycopg.rows import dict_row
    assert shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg is required for integration'
    dsn = os.environ['FACTLENS_SMOKE_TEST_DATABASE_URL']
    schema = 'smoke_test_' + uuid4().hex
    with psycopg.connect(dsn, autocommit=True) as admin:
        admin.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        try:
            @contextmanager
            def connect():
                with psycopg.connect(dsn, row_factory=dict_row, options=f'-c search_path={schema}') as conn:
                    yield conn
            with connect() as conn:
                for migration in ['001_initial.sql', '002_accounts.sql']:
                    conn.execute((ROOT / 'apps/api/migrations' / migration).read_text())
            monkeypatch.setattr(smoke, 'connection', connect)
            monkeypatch.setattr(budget, 'connection', connect)
            if failure:
                provider_double.error = TimeoutError(PRIVATE)
            original = source.read_bytes()
            report = smoke.run(source, consent=True)
            assert report['status'] == ('failed' if failure else 'completed')
            assert all(report['cleanup'].values())
            assert source.read_bytes() == original
            with connect() as conn:
                rows = conn.execute('SELECT * FROM usage_reservations').fetchall()
                assert len(rows) == (1 if failure else 3)
                assert rows[0]['actual_micros'] is None
                assert conn.execute("SELECT status,consent,owner_id FROM jobs").fetchone() == {
                    'status': 'deleted', 'consent': True, 'owner_id': None}
            assert_private(report)
        finally:
            admin.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
