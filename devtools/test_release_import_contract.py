"""Offline exact-source/profile/isolation checks; no Docker or CI credentials used."""
import copy
from contextlib import contextmanager
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import stat
import re
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import prebuilt_gate as gate

ROOT = Path(__file__).resolve().parents[1]
SHA = 'a' * 40
DIGEST = 'c' * 64


def release_profile():
    profile = json.loads((ROOT / 'devtools/docker29-pilot-profile.json').read_text())
    return {**profile, 'kind': 'ci-release-measurement-only'}


def profile_digest(profile):
    return hashlib.sha256(json.dumps(profile, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def measurement(status='measured'):
    profile = release_profile()
    processes = {
        name: {'pid': 101 + index, 'cgroup_matches_measurement': True,
               'binary_sha256': profile['binary_sha256'][name],
               'cgroup': '0::/system.slice/factlens-import-measure-12-2.service',
               'private_address_and_paths': True}
        for index, name in enumerate(('dockerd', 'containerd'))
    }
    proof = {'verified': True, 'processes': processes}
    tools = {name: {'device': 1, 'inode': 200 + index, 'mode': 0o700,
                    'binary_sha256': digest, 'executable': True}
             for index, (name, digest) in enumerate(profile['binary_sha256'].items())}
    return {'schema': 1, 'status': status, 'method': 'isolated-daemon-stream-load-v1',
            'platform': 'linux/amd64', 'image_archive_sha256': DIGEST,
            'peak_total_bytes': 512 * 1024**2, 'reserve_bytes': 256 * 1024**2,
            'disk_reserve_bytes': 10 * 1024**3, 'oom_events': 0,
            'measurement_run_url': 'https://github.com/P-GISE/Fact-checking-website/actions/runs/12',
            'source_sha': SHA, 'measurement_run_id': 12, 'measurement_run_attempt': 2,
            'runtime_profile_sha256': profile_digest(profile),
            'runtime_profile_kind': profile['kind'],
            'docker_server_version': profile['version'], 'docker_driver': profile['required_driver'],
            'docker_driver_status': [['driver-type', profile['required_snapshotter']]],
            'isolation_verified': True, 'isolation_version': 2,
            'isolation_before': proof, 'isolation_after': copy.deepcopy(proof),
            'tool_identity_version': 1, 'tool_identity_before': tools, 'tool_identity_after': copy.deepcopy(tools)}


def context():
    return {'sha': SHA, 'run_id': 12, 'attempt': 2, 'profile': release_profile()}


@contextmanager
def posix_tool_metadata(root, nonexecutable=None):
    """Windows lacks POSIX execute bits; real chmod is tested on Linux without mocks."""
    if os.name != 'nt':
        yield; return
    lstat = Path.lstat; fstat = os.fstat
    def mode(value, bits):
        fields = list(value); fields[0] = stat.S_IFMT(value.st_mode) | bits
        return os.stat_result(fields)
    def local_lstat(path, *args, **kwargs):
        value = lstat(path, *args, **kwargs)
        return mode(value, 0o600 if path.name == nonexecutable else 0o700) if path.parent == root else value
    with patch.object(Path, 'lstat', local_lstat), \
            patch.object(os, 'fstat', lambda fd: mode(fstat(fd), 0o700)):
        yield


class ReleaseImportContractTests(unittest.TestCase):
    def test_draft_pr_skips_heavy_pilot_but_keeps_light_verification(self):
        pilot = (ROOT / '.github/workflows/import-measurement-pilot.yml').read_text()
        job = pilot.split('\n  measurement-only:', 1)[1]
        condition = re.search(r'^    if: (.+)$', job, re.MULTILINE)
        self.assertIsNotNone(condition)
        self.assertEqual(condition.group(1), "github.event_name == 'pull_request' && github.event.pull_request.draft == false")
        for draft, expected in ((True, False), (False, True)):
            with self.subTest(draft=draft):
                evaluated = condition.group(1).replace("github.event_name", repr('pull_request')).replace('github.event.pull_request.draft', repr(draft)).replace('false', 'False').replace('&&', 'and')
                self.assertEqual(eval(evaluated, {'__builtins__': {}}), expected)
        workflow = (ROOT / '.github/workflows/deploy.yml').read_text()
        verification = workflow.split('\n  verify:', 1)[1].split('\n  deploy:', 1)[0]
        self.assertNotIn('draft', verification)
        self.assertNotIn('    if:', verification)

    def validate(self, data, **overrides):
        expected = context(); expected.update(overrides)
        return gate.validate_import_measurement(data, DIGEST, **expected)

    def test_legacy_resource_proof_is_not_accepted_as_measured_v2(self):
        gate.validate_resources(measurement(), DIGEST, 10**12, 10**12, 10**12, 300, 600, **context())
        data = measurement()
        for key in ('isolation_before', 'isolation_after', 'isolation_version', 'isolation_verified'):
            data.pop(key)
        with self.assertRaises(gate.GateError):
            gate.validate_resources(data, DIGEST, 10**12, 10**12, 10**12, 300, 600, **context())

    def test_exact_current_profile_proof_accepts(self):
        self.validate(measurement())

    def test_wrong_source_run_attempt_bundle_profile_and_legacy_proof_reject(self):
        changes = [('source_sha', 'b' * 40), ('measurement_run_id', 13),
                   ('measurement_run_attempt', 1), ('image_archive_sha256', 'd' * 64),
                   ('runtime_profile_sha256', 'e' * 64), ('runtime_profile_kind', 'ci-pilot-only'),
                   ('isolation_version', 1), ('isolation_verified', False),
                   ('measurement_run_url', 'https://github.com/P-GISE/Fact-checking-website/actions/runs/13'),
                   ('docker_server_version', '28.0.0'), ('docker_driver_status', []),
                   ('oom_events', 1), ('oom_events', False)]
        for key, value in changes:
            data = measurement(); data[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(gate.GateError):
                self.validate(data)

    def test_missing_or_changed_before_after_daemons_reject(self):
        for change in ('verified', 'missing', 'pid', 'pid-bool', 'same-pid', 'hash',
                       'cgroup', 'both-cgroups', 'private', 'group-match'):
            data = measurement(); after = data['isolation_after']; proc = after['processes']['containerd']
            if change == 'verified': after['verified'] = False
            if change == 'missing': del after['processes']['containerd']
            if change == 'pid': proc['pid'] = 999
            if change == 'pid-bool': proc['pid'] = True
            if change == 'same-pid':
                for key in ('isolation_before', 'isolation_after'):
                    data[key]['processes']['containerd']['pid'] = 101
            if change == 'hash': proc['binary_sha256'] = 'f' * 64
            if change == 'cgroup': proc['cgroup'] = '0::/system.slice/containerd.service'
            if change == 'both-cgroups':
                for key in ('isolation_before', 'isolation_after'):
                    for row in data[key]['processes'].values(): row['cgroup'] = '0::/other.service'
            if change == 'private': proc['private_address_and_paths'] = False
            if change == 'group-match': proc['cgroup_matches_measurement'] = False
            with self.subTest(change=change), self.assertRaises(gate.GateError):
                self.validate(data)

    def test_review_pending_does_not_validate_as_published_measurement(self):
        with self.assertRaises(gate.GateError): self.validate(measurement('measurement-requires-review'))
        gate.validate_import_measurement(measurement('measurement-requires-review'), DIGEST,
                                         **context(), status='measurement-requires-review')

    def test_source_unmeasured_or_other_profile_envelope_cannot_approve_fixture(self):
        profile = release_profile()
        policy = {'status': 'approved-measurement-envelope', 'max_import_peak_bytes': 1024**3,
                  'reserve_bytes': 512 * 1024**2,
                  'baseline_run_url': 'https://github.com/P-GISE/Fact-checking-website/actions/runs/123',
                  'runtime_profile_sha256': profile_digest(profile)}
        gate.validate_release_envelope(policy, profile)
        for key, value in (('status', 'unmeasured'), ('runtime_profile_sha256', 'f' * 64),
                           ('max_import_peak_bytes', True), ('reserve_bytes', 0)):
            altered = {**policy, key: value}
            with self.subTest(key=key), self.assertRaises(gate.GateError):
                gate.validate_release_envelope(altered, profile)
        for key, value in (('kind', 'ci-pilot-only'), ('memory_max_bytes', 1024),
                           ('binary_sha256', {}), ('required_driver', 'overlay2')):
            altered = {**profile, key: value}
            with self.subTest(profile_key=key), self.assertRaises(gate.GateError):
                gate.validate_import_measurement(measurement(), DIGEST, SHA, 12, 2, altered)

    def produce_measurement(self, events='oom 0\noom_kill 0\n'):
        source = (ROOT / 'devtools/measure-prebuilt-import.sh').read_text()
        producer = source.split("<<'PY'\n", 1)[1].split('\nPY\n', 1)[0]
        expected = measurement()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); group = root / 'group'; group.mkdir()
            (group / 'memory.events').write_text(events)
            (group / 'memory.peak').write_text(str(expected['peak_total_bytes']))
            (root / 'runtime.json').write_text(json.dumps({'server_version': expected['docker_server_version'],
                'driver': expected['docker_driver'], 'driver_status': expected['docker_driver_status']}))
            (root / 'components.json').write_text('[]')
            for name in ('before', 'after'):
                (root / f'isolation-{name}.json').write_text(json.dumps(expected[f'isolation_{name}']))
            (root / 'tool-identities.json').write_text(json.dumps(expected['tool_identity_before']))
            (root / 'tool-identities-after.json').write_text(json.dumps(expected['tool_identity_after']))
            profile = root / 'profile.json'; profile.write_text(json.dumps(release_profile()))
            output = root / 'measurement.json'
            arguments = ['producer', str(output), DIGEST, expected['measurement_run_url'],
                         str(group), SHA, '2', str(profile)]
            with patch.object(sys, 'argv', arguments), \
                    patch.object(os, 'uname', return_value=SimpleNamespace(release='synthetic', machine='x86_64'),
                                 create=True):
                exec(compile(producer, '<actual measurement JSON producer>', 'exec'), {})
            actual = json.loads(output.read_text())
            return actual

    def test_actual_measurement_json_producer_binds_source_and_profile(self):
        actual = self.produce_measurement()
        gate.validate_import_measurement(actual, DIGEST, **context(), status='measurement-requires-review')
        self.assertEqual(actual['runtime_profile_sha256'], profile_digest(release_profile()))

    def test_tool_identity_proof_requires_all_executable_pinned_files_without_drift(self):
        self.validate(measurement())
        for change in ('missing-proof', 'missing-cli', 'hash', 'mode', 'executable', 'inode', 'device', 'inode-bool'):
            data = measurement(); after = data['tool_identity_after']
            if change == 'missing-proof': data.pop('tool_identity_before')
            if change == 'missing-cli': after.pop('docker')
            if change == 'hash': after['docker']['binary_sha256'] = 'e' * 64
            if change == 'mode': after['docker']['mode'] = 0o600
            if change == 'executable': after['docker']['executable'] = False
            if change == 'inode': after['docker']['inode'] += 1
            if change == 'device': after['docker']['device'] += 1
            if change == 'inode-bool': after['docker']['inode'] = True
            with self.subTest(change=change), self.assertRaises(gate.GateError): self.validate(data)

    def test_producer_requires_present_unique_nonnegative_numeric_oom_counters(self):
        for events in ('', 'oom 0\n', 'oom_kill 0\n', 'oom 0\noom 0\noom_kill 0\n',
                       'oom 0\noom_kill 0\noom_kill 0\n', 'oom -1\noom_kill 0\n',
                       'oom 0\noom_kill -1\n', 'oom invalid\noom_kill 0\n',
                       'oom 0\noom_kill invalid\n', 'oom 1\noom_kill 0\n'):
            with self.subTest(events=events), self.assertRaises((SystemExit, ValueError)):
                self.produce_measurement(events)

    def test_ci_shell_syntax_check_reads_each_file(self):
        lines = (ROOT / '.github/workflows/deploy.yml').read_text().splitlines()
        index = next(i for i, line in enumerate(lines) if line.strip().startswith(
            ('bash -n devtools/', 'for script in devtools/')))
        check = '\n'.join(line.strip() for line in lines[index:index + (3 if 'for script' in lines[index] else 1)])
        names = re.findall(r'devtools/[a-z0-9-]+\.sh', check)
        self.assertGreater(len(names), 1)
        bash = 'C:/Program Files/Git/bin/bash.exe' if os.name == 'nt' else 'bash'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for bad in names[1:]:
                command = check
                for name in names:
                    script = root / Path(name).name
                    script.write_text('if then\n' if name == bad else '#!/bin/bash\ntrue\n')
                    command = command.replace(name, '"' + script.as_posix() + '"')
                result = subprocess.run([bash, '-c', 'set -e; ' + command], capture_output=True)
                with self.subTest(bad=bad): self.assertNotEqual(result.returncode, 0)

    def test_release_prepare_flags_on_still_rejects_current_unmeasured_policy_before_docker(self):
        bash = 'C:/Program Files/Git/bin/bash.exe' if os.name == 'nt' else 'bash'
        with tempfile.TemporaryDirectory() as directory:
            # python3 is a local test wrapper, not a global installation or real Docker command.
            command = 'python3() { "$PYTHON3" -I -X utf8 -B "$@"; }; export -f python3; bash devtools/prepare-docker29-release.sh'
            result = subprocess.run([bash, '-c', command], cwd=ROOT, capture_output=True,
                env={**os.environ, 'GITHUB_ACTIONS': 'true', 'GITHUB_REPOSITORY': 'P-GISE/Fact-checking-website',
                     'GITHUB_EVENT_NAME': 'push', 'GITHUB_REF': 'refs/heads/work',
                     'FACTLENS_PREBUILT_ENABLED': 'true', 'ARTIFACT_STORAGE_APPROVED': 'true',
                     'RUNNER_TEMP': directory, 'GITHUB_OUTPUT': str(Path(directory) / 'output'),
                     'PYTHON3': Path(sys.executable).as_posix()})
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b'Reviewed measured import envelope required', result.stderr)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_workflow_keeps_prebuilt_opt_in_and_runs_new_contract_checks(self):
        workflow = (ROOT / '.github/workflows/deploy.yml').read_text()
        verify = workflow.split('\n  verify:', 1)[1].split('\n  deploy:', 1)[0]
        self.assertIn('-p test_release_import_contract.py', verify)
        release = workflow.split('\n  build-publish:', 1)[1].split('\n  deploy-prebuilt:', 1)[0]
        self.assertIn("vars.FACTLENS_PREBUILT_ENABLED == 'true'", release)
        self.assertIn('FACTLENS_MEASUREMENT_TOOL_DIR: ${{ steps.measurement-tools.outputs.tool-dir }}', release)
        self.assertLess(release.index('bash devtools/prepare-docker29-release.sh'),
                        release.index('python3 devtools/build-prebuilt.py'))
        self.assertEqual(json.loads((ROOT / 'devtools/import-resource-policy.json').read_text())['status'],
                         'unmeasured')

    def test_private_release_binary_verification_requires_explicit_profile_kind(self):
        spec = importlib.util.spec_from_file_location('private_tools', ROOT / 'devtools/verify-pilot-docker29.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); profile = release_profile()
            for name in profile['binary_sha256']:
                data = ('synthetic-' + name).encode(); (root / name).write_bytes(data)
                (root / name).chmod(0o700)
                profile['binary_sha256'][name] = hashlib.sha256(data).hexdigest()
            with posix_tool_metadata(root):
                with self.assertRaises(ValueError): module.verify(root, profile)
                module.verify(root, profile, 'ci-release-measurement-only')
                (root / 'containerd').write_bytes(b'changed')
                with self.assertRaises(ValueError): module.verify(root, profile, 'ci-release-measurement-only')

    def test_private_binary_execute_bit_and_inode_drift_are_rejected(self):
        spec = importlib.util.spec_from_file_location('tool_modes', ROOT / 'devtools/verify-pilot-docker29.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); profile = release_profile()
            for name in profile['binary_sha256']:
                data = ('synthetic-' + name).encode(); (root / name).write_bytes(data); (root / name).chmod(0o700)
                profile['binary_sha256'][name] = hashlib.sha256(data).hexdigest()
            with posix_tool_metadata(root):
                original = module.verify(root, profile, 'ci-release-measurement-only')
            (root / 'docker').chmod(0o600)
            with posix_tool_metadata(root, 'docker'), self.assertRaises(ValueError):
                module.verify(root, profile, 'ci-release-measurement-only')
            (root / 'docker').chmod(0o700)
            replacement = root / 'replacement'; replacement.write_bytes((root / 'docker').read_bytes())
            replacement.chmod(0o700); replacement.replace(root / 'docker')
            with posix_tool_metadata(root), self.assertRaises(ValueError):
                module.verify(root, profile, 'ci-release-measurement-only', expected_identity=original)

    @unittest.skipIf(os.name == 'nt', 'real POSIX execute-bit/PATH fallback scenario runs on Linux CI')
    def test_nonexecuting_private_cli_never_reaches_later_host_cli(self):
        source = (ROOT / 'devtools/measure-prebuilt-import.sh').read_text()
        invocation = next(line.strip() for line in source.splitlines() if line.strip().startswith(
            ('"$docker_cli" --host="$socket" info >/dev/null', 'docker --host="$socket" info >/dev/null')))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); tools = root / 'private'; tools.mkdir(); host = root / 'host'; host.mkdir()
            profile = release_profile()
            for name in profile['binary_sha256']:
                data = b'#!/bin/sh\nprintf "private\\n" >> "$PRIVATE_CALL_LOG"\n'
                (tools / name).write_bytes(data); (tools / name).chmod(0o700)
                profile['binary_sha256'][name] = hashlib.sha256(data).hexdigest()
            (host / 'docker').write_text('#!/bin/sh\nprintf "host\\n" >> "$HOST_CALL_LOG"\n')
            (host / 'docker').chmod(0o700)
            profile_file = root / 'profile.json'; profile_file.write_text(json.dumps(profile))
            command = ('set -e; tool_dir=$1; profile=$2; verifier=$3; '
                       'docker_cli="$tool_dir/docker"; socket=unix://synthetic; '
                       'export PATH="$tool_dir:$4:$PATH"; '
                       '"$PYTHON3" -I -B "$verifier" "$tool_dir" "$profile" ci-release-measurement-only >/dev/null; '
                       + invocation)
            env = {**os.environ, 'PYTHON3': sys.executable, 'PRIVATE_CALL_LOG': str(root / 'private-calls'),
                   'HOST_CALL_LOG': str(root / 'host-calls')}
            args = ['bash', '-c', command, 'private-tool-test', str(tools), str(profile_file),
                    str(ROOT / 'devtools/verify-pilot-docker29.py'), str(host)]
            positive = subprocess.run(args, capture_output=True, env=env)
            self.assertEqual(positive.returncode, 0, positive.stderr)
            self.assertEqual((root / 'private-calls').read_text(), 'private\n')
            self.assertFalse((root / 'host-calls').exists())
            (tools / 'docker').chmod(0o600)
            rejected = subprocess.run(args, capture_output=True, env=env)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertFalse((root / 'host-calls').exists())
            self.assertEqual((root / 'private-calls').read_text(), 'private\n')

    def test_publisher_forwards_exact_private_runtime_and_consumes_current_proof(self):
        spec = importlib.util.spec_from_file_location('publisher_forwarding', ROOT / 'devtools/build-prebuilt.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        calls = []
        def command(*args):
            calls.append(args)
            if args[0] == 'git': return SHA
            if args[0] == 'docker': return 'sha256:' + 'd' * 64
            if args[:2] == ('bash', 'devtools/measure-prebuilt-import.sh'):
                current = measurement('measurement-requires-review'); current['image_archive_sha256'] = args[3]
                return json.dumps(current)
            raise AssertionError('Unexpected process boundary')
        def run(*args, **kwargs):
            if args[0][0] == 'gzip': kwargs['stdout'].write(b'synthetic archive')
            return SimpleNamespace(returncode=0)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / 'devtools').mkdir()
            tools = root / 'factlens-docker29.synthetic'; tools.mkdir()
            profile = root / 'devtools/docker29-release-profile.json'; profile.write_text(json.dumps(release_profile()))
            envelope = {'status': 'approved-measurement-envelope', 'max_import_peak_bytes': 1024**3,
                        'reserve_bytes': 512 * 1024**2,
                        'baseline_run_url': 'https://github.com/P-GISE/Fact-checking-website/actions/runs/123',
                        'runtime_profile_sha256': profile_digest(release_profile())}
            (root / 'devtools/import-resource-policy.json').write_text(json.dumps(envelope))
            previous = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, {'GITHUB_SHA': SHA, 'GITHUB_RUN_ID': '12',
                        'GITHUB_RUN_ATTEMPT': '2', 'RUNNER_TEMP': directory, 'ARTIFACT_STORAGE_APPROVED': 'true',
                        'FACTLENS_MEASUREMENT_TOOL_DIR': str(tools)}, clear=True), \
                        patch.object(module, 'command', side_effect=command), \
                        patch.object(module, 'validate_archive', return_value=100), \
                        patch.object(module.subprocess, 'run', side_effect=run), \
                        patch.object(module.subprocess, 'Popen', return_value=SimpleNamespace(
                            stdout=io.BytesIO(b'synthetic image stream'), wait=lambda: 0)):
                    module.main()
                call = next(args for args in calls if args[0] == 'bash')
                self.assertEqual(call[-2:], (str(tools), str(profile.resolve())))
                manifest = json.loads((root / 'factlens-release/manifest.json').read_text())
                gate.validate_import_measurement(manifest['import_policy'], manifest['archive_sha256'], **context())
                self.assertEqual(manifest['import_policy']['reserve_bytes'], envelope['reserve_bytes'])
            finally: os.chdir(previous)

    def test_publisher_rejects_missing_private_tools_before_docker_or_output(self):
        spec = importlib.util.spec_from_file_location('release_publisher', ROOT / 'devtools/build-prebuilt.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / 'devtools').mkdir()
            (root / 'devtools/docker29-release-profile.json').write_text(json.dumps(release_profile()))
            policy = {'status': 'approved-measurement-envelope', 'max_import_peak_bytes': 1024**3,
                      'reserve_bytes': 512 * 1024**2,
                      'baseline_run_url': 'https://github.com/P-GISE/Fact-checking-website/actions/runs/123',
                      'runtime_profile_sha256': profile_digest(release_profile())}
            (root / 'devtools/import-resource-policy.json').write_text(json.dumps(policy))
            previous = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, {'GITHUB_SHA': SHA, 'GITHUB_RUN_ID': '12',
                                             'GITHUB_RUN_ATTEMPT': '2', 'RUNNER_TEMP': directory,
                                             'ARTIFACT_STORAGE_APPROVED': 'true'}, clear=True), \
                        patch.object(module, 'command', return_value=SHA), \
                        patch.object(module.subprocess, 'run', side_effect=AssertionError('Docker must not run')):
                    with self.assertRaises(gate.GateError): module.main()
                self.assertFalse((root / 'factlens-release').exists())
            finally: os.chdir(previous)


if __name__ == '__main__': unittest.main()
