"""Save a separately reusable sample-aligned soundtrack without changing pictures."""
from pathlib import Path
import argparse,json,subprocess,sys,wave
sys.path.insert(0,str(Path(__file__).resolve().parent/'runtime'))
from audio_delivery import probe,sha256
from replace_music import binaries

def main():
    p=argparse.ArgumentParser();p.add_argument('--project',required=True,type=Path);p.add_argument('--input',required=True,type=Path);p.add_argument('--output',required=True,type=Path);p.add_argument('--frames',type=int,default=1417);p.add_argument('--fps',type=int,default=24);p.add_argument('--set-default',action='store_true');args=p.parse_args()
    root=args.project.resolve();source=args.input.resolve();dest=args.output.resolve()
    if dest.exists() or source==dest:raise SystemExit('对齐版必须另存，不覆盖原音频。')
    ffmpeg,ffprobe=binaries(root);info=probe(ffprobe,source);stream=next(s for s in info['streams'] if s['codec_type']=='audio');rate=int(stream['sample_rate']);samples=round(args.frames*rate/args.fps);duration=args.frames/args.fps
    if float(stream.get('duration') or info['format']['duration'])+1/rate<duration:raise SystemExit('音乐长度不足，不能擅自变速或循环。')
    dest.parent.mkdir(parents=True,exist_ok=True)
    if source.suffix.lower()=='.wav' and stream['codec_name']=='pcm_s16le':
        with wave.open(str(source),'rb') as inp:
            params=inp.getparams();data=inp.readframes(samples)
            with wave.open(str(dest),'wb') as out:out.setparams(params);out.writeframes(data)
    else:
        subprocess.run([ffmpeg,'-v','error','-n','-i',str(source),'-map','0:a:0','-af',f'atrim=end_sample={samples},asetpts=PTS-STARTPTS','-c:a','pcm_s24le',str(dest)],check=True)
    actual=probe(ffprobe,dest)['streams'][0];actual_samples=round(float(actual['duration_ts'])*float(actual['time_base'].split('/')[0])/float(actual['time_base'].split('/')[1])*rate)
    if actual_samples!=samples:raise RuntimeError('对齐音频样本数不正确。')
    try:path=str(dest.relative_to(root)).replace('\\','/')
    except ValueError:path=str(dest)
    result={'path':path,'sha256':sha256(dest),'start_seconds':0,'source_original':str(source),'source_original_sha256':sha256(source),'alignment':{'video_frames':args.frames,'fps':args.fps,'video_seconds':duration,'audio_sample_frames':samples,'sample_rate':rate,'audio_seconds':samples/rate,'timing_error_seconds':samples/rate-duration},'processing':'tail trim on original sample grid; no speed, gain, fade or channel change'}
    dest.with_suffix('.alignment.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    if args.set_default:
        manifest=root/'delivery_audio.json'
        if manifest.exists():(root/'制作分析').mkdir(exist_ok=True);backup=root/'制作分析'/('delivery_audio_before_'+dest.stem+'.json');backup.write_bytes(manifest.read_bytes())
        manifest.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':main()
