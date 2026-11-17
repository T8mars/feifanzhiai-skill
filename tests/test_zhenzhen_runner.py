"""Offline financial/resume invariants. Never reads credentials or spends."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts/runtime'))
import zhenzhen_batch as z


class Invariants(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.ctx = patch.object(z, 'ROOT', self.root)
        self.ctx.start()

    def tearDown(self):
        self.ctx.stop()
        self.tmp.cleanup()

    def test_cost_denominator_keeps_rejected_candidates_and_padding(self):
        state = {'jobs': {
            '001': {'task_id': 'a', 'status': 'SUCCESS', 'usage': {'amount': 4, 'currency': 'CNY'}, 'media': {'frames': 90, 'fps': '24'}},
            '001/repair': {'task_id': 'b', 'status': 'SUCCESS', 'usage': {'amount': 3, 'currency': 'CNY'}, 'media': {'frames': 78, 'fps': '24'}},
            '002/failure': {'task_id': 'c', 'status': 'FAILURE', 'usage': {'amount': 0, 'currency': 'CNY'}}}}
        report = z.billing(state)
        self.assertEqual(report['actual_total_by_currency'], {'CNY': '7'})
        self.assertEqual(float(report['actual_generated_seconds_including_all_candidates']), 7)
        self.assertEqual(float(report['actual_cost_per_generated_second']['CNY']), 1)
        self.assertEqual(len(report['tasks']), 3)

    def test_no_rate_when_settled_output_not_downloaded(self):
        report = z.billing({'jobs': {'001': {'task_id': 'a', 'status': 'SUCCESS', 'usage': {'amount': 2, 'currency': 'CNY'}}}})
        self.assertIsNone(report['actual_cost_per_generated_second'])
        self.assertEqual(report['successful_outputs_not_measured'], ['001'])

    def test_estimate_and_null_usage_never_become_actual_zero(self):
        report = z.billing({'jobs': {'001': {'task_id': 'a', 'status': 'SUCCESS', 'estimate': {'amount': 2}, 'media': {'frames': 90, 'fps': '24'}}}})
        self.assertEqual(report['actual_total_by_currency'], {})
        self.assertEqual(report['settlement_pending'], ['001'])
        self.assertIsNone(report['actual_cost_per_generated_second'])

    def test_output_parser_ignores_input_urls(self):
        self.assertIsNone(z.output_url({'metadata': {'video_url': ['https://input/video.mp4']}}))
        self.assertEqual(z.output_url({'result_url': 'https://cdn/out.mp4'}), 'https://cdn/out.mp4')

    def test_same_provider_task_is_counted_once_even_if_adopted_under_alias(self):
        record = {'task_id': 'one-task', 'status': 'SUCCESS', 'usage': {'amount': 2, 'currency': 'CNY'}, 'media': {'frames': 48, 'fps': '24'}}
        report = z.billing({'jobs': {'001': record, '001/alias': dict(record)}})
        self.assertEqual(report['actual_total_by_currency'], {'CNY': '2'})
        self.assertEqual(len(report['tasks']), 1)

    def test_ambiguous_submit_is_persisted_and_not_retryable(self):
        state = {'jobs': {'003': {'phase': 'PREPARED'}}}
        class Client:
            def request(self, *args):
                raise TimeoutError('receipt lost')
        with patch.object(z, 'STATE', self.root/'state.json'), patch.object(z, 'prepare', return_value=({}, state['jobs']['003'])):
            with self.assertRaises(RuntimeError):
                z.submit(Client(), state, '003')
            saved = json.loads((self.root/'state.json').read_text())
            self.assertEqual(saved['jobs']['003']['phase'], 'UNCERTAIN')
            self.assertNotIn('task_id', saved['jobs']['003'])

    def test_free_upload_throttle_waits_without_paid_post(self):
        state = {'jobs': {}}
        client = unittest.mock.Mock()
        with patch.object(z, 'STATE', self.root/'state.json'), patch.object(z, 'prepare', side_effect=z.ApiError(429, 'rate limit', 75)):
            z.submit(client, state, '003')
        client.request.assert_not_called()
        self.assertEqual(state['jobs']['003']['phase'], 'RATE_LIMITED')
        self.assertNotIn('task_id', state['jobs']['003'])


if __name__ == '__main__':
    unittest.main()
