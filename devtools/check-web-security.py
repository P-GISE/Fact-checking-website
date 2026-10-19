#!/usr/bin/env python3
"""Read-only API security smoke check; loopback target, four bounded requests."""
import argparse
import ipaddress
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',default='http://127.0.0.1:3000')
    args=parser.parse_args()
    url=urlsplit(args.base_url)
    try:
        target=ipaddress.ip_address(url.hostname or '')
        valid=(target.is_loopback and url.scheme=='http' and url.username is None
               and url.password is None and url.path in ('','/')
               and not url.query and not url.fragment and 0<(url.port if url.port is not None else 80)<=65535)
    except ValueError:
        valid=False
    if not valid:
        parser.error('Use an HTTP loopback IP origin without credentials, path or query.')
    # Local checks must not traverse the external proxy or follow redirects.
    opener=build_opener(ProxyHandler({}),NoRedirect())
    required={
        'X-Content-Type-Options':'nosniff','Cache-Control':'no-store',
        'X-Frame-Options':'DENY','Cross-Origin-Resource-Policy':'same-origin',
        'Referrer-Policy':'no-referrer',
        'Content-Security-Policy':"default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
    }
    cases=[('/api/health',{},200),('/api/not-found',{},404),
           ('/api/media/not-an-id',{},400),
           ('/api/analyses',{'Origin':'https://untrusted.example'},403)]
    results=[]
    for path,headers,status in cases:
        try:
            try:
                response=opener.open(Request(args.base_url.rstrip('/')+path,headers=headers),timeout=5)
            except HTTPError as error:
                response=error
            with response:
                missing=[name for name,value in required.items() if response.headers.get(name)!=value]
                if response.headers.get('X-Powered-By') is not None:missing.append('X-Powered-By exposed')
                results.append({'path':path,'status':response.code,'expectedStatus':status,
                                'failedHeaders':missing,'passed':response.code==status and not missing})
        except (URLError,TimeoutError,OSError):
            results.append({'path':path,'passed':False,'error':'CONNECTION_FAILED'})
    passed=all(item['passed'] for item in results)
    print(json.dumps({'scope':'local_api_headers_and_origin_only','passed':passed,'checks':results},indent=2))
    return 0 if passed else 1


if __name__=='__main__':
    sys.exit(main())
