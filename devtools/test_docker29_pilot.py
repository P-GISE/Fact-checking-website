import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('verify_tools',ROOT/'devtools/verify-pilot-docker29.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class Docker29PilotTests(unittest.TestCase):
    def test_verified_files_accept_then_tamper_missing_extra_or_production_profile_rejects(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            profile=json.loads((ROOT/'devtools/docker29-pilot-profile.json').read_text())
            for name in profile['binary_sha256']:
                data=('synthetic-'+name).encode();(root/name).write_bytes(data)
                profile['binary_sha256'][name]=hashlib.sha256(data).hexdigest()
            module.verify(root,profile)
            (root/'docker').write_bytes(b'tampered')
            with self.assertRaises(ValueError):module.verify(root,profile)
            (root/'docker').unlink()
            with self.assertRaises(ValueError):module.verify(root,profile)
            (root/'docker').write_bytes(b'synthetic-docker');(root/'extra').write_bytes(b'no')
            with self.assertRaises(ValueError):module.verify(root,profile)
            (root/'extra').unlink();profile['kind']='production'
            with self.assertRaises(ValueError):module.verify(root,profile)

    def test_private_prepare_does_not_start_install_or_change_global_path(self):
        script=(ROOT/'devtools/prepare-docker29-pilot.sh').read_text()
        self.assertIn('docker create --platform linux/amd64 --entrypoint /bin/true',script)
        self.assertIn('sha256:64d6ee47ea821c986467199baa162f5ac8cde3f57b719f18e23f3ed7a7444131',script)
        for forbidden in ('docker run','docker start','GITHUB_PATH','systemctl','/usr/bin/dockerd','apt-get','apk add'):
            self.assertNotIn(forbidden,script)
        self.assertIn('verify-pilot-docker29.py',script)

    def test_publisher_and_server_never_receive_pilot_profile(self):
        for name in ('devtools/build-prebuilt.py','devtools/deploy-prebuilt.sh','.github/workflows/deploy.yml',
                     'devtools/import-resource-policy.json'):
            source=(ROOT/name).read_text()
            for forbidden in ('PILOT_DOCKER29_TOOL_DIR','docker29-pilot-profile','prepare-docker29-pilot'):
                self.assertNotIn(forbidden,source,name)
        helper=(ROOT/'devtools/measure-prebuilt-import.sh').read_text()
        self.assertIn('--property=MemoryMax=768M',helper)
        self.assertIn('--property=MemorySwapMax=0',helper)
        self.assertIn('export PATH="$7:/usr/sbin:/usr/bin:/sbin:/bin"',helper)
        self.assertNotIn('--feature',helper)


if __name__=='__main__':unittest.main()
