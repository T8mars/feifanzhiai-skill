"""Three own generation slots across prepared repair candidates; no blind paid retry."""
from pathlib import Path
import atexit,json,os,re,shutil,subprocess,sys,time
import psutil

ROOT=Path(__file__).resolve().parent
AREA=ROOT/'制作分析'
TERMINAL={'SUCCESS','FAILED'}

def read_json(path,default):
    try:return json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError):return default

def task(key):
    n,m=key;s=read_json(ROOT/'candidates'/n/m/'rh_state.json',{})
    return s,s.get('tasks',{}).get(n,{})

def generation_slots(active,base):
    count=sum(t.get('status') not in TERMINAL for t in base.values())
    for key in active:
        _,t=task(key)
        if t.get('status') not in TERMINAL:count+=1
    return count

def main():
    AREA.mkdir(exist_ok=True);lock=AREA/'repair_scheduler.lock'
    if lock.exists():
        try:pid=int(lock.read_text())
        except ValueError:raise SystemExit('调度器锁内容不明，先检查。')
        if psutil.pid_exists(pid):raise SystemExit('已有修复调度器，不能重复启动。')
        lock.unlink()
    fd=os.open(lock,os.O_WRONLY|os.O_CREAT|os.O_EXCL);os.write(fd,str(os.getpid()).encode());os.close(fd)
    def release():
        if lock.exists() and lock.read_text()==str(os.getpid()):lock.unlink()
    atexit.register(release)
    active={};seen=set();done=set();blocked=set();freeze=False
    for proc in psutil.process_iter(['pid','name']):
        try:
            if 'python' not in (proc.info['name'] or '').lower() or 'rh_batch.py' not in ' '.join(proc.cmdline()):continue
            rel=Path(proc.cwd()).resolve().relative_to((ROOT/'candidates').resolve())
            if len(rel.parts)==2:active[tuple(rel.parts)]=(proc,None,None);seen.add(tuple(rel.parts))
        except (psutil.Error,ValueError):continue
    while True:
        base=read_json(ROOT/'rh_state.json',{}).get('tasks',{})
        # Never race a main batch that can still submit unaccepted base shots.
        ready=all(base.get(f'{i:03}',{}).get('taskId') for i in range(1,20))
        for key,(proc,popen,log) in list(active.items()):
            try:running=popen.poll() is None if popen else proc.is_running() and proc.status()!=psutil.STATUS_ZOMBIE
            except psutil.Error:running=False
            if running:continue
            if log:log.close()
            _,t=task(key)
            if t.get('status')=='SUCCESS' and t.get('file') and Path(t['file']).is_file():done.add(key)
            else:blocked.add(key)
            if t.get('status')=='SUBMISSION_UNCERTAIN':freeze=True
            del active[key]
        pending=[]
        for row in read_json(AREA/'repair_plan.json',[]):
            n,m=row['num'],row['method'];assert re.fullmatch(r'\d{3}',n) and re.fullmatch(r'[a-z0-9_]+',m);key=(n,m)
            if key in seen:continue
            s,t=task(key)
            if t.get('status')=='SUCCESS' and t.get('file') and Path(t['file']).is_file():seen.add(key);done.add(key);continue
            uncertain=t.get('status')=='SUBMISSION_UNCERTAIN' or (not t.get('taskId') and any(a.get('phase')=='sending' for a in s.get('submissions',[])))
            if uncertain:freeze=True;seen.add(key);blocked.add(key);continue
            if t.get('status')=='FAILED':seen.add(key);blocked.add(key);continue
            pending.append(key)
        while ready and not freeze and pending and generation_slots(active,base)<3:
            key=pending.pop(0);n,m=key;p=ROOT/'candidates'/n/m
            for item in ['提示词/'+n+'.txt','补齐生成用/原始帧数.txt','补齐生成用/补齐后帧数.txt','api_key.txt']:
                if not (p/item).is_file():raise SystemExit('候选尚未准备完整：'+str(p/item))
            if (p/'rh_state.lock').exists():
                try:pid=int((p/'rh_state.lock').read_text())
                except ValueError:raise SystemExit('候选锁内容不明。')
                if psutil.pid_exists(pid):raise SystemExit('候选存在活动worker，停止新提交以免重复。')
            shutil.copy2(ROOT/'rh_batch.py',p/'rh_batch.py');(p/'制作分析').mkdir(exist_ok=True)
            cache=AREA/'cos_verified_dns.json'
            if cache.exists():shutil.copy2(cache,p/'制作分析/cos_verified_dns.json')
            env=dict(os.environ);env['RH_SHARED_COOLDOWN']=str(AREA/'repair_submit_cooldown.txt')
            log=open(p/'制作分析/generation.log','a',encoding='utf-8')
            cmd='download' if task(key)[1].get('status')=='SUCCESS' else 'submit'
            args=[sys.executable,'-B','-X','utf8','-u','rh_batch.py',cmd]+([n] if cmd=='submit' else [])
            child=subprocess.Popen(args,cwd=p,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            active[key]=(psutil.Process(child.pid),child,log);seen.add(key)
            print('Started',key,'own_generation_slots',generation_slots(active,base),flush=True)
        snapshot={'base_ready':ready,'own_generation_slots':generation_slots(active,base),'active':[list(k) for k in active],'done':[list(k) for k in done],'needs_diagnosis':[list(k) for k in blocked],'pending':[list(k) for k in pending],'new_submissions_frozen':freeze}
        tmp=AREA/'repair_scheduler_state.tmp';tmp.write_text(json.dumps(snapshot,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(AREA/'repair_scheduler_state.json')
        if ready and not active and (not pending or freeze):break
        time.sleep(10)
    print('Repair workers ended; visual selection and dynamic review remain separate.',flush=True)

if __name__=='__main__':main()
