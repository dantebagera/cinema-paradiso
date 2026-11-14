import unittest
from types import SimpleNamespace
from flask import Flask
from services.ai_provider import AIProviderService
from services.ai_routes import register_ai_routes


class RoutesTests(unittest.TestCase):
    def setUp(self):
        self.config = {}
        self.service = AIProviderService(lambda: self.config.copy(), lambda value: self.config.update(value))
        self.app = Flask(__name__)
        register_ai_routes(self.app, self.service)
        self.client = self.app.test_client()

    def test_public_config_and_exact_count_roundtrip(self):
        self.assertEqual(self.client.get('/api/ai/config').json['provider'], 'ollama')
        response = self.client.put('/api/ai/config', json={'expected_generation': 0,
            'provider': 'chatgpt', 'recommendation_count': '9007199254740993'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['chatgpt']['recommendation_count'], '9007199254740993')
        self.assertEqual([feature['id'] for feature in self.client.get('/api/ai/features').json['features']],
                         ['F1', 'F2', 'F3', 'F4', 'F5', 'F6'])

    def test_bulk_start_calculates_the_confirmed_request_ceiling(self):
        from unittest.mock import Mock
        from services.ai_provider import AISelection
        account = AISelection('chatgpt', 1, 'fixture', 'model', 'skill', '1', 'hash', 'F5', 'provider')
        store = Mock()
        store.create.side_effect = lambda feature, selection, payload, key: {
            'id': key, 'state': 'queued', 'request': payload, 'cursor': {}, 'accepted_count': 0}
        catalog = Mock()
        catalog.resolve_selection.return_value = {'source_keys': list(range(6413)), 'catalog_generation': 7}
        app = Flask(__name__)
        register_ai_routes(app, SimpleNamespace(snapshot=lambda *args, **kw: account),
            jobs_factory=lambda: SimpleNamespace(store=store, start=lambda _: None),
            iptv_factory=lambda _: SimpleNamespace(store=catalog))
        client = app.test_client()
        path = '/api/iptv/providers/provider/movies/ai/bulk-jobs'
        def start(size, count):
            return client.post(path, json={'titles_per_request': size, 'expected_source_count': count,
                                          'request_key': f'{size}-{count}'})
        for size, initial, expected in [(100, 65, 969), (50, 129, 1161)]:
            result = start(size, 6413)
            self.assertEqual(result.status_code, 202, result.json)
            self.assertEqual(result.json['request'], {'bulk_call_budget': expected, 'titles_per_request': size})
            self.assertTrue(result.json['bulk']['automatic'])
            self.assertFalse(result.json['bulk']['recovery_enabled'])
            self.assertEqual(result.json['bulk']['estimated_first_pass_requests'], initial)
        explicit = client.post(path, json={'call_budget': 2, 'request_key': 'explicit'})
        self.assertEqual(explicit.json['request']['bulk_call_budget'], 2)
        self.assertTrue(explicit.json['bulk']['automatic'])
        self.assertFalse(explicit.json['bulk']['recovery_enabled'])
        self.assertNotIn('bulk_recovery_protocol_hash', store.create.call_args.args[2])
        self.assertEqual(start(100, 6400).json['error']['actual_count'], 6413)
        for size in (0, 101, True, 12.5):
            self.assertEqual(start(size, 6413).status_code, 400)
        catalog.resolve_selection.return_value['source_keys'] = list(range(10001))
        self.assertEqual(start(1, 10001).json['error']['minimum_titles_per_request'], 2)

    def test_local_json_and_unknown_fields_and_generation_are_enforced(self):
        for kwargs in [{'json': {'expected_generation': 0}, 'headers': {'Origin': 'https://evil.test'}},
                       {'data': '{}', 'content_type': 'text/plain'},
                       {'json': {'expected_generation': 0, 'token': 'never-allowed'}}]:
            self.assertIn(self.client.put('/api/ai/config', **kwargs).status_code, (400, 403, 415))
        self.assertEqual(self.client.put('/api/ai/config', json={'expected_generation': 99}).status_code, 409)

    def test_new_reads_reject_foreign_origins_and_selected_gpt_cannot_fall_through_to_ollama(self):
        self.assertEqual(self.client.get('/api/ai/config', headers={'Origin': 'https://foreign.invalid'}).status_code, 403)
        self.service.update_config({'provider': 'chatgpt'}, 0)
        self.assertEqual(self.client.post('/api/ollama/recommend', json={'prompt': 'A film'}).status_code, 409)

    def test_actual_app_composes_generic_routes_without_new_ollama_io(self):
        from tests.ai_provider_server import OfflineGuard
        with OfflineGuard():
            import app
            response = app.app.test_client().get('/api/ai/config')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json['provider'], 'ollama')

    def test_pinned_cloud_evidence_permission_is_rechecked_after_consent_is_removed(self):
        from unittest.mock import patch
        from services.ai_provider import AISelection, AIProviderError
        from tests.ai_provider_server import OfflineGuard
        with OfflineGuard():
            import app
            account = {'account_id': 'account', 'connected': True, 'plan_enabled': True}
            auth = SimpleNamespace(credentials=SimpleNamespace(profiles=lambda: [account]))
            with patch.object(app, '_get_chatgpt_auth', return_value=auth), patch.object(app, '_ai_provider_config', {'chatgpt': {}}):
                for feature in ('F3', 'F4', 'F5'):
                    with self.assertRaises(AIProviderError):
                        app._ai_check_permission(AISelection('chatgpt', 1, 'account', 'model', 'skill', '1', 'hash', feature))
                self.assertEqual(app._ai_tool_availability({'namespace': 'cp_metadata', 'domain': 'movie',
                    'name': 'maintenance_status'}, None), 'consent_required')

    def test_data_root_change_stops_old_owners_and_requires_fresh_account_selection_without_copying_credentials(self):
        from unittest.mock import Mock, patch
        from tests.ai_provider_server import OfflineGuard
        with OfflineGuard():
            import app
            jobs, auth = Mock(), Mock()
            config = {'chatgpt': {'active_account_id': 'account', 'model': 'model', 'recommendation_count': '120'}}
            with patch.multiple(app, _ai_job_service_owner=jobs, _ai_job_service_root='old',
                _chatgpt_auth_owner=auth, _chatgpt_auth_root='old-auth', _ai_job_store_owner=Mock(),
                _ai_job_store_root='old-store', _ai_provider_config=config):
                app._stop_ai_for_data_root_change()
                jobs.close.assert_called_once_with()
                auth.close.assert_called_once_with()
                self.assertIsNone(app._ai_job_service_owner)
                self.assertIsNone(app._chatgpt_auth_owner)
                self.assertIsNone(config['chatgpt']['active_account_id'])
                self.assertEqual(config['chatgpt']['model'], '')
                self.assertEqual(config['chatgpt']['recommendation_count'], '120')

    def test_provider_config_publication_never_exposes_a_half_cleared_ollama_default(self):
        from unittest.mock import patch
        from tests.ai_provider_server import OfflineGuard
        with OfflineGuard():
            import app
            observations = []
            class ObservedConfig(dict):
                def clear(self):
                    super().clear()
                    observations.append(app._ai_provider_config.get('ai_provider', 'ollama'))
            original = ObservedConfig(ai_provider='chatgpt', chatgpt={'model': 'old'}, ai_config_generation=1)
            with patch.multiple(app, _ai_provider_config=original), patch.object(app, '_save_config'), \
                 patch.object(app, '_load_config', return_value={}), patch.object(app, '_all_config', return_value={}):
                app._save_ai_provider_config({'ai_provider': 'chatgpt', 'chatgpt': {'model': 'new'}, 'ai_config_generation': 2})
                self.assertNotIn('ollama', observations)
                self.assertEqual(app._ai_provider_config['chatgpt']['model'], 'new')

    def test_auth_routes_keep_tokens_private_and_use_explicit_model_test(self):
        profiles = [{'account_id': 'account-a', 'connected': True, 'plan_enabled': True}]
        auth = SimpleNamespace(
            start=lambda **kwargs: {'attempt_id': 'attempt-a', 'expires_at': 1000},
            status=lambda attempt: {'state': 'complete', 'account_id': 'account-a', 'plan_enabled': True},
            cancel=lambda attempt: None,
            sign_out=lambda account: {'account_id': account, 'remote_revocation_confirmed': False},
        )
        calls = []
        def infer(selection, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(text='CP_CONNECTION_OK', response_id='resp_fake')
        transport = SimpleNamespace(list_models=lambda selection: [{'slug': 'model-a', 'display_name': 'Model A'}], run=infer)
        config = {}
        service = AIProviderService(lambda: config.copy(), lambda value: config.update(value), accounts=lambda: profiles)
        app = Flask('auth-fixture')
        register_ai_routes(app, service, auth_factory=lambda: auth, transport_factory=lambda: transport)
        client = app.test_client()
        start = client.post('/api/ai/auth/start', json={})
        self.assertEqual(start.status_code, 200)
        self.assertNotIn('authorization_url', start.json)
        self.assertEqual(client.get('/api/ai/auth/attempts/attempt-a').json['state'], 'complete')
        self.assertEqual(client.post('/api/ai/accounts/select', json={'account_id': 'account-a', 'expected_generation': 0}).status_code, 200)
        self.assertEqual(client.get('/api/ai/models').json['models'][0]['slug'], 'model-a')
        self.assertFalse(calls)
        client.put('/api/ai/config', json={'expected_generation': 1, 'chatgpt_model': 'model-a'})
        result = client.post('/api/ai/test', json={})
        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.json['success'])
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]['input_items'], [{'role': 'user', 'content': 'Say exactly: CP_CONNECTION_OK'}])
        self.assertEqual(client.delete('/api/ai/accounts/account-a/session', json={}).status_code, 200)

    def test_recommendation_route_uses_saved_target_and_explicit_override_without_settings_mutation(self):
        import os
        import tempfile
        from services.ai_jobs import AIJobStore
        from services.chatgpt_skills import load
        with tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT']) as root:
            config = {'ai_provider': 'chatgpt', 'chatgpt': {'active_account_id': 'account-a',
                'model': 'model-a', 'recommendation_count': '75'}}
            service = AIProviderService(lambda: config.copy(), lambda value: config.update(value),
                accounts=lambda: [{'account_id': 'account-a', 'connected': True, 'plan_enabled': True}], skill_loader=load)
            jobs = SimpleNamespace(store=AIJobStore(root), start=lambda job_id: None)
            app = Flask('job-fixture')
            register_ai_routes(app, service, jobs_factory=lambda: jobs)
            client = app.test_client()
            default = client.post('/api/ai/recommendations', json={'prompt': 'Synthetic', 'request_key': 'default'})
            self.assertEqual(default.status_code, 202)
            self.assertEqual(default.json['requested_count'], '75')
            explicit = client.post('/api/ai/recommendations', json={'prompt': 'Synthetic',
                'count': '1000', 'request_key': 'explicit'})
            self.assertEqual(explicit.status_code, 202)
            self.assertEqual(explicit.json['requested_count'], '1000')
            self.assertEqual(config['chatgpt']['recommendation_count'], '75')
            self.assertEqual(client.get('/api/ai/jobs/' + explicit.json['id']).status_code, 200)
