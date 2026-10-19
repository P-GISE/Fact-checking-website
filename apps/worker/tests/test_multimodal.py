from test_validator import claim
from factlens.visual import VisualAnalysis,VisualText


def visual(text,source='subtitle'):
    return VisualAnalysis(status='complete',durationSeconds=3,records=[VisualText(source=source,startSeconds=0,endSeconds=2,text=text)])


def test_modal_numeric_mismatch_is_independent_of_external_truth():
    from factlens.multimodal import review_modalities
    c=claim();checks=review_modalities([c],visual('2025년 한국 고용률 5%'))
    assert checks[0].status=='possible_mismatch'
    assert c.verdict=='INSUFFICIENT'
    assert checks[0].claimId==c.id and checks[0].source=='subtitle'


def test_negation_extra_context_and_period_unit_changes_require_review():
    from factlens.multimodal import review_modalities
    for text in ('2025년 한국 고용률 50%가 아니다','2024년 한국 고용률 5%','2025년 한국 고용률 5퍼센트포인트'):
        checks=review_modalities([claim()],visual(text))
        assert checks[0].status=='review_required'


def test_time_disjoint_records_are_not_compared():
    from factlens.multimodal import review_modalities
    v=visual('2025년 한국 고용률 5%');v.records[0].startSeconds=2;v.records[0].endSeconds=3
    assert review_modalities([claim()],v)==[]


def test_absent_visual_does_not_claim_internal_agreement():
    from factlens.multimodal import review_modalities
    assert review_modalities([claim()],VisualAnalysis(status='not_applicable',durationSeconds=3))==[]


def test_summary_is_counts_and_limits_not_a_truth_probability():
    from factlens.report import summarize
    a=claim();b=claim(id='second');a.verdict='CONFIRMED';b.verdict='REFUTED'
    result=summarize([a,b],[])
    assert result.overall=='mixed' and result.counts['CONFIRMED']==1
    assert result.independenceVerified is False
    assert result.strength=='not_assessed'
    assert 'probability' not in result.model_dump()


def test_modal_mismatch_requires_review_without_relabeling_external_claims():
    from factlens.multimodal import review_modalities
    from factlens.report import summarize
    c=claim();c.verdict='CONFIRMED'
    checks=review_modalities([c],visual('2025년 한국 고용률 5%'))
    assert summarize([c],checks).overall=='review_required'
    assert c.verdict=='CONFIRMED'


def test_pipeline_preserves_visual_provenance_and_adds_claim_summary(tmp_path):
    from factlens.pipeline import run_analysis
    from test_pipeline import TestProviders
    import subprocess
    video=tmp_path/'source.mp4'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=white:s=320x240:d=1','-c:v','libx264','-pix_fmt','yuv420p',str(video)],check=True)
    result=run_analysis({'consent':True,'path':str(tmp_path/'audio.wav'),'sourcePath':str(video),'duration':1},TestProviders())
    assert result.scope=='audio_visual' and result.visual.frames
    assert result.summary is not None and result.summary.counts['INSUFFICIENT']==5
    assert result.versions['visualVersion']=='visual-sampled-v1'
    assert result.versions['modalVersion']=='modal-record-review-v1'
