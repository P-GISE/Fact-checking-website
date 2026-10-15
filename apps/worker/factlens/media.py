import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

@dataclass
class MediaInfo:
    duration: float
    format: str

def probe_media(path: Path, timeout_seconds: int = 20) -> MediaInfo:
    if not 0 < path.stat().st_size <= 104857600:
        raise ValueError('SIZE_LIMIT')
    try:
        result=subprocess.run(['ffprobe','-v','error','-protocol_whitelist','file,pipe','-show_format','-show_streams','-of','json',str(path)],capture_output=True,check=True,timeout=timeout_seconds)
        data=json.loads(result.stdout)
        fmt=data['format']['format_name']
        duration=float(data['format']['duration'])
        if not any(s['codec_type']=='audio' for s in data['streams']):
            raise ValueError('NO_AUDIO')
        expected={'.mp4':'mp4','.mp3':'mp3','.wav':'wav'}.get(path.suffix.lower())
        if not expected or expected not in fmt.split(','):
            raise ValueError('FORMAT_MISMATCH')
        if expected=='mp4' and data['format'].get('tags',{}).get('major_brand','').strip() not in {'isom','iso2','iso3','iso4','iso5','iso6','iso7','iso8','iso9','mp41','mp42','avc1','dash'}:
            raise ValueError('FORMAT_MISMATCH')
        if not 0 < duration <= 180:
            raise ValueError('DURATION_LIMIT')
        # Decode the entire stream before any external call. Reject truncated/invalid media.
        subprocess.run(['ffmpeg','-v','error','-xerror','-protocol_whitelist','file,pipe','-i',str(path),'-map','0:a:0','-f','null','-'],check=True,capture_output=True,timeout=timeout_seconds)
        return MediaInfo(duration,fmt)
    except (subprocess.SubprocessError,KeyError,json.JSONDecodeError) as exc:
        raise ValueError('INVALID_MEDIA') from exc

def extract_audio(path: Path, target: Path) -> None:
    subprocess.run(['ffmpeg','-nostdin','-v','error','-xerror','-protocol_whitelist','file,pipe','-i',str(path),'-map','0:a:0','-ar','16000','-ac','1','-y',str(target)],capture_output=True,check=True,timeout=30)
