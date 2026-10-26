"""Pilot boundaries: no production eligibility, publication, credentials, or policy mutation."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


class ImportPilotTests(unittest.TestCase):
    def test_private_daemon_cannot_inherit_host_configuration(self):
        script=(ROOT/'devtools/measure-prebuilt-import.sh').read_text()
        self.assertIn("printf '{}\\n' > \"$benchmark/daemon-config.json\"",script)
        self.assertIn('dockerd --config-file="$benchmark/daemon-config.json"',script)
        self.assertLess(script.index('umask 077'),script.index('daemon-config.json'))
        self.assertNotIn('/etc/docker/daemon.json',script)
        self.assertNotIn('--feature',script)

    @unittest.skipIf(os.name=='nt','actual shell scanner aggregation executes on standard Linux CI')
    def test_image_failure_collects_all_three_images_and_still_fails(self):
        scanner=(ROOT/'devtools/scan-prebuilt-images.sh').read_text()
        loop='overall=0'+scanner.split('overall=0',1)[1]
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);tool=folder/'trivy'
            tool.write_text('''#!/usr/bin/env bash
set -eu
tag=${!#}
component=${tag#factlens-}; component=${component%%:*}
echo "$component" >> "$SCANNER_CALL_LOG"
while (($#)); do if [[ $1 == --output ]]; then output=$2; break; fi; shift; done
findings='[]'
if [[ $component == api ]]; then findings='[{"Severity":"HIGH","VulnerabilityID":"SYNTHETIC-TEST","PkgName":"synthetic"}]'; fi
printf '{"Results":[{"Class":"os-pkgs","Packages":[{}],"Vulnerabilities":%s},{"Class":"lang-pkgs","Packages":[{}]}]}\\n' "$findings" > "$output"
[[ $component != api ]]
''');tool.chmod(0o700)
            result=subprocess.run(['bash','-c','set -euo pipefail; scan="$1"; shift; '+loop,
                                   'scanner-aggregation',directory,'a'*40],capture_output=True,text=True,
                                  env={**os.environ,'SCANNER_CALL_LOG':str(folder/'calls')})
            self.assertNotEqual(result.returncode,0)
            self.assertEqual((folder/'calls').read_text().splitlines(),['api','worker','web'])
            for component in ('api','worker','web'):
                self.assertTrue((folder/(component+'.json')).exists())

    def test_workflow_is_pr_only_and_has_no_publication_or_production_capability(self):
        workflow=(ROOT/'.github/workflows/import-measurement-pilot.yml').read_text()
        self.assertIn('  pull_request:',workflow)
        self.assertNotIn('  push:',workflow)
        for forbidden in ('workflow_dispatch:','secrets.','environment:','upload-artifact@',
                          'docker push','scp ','ssh ','build-prebuilt.py','deploy-prebuilt.sh'):
            self.assertNotIn(forbidden,workflow)
        self.assertIn('needs: security',workflow)
        self.assertIn('runs-on: ubuntu-24.04',workflow)
        self.assertIn('contents: read',workflow)
        self.assertIn('persist-credentials: false',workflow)

    def test_pilot_mode_is_not_read_by_any_publisher_or_production_entry(self):
        for name in ('devtools/build-prebuilt.py','devtools/deploy-prebuilt.sh',
                     '.github/workflows/deploy.yml','devtools/import-resource-policy.json'):
            self.assertNotIn('PILOT_MEASURE_IMPORT',(ROOT/name).read_text(),name)
        self.assertEqual(json.loads((ROOT/'devtools/import-resource-policy.json').read_text())['status'],'unmeasured')

    def summarize(self,measurement,status=0,sca=0):
        path=ROOT/'devtools/summarize-import-pilot.py'
        spec=importlib.util.spec_from_file_location('pilot_summary',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module.summarize(measurement,status,sca)

    def measurement(self):
        return {'status':'measurement-requires-review','method':'isolated-daemon-stream-load-v1',
                'platform':'linux/amd64','peak_total_bytes':123456789,'oom_events':0,
                'isolation_verified':True,'isolation_version':2,
                'isolation_before':{'verified':True},'isolation_after':{'verified':True},
                'memory_max_bytes':768*1024**2,'memory_swap_max_bytes':0,'memory_swap_peak_bytes':0,
                'docker_server_version':'29.1.3','docker_driver':'overlayfs',
                'docker_driver_status':[['driver-type','io.containerd.snapshotter.v1']]}

    def test_real_measurement_never_auto_approves_a_production_policy(self):
        summary,exit_code=self.summarize(self.measurement())
        self.assertEqual(exit_code,0)
        self.assertTrue(summary['docker_engine_driver_match'])
        self.assertFalse(summary['runtime_equivalent_to_s2'])
        self.assertFalse(summary['production_envelope_approved'])
        self.assertEqual(summary['uploaded_artifacts'],0)

    def test_failures_zero_or_wrong_runtime_cannot_become_a_production_baseline(self):
        for change in ({'peak_total_bytes':0},{'oom_events':1},{'docker_driver':'overlay2'},
                       {'docker_server_version':'28.0.0'},{'docker_driver_status':[]},
                       {'isolation_verified':False},{'isolation_after':{'verified':False}}):
            data=self.measurement();data.update(change)
            summary,exit_code=self.summarize(data)
            self.assertNotEqual(exit_code,0)
            self.assertFalse(summary['production_envelope_approved'])
        for status,sca in ((1,0),(0,1),(2,0)):
            _,exit_code=self.summarize(self.measurement(),status,sca)
            self.assertNotEqual(exit_code,0)

    def test_bounded_import_rejects_missing_limits_swap_or_peak_above_cap(self) -> None:
        measurement=self.measurement()
        measurement.update({'memory_max_bytes':768*1024**2,'memory_swap_max_bytes':0,
                            'memory_swap_peak_bytes':0})
        _,status=self.summarize(measurement)
        self.assertEqual(status,0)
        for change in ({'memory_max_bytes':3*1024**3},{'memory_max_bytes':None},
                       {'memory_swap_max_bytes':None},{'memory_swap_max_bytes':1024},
                       {'memory_swap_peak_bytes':1},{'memory_swap_peak_bytes':None},
                       {'peak_total_bytes':768*1024**2+1}):
            with self.subTest(change=change):
                candidate={**measurement,**change}
                summary,status=self.summarize(candidate)
                self.assertNotEqual(status,0)
                self.assertNotIn('peak_total_bytes',summary['measurement'])
                self.assertFalse(summary['production_envelope_approved'])


if __name__=='__main__':unittest.main()
