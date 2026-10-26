"""Adversarial, offline checks: no GitHub credentials or Docker daemon required."""
import copy
import unittest
import tempfile
import tarfile
import io
import json
import hashlib
import zipfile
import os
import subprocess
import sys
from pathlib import Path
from prebuilt_gate import validate_run, validate_resources, validate_archive, validate_artifact, validate_artifact_zip, normalize_action_digest, GateError


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


class ArtifactGateTests(unittest.TestCase):
    def test_action_hex_and_api_prefixed_digest_match_without_accepting_other_algorithms(self):
        self.assertEqual(normalize_action_digest('c'*64),'sha256:'+'c'*64)
        self.assertEqual(normalize_action_digest('sha256:'+'c'*64),'sha256:'+'c'*64)
        for invalid in ('sha1:'+'c'*40,'sha256:sha256:'+'c'*64,'c'*63,'C'*64):
            with self.assertRaises(GateError):normalize_action_digest(invalid)

    def metadata(self):
        return {'id':34,'name':f'factlens-images-{SHA}-12-2','expired':False,
                'digest':'sha256:'+'c'*64,'size_in_bytes':100,'workflow_run':{
                    'id':12,'head_sha':SHA,'head_branch':'work','repository_id':1420151819,
                    'head_repository_id':1420151819}}

    def test_exact_artifact_metadata(self):
        validate_artifact(self.metadata(),34,12,SHA,2,'sha256:'+'c'*64)

    def test_wrong_expired_or_other_source_artifact(self):
        for field,value in (('id',35),('expired',True),('name','other'),('digest','sha256:'+'d'*64)):
            m=self.metadata();m[field]=value
            with self.subTest(field=field),self.assertRaises(GateError):
                validate_artifact(m,34,12,SHA,2,'sha256:'+'c'*64)
        m=self.metadata();m['workflow_run']['head_repository_id']=1
        with self.assertRaises(GateError):validate_artifact(m,34,12,SHA,2,'sha256:'+'c'*64)

    def test_zip_digest_inner_provenance_and_exact_files(self):
        for attack in (None,'digest','source','extra','inner'):
            with self.subTest(attack=attack),tempfile.TemporaryDirectory() as directory:
                path=Path(directory)/'artifact.zip';content=b'synthetic archive'
                digest=hashlib.sha256(content).hexdigest()
                manifest={'schema':1,'sha':SHA,'run_id':12,'run_attempt':2,'archive_sha256':digest}
                if attack=='source':manifest['run_attempt']=1
                with zipfile.ZipFile(path,'w') as output:
                    output.writestr('manifest.json',json.dumps(manifest))
                    output.writestr('checksums.sha256',digest+'  images.tar.gz\n')
                    output.writestr('images.tar.gz',content if attack!='inner' else b'changed')
                    if attack=='extra':output.writestr('../escape',b'no')
                outer='sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
                if attack=='digest':outer='sha256:'+'d'*64
                if attack:
                    with self.assertRaises(GateError):validate_artifact_zip(path,outer,SHA,12,2)
                else:self.assertEqual(validate_artifact_zip(path,outer,SHA,12,2),manifest)


