"""Run one named No Ordinary Love shot on the published Chenyu workflow."""
import argparse
from contextlib import contextmanager
from fractions import Fraction
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from urllib import error, parse, request
import uuid

BASE = 'https://www.chenyu.cn/api/open/v2'
WORKFLOW = 'wf_04a30714468c59fd78f5'
CAST = {'一号': ['一号'], '二号': ['二号'], '一号二号': ['一号', '二号']}
TERMINAL_FAILURE = {'failed', 'canceled', 'cancelled', 'error'}


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def save(path, obj):
    tmp = path.with_suffix('.tmp')
    with tmp.open('w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


@contextmanager
def project_lock(root):
    # The OS releases the lock on a crash. The file itself is reusable.
    with (root/'chenyu_workflow.lock').open('a+b') as f:
        f.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


class Api:
    def __init__(self, key_file):
        self.key = Path(key_file).read_text(encoding='utf-8-sig').strip()
        if not self.key:
            raise ValueError('Empty Chenyu key file')
        self.opener = request.build_opener(NoRedirect())

    def call(self, path, payload=None, mime=None):
        if isinstance(payload, dict):
            payload = json.dumps(payload, ensure_ascii=False).encode()
        req = request.Request(BASE + path, data=payload, headers={
            'Authorization':'Bearer ' + self.key, 'Content-Type':mime or 'application/json',
            'User-Agent':'Feifan-Workflow/1.0'})
        with self.opener.open(req, timeout=120) as response:
            envelope = json.load(response)
        if envelope.get('code') != 0:
            msg = str(envelope.get('msg','')).replace(self.key, '[redacted]')
            raise ValueError('Chenyu rejected request: '+str(envelope.get('code'))+' '+msg[:180])
        return envelope['data']

    def upload(self, path, kind):
        content = path.read_bytes()
        name = hashlib.sha256(content).hexdigest() + path.suffix.lower()
        boundary = uuid.uuid4().hex
        header = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\n'
                  f'Content-Type: {mimetypes.guess_type(name)[0] or "application/octet-stream"}\r\n\r\n')
        fields = ''.join(f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}'
                         for key,value in [('media_type',kind),('purpose','temp_input')])
        body = header.encode() + content + (fields + f'\r\n--{boundary}--\r\n').encode()
        data = self.call('/assets', body, 'multipart/form-data; boundary='+boundary)
        uri = data.get('asset_uri')
        if not isinstance(uri,str) or not uri.startswith('asset://'):
            raise ValueError('Missing Chenyu asset URI')
        return uri


def inputs_for(root, num):
    if not re.fullmatch(r'0(?:0[1-9]|1[0-9])', num):
        raise ValueError('Choose exactly one shot from 001 to 019')
    src = root/'补齐生成用'
    rows = [line.split() for line in (src/'补齐后帧数.txt').read_text(encoding='utf-8-sig').splitlines()]
    frame_text, cast = next(row[1:] for row in rows if row and row[0] == num+'.mp4')
    frames = int(frame_text)
    video = src/f'{num} {frames}.mp4'
    refs = [root/'替换用参考图'/(name+'.png') for name in CAST[cast]]
    prompt = (root/'提示词'/(num+'.txt')).read_text(encoding='utf-8-sig').strip()
    if not prompt or set(re.findall(r'<Picture (\d+)>',prompt)) != {str(i+1) for i in range(len(refs))}:
        raise ValueError('Prompt picture indices differ from this shot')
    if not 0 < frames <= 240:
        raise ValueError('Shot exceeds the 10-second generation limit')
    return frames,video,refs,prompt


def route(info, n):
    if info.get('workflow_id') != WORKFLOW or not info.get('revision_id'):
        raise ValueError('Unexpected workflow or missing published revision')
    if info.get('may_incur_external_model_cost') is not False:
        raise ValueError('Published workflow external-cost terms have changed')
    fields = {f['name']:f for f in info['editable_parameter_manifest']}
    types = {'node_138_value':'string','node_326_value':'int','node_342_video':'video_input'}
    for i in range(n):
        types[f'node_{386+i}_image']='image_input'
    if any(fields.get(k,{}).get('value_type') != v for k,v in types.items()) or any(
            f.get('required') and k not in types for k,f in fields.items()):
        raise ValueError('Published input schema changed; inspect before submitting')
    videos=[o['name'] for o in info['candidate_output_manifest'] if o.get('type')=='video']
    if len(videos)!=1:
        raise ValueError('Expected exactly one named video output')
    return videos[0]


