"""User-visible TV download contracts, using disposable stores and provider fixtures."""
import unittest
from unittest.mock import patch
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from tests import test_verified_tv_acquisition as fixtures
from services.tv_monitoring import TVMonitoring


class DownloadPolicyTests(unittest.TestCase):
    def setUp(self):
        import app
        self.app = app
        self.client = app.app.test_client()
        self.indexers = [{'id': 2, 'name': 'YTS'}, {'id': 7, 'name': 'LimeTorrents'}, {'id': 9, 'name': '1337x'}]
        for name, value in {
            '_download_trusted_indexers': [], '_download_trusted_indexers_configured': False,
            '_tv_download_trusted_indexers': [], '_tv_download_trusted_indexers_configured': False,
            '_download_indexer_mode': 'release', '_trusted_release_indexers': ['2'],
            '_download_legacy_policy_configured': True,
            '_trusted_release_indexers_configured': True,
            '_prowlarr_url': 'http://fixture.invalid', '_prowlarr_key': 'fixture',
        }.items():
            context = patch.object(app, name, value, create=True)
            context.start(); self.addCleanup(context.stop)
        for context in (patch('app._fetch_enabled_prowlarr_indexers', return_value=self.indexers), patch('app._save_config')):
            context.start(); self.addCleanup(context.stop)

    def test_independent_save_read_and_effective_tv_search_policy(self):
        response = self.client.post('/api/prowlarr/config', json={
            'download_trusted_indexers': ['2'], 'tv_download_trusted_indexers': ['7', '9', '7']})
        self.assertEqual(response.status_code, 200)
        data = self.client.get('/api/prowlarr/config').get_json()
        self.assertEqual(data['effective_download_trusted_indexers'], ['2'])
        self.assertEqual(data['effective_tv_download_trusted_indexers'], ['7', '9'])
        self.assertEqual(self.app._effective_tv_download_trusted_indexer_ids(), ['7', '9'])
        self.assertEqual(self.app._trusted_release_indexers, ['2'])
        self.assertEqual(data['url'], 'http://fixture.invalid')

    def test_empty_is_explicit_and_omission_preserves_it(self):
        self.client.post('/api/prowlarr/config', json={'tv_download_trusted_indexers': []})
        self.client.post('/api/prowlarr/config', json={'download_default_quality': '4K'})
        data = self.client.get('/api/prowlarr/config').get_json()
        self.assertTrue(data['tv_download_trusted_indexers_configured'])
        self.assertEqual(data['effective_tv_download_trusted_indexers'], [])
        self.assertEqual(data['effective_download_trusted_indexers'], ['2'])

    def test_bad_selection_is_atomic_and_unavailable_saved_ids_are_visible(self):
        for selected in ('7', ['999']):
            response = self.client.post('/api/prowlarr/config', json={'url': 'changed', 'tv_download_trusted_indexers': selected})
            self.assertEqual(response.status_code, 400)
            self.assertEqual(self.app._prowlarr_url, 'http://fixture.invalid')
        self.app._tv_download_trusted_indexers = ['999']
        self.app._tv_download_trusted_indexers_configured = True
        data = self.client.get('/api/prowlarr/config').get_json()
        self.assertEqual(data['tv_download_trusted_indexers'], ['999'])
        self.assertEqual(data['unavailable_tv_download_trusted_indexers'], ['999'])
        self.assertEqual(data['effective_tv_download_trusted_indexers'], [])

    def test_legacy_movie_modes_preserve_effective_behavior_until_explicit_save(self):
        self.app._download_indexer_mode = 'all'
        self.assertEqual(self.app._effective_download_trusted_indexer_ids(self.indexers), ['2', '7', '9'])
        self.client.post('/api/prowlarr/config', json={'download_trusted_indexers': []})
        self.assertEqual(self.app._effective_download_trusted_indexer_ids(self.indexers), [])
        self.assertEqual(self.app._effective_tv_download_trusted_indexer_ids(), [])

    def test_failed_persistence_preserves_previous_effective_source_selection(self):
        with patch('app._save_config', side_effect=OSError('fixture disk failure')):
            response = self.client.post('/api/prowlarr/config', json={'tv_download_trusted_indexers':['7']})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(self.app._tv_download_trusted_indexers, [])
        self.assertFalse(self.app._tv_download_trusted_indexers_configured)


