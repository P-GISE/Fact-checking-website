from hashlib import sha256

import pytest

from factlens.contracts import Claim, EvidenceCheck
from factlens.decision import decide
from factlens.source_document import SourceTrace
from factlens.validator import EvidenceDocument, Fact, validate_evidence
from test_source_trace import fetched


def scenario(monkeypatch, kind='paragraph', scoped=False):
    quote = '2024년 한국 실업률은 2.8%입니다.'
    body = ('<p>공식 통계</p><p>' + quote + '</p>') if kind == 'paragraph' else (
        '<table><caption>2024년 한국 실업률 (%)</caption>'
        '<tr><th>기간</th><th>실업률 (%)</th></tr>'
        '<tr><th>2024년 한국</th><td>2.8</td></tr></table>')
    raw = fetched('<meta name="publisher" content="통계 기관">'
                  '<meta property="article:published_time" content="2025-03-25">' + body)
    text = raw['text']
    trace = SourceTrace.model_validate(raw['sourceTrace'])
    if kind == 'table':
        quote = '2.8'
    policy = dict(policyId='synthetic-reviewed', url=raw['url'],
                  documentHash=trace.textSha256, sourceKind=kind, quote=quote,
                  quotePosition=text.index(quote), publisher='통계 기관',
                  publishedAt='2025-03-25', subject='한국', period='2024년',
                  metric='실업률', value='2.8', unit='%',
                  definition='경제활동인구 중 실업자 비율, 연간, 소수 첫째 자리',
                  precision=1, reviewReference=raw['url'], reviewedAt='2026-10-21')
    if kind == 'table':
        policy['table'] = dict(tableIndex=0, rowHeaderBlockIndex=3,
                               columnHeaderBlockIndex=2, valueBlockIndex=4)
    if scoped:
        policy.update(documentHash=None, quotePosition=0, context=dict(
            kind='paragraph', sha256=sha256(quote.encode()).hexdigest(), title='공식 통계'))
    c = Claim(id='c', text='2024년 한국 실업률은 2.8%입니다.',
              contextText='2024년 한국 실업률은 2.8%입니다.', startSeconds=0,
              endSeconds=1, subject='한국', period='2024년', metric='실업률', value='2.8', unit='%')
    d = EvidenceDocument(raw['url'], '통계', text, quote, text.index(quote),
                         '통계 기관', '2025-03-25', Fact('한국', '2024년', '실업률', '2.8', '%'),
                         sourceTrace=trace)
    from factlens import meaning_review as mr
    monkeypatch.setattr(mr, 'DEFAULT_POLICIES', [mr.ReviewedPolicy(**policy)])
    return c, d, policy


@pytest.mark.parametrize('kind', ['paragraph', 'table'])
@pytest.mark.parametrize('value,relation,verdict', [('2.8', 'SUPPORTED', 'CONFIRMED'), ('2.9', 'REFUTED', 'REFUTED')])
def test_reviewed_support_and_exact_precision_refutation(monkeypatch, kind, value, relation, verdict):
    c, d, _ = scenario(monkeypatch, kind)
    c.value = value
    c.text = c.contextText = f'2024년 한국 실업률은 {value}%입니다.'
    check = validate_evidence(c, d)
    assert check.usable, check.reasons
    assert check.relation == relation
    assert decide(c, [check]) == verdict
    assert check.meaningReview.documentHash == d.sourceTrace.textSha256
    assert check.meaningReview.quotePosition == d.position
    assert check.meaningReview.quoteLength == len(d.quote)
    assert set(check.meaningReview.model_dump()) == {
        'version', 'verified', 'policyId', 'sourceKind', 'documentHash', 'definition',
        'quotePosition', 'quoteLength', 'relation', 'reviewReference', 'reviewedAt'}


@pytest.mark.parametrize('text', [
    '2024년 한국 실업률 2.8%', '2024년 한국의 실업률은 2.8퍼센트입니다.',
    '2024년 한국 실업률은 2.8퍼센트', '2024년 한국의 실업률 2.8%.',
    '2024년 한국의 실업률은 2.8 퍼센트입니다.'])
def test_whole_sentence_variants(monkeypatch, text):
    c, d, _ = scenario(monkeypatch)
    c.text = c.contextText = text
    assert decide(c, [validate_evidence(c, d)]) == 'CONFIRMED'

