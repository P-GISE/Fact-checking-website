#!/usr/bin/env python3
"""Fail-closed FactLens prebuilt provenance/resource validation. No mutations."""
import argparse
import json
import re
import sys
import hashlib
import tarfile
import zipfile
from pathlib import PurePosixPath
from pathlib import Path


class GateError(ValueError):
    pass


def sha256_file(path):
    hasher = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024**2), b''): hasher.update(block)
    return hasher.hexdigest()


def normalize_action_digest(value):
    # Pinned upload-artifact outputs hex; the REST artifact API includes the algorithm prefix.
    if re.fullmatch('[0-9a-f]{64}', value): return 'sha256:' + value
    require(bool(re.fullmatch('sha256:[0-9a-f]{64}', value)), 'Invalid action digest')
    return value


def validate_archive(archive, sha, expected_ids, expanded_limit):
    """Inspect without extracting Docker save metadata; never print image environment."""
    require(bool(re.fullmatch('[0-9a-f]{40}', sha)), 'Invalid source SHA')
    require(set(expected_ids) == {'api', 'web', 'worker'}, 'Exactly three component IDs required')
    require(type(expanded_limit) is int and 0 < expanded_limit <= 8 * 1024**3,
            'Invalid expansion limit')
    with tarfile.open(archive, 'r:gz') as bundle:
        names = set(); members = {}; expanded = 0
        for member in bundle:
            path = PurePosixPath(member.name)
            require(not path.is_absolute() and '..' not in path.parts and '\\' not in member.name,
                    'Unsafe archive path')
            require(member.isfile() or member.isdir(), 'Archive links/devices are forbidden')
            require(member.name not in names, 'Duplicate archive member')
            names.add(member.name); members[member.name] = member
            expanded += member.size
            require(expanded <= expanded_limit and len(names) <= 20000, 'Archive expansion limit')
        def document(name):
            member = members.get(name)
            require(member is not None and member.isfile() and member.size <= 1024**2,
                    'Missing/oversized archive metadata')
            content = bundle.extractfile(member).read()
            return content, json.loads(content)
        _, manifest = document('manifest.json')
        require(type(manifest) is list and len(manifest) == 3, 'Exactly three images required')
        seen = set()
        for row in manifest:
            tags = row.get('RepoTags', [])
            require(type(tags) is list and len(tags) == 1, 'Exactly one tag per image required')
            components = [component for component in expected_ids
                          if tags[0] == f'factlens-{component}:{sha}']
            require(len(components) == 1 and components[0] not in seen, 'Unexpected image tag')
            component = components[0]; seen.add(component)
            config_bytes, config = document(row['Config'])
            require('sha256:' + hashlib.sha256(config_bytes).hexdigest() == expected_ids[component],
                    'Image config digest mismatch')
            require(config.get('os') == 'linux' and config.get('architecture') == 'amd64',
                    'Unsupported image platform')
            settings = config.get('config', {})
            expected_runtime = {
                'api': ('node', ['node', 'apps/api/dist/server.js'], ['docker-entrypoint.sh']),
                'worker': ('worker', ['python', '-m', 'factlens.main'], None),
                'web': ('nginx', ['nginx', '-g', 'daemon off;'], ['/docker-entrypoint.sh']),
            }
            user, command, entrypoint = expected_runtime[component]
            require(settings.get('User') == user and settings.get('Cmd') == command and
                    settings.get('Entrypoint') == entrypoint, 'Image runtime contract mismatch')
            labels = settings.get('Labels') or {}
            require(labels.get('org.opencontainers.image.revision') == sha, 'Image revision mismatch')
            if component == 'api':
                require(labels.get('io.factlens.migration-control') == 'v1', 'Migration control required')
            for layer in row.get('Layers', []):
                require(layer in members and members[layer].isfile(), 'Missing image layer')
        return expanded


def require(condition, message):
    if not condition:
        raise GateError(message)


