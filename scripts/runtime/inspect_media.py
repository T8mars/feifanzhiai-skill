"""Background-only visual review artifacts. Never used as generation references."""
from pathlib import Path
import sys,json
import av
from PIL import Image,ImageDraw
import numpy as np

ROOT=Path(__file__).resolve().parent
def keep_counts():
    return {p.split()[0][:3]:int(p.split()[1]) for p in (ROOT/'补齐生成用/原始帧数.txt').read_text().splitlines() if p[:1].isdigit()}

def review(num, video_path=None, label=None):
    p=Path(video_path) if video_path else ROOT/'完成分段'/f'{num}.mp4';keep=keep_counts()[num]
    out=ROOT/'制作分析/生成复核'/(label or num);out.mkdir(parents=True,exist_ok=True)
    pages=[];diff=[];prev=None;shape=None;black=[]
    with av.open(str(p)) as c:
        s=c.streams.video[0];fps=str(s.average_rate);total=0
        for i,f in enumerate(c.decode(video=0)):
            total+=1
            if i>=keep:continue
            im=f.to_image();shape=im.size
            small=np.array(im.resize((160,90)),dtype=np.float32)
            if prev is not None:diff.append([i,float(np.mean(np.abs(small-prev)))])
            prev=small
            if small.mean()<3:black.append(i)
            # Every retained frame is displayed in order; 24 images per page.
            if i%24==0:
                canvas=Image.new('RGB',(1920,4*206),(20,20,20));pages.append(canvas);d=ImageDraw.Draw(canvas)
            x=(i%24%6)*320;y=(i%24//6)*206
            canvas.paste(im.resize((320,180)),(x,y+24))
            d.text((x+4,y+4),f'{num} f{i} {i/24:.3f}s',fill='white')
        assert total>=keep,(num,total,keep)
    for j,canvas in enumerate(pages):canvas.save(out/f'{num}_all_{j+1:02}.jpg',quality=90)
    data={'num':num,'path':str(p),'fps':fps,'dimensions':shape,'decoded_frames':total,'keep':keep,'black_frames':black,'largest_frame_differences':sorted(diff,key=lambda x:-x[1])[:10],'review_state':'contact_sheets_ready; dynamic review pending'}
    (out/'metrics.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(data,ensure_ascii=False))

if __name__=='__main__':
    for job in sys.argv[1:]:
        num=job[:3]
        if '/' in job:
            review(num,ROOT/'candidates'/job/'完成分段'/f'{num}.mp4',job.replace('/','_'))
        else:review(num)