class AutomaticPreparationTests(unittest.TestCase):
    setUp = fixtures.TVAcquisitionTests.setUp
    tearDown = fixtures.TVAcquisitionTests.tearDown

    def unresolved(self):
        return {'title': self.filename, 'tmdbId': 900001, 'downloadUrl': 'http://prowlarr.invalid/7/download',
                'indexerId': 7, 'seeders': 20, 'size': 1000}

    def test_supported_automatic_link_is_prepared_without_hash_bypass(self):
        from unittest.mock import Mock
        self.provider.search_tv.return_value = [self.unresolved()]
        self.service.resolve_candidate = Mock(return_value={'info_hash': self.hash, 'magnet_url': 'magnet:?xt=urn:btih:'+self.hash, 'download_url': '', 'transport_verified': True})
        review = self.service.search(self.series, 1, 1, manual=False)
        result = self.service.select_automatic(review)
        self.assertTrue(result['decision']['accepted'])
        self.assertFalse(result['decision']['manual'])
        self.service.resolve_candidate.assert_called_once()
        self.manager.client.add_magnet.assert_not_called()
        self.service.submit(result['decision']['decision_token'], 'automatic-link')
        self.manager.client.add_magnet.assert_called_once()

    def test_rejected_identity_quality_and_untrusted_sources_never_resolve(self):
        from unittest.mock import Mock
        self.provider.search_tv.return_value = [
            {**self.unresolved(), 'tmdbId': 88},
            {**self.unresolved(), 'title': 'Harbor.Signals.S01E01.1080p.HDCAM'},
            {**self.unresolved(), 'indexerId': 99, 'downloadUrl': 'http://prowlarr.invalid/99/download'}]
        self.service.resolve_candidate = Mock()
        result = self.service.select_automatic(self.service.search(self.series, 1, 1, manual=False))
        self.assertIsNone(result['decision'])
        self.assertEqual(result['state'], 'rejected_sources')
        self.service.resolve_candidate.assert_not_called()

    def test_resolution_is_bounded_and_failures_are_not_empty_catalog(self):
        from unittest.mock import Mock
        self.provider.search_tv.return_value = [{**self.unresolved(), 'downloadUrl': f'http://prowlarr.invalid/7/download?id={n}'} for n in range(8)]
        self.service.resolve_candidate = Mock(side_effect=ValueError('invalid torrent identity'))
        result = self.service.select_automatic(self.service.search(self.series, 1, 1, manual=False))
        self.assertEqual(self.service.resolve_candidate.call_count, 5)
        self.assertEqual(result['state'], 'preparation_failed')
        self.assertEqual(result['result_count'], 8)

    def test_trust_removed_after_search_invalidates_automatic_submit(self):
        decision = self.service.search(self.series, 1, 1, manual=False)['decisions'][0]
        self.service.trusted_indexers = lambda: []
        with self.assertRaisesRegex(ValueError, 'trusted'):
            self.service.submit(decision['decision_token'], 'stale-trust')
        self.manager.client.add_magnet.assert_not_called()

    def test_provider_failure_and_hash_swap_remain_distinct_rejections(self):
        from unittest.mock import Mock
        self.provider.search_tv.return_value = [{**self.unresolved(), 'infoHash': self.hash}]
        self.service.resolve_candidate = Mock(return_value={'info_hash':'b'*40,'transport_verified':True})
        result = self.service.select_automatic(self.service.search(self.series, 1, 1, manual=False))
        self.assertEqual(result['state'], 'preparation_failed')
        self.assertIn('differs', result['error'])
        self.assertEqual(self.service.select_automatic({'decisions':[], 'search':{'partial':True}})['state'], 'provider_failed')
        self.manager.client.add_magnet.assert_not_called()


