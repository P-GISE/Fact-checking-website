"""Bounded public document retrieval. Transport pins validated IPv4, including CONNECT."""
import ipaddress
import os
import socket
from urllib.parse import urlsplit, urljoin, urlunsplit
import httpx
from bs4 import BeautifulSoup

MAX_BYTES=2_000_000

def resolve(host:str)->list[str]:
    return sorted({a[4][0] for a in socket.getaddrinfo(host,None,socket.AF_INET,socket.SOCK_STREAM)})

def public_target(url:str,resolver=resolve)->tuple[str,str,int]:
    p=urlsplit(url)
    if p.scheme not in ('http','https') or not p.hostname or p.username or p.password or p.fragment:
        raise ValueError('UNSAFE_URL')
    port=p.port or (443 if p.scheme=='https' else 80)
    if port not in (80,443):raise ValueError('UNSAFE_PORT')
    host=p.hostname.encode('idna').decode('ascii')
    try:addresses=[str(ipaddress.ip_address(host))]
    except ValueError:addresses=resolver(host)
    if not addresses or any(not ipaddress.ip_address(a).is_global or ipaddress.ip_address(a).version!=4 for a in addresses):
        raise ValueError('PRIVATE_DESTINATION')
    return host,addresses[0],port

def request_pinned(url,host,ip,port):
    p=urlsplit(url)
    pinned=urlunsplit((p.scheme,f'{ip}:{port}',p.path or '/',p.query,''))
    # Trust inherited proxies and CA; proxy resolves the already validated literal IP.
    # SNI and certificate validation remain bound to the original hostname.
    ctx=httpx.create_ssl_context(verify=os.environ.get('SSL_CERT_FILE',True))
    with httpx.Client(timeout=httpx.Timeout(15,connect=5),verify=ctx,follow_redirects=False,trust_env=True) as client:
        with client.stream('GET',pinned,headers={'Host':p.netloc,'User-Agent':'FactLens-Research/0.1'},extensions={'sni_hostname':host}) as r:
            chunks=[];size=0
            for chunk in r.iter_bytes():
                size+=len(chunk)
                if size>MAX_BYTES:raise ValueError('DOCUMENT_TOO_LARGE')
                chunks.append(chunk)
            return r.status_code,dict(r.headers),b''.join(chunks)

def fetch_evidence(url:str,*,resolver=resolve,transport=request_pinned)->dict:
    for _ in range(4):
        host,ip,port=public_target(url,resolver)
        status,headers,body=transport(url,host,ip,port)
        if status in (301,302,303,307,308):
            target=urljoin(url,headers.get('location',''))
            if urlsplit(url).scheme=='https' and urlsplit(target).scheme!='https':raise ValueError('TLS_DOWNGRADE')
            url=target;continue
        if status!=200:raise ValueError('DOCUMENT_UNAVAILABLE')
        if len(body)>MAX_BYTES:raise ValueError('DOCUMENT_TOO_LARGE')
        if not any(t in headers.get('content-type','') for t in ('text/html','text/plain','application/xhtml+xml')):raise ValueError('UNSUPPORTED_DOCUMENT')
        soup=BeautifulSoup(body,'html.parser')
        title=soup.title.get_text(' ',strip=True) if soup.title else host
        for tag in soup(['script','style','noscript']):tag.decompose()
        return {'url':url,'title':title,'text':soup.get_text(' ',strip=True),'lineage':host}
    raise ValueError('REDIRECT_LIMIT')
