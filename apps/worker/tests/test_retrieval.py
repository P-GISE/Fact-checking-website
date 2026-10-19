import pytest
from factlens.retrieval import public_target, fetch_evidence

@pytest.mark.parametrize('url',['http://127.0.0.1/a','http://169.254.169.254/latest','http://100.108.2.6/','http://[::1]/','file:///etc/passwd','https://user:pass@example.com/','http://localhost/','http://10.0.0.1/'])
def test_rejects_private_and_unsupported(url):
    with pytest.raises(ValueError):public_target(url)

def test_pins_public_ip_and_preserves_host():
    assert public_target('https://example.org/a',resolver=lambda h:['93.184.216.34'])==('example.org','93.184.216.34',443)

def test_rebinding_mixed_answers_rejected():
    with pytest.raises(ValueError):public_target('https://example.org/',resolver=lambda h:['93.184.216.34','127.0.0.1'])

def test_redirect_rechecks_target():
    def transport(url,host,ip,port):return (302,{'location':'http://127.0.0.1/secret'},b'')
    with pytest.raises(ValueError):fetch_evidence('https://example.org',resolver=lambda h:['93.184.216.34'],transport=transport)

def test_size_and_nontext_rejected():
    for headers,body in [({'content-type':'image/png'},b'PNG'),({'content-type':'text/plain'},b'x'*2000001)]:
        with pytest.raises(ValueError):fetch_evidence('https://example.org',resolver=lambda h:['93.184.216.34'],transport=lambda *a:(200,headers,body))


@pytest.mark.parametrize('url',['https://example.org:0/','http://example.org:0/'])
def test_explicit_port_zero_is_rejected_before_any_request(url):
    with pytest.raises(ValueError,match='UNSAFE_PORT'):
        public_target(url,resolver=lambda h:['93.184.216.34'])


@pytest.mark.parametrize('url',['https://@example.org/','https://:@example.org/'])
def test_even_empty_userinfo_is_not_an_unauthenticated_source_url(url):
    with pytest.raises(ValueError):public_target(url,resolver=lambda h:['93.184.216.34'])
