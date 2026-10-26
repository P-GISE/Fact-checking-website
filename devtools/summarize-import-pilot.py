#!/usr/bin/env python3
"""Minimal non-secret metrics; successful pilot never approves a production policy."""
import json
from pathlib import Path
import sys


def summarize(measurement,measurement_status,sca_status):
    valid=(measurement_status==0 and measurement.get('status')=='measurement-requires-review'
           and measurement.get('method')=='isolated-daemon-stream-load-v1'
           and measurement.get('platform')=='linux/amd64' and measurement.get('oom_events')==0
           and measurement.get('isolation_verified') is True and measurement.get('isolation_version')==2
           and measurement.get('isolation_before',{}).get('verified') is True
           and measurement.get('isolation_after',{}).get('verified') is True
           and type(measurement.get('peak_total_bytes')) is int and measurement['peak_total_bytes']>0)
    equivalent=(measurement.get('docker_server_version')=='29.1.3'
                and measurement.get('docker_driver')=='overlayfs'
                and ['driver-type','io.containerd.snapshotter.v1'] in measurement.get('docker_driver_status',[]))
    keys=('method','platform','peak_total_bytes','oom_events','docker_server_version','docker_driver',
          'docker_driver_status','docker_server_components','kernel_release','kernel_architecture','image_archive_sha256','measurement_run_url',
          'isolation_verified','isolation_version','isolation_before','isolation_after','measurement_scope')
    result={'measurement_status':'SUCCESS' if valid else 'FAILED_OR_UNASSESSED',
            'image_sca_status':'SUCCESS' if sca_status==0 else 'FAILED_OR_UNASSESSED',
            'docker_engine_driver_match':equivalent,'runtime_equivalent_to_s2':False,
            'runtime_equivalence_status':'UNPROVEN: CI kernel/distribution/components differ from S2',
            'production_envelope_approved':False,
            'uploaded_artifacts':0,'published_packages':0,'production_calls':0,
            'measurement':{key:measurement[key] for key in keys if key in measurement}}
    if not valid:result['measurement'].pop('peak_total_bytes',None)
    return result,0 if valid and equivalent and sca_status==0 else 1


if __name__=='__main__':
    try:measurement=json.loads(Path(sys.argv[1]).read_text())
    except (OSError,ValueError):measurement={}
    result,status=summarize(measurement,int(sys.argv[2]),int(sys.argv[3]))
    print('FACTLENS_IMPORT_PILOT_RESULT='+json.dumps(result,sort_keys=True))
    sys.exit(status)
