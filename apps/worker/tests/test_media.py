import subprocess
from pathlib import Path
import pytest
from factlens.media import probe_media, extract_audio

@pytest.fixture
def wav(tmp_path):
    p=tmp_path/'short.wav'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','sine=frequency=440:duration=1',str(p)],check=True)
    return p

def test_real_wav_and_extract(wav,tmp_path):
    assert probe_media(wav).duration == pytest.approx(1,abs=.01)
    out=tmp_path/'audio.wav'
    extract_audio(wav,out)
    assert out.stat().st_size>100

@pytest.mark.parametrize('suffix',['mp3','mp4'])
def test_real_formats(wav,tmp_path,suffix):
    p=tmp_path/f'a.{suffix}'
    subprocess.run(['ffmpeg','-v','error','-i',str(wav),str(p)],check=True)
    assert probe_media(p).duration>0

def test_container_mismatch(wav,tmp_path):
    p=tmp_path/'wrong.mp4';p.write_bytes(wav.read_bytes())
    with pytest.raises(ValueError,match='FORMAT_MISMATCH'):probe_media(p)

def test_corrupt_file(tmp_path):
    p=tmp_path/'bad.wav';p.write_bytes(b'not-media')
    with pytest.raises(ValueError,match='INVALID_MEDIA'):probe_media(p)

def test_duration_limit(tmp_path):
    p=tmp_path/'long.wav'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','anullsrc=r=8000:cl=mono','-t','180.01',str(p)],check=True)
    with pytest.raises(ValueError,match='DURATION_LIMIT'):probe_media(p)

def test_renamed_quicktime_is_not_mp4(wav,tmp_path):
    p=tmp_path/'not-mp4.mp4'
    subprocess.run(['ffmpeg','-v','error','-i',str(wav),'-f','mov',str(p)],check=True)
    with pytest.raises(ValueError,match='FORMAT_MISMATCH'):probe_media(p)