class FollowScheduleTests(unittest.TestCase):
    setUp = fixtures.TVAcquisitionTests.setUp
    tearDown = fixtures.TVAcquisitionTests.tearDown

    def monitor(self, instant):
        self.now = [instant]
        return TVMonitoring(self.tv, self.store, self.service, clock=lambda: self.now[0])

    def test_blocked_draft_is_saved_and_start_retains_actionable_error(self):
        self.service.trusted_indexers = lambda: []
        monitor = self.monitor(datetime(2026, 10, 8, tzinfo=ZoneInfo('Africa/Cairo')).timestamp())
        preview = monitor.preview(self.series)
        self.assertFalse(preview['readiness']['ready'])
        self.assertIn('Select TV trusted indexers in Settings', preview['readiness']['blockers'])
        draft = monitor.save_task(self.series)
        with self.assertRaisesRegex(ValueError, 'trusted indexers'): monitor.start_task(draft['id'])
        self.assertEqual(monitor.task(draft['id'])['state'], 'draft')
        self.assertIn('Settings', monitor.task(draft['id'])['error'])
        self.manager.client.add_magnet.assert_not_called()

    def test_missing_retries_after_exactly_five_elapsed_hours_and_restart_once(self):
        now = datetime(2026, 10, 8, tzinfo=ZoneInfo('Africa/Cairo')).timestamp()
        monitor = self.monitor(now)
        self.provider.search_tv.return_value = []
        task = monitor.start_task(monitor.save_task(self.series, scope='season', season=1)['id'])
        monitor.run_once(limit=1)
        episode = monitor.task(task['id'])['episodes'][0]
        self.assertEqual(episode['next_retry'] - episode['last_search'], 18000)
        self.now[0] += 17999
        # Bound to the already-searched episode to isolate the retry boundary.
        with self.store.transaction() as db: db.execute('DELETE FROM tv_task_episodes WHERE task_id=? AND episode_id<>?', (task['id'], episode['episode_id']))
        self.assertEqual(monitor.run_once(limit=1), [])
        self.now[0] += 1
        self.assertEqual(len(monitor.run_once(limit=1)), 1)
        self.now[0] += 54000
        restarted = TVMonitoring(self.tv, self.store, self.service, clock=lambda: self.now[0])
        self.assertEqual(len(restarted.run_once(limit=1)), 1)
        self.assertEqual(restarted.run_once(limit=1), [])

    def test_queued_is_not_acquired_until_binding_and_never_submits_again(self):
        now = datetime(2026, 10, 8, tzinfo=ZoneInfo('Africa/Cairo')).timestamp()
        monitor = self.monitor(now)
        task = monitor.start_task(monitor.save_task(self.series, scope='episodes', action='selected', selected_episodes=[self.tv.episodes(self.series, 1)[0]['id']])['id'])
        monitor.run_once(limit=1, submit=True)
        queued = monitor.task(task['id'])
        self.assertEqual(queued['counts']['queued'], 1)
        self.assertEqual(queued['counts']['acquired'], 0)
        self.now[0] += 20000
        monitor.run_once(limit=1, submit=True)
        self.manager.client.add_magnet.assert_called_once()
        # A ready intent alone (including a partial import) cannot prove this episode was imported.
        self.store.event(queued['episodes'][0]['intent_id'], 'partial_import', state='ready')
        self.now[0] += 60
        monitor.run_once(limit=1, submit=True)
        self.assertEqual(monitor.task(task['id'])['counts']['acquired'], 0)
        self.assertEqual(monitor.task(task['id'])['counts']['review'], 1)

    def test_other_worker_lease_prevents_overlap(self):
        now = datetime(2026, 10, 8, tzinfo=ZoneInfo('Africa/Cairo')).timestamp()
        monitor = self.monitor(now)
        monitor.start_task(monitor.save_task(self.series, scope='season', season=1)['id'])
        self.store.lease('tv-monitoring-pass', 'other-worker', ttl=1800)
        self.assertEqual(monitor.run_once(submit=True), [])
        self.provider.search_tv.assert_not_called()

    def test_missing_timezone_blocks_start_and_existing_worker_without_local_fallback(self):
        monitor = self.monitor(datetime(2026, 10, 8, tzinfo=ZoneInfo('Africa/Cairo')).timestamp())
        task = monitor.start_task(monitor.save_task(self.series, scope='season', season=1)['id'])
        blocked = TVMonitoring(self.tv, self.store, self.service, clock=lambda: self.now[0], timezone='Missing/Fixture')
        self.assertEqual(blocked.run_once(submit=True), [])
        self.assertEqual(blocked.task(task['id'])['state'], 'needs_review')
        self.assertIn('tzdata', blocked.task(task['id'])['error'])
        draft = blocked.save_task(self.series, scope='season', season=1)
        with self.assertRaisesRegex(ValueError, 'tzdata'): blocked.start_task(draft['id'])
        self.provider.search_tv.assert_not_called()

    def test_lost_submission_acknowledgement_recovers_same_intent_after_restart(self):
        from services.qbittorrent import QBittorrentError
        monitor = self.monitor(datetime(2026, 10, 8, tzinfo=ZoneInfo('Africa/Cairo')).timestamp())
        task = monitor.start_task(monitor.save_task(self.series, scope='episodes', action='missing', selected_episodes=[self.tv.episodes(self.series, 1)[0]['id']])['id'])
        present = []
        self.manager.client.torrents.side_effect = lambda: list(present)
        def lost_ack(*args, **kwargs):
            present.append(self.torrent)
            raise QBittorrentError('lost acknowledgement')
        self.manager.client.add_magnet.side_effect = lost_ack
        monitor.run_once(limit=1, submit=True)
        first = monitor.task(task['id'])['episodes'][0]
        self.assertIsNotNone(first['intent_id'])
        self.assertEqual(first['state'], 'needs_review')
        self.now[0] += 18000
        restarted = TVMonitoring(self.tv, self.store, self.service, clock=lambda: self.now[0])
        restarted.run_once(limit=1, submit=True)
        recovered = restarted.task(task['id'])
        self.assertEqual(recovered['counts']['queued'], 1, recovered['episodes'])
        self.manager.client.add_magnet.assert_called_once()
        with self.store.connection() as db: self.assertEqual(db.execute('SELECT COUNT(*) FROM intents').fetchone()[0], 1)

    def test_future_first_search_is_cairo_midnight_including_both_dst_boundaries(self):
        for day in ('2026-10-15', '2026-04-24', '2026-10-30'):
            with self.subTest(day=day):
                zone = ZoneInfo('Africa/Cairo'); boundary = datetime.fromisoformat(day).replace(tzinfo=zone).timestamp()
                metadata = self.tv.series(self.series)
                self.tv.refresh({**metadata, 'status': 'Returning Series'}, [
                    {**row, 'air_date': day if row['season_number'] == 1 and row['episode_number'] == 1 else row['air_date']}
                    for row in self.tv.episodes(self.series)])
                monitor = self.monitor(boundary - 1)
                self.provider.search_tv.return_value = []
                task = monitor.start_task(monitor.save_task(self.series, action='future', scope='episodes', selected_episodes=[self.tv.episodes(self.series, 1)[0]['id']])['id'])
                self.provider.search_tv.reset_mock()
                self.assertEqual(monitor.run_once(limit=1), [])
                self.assertEqual(monitor.task(task['id'])['episodes'][0]['next_retry'], boundary)
                self.now[0] = boundary
                with self.store.transaction() as db: db.execute('UPDATE tv_tasks SET next_due=0 WHERE id=?', (task['id'],))
                result = monitor.run_once(limit=1)
                self.assertEqual(len(result), 1)
                self.assertEqual(monitor.task(task['id'])['episodes'][0]['next_retry'], boundary+18000)
                with self.store.transaction() as db: db.execute("UPDATE tv_tasks SET state='cancelled' WHERE id=?", (task['id'],))
