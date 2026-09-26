import copy
from pathlib import Path
import tempfile
import unittest

from services.acquisition_decision import evaluate_release, rank_releases, shadow_compare
from services.acquisition_profiles import default_profile
from services.acquisition_store import AcquisitionRepository
from services.quality_catalog import release_claims


class AcquisitionDecisionTests(unittest.TestCase):
    def setUp(self):
        self.profile = default_profile()
        self.target = {'key': 'movie:tmdb:42', 'media_type': 'movie', 'released': True}
        self.candidate = {'title': 'Example.2020.1080p.WEB-DL', 'info_hash': 'a'*40, 'identity_verified': True, 'transport_verified': True, 'trusted_indexer': True, 'availability_verified': True, 'size_bytes': 2_000_000_000, 'seeders': 20}

    def test_verified_web_dl_does_not_require_yts(self):
        result = evaluate_release(self.candidate, self.target, self.profile)
        self.assertTrue(result['accepted'])
        self.assertEqual(result['claim']['source'], 'web_dl')
        self.assertEqual(result['measured_facts'], {})

    def test_captures_screeners_and_fake_labels_are_distinct_hard_blocks(self):
        for title in ('Example.1080p.HDCAM', 'Example.1080p.DVDScr'):
            result = evaluate_release({**self.candidate, 'title': title}, self.target, self.profile, manual=True)
            self.assertFalse(result['accepted'])
            self.assertIn('quality_blocked', [r['code'] for r in result['reasons']])
        result = evaluate_release({**self.candidate, 'title': 'Example.1080p.BluRay', 'manifest_names': ['Example.1080p.HDCAM.mkv']}, self.target, self.profile, manual=True)
        self.assertEqual(result['source_confidence'], 'contradictory')
        self.assertFalse(result['accepted'])

    def test_manual_only_cutoff_and_measured_ownership(self):
        self.profile['states']['web_dl:1080p'] = 'manual_only'
        self.assertFalse(evaluate_release(self.candidate, self.target, self.profile)['accepted'])
        self.assertTrue(evaluate_release(self.candidate, self.target, self.profile, manual=True)['accepted'])
        self.profile['states']['web_dl:1080p'] = 'allowed'
        self.assertFalse(evaluate_release(self.candidate, self.target, self.profile, owned=[{'quality_class': '720p'}])['accepted'])
        self.profile['automatic_upgrades'] = True
        self.assertTrue(evaluate_release(self.candidate, self.target, self.profile, owned=[{'quality_class': '720p'}])['accepted'])
        self.assertFalse(evaluate_release(self.candidate, self.target, self.profile, owned=[{'quality_class': '1080p'}])['accepted'])

    def test_shadow_is_deterministic_and_does_not_mutate_inputs(self):
        candidates = [self.candidate, {**self.candidate, 'info_hash': 'b'*40, 'seeders': 2}]
        before = copy.deepcopy(candidates)
        first = shadow_compare(candidates, self.target, self.profile, 'a'*40)
        second = shadow_compare(list(reversed(candidates)), self.target, self.profile, 'a'*40)
        self.assertEqual(first, second)
        self.assertEqual(candidates, before)
        self.assertTrue(first['selection_matches'])

    def test_identity_safety_and_episode_coverage_are_not_manually_overridable(self):
        target = {'key': 'episode:tmdb:tv:1:1:2', 'media_type': 'tv', 'released': True, 'episode_ids': [2]}
        result = evaluate_release({**self.candidate, 'identity_verified': False, 'episode_ids': [1]}, target, self.profile, manual=True)
        self.assertFalse(result['accepted'])
        self.assertIn('coverage_missing', [r['code'] for r in result['reasons']])
        self.assertIn('identity_unverified', [r['code'] for r in result['reasons']])

    def test_profile_reference_deletion_leases_expiry_and_idempotency(self):
        with tempfile.TemporaryDirectory() as root:
            now = [100]
            store = AcquisitionRepository(Path(root)/'acquisition.sqlite', clock=lambda: now[0])
            with self.assertRaises(ValueError):
                store.delete_profile('cp-compatibility')
            decision = evaluate_release(self.candidate, self.target, self.profile)
            store.record_decision(decision)
            first = store.intent('request-1', decision)
            self.assertEqual(store.intent('request-1', decision)['id'], first['id'])
            with self.assertRaises(ValueError):
                store.intent('request-2', decision)
            self.assertTrue(store.lease('episode:1', 'worker-a', ttl=10, reserved_bytes=80, available_bytes=100))
            self.assertFalse(store.lease('episode:1', 'worker-b', ttl=10))
            self.assertFalse(store.lease('episode:2', 'worker-b', ttl=10, reserved_bytes=30, available_bytes=100))
            now[0] = 111
            self.assertTrue(store.lease('episode:1', 'worker-b', ttl=10))
            store.block(self.target['key'], 'a'*40, 'corrupt', ttl=10)
            self.assertTrue(store.blocked(self.target['key'], 'a'*40))
            now[0] = 122
            self.assertFalse(store.blocked(self.target['key'], 'a'*40))


class SourceContainerTests(unittest.TestCase):
    def test_transport_stream_extension_is_not_a_telesync_claim(self):
        from services.quality_catalog import source_claim
        self.assertEqual(source_claim('Harbor.S01E01.1080p.HDTV.ts'), 'hdtv')
        self.assertEqual(source_claim('Harbor.S01E01.1080p.TS.mkv'), 'ts')
