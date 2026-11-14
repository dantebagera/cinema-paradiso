import threading
import os
import tempfile
import time
import unittest
from unittest.mock import Mock, patch
from services.ai_provider import AISelection
from services.chatgpt_skills import load
from services.chatgpt_transport import CompletedResponse, ToolCall
from services.iptv_movie_service import IPTVMovieService
from services.iptv_metadata_settings import IPTVMetadataSettings
from services.iptv_movie_store import source_key
from tests.iptv_movie_fixtures import create_raw_service, FakeTMDBClient, tmdb_payload


class IPTVCloudTests(unittest.TestCase):
    def test_oversized_metadata_selection_stops_after_the_first_page(self):
        from services.iptv_movie_store import IPTVMovieStore, IPTVSelectionError

        store = object.__new__(IPTVMovieStore)
        store.source_generation = Mock(return_value=1)
        store.review_queue = Mock(side_effect=lambda view, *, page, page_size, filters: {
            'total': 6413, 'page_size': page_size,
            'items': [{'source_key': f's_{page}_{index}'} for index in range(page_size)],
        })
        with self.assertRaises(IPTVSelectionError) as failure:
            store.resolve_selection(mode='all-filtered', filters={'review_view': 'unmatched'})
        self.assertEqual(failure.exception.code, 'iptv_selection_too_large')
        store.review_queue.assert_called_once()

    def test_filtered_selection_accepts_the_desktop_spelling_for_both_jobs(self):
        from flask import Flask
        from types import SimpleNamespace
        from services.ai_routes import register_ai_routes

        app = Flask(__name__)
        provider, owner, jobs = Mock(), Mock(), Mock()
        provider.snapshot.return_value = SimpleNamespace(provider='chatgpt')
        owner.store.resolve_selection.return_value = {'source_keys': ['s_fixture'], 'catalog_generation': 1}
        jobs.store.create.return_value = {'id': 'fixture'}
        register_ai_routes(app, provider, iptv_factory=lambda _: owner, jobs_factory=lambda: jobs)
        for action in ('classification', 'match'):
            response = app.test_client().post(f'/api/iptv/providers/fixture/movies/ai/{action}-jobs',
                json={'selection_mode': 'all-filtered', 'filters': {'review_view': 'unmatched'}, 'request_key': action})
            self.assertEqual(response.status_code, 202, response.json)

    def test_lionz_title_cleanup_preserves_real_numbers_and_separates_scripts(self):
        from services.iptv_tmdb import parse_provider_title, combine_provider_title_evidence
        from services.iptv_movie_store import _provider_year

        self.assertEqual(parse_provider_title('Bird Box (2018) Multi Sub')['aliases'], ['bird box'])
        self.assertEqual(parse_provider_title('Feel the Beat (2020) Multi Audio And Subtitle')['aliases'], ['feel the beat'])
        self.assertEqual(parse_provider_title('Merry Little Batman ميلاد سعيد باتمان الصغير (2023) (مدبلج)')['aliases'],
                         ['merry little batman', 'ميلاد سعيد باتمان الصغير'])
        self.assertEqual(parse_provider_title('1917 (2019)')['aliases'], ['1917'])
        self.assertEqual(parse_provider_title('1917 (2019)', 1917)['year'], 2019)
        self.assertEqual(_provider_year('', '1917 (2019)'), 2019)
        self.assertEqual(parse_provider_title('1917', 1917)['aliases'], ['1917'])
        self.assertEqual(parse_provider_title('مُسرحية الاختبار')['aliases'], ['مسرحية الاختبار'])
        self.assertEqual(parse_provider_title('Toy Story 2 (1999)')['aliases'], ['toy story 2'])
        title = '207-In The Mood For Love (2000)'
        self.assertEqual(combine_provider_title_evidence(title, playlist_name='IMDB [ TOP 264 Movie ]')['aliases'],
                         ['in the mood for love'])
        self.assertEqual(parse_provider_title(title)['aliases'], ['207 in the mood for love'])

    def test_classification_queue_and_mixed_playlist_send_playlist_only_guess_to_gpt(self):
        with tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT']) as root:
            raw = create_raw_service(root, 'a' * 32, movie_rows=[{'stream_id': '10',
                'name': '95th Annual Academy Awards | حفل توزيع الاوسكار', 'category_id': 'movies-a'}])
            owner = IPTVMovieService(raw.root, 'a' * 32, raw, IPTVMetadataSettings(root))
            owner.start_projection(wait=True)
            key = source_key('10')
            self.assertEqual(owner.metadata_review('classification-review')['total'], 1)
            with owner.store.connection(immediate=True) as connection:
                connection.execute("UPDATE movie_sources SET playlist_name='Concerts - حفلات' WHERE source_key=?", (key,))
            classifier = Mock(return_value={'category': 'Misc', 'confidence': .99, 'mixed': False,
                'uncertain': False, 'title_exceptions': [], 'status': 'classified'})
            review = owner.classification_preview({'selected_keys': [key]}, ai_classifier=classifier)
            classifier.assert_called_once()
            self.assertEqual(review['proposals'][0]['category'], 'misc')
            self.assertEqual(owner.store.source(key)['category'], 'unclassified')

    def test_rule_upgrade_is_offered_before_stale_rows_are_marked(self):
        from pathlib import Path
        from services.iptv_movie_store import IPTVMovieStore
        with tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT']) as root:
            store = IPTVMovieStore(Path(root) / ('a' * 32), 'a' * 32)
            with store.connection(immediate=True) as connection:
                store._set_meta(connection, 'parser_version', '3')
            self.assertTrue(store.worker_control_status()['rules_update_pending'])
            self.assertEqual(store.worker_control_status()['stale'], 0)
            store.mark_stale_automatic_results()
            self.assertFalse(store.worker_control_status()['rules_update_pending'])

    def test_play_metadata_retains_source_identity_and_sports_music_cannot_match(self):
        with tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT']) as root:
            raw = create_raw_service(root, 'a' * 32, movie_rows=[{'stream_id': str(i),
                'name': f'Fixture {i}', 'category_id': 'movies-a' if i == 1 else 'movies-b'} for i in range(1, 5)])
            tmdb_id = 781869
            client = FakeTMDBClient(movies={tmdb_id: tmdb_payload(tmdb_id, 'Fixture stage performance', 1980)})
            owner = IPTVMovieService(raw.root, 'a' * 32, raw, IPTVMetadataSettings(root), tmdb_client_factory=lambda: client)
            owner.start_projection(wait=True)
            for i, category in enumerate(('plays', 'sports', 'music', 'film'), 1):
                owner.store.apply_classification_decisions([{'source_key': source_key(str(i)), 'category': category}])
            play_key = 'source:' + source_key('1')
            owner.store.set_list_membership('fixture-list', play_key, True)
            self.assertEqual(owner.manual_match(play_key, tmdb_id), play_key)
            owner.manual_match('source:' + source_key('4'), tmdb_id)
            play = owner.store.movie(play_key)
            self.assertEqual((play['category'], play['tmdb_id'], play['list_ids']), ('plays', tmdb_id, ['fixture-list']))
            self.assertEqual(owner.store.source_keys_for_movie(f'tmdb:{tmdb_id}'), [source_key('4')])
            self.assertEqual(owner.store.list_movies({'view': 'cp', 'category': 'plays'})['items'][0]['movie_key'], play_key)
            self.assertEqual(owner.store.list_movies({'view': 'cp', 'category': 'film', 'playlist_id': 'movies-a'})['total'], 0)
            self.assertEqual(owner.store.fusion_candidate_rows()['classification'], [])
            for i in (2, 3):
                with self.assertRaisesRegex(ValueError, 'classification'):
                    owner.manual_match('source:' + source_key(str(i)), tmdb_id)
            owner.remove_match(play_key)
            play = owner.store.movie(play_key)
            self.assertEqual((play['category'], play['tmdb_id'], play['list_ids']), ('plays', None, ['fixture-list']))
            owner.manual_match(play_key, tmdb_id)
            owner.store.apply_classification_decisions([{'source_key': source_key('1'), 'category': 'music'}], manual=True)
            self.assertFalse(owner.store.movie(play_key)['matched'])

    def test_model_search_aliases_do_not_corroborate_a_fuzzy_candidate(self):
        from services.iptv_tmdb import choose_automatic_match

        stem = 'An exceptionally long illustrative movie title for a theatre screening about a mysterious village near the old harbour '
        candidate = tmdb_payload(550, stem + 'pp', 2024)
        candidate['search_aliases'] = ['first model title', 'second model title']
        decision = choose_automatic_match(stem + 'pt (2024)', 2024, [candidate])
        self.assertGreaterEqual(decision['candidates'][0]['match_score'], 94)
        self.assertEqual(decision['state'], 'ambiguous')

    def test_hints_find_candidates_but_are_not_identity_evidence(self):
        with tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT']) as root:
            raw = create_raw_service(root, 'a' * 32, movie_rows=[{'stream_id': '10',
                'name': 'تحدي الأقوياء (1980)', 'category_id': 'movies-a'}])
            key = source_key('10')
            right = tmdb_payload(550, 'The Strong Challenge', 1980)
            right['alternative_titles'] = {'titles': [{'title': 'تحدي الأقوياء'}]}
            wrong = tmdb_payload(551, 'The Strong Challenge', 1980)
            class Client(FakeTMDBClient):
                def search_movies(self, title, year=0, page=1):
                    return [wrong, right] if title == 'the strong challenge' else []
            owner = IPTVMovieService(raw.root, 'a' * 32, raw, IPTVMetadataSettings(root),
                tmdb_client_factory=lambda: Client(movies={550: right, 551: wrong}))
            owner.start_projection(wait=True)
            owner.store.apply_classification_decisions([{'source_key': key, 'category': 'film'}])
            hints = Mock(return_value=['The Strong Challenge'])
            rank = Mock(return_value={'tmdb_id': 550})
            job = owner.create_match_job({'method': 'ai', 'selected_keys': [key]}, ai_ranker=rank, ai_title_hints=hints)
            self.assertEqual(job['proposals'][0]['candidate_tmdb_id'], 550)
            self.assertEqual([item['tmdb_id'] for item in rank.call_args.args[0]['candidates']], [550])
            self.assertIn('تحدي الأقوياء', rank.call_args.args[0]['candidates'][0]['aliases'])
            self.assertEqual(job['proposals'][0]['evidence']['search_hints'], ['The Strong Challenge'])
            self.assertFalse(owner.store.movie('source:' + key)['matched'])

    def test_hint_mode_uses_alias_only_schema_and_rejects_urls(self):
        import json
        from services.chatgpt_iptv import IPTVInference
        from services.chatgpt_transport import ChatGPTError

        skill = load('F5')
        selection = AISelection('chatgpt', 1, 'account', 'model', skill['id'], skill['version'], skill['hash'], 'F5', 'provider')
        runner = Mock()
        runner.run.return_value = CompletedResponse('fixture', '', [], [ToolCall('call', 'cp_result.submit',
            {'aliases': ['تحدي الأقوياء', 'The Strong Challenge']})])
        inference = IPTVInference(runner)
        evidence = {'title': 'تحدي الاقوياء (1980)', 'year': 1980, 'aliases': []}
        self.assertEqual(inference.suggest_titles(selection, evidence, cancel=threading.Event()),
                         ['تحدي الأقوياء', 'The Strong Challenge'])
        arguments = runner.run.call_args.kwargs
        self.assertEqual(json.loads(arguments['input_items'][0]['content'])['mode'], 'suggest-search-aliases')
        self.assertEqual(arguments['tools'][0]['tools'][0]['parameters']['required'], ['aliases'])
        self.assertIn('transliterations', arguments['instructions'])
        for invalid in ({'tmdb_id': 550}, {'aliases': ['https://example.invalid/movie']}, {'aliases': ['One'] * 4}):
            runner.run.return_value = CompletedResponse('fixture', '', [], [ToolCall('call', 'cp_result.submit', invalid)])
            with self.assertRaisesRegex(ChatGPTError, 'invalid_iptv_result'):
                inference.suggest_titles(selection, evidence, cancel=threading.Event())

    def test_classification_apply_keeps_entire_reviewed_set_and_preserves_locked_rows_for_gpt(self):
        rows = [{'stream_id': str(i), 'name': 'Object ' + str(i), 'category_id': 'movies-a'} for i in range(1001)]
        with tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT']) as root:
            raw = create_raw_service(root, 'a' * 32, movie_rows=rows)
            owner = IPTVMovieService(raw.root, 'a' * 32, raw, IPTVMetadataSettings(root))
            owner.start_projection(wait=True)
            locked = source_key('0')
            owner.store.apply_classification_decisions([{'source_key': locked, 'category': 'music', 'confidence': 1}], manual=True)
            proposals = [{'source_key': source_key(str(i)), 'category': 'film'} for i in range(1001)]
            outcome = owner.classification_apply({'catalog_generation': owner.store.source_generation(), 'proposals': proposals},
                                                  preserve_manual_locks=True)
            self.assertEqual(len(outcome['applied']), 1000)
            self.assertEqual(outcome['locked'], [locked])
            self.assertEqual(owner.store.source(locked)['category'], 'music')
            self.assertEqual(owner.store.source(source_key('1000'))['category'], 'film')

    def test_both_job_routes_require_recorded_confirmation_for_actual_provider_apply(self):
        from flask import Flask
        from services.ai_jobs import AIJobStore, AIJobService
        from services.ai_provider import AIProviderService
        from services.ai_routes import register_ai_routes
        from services.chatgpt_iptv import IPTVJob
        from services.chatgpt_domain_tools import DomainTools
        from services.iptv_routes import register_iptv_routes
        from services import ai_control
        from types import SimpleNamespace
        for feature, suffix in [('F4', 'classification-jobs'), ('F5', 'match-jobs')]:
            with self.subTest(feature=feature), tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT']) as root:
                title = 'Opaque catalogue title' if feature == 'F4' else 'Fixture Movie (2024)'
                raw = create_raw_service(root, 'a' * 32, movie_rows=[{'stream_id': '10', 'name': title, 'category_id': 'movies-a'}])
                owner = IPTVMovieService(raw.root, 'a' * 32, raw, IPTVMetadataSettings(root), tmdb_client_factory=lambda: FakeTMDBClient(),
                    ollama_runner=lambda value: self.fail('Ollama called'))
                owner.start_projection(wait=True)
                if feature == 'F5':
                    owner.store.apply_classification_decisions([{'source_key': source_key('10'), 'category': 'film',
                        'method': 'fixture', 'confidence': 1}])
                store = AIJobStore(root)
                calls = []
                def transport(selection, job_id):
                    class Runner:
                        def run(self, selected, **kwargs):
                            store.reserve_inference(job_id)
                            calls.append(kwargs['input_items'])
                            result = {'tmdb_id': 550} if selected.feature == 'F5' else {'category': 'Film', 'confidence': .95,
                                'mixed': False, 'uncertain': False, 'title_exceptions': [], 'evidence_summary': 'Synthetic'}
                            return CompletedResponse('fixture', '', [], [ToolCall('call', 'cp_result.submit', result)])
                    return Runner()
                plans = ai_control.PlanStore()
                def dispatch(endpoint, *, method, values, query, body):
                    url = application.url_map.bind('localhost').build(endpoint, values, method=method)
                    response = application.test_client().open(url, method=method, json=body, query_string=query)
                    self.assertLess(response.status_code, 400, response.json)
                    return response.json
                domain = DomainTools(store, None, plans, dispatch, iptv_factory=lambda identity: owner,
                    execute_movie=lambda identity, **options: ai_control.execute_plan(identity, plan_store=plans, **options))
                worker = IPTVJob(store, lambda identity: owner, transport, prepare_review=domain.prepare_iptv_job_review)
                jobs = AIJobService(store, {'F4': worker.run, 'F5': worker.run})
                config = {'ai_provider': 'chatgpt', 'chatgpt': {'active_account_id': 'account', 'model': 'fixture', 'allow_iptv_titles': True}}
                provider = AIProviderService(lambda: config, lambda data: None, skill_loader=load,
                    accounts=lambda: [{'account_id': 'account', 'connected': True, 'plan_enabled': True}])
                application = Flask('iptv-job-fixture-' + feature)
                register_iptv_routes(application, SimpleNamespace(service=lambda identity: raw, movie_service=lambda identity: owner,
                    redacted_error=lambda error, identity='': str(error)))
                register_ai_routes(application, provider, jobs_factory=lambda: jobs, iptv_factory=lambda identity: owner,
                                   control_factory=lambda: domain)
                try:
                    client = application.test_client()
                    response = client.post('/api/iptv/providers/' + owner.provider_id + '/movies/ai/' + suffix,
                        json={'selected_keys': ['source:' + source_key('10')], 'request_key': 'fixture'})
                    self.assertEqual(response.status_code, 202, response.json)
                    deadline = time.monotonic() + 3
                    while time.monotonic() < deadline:
                        operation = client.get('/api/ai/jobs/' + response.json['job_id']).json
                        if operation['state'] not in ('queued', 'running'):
                            break
                        time.sleep(.01)
                    self.assertEqual(operation['state'], 'completed', operation)
                    self.assertEqual(operation['accepted_count'], 1)
                    self.assertEqual(operation['run_calls'], 1)
                    self.assertTrue(operation['output']['review_required'])
                    self.assertNotIn('fixture-password', str(calls))
                    self.assertNotIn('provider.example', str(calls))
                    if feature == 'F4':
                        self.assertEqual(owner.store.source(source_key('10'))['category'], 'unclassified')
                    else:
                        self.assertEqual(operation['output']['review']['state'], 'ready')
                        self.assertEqual(operation['output']['review']['proposals'][0]['candidate_tmdb_id'], 550)
                        with owner.store.connection() as connection:
                            before = connection.execute('SELECT * FROM source_matches WHERE source_key=?', (source_key('10'),)).fetchone()
                            self.assertIsNone(before['tmdb_id'])
                    prepared = operation['output']['prepared_review']
                    action = prepared['action']
                    confirmed = client.post('/api/ai/control/plans/' + action['action_id'] + '/confirm', json={
                        'revision': action['revision'], 'selected_keys': ['item-1'], 'confirmation_phrase': '', 'request_key': 'confirm'})
                    self.assertEqual(confirmed.status_code, 200, confirmed.json)
                    self.assertEqual(confirmed.json['state'], 'completed', confirmed.json)
                    if feature == 'F4':
                        self.assertEqual(owner.store.source(source_key('10'))['category'], 'film')
                    else:
                        with owner.store.connection() as connection:
                            after = connection.execute('SELECT * FROM source_matches WHERE source_key=?', (source_key('10'),)).fetchone()
                            self.assertEqual(after['tmdb_id'], 550)
                            self.assertEqual(after['manual_lock'], 1)
                finally:
                    jobs.close()

    def test_paused_ranking_resumes_same_native_proposals_without_repeating_completed_source(self):
        from services.ai_jobs import AIJobError
        rows = [{'stream_id': str(i), 'category_id': 'movies-a', 'name': 'Fixture Movie (2024)'} for i in (1, 2)]
        with tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT']) as root:
            raw = create_raw_service(root, 'a' * 32, movie_rows=rows)
            service = IPTVMovieService(raw.root, 'a' * 32, raw, IPTVMetadataSettings(root),
                tmdb_client_factory=lambda: FakeTMDBClient())
            service.start_projection(wait=True)
            keys = [source_key(str(i)) for i in (1, 2)]
            service.store.apply_classification_decisions([{'source_key': key, 'category': 'film',
                'confidence': 1, 'method': 'fixture'} for key in keys])
            selection = service.store.resolve_selection(selected_keys=keys)
            native, calls = [], []
            def rank(evidence):
                calls.append(evidence)
                if len(calls) == 2:
                    raise AIJobError('paused_budget')
                return {'tmdb_id': 550}
            with self.assertRaises(AIJobError):
                service.create_match_job({'method': 'ai'}, ai_ranker=rank, selection_snapshot=selection,
                    on_created=native.append)
            self.assertEqual(len(service.match_job(native[0])['proposals']), 1)
            resumed = service.create_match_job({'method': 'ai'}, ai_ranker=rank, selection_snapshot=selection,
                resume_job_id=native[0])
            self.assertEqual(resumed['state'], 'ready')
            self.assertEqual(len(resumed['proposals']), 2)
            self.assertEqual({row['source_key'] for row in resumed['proposals']}, set(keys))
            self.assertEqual(len(calls), 3)

    def test_structured_classifier_reuses_validator_and_rejects_foreign_title_exceptions(self):
        from services.chatgpt_iptv import IPTVInference
        from services.chatgpt_transport import ChatGPTError
        from services.iptv_movie_classifier import validate_classification_result, validate_ollama_classification
        self.assertIs(validate_classification_result, validate_ollama_classification)
        skill = load('F4')
        selection = AISelection('chatgpt', 1, 'account', 'model', skill['id'], '1', skill['hash'], 'F4', 'provider-a')
        class Runner:
            def run(self, *args, **kwargs):
                return CompletedResponse('fake', '', [], [ToolCall('c', 'cp_result.submit', {
                    'category': 'Film', 'confidence': .99, 'evidence_summary': 'Synthetic', 'mixed': False, 'uncertain': False,
                    'title_exceptions': [{'title': 'Foreign title', 'category': 'Film', 'confidence': .99, 'evidence_summary': 'Foreign'}]})])
        with self.assertRaises(ChatGPTError):
            IPTVInference(Runner()).classify(selection, 'Unknown', ['Actual title'], cancel=threading.Event())

    def test_candidate_ranker_can_choose_only_actually_supplied_ids_and_preserves_locks(self):
        with tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT']) as root:
            raw = create_raw_service(root, 'a' * 32)
            service = IPTVMovieService(raw.root, 'a' * 32, raw, IPTVMetadataSettings(root))
            service.start_projection(wait=True)
            key = source_key('10')
            service.store.apply_classification_decisions([{'source_key': key, 'category': 'film',
                'confidence': 1, 'method': 'fixture'}])
            candidates = [tmdb_payload(i, 'Fixture Movie', 2024) for i in range(1, 10)]
            client = FakeTMDBClient(search_results=candidates)
            captured = []
            def rank(evidence):
                captured.append(evidence)
                return {'tmdb_id': 9}
            with patch('services.iptv_movie_service.bounded_search_candidates', return_value=(candidates, [])), \
                 self.assertRaisesRegex(ValueError, 'supplied'):
                service._proposal_for_source(key, client, method='ai', ai_ranker=rank)
            self.assertEqual(len(captured[0]['candidates']), 8)
            self.assertNotIn('fixture-password', str(captured))
            service.store.apply_match('source:' + key, client.normalized_movie(550), manual=True)
            calls = []
            result = service._proposal_for_source(key, client, method='ai', ai_ranker=lambda value: calls.append(value))
            self.assertEqual(result['recommendation'], 'locked')
            self.assertFalse(calls)

    def test_explicit_classification_can_reach_selected_row_beyond_first_5000(self):
        service = object.__new__(IPTVMovieService)
        service.provider_id = 'provider-a'
        store = Mock()
        store.resolve_selection.return_value = {'source_keys': ['late-row'], 'catalog_generation': 9, 'mode': 'explicit'}
        store.source.return_value = {'source_key': 'late-row', 'provider_title': 'Unidentified object',
            'provider_year': 0, 'playlist_name': 'Unknown collection', 'category': 'unclassified', 'classification_manual_lock': 0}
        service._store = store
        service._store_lock = threading.RLock()
        # The ready store property returns the explicitly injected store without opening a database.
        service._ready_store = lambda: store
        evidence = []
        def classify(playlist, titles):
            evidence.append((playlist, titles))
            return {'category': 'Film', 'confidence': .95, 'evidence_summary': 'Synthetic',
                    'mixed': False, 'uncertain': False, 'title_exceptions': [], 'status': 'classified'}
        result = service.classification_preview({'selected_keys': ['source:late-row']}, ai_classifier=classify,
            ai_provenance={'provider': 'chatgpt', 'model': 'fixture'})
        self.assertEqual([row['source_key'] for row in result['proposals']], ['late-row'])
        self.assertEqual(result['proposals'][0]['method'], 'chatgpt')
        self.assertEqual(result['proposals'][0]['category'], 'film')
        self.assertEqual(evidence[0][1], ['Unidentified object'])
        store.classification_rows.assert_not_called()
        store.apply_classification_decisions.assert_not_called()

    def test_classification_limits_each_model_batch_to_25_and_preserves_manual_locks(self):
        service = object.__new__(IPTVMovieService)
        service.provider_id = 'provider-a'
        store = Mock()
        keys = [str(i) for i in range(53)]
        store.resolve_selection.return_value = {'source_keys': keys, 'catalog_generation': 1, 'mode': 'explicit'}
        store.source.side_effect = lambda key: {'source_key': key, 'provider_title': 'Object ' + key,
            'provider_year': 0, 'playlist_name': 'Unknown', 'category': 'unclassified', 'classification_manual_lock': key == '0'}
        service._store = store
        service._store_lock = threading.RLock()
        service._ready_store = lambda: store
        sizes = []
        def classify(playlist, titles):
            sizes.append(len(titles))
            return {'category': 'Film', 'confidence': .95, 'evidence_summary': 'Synthetic',
                    'mixed': False, 'uncertain': False, 'title_exceptions': [], 'status': 'classified'}
        result = service.classification_preview({'selected_keys': keys}, ai_classifier=classify)
        self.assertEqual(sizes, [25, 25, 2])
        self.assertEqual(len(result['proposals']), 53)
        self.assertTrue(result['proposals'][0]['locked'])
        self.assertEqual(result['proposals'][0]['category'], 'unclassified')
