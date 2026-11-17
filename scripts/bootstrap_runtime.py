"""Install reviewed helpers into a work copy. Never copy private state or keys."""
from pathlib import Path
import argparse,datetime,hashlib,json,shutil,os

SKILL=Path(__file__).resolve().parent.parent
ORIGINAL=Path('D:/全自动生成非凡之爱').resolve()

def main():
    p=argparse.ArgumentParser();p.add_argument('--project',required=True,type=Path);p.add_argument('--apply',action='store_true');p.add_argument('--set-default-audio',action='store_true');p.add_argument('--provider',choices=['runninghub','zhenzhen_ai']);p.add_argument('--key-file',type=Path);args=p.parse_args();root=args.project.resolve()
    if root==ORIGINAL or root==SKILL or ORIGINAL in root.parents:raise SystemExit('请使用独立工作副本，不能改写D盘原包。')
    for name in ['LICENSE.txt','补齐生成用/原始帧数.txt','补齐生成用/补齐后帧数.txt']:
        if not (root/name).is_file():raise SystemExit('工作副本缺少：'+name)
    import psutil
    for lock in [root/'rh_state.lock',root/'zhenzhen_state.lock',root/'repair_scheduler.lock',root/'制作分析/repair_scheduler.lock']:
        if lock.exists():
            try:
                value=lock.read_text();pid=int(json.loads(value)['pid']) if value.lstrip().startswith('{') else int(value)
            except (ValueError,KeyError,TypeError):raise SystemExit('锁文件内容不明，先检查：'+str(lock))
            if psutil.pid_exists(pid):raise SystemExit('工作副本有活动进程，停止升级其运行文件。')
    old_provider=json.loads((root/'provider.json').read_text(encoding='utf-8')) if (root/'provider.json').exists() else {}
    if args.provider and old_provider.get('provider') not in [None,args.provider]:raise SystemExit('更换渠道请建立新工作副本，避免混用任务与费用。')
    if args.provider=='zhenzhen_ai' and not (args.key_file or old_provider.get('api_key_file')):raise SystemExit('贞贞AI请用--key-file引用本机私有文件，不把Key写进参数。')
    names=['rh_batch.py','zhenzhen_batch.py','assemble.py','audio_delivery.py','inspect_media.py','repair_scheduler.py','quality_review.py']
    plan={'project':str(root),'runtime_files':names,'provider':args.provider or old_provider.get('provider'),'install_default_music':not (root/'delivery_audio.json').exists() or args.set_default_audio,'apply':args.apply}
    print(json.dumps(plan,ensure_ascii=False),flush=True)
    if not args.apply:return
    # Public distributions intentionally omit third-party music. Fail before
    # changing runtime or provider files, and preserve already configured audio.
    for name in names:
        if not (SKILL/'scripts/runtime'/name).is_file():raise SystemExit('技能缺少运行文件：'+name)
    if plan['install_default_music']:
        defaults=json.loads((SKILL/'meta.json').read_text(encoding='utf-8'))['default_audio']
        if not (SKILL/defaults['asset']).is_file():
            raise SystemExit('公开版不附带音乐。请先用scripts/prepare_audio.py --project <工作副本> --input <本机音乐> --output <工作副本>/配乐/已对齐.wav --set-default配置交付音乐，再安装运行文件；已有音乐时不要加--set-default-audio。')
    backup=root/'制作分析/runtime_backup'/datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f');backup.mkdir(parents=True)
    for name in names:
        src=SKILL/'scripts/runtime'/name
        if not src.is_file():raise SystemExit('技能缺少运行文件：'+name)
        dest=root/name
        if dest.exists():shutil.copy2(dest,backup/name)
        shutil.copy2(src,dest)
    if args.provider:
        manifest=root/'provider.json'
        if manifest.exists():shutil.copy2(manifest,backup/manifest.name)
        cfg=dict(old_provider,provider=args.provider,max_concurrency=3)
        if args.provider=='zhenzhen_ai':
            cfg.update(base_url='https://api.seedance.nz',model='minimax-h3-comfyui-charswap',resolution='1088p',ratio='16:9',output_fps=24,frames_instead_of_seconds=True)
            if args.key_file:cfg['api_key_file']=str(args.key_file.resolve())
        manifest.write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding='utf-8')
    visual=root/'delivery_visual.json'
    if not visual.exists():visual.write_text(json.dumps({'shot019_color':'unreviewed','reason':'Inspect current character references before selecting selective colour or monochrome.'},ensure_ascii=False,indent=2),encoding='utf-8')
    if plan['install_default_music']:
        defaults=json.loads((SKILL/'meta.json').read_text(encoding='utf-8'))['default_audio']
        source=SKILL/defaults['asset'];dest=root/'配乐'/source.name;dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists() and dest.read_bytes()!=source.read_bytes():shutil.copy2(dest,backup/'previous_default_music.wav')
        shutil.copy2(source,dest)
        manifest=root/'delivery_audio.json'
        if manifest.exists():shutil.copy2(manifest,backup/manifest.name)
        cfg={'path':'配乐/'+source.name,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'start_seconds':0,'duration_policy':'already aligned1417frames24fps; preserve_video_timing','source':'user-provided aligned default music,2026-11-17','alignment':defaults['alignment']}
        manifest.write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding='utf-8')
    receipt=root/'制作分析/runtime_install.json'
    if receipt.exists():shutil.copy2(receipt,backup/receipt.name)
    receipt.write_text(json.dumps({
        'skill_version':json.loads((SKILL/'meta.json').read_text(encoding='utf-8'))['skill_version'],
        'runtime_sha256':{name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in names},
        'backup':str(backup),'network_or_generation_submitted':False
    },ensure_ascii=False,indent=2),encoding='utf-8')
    print('Installed reviewed runtime and preserved prior scripts; no network or generation submitted.',flush=True)

if __name__=='__main__':main()
