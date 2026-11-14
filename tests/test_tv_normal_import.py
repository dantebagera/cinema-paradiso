"""New TV jobs publish verified episodes before removing their staging copies."""
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from tests import test_verified_tv_acquisition as fixtures
from services.tv_monitoring import TVMonitoring
from services.qbittorrent import QBittorrentJobStore
from services.verified_import import import_verified_files, rollback_verified_files


class TVNormalImportTests(unittest.TestCase):
    setUp = fixtures.TVAcquisitionTests.setUp
    tearDown = fixtures.TVAcquisitionTests.tearDown
    submit = fixtures.TVAcquisitionTests.submit

    def complete(self):
        self.manager.process_completed()
        self.torrent['progress'] = 1
        return self.manager.process_completed()[0]

    def test_manual_preview_and_submission_use_approved_season_and_normal_lifecycle(self):
        preview = self.service.search(self.series, 1, 1)
        self.assertEqual(preview['import_destination']['path'], str(self.home / 'Season 01'))
        self.assertEqual(preview['import_policy'], {'version': 1, 'mode': 'move', 'seeding_mode': 'none'})
        for profile in ('safe-hd', 'cp-compatibility'):
            review = self.service.search(self.series, 1, 1, profile_id=profile)
            self.assertEqual(review['import_policy']['mode'], 'move')
        submitted = self.service.submit(preview['decisions'][0]['decision_token'], 'request-1')
        self.assertEqual(submitted['job']['destination'], str(self.home / 'Season 01'))
        self.assertEqual(submitted['job']['tv_lifecycle_version'], 1)
        self.assertEqual(submitted['job']['import_mode'], 'move')
        self.assertEqual(submitted['job']['seeding_policy']['seeding_mode'], 'none')
        self.assertEqual(self.store.profile('safe-hd')['seeding_mode'], 'forever')

    def test_hybrid_torrent_import_preserves_the_tv_acquisition_key(self):
        submitted = self.submit()
        primary = 'b' * 40
        self.torrent.update(hash=primary, infohash_v1=self.hash, infohash_v2=primary + 'b' * 24)

        completed = self.complete()

        self.assertEqual(completed['state'], 'imported', completed.get('last_error'))
        self.assertEqual(completed['hash'], submitted['job']['hash'])
        self.assertEqual(list(self.manager.jobs.all()), [self.hash])
        self.assertTrue(self.tv.episodes(self.series, 1)[0]['versions'])
        self.manager.client.resume.assert_called_once_with(primary)
        self.manager.client.remove_without_files.assert_called_once_with(primary)

    def test_missing_home_blocks_submission_without_intent_claim_or_transfer(self):
        with self.tv.store.transaction() as db:
            db.execute('DELETE FROM tv_import_homes')
            db.execute('DELETE FROM tv_path_assignments')
        flat = self.library / 'Flat collection'
        flat.mkdir()
        self.tv.approve_path(flat, 'folder', self.series)
        review = self.service.search(self.series, 1, 1)
        self.assertEqual(review['import_destination']['state'], 'needs_home')
        with self.assertRaisesRegex(ValueError, 'destination review'):
            self.service.submit(review['decisions'][0]['decision_token'], 'blocked')
        with self.store.connection() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM intents').fetchone()[0], 0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM intent_claims').fetchone()[0], 0)
        self.assertFalse(self.manager.jobs.all())

    def test_genuinely_new_metadata_home_is_reserved_on_submit_and_created_only_on_import(self):
        with self.tv.store.transaction() as db:
            db.execute('DELETE FROM tv_import_homes')
            db.execute('DELETE FROM tv_path_assignments')
        destination = self.library / 'Harbor Signals (2020)' / 'Season 01'
        review = self.service.search(self.series, 1, 1)
        self.assertEqual(review['import_destination']['path'], str(destination))
        self.assertFalse(destination.parent.exists())
        result = self.service.submit(review['decisions'][0]['decision_token'], 'new-home')
        self.assertFalse(destination.parent.exists())
        self.assertEqual(result['job']['import_destination']['origin'], 'metadata')
        completed = self.complete()
        self.assertEqual(completed['state'], 'imported', completed.get('last_error'))
        self.assertEqual(self.tv.episodes(self.series, 1)[0]['versions'][0]['path'], str(destination / self.filename))
        self.assertFalse(self.file.exists())

    def test_external_folder_created_after_reservation_cannot_be_adopted(self):
        with self.tv.store.transaction() as db:
            db.execute('DELETE FROM tv_import_homes')
            db.execute('DELETE FROM tv_path_assignments')
        review = self.service.search(self.series, 1, 1)
        self.service.submit(review['decisions'][0]['decision_token'], 'new-home')
        home = Path(review['import_destination']['show_home']); home.mkdir()
        unrelated = home / 'unrelated.txt'; unrelated.write_text('external')
        result = self.complete()
        self.assertEqual(result['state'], 'needs_review')
        self.assertEqual(unrelated.read_text(), 'external')
        self.assertTrue(self.file.exists())

    def test_home_change_invalidates_old_review_and_new_request_snapshots_choice(self):
        old = self.service.search(self.series, 1, 1)
        second = self.library / 'Second'
        (second / 'Season 01').mkdir(parents=True)
        self.tv.approve_path(second, 'folder', self.series)
        self.tv.set_import_home(self.series, second, [self.library])
        with self.assertRaisesRegex(ValueError, 'Destination changed'):
            self.service.submit(old['decisions'][0]['decision_token'], 'stale')
        new = self.service.search(self.series, 1, 1)
        self.assertNotEqual(old['decisions'][0]['decision_token'], new['decisions'][0]['decision_token'])
        result = self.service.submit(new['decisions'][0]['decision_token'], 'request-1')
        self.assertEqual(result['job']['destination'], str(second / 'Season 01'))
        self.tv.set_import_home(self.series, self.home, [self.library])
        again = self.service.submit(new['decisions'][0]['decision_token'], 'request-1')
        self.assertEqual(again['job']['destination'], result['job']['destination'])

    def test_follow_preview_reports_destination_per_targeted_season(self):
        preview = TVMonitoring(self.tv, self.store, self.service).preview(self.series)
        self.assertTrue(preview['import_destinations'])
        self.assertTrue(all(row['state'] == 'ready' for row in preview['import_destinations']))
        self.assertEqual(preview['import_policy']['seeding_mode'], 'none')

    def test_complete_publishes_binding_before_removal_then_deletes_only_own_source(self):
        submitted = self.submit()
        neighbor = self.manager.staging_dir / 'unrelated.mkv'
        neighbor.write_bytes(b'unrelated')
        def remove(_):
            self.assertTrue(self.tv.episodes(self.series, 1)[0]['available'])
            self.assertTrue(self.file.exists())
        self.manager.client.remove_without_files.side_effect = remove
        result = self.complete()
        self.assertEqual(result['state'], 'imported', result.get('last_error'))
        self.assertFalse(self.file.exists())
        self.assertTrue(neighbor.exists())
        destination = self.home / 'Season 01' / self.filename
        self.assertEqual(destination.read_bytes(), b'synthetic episode')
        self.assertEqual(self.tv.episodes(self.series, 1)[0]['versions'][0]['path'], str(destination))
        self.assertFalse(result['source_retained'])
        self.assertFalse(result['rollback_available'])
        self.assertFalse(result['library_scan_pending'])
        self.manager.client.remove_without_files.assert_called_once_with(self.hash)
        self.service.probe = Mock(side_effect=AssertionError('must not reprobe deleted source'))
        self.manager.client.torrents.return_value = []
        self.assertEqual(self.manager.process_completed()[0]['state'], 'imported')
        with self.assertRaisesRegex(ValueError, 'cleanup'):
            self.service.manage(submitted['intent']['id'], 'rollback')

    def test_torrent_removal_failure_retries_cleanup_without_recopy_or_rebind(self):
        submitted = self.submit()
        self.manager.client.remove_without_files.side_effect = OSError('qBT unavailable')
        result = self.complete()
        self.assertEqual(result['state'], 'cleanup_failed', result.get('last_error'))
        self.assertTrue(self.file.exists())
        self.assertTrue(self.tv.episodes(self.series, 1)[0]['available'])
        self.manager.client.remove_without_files.side_effect = None
        self.service.manage(submitted['intent']['id'], 'retry')
        with patch.object(self.tv, 'bind_files', side_effect=AssertionError('already committed')), patch.object(self.service, 'probe', side_effect=AssertionError('already measured')):
            result = self.manager.process_completed()[0]
        self.assertEqual(result['state'], 'imported', result.get('last_error'))
        self.assertFalse(self.file.exists())

    def test_changed_destination_pauses_before_publication(self):
        self.submit()
        self.tv.exclude_path(self.home / 'Season 01', 'folder', 'destination withdrawn')
        result = self.complete()
        self.assertEqual(result['state'], 'needs_review')
        self.assertFalse(self.tv.episodes(self.series, 1)[0]['available'])
        self.assertTrue(self.file.exists())

    def test_catalog_failure_retains_source_and_rollback_removes_only_job_bindings(self):
        submitted = self.submit()
        with patch.object(self.tv, 'bind_files', side_effect=ValueError('catalog rejected')):
            result = self.complete()
        self.assertEqual(result['state'], 'needs_review')
        self.assertTrue(self.file.exists())
        self.assertTrue(result['rollback_available'])
        self.service.manage(submitted['intent']['id'], 'rollback')
        self.assertFalse((self.home / 'Season 01' / self.filename).exists())
        self.assertTrue(self.file.exists())

    def test_changed_or_shared_source_blocks_cleanup_without_deleting_any_neighbor(self):
        self.submit()
        self.manager.client.remove_without_files.side_effect = OSError('hold before cleanup')
        self.complete()
        self.manager.jobs.upsert('f'*40, {'state': 'downloading', 'payload_paths': [str(self.file)]})
        self.manager.client.remove_without_files.side_effect = None
        self.manager.jobs.upsert(self.hash, {'state': 'importing'})
        result = self.manager.process_completed()[0]
        self.assertEqual(result['state'], 'cleanup_failed')
        self.assertIn('another', result['last_error'])
        self.assertTrue(self.file.exists())
        self.manager.jobs.upsert('f'*40, {'state': 'cancelled', 'payload_paths': []})
        self.file.write_bytes(b'changed')
        self.manager.jobs.upsert(self.hash, {'state': 'importing'})
        result = self.manager.process_completed()[0]
        self.assertEqual(result['state'], 'cleanup_failed')
        self.assertIn('changed', result['last_error'].lower())
        self.assertEqual(self.file.read_bytes(), b'changed')

    def test_move_collision_distinguishes_identical_conflict_and_explicit_upgrade(self):
        target = self.home / 'Season 01' / self.filename
        target.write_bytes(self.file.read_bytes())
        self.manager.jobs.upsert(self.hash, {'state': 'downloading'})
        result = import_verified_files(self.manager.jobs, self.hash, [self.file], self.manager.staging_dir, target.parent, mode='move')
        self.assertTrue(result['preserving_import_plan'][0]['pre_existing'])
        rollback_verified_files(self.manager.jobs, self.hash, unpublish=lambda _: None)
        self.assertTrue(target.exists())
        target.write_bytes(b'old version')
        self.manager.jobs.upsert('b'*40, {'state': 'downloading'})
        with self.assertRaisesRegex(ValueError, 'collision'):
            import_verified_files(self.manager.jobs, 'b'*40, [self.file], self.manager.staging_dir, target.parent, mode='move')
        self.assertEqual(target.read_bytes(), b'old version')
        upgraded = import_verified_files(self.manager.jobs, 'b'*40, [self.file], self.manager.staging_dir, target.parent, mode='move', upgrade=True)
        self.assertEqual(Path(upgraded['imported_paths'][0]).name, Path(self.filename).stem + ' [upgrade 1].mkv')
        self.assertEqual(target.read_bytes(), b'old version')

    def test_crash_after_source_unlink_recovers_from_destination_and_checkpoint(self):
        self.submit()
        original = Path.unlink
        def interrupted(path, *args, **kwargs):
            original(path, *args, **kwargs)
            if path == self.file:
                raise OSError('power loss after unlink')
        with patch.object(Path, 'unlink', interrupted):
            result = self.complete()
        self.assertEqual(result['state'], 'cleanup_failed')
        self.assertFalse(self.file.exists())
        self.manager.jobs = QBittorrentJobStore(self.manager.jobs.path)
        self.manager.jobs.upsert(self.hash, {'state': 'importing'})
        self.manager.client.torrents.return_value = []
        self.service.probe = Mock(side_effect=AssertionError('deleted source'))
        result = self.manager.process_completed()[0]
        self.assertEqual(result['state'], 'imported', result.get('last_error'))
        self.assertTrue(self.tv.episodes(self.series, 1)[0]['available'])

    def test_conflicting_identical_target_binding_survives_refusal_and_rollback(self):
        target = self.home / 'Season 01' / self.filename
        target.write_bytes(self.file.read_bytes())
        wrong_episode = self.tv.episodes(self.series, 1)[1]['id']
        self.tv.bind_file(target, [wrong_episode], {}, [self.library])
        submitted = self.submit()
        result = self.complete()
        self.assertEqual(result['state'], 'needs_review')
        self.assertIn('conflicting TV', result['last_error'])
        self.service.manage(submitted['intent']['id'], 'rollback')
        self.assertTrue(target.exists())
        self.assertTrue(self.tv.episodes(self.series, 1)[1]['available'])
        self.assertFalse(self.tv.episodes(self.series, 1)[0]['available'])

    def test_crash_after_bind_before_checkpoint_reuses_same_paths_and_binding(self):
        submitted = self.submit()
        original = self.manager.jobs.upsert
        crash = [True]
        def interrupted(key, values):
            if values.get('tv_publication', {}).get('state') == 'committed' and crash[0]:
                crash[0] = False
                raise RuntimeError('lost binding checkpoint')
            return original(key, values)
        with patch.object(self.manager.jobs, 'upsert', interrupted):
            result = self.complete()
        self.assertEqual(result['state'], 'needs_review')
        self.assertTrue(self.tv.episodes(self.series, 1)[0]['available'])
        self.assertTrue(self.file.exists())
        self.manager.jobs = QBittorrentJobStore(self.manager.jobs.path)
        self.service.manage(submitted['intent']['id'], 'retry')
        result = self.manager.process_completed()[0]
        self.assertEqual(result['state'], 'imported', result.get('last_error'))
        self.assertEqual(len(self.tv.episodes(self.series, 1)[0]['versions']), 1)
        self.assertEqual(len(list((self.home / 'Season 01').iterdir())), 1)

    def test_crash_after_publication_before_journal_recovers_without_torrent(self):
        submitted = self.submit()
        def interrupt(phase, _):
            if phase == 'published_before_journal':
                raise RuntimeError('lost publication checkpoint')
        def importer(*args, **kwargs):
            return import_verified_files(*args, **kwargs, checkpoint=interrupt)
        with patch('services.tv_acquisition.import_verified_files', importer):
            result = self.complete()
        self.assertEqual(result['state'], 'needs_review')
        self.manager.client.torrents.return_value = []
        self.service.manage(submitted['intent']['id'], 'retry')
        result = self.manager.process_completed()[0]
        self.assertEqual(result['state'], 'imported', result.get('last_error'))
        self.assertFalse(self.file.exists())
        self.assertEqual(len(list((self.home / 'Season 01').iterdir())), 1)

    def test_crash_after_torrent_removal_before_checkpoint_finishes_without_readding(self):
        submitted = self.submit()
        original = self.manager.jobs.upsert
        crash = [True]
        def interrupted(key, values):
            if values.get('torrent_removed') and crash[0]:
                crash[0] = False
                self.manager.client.torrents.return_value = []
                raise OSError('lost removal checkpoint')
            return original(key, values)
        with patch.object(self.manager.jobs, 'upsert', interrupted):
            result = self.complete()
        self.assertEqual(result['state'], 'cleanup_failed')
        self.service.manage(submitted['intent']['id'], 'retry')
        result = self.manager.process_completed()[0]
        self.assertEqual(result['state'], 'imported', result.get('last_error'))
        self.manager.client.add_magnet.assert_called_once()
        self.manager.client.remove_without_files.assert_called_once()

    def test_dedicated_payload_unknown_content_pauses_cleanup_and_preserves_neighbors(self):
        payload = self.manager.staging_dir / 'pack'
        payload.mkdir()
        self.file.rename(payload / self.filename)
        self.file = payload / self.filename
        self.torrent['save_path'] = str(payload)
        unknown = payload / 'unknown.txt'
        unknown.write_bytes(b'keep me')
        self.submit()
        result = self.complete()
        self.assertEqual(result['state'], 'cleanup_failed')
        self.assertIn('Unknown', result['last_error'])
        self.assertTrue(unknown.exists())
        self.assertTrue(self.file.exists())

    def test_disk_full_and_failed_probe_never_remove_source_or_publish_bad_binding(self):
        self.submit()
        self.manager.process_completed()
        self.torrent['progress'] = 1
        with patch('services.verified_import.shutil.disk_usage', return_value=type('Disk', (), {'free': 0})()):
            result = self.manager.process_completed()[0]
        self.assertEqual(result['state'], 'retry_wait')
        self.assertEqual(result['tv_import']['imported_files'], 0)
        self.assertTrue(self.file.exists())
        self.assertFalse(self.tv.episodes(self.series, 1)[0]['available'])
        self.manager.client.remove_without_files.assert_not_called()

    def test_unknown_missing_source_without_cleanup_checkpoint_requires_review(self):
        submitted = self.submit()
        self.manager.client.remove_without_files.side_effect = OSError('before unlink')
        self.complete()
        self.file.unlink()
        self.manager.client.remove_without_files.side_effect = None
        self.service.manage(submitted['intent']['id'], 'retry')
        result = self.manager.process_completed()[0]
        self.assertEqual(result['state'], 'cleanup_failed')
        self.assertIn('missing without', result['last_error'])

    def test_cp_compatibility_profile_also_completes_move_without_changing_movie_policy(self):
        decision = self.service.search(self.series, 1, 1, profile_id='cp-compatibility')['decisions'][0]
        self.service.submit(decision['decision_token'], 'compatibility')
        result = self.complete()
        self.assertEqual(result['state'], 'imported', result.get('last_error'))
        self.assertFalse(self.file.exists())
        self.assertFalse(result['source_retained'])

    def test_follow_and_bulk_created_jobs_use_the_same_destination_and_lifecycle(self):
        monitor = TVMonitoring(self.tv, self.store, self.service)
        task = monitor.start_task(monitor.save_task(self.series, scope='episodes', action='selected',
            selected_episodes=[self.tv.episodes(self.series, 1)[0]['id']])['id'])
        results = monitor.run_once(limit=1, submit=True)
        self.assertTrue(results[0]['submitted'], results)
        job = self.manager.jobs.get(self.hash)
        self.assertEqual(job['destination'], str(self.home / 'Season 01'))
        self.assertEqual(job['tv_lifecycle_version'], 1)
        self.assertEqual(job['seeding_policy']['seeding_mode'], 'none')

    def test_bulk_without_destination_keeps_blocked_draft_without_claim(self):
        with self.tv.store.transaction() as db:
            db.execute('DELETE FROM tv_import_homes')
            db.execute('DELETE FROM tv_path_assignments')
        flat = self.library / 'Flat'; flat.mkdir()
        self.tv.approve_path(flat, 'folder', self.series)
        monitor = TVMonitoring(self.tv, self.store, self.service)
        draft = monitor.save_task(self.series, kind='bulk')
        with self.assertRaisesRegex(ValueError, 'destination review'): monitor.start_task(draft['id'])
        self.assertEqual(monitor.task(draft['id'])['state'], 'draft')
        self.assertFalse(self.manager.jobs.all())
        with self.store.connection() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM intent_claims').fetchone()[0], 0)

    def test_downloads_rollback_flag_reflects_changed_source_and_cleanup_checkpoint(self):
        submitted = self.submit()
        with patch.object(self.tv, 'bind_files', side_effect=ValueError('hold publication')):
            self.complete()
        self.assertTrue(self.service.job_status(self.manager.jobs.get(self.hash))['rollback_available'])
        self.file.write_bytes(b'changed source')
        self.assertFalse(self.service.job_status(self.manager.jobs.get(self.hash))['rollback_available'])

    def test_active_validated_manifest_reference_also_protects_a_shared_source(self):
        self.submit()
        self.manager.jobs.upsert('d'*40, {'state': 'downloading', 'media_type': 'tv',
            'tv_download_staging_root': str(self.manager.staging_dir),
            'validated_manifest': {'domain': {'mappings': [{'name': self.filename, 'episode_ids': [99]}]}}})
        result = self.complete()
        self.assertEqual(result['state'], 'cleanup_failed')
        self.assertTrue(self.file.exists())

    def test_status_poll_uses_recorded_file_fingerprint_instead_of_rereading_video_bytes(self):
        self.submit()
        with patch.object(self.tv, 'bind_files', side_effect=ValueError('hold publication')):
            self.complete()
        with patch('services.verified_import.sha256', side_effect=AssertionError('poll should not hash video')):
            self.assertTrue(self.service.job_status(self.manager.jobs.get(self.hash))['rollback_available'])

    def test_all_failed_media_checks_report_each_file_and_stop_new_job_seeding(self):
        self.submit()
        self.service.probe = lambda _: {'probe_status': 'failed', 'quality_class': 'unknown'}
        result = self.complete()
        self.assertEqual(result['state'], 'needs_review')
        self.assertEqual(result['tv_import']['failed_files'], 1)
        self.assertEqual(result['tv_import']['failures'][0]['name'], self.filename)
        self.assertTrue(self.file.exists())
        self.assertFalse(self.tv.episodes(self.series, 1)[0]['available'])
        self.manager.client.pause.assert_called_with(self.hash)
        self.manager.client.remove_without_files.assert_not_called()

    def test_unexplained_temporary_neighbor_is_not_deleted_or_adopted(self):
        destination = self.home / 'Season 01'
        neighbor = destination / f'.{self.filename}.{self.hash[:12]}.partial'
        neighbor.write_bytes(b'unknown library neighbor')
        self.manager.jobs.upsert(self.hash, {'state': 'downloading'})
        with self.assertRaisesRegex(ValueError, 'temporary'):
            import_verified_files(self.manager.jobs, self.hash, [self.file], self.manager.staging_dir, destination, mode='move')
        self.assertEqual(neighbor.read_bytes(), b'unknown library neighbor')
        self.assertTrue(self.file.exists())

    def test_valid_approved_destination_does_not_depend_on_first_root_order(self):
        self.service.roots = lambda: [self.root / 'offline-root', self.library]
        result = self.submit()
        self.assertEqual(result['job']['destination'], str(self.home / 'Season 01'))

    def test_import_home_route_rejects_unapproved_choice_without_queue_mutation(self):
        from flask import Flask
        from services.tv_routes import register_tv_routes
        web = Flask(__name__)
        register_tv_routes(web, lambda: {'repository': self.tv}, lambda: True, None,
                           acquisition=lambda: self.service)
        response = web.test_client().post(f'/api/tv/series/{self.series}/import-home',
                                          json={'path': str(self.root / 'unapproved')})
        self.assertEqual(response.status_code, 400)
        self.assertIn('approved TV show folder', response.json['error'])
        self.assertFalse(self.manager.jobs.all())
        with self.store.connection() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM intents').fetchone()[0], 0)

    def test_rollback_refuses_changed_catalog_ownership_before_any_mutation(self):
        submitted = self.submit()
        original = self.manager.jobs.upsert
        def interrupted(key, values):
            if values.get('tv_publication', {}).get('state') == 'committed':
                raise RuntimeError('before cleanup')
            return original(key, values)
        with patch.object(self.manager.jobs, 'upsert', interrupted):
            self.complete()
        target = self.home / 'Season 01' / self.filename
        wrong = self.tv.episodes(self.series, 1)[1]['id']
        with self.tv.store.transaction() as db:
            file_id = db.execute('SELECT id FROM media_files WHERE path=?', (str(target),)).fetchone()[0]
            db.execute('DELETE FROM episode_file_bindings WHERE file_id=?', (file_id,))
            db.execute('INSERT INTO episode_file_bindings(episode_id,file_id) VALUES(?,?)', (wrong, file_id))
        with self.assertRaisesRegex(ValueError, 'binding changed'):
            self.service.manage(submitted['intent']['id'], 'rollback')
        self.assertTrue(target.exists())
        self.assertTrue(self.file.exists())
        self.assertTrue(self.tv.episodes(self.series, 1)[1]['available'])

    def test_rollback_does_not_delete_target_that_appeared_before_job_publication(self):
        self.manager.jobs.upsert(self.hash, {'state': 'downloading'})
        def interrupt(phase, _):
            if phase == 'planned':
                raise RuntimeError('before publication')
        destination = self.home / 'Season 01'
        with self.assertRaises(RuntimeError):
            import_verified_files(self.manager.jobs, self.hash, [self.file], self.manager.staging_dir,
                                  destination, mode='move', checkpoint=interrupt)
        target = destination / self.filename
        target.write_bytes(self.file.read_bytes())
        rollback_verified_files(self.manager.jobs, self.hash, unpublish=lambda _: None)
        self.assertTrue(target.exists())
        self.assertTrue(self.file.exists())