def test_invalid_trace_has_bounded_diagnostic_and_cannot_confirm(monkeypatch, caplog):
    import logging
    c,d,_=scenario(monkeypatch)
    d.sourceTrace.blocks[0].position=-1
    with caplog.at_level(logging.INFO,logger='factlens.meaning_review'):
        check=validate_evidence(c,d)
    assert not check.usable and 'SOURCE_TRACE_MISMATCH' in check.reasons
    assert caplog.messages==['REVIEWED_SOURCE_TRACE_REJECTED']
    assert d.quote not in caplog.text and d.url not in caplog.text


@pytest.mark.parametrize('text', [
    '2024년 한국 실업률은 2.8%가 아닙니다.', '만약 2024년 한국 실업률은 2.8%입니다.',
    '2024년 한국 실업률은 약 2.8%입니다.', '2024년 한국 실업률은 2.8%입니다. 정정합니다.',
    '2024년 한국 실업률은 2.8%입니다.\n2025년에는 3.0%입니다.',
    '2024년 한국 실업률은 2.8% 이상입니다.', '2024년 한국 실업률은 전체 인구의 2.8%입니다.',
    '2024년 한국 실업률은 2.80%입니다.', '2025년 한국 실업률은 2.8%입니다.', None])
def test_rejects_unsafe_or_inconsistent_entire_context(monkeypatch, text):
    c, d, _ = scenario(monkeypatch)
    c.contextText = text
    check = validate_evidence(c, d)
    assert not check.usable
    assert getattr(check, 'meaningReview', None) is None
    assert decide(c, [check]) not in ('CONFIRMED', 'REFUTED')


@pytest.mark.parametrize('mutation', [
    'text', 'url', 'requestedUrl', 'finalUrl', 'hash', 'length', 'truncated',
    'incomplete', 'bounds', 'quote', 'position', 'publisher', 'date', 'fact',
    'precision', 'duplicate', 'missingTrace'])
def test_rejects_changed_document_or_trace(monkeypatch, mutation):
    c, d, _ = scenario(monkeypatch)
    if mutation == 'text': d.text += ' 정정'
    elif mutation == 'url': d.url = 'https://example.org/other'
    elif mutation in ('requestedUrl', 'finalUrl'): setattr(d.sourceTrace, mutation, 'https://evil.example/report')
    elif mutation == 'hash': d.sourceTrace.textSha256 = '0' * 64
    elif mutation == 'length': d.sourceTrace.textLength += 1
    elif mutation == 'truncated': d.sourceTrace.extractionTruncated = True
    elif mutation == 'incomplete': d.sourceTrace.structureComplete = False
    elif mutation == 'bounds': d.sourceTrace.blocks[-1].length += 9999
    elif mutation == 'quote': d.quote = '2.8%'
    elif mutation == 'position': d.position += 1
    elif mutation == 'publisher': d.publisher = '다른 기관'
    elif mutation == 'date': d.publishedAt = '2025-03-26'
    elif mutation == 'fact': d.fact.period = '2025년'
    elif mutation == 'precision':
        c.value = '2.80'
        c.text = c.contextText = '2024년 한국 실업률은 2.80%입니다.'
    elif mutation == 'duplicate':
        d.text += '\n' + d.quote
        d.sourceTrace.textLength = len(d.text)
        d.sourceTrace.textSha256 = sha256(d.text.encode()).hexdigest()
    elif mutation == 'missingTrace': d.sourceTrace = None
    check = validate_evidence(c, d)
    assert not check.usable
    assert getattr(check, 'meaningReview', None) is None


def test_scoped_article_ignores_changing_navigation_but_checks_full_trace(monkeypatch):
    c, d, _ = scenario(monkeypatch, scoped=True)
    d.text = '조회수 123\n' + d.text
    for block in d.sourceTrace.blocks: block.position += 8
    d.position += 8
    d.sourceTrace.textLength = len(d.text)
    d.sourceTrace.textSha256 = sha256(d.text.encode()).hexdigest()
    assert validate_evidence(c, d).usable
    d.sourceTrace.textSha256 = '0' * 64
    assert not validate_evidence(c, d).usable


