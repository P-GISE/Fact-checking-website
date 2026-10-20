from factlens.contracts import Claim
from factlens.multimodal import ModalCheck
from factlens.report import summarize


def reviewed_claim(id='c1', digest='a', group=None, verdict='CONFIRMED'):
    relation = 'REFUTED' if verdict == 'REFUTED' else 'SUPPORTED'
    evidence = dict(url='https://example.org/report', title='검토 원문', quote='가😀나', position=7,
                    relation=relation, usable=True, reasons=[], lineage='example.org',
                    meaningReview=dict(version='reviewed-meaning-v1', verified=True, policyId='fixture-policy',
                        sourceKind='paragraph', documentHash=digest * 64, definition='15세 이상 고용률',
                        quotePosition=7, quoteLength=3, relation=relation,
                        reviewReference='https://example.org/review', reviewedAt='2026-10-21'))
    if group:
        evidence['sourceReview'] = dict(version='source-review-v1', registryVersion='fixture-v1',
            identity=dict(status='unregistered', publisherId=None, registeredName=None),
            independence='unverified', groupId=group * 64, groupSize=2, relatedUrls=[], signals=['SAME_TEXT_HASH'])
    return Claim.model_validate(dict(id=id, text='2025년 한국 고용률 50%', startSeconds=0,
                                    endSeconds=1, verdict=verdict, evidence=[evidence]))


def test_legacy_summary_remains_unassessed_without_review():
    c = Claim(id='legacy', text='원문', startSeconds=0, endSeconds=1, verdict='CONFIRMED')
    result = summarize([c], [])
    assert result.version == 'claim-summary-v1'
    assert result.strength == 'not_assessed'
    assert result.model_dump().get('reviewedEvidence') is None


def test_reviewed_summary_explains_direct_coverage_without_independence_claim():
    result = summarize([reviewed_claim()], [])
    summary = result.model_dump()['reviewedEvidence']
    assert summary['version'] == 'reviewed-summary-v1'
    assert summary['claimIds'] == ['c1']
    assert summary['strength'] == 'moderate'
    assert summary['documentCount'] == summary['originGroupCount'] == 1
    assert 'INDEPENDENCE_UNVERIFIED' in summary['reasons']
    assert result.strength == 'not_assessed' and result.independenceVerified is False


def test_duplicate_documents_and_linked_origins_do_not_inflate_groups():
    claims = [reviewed_claim('c1', 'a', 'c'), reviewed_claim('c2', 'a', 'd'),
              reviewed_claim('c3', 'b', 'd')]
    summary = summarize(claims, []).model_dump()['reviewedEvidence']
    assert summary['documentCount'] == 2
    assert summary['originGroupCount'] == 1
    assert 'SHARED_OR_DUPLICATE_ORIGIN' in summary['reasons']

def test_reviewed_republication_on_two_hosts_counts_one_known_origin():
    first=reviewed_claim('c1','a')
    second=reviewed_claim('c2','b')
    first.evidence[0].lineage='reviewed-origin:kostat-labour-force-2024-unemployment'
    second.evidence[0].lineage='reviewed-origin:kostat-labour-force-2024-unemployment'
    result=summarize([first,second],[])
    assert result.reviewedEvidence.documentCount==2
    assert result.reviewedEvidence.originGroupCount==1
    assert result.independenceVerified is False


def test_unresolved_selected_claim_lowers_strength_and_remains_in_scope():
    unresolved = Claim(id='unresolved', text='확인 못한 주장', startSeconds=0, endSeconds=1)
    result = summarize([reviewed_claim(), unresolved], [])
    summary = result.model_dump()['reviewedEvidence']
    assert result.overall == 'insufficient'
    assert summary['strength'] == 'low'
    assert summary['claimIds'] == ['c1', 'unresolved']
    assert 'UNRESOLVED_CLAIMS' in summary['reasons']


def test_internal_mismatch_lowers_strength_without_relabeling_external_verdict():
    claim = reviewed_claim()
    check = ModalCheck(claimId='c1', source='subtitle', startSeconds=0, endSeconds=1,
                       observedText='음성 수치와 다른 자막', status='possible_mismatch', reasons=['VALUE_MISMATCH'])
    result = summarize([claim], [check])
    assert result.overall == 'review_required' and result.crossModalReviewRequired is True
    assert result.counts['CONFIRMED'] == 1 and claim.verdict == 'CONFIRMED'
    assert result.model_dump()['reviewedEvidence']['strength'] == 'low'
    assert 'MODAL_UNCERTAINTY' in result.model_dump()['reviewedEvidence']['reasons']


def test_conflicting_or_unreviewed_claims_cannot_get_moderate_strength():
    for verdict in ['INSUFFICIENT', 'REVIEW_REQUIRED', 'CONFIRMED']:
        claim = Claim(id='unreviewed', text='주장', startSeconds=0, endSeconds=1, verdict=verdict)
        assert summarize([reviewed_claim(), claim], []).model_dump()['reviewedEvidence']['strength'] == 'low'


def test_mixed_external_verdicts_stay_mixed_and_exclusions_are_outside_review_scope():
    excluded = Claim(id='opinion', text='의견', startSeconds=0, endSeconds=1, verdict='EXCLUDED')
    result = summarize([reviewed_claim(), reviewed_claim('c2', 'b', verdict='REFUTED'), excluded], [])
    assert result.overall == 'mixed' and result.counts['EXCLUDED'] == 1
    assert result.model_dump()['reviewedEvidence']['claimIds'] == ['c1', 'c2']
