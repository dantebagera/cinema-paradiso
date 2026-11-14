import copy
import unittest
from services.ai_provider import AIProviderService, AIProviderError, canonical_count


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.config = {'ollama_candidate_limit': 37, 'ollama_model': 'legacy', 'unrelated': {'keep': True}}
        self.profiles = [{'account_id': 'account-a', 'connected': True, 'plan_enabled': True}]
        self.dependencies = {}
        self.service = AIProviderService(lambda: copy.deepcopy(self.config), self.save,
            accounts=lambda: self.profiles, skill_loader=lambda feature: {
                'id': feature, 'version': '1', 'hash': 'fixture'},
            dependencies=lambda feature, domain: self.dependencies.get(feature))

    def save(self, value):
        self.config = copy.deepcopy(value)

    def ready(self):
        return self.service.update_config({'provider': 'chatgpt', 'active_account_id': 'account-a',
            'chatgpt_model': 'available-model', 'allow_movie_identity_hints': True,
            'allow_iptv_titles': True}, 0)

    def test_legacy_defaults_do_not_load_accounts_or_gpt_skills(self):
        self.service.accounts = lambda: self.fail('Ollama must not read GPT credentials')
        self.service.skill_loader = lambda feature: self.fail('Ollama must not load GPT resources')
        self.assertEqual(self.service.public_config()['provider'], 'ollama')
        self.assertEqual(self.service.snapshot('F1').provider, 'ollama')

    def test_config_is_additive_exact_and_compare_and_swap(self):
        original = copy.deepcopy(self.config)
        self.ready()
        self.service.update_config({'recommendation_count': '9007199254740993'}, 1)
        self.assertEqual(self.service.public_config()['chatgpt']['recommendation_count'], '9007199254740993')
        for key, value in original.items():
            self.assertEqual(self.config[key], value)
        with self.assertRaises(AIProviderError):
            self.service.update_config({'provider': 'ollama'}, 0)
        self.assertEqual(self.service.public_config()['provider'], 'chatgpt')

    def test_count_has_no_arbitrary_upper_bound_or_rounding(self):
        for value in [15, 75, 1000, '9007199254740993', '1' + '0' * 500]:
            self.assertEqual(canonical_count(value), str(value))
        self.assertEqual(canonical_count('00015'), '15')
        for invalid in [True, False, 0, -1, 1.5, 15.0, '0', '-2', '1e3', '3.1', None, [], '']:
            with self.subTest(value=invalid), self.assertRaises(AIProviderError):
                canonical_count(invalid)

    def test_invalid_atomic_update_and_save_failure_preserve_config(self):
        before = copy.deepcopy(self.config)
        for payload in [{'provider': 'unknown'}, {'unknown': 1}, {'allow_iptv_titles': 'true'},
                        {'recommendation_count': 0}, {'provider': 'chatgpt', 'active_account_id': 'other'}]:
            with self.assertRaises(AIProviderError):
                self.service.update_config(payload, 0)
            self.assertEqual(self.config, before)

    def test_all_six_features_are_ready_without_ollama(self):
        self.ready()
        features = self.service.features(domain_id='iptv-a')
        self.assertEqual([f['id'] for f in features], ['F1', 'F2', 'F3', 'F4', 'F5', 'F6'])
        self.assertTrue(all(f['ready'] for f in features))
        self.config['ollama_model'] = ''
        self.assertEqual(self.service.snapshot('F5', domain_id='iptv-a').model, 'available-model')

    def test_nested_feature_retains_parent_binding_but_rechecks_evidence_permission(self):
        self.ready()
        parent = self.service.snapshot('F2')
        self.service.update_config({'provider': 'ollama', 'chatgpt_model': 'later-model'}, 1)
        nested = self.service.for_feature(parent, 'F5', domain_id='provider-a')
        self.assertEqual(nested.provider, 'chatgpt')
        self.assertEqual(nested.model, parent.model)
        self.assertEqual(nested.config_generation, parent.config_generation)
        self.assertEqual(nested.feature, 'F5')
        self.assertEqual(nested.domain_id, 'provider-a')
        self.service.update_config({'allow_iptv_titles': False}, 2)
        with self.assertRaises(AIProviderError):
            self.service.for_feature(parent, 'F5', domain_id='provider-a')

    def test_saved_iptv_context_requires_current_evidence_permission(self):
        self.ready()
        self.service.check_evidence_scopes(['iptv_titles'])
        self.service.update_config({'allow_iptv_titles': False}, 1)
        with self.assertRaises(AIProviderError):
            self.service.check_evidence_scopes(['iptv_titles'])

    def test_permission_and_domain_dependency_reasons_are_independent(self):
        self.ready()
        self.service.update_config({'allow_iptv_titles': False, 'allow_movie_identity_hints': False}, 1)
        self.assertTrue(self.service.readiness('F1')['ready'])
        for feature in ('F3', 'F4', 'F5'):
            self.assertEqual(self.service.readiness(feature)['reason'], 'consent_required')
        self.service.update_config({'allow_iptv_titles': True}, 2)
        self.dependencies['F5'] = 'integration_missing'
        self.assertEqual(self.service.readiness('F5', 'iptv-a')['reason'], 'integration_missing')

    def test_selection_is_immutable_and_retains_account_model_and_generation(self):
        self.ready()
        selected = self.service.snapshot('F1')
        self.service.update_config({'chatgpt_model': 'next-model'}, 1)
        self.assertEqual(selected.model, 'available-model')
        self.assertEqual(selected.config_generation, 1)
        self.assertEqual(selected.account_id, 'account-a')
        with self.assertRaises(AttributeError):
            selected.model = 'changed'

