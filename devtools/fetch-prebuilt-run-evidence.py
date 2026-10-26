#!/usr/bin/env python3
"""Read only exact Actions-attempt evidence; token stays in memory, never in argv/logs."""
import argparse
import json
import os
import sys
from urllib.request import Request,build_opener,HTTPRedirectHandler
from prebuilt_gate import validate_run,GateError


class RejectRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise GateError('API redirect rejected')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--sha',required=True)
    parser.add_argument('--run-id',type=int,required=True)
    parser.add_argument('--attempt',type=int,required=True)
    args=parser.parse_args()
    try:
        token=os.environ['GH_TOKEN']
        if args.run_id<=0 or args.attempt<=0:raise GateError('Invalid run identity')
        prefix='https://api.github.com/repos/P-GISE/Fact-checking-website/'
        def get(path):
            request=Request(prefix+path,headers={'Authorization':'Bearer '+token,
                'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'})
            # API is authenticated GitHub only. Redirects are not valid evidence.
            with build_opener(RejectRedirect()).open(request,timeout=30) as response:
                if response.url!=prefix+path:raise GateError('API redirect rejected')
                return json.load(response)
        run=get(f'actions/runs/{args.run_id}/attempts/{args.attempt}')
        jobs=[];expected=None
        for page in range(1,101):
            batch=get(f'actions/runs/{args.run_id}/attempts/{args.attempt}/jobs?per_page=100&page={page}')
            if expected is None:expected=batch['total_count']
            if batch['total_count']!=expected:raise GateError('Unstable job pagination')
            jobs.extend(batch['jobs'])
            if len(jobs)>=expected:break
            if not batch['jobs']:raise GateError('Truncated job pagination')
        if len(jobs)!=expected:raise GateError('Incomplete/duplicate job pagination')
        current=get('git/ref/heads/work')['object']['sha']
        validate_run(run,jobs,args.sha,args.run_id,args.attempt,current)
    except Exception:
        # Auth/network/JSON errors all fail closed without exposing response bodies or credentials.
        print('Actions prerequisite evidence rejected.',file=sys.stderr)
        return 1
    print('Exact Actions prerequisite jobs verified; current deployment may be in progress.')
    return 0


if __name__=='__main__':sys.exit(main())
