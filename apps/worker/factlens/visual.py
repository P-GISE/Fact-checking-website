"""Local bounded visual observations. OCR is uncertain, never a fact verdict."""
import json
import math
import re
import shutil
import subprocess
from pathlib import Path
from typing import Literal
from uuid import uuid4
from pydantic import BaseModel,Field,model_validator

VISUAL_VERSION='visual-sampled-v1'
MAX_FRAMES=12
MAX_CUES=2000

class VisualText(BaseModel):
    source:Literal['subtitle','ocr']
    startSeconds:float=Field(ge=0,allow_inf_nan=False)
    endSeconds:float=Field(ge=0,allow_inf_nan=False)
    text:str=Field(min_length=1,max_length=2000)
    frameId:str|None=Field(default=None,pattern=r'^[a-zA-Z0-9-]{1,64}$')

class Frame(BaseModel):
    frameId:str=Field(pattern=r'^[a-zA-Z0-9-]{1,64}$')
    timeSeconds:float=Field(ge=0,allow_inf_nan=False)

class VisualAnalysis(BaseModel):
    version:Literal['visual-sampled-v1']='visual-sampled-v1'
    status:Literal['complete','partial','unavailable','not_applicable']
    durationSeconds:float=Field(gt=0,le=180,allow_inf_nan=False)
    subtitleStatus:Literal['extracted','not_present','unsupported','failed','truncated']='not_present'
    ocrStatus:Literal['complete','partial','unavailable','no_video']='no_video'
    frames:list[Frame]=Field(default_factory=list,max_length=MAX_FRAMES)
    records:list[VisualText]=Field(default_factory=list,max_length=MAX_CUES+MAX_FRAMES)
    limitations:list[str]=Field(default_factory=list,max_length=20)

    @model_validator(mode='after')
    def valid_times(self):
        if any(r.endSeconds<r.startSeconds or r.endSeconds>self.durationSeconds for r in self.records):raise ValueError('INVALID_VISUAL_TIME')
        if any(f.timeSeconds>=self.durationSeconds for f in self.frames):raise ValueError('INVALID_VISUAL_TIME')
        ids={f.frameId for f in self.frames}
        if len(ids)!=len(self.frames):raise ValueError('DUPLICATE_FRAME_REFERENCE')
        if any(r.source=='ocr' and r.frameId not in ids for r in self.records):raise ValueError('INVALID_FRAME_REFERENCE')
        return self


def timestamp(value:str)->float:
    match=re.fullmatch(r'(?:(\d{2,3}):)?(\d{2}):(\d{2})\.(\d{3})',value)
    if not match:raise ValueError('INVALID_SUBTITLE_TIME')
    hours,minutes,seconds,millis=match.groups()
    if int(minutes)>=60 or int(seconds)>=60:raise ValueError('INVALID_SUBTITLE_TIME')
    return int(hours or 0)*3600+int(minutes)*60+int(seconds)+int(millis)/1000


def parse_vtt(body:str,duration:float)->tuple[list[VisualText],bool]:
    if not math.isfinite(duration) or not 0<duration<=180:raise ValueError('INVALID_DURATION')
    complete=len(body)<=8*1024*1024
    blocks=re.split(r'\n\s*\n',body[:8*1024*1024].replace('\r\n','\n').lstrip('\ufeff'))
    records=[]
    for block in blocks:
        lines=block.splitlines()
        if not lines or lines[0].startswith(('WEBVTT','NOTE','STYLE','REGION')):continue
        timing=next((i for i,line in enumerate(lines[:2]) if '-->' in line),None)
        if timing is None:complete=False;continue
        if len(records)>=MAX_CUES:complete=False;break
        try:
            left,right=lines[timing].split('-->',1)
            start,end=timestamp(left.strip()),timestamp(right.strip().split()[0])
            text=' '.join(' '.join(lines[timing+1:]).split())
            if not 0<=start<=end<=duration or not text:raise ValueError()
            if len(text)>2000:complete=False
            records.append(VisualText(source='subtitle',startSeconds=start,endSeconds=end,text=text[:2000]))
        except (ValueError,IndexError):complete=False
    return records,complete


def run(command:list[str],timeout:int=15):
    return subprocess.run(command,check=True,capture_output=True,timeout=timeout)


