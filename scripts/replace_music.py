"""Replace only delivery music, retaining video packets and required attribution."""
from pathlib import Path
import argparse,array,json,math,subprocess,sys
sys.path.insert(0,str(Path(__file__).resolve().parent/'runtime'))
from audio_delivery import audio_options,probe,resolve_audio,sha256

def binaries(project):
    import shutil
    result=[]
    for name in ['ffmpeg','ffprobe']:
        local=project/'ffmpeg'/f'{name}.exe'
        found=str(local) if local.is_file() else shutil.which(name)
        if not found:raise SystemExit('缺少'+name)
        result.append(found)
    return result

def video_packets(ffprobe,path):
    cmd=[str(ffprobe),'-v','error','-select_streams','v:0','-show_packets','-show_data_hash','sha256','-show_entries','packet=pts,dts,duration,data_hash','-of','json',str(path)]
    return json.loads(subprocess.run(cmd,capture_output=True,check=True).stdout)['packets']

def mono(ffmpeg,path,duration,start=0):
    cmd=[str(ffmpeg),'-v','error']
    if start:cmd+=['-ss',str(start)]
    cmd+=['-i',str(path),'-map','0:a:0','-t',str(duration),'-ac','1','-ar','8000','-f','f32le','pipe:1']
    a=array.array('f');a.frombytes(subprocess.run(cmd,capture_output=True,check=True).stdout)
    if sys.byteorder!='little':a.byteswap()
    return a

def verify(ffmpeg,ffprobe,source,output,music,project):
    before=probe(ffprobe,source);after=probe(ffprobe,output,count=True)
    sv=next(s for s in before['streams'] if s['codec_type']=='video')
    ov=next(s for s in after['streams'] if s['codec_type']=='video')
    duration=float(ov['duration'])
    for field in ['width','height','r_frame_rate','avg_frame_rate','time_base','duration_ts']:
        if sv[field]!=ov[field]:raise RuntimeError('视频参数变化：'+field)
    if int(ov['nb_read_frames'])!=int(sv['nb_frames']):raise RuntimeError('视频帧数发生变化。')
    if video_packets(ffprobe,source)!=video_packets(ffprobe,output):raise RuntimeError('视频包或时间戳变化，不是无损换配乐。')
    if len([s for s in after['streams'] if s['codec_type']=='audio'])!=1:raise RuntimeError('音轨数量不正确。')
    original_tags=before['format'].get('tags',{});tags=after['format'].get('tags',{})
    for key in ['title','artist','comment','copyright','description']:
        if original_tags.get(key)!=tags.get(key):raise RuntimeError('署名/许可metadata变化：'+key)
    if (project/'LICENSE.txt').is_file() and tags.get('description')!=(project/'LICENSE.txt').read_text(encoding='utf-8').strip():raise RuntimeError('LICENSE metadata不完整。')
    a=mono(ffmpeg,music['path'],duration,music['start_seconds']);b=mono(ffmpeg,output,duration)
    n=min(len(a),len(b));ma=math.fsum(a[:n])/n;mb=math.fsum(b[:n])/n
    aa=math.fsum((x-ma)**2 for x in a[:n]);bb=math.fsum((y-mb)**2 for y in b[:n])
    corr=math.fsum((x-ma)*(y-mb) for x,y in zip(a[:n],b[:n]))/math.sqrt(aa*bb) if aa*bb else None
    if corr is not None and corr<.98:raise RuntimeError('新配乐波形或起点核验未通过。')
    subprocess.run([str(ffmpeg),'-v','error','-i',str(output),'-map','0:v:0','-map','0:a:0','-f','null','-'],capture_output=True,check=True)
    return {'file':str(output),'source_video':str(source),'music_source':music,'frames':int(ov['nb_read_frames']),'fps':ov['avg_frame_rate'],'dimensions':[ov['width'],ov['height']],'video_seconds':duration,'video_packets_and_timestamps_identical':True,'audio_codec':'aac','music_zero_lag_correlation':corr,'music_start_verified':True,'license_and_attribution_preserved':True,'full_decode_passed':True,'sha256':sha256(output),'dynamic_review':'unchanged picture; previous visual review status retained'}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--project',required=True,type=Path)
    parser.add_argument('--input',required=True,type=Path)
    parser.add_argument('--music',type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--audit',type=Path)
    args=parser.parse_args();project=args.project.resolve();source=args.input.resolve();output=args.output.resolve()
    if not source.is_file():raise SystemExit('缺少已完成的视频。')
    if output==source or output.exists():raise SystemExit('输出已存在或指向原片；请选择新的版本目录。')
    ffmpeg,ffprobe=binaries(project);music=resolve_audio(project,args.music)
    original=probe(ffprobe,source);v=next(s for s in original['streams'] if s['codec_type']=='video');duration=float(v['duration'])
    inputs,codec=audio_options(ffprobe,music,duration)
    output.parent.mkdir(parents=True,exist_ok=True);partial=output.with_suffix('.partial.mp4')
    if partial.exists():raise SystemExit('存在未完成输出，先检查该partial文件。')
    subprocess.run([str(ffmpeg),'-v','error','-n','-i',str(source),*inputs,'-map','0:v:0','-map','1:a:0','-map_metadata','0','-c:v','copy',*codec,'-t',f'{duration:.9f}','-movflags','+faststart',str(partial)],check=True)
    report=verify(ffmpeg,ffprobe,source,partial,music,project)
    partial.replace(output);report['file']=str(output)
    audit=args.audit or output.parent/'music_audit.json';audit.parent.mkdir(parents=True,exist_ok=True);audit.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':main()
