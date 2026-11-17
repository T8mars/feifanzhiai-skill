"""Offline review records bound to the exact candidate, source and references.

This validates recorded visual inspection; it does not recognise people or props.
Preparing a record never marks a visual check as passed and never submits jobs.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path


CHECKS = (
    'identity', 'subject_count', 'prop_owner', 'action_and_timing',
    'clothing_transfer', 'anatomy_and_occlusion', 'artifacts', 'adjacent_continuity',
)
REVIEW_FILE = '制作分析/candidate_reviews.json'
KEEP_FRAMES = (74, 87, 78, 51, 151, 121, 37, 34, 54, 53, 115, 98, 84, 51, 61, 64, 72, 86, 46)


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def within(root, path):
    root = Path(root).resolve()
    path = Path(path)
    path = (root / path).resolve() if not path.is_absolute() else path.resolve()
    if not path.is_relative_to(root):
        raise ValueError('文件必须位于本次工作副本内：' + str(path))
    return path


def rows_for(root):
    rows = []
    for line in (Path(root) / '补齐生成用/原始帧数.txt').read_text(encoding='utf-8-sig').splitlines():
        p = line.split()
        if len(p) >= 2 and p[0].endswith('.mp4') and p[0][:3].isdigit():
            rows.append((p[0], int(p[1])))
    expected = [(f'{i:03}.mp4', keep) for i, keep in enumerate(KEEP_FRAMES, 1)]
    if rows != expected:
        raise ValueError('本技能要求固定19段、1417保留帧；请检查原始帧数表。')
    return rows


def expected_roles(root):
    roles = {}
    for line in (Path(root) / '补齐生成用/补齐后帧数.txt').read_text(encoding='utf-8-sig').splitlines():
        p = line.split()
        if len(p) >= 3 and p[0].endswith('.mp4'):
            roles[p[0][:3]] = [r for token, r in [('一号', 'source_1'), ('二号', 'source_2')] if token in p[2]]
    return roles


def binding(root, num, keep, selected):
    root = Path(root)
    candidate = within(root, selected['path'])
    sources = list((root / '补齐生成用').glob(num + ' *.mp4'))
    if len(sources) != 1:
        raise ValueError(num + ' 原运动视频不唯一。')
    refs = {name: sha256(root / '替换用参考图' / name) for name in ('一号.png', '二号.png')}
    return {
        'candidate_sha256': sha256(candidate),
        'source_sha256': sha256(sources[0]),
        'reference_sha256': refs,
        'keep_frames': keep,
    }


def prepare(root, selection, previous=None):
    root = Path(root)
    old = (previous or {}).get('segments', {})
    roles = expected_roles(root)
    result = {'schema_version': 1, 'purpose': 'Recorded visual inspection, not automatic semantic detection', 'segments': {}}
    timeline = []
    start = 0
    for name, keep in rows_for(root):
        num = name[:3]
        timeline.append({'num': num, 'start_frame': start, 'end_frame_exclusive': start + keep,
                         'start_seconds': start / 24, 'end_seconds': (start + keep) / 24})
        start += keep
        selected = selection.get('segments', {}).get(num)
        if not selected:
            continue
        b = binding(root, num, keep, selected)
        if old.get(num, {}).get('binding') == b:
            result['segments'][num] = copy.deepcopy(old[num])
            continue
        keyframes = [0, 18, 32, 50, 75, keep - 1] if num == '013' else [0, keep - 1]
        result['segments'][num] = {
            'binding': b, 'reviewer': '', 'reviewed_frame_ranges': [],
            'source_frames_checked': [], 'checks': {key: 'pending' for key in CHECKS},
            'observations': {'source_roles_present': [], 'umbrella_operator': None, 'outer_garment_owner': None},
            'notes': '', 'dynamic_review': {'status': 'pending', 'reviewer': '', 'notes': ''},
            'review_guidance': {'expected_source_roles': roles.get(num), 'required_source_frames': keyframes,
                                '013_contract': {'umbrella_operator': 'source_1', 'outer_garment_owner': 'source_2'} if num == '013' else None},
        }
    result['timeline'] = timeline
    return result


def full_coverage(ranges, keep):
    if not isinstance(ranges, list) or not ranges:
        return False
    covered = set()
    for interval in ranges:
        if not isinstance(interval, list) or len(interval) != 2:
            return False
        a, b = interval
        if type(a) is not int or type(b) is not int or not 0 <= a <= b < keep:
            return False
        covered.update(range(a, b + 1))
    return len(covered) == keep


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def errors_for(root, rows, selection, report):
    """Reject incomplete or stale inspection and the known 013 role regression."""
    errors = []
    if report.get('schema_version') != 1:
        errors.append('复核记录schema_version必须为1。')
    roles = expected_roles(root)
    for name, keep in rows:
        num = name[:3]
        selected = selection.get('segments', {}).get(num)
        review = report.get('segments', {}).get(num)
        if not selected or not review:
            errors.append(num + ' 缺少选片或联合复核记录。')
            continue
        try:
            current = binding(root, num, keep, selected)
        except (OSError, ValueError, KeyError) as e:
            errors.append(num + ' 无法验证复核绑定：' + str(e))
            continue
        if review.get('binding') != current:
            errors.append(num + ' 候选、运动源或参考图已变化，旧复核失效。')
        if selected.get('sha256') != current['candidate_sha256']:
            errors.append(num + ' 选片哈希缺失或不一致。')
        if selected.get('status') != 'static_passed':
            errors.append(num + ' 选片尚未通过静态检查。')
        if not full_coverage(review.get('reviewed_frame_ranges'), keep):
            errors.append(num + ' 未记录全部保留帧的检查覆盖。')
        failed = [key for key in CHECKS if review.get('checks', {}).get(key) != 'pass']
        if failed:
            errors.append(num + ' 联合复核未通过：' + ', '.join(failed))
        if not nonempty(review.get('reviewer')) or not nonempty(review.get('notes')):
            errors.append(num + ' 缺少复核者或实际观察记录。')
        checked = review.get('source_frames_checked')
        required = {0, keep - 1} | ({18, 32, 50, 75} if num == '013' else set())
        if not isinstance(checked, list) or any(type(i) is not int for i in checked) or not required.issubset(checked):
            errors.append(num + ' 缺少原片关键帧对照。')
        observed = review.get('observations', {})
        present = observed.get('source_roles_present')
        expected = roles.get(num)
        if not expected or not isinstance(present, list) or any(not isinstance(r, str) for r in present) or sorted(present) != sorted(expected):
            errors.append(num + ' 两位/单人源动作角色记录不符：预期 ' + str(expected))
        if num == '013':
            if observed.get('umbrella_operator') != 'source_1':
                errors.append('013 撑伞者必须是一号源动作角色。')
            if observed.get('outer_garment_owner') != 'source_2':
                errors.append('013 披衣应留在二号源动作角色。')
        dynamic = review.get('dynamic_review', {})
        if dynamic.get('status') != 'pass' or not nonempty(dynamic.get('reviewer')) or not nonempty(dynamic.get('notes')):
            errors.append(num + ' 原速动态复核未完成。')
    return errors


def validate_final(root, rows, selection):
    if rows != rows_for(root):
        raise ValueError('合片镜头与固定帧数表不一致。')
    path = Path(root) / REVIEW_FILE
    if not path.is_file():
        raise ValueError('缺少候选联合复核记录。先运行 quality_review.py prepare --project <工作副本>，实际检查后填写记录。')
    errors = errors_for(root, rows, selection, read_json(path))
    if errors:
        raise ValueError('候选联合复核未通过：\n' + '\n'.join(errors))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'check'])
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--selection', default='制作分析/delivery_selection.json')
    parser.add_argument('--output', default=REVIEW_FILE, help='复核记录路径；prepare合并同哈希已有记录，其余重置待检查。')
    args = parser.parse_args()
    root = args.project.resolve()
    selection_path = within(root, args.selection)
    selection = read_json(selection_path)
    report_path = within(root, args.output)
    if report_path == selection_path:
        raise SystemExit('复核记录不能覆盖选片清单。')
    if args.command == 'prepare':
        old = read_json(report_path) if report_path.exists() else None
        report = prepare(root, selection, old)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = report_path.with_suffix('.tmp')
        tmp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        tmp.replace(report_path)
        print('已准备待检查记录：' + str(report_path) + '；未自动通过任何视觉检查。')
    else:
        errors = errors_for(root, rows_for(root), selection, read_json(report_path))
        print(json.dumps({'passed': not errors, 'errors': errors}, ensure_ascii=False, indent=2))
        raise SystemExit(1 if errors else 0)


if __name__ == '__main__':
    main()
