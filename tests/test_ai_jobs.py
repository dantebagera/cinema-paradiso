import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from services.ai_jobs import AIJobStore, AIJobError
from services.ai_provider import AISelection


class JobTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT'])
        self.addCleanup(self.temp.cleanup)
        self.store = AIJobStore(self.temp.name)
        self.selection = AISelection('chatgpt', 1, 'acct-a', 'model-a', 'curator', '1', 'hash', 'F1')

    def create(self, **changes):
        return self.store.create('F1', self.selection, {'prompt': 'synthetic', 'count': '9007199254740993', **changes}, 'request-a')

    def test_runtime_progress_is_read_only_and_bound_to_one_run(self):
        job = self.create()
        self.assertIsNone(job['progress_phase'])
        running = self.store.start_run(job['id'], job['revision'])
        report = self.store.progress_reporter(job['id'])
        self.assertEqual(running['progress_phase'], 'preparing')
        # Phase updates must neither write SQLite nor advance the job revision.
        with patch.object(self.store, '_connection', side_effect=AssertionError('phase wrote database')):
            report('connecting')
            report('retrieving')
        self.assertEqual(self.store.snapshot(job['id'])['revision'], running['revision'])
        self.assertEqual(self.store.snapshot(job['id'])['progress_phase'], 'retrieving')
        other = AIJobStore(self.temp.name)
        self.assertIsNone(other.snapshot(job['id'])['progress_phase'])
        failed = self.store.finish(job['id'], 'failed')
        report('matching')
        self.assertIsNone(self.store.snapshot(job['id'])['progress_phase'])
        queued = self.store.continue_job(job['id'], failed['revision'], 'resume')
        self.store.start_run(job['id'], queued['revision'])
        report('matching')
        self.assertEqual(self.store.snapshot(job['id'])['progress_phase'], 'preparing')
        fresh = self.store.progress_reporter(job['id'])
        fresh('matching')
        current = self.store.snapshot(job['id'])
        self.assertEqual(current['progress_phase'], 'matching')
        self.store.cancel(job['id'], current['revision'])
        fresh('connecting')
        self.assertIsNone(self.store.snapshot(job['id'])['progress_phase'])

    def test_disconnect_discards_runtime_progress(self):
        job = self.create()
        self.store.start_run(job['id'], job['revision'])
        report = self.store.progress_reporter(job['id'])
        self.store.disconnect(self.selection.account_id)
        report('retrieving')
        self.assertIsNone(self.store.snapshot(job['id'])['progress_phase'])

    def test_store_is_lazy_and_exact_target_survives_budget_pause_and_continue(self):
        self.assertFalse(self.store.path.exists())
        job = self.create()
        self.assertEqual(job['requested_count'], '9007199254740993')
        running = self.store.start_run(job['id'], job['revision'])
        for _ in range(24):
            self.store.reserve_inference(job['id'])
        with self.assertRaises(AIJobError):
            self.store.reserve_inference(job['id'])
        paused = self.store.snapshot(job['id'])
        self.assertEqual(paused['state'], 'paused_budget')
        self.assertEqual(paused['run_calls'], 24)
        resumed = self.store.continue_job(job['id'], paused['revision'], 'continue-a')
        self.assertEqual(resumed['requested_count'], '9007199254740993')
        self.assertEqual(resumed['state'], 'queued')
        self.assertEqual(resumed['run_calls'], 0)

    def test_idempotent_create_conflict_and_session_account_isolation(self):
        job = self.create()
        self.assertEqual(self.create()['id'], job['id'])
        with self.assertRaises(AIJobError):
            self.create(prompt='different')
        other = AISelection('chatgpt', 1, 'acct-b', 'model-a', 'curator', '1', 'hash', 'F1')
        with self.assertRaises(AIJobError) as caught:
            self.store.create('F1', other, {'prompt': 'followup', 'count': '15', 'session_id': job['session_id']}, 'other')
        self.assertEqual(caught.exception.code, 'session_account_mismatch')

    def test_verified_result_identity_deduplicates_and_pages_without_rounding_target(self):
        job = self.create()
        self.store.start_run(job['id'], job['revision'])
        rows = [{'domain': 'movie', 'identity': str(i), 'card': {'tmdb_id': i, 'title': 'Movie ' + str(i)}} for i in range(1, 31)]
        self.store.add_results(job['id'], rows + rows)
        page1 = self.store.snapshot(job['id'])
        page2 = self.store.snapshot(job['id'], page=2)
        self.assertEqual(page1['accepted_count'], 30)
        self.assertEqual(len(page1['results']), 20)
        self.assertEqual(len(page2['results']), 10)
        self.assertEqual(page1['requested_count'], '9007199254740993')

    def test_batch_persistence_stops_at_target_after_deduplication(self):
        job = self.create(count='3')
        self.store.start_run(job['id'], job['revision'])
        rows = [{'domain': 'movie', 'identity': str(i), 'card': {'tmdb_id': i}} for i in [1, 1, 2, 3, 4]]
        result = self.store.add_results(job['id'], rows, limit_to_target=True)
        self.assertEqual(result['accepted_count'], 3)

    def test_cancel_revision_and_restart_do_not_replay_or_erase_results(self):
        job = self.create()
        self.store.start_run(job['id'], job['revision'])
        with self.assertRaises(AIJobError):
            self.store.cancel(job['id'], job['revision'])
        current = self.store.snapshot(job['id'])
        cancelled = self.store.cancel(job['id'], current['revision'])
        self.assertEqual(cancelled['state'], 'cancelled')
        reopened = AIJobStore(self.temp.name)
        self.assertEqual(reopened.snapshot(job['id'])['state'], 'cancelled')
        with self.assertRaises(AIJobError):
            self.store.add_results(job['id'], [{'domain': 'movie', 'identity': '1', 'card': {}}])

    def test_cancel_running_generation_survives_progress_but_rejects_an_earlier_run(self):
        job = self.create()
        self.store.start_run(job['id'], job['revision'])
        self.store.reserve_inference(job['id'])
        cancelled = self.store.cancel(job['id'], job['revision'], run_number=0)
        self.assertEqual(cancelled['state'], 'cancelled')
        self.assertEqual(cancelled['run_calls'], 1)

        other = self.store.create('F1', self.selection, {'prompt': 'another', 'count': '500'}, 'request-b')
        self.store.finish(other['id'], 'partial')
        paused = self.store.snapshot(other['id'])
        resumed = self.store.continue_job(other['id'], paused['revision'], 'continue-b')
        with self.assertRaises(AIJobError):
            self.store.cancel(other['id'], resumed['revision'], run_number=0)
        self.assertEqual(self.store.snapshot(other['id'])['state'], 'queued')
        self.assertEqual(self.store.cancel(other['id'], resumed['revision'], run_number=1)['state'], 'cancelled')

    def test_installation_limit_is_shared_and_live_expired_leases_are_not_stolen(self):
        other = AIJobStore(self.temp.name)
        first = self.store.acquire_inference_slot('synthetic-one')
        second = other.acquire_inference_slot('synthetic-two')
        now = self.store.clock()
        self.store.clock = other.clock = lambda: now + 300
        self.assertIsNone(self.store.acquire_inference_slot('third'))
        self.store.release_inference_slot(first)
        third = other.acquire_inference_slot('third')
        self.assertIsNotNone(third)
        self.store.release_inference_slot(second)
        other.release_inference_slot(third)

    def test_dead_worker_is_observed_as_interrupted_without_automatic_resume(self):
        job = self.create()
        self.store.start_run(job['id'], job['revision'])
        reopened = AIJobStore(self.temp.name, process_alive=lambda pid: False)
        interrupted = reopened.snapshot(job['id'])
        self.assertEqual(interrupted['state'], 'interrupted')
        self.assertEqual(interrupted['run_calls'], 0)
        resumed = reopened.continue_job(job['id'], interrupted['revision'], 'explicit-continue')
        self.assertEqual(resumed['state'], 'queued')

    def test_expired_session_cannot_be_continued_with_guessed_context(self):
        job = self.create()
        running = self.store.start_run(job['id'], job['revision'])
        partial = self.store.finish(job['id'], 'partial')
        now = self.store.clock()
        self.store.clock = lambda: now + 8 * 86400
        with self.assertRaises(AIJobError) as caught:
            self.store.continue_job(job['id'], partial['revision'], 'expired-continue')
        self.assertEqual(caught.exception.code, 'new_session_required')

    def test_session_context_keeps_twenty_turns_and_separate_durable_constraints(self):
        job = self.create()
        for i in range(25):
            self.store.append_turn(job['session_id'], 'acct-a', {'role': 'user', 'content': str(i)},
                                   constraints={'exclude_horror': True})
        session = self.store.session(job['session_id'], 'acct-a')
        self.assertEqual(len(session['turns']), 20)
        self.assertEqual(session['turns'][0]['content'], '5')
        self.assertTrue(session['constraints']['exclude_horror'])

    def test_action_confirmation_is_claimed_once_and_dependencies_use_actual_receipts(self):
        job = self.create()
        self.store.start_run(job['id'], job['revision'])
        first = self.store.prepare_action(job['id'], 'create_list', {'owner_plan_id': 'owner-a'}, request_key='prepare-first')
        same = self.store.prepare_action(job['id'], 'create_list', {'owner_plan_id': 'owner-a'}, request_key='prepare-first')
        self.assertEqual(first['action_id'], same['action_id'])
        second = self.store.prepare_action(job['id'], 'download', {'owner_plan_id': 'owner-b'},
            request_key='prepare-second', depends_on=[first['action_id']])
        with self.assertRaises(AIJobError):
            self.store.claim_action(second['action_id'], second['revision'])
        claimed = self.store.claim_action(first['action_id'], first['revision'])
        with self.assertRaises(AIJobError):
            self.store.claim_action(first['action_id'], first['revision'])
        self.store.complete_action(first['action_id'], claimed['revision'], {'created_id': 'persisted-list'}, state='completed')
        reused = self.store.claim_action(first['action_id'], first['revision'])
        self.assertTrue(reused['already_completed'])
        self.assertEqual(reused['outcome']['created_id'], 'persisted-list')
        self.assertEqual(self.store.claim_action(second['action_id'], second['revision'])['state'], 'executing')

    def test_uncertain_action_never_replays_and_foreign_account_cannot_read_it(self):
        job = self.create()
        self.store.start_run(job['id'], job['revision'])
        action = self.store.prepare_action(job['id'], 'download', {'owner_plan_id': 'p'}, request_key='p')
        with self.assertRaises(AIJobError):
            self.store.action(action['action_id'], 'acct-b')
        claim = self.store.claim_action(action['action_id'], 0)
        self.store.complete_action(action['action_id'], claim['revision'], {'code': 'owner_timeout'}, state='uncertain')
        with self.assertRaises(AIJobError):
            AIJobStore(self.temp.name).claim_action(action['action_id'], 0)
        with self.assertRaises(AIJobError):
            self.store.prepare_action(job['id'], 'download', {'owner_plan_id': 'another'}, request_key='new-key')

    def test_confirmation_updates_a_followup_that_is_reviewing_the_same_prior_action(self):
        from dataclasses import replace
        selection = replace(self.selection, feature='F2')
        first = self.store.create('F2', selection, {'prompt': 'Prepare'}, 'first')
        self.store.start_run(first['id'], 0)
        action = self.store.prepare_action(first['id'], 'fixture', {}, request_key='action')
        self.store.finish(first['id'], 'awaiting_confirmation')
        followup = self.store.create('F2', selection, {'prompt': 'Explain', 'session_id': first['session_id']}, 'followup')
        self.store.start_run(followup['id'], 0)
        self.store.save_checkpoint(followup['id'], 'agent', {'prepared': [action]})
        self.store.finish(followup['id'], 'awaiting_confirmation')
        claim = self.store.claim_action(action['action_id'], 0)
        self.store.complete_action(action['action_id'], claim['revision'], {'saved': True}, state='completed')
        self.store.finalize_actions(first['id'])
        self.assertEqual(self.store.snapshot(first['id'])['state'], 'completed')
        self.assertEqual(self.store.snapshot(followup['id'])['state'], 'completed')

    def test_cancelling_future_control_work_cancels_prepared_receipts_for_followup_context(self):
        from dataclasses import replace
        job = self.store.create('F2', replace(self.selection, feature='F2'), {'prompt': 'Prepare'}, 'cancel-control')
        self.store.start_run(job['id'], 0)
        action = self.store.prepare_action(job['id'], 'fixture', {}, request_key='action')
        finished = self.store.finish(job['id'], 'awaiting_confirmation')
        self.store.cancel(job['id'], finished['revision'])
        self.assertEqual(self.store.action(action['action_id'], 'acct-a')['state'], 'cancelled')

    def test_result_handles_survive_restart_without_cross_session_access(self):
        from services.ai_catalog import ResultSet
        job = self.create()
        self.store.start_run(job['id'], job['revision'])
        result = ResultSet('set-a', 'fingerprint', ({'tmdb_id': 3, 'title': 'Three'},),
                           'complete', None, 1, 1, 1, 0, 0, None)
        self.store.save_result_set(job['id'], result)
        restored = AIJobStore(self.temp.name).result_sets(job['session_id'], 'acct-a')
        self.assertEqual([dict(row) for row in restored['set-a'].movies], [{'tmdb_id': 3, 'title': 'Three'}])
        with self.assertRaises(TypeError):
            restored['set-a'].movies[0]['title'] = 'changed'
        with self.assertRaises(AIJobError):
            self.store.result_sets(job['session_id'], 'acct-b')

    def test_nested_recommendations_share_parent_budget_and_cancellation(self):
        from dataclasses import replace
        parent = self.store.create('F2', replace(self.selection, feature='F2'), {'prompt': 'Suggest and list'}, 'parent')
        self.store.start_run(parent['id'], 0)
        child = self.store.create('F1', self.selection, {'prompt': 'Synthetic', 'count': '1000',
            'session_id': parent['session_id'], 'parent_job_id': parent['id']}, 'child')
        self.store.start_run(child['id'], 0)
        for _ in range(23):
            self.store.reserve_inference(parent['id'])
        self.store.reserve_inference(child['id'])
        self.assertEqual(self.store.snapshot(parent['id'])['run_calls'], 24)
        with self.assertRaises(AIJobError):
            self.store.reserve_inference(child['id'])
        self.assertEqual(self.store.snapshot(parent['id'])['state'], 'paused_budget')
        self.assertEqual(self.store.snapshot(child['id'])['state'], 'paused_budget')

    def test_shared_session_prevents_competing_main_turns_but_allows_nested_work(self):
        job = self.create()
        with self.assertRaises(AIJobError):
            self.store.create('F1', self.selection, {'prompt': 'competing', 'count': '15',
                'session_id': job['session_id']}, 'competing')

    def test_cloud_evidence_scopes_survive_session_turn_trimming(self):
        job = self.create()
        self.store.mark_evidence_scope(job['session_id'], 'acct-a', 'iptv_titles')
        for i in range(21):
            self.store.append_turn(job['session_id'], 'acct-a', {'role': 'user', 'content': str(i)})
        session = self.store.session(job['session_id'], 'acct-a')
        self.assertEqual(session['constraints']['evidence_scopes'], ['iptv_titles'])

    def test_page_cursor_keeps_exact_membership_and_rejects_foreign_job_binding(self):
        job = self.create()
        self.store.start_run(job['id'], job['revision'])
        self.store.add_results(job['id'], [{'domain': 'movie', 'identity': str(i), 'card': {'tmdb_id': i}} for i in range(30)])
        first = self.store.snapshot(job['id'])
        second = self.store.snapshot(job['id'], cursor=first['next_cursor'])
        self.assertEqual([row['tmdb_id'] for row in second['results']], list(range(20, 30)))
        other = self.store.create('F1', self.selection, {'prompt': 'other', 'count': '15'}, 'other')
        with self.assertRaises(AIJobError):
            self.store.snapshot(other['id'], cursor=first['next_cursor'])
