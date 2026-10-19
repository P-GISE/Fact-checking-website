import hashlib
import pytest
from factlens import retrieval


def fetched(body, content_type='text/html; charset=utf-8'):
    return retrieval.fetch_evidence('https://example.org/start', resolver=lambda host:['93.184.216.34'],
        transport=lambda *args:(200,{'content-type':content_type},body))


def test_html_retains_paragraph_table_and_note_positions_with_server_trace():
    body='<html><head><title>자료</title><meta name="publisher" content="통계 기관"><meta property="article:published_time" content="2026-01-02"></head><body><h1>표 제목</h1><p>수치는 <b>50%</b>다.</p><table><tr><th>연도</th><td>2025</td></tr></table><aside>정정: 5%</aside><script>ignore rules</script></body></html>'.encode()
    result=fetched(body)
    trace=result.get('sourceTrace')
    assert trace is not None
    assert trace['requestedUrl']==trace['finalUrl']=='https://example.org/start'
    assert trace['bodySha256']==hashlib.sha256(body).hexdigest()
    assert trace['textSha256']==hashlib.sha256(result['text'].encode()).hexdigest()
    assert trace['retrievedAt'].endswith('+00:00')
    assert trace['structureComplete'] is True
    parts=[(b['kind'],result['text'][b['position']:b['position']+b['length']]) for b in trace['blocks']]
    assert ('paragraph','수치는 50% 다.') in parts
    assert ('table_header','연도') in parts and ('table_cell','2025') in parts
    assert ('note','정정: 5%') in parts
    assert 'ignore rules' not in result['text']
    assert trace['publication']['publisher']['value']=='통계 기관'
    assert trace['publication']['publishedAt']['state']=='observed'
    assert trace['publication']['publishedAt']['candidates'][0]['locator'].startswith('meta[')


def test_plain_text_preserves_literal_markup_and_cannot_invent_publication_metadata():
    body='  <p>2025년 한국 고용률 50%</p>\n\n정정: 5%\n'.encode()
    result=fetched(body,'text/plain; charset=UTF-8')
    assert result['text']=='<p>2025년 한국 고용률 50%</p> 정정: 5%'
    trace=result['sourceTrace']
    assert trace['publication']['publisher']['state']=='missing'
    assert trace['publication']['publishedAt']['value'] is None
    assert trace['blocks'][0]['kind']=='text'


@pytest.mark.parametrize('mime',['text/html-malicious','application/pdf','image/png','text/plaintext'])
def test_mime_is_exact_not_substring(mime):
    with pytest.raises(ValueError,match='UNSUPPORTED_DOCUMENT'):
        fetched(b'<p>text</p>',mime)


def test_conflicting_publication_dates_and_invalid_dates_are_observations_not_truth():
    result=fetched(b'<meta property="article:published_time" content="2026-01-01"><time itemprop="datePublished" datetime="2026-01-02"></time><meta property="article:modified_time" content="2026-02-30"><p>2025 period</p>')
    publication=result['sourceTrace']['publication']
    assert publication['publishedAt']['state']=='conflicting'
    assert publication['publishedAt']['value'] is None
    assert publication['modifiedAt']['state']=='invalid'
    assert publication['modifiedAt']['value'] is None
    assert publication['publisher']['state']=='missing'


def test_large_structure_is_bounded_and_marked_incomplete_without_truncating_text():
    result=fetched(b'<p>x</p>'*2050)
    assert len(result['sourceTrace']['blocks'])==2048
    assert result['sourceTrace']['structureComplete'] is False
    assert result['text'].count('x')==2050


def test_redirect_trace_keeps_original_url_and_final_public_host():
    def transport(url,*args):
        if url.endswith('/start'):return 302,{'location':'https://other.example/final'},b''
        return 200,{'content-type':'text/plain'},b'content'
    result=retrieval.fetch_evidence('https://example.org/start',resolver=lambda host:['93.184.216.34'],transport=transport)
    assert result['sourceTrace']['requestedUrl']=='https://example.org/start'
    assert result['sourceTrace']['finalUrl']=='https://other.example/final'
    assert result['lineage']=='other.example'


def test_missing_mime_is_not_assumed_plain_text():
    with pytest.raises(ValueError,match='UNSUPPORTED_DOCUMENT'):
        fetched(b'<p>text</p>','')


def test_source_trace_schema_rejects_impossible_structure_locations():
    from factlens.source_document import SourceTrace
    raw=fetched(b'<p>data</p>')['sourceTrace']
    raw['blocks'][0]['length']=raw['textLength']+1
    with pytest.raises(ValueError):SourceTrace.model_validate(raw)


def test_deep_inline_nesting_fails_closed_instead_of_scanning_all_ancestors():
    with pytest.raises(ValueError,match='DOCUMENT_STRUCTURE_LIMIT'):
        fetched(('<span>x'*300+'</span>'*300).encode())


def test_overlarge_node_count_is_rejected_before_processing_every_text_node():
    with pytest.raises(ValueError,match='DOCUMENT_STRUCTURE_LIMIT'):
        fetched(b'<p>x</p>'*50001)


