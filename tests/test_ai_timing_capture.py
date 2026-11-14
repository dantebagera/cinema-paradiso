import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.profile_ai_features import Trace, CallBudget, stage_timings, safe


class TimingCaptureTests(unittest.TestCase):
    def test_span_duration_excludes_writing_its_start_marker(self):
        with tempfile.TemporaryDirectory() as root:
            now = [0.0]
            with patch('tools.profile_ai_features.time.perf_counter', side_effect=lambda: now[0]):
                trace = Trace(root)
                original = trace.emit
                def delayed_emit(event, **values):
                    now[0] += 5.85
                    original(event, **values)
                trace.emit = delayed_emit
                with trace.span('lease_acquire'):
                    now[0] += .01
            rows = [json.loads(line) for line in trace.path.read_text().splitlines()]
            self.assertAlmostEqual(rows[-1]['seconds'], .01)
    def test_public_token_usage_details_are_retained_without_credentials(self):
        value = safe({'usage': {'input_tokens': 99, 'input_tokens_details': {'cached_tokens': 64},
                              'output_tokens_details': {'reasoning_tokens': 18}}, 'access_token': 'secret'})
        self.assertEqual(value, {'usage': {'input_tokens': 99, 'input_tokens_details': {'cached_tokens': 64},
                                          'output_tokens_details': {'reasoning_tokens': 18}}})
    def test_matching_is_wall_time_and_not_the_sum_of_overlapping_http_requests(self):
        rows = [{'event': 'workflow_started', 'at_seconds': 2},
                {'event': 'first_cards', 'at_seconds': 13},
                {'event': 'span_end', 'phase': 'gpt_run', 'seconds': 10},
                {'event': 'span_end', 'phase': 'gpt_http', 'seconds': 9.5},
                {'event': 'span_end', 'phase': 'tmdb_matching', 'seconds': 6}]
        rows += [{'event': 'span_end', 'phase': 'tmdb_http', 'seconds': 5} for _ in range(4)]
        timings = stage_timings(rows, 17)
        self.assertEqual(timings['gpt_seconds'], 10)
        self.assertEqual(timings['matching_after_gpt_seconds'], 6)
        self.assertEqual(timings['other_seconds'], 1)
        self.assertEqual(timings['first_cards_seconds'], 11)

    def test_gpt_tmdb_overlap_is_an_interval_intersection_not_summed_worker_seconds(self):
        rows = []
        for phase, key, identity, start, end in [('gpt_http','attempt',1,0,10),
                                               ('tmdb_http','request',1,4,8),
                                               ('tmdb_http','request',2,6,12),
                                               ('tmdb_http','request',3,13,15)]:
            rows.extend([{'event':'span_start','phase':phase,key:identity,'at_seconds':start},
                         {'event':'span_end','phase':phase,key:identity,'at_seconds':end,'seconds':end-start}])
        times = stage_timings(rows, 16)
        self.assertEqual(times['tmdb_http_active_seconds'], 10)
        self.assertEqual(times['gpt_tmdb_overlap_seconds'], 6)
    def test_attempt_budget_is_reserved_before_io_and_does_not_allow_an_extra_attempt(self):
        budget = CallBudget(2)
        self.assertEqual(budget.reserve(), 1)
        self.assertEqual(budget.reserve(), 2)
        with self.assertRaisesRegex(RuntimeError, 'diagnostic_call_budget'):
            budget.reserve()
        self.assertEqual(budget.used, 2)

    def test_trace_is_incremental_and_does_not_write_credentials_or_query_strings(self):
        with tempfile.TemporaryDirectory() as root:
            trace = Trace(Path(root))
            trace.emit('test', token='secret-a', access_token='secret-b', authorization='secret-c',
                       url='https://example.invalid/?api_key=secret-d', model='model-a')
            text = trace.path.read_text()
            self.assertNotIn('secret-', text)
            self.assertEqual(json.loads(text)['model'], 'model-a')

    def test_span_records_failure_without_arbitrary_exception_text(self):
        with tempfile.TemporaryDirectory() as root:
            trace = Trace(Path(root))
            with self.assertRaises(ValueError):
                with trace.span('matching', title='Movie'):
                    raise ValueError('secret from remote server')
            rows = [json.loads(line) for line in trace.path.read_text().splitlines()]
            self.assertEqual(rows[-1]['state'], 'failed')
            self.assertEqual(rows[-1]['error'], 'ValueError')
            self.assertGreaterEqual(rows[-1]['seconds'], 0)
            self.assertNotIn('secret', trace.path.read_text())