def local_proof(path, binary, frames):
    info = subprocess.check_output([binary('ffprobe'),'-v','error','-count_frames','-show_streams',
                                    '-of','json',str(path)])
    streams = json.loads(info)['streams']
    v = next(s for s in streams if s['codec_type']=='video')
    if int(v['nb_read_frames'])!=frames or Fraction(v['avg_frame_rate'])!=24:
        raise ValueError('Downloaded frame count or cadence differs from the request')
    subprocess.run([binary('ffmpeg'),'-nostdin','-v','error','-xerror','-i',str(path),
                    '-map','0:v:0','-map','0:a?','-f','null','-'],check=True)
    return {'width':v['width'],'height':v['height'],'frames':frames,'fps':24,
            'audio':any(s['codec_type']=='audio' for s in streams),
            'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def run(root, num):
    cfg = read(root/'provider.json')
    if cfg.get('provider') != 'chenyu' or cfg.get('workflow_id') != WORKFLOW:
        raise ValueError('Select the Chenyu channel in a separate work copy')
    api = Api(cfg['api_key_file'])
    frames,video,refs,prompt = inputs_for(root,num)
    signature = {'prompt':hashlib.sha256(prompt.encode()).hexdigest(), 'frames':frames,
                 'files':[hashlib.sha256(p.read_bytes()).hexdigest() for p in [video,*refs]]}
    analysis = root/'制作分析'/'chenyu'
    analysis.mkdir(parents=True,exist_ok=True)
    receipt = analysis/(num+'.json')
    dest = root/'完成分段'/(num+'.mp4')
    def binary(name):
        local = root/'ffmpeg'/(name+'.exe')
        return str(local) if local.is_file() else name
    if receipt.exists():
        state = read(receipt)
        if state['inputs_sha256'] != signature:
            raise ValueError('Shot inputs changed; use a new work copy')
        if state.get('proof') and dest.exists():
            if hashlib.sha256(dest.read_bytes()).hexdigest()!=state['proof']['sha256']:
                raise ValueError('Verified output was modified')
            return state
    else:
        if dest.exists():
            raise ValueError('Destination already contains an unrelated shot')
        info = api.call('/workflow/market/info?workflow_id='+WORKFLOW)
        output_name = route(info,len(refs))
        inputs = {'node_138_value':prompt,'node_326_value':frames,'node_342_video':api.upload(video,'video')}
        for i,p in enumerate(refs):
            inputs[f'node_{386+i}_image'] = api.upload(p,'image')
        state={'inputs_sha256':signature,'output_name':output_name,'request':{
            'inputs':inputs,'workflow_id':WORKFLOW,'revision_id':info['revision_id'],
            'idempotency_key':uuid.uuid4().hex,'accept_external_cost_risk':False}}
        save(receipt,state)
    if not state.get('order'):
        accepted = api.call('/workflow/run/submit', state['request'])
        state['order'] = accepted['run_order_id']
        save(receipt,state)
        print('Accepted', num, state['order'],flush=True)
    url = '/workflow/run/info?' + parse.urlencode({'run_order_id':state['order']})
    previous = None
    while True:
        try:
            data = api.call(url)
        except error.HTTPError as exc:
            if exc.code not in (408,429,500,502,503,504): raise
            time.sleep(15)
            continue
        except (error.URLError,TimeoutError,ConnectionError):
            time.sleep(15)
            continue
        if data.get('run_order_id') != state['order'] or data.get('revision_id') != state['request']['revision_id']:
            raise ValueError('Order or revision mismatch')
        status = data['run_status']
        state['billing']={k:data.get(k) for k in ('settlement_status','quote_currency','final_amount','total_cost')}
        state['status']=status
        save(receipt,state)
        if status != previous:
            print('Shot',num,status,flush=True)
            previous=status
        if status in TERMINAL_FAILURE:
            raise RuntimeError('Chenyu order ended: '+status+' '+str(data.get('error_code') or ''))
        outputs = data.get('outputs')
        value = outputs.get(state['output_name']) if isinstance(outputs, dict) else None
        if isinstance(value,list) and len(value)==1: value=value[0]
        if status=='succeeded' and isinstance(value,str) and value.startswith('https://'):
            break
        time.sleep(10)
    dest.parent.mkdir(parents=True,exist_ok=True)
    temp=dest.with_suffix('.chenyu.part.mp4')
    if dest.exists():
        proof=local_proof(dest,binary,frames)
        if proof['sha256'] != state.get('verified_sha256'):
            raise ValueError('Unregistered output exists; refusing to overwrite')
    else:
        # Public result requests carry no API credential.
        with request.urlopen(request.Request(value,headers={'User-Agent':'Mozilla/5.0'}),timeout=90) as r, temp.open('wb') as out:
            shutil.copyfileobj(r,out)
        proof=local_proof(temp,binary,frames)
        state['verified_sha256']=proof['sha256']
        save(receipt,state)
        os.replace(temp,dest)
    state['proof']=proof
    save(receipt,state)
    return state


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('shot',help='One segment ID, for example 015')
    parser.add_argument('--project',type=Path,default=Path(__file__).resolve().parent)
    args=parser.parse_args()
    with project_lock(args.project):
        result=run(args.project,args.shot)
    print(json.dumps({'order':result['order'],'media':result['proof'],'billing':result['billing']},ensure_ascii=False))