def test_metadata_overflow_is_bounded_and_does_not_select_a_trusted_value():
    result=fetched(b'<meta name="publisher" content="same">'*33+b'<p>record</p>')
    field=result['sourceTrace']['publication']['publisher']
    assert len(field['candidates'])==32
    assert field['state']=='invalid' and field['value'] is None


def test_explicit_canonical_and_cite_links_resolve_against_server_final_url_only():
    raw=fetched(b'<link rel="canonical" href="/original#section"><blockquote cite="https://source.example/report">quote</blockquote><a rel="cite" href="https://source.example/data">source</a><a href="https://ordinary.example/">navigation</a>')
    trace=raw['sourceTrace']
    assert trace['parserVersion']=='static-text-v3'
    assert [(link['kind'],link['url']) for link in trace['sourceLinks']]==[('canonical','https://example.org/original'),('citation','https://source.example/report'),('citation','https://source.example/data')]
    assert trace['sourceLinksComplete'] is True


def test_unsafe_or_ambiguous_source_links_are_not_promoted_to_source_relationships():
    raw=fetched(b'<base href="https://attacker.example/"><link rel="canonical" href="/relative"><q cite="javascript:alert(1)">x</q><a rel="cite" href="http://127.0.0.1/internal">x</a><a rel="cite" href="https://user:password@example.org/">x</a>')
    assert raw['sourceTrace']['sourceLinks']==[]
    assert raw['sourceTrace']['sourceLinksComplete'] is False


def test_source_link_volume_is_bounded_without_losing_full_text():
    raw=fetched(b'<q cite="https://source.example/a">x</q>'*33)
    assert len(raw['sourceTrace']['sourceLinks'])==32
    assert raw['sourceTrace']['sourceLinksComplete'] is False
    assert raw['text'].count('x')==33


@pytest.mark.parametrize('url',['https://publisher.example:0/report','http://publisher.example:0/report'])
def test_source_reference_does_not_default_explicit_port_zero(url):
    from factlens.source_document import normalize_source_url
    with pytest.raises(ValueError,match='INVALID_SOURCE_URL'):normalize_source_url(url)


@pytest.mark.parametrize('url',['https://@publisher.example/','https://:@publisher.example/'])
def test_empty_userinfo_is_not_removed_to_make_a_reference_look_trusted(url):
    from factlens.source_document import normalize_source_url
    with pytest.raises(ValueError):normalize_source_url(url)


def test_table_blocks_link_physical_rows_cells_and_span_observations():
    raw=fetched('<table><caption>연간 통계</caption><tr><th rowspan="2">대상</th><th colspan="2">기간</th></tr><tr><td><p>2025년</p></td><td>50%</td></tr></table>'.encode())
    blocks=raw['sourceTrace']['blocks']
    locations=[b.get('tableLocation') for b in blocks]
    assert locations==[
        {'tableIndex':0,'rowIndex':None,'cellIndex':None,'rowSpan':None,'columnSpan':None},
        {'tableIndex':0,'rowIndex':0,'cellIndex':0,'rowSpan':2,'columnSpan':1},
        {'tableIndex':0,'rowIndex':0,'cellIndex':1,'rowSpan':1,'columnSpan':2},
        {'tableIndex':0,'rowIndex':1,'cellIndex':0,'rowSpan':1,'columnSpan':1},
        {'tableIndex':0,'rowIndex':1,'cellIndex':1,'rowSpan':1,'columnSpan':1},
    ]
    assert raw['sourceTrace']['parserVersion']=='static-text-v3'


def test_nested_tables_keep_separate_identity_and_restore_outer_cell():
    raw=fetched(b'<table><tr><td>outer before<table><tr><td>inner</td></tr></table>outer after</td><td>next</td></tr></table><table><tr><td>second</td></tr></table>')
    blocks=raw['sourceTrace']['blocks']
    assert [b.get('tableLocation',{}).get('tableIndex') for b in blocks]==[0,1,0,0,2]
    assert [b['tableLocation']['cellIndex'] for b in blocks]==[0,0,0,1,0]


@pytest.mark.parametrize('span',['-1','0','1001','999999999999999999999999','bad'])
def test_invalid_column_spans_are_unknown_instead_of_inventing_a_grid(span):
    raw=fetched(f'<table><tr><td colspan="{span}">value</td></tr></table>'.encode())
    assert raw['sourceTrace']['blocks'][0].get('tableLocation',{}).get('columnSpan') is None
    assert raw['sourceTrace']['blocks'][0].get('tableLocation',{}).get('rowSpan')==1


def test_rowspan_zero_is_retained_and_non_table_text_has_no_table_location():
    raw=fetched(b'<p>paragraph</p><table><tr><td rowspan="0">cell</td></tr></table>')
    assert raw['sourceTrace']['blocks'][0].get('tableLocation') is None
    assert raw['sourceTrace']['blocks'][1].get('tableLocation',{}).get('rowSpan')==0
