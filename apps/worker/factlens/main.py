import multiprocessing
import os
import time
from pathlib import Path
from uuid import UUID
import redis
from factlens.queue import claim_job, complete_job, fail_job, set_stage, recover_expired
from factlens.media import probe_media, extract_audio
from factlens.pipeline import run_analysis, Providers, ProviderUnavailable

def process_job(job):
    job_id,version=job['id'],job['version']
    try:
        path=Path(job['path'])
        info=probe_media(path)
        if not set_stage(job_id,version,'transcribing'):return
        audio=path.parent/'audio.wav'
        extract_audio(path,audio)
        result=run_analysis({**job,'path':str(audio),'duration':info.duration},Providers(),stage=lambda s:set_stage(job_id,version,s))
        complete_job(job_id,version,result)
    except ProviderUnavailable:
        fail_job(job_id,version,'PROVIDER_NOT_CONFIGURED')
    except ValueError as exc:
        # Only our own controlled error codes are exposed; no raw document/provider data.
        code=str(exc)
        fail_job(job_id,version,code if code in {'SIZE_LIMIT','NO_AUDIO','FORMAT_MISMATCH','DURATION_LIMIT','INVALID_MEDIA','CONSENT_REQUIRED','CLAIM_OUT_OF_RANGE','JOB_CANCELLED'} else 'ANALYSIS_FAILED')
    except Exception:
        fail_job(job_id,version,'ANALYSIS_FAILED')

def main():
    client=redis.Redis.from_url(os.environ['REDIS_URL'],socket_connect_timeout=2,socket_timeout=4)
    while True:
        recover_expired()
        candidate=None
        try:
            item=client.brpop('factlens:jobs',timeout=1)
            if item:
                try:candidate=UUID(item[1].decode())
                except ValueError:pass
        except redis.RedisError:time.sleep(1)
        job=claim_job(candidate)
        if job is None:job=claim_job()  # Durable recovery if enqueue/Redis failed.
        if not job:continue
        child=multiprocessing.Process(target=process_job,args=(job,))
        child.start();child.join(600)
        if child.is_alive():
            child.terminate();child.join(5)
            if child.is_alive():child.kill();child.join()
            fail_job(job['id'],job['version'],'TIMEOUT')
        elif child.exitcode:
            fail_job(job['id'],job['version'],'WORKER_EXITED')

if __name__=='__main__':main()
