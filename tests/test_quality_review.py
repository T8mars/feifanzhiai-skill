"""Offline regression checks for omitted roles, wrong props and stale review."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

RUNTIME = Path(__file__).resolve().parents[1] / 'scripts/runtime'
sys.path.insert(0, str(RUNTIME))
import quality_review as q
import assemble as a


class ReviewGate(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for name in ('补齐生成用', '替换用参考图', '完成分段', '制作分析'):
            (self.root / name).mkdir()
        self.rows = [(f'{i:03}.mp4', keep) for i, keep in enumerate(q.KEEP_FRAMES, 1)]
        (self.root / '补齐生成用/原始帧数.txt').write_text(''.join(f'{name}\t{keep}\n' for name, keep in self.rows), encoding='utf-8')
        (self.root / '补齐生成用/补齐后帧数.txt').write_text(''.join(f'{name}\t{keep}\t一号二号\n' for name, keep in self.rows), encoding='utf-8')
        for name in ('一号.png', '二号.png'):
            (self.root / '替换用参考图' / name).write_bytes(name.encode())
        self.selection = {'segments': {}}
        for name, keep in self.rows:
            (self.root / '补齐生成用' / f'{name[:3]} {keep}.mp4').write_bytes(b'source' + name.encode())
            candidate = self.root / '完成分段' / name
            candidate.write_bytes(b'candidate' + name.encode())
            self.selection['segments'][name[:3]] = {'path': str(candidate), 'sha256': q.sha256(candidate), 'status': 'static_passed'}
        self.report = q.prepare(self.root, self.selection)
        # Simulated observations belong only to these isolated fixtures.
        for num, review in self.report['segments'].items():
            keep = review['binding']['keep_frames']
            review.update(reviewer='offline test fixture', reviewed_frame_ranges=[[0, keep - 1]],
                          source_frames_checked=review['review_guidance']['required_source_frames'],
                          checks=dict.fromkeys(q.CHECKS, 'pass'), notes='Simulated complete inspection.')
            review['observations'] = {'source_roles_present': ['source_1', 'source_2'], 'umbrella_operator': 'source_1', 'outer_garment_owner': 'source_2'}
            review['dynamic_review'] = {'status': 'pass', 'reviewer': 'test fixture', 'notes': 'Simulated playback review.'}

    def tearDown(self):
        self.temp.cleanup()

    def errors(self):
        return q.errors_for(self.root, self.rows, self.selection, self.report)

    def test_complete_bound_inspection_passes(self):
        self.assertEqual(self.errors(), [])

    def test_wrap_fix_with_missing_partner_and_wrong_umbrella_is_rejected(self):
        observed = self.report['segments']['013']['observations']
        observed.update(source_roles_present=['source_2'], umbrella_operator='source_2')
        errors = self.errors()
        self.assertTrue(any('013' in e and '角色记录不符' in e for e in errors))
        self.assertTrue(any('013' in e and '撑伞者' in e for e in errors))

    def test_only_clothing_check_does_not_approve_entire_candidate(self):
        self.report['segments']['013']['checks']['subject_count'] = 'pending'
        self.assertTrue(any('subject_count' in e for e in self.errors()))

    def test_wrong_garment_owner_rejected_even_with_two_people(self):
        self.report['segments']['013']['observations']['outer_garment_owner'] = 'source_1'
        self.assertTrue(any('披衣' in e for e in self.errors()))

    def test_new_candidate_cannot_reuse_old_review_even_if_manifest_is_rehashed(self):
        selected = self.selection['segments']['013']
        Path(selected['path']).write_bytes(b'new candidate')
        selected['sha256'] = q.sha256(selected['path'])
        self.assertTrue(any('013' in e and '旧复核失效' in e for e in self.errors()))

    def test_new_source_or_reference_invalidates_review(self):
        (self.root / '补齐生成用/013 84.mp4').write_bytes(b'changed source')
        self.assertTrue(any('013' in e and '旧复核失效' in e for e in self.errors()))
        (self.root / '替换用参考图/一号.png').write_bytes(b'new person')
        self.assertTrue(any('001' in e and '旧复核失效' in e for e in self.errors()))

    def test_sparse_contact_frames_do_not_count_as_all_frames_reviewed(self):
        self.report['segments']['013']['reviewed_frame_ranges'] = [[0, 0], [32, 32], [83, 83]]
        self.assertTrue(any('013' in e and '检查覆盖' in e for e in self.errors()))

    def test_static_sheet_cannot_replace_dynamic_review(self):
        self.report['segments']['013']['dynamic_review']['status'] = 'pending'
        self.assertTrue(any('013' in e and '原速动态' in e for e in self.errors()))

    def test_prepare_preserves_unchanged_records_but_resets_replaced_candidate(self):
        selected = self.selection['segments']['013']
        Path(selected['path']).write_bytes(b'changed')
        selected['sha256'] = q.sha256(selected['path'])
        prepared = q.prepare(self.root, self.selection, self.report)
        self.assertEqual(prepared['segments']['012'], self.report['segments']['012'])
        self.assertTrue(all(v == 'pending' for v in prepared['segments']['013']['checks'].values()))
        self.assertEqual(prepared['segments']['013']['reviewed_frame_ranges'], [])
        self.assertAlmostEqual(prepared['timeline'][12]['start_seconds'], 953 / 24)

    def test_missing_quality_record_blocks_assembler_before_rendering(self):
        (self.root / '制作分析/delivery_selection.json').write_text(json.dumps(self.selection), encoding='utf-8')
        with patch.object(a, 'ROOT', str(self.root)), patch.object(a, 'TABLE', str(self.root / '补齐生成用/原始帧数.txt')), patch.object(sys, 'argv', ['assemble.py']), patch.object(a, 'render_homogeneous_once') as render:
            with self.assertRaisesRegex(SystemExit, '缺少候选联合复核记录'):
                a.main()
            render.assert_not_called()

    def test_frame_table_cannot_omit_a_scene_to_bypass_quality(self):
        table = self.root / '补齐生成用/原始帧数.txt'
        table.write_text(table.read_text(encoding='utf-8').replace('013.mp4\t84\n', ''), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, '19段'):
            q.validate_final(self.root, self.rows[:12] + self.rows[13:], self.selection)


if __name__ == '__main__':
    unittest.main()