def validate_artifact(metadata, artifact_id, run_id, sha, attempt, expected_digest):
    require(type(artifact_id) is int and artifact_id > 0 and
            bool(re.fullmatch('sha256:[0-9a-f]{64}', expected_digest)), 'Invalid expected artifact identity')
    require(metadata.get('id') == artifact_id and metadata.get('expired') is False,
            'Missing or expired artifact')
    require(metadata.get('name') == f'factlens-images-{sha}-{run_id}-{attempt}', 'Artifact name mismatch')
    require(metadata.get('digest') == expected_digest, 'Artifact API digest mismatch')
    workflow = metadata.get('workflow_run') or {}
    require(workflow.get('id') == run_id and workflow.get('head_sha') == sha and
            workflow.get('head_branch') == 'work' and workflow.get('repository_id') == 1420151819 and
            workflow.get('head_repository_id') == 1420151819, 'Artifact source mismatch')
    require(type(metadata.get('size_in_bytes')) is int and
            0 < metadata['size_in_bytes'] <= 451 * 1024**2, 'Artifact size limit')


def validate_artifact_zip(path, expected_digest, sha, run_id, attempt):
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 451 * 1024**2,
            'Invalid artifact ZIP')
    require('sha256:' + sha256_file(path) == expected_digest, 'Downloaded artifact digest mismatch')
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        require(len(entries) == 3 and {row.filename for row in entries} ==
                {'images.tar.gz', 'manifest.json', 'checksums.sha256'}, 'Unexpected artifact files')
        for row in entries:
            require((row.external_attr >> 16) & 0o170000 in (0, 0o100000) and
                    not row.is_dir() and not row.flag_bits & 1, 'Unsafe artifact entry type')
            limit = 450 * 1024**2 if row.filename == 'images.tar.gz' else 1024**2
            require(0 < row.file_size <= limit, 'Artifact file size limit')
        manifest = json.loads(archive.read('manifest.json'))
        require(manifest.get('schema') == 1 and manifest.get('sha') == sha and
                manifest.get('run_id') == run_id and manifest.get('run_attempt') == attempt,
                'Inner manifest source mismatch')
        digest = manifest.get('archive_sha256', '')
        require(bool(re.fullmatch('[0-9a-f]{64}', digest)), 'Invalid inner digest')
        require(archive.read('checksums.sha256') == (digest + '  images.tar.gz\n').encode(),
                'Inner checksum declaration mismatch')
        hasher = hashlib.sha256()
        with archive.open('images.tar.gz') as stream:
            for block in iter(lambda: stream.read(1024**2), b''): hasher.update(block)
        require(hasher.hexdigest() == digest, 'Inner archive digest mismatch')
        return manifest


def validate_run(run, jobs, sha, run_id, attempt, current_work_sha):
    require(bool(re.fullmatch('[0-9a-f]{40}', sha)), 'Invalid source SHA')
    require(sha == current_work_sha, 'Source is no longer current work HEAD')
    require(run.get('id') == run_id and run.get('run_attempt') == attempt,
            'Run/attempt mismatch')
    require(run.get('repository', {}).get('id') == 1420151819 and
            run.get('repository', {}).get('full_name') == 'P-GISE/Fact-checking-website' and
            run.get('head_repository', {}).get('id') == 1420151819, 'Repository mismatch')
    require(run.get('workflow_id') == 390486634 and
            run.get('path') == '.github/workflows/deploy.yml', 'Workflow mismatch')
    require(run.get('event') == 'push' and run.get('head_branch') == 'work' and
            run.get('head_sha') == sha, 'Event/ref/SHA mismatch')
    # deploy itself is in progress: never demand whole-run completed/success.
    for name in ('verify', 'security / scan', 'build-publish'):
        matches = [job for job in jobs if job.get('name') == name]
        require(len(matches) == 1, 'Missing or duplicate prerequisite job')
        job = matches[0]
        require(job.get('status') == 'completed' and job.get('conclusion') == 'success' and
                job.get('head_sha') == sha and job.get('run_attempt') == attempt,
                'Prerequisite did not succeed for this exact source/attempt')


