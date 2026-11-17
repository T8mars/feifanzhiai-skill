"""Offline identity-recovery guide for the original015; character refs unchanged."""
from pathlib import Path
from fractions import Fraction
import argparse,hashlib,importlib.util,json,os,re,shutil,subprocess,sys
import av
import numpy as np
from PIL import Image,ImageDraw,ImageFilter

SKILL=Path(__file__).resolve().parent.parent

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--project',required=True,type=Path);parser.add_argument('--name',required=True);parser.add_argument('--prompt',required=True,type=Path);parser.add_argument('--radius',type=float,default=70);args=parser.parse_args()
    if not re.fullmatch(r'[a-z0-9_]+',args.name) or not 40<=args.radius<=120:raise SystemExit('候选名称或软化半径无效。')
    root=args.project.resolve();cfg=json.loads((SKILL/'references/015-tracking.json').read_text(encoding='utf-8'));source=root/'补齐生成用'/cfg['source_filename']
    if hashlib.sha256(source.read_bytes()).hexdigest()!=cfg['source_sha256']:raise SystemExit('视频不是本技能固定015源片，不能套用这组跟踪坐标。')
    dest=root/'candidates/015'/args.name
    if dest.exists():raise SystemExit('候选目录已存在，不覆盖受理输入或历史。')
    for d in ['补齐生成用','提示词','替换用参考图','完成分段','制作分析','ffmpeg']:(dest/d).mkdir(parents=True,exist_ok=True)
    for f in ['rh_batch.py','validate_prompts.py','LICENSE.txt']:shutil.copy2(root/f,dest/f)
    if (root/'api_key.txt').exists():shutil.copy2(root/'api_key.txt',dest/'api_key.txt')
    for f in ['一号.png','二号.png']:shutil.copy2(root/'替换用参考图'/f,dest/'替换用参考图'/f)
    for table in ['原始帧数.txt','补齐后帧数.txt']:
        lines=[x for x in (root/'补齐生成用'/table).read_text(encoding='utf-8').splitlines() if x.startswith('015')]
        if len(lines)!=1:raise SystemExit('015帧数表不唯一。')
        (dest/'补齐生成用'/table).write_text(lines[0]+'\n',encoding='utf-8')
    shutil.copy2(root/'补齐生成用/015.txt',dest/'补齐生成用/015.txt');shutil.copy2(args.prompt,dest/'提示词/015.txt')
    for f in ['ffmpeg.exe','ffprobe.exe']:os.link(root/'ffmpeg'/f,dest/'ffmpeg'/f)
    shutil.copy2(root/'ai应用.txt',dest/'ai应用.txt');(dest/'并发数.txt').write_text('1\n',encoding='utf-8')
    subprocess.run([sys.executable,'-B','-X','utf8',str(dest/'validate_prompts.py')],check=True)
    silent=dest/'制作分析/guide_silent.mp4'
    with av.open(str(source)) as inp,av.open(str(silent),'w') as out:
        if not inp.streams.audio:raise SystemExit('源片必须带原段音轨。')
        stream=out.add_stream('libx264',rate=24);stream.width=1920;stream.height=1080;stream.pix_fmt='yuv420p';stream.options={'crf':'10','preset':'medium'};count=0
        for i,frame in enumerate(inp.decode(video=0)):
            im=frame.to_image()
            if im.size!=(1920,1080):raise SystemExit('源片画幅不匹配。')
            for n,subject in enumerate(['male','female']):
                boxes=cfg[subject];box=tuple(round(np.interp(i,cfg['keys'],[b[k] for b in boxes])) for k in range(4));region=im.crop(box)
                mask=Image.new('L',region.size,0);ImageDraw.Draw(mask).ellipse((8,8,region.width-8,region.height-8),fill=255);mask=mask.filter(ImageFilter.GaussianBlur(10));arr=np.array(mask)
                if n==0:
                    rgb=np.asarray(region);red=(rgb[:,:,0]>85)&(rgb[:,:,1]<45)&(rgb[:,:,2]<60)&(rgb[:,:,0].astype(float)>np.maximum(rgb[:,:,1],rgb[:,:,2]).astype(float)*2.5);red[round(region.height*.5):,:]=False;arr[red]=0
                im.paste(Image.composite(region.filter(ImageFilter.GaussianBlur(args.radius)),region,Image.fromarray(arr)),box[:2])
            vf=av.VideoFrame.from_image(im);vf.pts=i;vf.time_base=Fraction(1,24)
            for packet in stream.encode(vf):out.mux(packet)
            if i in [0,24,60]:im.resize((960,540)).save(dest/'制作分析'/f'guide_{i:02}.jpg',quality=93)
            count+=1
        for packet in stream.encode():out.mux(packet)
    if count!=73:raise SystemExit('引导帧数不匹配，不能提交。')
    video=dest/'补齐生成用'/cfg['source_filename']
    subprocess.run([str(root/'ffmpeg/ffmpeg.exe'),'-v','error','-n','-i',str(silent),'-i',str(source),'-map','0:v:0','-map','1:a:0','-c','copy','-movflags','+faststart',str(video)],check=True)
    metadata={'segment':'015','method':args.name,'status':'prepared_not_submitted','private':True,'radius':args.radius,'source_sha256':cfg['source_sha256'],'guide_sha256':hashlib.sha256(video.read_bytes()).hexdigest(),'frames':73,'fps':24,'source_audio_preserved':True,'reference_images_unchanged':True,'purpose':'temporary motion input, not delivery video'}
    (dest/'meta.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    spec=importlib.util.spec_from_file_location('guide_rh',dest/'rh_batch.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.validate_motion_input('015')
    print(json.dumps({'candidate':str(dest),'prepared_only':True,'no_network_or_paid_submission':True},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
