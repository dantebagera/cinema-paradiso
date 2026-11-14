import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from services.acquisition_store import AcquisitionRepository
from services.qbittorrent import QBittorrentManager, QBittorrentJobStore, TorrentValidationError
from services.tv_acquisition import TVAcquisition
from services.tv_catalog_repository import TVCatalogRepository
from services.tv_monitoring import TVMonitoring
from services.tv_filename_parser import parse_episode_name
from services.verified_import import import_verified_files, rollback_verified_files


class VerifiedImportTests(unittest.TestCase):
    def test_copy_crash_between_publication_and_journal_recovers_without_duplicate_or_source_loss(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); staging = root/'staging'; staging.mkdir(); destination = root/'library'
            source = staging/'episode.mkv'; source.write_bytes(b'new video')
            jobs = QBittorrentJobStore(root/'jobs.json'); jobs.upsert('a'*40, {'state':'downloading'})
            def crash(phase, _):
                if phase == 'published_before_journal':
                    raise RuntimeError('simulated power loss')
            with self.assertRaisesRegex(RuntimeError, 'power loss'):
                import_verified_files(jobs, 'a'*40, [source], staging, destination, mode='copy', checkpoint=crash)
            recovered = import_verified_files(QBittorrentJobStore(root/'jobs.json'), 'a'*40, [source], staging, destination, mode='copy')
            self.assertEqual(len(recovered['imported_paths']), 1)
            self.assertEqual(list(destination.iterdir()), [destination/'episode.mkv'])
            self.assertEqual(source.read_bytes(), b'new video')
            unpublish = Mock()
            rollback_verified_files(jobs, 'a'*40, unpublish=unpublish)
            unpublish.assert_called_once()
            self.assertTrue(source.exists())
            self.assertFalse((destination/'episode.mkv').exists())

    def test_collision_preserves_existing_copy_and_hardlink_keeps_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); source=root/'staging'/'episode.mkv'; source.parent.mkdir(); source.write_bytes(b'new')
            destination=root/'library'; destination.mkdir(); old=destination/'episode.mkv'; old.write_bytes(b'old')
            jobs=QBittorrentJobStore(root/'jobs.json'); jobs.upsert('b'*40, {})
            result=import_verified_files(jobs,'b'*40,[source],source.parent,destination)
            self.assertEqual(old.read_bytes(), b'old')
            self.assertEqual(Path(result['imported_paths'][0]).read_bytes(), b'new')
            self.assertTrue(source.exists())
            self.assertEqual(result['preserving_import_plan'][0]['method'], 'hardlink')

    def test_changed_source_and_nested_roots_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); staging=root/'staging'; staging.mkdir(); source=staging/'episode.mkv'; source.write_bytes(b'one')
            jobs=QBittorrentJobStore(root/'jobs.json'); jobs.upsert('c'*40,{})
            with self.assertRaises(ValueError):
                import_verified_files(jobs,'c'*40,[source],staging,staging/'library')
            def crash(phase, _):
                if phase == 'planned': raise RuntimeError('interruption')
            with self.assertRaises(RuntimeError):
                import_verified_files(jobs,'c'*40,[source],staging,root/'library',checkpoint=crash)
            source.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'Source changed'):
                import_verified_files(jobs,'c'*40,[source],staging,root/'library')


class AuxiliaryVideoPathTests(unittest.TestCase):
    def test_louie_featurette_directory_is_ignored_with_both_separators(self):
        path = 'Louie (2010) Season 2 S02 (1080p BluRay x265 HEVC 10bit AAC 5.1 Garshasp)/Featurettes/Fox Movie Channel Presents World Premiere - Louie Season 2.mkv'
        for name in (path, path.replace('/', '\\')):
            with self.subTest(name=name):
                self.assertTrue(parse_episode_name(name)['ignored'])

    def test_auxiliary_directory_survives_numbered_episode_branches(self):
        for directory in ('Samples', 'Trailers', 'Extras', 'Featurettes'):
            for filename in ('Harbor.Signals.S01E01.mkv', 'Harbor.Signals.1x01.mkv'):
                with self.subTest(directory=directory, filename=filename):
                    self.assertTrue(parse_episode_name('Harbor Signals/' + directory + '/' + filename)['ignored'])

    def test_package_root_and_similar_folder_are_not_auxiliary(self):
        for name in ('Extras/S01E01.mkv', 'Featurettes/S01E01.mkv', 'Harbor Signals/Extras Season/S01E01.mkv'):
            with self.subTest(name=name):
                self.assertFalse(parse_episode_name(name)['ignored'])


class TVAcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name)
        fixture=json.loads((Path(__file__).parent/'fixtures/native_tv_cases.json').read_text())
        self.tv=TVCatalogRepository(self.root/'tv-catalog.sqlite'); self.series=self.tv.refresh(fixture['series'],fixture['episodes'])
        self.library=self.root/'tv'; self.library.mkdir()
        self.home = self.library / 'Harbor Signals'
        (self.home / 'Season 01').mkdir(parents=True)
        self.tv.approve_path(self.home, 'folder', self.series)
        self.tv.set_import_home(self.series, self.home, [self.library])
        self.store=AcquisitionRepository(self.root/'acquisition.sqlite')
        self.manager=QBittorrentManager(self.root/'data',{},[self.root/'movies'])
        self.manager.staging_dir.mkdir(parents=True)
        self.hash='a'*40
        self.filename='Harbor.Signals.S01E01.1080p.WEB-DL.mkv'
        self.file=self.manager.staging_dir/self.filename; self.file.write_bytes(b'synthetic episode')
        self.files=[{'name':self.filename,'size':self.file.stat().st_size}]
        self.torrent={'hash':self.hash,'name':self.filename,'progress':0,'save_path':str(self.manager.staging_dir)}
        self.manager.ensure_running=Mock(return_value=True)
        self.manager.client=Mock()
        self.manager.client.torrents.return_value=[self.torrent]
        self.manager.client.files.side_effect=lambda _:self.files
        self.provider=SimpleNamespace(base_url='http://prowlarr.invalid',search_tv=Mock(return_value=[{'title':self.filename,'tmdbId':900001,'infoHash':self.hash,'magnetUrl':'magnet:?xt=urn:btih:'+self.hash,'indexerId':7,'indexer':'Fixture','size':self.file.stat().st_size,'seeders':20}]))
        self.service=TVAcquisition(self.tv,self.store,lambda:self.provider,lambda:self.manager,lambda:[self.library],trusted_indexers=lambda:[7],probe=lambda _: {'probe_status':'ok','quality_class':'1080p'})
        self.manager.domain_handlers['tv']=self.service

    def tearDown(self):
        self.temp.cleanup()

    def test_follow_draft_start_cancel_and_durable_notifications(self):
        monitor = TVMonitoring(self.tv, self.store, self.service)
        draft = monitor.save_task(self.series, scope='series', action='missing')
        self.assertEqual(draft['state'], 'draft')
        self.assertEqual(monitor.monitored_tmdb_ids(), set())
        started = monitor.start_task(draft['id'])
        self.assertEqual(started['state'], 'running')
        self.assertTrue(started['target_episode_ids'])
        preview = monitor.cancel_preview(draft['id'])
        self.assertEqual(preview['transfers'], [])
        result = monitor.cancel_task(draft['id'], 'keep', preview['token'])
        self.assertEqual(result['task']['state'], 'cancelled')
        self.assertEqual(monitor.list_tasks(self.series, history=True)['total'], 1)
        notifications = self.store.notifications()
        self.assertEqual(notifications['unread'], 2)
        first = notifications['items'][0]['id']
        self.assertEqual(self.store.mark_notifications_read([first])['read'], 1)
        self.assertEqual(self.store.notifications()['unread'], 1)

    def test_one_shot_bulk_reports_no_source_and_does_not_follow_future(self):
        self.provider.search_tv.return_value = []
        monitor = TVMonitoring(self.tv, self.store, self.service)
        draft = monitor.save_task(self.series, kind='bulk')
        started = monitor.start_task(draft['id'])
        self.assertEqual(started['kind'], 'bulk')
        self.assertTrue(started['target_episode_ids'])
        results = monitor.run_once(limit=25, submit=False)
        self.assertTrue(results)
        self.assertTrue(all(item['error'] == 'No source found' for item in results))
        completed = monitor.task(draft['id'])
        self.assertEqual(completed['state'], 'completed')
        self.assertTrue(all(item['error'] == 'No source found' for item in completed['episodes']))
        self.assertEqual(monitor.monitored_tmdb_ids(), set())

    def test_legacy_episode_monitor_migrates_once_and_keeps_its_scope(self):
        target = 'episode:tmdb:tv:900001:1:1'
        with self.store.transaction() as db:
            db.execute('INSERT INTO monitors(target,mode,profile_id,next_due) VALUES(?,?,?,?)',
                       (target, 'all', 'safe-hd', 0))
        migrated = AcquisitionRepository(self.store.path)
        migrated = AcquisitionRepository(migrated.path)
        with migrated.connection() as db:
            tasks = [dict(row) for row in db.execute('SELECT * FROM tv_tasks WHERE id=?', ('legacy:' + target,))]
            self.assertEqual(db.execute('SELECT mode FROM monitors WHERE target=?', (target,)).fetchone()[0], 'none')
        self.assertEqual(len(tasks), 1)
        self.assertEqual((tasks[0]['scope'], tasks[0]['action'], tasks[0]['state']), ('episodes', 'missing', 'draft'))
        monitor = TVMonitoring(self.tv, migrated, self.service)
        self.assertEqual(monitor.run_once(limit=1), [])
        self.provider.search_tv.assert_not_called()
        self.assertEqual(monitor.list_tasks(self.series)['total'], 1)
        monitor.start_task('legacy:' + target)
        task = monitor.task('legacy:' + target)
        self.assertEqual(len(task['target_episode_ids']), 1)
        self.assertEqual(self.tv.episode(task['target_episode_ids'][0])['episode_number'], 1)

    def test_task_cancellation_protects_an_imported_file_that_is_playing(self):
        monitor = TVMonitoring(self.tv, self.store, self.service)
        task = monitor.start_task(monitor.save_task(self.series, action='missing')['id'])
        submitted = self.submit()
        episode_id = self.tv.episodes(self.series, 1)[0]['id']
        imported = self.library / self.filename
        imported.write_bytes(b'completed fixture')
        self.tv.bind_files([{'path': imported, 'episode_ids': [episode_id], 'facts': {}}], [self.library])
        with self.store.transaction() as db:
            db.execute('UPDATE tv_task_episodes SET state="queued",intent_id=? WHERE task_id=? AND episode_id=?',
                       (submitted['intent']['id'], task['id'], episode_id))
        self.manager.jobs.upsert(self.hash, {'state': 'imported', 'acquisition_id': submitted['intent']['id'],
            'preserving_import_plan': [{'target': str(imported), 'state': 'published'}]})
        trash = Mock()
        monitor = TVMonitoring(self.tv, self.store, self.service, active_media_path=lambda: str(imported), trash_file=trash)
        preview = monitor.cancel_preview(task['id'])
        self.assertFalse(preview['completed_files'])
        self.assertTrue(any(item['reason'] == 'Currently playing' for item in preview['protected']))
        outcome = monitor.cancel_task(task['id'], 'all', preview['token'])['outcome']
        self.assertTrue(imported.exists())
        self.assertTrue(outcome['protected'])
        trash.assert_not_called()

    def submit(self):
        decision=self.service.search(self.series,1,1)['decisions'][0]
        self.assertTrue(decision['accepted'],decision['reasons'])
        return self.service.submit(decision['decision_token'],'request-1')

    def submit_legacy(self):
        result = self.submit()
        profile = self.store.profile('safe-hd')
        result['job'] = self.manager.jobs.upsert(self.hash, {'tv_lifecycle_version': None, 'import_mode': 'hardlink_copy',
            'import_destination': None, 'tv_download_staging_root': None,
            'destination': str(self.library / 'Legacy recorded placement'),
            'seeding_policy': {key: profile[key] for key in ('seeding_mode', 'seed_ratio', 'seed_time_seconds')}})
        return result

    def test_fake_client_single_episode_validates_before_resume_and_retains_seeding(self):
        result=self.submit_legacy()
        self.assertEqual(result['job']['state'],'validating')
        self.manager.client.resume.assert_not_called()
        self.manager.process_completed()
        self.manager.client.resume.assert_called_once_with(self.hash)
        self.torrent['progress']=1
        completed=self.manager.process_completed()[0]
        self.assertEqual(completed['state'],'imported',completed.get('last_error'))
        self.assertTrue(self.tv.episodes(self.series,1)[0]['available'])
        self.assertTrue(self.file.exists())
        self.manager.client.pause.assert_not_called()
        self.manager.client.remove_without_files.assert_not_called()
        before=len(list(self.library.rglob('*.mkv')))
        self.manager.process_completed()
        self.assertEqual(len(list(self.library.rglob('*.mkv'))),before)
        self.assertFalse((self.root/'catalog.sqlite').exists())

    def test_fake_label_and_wrong_episode_never_resume(self):
        self.submit()
        self.files=[{'name':'Harbor.Signals.S01E01.1080p.HDCAM.mkv','size':100}]
        result=self.manager.process_completed()[0]
        self.assertEqual(result['state'],'validation_failed')
        self.manager.client.resume.assert_not_called()
        self.assertIn('labels disagree',result['last_error'])

    def _auxiliary_pack(self):
        package = 'Harbor.Signals.S01.1080p.WEB-DL'
        self.files = []
        for number in (1, 2, 3):
            name = package + f'/Harbor.Signals.S01E{number:02d}.1080p.WEB-DL.mkv'
            path = self.manager.staging_dir / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'synthetic episode')
            self.files.append({'index': number - 1, 'name': name, 'size': path.stat().st_size, 'priority': 1})
        bonus = package + '/Featurettes/Fox Movie Channel Presents World Premiere - Harbor Signals Season 1.mkv'
        bonus_path = self.manager.staging_dir / bonus
        bonus_path.parent.mkdir(parents=True)
        bonus_path.write_bytes(b'synthetic bonus')
        self.files.insert(0, {'index': 3, 'name': bonus, 'size': bonus_path.stat().st_size, 'priority': 1})
        self.provider.search_tv.return_value[0].update(title=package, size=sum(row['size'] for row in self.files))
        self.torrent.update(name=package)
        def priorities(_hash, indices, priority):
            for row in self.files:
                if row['index'] in indices:
                    row['priority'] = priority
        self.manager.client.file_priority.side_effect = priorities
        decision = self.service.search(self.series, 1)['decisions'][0]
        return decision, bonus

    def test_pack_bonus_is_unselected_before_resume_and_never_imported(self):
        decision, bonus = self._auxiliary_pack()
        submitted = self.service.submit(decision['decision_token'], 'bonus-pack')
        mapping = self.service.validate_manifest(submitted['job'], self.files)
        self.assertEqual(mapping['skipped_files'], [bonus])
        self.assertEqual(len(mapping['mappings']), 3)
        validated = self.manager.process_completed()[0]
        self.assertEqual(validated['state'], 'downloading', validated.get('last_error'))
        self.assertEqual(self.files[0]['priority'], 0)
        self.assertEqual([row['priority'] for row in self.files[1:]], [1, 1, 1])
        self.manager.client.resume.assert_called_once_with(self.hash)
        self.torrent['progress'] = 1
        completed = self.manager.process_completed()[0]
        self.assertEqual(completed['state'], 'imported', completed.get('last_error'))
        self.assertEqual(completed['tv_import']['imported_files'], 3)
        self.assertTrue(all(row['available'] for row in self.tv.episodes(self.series, 1)))
        self.assertEqual(len(list(self.home.rglob('*.mkv'))), 3)
        self.assertFalse(any('Premiere' in path.name for path in self.home.rglob('*.mkv')))
        self.assertFalse((self.manager.staging_dir / bonus).exists())

    def _replace_bonus_directory_with_alias(self, bonus):
        source = self.manager.staging_dir / bonus
        unrelated = self.manager.staging_dir / 'unowned-other-job'
        unrelated.mkdir()
        preserved = unrelated / source.name
        source.rename(preserved)
        source.parent.rmdir()
        self._directory_alias(unrelated, source.parent)
        return preserved

    @staticmethod
    def _directory_alias(target, alias):
        if os.name == 'nt':
            import _winapi
            _winapi.CreateJunction(str(target), str(alias))
        else:
            alias.symlink_to(target, target_is_directory=True)

    def test_aliased_save_path_cannot_delete_foreign_auxiliary_source(self):
        decision, bonus = self._auxiliary_pack()
        self.service.submit(decision['decision_token'], 'aliased-save-path')
        self.manager.process_completed()
        foreign = self.manager.staging_dir / 'unowned-other-job'
        foreign.mkdir()
        package = self.manager.staging_dir / Path(bonus).parts[0]
        package.rename(foreign / package.name)
        alias = self.manager.staging_dir / 'aliased-save-path'
        self._directory_alias(foreign, alias)
        self.torrent.update(save_path=str(alias), progress=1)
        result = self.manager.process_completed()[0]
        self.assertEqual(result['state'], 'needs_review', result.get('last_error'))
        self.assertIn('link', result['last_error'].lower())
        self.assertEqual((foreign / bonus).read_bytes(), b'synthetic bonus')
        self.assertTrue(all((foreign / row['name']).exists() for row in self.files[1:]))

    def test_save_path_replaced_with_junction_after_snapshot_prevents_cleanup(self):
        decision, bonus = self._auxiliary_pack()
        dedicated = self.manager.staging_dir / 'dedicated-save-path'
        dedicated.mkdir()
        package = self.manager.staging_dir / Path(bonus).parts[0]
        package.rename(dedicated / package.name)
        self.torrent['save_path'] = str(dedicated)
        submitted = self.service.submit(decision['decision_token'], 'changed-save-path')
        self.manager.process_completed()
        self.torrent['progress'] = 1
        self.manager.client.remove_without_files.side_effect = OSError('hold before cleanup')
        self.assertEqual(self.manager.process_completed()[0]['state'], 'cleanup_failed')
        foreign = self.manager.staging_dir / 'unowned-other-job'
        dedicated.rename(foreign)
        self._directory_alias(foreign, dedicated)
        self.manager.client.remove_without_files.side_effect = None
        self.service.manage(submitted['intent']['id'], 'retry')
        result = self.manager.process_completed()[0]
        self.assertEqual(result['state'], 'cleanup_failed', result.get('last_error'))
        self.assertIn('link', result['last_error'].lower())
        self.assertEqual((foreign / bonus).read_bytes(), b'synthetic bonus')
        self.assertTrue(all((foreign / row['name']).exists() for row in self.files[1:]))

    def test_auxiliary_directory_alias_cannot_delete_another_staging_file(self):
        decision, bonus = self._auxiliary_pack()
        self.service.submit(decision['decision_token'], 'bonus-directory-alias')
        self.manager.process_completed()
        preserved = self._replace_bonus_directory_with_alias(bonus)
        self.torrent['progress'] = 1
        result = self.manager.process_completed()[0]
        self.assertEqual(result['state'], 'needs_review', result.get('last_error'))
        self.assertIn('link', result['last_error'].lower())
        self.assertEqual(preserved.read_bytes(), b'synthetic bonus')
        self.assertTrue(all((self.manager.staging_dir / row['name']).exists() for row in self.files[1:]))

    def test_auxiliary_directory_alias_after_snapshot_prevents_cleanup(self):
        decision, bonus = self._auxiliary_pack()
        submitted = self.service.submit(decision['decision_token'], 'bonus-directory-alias-after-snapshot')
        self.manager.process_completed()
        self.torrent['progress'] = 1
        self.manager.client.remove_without_files.side_effect = OSError('hold before cleanup')
        result = self.manager.process_completed()[0]
        self.assertEqual(result['state'], 'cleanup_failed')
        preserved = self._replace_bonus_directory_with_alias(bonus)
        self.manager.client.remove_without_files.side_effect = None
        self.service.manage(submitted['intent']['id'], 'retry')
        result = self.manager.process_completed()[0]
        self.assertEqual(result['state'], 'cleanup_failed', result.get('last_error'))
        self.assertIn('link', result['last_error'].lower())
        self.assertEqual(preserved.read_bytes(), b'synthetic bonus')
        self.assertTrue(all((self.manager.staging_dir / row['name']).exists() for row in self.files[1:]))

    def test_changed_auxiliary_source_prevents_cleanup_of_every_source(self):
        decision, bonus = self._auxiliary_pack()
        submitted = self.service.submit(decision['decision_token'], 'changed-bonus')
        self.manager.process_completed()
        self.torrent['progress'] = 1
        self.manager.client.remove_without_files.side_effect = OSError('hold before cleanup')
        result = self.manager.process_completed()[0]
        self.assertEqual(result['state'], 'cleanup_failed')
        bonus_path = self.manager.staging_dir / bonus
        bonus_path.write_bytes(b'changed bonus')
        self.manager.client.remove_without_files.side_effect = None
        self.service.manage(submitted['intent']['id'], 'retry')
        result = self.manager.process_completed()[0]
        self.assertEqual(result['state'], 'cleanup_failed')
        self.assertIn('changed', result['last_error'].lower())
        self.assertEqual(bonus_path.read_bytes(), b'changed bonus')
        self.assertTrue(all((self.manager.staging_dir / row['name']).exists() for row in self.files[1:]))

    def test_shared_auxiliary_source_is_retained_on_cleanup(self):
        decision, bonus = self._auxiliary_pack()
        self.service.submit(decision['decision_token'], 'shared-bonus')
        self.manager.process_completed()
        bonus_path = self.manager.staging_dir / bonus
        self.manager.jobs.upsert('f' * 40, {'state': 'downloading', 'payload_paths': [str(bonus_path)]})
        self.torrent['progress'] = 1
        result = self.manager.process_completed()[0]
        self.assertEqual(result['state'], 'cleanup_failed')
        self.assertIn('another', result['last_error'])
        self.assertTrue(bonus_path.exists())
        self.assertTrue(all((self.manager.staging_dir / row['name']).exists() for row in self.files[1:]))

    def test_retry_recovers_crash_after_auxiliary_unlink_without_duplicate_import(self):
        decision, bonus = self._auxiliary_pack()
        submitted = self.service.submit(decision['decision_token'], 'bonus-unlink-recovery')
        self.manager.process_completed()
        self.torrent['progress'] = 1
        bonus_path = self.manager.staging_dir / bonus
        unlink = Path.unlink
        def interrupted(path, *args, **kwargs):
            unlink(path, *args, **kwargs)
            if path == bonus_path:
                raise OSError('crash after unlink before removed checkpoint')
        with patch.object(Path, 'unlink', interrupted):
            result = self.manager.process_completed()[0]
        self.assertEqual(result['state'], 'cleanup_failed')
        self.assertEqual(result['tv_auxiliary_files'][0]['cleanup_state'], 'unlinking')
        self.assertFalse(bonus_path.exists())
        self.service.manage(submitted['intent']['id'], 'retry')
        result = self.manager.process_completed()[0]
        self.assertEqual(result['state'], 'imported', result.get('last_error'))
        self.assertEqual(result['tv_auxiliary_files'][0]['cleanup_state'], 'removed')
        self.assertEqual(len(list(self.home.rglob('*.mkv'))), 3)
        self.manager.client.add_magnet.assert_called_once()

    def test_unknown_neighbor_of_auxiliary_source_is_not_deleted(self):
        decision, bonus = self._auxiliary_pack()
        self.service.submit(decision['decision_token'], 'unknown-bonus-neighbor')
        self.manager.process_completed()
        unknown = (self.manager.staging_dir / bonus).parent / 'unknown.mkv'
        unknown.write_bytes(b'keep this unrelated file')
        self.torrent['progress'] = 1
        result = self.manager.process_completed()[0]
        self.assertEqual(result['state'], 'cleanup_failed')
        self.assertIn('Unknown', result['last_error'])
        self.assertEqual(unknown.read_bytes(), b'keep this unrelated file')
        self.assertTrue((self.manager.staging_dir / bonus).exists())

    def test_explicit_retry_keeps_failed_pack_intent_and_retained_payload(self):
        decision, bonus = self._auxiliary_pack()
        submitted = self.service.submit(decision['decision_token'], 'bonus-retry')
        self.manager.jobs.upsert(self.hash, {'state': 'validation_failed', 'last_error': 'Torrent filenames identify a different series'})
        retained = self.manager.staging_dir / self.files[1]['name']
        before = retained.read_bytes()
        self.service.manage(submitted['intent']['id'], 'retry')
        validated = self.manager.process_completed()[0]
        self.assertEqual(validated['state'], 'downloading', validated.get('last_error'))
        self.assertEqual(validated['acquisition_id'], submitted['intent']['id'])
        self.assertEqual(retained.read_bytes(), before)
        self.manager.client.add_magnet.assert_called_once()
        self.manager.client.resume.assert_called_once_with(self.hash)
        self.assertEqual(self.files[0]['priority'], 0)

    def test_real_wrong_show_episode_still_blocks_pack_with_auxiliary_files(self):
        decision, _ = self._auxiliary_pack()
        self.files[1]['name'] = 'Harbor.Signals.S01.1080p.WEB-DL/Episodes/Another.Show.S01E01.1080p.WEB-DL.mkv'
        self.service.submit(decision['decision_token'], 'wrong-show-with-bonus')
        result = self.manager.process_completed()[0]
        self.assertEqual(result['state'], 'validation_failed')
        self.assertIn('different series', result['last_error'])
        self.manager.client.resume.assert_not_called()

    def test_auxiliary_files_cannot_satisfy_season_coverage(self):
        decision, bonus = self._auxiliary_pack()
        submitted = self.service.submit(decision['decision_token'], 'bonus-only')
        with self.assertRaisesRegex(TorrentValidationError, 'cover'):
            self.service.validate_manifest(submitted['job'], [self.files[0]])

    def test_profile_edit_invalidates_old_decision_and_repeat_submit_is_idempotent(self):
        decision=self.service.search(self.series,1,1)['decisions'][0]
        self.store.save_profile(self.store.profile('safe-hd'))
        with self.assertRaisesRegex(ValueError,'Profile changed'):
            self.service.submit(decision['decision_token'],'stale')
        result=self.submit()
        again=self.service.submit(result['job']['decision_token'],'request-1')
        self.assertEqual(result['intent']['id'],again['intent']['id'])
        self.manager.client.add_magnet.assert_called_once()

    def test_monitoring_defaults_off_is_bounded_and_suppresses_repeat_search(self):
        monitoring=TVMonitoring(self.tv,self.store,self.service)
        self.assertEqual(monitoring.run_once(),[])
        monitoring.configure(self.series,mode='missing',profile_id='safe-hd')
        first=monitoring.run_once(limit=1)
        self.assertEqual(len(first),1)
        count=self.provider.search_tv.call_count
        second=monitoring.run_once(limit=1)
        self.assertNotEqual(first[0]['episode_id'],second[0]['episode_id'])
        self.assertEqual(self.provider.search_tv.call_count,count+1)
        monitoring.configure(self.series,mode='none',season=1)
        self.assertTrue(all(row['mode']=='none' for row in monitoring.describe(self.series)['episodes'] if self.tv.episode(row['episode_id'])['season_number']==1))

    def test_import_recovery_without_torrent_and_rollback_preserve_source(self):
        result = self.submit_legacy()
        self.manager.process_completed()
        job = self.manager.jobs.get(self.hash)
        mapping = self.service.validate_manifest(job, self.files)
        self.manager.jobs.upsert(self.hash, {'tv_verified_mapping': mapping})
        def crash(phase, _):
            if phase == 'published_before_journal':
                raise RuntimeError('power loss')
        with self.assertRaises(RuntimeError):
            import_verified_files(self.manager.jobs, self.hash, [self.file], self.manager.staging_dir, job['destination'], checkpoint=crash)
        self.manager.client.torrents.return_value = []
        recovered = self.manager.process_completed()[0]
        self.assertEqual(recovered['state'], 'imported', recovered.get('last_error'))
        self.assertTrue(self.tv.episodes(self.series, 1)[0]['available'])
        self.service.manage(result['intent']['id'], 'rollback')
        self.assertFalse(self.tv.episodes(self.series, 1)[0]['available'])
        self.assertTrue(self.file.is_file())

    def test_failed_manifest_can_retry_but_cancel_never_removes_files(self):
        result = self.submit()
        self.files = [{'name': 'Harbor.Signals.S01E01.1080p.HDCAM.mkv', 'size': 100}]
        self.manager.process_completed()
        self.service.manage(result['intent']['id'], 'retry')
        self.files = [{'name': self.filename, 'size': self.file.stat().st_size}]
        self.manager.process_completed()
        self.manager.client.resume.assert_called_once_with(self.hash)
        self.service.manage(result['intent']['id'], 'block')
        self.assertTrue(self.store.blocked(result['intent']['target'], self.hash))
        self.assertTrue(self.file.exists())
        self.manager.client.remove_without_files.assert_not_called()

    def test_coordinated_checkpoint_restores_policy_tv_and_transfer_journal(self):
        from services.tv_checkpoint import checkpoint, restore_offline
        self.submit()
        snapshot = self.root/'checkpoint'
        checkpoint(self.tv, self.store, self.manager, snapshot, acquisition_lock=self.service._lock)
        self.manager.jobs.upsert(self.hash, {'state':'changed'})
        restore_offline(snapshot, self.tv.store.path, self.store.path, self.manager.jobs.path, application_stopped=True)
        self.assertEqual(self.manager.jobs.get(self.hash)['state'], 'validating')
        self.assertEqual(self.tv.store.audit()['integrity'], 'ok')
        with self.assertRaises(ValueError):
            restore_offline(snapshot, self.tv.store.path, self.store.path, self.manager.jobs.path)
        (snapshot/'jobs.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'checksum'):
            restore_offline(snapshot, self.tv.store.path, self.store.path, self.manager.jobs.path, application_stopped=True)
        audit = self.store.audit(self.manager.jobs)
        self.assertEqual(audit['integrity'], 'ok')
        self.assertEqual(audit['foreign_keys'], [])
        self.assertTrue(all(count == 0 for count in audit['orphans'].values()), audit)

    def test_season_pack_imports_multiple_files_and_suppresses_overlapping_episode(self):
        self.provider.search_tv.return_value[0]['title'] = 'Harbor.Signals.S01.1080p.WEB-DL'
        self.files = []
        for number in (1,2,3):
            name = f'Harbor.Signals.S01E{number:02d}.1080p.WEB-DL.mkv'
            path = self.manager.staging_dir/name
            path.write_bytes(b'synthetic episode')
            self.files.append({'name':name, 'size':path.stat().st_size})
        self.provider.search_tv.return_value[0]['size'] = sum(row['size'] for row in self.files)
        decision = self.service.search(self.series,1)['decisions'][0]
        self.assertTrue(decision['accepted'], decision['reasons'])
        self.service.submit(decision['decision_token'], 'season-pack')
        self.provider.search_tv.return_value[0].update(title=self.filename, infoHash='b'*40, magnetUrl='magnet:?xt=urn:btih:'+'b'*40)
        overlapping = self.service.search(self.series,1,1)['decisions'][0]
        with self.assertRaisesRegex(ValueError, 'outstanding'):
            self.service.submit(overlapping['decision_token'], 'overlap')
        self.manager.process_completed()
        self.torrent['progress'] = 1
        result = self.manager.process_completed()[0]
        self.assertEqual(result['state'], 'imported', result.get('last_error'))
        self.assertEqual(result['tv_import']['imported_files'], 3)
        self.assertTrue(all(row['available'] for row in self.tv.episodes(self.series,1)))

    def test_seeding_ratio_cleanup_removes_only_the_torrent(self):
        profile = self.store.profile('safe-hd')
        profile.update(seeding_mode='ratio', seed_ratio=1.5)
        self.store.save_profile(profile)
        self.submit_legacy()
        self.manager.process_completed()
        self.torrent.update(progress=1, ratio=1.0, seeding_time=30)
        imported = self.manager.process_completed()[0]
        self.assertEqual(imported['state'], 'imported')
        self.manager.client.remove_without_files.assert_not_called()
        self.torrent['ratio'] = 1.6
        complete = self.manager.process_completed()[0]
        self.assertEqual(complete['state'], 'seed_complete')
        self.manager.client.pause.assert_called_once_with(self.hash)
        self.manager.client.remove_without_files.assert_called_once_with(self.hash)
        self.assertTrue(self.file.exists())
        self.assertTrue(next(self.library.rglob('*.mkv')).exists())

    def test_transient_import_failure_retries_with_backoff_then_succeeds(self):
        now = [1000.0]
        self.service.clock = lambda: now[0]
        self.service.probe = Mock(side_effect=[OSError('temporarily locked'), {'probe_status':'ok', 'quality_class':'1080p'}])
        self.submit()
        self.manager.process_completed()
        self.torrent['progress'] = 1
        waiting = self.manager.process_completed()[0]
        self.assertEqual(waiting['state'], 'retry_wait')
        self.assertEqual(waiting['next_retry_at'], 1300)
        self.assertEqual(self.manager.process_completed()[0]['state'], 'retry_wait')
        now[0] = 1300
        imported = self.manager.process_completed()[0]
        self.assertEqual(imported['state'], 'imported', imported.get('last_error'))
        self.assertEqual(imported['retry_attempts'], 1)

    def test_partial_pack_publishes_verified_files_and_reports_the_failure(self):
        self.provider.search_tv.return_value[0]['title'] = 'Harbor.Signals.S01.1080p.WEB-DL'
        self.files = []
        for number in (1, 2, 3):
            name = f'Harbor.Signals.S01E{number:02d}.1080p.WEB-DL.mkv'
            path = self.manager.staging_dir/name
            path.write_bytes(b'synthetic episode')
            self.files.append({'name':name, 'size':path.stat().st_size})
        self.provider.search_tv.return_value[0]['size'] = sum(row['size'] for row in self.files)
        self.service.probe = lambda path: {'probe_status': 'failed' if 'E02' in path else 'ok', 'quality_class':'1080p'}
        decision = self.service.search(self.series, 1)['decisions'][0]
        self.service.submit(decision['decision_token'], 'partial-pack')
        self.manager.process_completed()
        self.torrent['progress'] = 1
        result = self.manager.process_completed()[0]
        self.assertEqual(result['state'], 'partial_import')
        self.assertEqual(result['tv_import']['imported_files'], 2)
        self.assertEqual(result['tv_import']['failed_files'], 1)
        episodes = self.tv.episodes(self.series, 1)
        self.assertEqual([row['available'] for row in episodes], [True, False, True])
        self.assertTrue((self.manager.staging_dir/self.files[1]['name']).exists())
        self.manager.client.pause.assert_called_with(self.hash)
        self.manager.client.remove_without_files.assert_not_called()

    def test_repeat_search_does_not_replace_a_referenced_decision(self):
        self.provider.search_tv.return_value[0]['published_at'] = 1
        result = self.submit()
        self.service.search(self.series, 1, 1)
        self.store.clock = lambda: 10**12
        repeat = self.service.submit(result['job']['decision_token'], 'request-1')
        self.assertEqual(repeat['intent']['id'], result['intent']['id'])
        self.manager.client.add_magnet.assert_called_once()

    def test_pending_transfers_reserve_space_before_another_submit(self):
        from unittest.mock import patch
        decision = self.service.search(self.series, 1, 1)['decisions'][0]
        self.manager.jobs.upsert('b'*40, {'state':'downloading','expected_size':95,'expected_info_hash':'b'*40})
        with patch('services.tv_acquisition.shutil.disk_usage', return_value=SimpleNamespace(free=100)):
            with self.assertRaisesRegex(ValueError,'unreserved'):
                self.service.submit(decision['decision_token'],'disk-bound')
        self.manager.client.add_magnet.assert_not_called()

    def test_pack_catalog_publication_rolls_back_all_bindings_if_one_fails(self):
        good = self.library/'good.mkv'; good.write_bytes(b'fixture')
        ids = [row['id'] for row in self.tv.episodes(self.series, 1)]
        with self.assertRaises(ValueError):
            self.tv.bind_files([{'path':good,'episode_ids':[ids[0]],'facts':{}}, {'path':self.library/'missing.mkv','episode_ids':[ids[1]],'facts':{}}], [self.library])
        self.assertFalse(self.tv.episodes(self.series, 1)[0]['available'])