def extract_visual(path:Path,duration:float)->VisualAnalysis:
    if not math.isfinite(duration) or not 0<duration<=180:raise ValueError('INVALID_DURATION')
    if path.is_symlink() or not path.is_file():raise ValueError('INVALID_VISUAL_INPUT')
    result=VisualAnalysis(status='not_applicable',durationSeconds=duration)
    try:
        probe=json.loads(run(['ffprobe','-v','error','-protocol_whitelist','file,pipe','-show_streams','-of','json',str(path)]).stdout)
    except (OSError,subprocess.SubprocessError,ValueError):
        result.status='unavailable';result.limitations=['영상 스트림 정보를 읽지 못했습니다.'];return result
    streams=probe.get('streams',[])
    videos=[s for s in streams if s.get('codec_type')=='video' and not s.get('disposition',{}).get('attached_pic')]
    subtitles=[s for s in streams if s.get('codec_type')=='subtitle']
    if not videos and not subtitles:return result
    folder=path.parent/('visual-'+str(uuid4()));folder.mkdir(mode=0o700)
    result.status='complete'
    if subtitles:
        stream=subtitles[0]
        if stream.get('codec_name') not in ('mov_text','subrip','webvtt','ass','ssa','text'):
            result.subtitleStatus='unsupported';result.status='partial'
        else:
            target=folder/'subtitles.vtt'
            try:
                run(['ffmpeg','-nostdin','-v','error','-protocol_whitelist','file,pipe','-i',str(path),'-map',f"0:{int(stream['index'])}",'-c:s','webvtt','-fs','1048576',str(target)])
                with target.open('rb') as source:data=source.read(1048577)
                records,complete=parse_vtt(data[:1048576].decode('utf-8',errors='strict'),duration)
                result.records=records;result.subtitleStatus='extracted' if complete and len(data)<1048576 else 'truncated'
                if result.subtitleStatus=='truncated':result.status='partial'
            except (OSError,subprocess.SubprocessError,ValueError):result.subtitleStatus='failed';result.status='partial'
    if not videos:return result
    result.limitations=['15초 간격의 최대 12개 프레임을 표본으로 확인했습니다. 전체 화면의 의미 검증이 아닙니다.','OCR에는 인식 오류가 있을 수 있으며 사실 여부를 확정하지 않습니다.']
    executable=shutil.which('tesseract')
    languages=[]
    if executable:
        try:languages=run([executable,'--list-langs'],5).stdout.decode().splitlines()[1:]
        except (OSError,subprocess.SubprocessError):executable=None
    korean='kor' in languages
    result.ocrStatus='complete' if executable and korean else 'partial' if executable else 'unavailable'
    if not korean:result.limitations.append('한국어 OCR 언어 데이터가 없어 한국어 화면 인식은 미완료입니다.')
    if result.ocrStatus!='complete':result.status='partial'
    for index in range(min(MAX_FRAMES,math.ceil(duration/15))):
        moment=index*15;frame_id=str(uuid4());image=folder/(frame_id+'.png')
        try:
            run(['ffmpeg','-nostdin','-v','error','-protocol_whitelist','file,pipe','-ss',str(moment),'-i',str(path),'-map',f"0:{int(videos[0]['index'])}",'-frames:v','1','-vf','scale=960:540:force_original_aspect_ratio=decrease','-threads','1','-fs','2097152',str(image)],10)
            if not image.is_file() or image.is_symlink() or image.stat().st_size>2097152:raise ValueError()
            result.frames.append(Frame(frameId=frame_id,timeSeconds=moment))
            if executable:
                output=folder/(frame_id+'-ocr')
                run([executable,str(image),str(output),'-l','kor+eng' if korean else 'eng','--psm','11'],10)
                with output.with_suffix('.txt').open('rb') as source:data=source.read(16385)
                text=' '.join(data[:16384].decode('utf-8',errors='replace').split())
                if len(data)>16384 or len(text)>2000:result.status='partial';result.ocrStatus='partial'
                if text:result.records.append(VisualText(source='ocr',startSeconds=moment,endSeconds=min(moment+15,duration),text=text[:2000],frameId=frame_id))
        except (OSError,subprocess.SubprocessError,ValueError):result.status='partial';result.ocrStatus='partial'
    return result
