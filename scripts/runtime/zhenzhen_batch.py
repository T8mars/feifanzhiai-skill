"""Resumable MiniMax H3 charswap REST runner. Credentials never enter snapshots.

quote: free uploads + estimate; run: at most 3 generation tasks in this run.
All accepted tasks (including failures and discarded candidates) remain in ledger.
"""
import argparse
import concurrent.futures as futures
import hashlib
import json
import mimetypes
import os
import re
from pathlib import Path
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from decimal import Decimal

ROOT = Path(__file__).resolve().parent
STATE = ROOT / 'zhenzhen_state.json'
LOCK = ROOT / 'zhenzhen_state.lock'
PRIVATE = ROOT / 'private'
SUCCESS = {'SUCCESS', 'SUCCEEDED', 'COMPLETED'}
FAILED = {'FAILURE', 'FAILED', 'CANCELLED', 'CANCELED'}


def read(path, default=None):
    return json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else default


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(tmp, path)


def sha(path):
    with open(path, 'rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


class ApiError(Exception):
    def __init__(self, code, body, retry_after=60):
        self.code, self.body, self.retry_after = code, body, retry_after
        super().__init__(f'HTTP {code}: {body[:600]}')


class Client:
    def __init__(self):
        self.cfg = read(ROOT / 'provider.json')
        if self.cfg['provider'] != 'zhenzhen_ai':
            raise ValueError('This runner requires explicitly selected zhenzhen_ai')
        self.key = Path(self.cfg['api_key_file']).read_text(encoding='utf-8-sig').strip()
        if not self.key:
            raise ValueError('Empty private key file')

    def request(self, method, path, payload=None, body=None, content_type=None):
        headers = {'Authorization': 'Bearer ' + self.key,
                   'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
            content_type = 'application/json'
        if content_type:
            headers['Content-Type'] = content_type
        req = urllib.request.Request(self.cfg['base_url'].rstrip('/') + path,
                                     data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            text = e.read().decode('utf-8', errors='replace').replace(self.key, '[REDACTED]')
            wait = e.headers.get('Retry-After', '60')
            raise ApiError(e.code, text, int(wait) if wait.isdigit() else 60) from None

    def upload(self, path, state):
        digest = sha(path)
        cached = state.setdefault('uploads', {}).get(digest)
        if cached and cached['expires_at'] > time.time() + 1800:
            return cached['url']
        boundary = '----Codex' + uuid.uuid4().hex
        # Stable ASCII multipart filename avoids Windows/CJK parser differences.
        name = digest[:16] + path.suffix.lower()
        head = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
                f'filename="{name}"\r\nContent-Type: '
                f'{mimetypes.guess_type(name)[0] or "application/octet-stream"}\r\n\r\n').encode()
        body = head + path.read_bytes() + f'\r\n--{boundary}--\r\n'.encode()
        result = self.request('POST', '/v1/files/upload', body=body,
                              content_type='multipart/form-data; boundary=' + boundary)
        data = result.get('data', result)
        if not isinstance(data, dict) or not data.get('url'):
            raise ValueError('Upload response lacks URL: ' + str(result)[:250])
        state['uploads'][digest] = {'url': data['url'], 'sha256': digest,
                                    'expires_at': time.time() + int(data.get('expires_in', 86400))}
        save(STATE, state)
        return data['url']


def table():
    rows = {}
    for line in (ROOT / '补齐生成用/补齐后帧数.txt').read_text(encoding='utf-8-sig').splitlines():
        parts = line.split('\t')
        if len(parts) >= 3 and parts[0].endswith('.mp4'):
            rows[parts[0][:3]] = (int(parts[1]), parts[2].strip())
    return rows


def job_root(job):
    if not re.fullmatch(r'\d{3}(?:/[A-Za-z0-9_-]+)?', job) or job[:3] not in table():
        raise ValueError('Job must be a source shot or shot/safe_candidate_name')
    return ROOT if '/' not in job else ROOT / 'candidates' / job


def probe(path):
    exe = ROOT / 'ffmpeg/ffprobe.exe'
    result = subprocess.run([str(exe), '-v', 'error', '-count_frames', '-show_streams',
                             '-of', 'json', str(path)], capture_output=True, check=True)
    streams = json.loads(result.stdout)['streams']
    video = next(s for s in streams if s['codec_type'] == 'video')
    from fractions import Fraction
    fps = Fraction(video['avg_frame_rate'])
    frames = int(video['nb_read_frames'])
    return {'frames': frames, 'fps': str(fps), 'seconds': float(frames / fps),
            'width': video['width'], 'height': video['height'],
            'audio': any(s['codec_type'] == 'audio' for s in streams)}


def extend_short_motion(video, info):
    """Pad only the derivative tail; original kept frames and source are read-only."""
    if info['seconds'] >= 2:
        return video, info, None
    target = 56  # smallest 22+17n >= 48 (2s at 24fps)
    digest = sha(video)
    folder = PRIVATE / 'motion_inputs' / digest
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / (video.stem[:3] + '_min2s_56.mp4')
    if not dest.exists():
        part = dest.with_suffix('.part.mp4')
        cmd = [str(ROOT/'ffmpeg/ffmpeg.exe'), '-hide_banner', '-loglevel', 'error', '-y',
               '-i', str(video), '-map', '0:v:0', '-map', '0:a:0',
               '-vf', f'tpad=stop_mode=clone:stop={target-info["frames"]},trim=end_frame={target},setpts=PTS-STARTPTS',
               '-af', 'apad,atrim=end=2.333333333333333', '-c:v', 'libx264', '-crf', '0',
               '-pix_fmt', 'yuv420p', '-r', '24', '-c:a', 'aac', '-b:a', '320k',
               '-movflags', '+faststart', str(part)]
        subprocess.run(cmd, capture_output=True, check=True)
        check = probe(part)
        if check['frames'] != target or not check['audio'] or check['fps'] != '24':
            raise ValueError('Invalid short-motion derivative')
        os.replace(part, dest)
    result = probe(dest)
    return dest, result, {'method': 'tail_only_min2s_lossless_video',
                          'parent_sha256': digest, 'parent_frames': info['frames'],
                          'derived_frames': target, 'preserve_kept_timing': True}


def prepare(client, state, job):
    num = job[:3]
    frames, cast = table()[num]
    base = job_root(job)
    override = read(base / 'candidate_config.json', {})
    if 'frames' in override:
        frames = int(override['frames'])
    if frames < 22 or (frames - 22) % 17 or frames > 240:
        raise ValueError('frames must be 22+17n and input/output <=10 seconds')
    candidates = list((base / '补齐生成用').glob(num + ' *.mp4'))
    video = candidates[0] if candidates else next((ROOT / '补齐生成用').glob(num + ' *.mp4'))
    info = probe(video)
    if info['frames'] != frames or info['fps'] != '24' or not info['audio']:
        raise ValueError('Motion input requires exact source frames, 24fps and original audio')
    video, info, derivation = extend_short_motion(video, info)
    frames = info['frames']
    if video.stat().st_size > 50 * 1024**2:
        raise ValueError('Video exceeds 50 MiB')
    names = {'一号二号': ['一号.png', '二号.png'], '一号': ['一号.png'], '二号': ['二号.png']}[cast]
    refs = [ROOT / '替换用参考图' / name for name in names]
    if any(p.stat().st_size > 10 * 1024**2 for p in refs):
        raise ValueError('Reference exceeds 10 MiB')
    prompt_path = base / '提示词' / (num + '.txt')
    prompt = prompt_path.read_text(encoding='utf-8-sig')
    if not prompt.startswith('subject_definitions:') or len(prompt) > 20480:
        raise ValueError('Invalid six-part prompt or prompt >20480 characters')
    headers = ['subject_definitions:', 'summary:', 'retention_analysis:',
               'detailed_description:', 'overall_soundscape:', 'non_diegetic_music:']
    positions = [prompt.find(s) for s in headers]
    if min(positions) < 0 or positions != sorted(positions):
        raise ValueError('Missing or unordered six-part prompt sections')
    pictures = re.findall(r'<Picture (\d+)>', prompt)
    if pictures != [str(i + 1) for i in range(len(refs))]:
        raise ValueError('Reference order/count does not match this shot cast')
    metadata = {'video_url': [client.upload(video, state)], 'frames': frames,
                'resolution': client.cfg['resolution'], 'ratio': client.cfg['ratio']}
    if 'seed' in override:
        metadata['seed'] = int(override['seed'])
    payload = {'model': client.cfg['model'], 'prompt': prompt,
               'images': [client.upload(p, state) for p in refs], 'metadata': metadata}
    quote = client.request('POST', '/v1/video/generations/estimate', payload)
    record = {'job': job, 'num': num, 'frames_requested': frames,
              'source_sha256': sha(video), 'reference_sha256': [sha(p) for p in refs],
              'prompt_sha256': sha(prompt_path), 'estimate': quote,
              'phase': 'PREPARED', 'prepared_at': time.time()}
    if derivation:
        record['motion_derivation'] = derivation
    save(PRIVATE / (job.replace('/', '_') + '_request.json'), payload)
    state.setdefault('jobs', {})[job] = record
    save(STATE, state)
    return payload, record


def data_of(response):
    d = response.get('data')
    return d if isinstance(d, dict) else response


def submit(client, state, job):
    try:
        payload, record = prepare(client, state, job)
    except ApiError as e:
        if e.code != 429:
            raise
        # Free upload/estimate throttling: no paid POST has happened.
        state.setdefault('jobs', {}).setdefault(job, {'job': job, 'num': job[:3]}).update(
            phase='RATE_LIMITED', retry_at=time.time() + max(60, e.retry_after),
            wait_reason='free preparation rate limit; no paid submit')
        save(STATE, state)
        print('WAIT', job, 'free upload/estimate rate limit', flush=True)
        return
    # Persist intent before POST. A network error may mean the server accepted it.
    record['phase'] = 'SENDING'
    record['sent_at'] = time.time()
    save(STATE, state)
    try:
        result = client.request('POST', '/v1/video/generations', payload)
    except ApiError as e:
        if e.code == 429:
            record.update(phase='RATE_LIMITED', retry_at=time.time() + max(60, e.retry_after))
            save(STATE, state)
            return
        record.update(phase='REJECTED' if 400 <= e.code < 500 else 'UNCERTAIN', error=str(e))
        save(STATE, state)
        raise
    except Exception as e:
        record.update(phase='UNCERTAIN', error=type(e).__name__)
        save(STATE, state)
        raise RuntimeError('Ambiguous submit; reconcile provider task records before resubmitting') from None
    save(PRIVATE / (job.replace('/', '_') + '_submit.json'), result)
    d = data_of(result)
    task_id = d.get('task_id') or d.get('id') or result.get('task_id') or result.get('id')
    if not task_id:
        record.update(phase='UNCERTAIN', error='Missing task ID; response retained privately')
        save(STATE, state)
        raise RuntimeError(record['error'])
    record.update(phase='ACCEPTED', task_id=str(task_id), accepted_at=time.time(),
                  status=str(d.get('status', 'QUEUED')).upper())
    save(STATE, state)
    print('ACCEPTED', job, task_id, 'frames', record['frames_requested'], flush=True)


def output_url(d):
    # Only documented output locations; never walk input metadata.video_url.
    for value in [d.get('result_url'), d.get('output_url')]:
        if isinstance(value, str) and value.startswith('https://'):
            return value
    content = (d.get('data') or {}).get('content', {})
    value = content.get('video_url') or content.get('video_urls')
    if isinstance(value, list):
        value = value[0] if value else None
    if isinstance(value, str) and value.startswith('https://'):
        return value
    value = (d.get('metadata') or {}).get('url')
    return value if isinstance(value, str) and value.startswith('https://') else None


def refresh(client, state):
    for job, record in state.get('jobs', {}).items():
        if not record.get('task_id') or record.get('phase') in {'PREPARED', 'REJECTED'}:
            continue
        if (record.get('downloaded') or record.get('status') in FAILED) and record.get('usage') is not None:
            continue
        try:
            result = client.request('GET', '/v1/video/generations/' + record['task_id'])
            save(PRIVATE / (job.replace('/', '_') + '_query.json'), result)
            d = data_of(result)
            status = str(d.get('status', record.get('status', 'UNKNOWN'))).upper()
            if status != record.get('status'):
                print('STATUS', job, status, flush=True)
            record['status'] = status
            record['queried_at'] = time.time()
            record['provider_timing'] = {k: d.get(k) for k in ['submit_time', 'start_time', 'finish_time'] if d.get(k)}
            if status in SUCCESS | FAILED:
                record['phase'] = 'TERMINAL'
                record.setdefault('finished_at', time.time())
                usage = d.get('usage', result.get('usage'))
                if usage is not None:
                    record['usage'] = usage
                if status in SUCCESS:
                    url = output_url(d)
                    if url:
                        record['output_url'] = url
                else:
                    record['failure'] = d.get('fail_reason') or d.get('error') or d.get('message')
            record.pop('query_error', None)
        except Exception as e:
            record['query_error'] = str(e).replace(client.key, '[REDACTED]')[:500]
        save(STATE, state)


def download_one(job, record):
    dest = job_root(job) / '完成分段' / (record['num'] + '.mp4')
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix('.part.mp4')
    # Result CDN rejects Python's default UA. Public media requests carry no key.
    req = urllib.request.Request(record['output_url'], headers={'User-Agent': 'Mozilla/5.0', 'Accept': '*/*'})
    try:
        with urllib.request.urlopen(req, timeout=30) as response, open(part, 'wb') as out:
            expected = response.headers.get('Content-Length')
            size = 0
            deadline = time.monotonic() + 180
            while True:
                if time.monotonic() > deadline:
                    raise TimeoutError('Media download exceeded 180 seconds')
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                size += len(chunk)
            if expected is not None and size != int(expected):
                raise ValueError('Incomplete media Content-Length')
    except Exception:
        host = urllib.parse.urlsplit(record['output_url']).hostname or ''
        if not host.endswith('.myqcloud.com'):
            raise
        from rh_batch import retrieve_result
        retrieve_result(record['output_url'], str(part))
    info = probe(part)
    if info['fps'] != '24' or info['frames'] < record['frames_requested']:
        raise ValueError('Output frame deficit/rate mismatch; retained .part for diagnosis')
    os.replace(part, dest)
    return {'downloaded': True, 'path': str(dest.relative_to(ROOT)),
            'sha256': sha(dest), 'media': info, 'downloaded_at': time.time()}


def billing(state):
    rows = []
    totals = {}
    seconds = Decimal(0)
    pending = []
    media_pending = []
    seen_ids = set()
    for job, r in state.get('jobs', {}).items():
        if not r.get('task_id'):
            continue
        if r['task_id'] in seen_ids:
            continue
        seen_ids.add(r['task_id'])
        row = {k: r.get(k) for k in ['task_id', 'status', 'frames_requested', 'media', 'usage', 'sha256']}
        row['job'] = job
        usage = r.get('usage')
        if isinstance(usage, dict) and usage.get('amount') is not None and usage.get('currency'):
            currency = usage['currency']
            totals[currency] = totals.get(currency, Decimal(0)) + Decimal(str(usage['amount']))
        else:
            pending.append(job)
        if r.get('media'):
            from fractions import Fraction
            seconds += Decimal(r['media']['frames']) / Decimal(str(float(Fraction(r['media']['fps']))))
        elif r.get('status') in SUCCESS:
            media_pending.append(job)
        rows.append(row)
    result = {'tasks': rows, 'actual_total_by_currency': {k: str(v) for k, v in totals.items()},
              'actual_generated_seconds_including_all_candidates': str(seconds),
              'settlement_pending': pending,
              'successful_outputs_not_measured': media_pending,
              'actual_cost_per_generated_second': {k: str(v / seconds) for k, v in totals.items()} if seconds and not pending and not media_pending else None,
              'final_kept_seconds': '59.0416666666666667',
              'note': 'Estimates and wallet differences are not actual settled usage.'}
    save(ROOT / '制作分析/zhenzhen_cost_ledger.json', result)
    return result


def run(client, state, jobs):
    active_downloads = {}
    with futures.ThreadPoolExecutor(max_workers=3) as pool:
        last_message = 0
        while True:
            live = read(ROOT / '制作分析/zhenzhen_queue.json', {})
            targets = list(dict.fromkeys(jobs + live.get('jobs', []) +
                           [j for j, r in state.get('jobs', {}).items() if r.get('task_id')]))
            if any(r.get('phase') in {'SENDING', 'UNCERTAIN'} for r in state.get('jobs', {}).values()):
                raise RuntimeError('Uncertain submission exists. Reconcile before another paid POST.')
            refresh(client, state)
            for job, future in list(active_downloads.items()):
                if future.done():
                    try:
                        state['jobs'][job].update(future.result())
                        state['jobs'][job].pop('download_error', None)
                        state['jobs'][job].pop('download_retry_at', None)
                        print('DOWNLOADED', job, flush=True)
                    except Exception as e:
                        state['jobs'][job]['download_error'] = str(e).replace(client.key, '[REDACTED]')[:500]
                        state['jobs'][job]['download_retry_at'] = time.time() + 60
                    del active_downloads[job]
                    save(STATE, state)
            for job, r in state.get('jobs', {}).items():
                if (r.get('status') in SUCCESS and r.get('output_url') and not r.get('downloaded')
                        and job not in active_downloads and r.get('download_retry_at', 0) < time.time()):
                    active_downloads[job] = pool.submit(download_one, job, dict(r))
            active = sum(bool(r.get('task_id')) and r.get('status') not in SUCCESS | FAILED
                         for r in state.get('jobs', {}).values())
            for job in targets:
                r = state.get('jobs', {}).get(job, {})
                if r.get('task_id') or r.get('phase') == 'REJECTED' or r.get('retry_at', 0) > time.time():
                    continue
                if active >= min(3, client.cfg.get('max_concurrency', 3)):
                    break
                submit(client, state, job)
                if state['jobs'][job].get('task_id'):
                    active += 1
                elif state['jobs'][job].get('phase') == 'RATE_LIMITED':
                    break
            billing(state)
            if all((state.get('jobs', {}).get(j, {}).get('downloaded') or
                    state.get('jobs', {}).get(j, {}).get('status') in FAILED)
                   and state.get('jobs', {}).get(j, {}).get('usage') is not None for j in targets):
                break
            if time.time() - last_message > 60:
                print('PROGRESS', sum(bool(r.get('downloaded')) for r in state['jobs'].values()),
                      'downloaded;', active, 'generating', flush=True)
                last_message = time.time()
            time.sleep(10)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['quote', 'run', 'status', 'ledger'])
    parser.add_argument('jobs', nargs='*')
    args = parser.parse_args()
    import psutil
    try:
        fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        old = read(LOCK, {})
        if not old or psutil.pid_exists(old.get('pid', -1)):
            raise SystemExit('Another central runner owns this run (or lock is being written)')
        LOCK.unlink()
        fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    with os.fdopen(fd, 'w') as f:
        json.dump({'pid': os.getpid()}, f)
    try:
        client = Client()
        state = read(STATE, {'jobs': {}, 'uploads': {}})
        if args.command == 'quote':
            for job in args.jobs:
                if state['jobs'].get(job, {}).get('task_id'):
                    print('Already accepted', job)
                    continue
                _, r = prepare(client, state, job)
                print('QUOTE', job, json.dumps(r['estimate'], ensure_ascii=False), flush=True)
        elif args.command == 'run':
            run(client, state, args.jobs or list(table()))
        elif args.command == 'status':
            refresh(client, state)
            print({j: r.get('status', r.get('phase')) for j, r in state['jobs'].items()})
        else:
            b = billing(state)
            print({k: v for k, v in b.items() if k != 'tasks'})
    finally:
        LOCK.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
