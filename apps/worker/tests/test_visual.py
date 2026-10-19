import subprocess
from pathlib import Path
import pytest


def test_webvtt_keeps_timestamps_and_plain_text_without_interpreting_markup():
    from factlens.visual import parse_vtt
    cues,complete=parse_vtt('WEBVTT\n\n00:00:00.500 --> 00:00:02.000\n2025년 한국 고용률 50%\n\n00:00:02.000 --> 00:00:03.000\n<b>50%</b>\n',3)
    assert complete and len(cues)==2
    assert cues[0].startSeconds==.5 and cues[0].endSeconds==2
    assert cues[1].text=='<b>50%</b>' and cues[0].source=='subtitle'


@pytest.mark.parametrize('times',['00:00:02.000 --> 00:00:01.000','00:00:00.000 --> 00:00:05.000','nan --> 00:00:01.000'])
def test_invalid_subtitle_time_is_explicitly_incomplete(times):
    from factlens.visual import parse_vtt
    cues,complete=parse_vtt('WEBVTT\n\n'+times+'\ntext\n',3)
    assert not cues and not complete


def test_subtitle_count_and_text_are_bounded():
    from factlens.visual import parse_vtt
    body='WEBVTT\n\n'+('00:00:00.000 --> 00:00:01.000\n'+('x'*2100)+'\n\n')*2100
    cues,complete=parse_vtt(body,3)
    assert len(cues)==2000 and not complete
    assert len(cues[0].text)==2000


def test_audio_only_input_does_not_invent_visual_coverage(tmp_path):
    from factlens.visual import extract_visual
    audio=tmp_path/'source.wav'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','sine=duration=1',str(audio)],check=True)
    result=extract_visual(audio,1)
    assert result.status=='not_applicable' and result.frames==[] and result.records==[]


def test_generated_video_extracts_private_timed_frames_and_real_ocr(tmp_path):
    from factlens.visual import extract_visual
    video=tmp_path/'source.mp4'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=white:s=640x360:d=2','-vf',"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='RATE 50 PERCENT':fontcolor=black:fontsize=42:x=30:y=150",'-c:v','libx264','-pix_fmt','yuv420p',str(video)],check=True)
    result=extract_visual(video,2)
    assert result.frames and result.frames[0].timeSeconds==0
    assert any('50' in record.text for record in result.records if record.source=='ocr')
    assert all(0<=record.startSeconds<=record.endSeconds<=2 for record in result.records)
    assert 'source.mp4' not in result.model_dump_json()
    assert len(list(tmp_path.rglob('*.png')))<=12


def test_invalid_duration_cannot_create_unbounded_frames(tmp_path):
    from factlens.visual import extract_visual
    for duration in (0,-1,181,float('nan'),float('inf')):
        with pytest.raises(ValueError):extract_visual(tmp_path/'source.mp4',duration)


def test_visual_rejects_duplicate_or_unbounded_frame_references():
    from factlens.visual import VisualAnalysis,Frame
    import pytest
    for frames in ([Frame(frameId='same',timeSeconds=0),Frame(frameId='same',timeSeconds=1)],):
        with pytest.raises(ValueError):VisualAnalysis(status='complete',durationSeconds=2,frames=frames)
    with pytest.raises(ValueError):Frame(frameId='../outside',timeSeconds=0)


def test_real_embedded_subtitles_keep_timing_and_text(tmp_path):
    import subprocess
    from factlens.visual import extract_visual
    subtitle=tmp_path/'text.srt';subtitle.write_text('1\n00:00:00,000 --> 00:00:01,000\n2025년 한국 고용률 50%\n',encoding='utf-8')
    media=tmp_path/'subtitled.mp4'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=black:s=320x180:d=2','-i',str(subtitle),'-c:v','libx264','-threads','1','-c:s','mov_text',str(media)],check=True)
    result=extract_visual(media,2)
    assert result.subtitleStatus=='extracted'
    records=[r for r in result.records if r.source=='subtitle']
    assert records[0].text=='2025년 한국 고용률 50%' and records[0].endSeconds==1