class WorkflowBoundaryTests(unittest.TestCase):
    @unittest.skipIf(os.name=='nt','root ownership boundary executes on the actual Linux CI runner')
    def test_root_owned_private_measurement_is_read_without_relaxing_mode(self):
        root=Path(__file__).resolve().parents[1]
        script=(root/'devtools/measure-prebuilt-import.sh').read_text()
        line=next(row.strip() for row in script.splitlines() if 'cat -- "$benchmark/measurement.json"' in row)
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'source.json';source.write_text('{"synthetic":true}\n')
            target=Path(directory)/'measurement.json'
            subprocess.run(['sudo','install','-o','0','-g','0','-m','600',str(source),str(target)],check=True)
            try:
                with self.assertRaises(PermissionError):target.read_text()
                result=subprocess.check_output(['bash','-c','benchmark="$1"; '+line,'read-boundary',directory],text=True)
                self.assertEqual(json.loads(result),{'synthetic':True})
                self.assertEqual(target.stat().st_mode & 0o777,0o600)
                self.assertEqual(target.stat().st_uid,0)
            finally:subprocess.run(['sudo','rm','-f','--',str(target)],check=True)

    def test_image_sca_zero_coverage_findings_and_tool_errors_fail_closed(self):
        root=Path(__file__).resolve().parents[1]
        script=(root/'devtools/scan-prebuilt-images.sh').read_text()
        checker=script.split("<<'PY'\n",1)[1].split('\nPY\n',1)[0]
        good={'Results':[{'Class':'os-pkgs','Packages':[{'Name':'synthetic-os'}]},
                         {'Class':'lang-pkgs','Packages':[{'Name':'synthetic-library'}]}]}
        for attack in (None,'os-missing','library-missing','critical','error'):
            with self.subTest(attack=attack),tempfile.TemporaryDirectory() as directory:
                data=copy.deepcopy(good)
                if attack=='os-missing':data['Results'].pop(0)
                if attack=='library-missing':data['Results'].pop(1)
                if attack=='critical':data['Results'][0]['Vulnerabilities']=[{'Severity':'CRITICAL'}]
                report=Path(directory)/'report.json';report.write_text(json.dumps(data))
                status='2' if attack=='error' else '1' if attack=='critical' else '0'
                result=subprocess.run([sys.executable,'-c',checker,str(report),status,'api'],capture_output=True)
                self.assertEqual(result.returncode==0,attack is None)

    def test_unmeasured_source_cannot_even_prepare_publication(self):
        root=Path(__file__).resolve().parents[1]
        sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
        with tempfile.TemporaryDirectory() as directory:
            result=subprocess.run([sys.executable,'devtools/build-prebuilt.py'],cwd=root,capture_output=True,text=True,
                env={**os.environ,'GITHUB_SHA':sha,'GITHUB_RUN_ID':'12','GITHUB_RUN_ATTEMPT':'2',
                     'RUNNER_TEMP':directory,'ARTIFACT_STORAGE_APPROVED':'true'})
            self.assertNotEqual(result.returncode,0)
            self.assertFalse((Path(directory)/'factlens-release').exists())

    def test_publisher_and_prebuilt_deployment_require_all_gates_and_explicit_flag(self):
        root=Path(__file__).resolve().parents[1]
        workflow=(root/'.github/workflows/deploy.yml').read_text()
        self.assertIn("group: ${{ github.event_name == 'pull_request' && format('factlens-pr-{0}', github.event.pull_request.number) || 'factlens-production' }}",workflow)
        self.assertIn('cancel-in-progress: false',workflow.split('jobs:',1)[0])
        build=workflow.split('\n  build-publish:',1)[1].split('\n  deploy-prebuilt:',1)[0]
        deploy=workflow.split('\n  deploy-prebuilt:',1)[1]
        self.assertIn('needs: [security, verify]',build)
        self.assertIn('needs: [security, verify, build-publish]',deploy)
        for job in (build,deploy):
            self.assertIn("vars.FACTLENS_PREBUILT_ENABLED == 'true'",job)
            self.assertIn("github.event_name == 'push'",job)
            self.assertIn("github.ref == 'refs/heads/work'",job)
        self.assertLess(build.index('python3 devtools/build-prebuilt.py'),build.index('actions/upload-artifact@'))
        self.assertLess(deploy.index('fetch-prebuilt-run-evidence.py'),deploy.index('Prepare pinned SSH'))
        self.assertIn('"set -eu; umask 077; test ! -L .factlens-incoming;',deploy)
        self.assertIn('retention-days: 1',build)
        self.assertIn('compression-level: 0',build)


if __name__ == '__main__': unittest.main()