@pytest.mark.parametrize('mutation', ['merged', 'noHeader', 'crossTable', 'unresolved', 'incompleteAudit'])
def test_simple_table_refuses_ambiguous_structure(monkeypatch, mutation):
    c, d, _ = scenario(monkeypatch, 'table')
    if mutation == 'merged': d.sourceTrace.blocks[3].tableLocation.rowSpan = 2
    elif mutation == 'noHeader': d.sourceTrace.blocks[2].kind = 'table_cell'
    elif mutation == 'crossTable': d.sourceTrace.blocks[2].tableLocation.tableIndex = 1
    elif mutation == 'incompleteAudit': d.sourceTrace.tableReferenceAudit.complete = False
    else:
        from factlens.table_references import HeaderReference
        d.sourceTrace.tableReferenceAudit.references.append(HeaderReference(
            cellBlockIndex=4, declaredId='missing', status='missing_id'))
    assert not validate_evidence(c, d).usable


def test_forged_serialized_or_mutated_meaning_review_cannot_bypass_decision(monkeypatch):
    c, d, _ = scenario(monkeypatch)
    check = validate_evidence(c, d)
    assert check.usable
    forged = EvidenceCheck.model_validate(check.model_dump())
    assert decide(c, [forged]) == 'REVIEW_REQUIRED'
    changed = check.model_copy(deep=True)
    changed.relation = 'REFUTED'
    assert decide(c, [changed]) != 'REFUTED'
    c.text = c.contextText = '2024년 한국 실업률은 2.8%가 아닙니다.'
    assert decide(c, [check]) == 'REVIEW_REQUIRED'


def test_no_policy_preserves_v4_abstention(monkeypatch):
    c, d, _ = scenario(monkeypatch)
    from factlens import meaning_review as mr
    monkeypatch.setattr(mr, 'DEFAULT_POLICIES', [])
    check = validate_evidence(c, d)
    assert not check.usable and check.meaningReview is None
    assert 'SOURCE_AUTHENTICITY_UNVERIFIED' in check.reasons


def test_decision_survives_source_review_decoration(monkeypatch):
    from factlens.source_review import review_sources
    c, d, _ = scenario(monkeypatch)
    check = validate_evidence(c, d)
    check.sourceReview = review_sources([check])[0]
    c.evidence = [check]
    assert decide(c, c.evidence) == 'CONFIRMED'


@pytest.mark.parametrize('mutation', ['none', 'dateMissing', 'wrongDate', 'conflict', 'wrongTitle', 'bodyChange', 'duplicateBody', 'quoteOutside'])
def test_explicit_scoped_publication_review(monkeypatch, mutation):
    from factlens import meaning_review as mr
    from factlens.source_document import Publication, TextBlock
    c, d, policy = scenario(monkeypatch, scoped=True)
    policy['publicationDateText'] = '게시일 2025-03-25'
    d.text += '\n게시일 2025-03-25'
    d.sourceTrace.publication = Publication()
    d.publisher = d.publishedAt = None
    if mutation == 'dateMissing': d.text = d.text.replace('게시일', '다른값')
    elif mutation == 'wrongDate': d.text = d.text.replace('2025-03-25', '2025-03-26')
    elif mutation == 'conflict': d.sourceTrace.publication.publisher.state = 'conflicting'
    elif mutation == 'wrongTitle': d.text = d.text.replace('공식 통계', '다른 통계')
    elif mutation == 'bodyChange': d.text = d.text.replace('2.8%', '2.9%')
    elif mutation == 'duplicateBody':
        position = len(d.text) + 1
        d.text += '\n' + d.quote
        d.sourceTrace.blocks.append(TextBlock(kind='paragraph', position=position, length=len(d.quote)))
    elif mutation == 'quoteOutside':
        policy['quotePosition'] = len(d.quote)
    d.sourceTrace.textLength = len(d.text)
    d.sourceTrace.textSha256 = sha256(d.text.encode()).hexdigest()
    monkeypatch.setattr(mr, 'DEFAULT_POLICIES', [mr.ReviewedPolicy(**policy)])
    check = validate_evidence(c, d)
    assert check.usable == (mutation == 'none')
    if mutation == 'none':
        assert (check.publisher, check.publishedAt) == ('통계 기관', '2025-03-25')
        assert check.sourceTrace.publication.publisher.state == 'missing'
        assert decide(c, [check]) == 'CONFIRMED'


