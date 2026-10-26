"""Adversarial, offline checks: no GitHub credentials or Docker daemon required."""
import copy
import unittest
import tempfile
import tarfile
import io
import json
import hashlib
from pathlib import Path
from prebuilt_gate import validate_run, validate_resources, validate_archive, GateError


SHA = 'a' * 40


def evidence():
    run = {'id': 12, 'run_attempt': 2, 'repository': {'id': 1420151819,
           'full_name': 'P-GISE/Fact-checking-website'},
           'head_repository': {'id': 1420151819}, 'workflow_id': 390486634,
           'path': '.github/workflows/deploy.yml', 'event': 'push',
           'head_branch': 'work', 'head_sha': SHA, 'status': 'in_progress'}
    jobs = [{'name': name, 'head_sha': SHA, 'status': 'completed',
             'conclusion': 'success', 'run_attempt': 2} for name in
            ('verify', 'security / scan', 'build-publish')]
    jobs.append({'name': 'deploy', 'status': 'in_progress', 'head_sha': SHA})
    return run, jobs


class RunGateTests(unittest.TestCase):
    def test_current_deploy_in_progress_is_valid(self):
        validate_run(*evidence(), SHA, 12, 2, SHA)

    def test_missing_duplicate_failed_or_stale_job_rejected(self):
        for mutation in ('missing', 'duplicate', 'failed', 'stale', 'attempt'):
            run, jobs = evidence()
            if mutation == 'missing': jobs.pop(0)
            if mutation == 'duplicate': jobs.append(copy.deepcopy(jobs[0]))
            if mutation == 'failed': jobs[0]['conclusion'] = 'failure'
            if mutation == 'stale': jobs[0]['head_sha'] = 'b' * 40
            if mutation == 'attempt': jobs[0]['run_attempt'] = 1
            with self.subTest(mutation=mutation), self.assertRaises(GateError):
                validate_run(run, jobs, SHA, 12, 2, SHA)

    def test_wrong_identity_or_event_rejected(self):
        for field, value in (('event', 'pull_request'), ('head_branch', 'main'),
                             ('workflow_id', 1), ('head_sha', 'b' * 40),
                             ('path', '.github/workflows/other.yml'), ('run_attempt', 1)):
            run, jobs = evidence(); run[field] = value
            with self.subTest(field=field), self.assertRaises(GateError):
                validate_run(run, jobs, SHA, 12, 2, SHA)
        run, jobs = evidence(); run['head_repository']['id'] = 1
        with self.assertRaises(GateError): validate_run(run, jobs, SHA, 12, 2, SHA)

    def test_newer_work_ref_rejected(self):
        with self.assertRaises(GateError): validate_run(*evidence(), SHA, 12, 2, 'b' * 40)


class ResourceGateTests(unittest.TestCase):
    def policy(self):
        return {'schema': 1, 'status': 'measured', 'method': 'isolated-daemon-stream-load-v1',
                'image_archive_sha256': 'c' * 64, 'peak_total_bytes': 512 * 1024**2,
                'reserve_bytes': 256 * 1024**2, 'disk_reserve_bytes': 10 * 1024**3,
                'measurement_run_url': 'https://github.com/P-GISE/Fact-checking-website/actions/runs/123',
                'oom_events': 0, 'platform': 'linux/amd64'}

    def test_unmeasured_policy_fails(self):
        for policy in ({}, {'schema': 1, 'status': 'unmeasured'}, None):
            with self.assertRaises(GateError):
                validate_resources(policy, 'c' * 64, 10**12, 10**12, 10**12, 100, 100)

    def test_measured_policy_and_each_resource_boundary(self):
        p = self.policy(); mem = p['peak_total_bytes'] + p['reserve_bytes']
        # Same filesystem: reserve + compressed archive + expanded images + rollback images.
        disk = 10 * 1024**3 + 300 + 600 + 600
        validate_resources(p, 'c' * 64, mem, disk, disk, 300, 600)
        for memory, scratch, docker in ((mem-1,disk,disk),(mem,disk-1,disk),(mem,disk,disk-1)):
            with self.assertRaises(GateError):
                validate_resources(p, 'c'*64, memory, scratch, docker, 300, 600)

    def test_wrong_bundle_oom_or_untrusted_measurement_rejected(self):
        for field, value in (('image_archive_sha256','d'*64), ('oom_events',1),
                             ('measurement_run_url','https://example.com/run'),
                             ('peak_total_bytes',0), ('platform','linux/arm64')):
            p=self.policy(); p[field]=value
            with self.subTest(field=field), self.assertRaises(GateError):
                validate_resources(p,'c'*64,10**12,10**12,10**12,300,600)


class ArchiveGateTests(unittest.TestCase):
    def make(self, folder, attack=None):
        path=Path(folder)/'images.tar.gz'; ids={}; rows=[]
        with tarfile.open(path,'w:gz') as output:
            def add(name, content):
                entry=tarfile.TarInfo(name); entry.size=len(content)
                output.addfile(entry,io.BytesIO(content))
            for component in ('api','web','worker'):
                config={'os':'linux','architecture':'amd64','config':{'Labels':{
                    'org.opencontainers.image.revision':SHA,'io.factlens.migration-control':'v1'}}}
                runtime={
                    'api':('node',['node','apps/api/dist/server.js'],['docker-entrypoint.sh']),
                    'worker':('worker',['python','-m','factlens.main'],None),
                    'web':('nginx',['nginx','-g','daemon off;'],['/docker-entrypoint.sh'])}[component]
                config['config'].update(zip(('User','Cmd','Entrypoint'),runtime))
                if attack=='runtime' and component=='worker':config['config']['User']='root'
                if attack=='revision' and component=='api':
                    config['config']['Labels']['org.opencontainers.image.revision']='b'*40
                if attack=='migration' and component=='api':
                    del config['config']['Labels']['io.factlens.migration-control']
                data=json.dumps(config).encode(); digest=hashlib.sha256(data).hexdigest()
                ids[component]='sha256:'+digest
                filename=component+'.json'; add(filename,data)
                rows.append({'Config':filename,'RepoTags':[f'factlens-{component}:{SHA}'],'Layers':[]})
            if attack=='extra': rows.append(rows[0])
            if attack=='traversal': add('../outside',b'no')
            if attack=='symlink':
                entry=tarfile.TarInfo('link');entry.type=tarfile.SYMTYPE;entry.linkname='outside';output.addfile(entry)
            if attack=='duplicate': add('api.json',b'{}')
            add('manifest.json',json.dumps(rows).encode())
        return path,ids

    def test_exact_three_valid_images(self):
        with tempfile.TemporaryDirectory() as directory:
            path,ids=self.make(directory)
            self.assertGreater(validate_archive(path,SHA,ids,1024**2),0)

    def test_attacker_archives_rejected_before_load(self):
        for attack in ('revision','migration','runtime','extra','traversal','symlink','duplicate'):
            with self.subTest(attack=attack), tempfile.TemporaryDirectory() as directory:
                path,ids=self.make(directory,attack)
                with self.assertRaises(GateError): validate_archive(path,SHA,ids,1024**2)

    def test_config_digest_and_expansion_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            path,ids=self.make(directory);ids['api']='sha256:'+'d'*64
            with self.assertRaises(GateError):validate_archive(path,SHA,ids,1024**2)
            path,ids=self.make(directory)
            with self.assertRaises(GateError):validate_archive(path,SHA,ids,1)


if __name__ == '__main__': unittest.main()
