"""Explicit paid smoke: PYTHONPATH=apps/worker python devtools/verify-live-ai.py --input OWNED.wav --consent.

Use the deployment lock externally. Credentials and budgets come only from the
existing process environment. No queue, service activation, or transcript output.
"""
import argparse
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
import json
import logging
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile
from uuid import uuid4

from factlens.live_providers import Settings, build_providers
from factlens.media import probe_media, extract_audio
from factlens.metered import BudgetDenied, InvalidUsage
from factlens.pipeline import run_analysis
from factlens.queue import connection

LABEL = 'controlled-live-smoke'
MAX_BYTES = 104857600
ERRORS = {
    'CONSENT_REQUIRED', 'INPUT_REQUIRED', 'INVALID_ARGUMENTS', 'INVALID_INPUT',
    'PRIVATE_INPUT_REQUIRED', 'LIVE_MODE_REQUIRED', 'INVALID_PROVIDER_MODE',
    'INVALID_JOB_BUDGET', 'INVALID_MONTH_BUDGET', 'SIZE_LIMIT', 'NO_AUDIO',
    'FORMAT_MISMATCH', 'DURATION_LIMIT', 'INVALID_MEDIA', 'CLAIM_OUT_OF_RANGE',
    'PROVIDER_NOT_CONFIGURED', 'PROVIDER_AUTH_FAILED', 'PROVIDER_RATE_LIMITED', 'PROVIDER_QUOTA_EXCEEDED',
    'PROVIDER_MODEL_UNAVAILABLE', 'PROVIDER_INPUT_LIMIT', 'PROVIDER_RESPONSE_INVALID',
    'PROVIDER_REQUEST_FAILED', 'PROVIDER_SEARCH_LIMIT',
}


def error_code(exc):
    if isinstance(exc, KeyboardInterrupt):
        return 'INTERRUPTED'
    if isinstance(exc, BudgetDenied):
        return 'BUDGET_EXCEEDED'
    if isinstance(exc, InvalidUsage):
        return 'BILLING_REVIEW_REQUIRED'
    code = exc.args[0] if exc.args else None
    return code if isinstance(code, str) and code in ERRORS else 'ANALYSIS_FAILED'


def safe_versions(versions):
    return {
        key: value for key, value in versions.items()
        if (key.endswith('Version') or key in ('providerProfile', 'speechModel', 'languageModel'))
        and isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_.:-]{1,100}', value)
    }


def register(job, source):
    with connection() as conn:
        conn.execute(
            "INSERT INTO media(id,path,original_name,bytes,mime,owner_id,expires_at) "
            "VALUES(%s,%s,%s,%s,%s,NULL,now()+interval '1 hour')",
            (job['media_id'], str(source), source.name, source.stat().st_size,
             {'.wav': 'audio/wav', '.mp3': 'audio/mpeg', '.mp4': 'video/mp4'}[source.suffix]))
        conn.execute(
            "INSERT INTO jobs(id,media_id,status,consent,owner_id,idempotency_key,expires_at) "
            "VALUES(%s,%s,'completed',true,NULL,%s,now()+interval '1 hour')",
            (job['id'], job['media_id'], job['idempotency_key']))


def tombstone(job):
    scope = (job['id'], job['media_id'], job['idempotency_key'])
    with connection() as conn:
        before = conn.execute(
            'SELECT id,reserved_micros,actual_micros FROM usage_reservations '
            'WHERE job_id=%s ORDER BY id', (job['id'],)).fetchall()
        updated = conn.execute(
            "UPDATE jobs SET status='deleted',result=NULL,error=NULL,deleted_at=now(),"
            "expires_at=now(),version=version+1 WHERE id=%s AND media_id=%s "
            "AND idempotency_key=%s AND owner_id IS NULL AND consent RETURNING id", scope).fetchone()
        if updated:
            # A literal 'deleted' conflicts with media.path UNIQUE on the second run.
            conn.execute(
                "UPDATE media SET path=%s,original_name='deleted',expires_at=now() "
                "WHERE id=%s AND owner_id IS NULL AND path=%s AND original_name=%s",
                (f"deleted:{job['media_id']}", job['media_id'], job['sourcePath'],
                 Path(job['sourcePath']).name))
    with connection() as conn:
        row = conn.execute(
            "SELECT j.status,j.result,j.error,j.consent,j.expires_at<=now() AS job_expired,"
            "m.path,m.original_name,m.expires_at<=now() AS media_expired "
            "FROM jobs j JOIN media m ON m.id=j.media_id WHERE j.id=%s AND j.media_id=%s "
            "AND j.idempotency_key=%s AND j.owner_id IS NULL AND m.owner_id IS NULL", scope).fetchone()
        after = conn.execute(
            'SELECT id,reserved_micros,actual_micros FROM usage_reservations '
            'WHERE job_id=%s ORDER BY id', (job['id'],)).fetchall()
    flags = {
        'jobTombstoned': bool(row and row['status'] == 'deleted' and row['result'] is None
                              and row['error'] is None and row['consent'] and row['job_expired']),
        'mediaTombstoned': bool(row and row['path'] == f"deleted:{job['media_id']}"
                                and row['original_name'] == 'deleted' and row['media_expired']),
        'usageRetained': before == after,
    }
    usage = {
        'calls': len(after),
        'actualMicros': sum(r['actual_micros'] or 0 for r in after),
        'unknownUsageCalls': sum(r['actual_micros'] is None for r in after),
        'conservativeMicros': sum(r['reserved_micros'] if r['actual_micros'] is None
                                  else r['actual_micros'] for r in after),
        'currency': 'USD', 'costBasis': 'published_tariff_not_invoice',
    }
    return flags, usage