@pytest.mark.parametrize('field,value', [
    ('url', 'http://example.org/report'), ('url', 'https://user@example.org/report'),
    ('url', 'https://127.0.0.1/report'), ('url', 'https://example.org/report#fragment'),
    ('precision', True), ('precision', 2), ('definition', ''), ('reviewedAt', '2026-02-30'),
    ('documentHash', '0' * 63), ('extra', 'unexpected'), ('sourceKind', 'unknown'),
    ('publicationDateText', '게시일 2025-03-26')])
def test_policy_loader_rejects_invalid_or_extra_fields(monkeypatch, tmp_path, field, value):
    import json
    from factlens.meaning_review import load_policies
    _, _, policy = scenario(monkeypatch)
    policy[field] = value
    path = tmp_path / 'policies.json'
    path.write_text(json.dumps([policy]), encoding='utf-8')
    with pytest.raises(ValueError):
        load_policies(path)


def test_policy_loader_strict_list_and_unique_ids(monkeypatch, tmp_path):
    import json
    from factlens.meaning_review import load_policies
    _, _, policy = scenario(monkeypatch)
    path = tmp_path / 'policies.json'
    for data in ({'policies': [policy]}, [policy, policy]):
        path.write_text(json.dumps(data), encoding='utf-8')
        with pytest.raises(ValueError):
            load_policies(path)
    path.write_text('[]', encoding='utf-8')
    assert load_policies(path) == []


def test_reviewed_fact_value_must_be_anchored_in_full_quote(monkeypatch):
    from factlens import meaning_review as mr
    c, d, policy = scenario(monkeypatch)
    policy['value'] = d.fact.value = '3.8'
    monkeypatch.setattr(mr, 'DEFAULT_POLICIES', [mr.ReviewedPolicy(**policy)])
    check = validate_evidence(c, d)
    assert not check.usable
    assert check.meaningReview is None


@pytest.mark.parametrize('field,value', [('subject', '대한민국'), ('period', '2023년'),
                                        ('metric', '고용률'), ('unit', '퍼센트포인트')])
def test_scalar_scope_mismatch_never_refutes(monkeypatch, field, value):
    c, d, _ = scenario(monkeypatch)
    setattr(c, field, value)
    c.text = c.contextText = f'{c.period} {c.subject} {c.metric} {c.value}{c.unit}'
    check = validate_evidence(c, d)
    assert not check.usable and check.meaningReview is None
    assert decide(c, [check]) not in ('CONFIRMED', 'REFUTED')


@pytest.mark.parametrize('field,value', [('verified', False), ('verified', 1),
                                        ('quotePosition', -1), ('quoteLength', 0),
                                        ('documentHash', 'f' * 63), ('relation', 'INSUFFICIENT'),
                                        ('reviewReference', 'http://example.org/'),
                                        ('reviewedAt', '2026-02-30'), ('extra', 'ignored?')])
def test_meaning_wire_contract_rejects_invalid_values(monkeypatch, field, value):
    from factlens.meaning_review import MeaningReview
    c, d, _ = scenario(monkeypatch)
    data = validate_evidence(c, d).meaningReview.model_dump()
    data[field] = value
    with pytest.raises(ValueError):
        MeaningReview.model_validate(data)


def sparse_live_table(monkeypatch):
    from factlens import meaning_review as mr
    c, _, policy = scenario(monkeypatch)
    raw = fetched('<table><caption>한국 실업률</caption>'
                  '<tr><td></td><th>2023</th><th>2024</th></tr>'
                  '<tr><td></td></tr>'
                  '<tr><th>실업률(%)</th><td>2.8</td><td>2.8</td></tr></table>')
    trace = SourceTrace.model_validate(raw['sourceTrace'])
    position = raw['text'].rindex('2.8')
    policy.update(documentHash=trace.textSha256, sourceKind='table', quote='2.8',
                  quotePosition=position, publishedAt=None, publicationMode='live_dataset',
                  table=dict(tableIndex=0, rowHeaderBlockIndex=3,
                             columnHeaderBlockIndex=2, valueBlockIndex=5,
                             rowHeaderText='실업률(%)', columnHeaderText='2024'))
    monkeypatch.setattr(mr, 'DEFAULT_POLICIES', [mr.ReviewedPolicy(**policy)])
    d = EvidenceDocument(raw['url'], '통계', raw['text'], '2.8', position, None, None,
                         Fact('한국', '2024년', '실업률', '2.8', '%'), sourceTrace=trace)
    return c, d, policy


