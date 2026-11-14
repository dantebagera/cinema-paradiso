import os
import json
import tempfile
import threading
import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from services.ai_jobs import AIJobStore
from services.ai_provider import AISelection
from services.ai_catalog import AICatalog
from services.chatgpt_recommendations import Recommender
from services.chatgpt_skills import load
from services.chatgpt_transport import CompletedResponse, ToolCall
from services.chatgpt_transport import ChatGPTError
from services.ai_provider import AIProviderError


def query_without_horror():
    return {'version': 1, 'scope': 'discover', 'mode': 'advanced', 'feed': 'catalog',
        'sort': {'key': 'auto', 'direction': 'desc'}, 'groups': [
            {'type': 'genre', 'join': 'or', 'values': [{'id': '27', 'label': 'Horror', 'exclude': True}]}]}


class RecommendationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT'])
        self.addCleanup(self.temp.cleanup)
        self.store = AIJobStore(self.temp.name)
        skill = load('F1')
        self.selection = AISelection('chatgpt', 1, 'account', 'fixture', skill['id'], skill['version'], skill['hash'], 'F1')
        self.calls = 0
        self.next_identity = 1
        self.seen_inputs = []
        self.include_rejected = False
        self.empty_after = None
        self.nl_count = None
        self.catalogue = AICatalog(lambda *args: {}, details=lambda identity: {}, person_seed=lambda plan: None)
        def transport(selection, job_id):
            def run(*args, **kwargs):
                self.store.reserve_inference(job_id)
                return self.infer(selection, **kwargs)
            return SimpleNamespace(run=run)
        self.runner = Recommender(self.store, transport,
                                  self.resolve, catalogue=self.catalogue)

    def resolve(self, candidate):
        identity = int(candidate['title'].split()[-1])
        raw = {'id': identity, 'title': candidate['title'], 'runtime': 90, 'release_date': '2001-01-01',
               'genre_ids': [27] if identity == 999 else [878]}
        return {'raw': raw, 'card': {'tmdb_id': identity, 'title': candidate['title'], 'year': '2001'}}

    def infer(self, selection, **kwargs):
        self.calls += 1
        self.seen_inputs.append(kwargs['input_items'])
        remaining = 20 if self.empty_after is None else max(0, min(20, self.empty_after - self.next_identity + 1))
        recommendations = [{'title': 'Movie ' + str(i), 'year': '2001'}
                           for i in range(self.next_identity, self.next_identity + remaining)]
        self.next_identity += remaining
        if self.include_rejected and self.calls == 1:
            recommendations = [{'title': 'Movie 999', 'year': '2001'}] + recommendations[:18]
            recommendations += [recommendations[1]]
        import json
        evidence = json.loads(kwargs['input_items'][0]['content'])
        arguments = {'recommendations': recommendations}
        if not evidence.get('scope_is_fixed'):
            arguments['scope'] = {'query': query_without_horror(),
                'subjective_requirements': ['atmospheric'], 'requested_count': self.nl_count}
        return CompletedResponse('resp_fake', json.dumps(arguments), ())

    def job(self, count, **request):
        return self.store.create('F1', self.selection, {'prompt': 'Atmospheric science fiction, no horror',
            'count': str(count), 'count_source': 'explicit', **request}, 'request-' + str(count))

    def test_120_verified_unique_results_are_batched_and_preserve_exclusion(self):
        self.include_rejected = True
        job = self.job(120)
        self.runner.run(job['id'])
        done = self.store.snapshot(job['id'], page_size=100)
        self.assertEqual(done['state'], 'completed')
        self.assertEqual(done['accepted_count'], 120)
        self.assertGreater(self.calls, 6)
        self.assertNotIn(999, [row['tmdb_id'] for row in done['results']])
        self.assertEqual(len({row['tmdb_id'] for row in done['results']}), 100)
        self.assertEqual(len(self.store.snapshot(job['id'], page=2, page_size=100)['results']), 20)

    def test_shortfall_is_honest_and_never_padded(self):
        self.empty_after = 11
        job = self.job(20)
        self.runner.run(job['id'])
        result = self.store.snapshot(job['id'])
        self.assertEqual(result['state'], 'partial')
        self.assertEqual(result['accepted_count'], 11)
        self.assertEqual(result['requested_count'], '20')

    def test_exhaustive_factual_request_hands_original_prompt_to_ai_control_without_padding(self):
        self.infer = lambda *args, **kwargs: CompletedResponse('fixture', '', (), (ToolCall('handoff', 'cp_control.open', {}),))
        job = self.job(15, prompt='All films produced by the resolved studio')
        self.runner.run(job['id'])
        result = self.store.snapshot(job['id'])
        self.assertEqual(result['accepted_count'], 0)
        self.assertEqual(result['run_calls'], 1)
        self.assertEqual(result['output']['handoff'], 'ai-control')
        self.assertEqual(result['output']['prompt'], job['request']['prompt'])

    def test_fifty_target_fits_one_requested_batch_and_fixed_scope_is_not_advertised_again(self):
        original = self.infer
        advertised = []
        targets = []
        def infer(selection, **options):
            import json
            advertised.append({tool['name'] for tool in options['tools']})
            targets.append(json.loads(options['input_items'][0]['content'])['batch_target'])
            result = original(selection, **options)
            return result
        self.infer = infer
        job = self.job(50)
        self.runner.run(job['id'])
        self.assertEqual(self.store.snapshot(job['id'])['accepted_count'], 50)
        self.assertEqual(targets[0], 50)
        self.assertNotIn('cp_scope', advertised[0])
        self.assertNotIn('cp_scope', advertised[1])
        self.assertNotIn('cp_result', advertised[0])
        self.assertEqual(advertised[1], set())
        self.assertTrue(any('Movie 1' == row['title'] for row in
            json.loads(self.seen_inputs[-1][0]['content'])['already_accepted_examples']))

    def test_first_verified_card_is_saved_before_the_entire_candidate_batch_finishes(self):
        original = self.resolve
        already_saved = []
        job = self.job(20)
        def resolve(candidate):
            already_saved.append(self.store.snapshot(job['id'])['accepted_count'])
            return original(candidate)
        self.runner.resolve_candidate = resolve
        self.runner.run(job['id'])
        self.assertEqual(self.store.snapshot(job['id'])['accepted_count'], 20)
        self.assertTrue(any(count > 0 for count in already_saved), already_saved)

    def test_topup_is_told_which_candidates_failed_instead_of_recommending_them_again(self):
        import json
        original = self.infer
        def infer(selection, **options):
            response = original(selection, **options)
            if self.calls == 1:
                result = json.loads(response.text)
                result['recommendations'][0]['title'] = 'Movie 999'
                response = CompletedResponse(response.response_id, json.dumps(result), ())
            else:
                rejected = json.loads(options['input_items'][0]['content'])['rejected_candidates']
                self.assertIn('Movie 999', [row['title'] for row in rejected])
            return response
        self.infer = infer
        job = self.job(20)
        self.runner.run(job['id'])
        self.assertEqual(self.store.snapshot(job['id'])['accepted_count'], 20)

    def test_one_title_year_response_produces_fifty_verified_cards_without_more_inference(self):
        def infer(selection, **options):
            self.calls += 1
            self.assertNotIn('cp_result', {tool['name'] for tool in options['tools']})
            result = {'scope': {'query': query_without_horror(), 'subjective_requirements': ['twisted endings'],
                                'requested_count': None},
                      'recommendations': [{'title': 'Movie ' + str(i), 'year': '2001'} for i in range(1, 51)]}
            return CompletedResponse('fixture', json.dumps(result), ())
        self.infer = infer
        job = self.job(50, prompt='movies with very twisted story you wont expect the ending')
        self.runner.run(job['id'])
        done = self.store.snapshot(job['id'], page_size=100)
        self.assertEqual(done['state'], 'completed', done)
        self.assertEqual(done['accepted_count'], 50)
        self.assertEqual(self.calls, 1)
        self.assertEqual({int(row['tmdb_id']) for row in done['results']}, set(range(1, 51)))

    def streamed_result(self, identity=1):
        return {'scope': {'query': query_without_horror(), 'subjective_requirements': [], 'requested_count': None},
                'recommendations': [{'title': 'Movie ' + str(identity), 'year': '2001'}]}

    def test_lookup_starts_during_gpt_but_no_card_is_saved_before_terminal_scope_validation(self):
        started = threading.Event()
        original = self.resolve
        def resolve(candidate):
            started.set()
            return original(candidate)
        self.runner.resolve_candidate = resolve
        job = self.job(1)
        def infer(selection, **options):
            result = self.streamed_result()
            options['on_text_delta'](json.dumps(result))
            self.assertTrue(started.wait(2), 'TMDB lookup did not overlap the unfinished GPT call')
            snapshot = self.store.snapshot(job['id'])
            self.assertEqual(snapshot['accepted_count'], 0)
            self.assertFalse(snapshot['cursor'].get('scope_fixed'))
            return CompletedResponse('fixture', json.dumps(result), ())
        self.infer = infer
        self.runner.run(job['id'])
        result = self.store.snapshot(job['id'])
        self.assertEqual(result['state'], 'completed', result)
        self.assertEqual(result['accepted_count'], 1)

    def test_changed_final_candidate_is_authoritative_over_speculative_streamed_title(self):
        def infer(selection, **options):
            options['on_text_delta'](json.dumps(self.streamed_result(999)))
            return CompletedResponse('fixture', json.dumps(self.streamed_result(1)), ())
        self.infer = infer
        job = self.job(1)
        self.runner.run(job['id'])
        done = self.store.snapshot(job['id'])
        self.assertEqual(done['state'], 'completed', done)
        self.assertEqual([str(row['tmdb_id']) for row in done['results']], ['1'])

    def test_failed_gpt_response_discards_prefetched_results(self):
        def infer(selection, **options):
            options['on_text_delta'](json.dumps(self.streamed_result()))
            raise ChatGPTError('network_error')
        self.infer = infer
        job = self.job(1)
        self.runner.run(job['id'])
        done = self.store.snapshot(job['id'])
        self.assertEqual(done['state'], 'failed')
        self.assertEqual(done['message'], 'network_error')
        self.assertEqual(done['accepted_count'], 0)

    def test_permission_loss_during_stream_prevents_publication_of_prefetched_results(self):
        revoked = []
        def permission(selection):
            if revoked:
                raise AIProviderError('account_disconnected')
        def infer(selection, **options):
            options['on_text_delta'](json.dumps(self.streamed_result()))
            revoked.append(True)
            return CompletedResponse('fixture', json.dumps(self.streamed_result()), ())
        self.runner.check_permission = permission
        self.infer = infer
        job = self.job(1)
        self.runner.run(job['id'])
        done = self.store.snapshot(job['id'])
        self.assertEqual(done['accepted_count'], 0)
        self.assertEqual(done['state'], 'failed')
        self.assertEqual(done['message'], 'account_disconnected')

    def test_permission_loss_during_lookup_is_checked_before_saving_any_card(self):
        revoked = []
        original = self.resolve
        def resolve(candidate):
            result = original(candidate)
            revoked.append(True)
            return result
        def permission(selection):
            if revoked:
                raise AIProviderError('account_disconnected')
        self.runner.resolve_candidate = resolve
        self.runner.check_permission = permission
        job = self.job(1)
        self.runner.run(job['id'])
        done = self.store.snapshot(job['id'])
        self.assertEqual(done['accepted_count'], 0)
        self.assertEqual(done['state'], 'failed')
        self.assertEqual(done['message'], 'account_disconnected')

    def test_duplicate_identity_is_reported_to_the_replacement_call(self):
        original = self.infer
        def infer(selection, **options):
            response = original(selection, **options)
            result = json.loads(response.text)
            if self.calls == 1:
                result['recommendations'][-1] = result['recommendations'][0]
            else:
                rejected = json.loads(options['input_items'][0]['content'])['rejected_candidates']
                self.assertTrue(any(row['title'] == 'Movie 1' and 'already' in row['reason'] for row in rejected), rejected)
            return CompletedResponse(response.response_id, json.dumps(result), ())
        self.infer = infer
        job = self.job(20)
        self.runner.run(job['id'])
        result = self.store.snapshot(job['id'])
        self.assertEqual(result['state'], 'completed', result)
        self.assertEqual(result['accepted_count'], 20)

    def test_duplicate_from_an_older_session_job_is_named_in_replacement_feedback(self):
        original = self.infer
        def one(selection, **options):
            response = original(selection, **options)
            result = json.loads(response.text)
            result['recommendations'] = result['recommendations'][:1]
            if self.calls == 3:
                evidence = json.loads(options['input_items'][0]['content'])
                self.assertNotIn('Movie 1', [row['title'] for row in evidence['previous_results']])
                result['recommendations'] = [{'title': 'Movie 1', 'year': '2001'}]
            elif self.calls == 4:
                evidence = json.loads(options['input_items'][0]['content'])
                self.assertIn('Movie 1', [row['title'] for row in evidence['rejected_candidates']])
            return CompletedResponse(response.response_id, json.dumps(result), ())
        self.infer = one
        first = self.job(1)
        self.runner.run(first['id'])
        for index in (2, 3):
            job = self.store.create('F1', self.selection, {'prompt': 'More, keep exclusions', 'count': '1',
                'count_source': 'explicit', 'session_id': first['session_id']}, 'older-job-' + str(index))
            self.runner.run(job['id'])
            done = self.store.snapshot(job['id'])
            self.assertEqual(done['state'], 'completed', done)
            self.assertNotEqual(str(done['results'][0]['tmdb_id']), '1')
        self.assertEqual(self.calls, 4)

    def test_matching_phase_includes_the_final_pending_result_save(self):
        job = self.job(3)
        finished_counts = []
        @contextmanager
        def measure(phase):
            self.assertEqual(phase, 'tmdb_matching')
            yield
            finished_counts.append(self.store.snapshot(job['id'])['accepted_count'])
        self.runner.measure_phase = measure
        self.runner.run(job['id'])
        self.assertEqual(finished_counts, [3])

    def test_malformed_text_is_repaired_once_and_provider_failure_is_visible(self):
        self.infer = lambda *args, **kwargs: CompletedResponse('fixture', 'not valid JSON', ())
        job = self.job(50)
        self.runner.run(job['id'])
        result = self.store.snapshot(job['id'])
        self.assertEqual(result['state'], 'failed')
        self.assertEqual(result['run_calls'], 2)
        self.assertEqual(result['message'], 'invalid_feature_result')

    def test_replacements_cannot_redeclare_or_weaken_fixed_scope(self):
        original = self.infer
        def infer(selection, **options):
            response = original(selection, **options)
            result = json.loads(response.text)
            result['scope'] = {'query': query_without_horror(), 'subjective_requirements': [], 'requested_count': None}
            return CompletedResponse(response.response_id, json.dumps(result), ())
        self.infer = infer
        job = self.job(50)
        self.runner.run(job['id'])
        result = self.store.snapshot(job['id'])
        self.assertEqual(result['state'], 'partial', result)
        self.assertEqual(result['accepted_count'], 20)
        self.assertEqual(result['message'], 'invalid_feature_result')

    def test_budget_pause_and_continue_preserve_the_exact_target_and_results(self):
        job = self.job('9007199254740993')
        self.runner.run(job['id'])
        result = self.store.snapshot(job['id'])
        self.assertEqual(result['state'], 'paused_budget')
        self.assertEqual(result['run_calls'], 24)
        self.assertEqual(result['requested_count'], '9007199254740993')
        self.assertEqual(result['accepted_count'], 480)
        resumed = self.store.continue_job(job['id'], result['revision'], 'continue')
        self.empty_after = self.next_identity - 1
        self.runner.run(resumed['id'])
        self.assertEqual(self.store.snapshot(job['id'])['accepted_count'], 480)

    def test_followup_uses_actual_previous_third_result_and_retains_scope(self):
        first = self.job(3)
        self.runner.run(first['id'])
        followup = self.store.create('F1', self.selection, {'prompt': 'More like the third, less violent',
            'count': '3', 'session_id': first['session_id'], 'count_source': 'explicit'}, 'followup')
        self.runner.run(followup['id'])
        self.assertIn('Movie 3', str(self.seen_inputs[-1]))
        self.assertEqual(self.store.snapshot(followup['id'])['accepted_count'], 3)

    def test_text_quantity_overrides_saved_default_only_for_the_job(self):
        self.nl_count = '120'
        job = self.job(75, count_source='settings')
        self.runner.run(job['id'])
        result = self.store.snapshot(job['id'])
        self.assertEqual(result['requested_count'], '120')
        self.assertEqual(result['accepted_count'], 120)

    def test_real_cp_route_worker_and_identity_owner_return_the_complete_verified_set(self):
        import json
        import time
        from unittest.mock import patch
        from tests.ai_provider_server import OfflineGuard
        with OfflineGuard():
            import app
            next_id = [1]
            profile = {'account_id': 'account', 'connected': True, 'plan_enabled': True}
            auth = SimpleNamespace(credentials=SimpleNamespace(profiles=lambda: [profile]), access_token=lambda account: 'offline')
            def transport(job_id=None):
                def run(selection, **kwargs):
                    app._get_ai_job_store().reserve_inference(job_id)
                    content = json.loads(kwargs['input_items'][0]['content'])
                    size = content['batch_target']
                    candidates = [{'title': 'Movie ' + str(i), 'year': '2001'}
                                  for i in range(next_id[0], next_id[0] + size)]
                    next_id[0] += size
                    arguments = {'recommendations': candidates}
                    if not content.get('scope_is_fixed'):
                        arguments['scope'] = {'query': query_without_horror(),
                            'subjective_requirements': [], 'requested_count': None}
                    return CompletedResponse('resp_fake', json.dumps(arguments), ())
                return SimpleNamespace(run=run)
            def raw(identity):
                return {'id': int(identity), 'title': 'Movie ' + str(identity), 'release_date': '2001-01-01',
                        'runtime': 95, 'genre_ids': [878], 'overview': 'Synthetic movie evidence.',
                        'vote_count': 100, 'vote_average': 7.5, 'original_language': 'en'}
            def search(title, year=''):
                return [raw(int(title.split()[-1]))]
            configuration = {'ai_provider': 'chatgpt', 'chatgpt': {'active_account_id': 'account', 'model': 'offline',
                'recommendation_count': '120'}}
            with patch.multiple(app, _user_data_dir=self.temp.name, _tmdb_key='offline', _ai_provider_config=configuration,
                _ai_job_store_owner=None, _ai_job_store_root=None, _ai_job_service_owner=None, _ai_job_service_root=None), \
                patch.object(app, '_get_chatgpt_auth', return_value=auth), \
                patch.object(app, '_get_chatgpt_transport', side_effect=transport), \
                patch.object(app, '_ai_scope_context', return_value={'genre': [{'id': '27', 'label': 'Horror'}]}), \
                patch.object(app, '_smart_match_tmdb_search', side_effect=search), \
                patch.object(app, '_smart_match_tmdb_alternative_titles', return_value=[]), \
                patch.object(app, '_ai_movie_details', side_effect=raw), \
                patch.object(app, '_ollama_api_json', side_effect=AssertionError('GPT reached Ollama')):
                try:
                    client = app.app.test_client()
                    started = client.post('/api/ai/recommendations', json={'prompt': 'Synthetic science fiction, no horror', 'request_key': 'route-proof'})
                    self.assertEqual(started.status_code, 202)
                    job_id = started.json['id']
                    deadline = time.monotonic() + 10
                    while True:
                        result = client.get('/api/ai/jobs/' + job_id + '?page_size=100').json
                        if result['state'] not in ('queued', 'running') or time.monotonic() > deadline:
                            break
                        threading.Event().wait(0.02)
                    self.assertEqual(result['state'], 'completed', result)
                    second = client.get('/api/ai/jobs/' + job_id + '?page=2&page_size=100').json
                    ids = {int(row['tmdb_id']) for row in result['results'] + second['results']}
                    self.assertEqual(ids, set(range(1, 121)))
                    self.assertEqual(result['requested_count'], '120')
                finally:
                    if app._ai_job_service_owner is not None:
                        app._ai_job_service_owner.close()