def run(input_path, *, consent):
    mode = os.environ.get('FACTLENS_AI_MODE', 'disabled')
    report = {
        'status': 'failed', 'error': None, 'stages': [], 'claimsCount': 0,
        'verdictCounts': {}, 'evidenceCount': 0, 'usage': None, 'versions': {},
        'runtime': {'mode': mode if mode in ('disabled', 'openai_brave') else 'invalid',
                    'openaiKeyPresent': bool(os.environ.get('OPENAI_API_KEY', '').strip()),
                    'braveKeyPresent': bool(os.environ.get('BRAVE_SEARCH_API_KEY', '').strip())},
        'cleanup': {'filesRemoved': True, 'jobTombstoned': None,
                    'mediaTombstoned': None, 'usageRetained': None},
    }
    folder = providers = None
    attempted_insert = False
    job = {'id': uuid4(), 'media_id': uuid4(), 'consent': True}
    job['idempotency_key'] = f"{LABEL}:{job['id']}"
    previous_logging = logging.root.manager.disable
    with open(os.devnull, 'w') as quiet, redirect_stdout(quiet), redirect_stderr(quiet):
        logging.disable(logging.CRITICAL)
        try:
            if not consent:
                raise ValueError('CONSENT_REQUIRED')
            if not input_path:
                raise ValueError('INPUT_REQUIRED')
            settings = Settings.from_env()
            if settings.mode != 'openai_brave':
                raise ValueError('LIVE_MODE_REQUIRED')
            if not settings.openai_key.strip() or not settings.brave_key.strip():
                raise ValueError('PROVIDER_NOT_CONFIGURED')
            source = Path(input_path)
            if source.is_symlink() or not source.is_file():
                raise ValueError('INVALID_INPUT')
            suffix = source.suffix.lower()
            if suffix not in ('.wav', '.mp3', '.mp4'):
                raise ValueError('FORMAT_MISMATCH')
            with os.fdopen(os.open(source, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
                                   | getattr(os, 'O_NONBLOCK', 0)), 'rb') as original:
                info = os.fstat(original.fileno())
                if not stat.S_ISREG(info.st_mode):
                    raise ValueError('INVALID_INPUT')
                if os.name == 'posix' and (info.st_uid != os.geteuid() or info.st_mode & 0o077):
                    raise ValueError('PRIVATE_INPUT_REQUIRED')
                if not 0 < info.st_size <= MAX_BYTES:
                    raise ValueError('SIZE_LIMIT')
                folder = Path(tempfile.mkdtemp(prefix=f'{LABEL}-')).resolve()
                folder.chmod(0o700)
                copied = folder / f'{LABEL}{suffix}'
                data = original.read(MAX_BYTES + 1)
                if not 0 < len(data) <= MAX_BYTES:
                    raise ValueError('SIZE_LIMIT')
                copied.write_bytes(data)
                copied.chmod(0o600)
                del data
            info = probe_media(copied)
            audio = folder / 'audio.wav'
            extract_audio(copied, audio)
            job.update(path=str(audio), sourcePath=str(copied), duration=info.duration)
            attempted_insert = True
            register(job, copied)
            providers = build_providers(job, settings)
            report['versions'] = safe_versions(providers.versions())

            def stage(name):
                report['stages'].append(name)
                return True

            result = run_analysis(job, providers, stage=stage)
            report.update(status='completed', claimsCount=len(result.claims),
                          verdictCounts=dict(Counter(c.verdict for c in result.claims)),
                          evidenceCount=sum(len(c.evidence) for c in result.claims))
            report['versions'] = safe_versions(result.versions)
        except (Exception, KeyboardInterrupt) as exc:
            report['error'] = error_code(exc)
        finally:
            cleanup_failed = False
            if attempted_insert:
                report['cleanup'].update(jobTombstoned=False, mediaTombstoned=False, usageRetained=False)
                try:
                    flags, usage = tombstone(job)
                    report['cleanup'].update(flags)
                    report['usage'] = usage
                    cleanup_failed = not all(flags.values())
                except (Exception, KeyboardInterrupt):
                    cleanup_failed = True
            if providers is not None:
                for client in (providers.sdk, providers.search_client):
                    try:
                        client.close()
                    except (Exception, KeyboardInterrupt):
                        cleanup_failed = True
            if folder is not None:
                try:
                    shutil.rmtree(folder)
                except (Exception, KeyboardInterrupt):
                    cleanup_failed = True
                report['cleanup']['filesRemoved'] = not os.path.lexists(folder)
                cleanup_failed |= not report['cleanup']['filesRemoved']
            if cleanup_failed:
                report.update(status='failed', error='CLEANUP_FAILED')
            logging.disable(previous_logging)
    return report


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError('INVALID_ARGUMENTS')


def main(argv=None):
    parser = Parser(description=__doc__)
    parser.add_argument('--input', help='Private, owned local WAV/MP3/MP4; original is never modified')
    parser.add_argument('--consent', action='store_true', help='Authorize external processing and bounded paid calls')
    try:
        args = parser.parse_args(argv)
        if not args.input and not args.consent:
            raise ValueError('INPUT_REQUIRED')
        report = run(args.input, consent=args.consent)
    except ValueError as exc:
        report = {'status': 'failed', 'error': error_code(exc)}
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    return 0 if report['status'] == 'completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