@pytest.mark.parametrize('value,verdict', [('2.8', 'CONFIRMED'), ('2.9', 'REFUTED')])
def test_sparse_live_table_repeated_value_is_anchored_to_exact_cell(monkeypatch, value, verdict):
    c, d, _ = sparse_live_table(monkeypatch)
    c.value = value
    c.text = c.contextText = f'2024년 한국 실업률은 {value}%입니다.'
    check = validate_evidence(c, d)
    assert check.usable
    assert check.publishedAt is None
    assert check.publisher == '통계 기관'
    assert check.sourceTrace.quoteOccurrences == 2
    assert check.sourceTrace.quoteBlockIndexes == [5]
    assert check.sourceTrace.tableContext is None
    assert check.meaningReview.quotePosition == d.position
    assert decide(c, [check]) == verdict
    assert EvidenceCheck.model_validate(check.model_dump()).sourceTrace.quoteBlockIndexes == [5]


@pytest.mark.parametrize('mutation', ['wrongCell', 'rowHeader', 'columnHeader',
                                     'rowGeometry', 'columnGeometry', 'duplicateCoordinates',
                                     'span', 'publicationConflict', 'inventedDate', 'changedHash'])
def test_sparse_live_table_refuses_anchor_or_metadata_mismatch(monkeypatch, mutation):
    c, d, _ = sparse_live_table(monkeypatch)
    if mutation == 'wrongCell': d.position = d.text.index('2.8')
    elif mutation == 'rowHeader': d.sourceTrace.blocks[3].kind = 'table_cell'
    elif mutation == 'columnHeader': d.sourceTrace.blocks[2].kind = 'table_cell'
    elif mutation == 'rowGeometry': d.sourceTrace.blocks[3].tableLocation.rowIndex = 1
    elif mutation == 'columnGeometry': d.sourceTrace.blocks[2].tableLocation.cellIndex = 1
    elif mutation == 'duplicateCoordinates': d.sourceTrace.blocks[4].tableLocation.cellIndex = 2
    elif mutation == 'span': d.sourceTrace.blocks[3].tableLocation.columnSpan = 2
    elif mutation == 'publicationConflict': d.sourceTrace.publication.publisher.state = 'conflicting'
    elif mutation == 'inventedDate': d.publishedAt = '2026-10-21'
    elif mutation == 'changedHash': d.sourceTrace.textSha256 = '0' * 64
    check = validate_evidence(c, d)
    assert not check.usable and check.meaningReview is None


@pytest.mark.parametrize('mutation', ['paragraph', 'dated', 'missingMode', 'oneHeader'])
def test_live_dataset_policy_cannot_weaken_paragraph_publication(monkeypatch, mutation):
    from factlens.meaning_review import ReviewedPolicy
    _, _, policy = sparse_live_table(monkeypatch)
    if mutation == 'paragraph':
        policy.update(sourceKind='paragraph', table=None)
    elif mutation == 'dated': policy['publishedAt'] = '2026-10-21'
    elif mutation == 'missingMode': del policy['publicationMode']
    elif mutation == 'oneHeader': del policy['table']['columnHeaderText']
    with pytest.raises(ValueError):
        ReviewedPolicy(**policy)


def test_policy_loader_preserves_explicit_reviewed_origin(monkeypatch, tmp_path):
    import json
    from factlens.meaning_review import load_policies
    _, _, policy = scenario(monkeypatch)
    policy['originId'] = 'kostat-labour-force-2024-unemployment'
    path = tmp_path / 'policies.json'
    path.write_text(json.dumps([policy]), encoding='utf-8')
    assert load_policies(path)[0].originId == 'kostat-labour-force-2024-unemployment'
    for origin in ('a' * 121, '', 'shared origin', 'https://example.org', '-leading'):
        policy['originId'] = origin
        path.write_text(json.dumps([policy]), encoding='utf-8')
        with pytest.raises(ValueError):
            load_policies(path)
