#!/usr/bin/env python3
"""Check actual running binaries, private addresses and equal cgroups; print no raw argv."""
import hashlib
import json
from pathlib import Path
import sys


def sha(path):
    result=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024**2),b''):result.update(block)
    return result.hexdigest()


def flag(arguments,name):
    values=[]
    for index,arg in enumerate(arguments):
        if arg==name and index+1<len(arguments):values.append(arguments[index+1])
        elif arg.startswith(name+'='):values.append(arg.split('=',1)[1])
    if len(values)!=1:raise ValueError('Missing or ambiguous private process flag')
    return values[0]


def verify(root,pids,executables,proc=Path('/proc')):
    own=(proc/'self/cgroup').read_text().strip()
    if not own.startswith('0::/'):raise ValueError('Cgroup v2 required')
    expected={
        'containerd':{'--config':root/'containerd.toml','--address':root/'containerd.sock',
                      '--root':root/'containerd-root','--state':root/'containerd-state'},
        'dockerd':{'--config-file':root/'daemon-config.json','--containerd':root/'containerd.sock',
                   '--data-root':root/'data','--exec-root':root/'exec','--host':'unix://'+str(root/'docker.sock')},
    }
    processes={}
    for name in ('containerd','dockerd'):
        pid=int(pids[name]);folder=proc/str(pid)
        if pid<=1 or (folder/'cgroup').read_text().strip()!=own:
            raise ValueError('Daemon outside measured cgroup')
        expected_exe=executables[name].resolve(strict=True)
        if not (folder/'exe').samefile(expected_exe) or sha(folder/'exe')!=sha(expected_exe):
            raise ValueError('Unexpected running daemon executable')
        arguments=(folder/'cmdline').read_bytes().decode().strip('\0').split('\0')
        for option,value in expected[name].items():
            if flag(arguments,option)!=str(value):raise ValueError('Daemon has non-private address/root/state')
        processes[name]={'pid':pid,'cgroup_matches_measurement':True,'binary_sha256':sha(folder/'exe'),
                         'cgroup':own,'private_address_and_paths':True}
    if pids['containerd']==pids['dockerd']:raise ValueError('Expected two distinct private daemons')
    return {'verified':True,'processes':processes}


if __name__=='__main__':
    try:
        result=verify(Path(sys.argv[1]),{'dockerd':int(sys.argv[2]),'containerd':int(sys.argv[3])},
                      {'dockerd':Path(sys.argv[4]),'containerd':Path(sys.argv[5])})
        print(json.dumps(result,sort_keys=True))
    except (OSError,ValueError,KeyError,TypeError):
        raise SystemExit('Private daemon PID/binary/socket/cgroup isolation rejected')