def runtime_profile_digest(profile):
    return hashlib.sha256(json.dumps(profile, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def validate_release_profile(profile):
    require(isinstance(profile, dict) and profile.get('kind') == 'ci-release-measurement-only' and
            profile.get('platform') == 'linux/amd64' and profile.get('version') == '29.1.3' and
            profile.get('required_driver') == 'overlayfs' and
            profile.get('required_snapshotter') == 'io.containerd.snapshotter.v1' and
            type(profile.get('memory_max_bytes')) is int and profile['memory_max_bytes'] == 3 * 1024**3,
            'Pinned CI release measurement profile required')
    hashes = profile.get('binary_sha256')
    require(isinstance(hashes, dict) and set(hashes) ==
            {'docker', 'dockerd', 'containerd', 'containerd-shim-runc-v2', 'ctr', 'runc', 'docker-proxy', 'docker-init'} and
            all(isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) for value in hashes.values()),
            'Complete pinned binary profile required')


def validate_release_envelope(policy, profile):
    validate_release_profile(profile)
    require(isinstance(policy, dict) and policy.get('status') == 'approved-measurement-envelope',
            'Reviewed measured import envelope required before building/publishing')
    for field in ('max_import_peak_bytes', 'reserve_bytes'):
        require(type(policy.get(field)) is int and policy[field] > 0, 'Invalid reviewed measurement envelope')
    require(bool(re.fullmatch(r'https://github\.com/P-GISE/Fact-checking-website/actions/runs/[0-9]+',
                             policy.get('baseline_run_url', ''))), 'Actual baseline measurement evidence required')
    require(policy.get('runtime_profile_sha256') == runtime_profile_digest(profile),
            'Reviewed measurement runtime profile mismatch')


def validate_import_measurement(policy, digest, sha, run_id, attempt, profile, *, status='measured'):
    require(isinstance(policy, dict) and type(policy.get('schema')) is int and policy['schema'] == 1 and
            status in ('measured', 'measurement-requires-review') and policy.get('status') == status,
            'Measured import policy required')
    validate_release_profile(profile)
    require(bool(re.fullmatch('[0-9a-f]{40}', sha or '')) and type(run_id) is int and run_id > 0 and
            type(attempt) is int and attempt > 0, 'Exact measurement source/run/attempt required')
    require(policy.get('source_sha') == sha and type(policy.get('measurement_run_id')) is int and
            policy['measurement_run_id'] == run_id and type(policy.get('measurement_run_attempt')) is int and
            policy['measurement_run_attempt'] == attempt and
            policy.get('measurement_run_url') ==
            f'https://github.com/P-GISE/Fact-checking-website/actions/runs/{run_id}',
            'Measurement source/run/attempt mismatch')
    require(bool(re.fullmatch('[0-9a-f]{64}', digest)) and
            policy.get('image_archive_sha256') == digest, 'Measurement bundle mismatch')
    require(policy.get('runtime_profile_sha256') == runtime_profile_digest(profile) and
            policy.get('runtime_profile_kind') == profile['kind'], 'Measurement runtime profile mismatch')
    require(policy.get('method') == 'isolated-daemon-stream-load-v1' and
            policy.get('platform') == profile.get('platform') == 'linux/amd64' and
            type(policy.get('oom_events')) is int and policy['oom_events'] == 0 and
            type(policy.get('peak_total_bytes')) is int and
            0 < policy['peak_total_bytes'] <= profile.get('memory_max_bytes', 0),
            'Unsupported or OOM measurement')
    require(policy.get('docker_server_version') == profile.get('version') and
            policy.get('docker_driver') == profile.get('required_driver') and
            isinstance(policy.get('docker_driver_status'), list) and
            ['driver-type', profile.get('required_snapshotter')] in policy['docker_driver_status'],
            'Measured runtime differs from source profile')
    require(type(policy.get('tool_identity_version')) is int and policy['tool_identity_version'] == 1,
            'Pinned executable tool identity proof required')
    previous_tools = None
    for key in ('tool_identity_before', 'tool_identity_after'):
        identities = policy.get(key)
        require(isinstance(identities, dict) and set(identities) == set(profile['binary_sha256']),
                'All private runtime tool identities required')
        for name, identity in identities.items():
            require(isinstance(identity, dict) and type(identity.get('device')) is int and identity['device'] >= 0 and
                    type(identity.get('inode')) is int and identity['inode'] > 0 and
                    type(identity.get('mode')) is int and identity['mode'] == 0o700 and
                    identity.get('executable') is True and
                    identity.get('binary_sha256') == profile['binary_sha256'][name],
                    'Private runtime tool executable/inode/digest mismatch')
        require(previous_tools is None or identities == previous_tools, 'Private tool identity drift during import')
        previous_tools = identities
    require(policy.get('isolation_verified') is True and type(policy.get('isolation_version')) is int and
            policy['isolation_version'] == 2, 'Private isolation v2 proof required')
    previous = None
    for key in ('isolation_before', 'isolation_after'):
        proof = policy.get(key)
        require(isinstance(proof, dict) and proof.get('verified') is True, 'Private daemon proof required')
        processes = proof.get('processes')
        require(isinstance(processes, dict) and set(processes) == {'dockerd', 'containerd'},
                'Both private daemon identities required')
        groups = set(); pids = set()
        for name, process in processes.items():
            require(isinstance(process, dict) and type(process.get('pid')) is int and process['pid'] > 1 and
                    process.get('cgroup_matches_measurement') is True and
                    process.get('private_address_and_paths') is True and
                    process.get('binary_sha256') == profile.get('binary_sha256', {}).get(name),
                    'Private daemon PID/binary/paths mismatch')
            group = process.get('cgroup', '')
            require(isinstance(group, str) and group.startswith('0::/') and '\n' not in group and
                    group.endswith(f'/factlens-import-measure-{run_id}-{attempt}.service'),
                    'Daemon outside exact measured run cgroup')
            groups.add(group); pids.add(process['pid'])
        require(len(groups) == 1 and len(pids) == 2, 'Distinct daemons in one measured cgroup required')
        require(previous is None or processes == previous, 'Daemon identity changed during import')
        previous = processes


def validate_resources(policy, digest, available_memory, scratch_free, docker_free,
                       compressed_bytes, expanded_bytes, *, sha=None, run_id=None, attempt=None, profile=None):
    validate_import_measurement(policy, digest, sha, run_id, attempt, profile)
    for key in ('peak_total_bytes', 'reserve_bytes', 'disk_reserve_bytes'):
        require(type(policy.get(key)) is int and policy[key] > 0, 'Invalid measured resource policy')
    require(policy['disk_reserve_bytes'] >= 10 * 1024**3, 'Disk reserve must preserve original 10 GiB floor')
    require(all(type(value) is int and value > 0 for value in
                (available_memory, scratch_free, docker_free, compressed_bytes, expanded_bytes)),
            'Invalid observed resources')
    require(available_memory >= policy['peak_total_bytes'] + policy['reserve_bytes'],
            'IMPORT_RESOURCE_MEMORY: preserve existing services')
    # Conservative both-filesystems bound also covers sharing a filesystem; old layers retained.
    required_disk = policy['disk_reserve_bytes'] + compressed_bytes + 2 * expanded_bytes
    require(scratch_free >= required_disk and docker_free >= required_disk,
            'IMPORT_RESOURCE_DISK: reserve plus archive/new/rollback images required')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--jobs', type=Path, required=True)
    parser.add_argument('--sha', required=True)
    parser.add_argument('--run-id', type=int, required=True)
    parser.add_argument('--attempt', type=int, required=True)
    parser.add_argument('--work-sha', required=True)
    args = parser.parse_args()
    try:
        validate_run(json.loads(args.run.read_text()), json.loads(args.jobs.read_text()),
                     args.sha, args.run_id, args.attempt, args.work_sha)
    except (GateError, OSError, ValueError, TypeError, KeyError):
        print('Prebuilt prerequisite evidence rejected.', file=sys.stderr)
        return 1
    print('Exact prerequisite jobs verified; current deployment remains in progress.')
    return 0


if __name__ == '__main__': sys.exit(main())
