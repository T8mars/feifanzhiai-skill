"""Local delivery audio policy; generation reference-video audio stays separate."""
from pathlib import Path
import hashlib,json,subprocess

def sha256(path):
    digest=hashlib.sha256()
    with open(path,'rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()

def resolve_audio(project, override=None):
    project=Path(project).resolve()
    manifest=project/'delivery_audio.json'
    cfg=json.loads(manifest.read_text(encoding='utf-8')) if manifest.exists() else {}
    if override is not None:cfg={'path':str(override),'start_seconds':0}
    path=Path(cfg.get('path','配乐/非凡之爱_新配乐_已对齐.wav'))
    if not path.is_absolute():path=project/path
    path=path.resolve()
    if not path.is_file():raise SystemExit('缺少交付配乐；先运行技能bootstrap_runtime.py，或明确指定新的音乐文件。')
    if cfg.get('sha256') and sha256(path)!=cfg['sha256']:
        raise SystemExit('配乐与已记录的SHA256不一致，请确认新版本后更新delivery_audio.json。')
    start=float(cfg.get('start_seconds',0))
    if start<0:raise SystemExit('配乐起点不能为负数。')
    return {'path':str(path),'sha256':sha256(path),'start_seconds':start}

def probe(ffprobe,path,count=False):
    args=[str(ffprobe),'-v','error']
    if count:args+=['-count_frames']
    args+=['-show_streams','-show_format','-of','json',str(path)]
    return json.loads(subprocess.run(args,capture_output=True,check=True).stdout)

def audio_options(ffprobe,setting,duration):
    info=probe(ffprobe,setting['path'])
    streams=[s for s in info['streams'] if s['codec_type']=='audio']
    if not streams:raise SystemExit('指定音乐没有可解码音轨。')
    stream=streams[0];length=float(stream.get('duration') or info['format']['duration'])
    start=setting['start_seconds']
    rate=int(stream.get('sample_rate') or 44100)
    if length-start+1/rate<duration:
        raise SystemExit('音乐短于画面；停止导出，不能截短视频、变速或擅自循环音乐。')
    inputs=(['-ss',str(start)] if start else [])+['-i',setting['path']]
    codec=['-c:a','copy'] if stream['codec_name']=='aac' and start==0 else ['-c:a','aac','-b:a','320k']
    return inputs,codec
