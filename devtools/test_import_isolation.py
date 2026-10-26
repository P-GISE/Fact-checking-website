import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('isolation',ROOT/'devtools/check-import-isolation.py')
gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)


class ImportIsolationTests(unittest.TestCase):
    def test_helper_cannot_auto_reuse_host_containerd_and_proves_before_after_unpack(self):
        script=(ROOT/'devtools/measure-prebuilt-import.sh').read_text()
        for required in ('containerd --config "$benchmark/containerd.toml" --address "$benchmark/containerd.sock"',
                         '--root "$benchmark/containerd-root" --state "$benchmark/containerd-state"',
                         '--containerd="$benchmark/containerd.sock"','isolation-before.json','isolation-after.json',
                         'create --pull=never --network none --entrypoint /bin/true'):
            self.assertIn(required,script)
        self.assertLess(script.index('> "$benchmark/isolation-before.json"'),script.index('gzip -dc'))
        self.assertGreater(script.index('> "$benchmark/isolation-after.json"'),script.index('create --pull=never'))
        self.assertNotIn('/run/containerd/containerd.sock',script)

    def fixture(self,folder):
        root=folder/'private';root.mkdir();proc=folder/'proc';(proc/'self').mkdir(parents=True)
        (proc/'self/cgroup').write_text('0::/system.slice/synthetic.service\n')
        pids={'dockerd':101,'containerd':102};bins={}
        options={'dockerd':{'--config-file':root/'daemon-config.json','--containerd':root/'containerd.sock',
                           '--data-root':root/'data','--exec-root':root/'exec','--host':'unix://'+str(root/'docker.sock')},
                 'containerd':{'--config':root/'containerd.toml','--address':root/'containerd.sock',
                               '--root':root/'containerd-root','--state':root/'containerd-state'}}
        for name,pid in pids.items():
            binary=folder/(name+'-binary');binary.write_bytes(('synthetic-'+name).encode());bins[name]=binary
            directory=proc/str(pid);directory.mkdir()
            # The function accepts a test proc tree; real CI reads kernel /proc directly.
            (directory/'exe').hardlink_to(binary)
            (directory/'cgroup').write_text('0::/system.slice/synthetic.service\n')
            (directory/'cmdline').write_bytes(('\0'.join([str(binary)]+[f'{k}={v}' for k,v in options[name].items()])+'\0').encode())
        return root,proc,pids,bins

    def test_actual_process_isolation_accepts_private_daemons(self):
        with tempfile.TemporaryDirectory() as directory:
            root,proc,pids,bins=self.fixture(Path(directory))
            self.assertTrue(gate.verify(root,pids,bins,proc)['verified'])

    def test_host_containerd_group_or_socket_and_wrong_binary_are_rejected(self):
        for attack in ('cgroup','socket','binary'):
            with self.subTest(attack=attack),tempfile.TemporaryDirectory() as directory:
                root,proc,pids,bins=self.fixture(Path(directory));target=proc/'102'
                if attack=='cgroup':(target/'cgroup').write_text('0::/system.slice/containerd.service\n')
                if attack=='socket':
                    (target/'cmdline').write_bytes((target/'cmdline').read_bytes().replace(str(root/'containerd.sock').encode(),b'/run/containerd/containerd.sock'))
                if attack=='binary':bins['containerd']=bins['dockerd']
                with self.assertRaises(ValueError):gate.verify(root,pids,bins,proc)


if __name__=='__main__':unittest.main()
