"""Public release contains no music or credentials; install stays offline."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/bootstrap_runtime.py'
spec = importlib.util.spec_from_file_location('public_bootstrap', SCRIPT)
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)


class PublicBootstrap(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.skill, self.root = base / 'skill', base / 'work'
        (self.skill / 'scripts/runtime').mkdir(parents=True)
        (self.root / '补齐生成用').mkdir(parents=True)
        for name in ('LICENSE.txt', '补齐生成用/原始帧数.txt', '补齐生成用/补齐后帧数.txt'):
            (self.root / name).write_text('fixture', encoding='utf-8')
        self.names = ['rh_batch.py', 'zhenzhen_batch.py', 'assemble.py', 'audio_delivery.py', 'inspect_media.py', 'repair_scheduler.py', 'quality_review.py']
        for name in self.names:
            (self.skill / 'scripts/runtime' / name).write_text('# public fixture\n', encoding='utf-8')
        (self.skill / 'meta.json').write_text(json.dumps({'skill_version': '3.0.1', 'default_audio': {'asset': 'assets/not-bundled.wav'}}), encoding='utf-8')

    def tearDown(self):
        self.tmp.cleanup()

    def install(self):
        with patch.object(b, 'SKILL', self.skill), patch.object(sys, 'argv', ['bootstrap_runtime.py', '--project', str(self.root), '--apply']), contextlib.redirect_stdout(io.StringIO()):
            b.main()

    def test_missing_public_audio_fails_before_any_project_mutation(self):
        before = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        with self.assertRaisesRegex(SystemExit, '公开版不附带音乐'):
            self.install()
        after = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before, after)

    def test_existing_local_music_and_task_state_survive_public_install(self):
        preserved = {'delivery_audio.json': b'{"path":"local.wav"}', 'rh_state.json': b'{"tasks":{}}', 'api_key.txt': b'offline-test-placeholder', 'local.wav': b'local audio fixture'}
        for name, data in preserved.items():
            (self.root / name).write_bytes(data)
        self.install()
        self.assertTrue(all((self.root / name).is_file() for name in self.names))
        for name, data in preserved.items():
            self.assertEqual((self.root / name).read_bytes(), data)
        receipt = json.loads((self.root / '制作分析/runtime_install.json').read_text(encoding='utf-8'))
        self.assertEqual(receipt['skill_version'], '3.0.1')
        self.assertFalse(receipt['network_or_generation_submitted'])


if __name__ == '__main__':
    unittest.main()
