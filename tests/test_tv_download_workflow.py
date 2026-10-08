import hashlib
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tests import test_verified_tv_acquisition as fixtures
from services.tv_filename_parser import series_identity
from services.qbittorrent import torrent_content_hash, TorrentValidationError


class TVDownloadWorkflowTests(unittest.TestCase):
    setUp = fixtures.TVAcquisitionTests.setUp
    tearDown = fixtures.TVAcquisitionTests.tearDown

    def release(self, number=1, digest='a'):
        return {'title': f'Harbor.Signals.S01E{number:02d}.1080p.WEB-DL', 'infoHash': digest*40,
                'magnetUrl': 'magnet:?xt=urn:btih:'+digest*40, 'size': 1000, 'seeders': 20, 'indexerId': 7}

    def test_missing_provider_ids_and_hash_are_resolvable_not_permanently_rejected(self):
        row = self.release(); row.pop('infoHash'); row.pop('magnetUrl'); row['downloadUrl'] = 'http://prowlarr.invalid/7/download?token=x'
        self.provider.search_tv.return_value = [row]
        result = self.service.search(self.series, 1, 1)['decisions'][0]
        self.assertEqual(result['state'], 'resolve', result['reasons'])
        self.service.resolve_candidate = Mock(return_value={'info_hash': self.hash, 'transport_verified': True})
        prepared = self.service.prepare(result['decision_token'])
        self.assertTrue(prepared['accepted'], prepared['reasons'])
        self.manager.client.add_magnet.assert_not_called()

    def test_wrong_series_and_same_title_year_are_not_silently_matched(self):
        series = {'tmdb_id': 1, 'title': 'Dark Matter', 'first_air_date': '2024-01-01'}
        self.assertEqual(series_identity({'title': 'Dark.Matter.2015.S01E01.1080p'}, series)['state'], 'conflict')
        self.assertEqual(series_identity({'title': 'Dark.Matter.S01E01.1080p'}, series, ambiguous=True)['state'], 'review')
        self.assertEqual(series_identity({'title': 'Dark.Matter.2024.S01E01.1080p'}, series, ambiguous=True)['state'], 'matched')
        self.assertEqual(series_identity({'title': 'Daredevil.S01E01.1080p'}, {'title': 'Daredevil: Born Again'})['state'], 'conflict')

    def test_season_can_be_fulfilled_by_multiple_episode_releases(self):
        self.provider.search_tv.return_value = [self.release(1, 'a'), self.release(2, 'b'), self.release(3, 'c')]
        result = self.service.search(self.series, 1)
        self.assertEqual(len(result['recommended']), 3)
        self.assertEqual(result['missing_episodes'], [])
        self.assertTrue(all(d['accepted'] for d in result['decisions']))
        self.assertEqual(len({d['target'] for d in result['decisions']}), 3)

    def test_multi_season_review_only_released_missing_and_explicit_submit(self):
        def releases(**kw):
            season = kw['season']
            return [{**self.release(), 'title': f'Harbor.Signals.S{season:02d}.1080p.WEB-DL', 'infoHash': chr(96+season)*40,
                     'magnetUrl': 'magnet:?xt=urn:btih:'+chr(96+season)*40}]
        self.provider.search_tv.side_effect = releases
        review = self.service.search_seasons(self.series, seasons=[2, 1, 2])
        self.assertEqual(review['selected_seasons'], [1, 2])
        self.assertEqual(review['scope_counts']['targets'], 4)
        self.assertEqual(len(review['season_reviews']), 2)
        self.manager.client.add_magnet.assert_not_called()
        with self.store.connection() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM tv_tasks').fetchone()[0], 0)
        result = self.service.submit_batch(review['recommended'], 'multi-season')
        self.assertTrue(result['complete'], result)
        self.assertEqual(self.manager.client.add_magnet.call_count, 2)
        self.service.submit_batch(review['recommended'], 'multi-season')
        self.assertEqual(self.manager.client.add_magnet.call_count, 2)

    def test_preparing_multi_season_release_keeps_its_stored_scope_after_single_review(self):
        self.service.prepare(self.service.search(self.series, 1, missing_only=True)['decisions'][0]['decision_token'])
        multi = self.service.search_seasons(self.series, seasons=[1])
        prepared = self.service.prepare(multi['decisions'][0]['decision_token'])
        stored = self.store.decision(prepared['decision_token'])
        self.assertEqual(stored.get('multi_season_scope'), multi['decisions'][0]['multi_season_scope'])
        self.assertEqual(stored.get('covered_episode_keys'), prepared['covered_episode_keys'])

    def test_multi_season_validation_and_partial_provider_failure_are_visible(self):
        for seasons in ([], [0], [99], '1', list(range(1, 152))):
            with self.assertRaises(ValueError): self.service.search_seasons(self.series, seasons=seasons)
        def releases(**kw):
            if kw['season'] == 2: raise TimeoutError('fixture provider timeout')
            return [self.release()]
        self.provider.search_tv.side_effect = releases
        review = self.service.search_seasons(self.series, seasons=[1, 2])
        self.assertTrue(review['search']['partial'])
        self.assertIn('timeout', review['season_reviews'][1]['search']['error'])
        self.assertEqual(len(review['recommended']), 1)

    def test_multi_season_cancellation_does_not_search_remaining_seasons(self):
        calls = []
        def releases(**kw): calls.append(kw); return [self.release()]
        self.provider.search_tv.side_effect = releases
        result = self.service.search_seasons(self.series, seasons=[1,2], cancelled=lambda: bool(calls))
        self.assertEqual(len(calls), 1)
        self.assertTrue(result['search']['partial'])
        self.assertIn('cancelled', result['season_reviews'][1]['search']['error'])
        self.manager.client.add_magnet.assert_not_called()

    def test_multi_season_preview_uses_composite_keys_when_provider_preview_ids_repeat(self):
        from services.tv_metadata import TVMetadata
        metadata = TVMetadata(self.tv, lambda:'fixture')
        raw = {'id':99, 'name':'New Harbor', 'first_air_date':'2020-01-01',
               'seasons':[{'season_number':n,'episode_count':1} for n in (1,2)]}
        def request(path, **kw):
            if path == '/tv/99': return raw
            if path == '/search/tv': return {'results':[raw]}
            return {'episodes':[{'id':101,'season_number':int(path.rsplit('/',1)[1]), 'episode_number':1,'name':'Pilot','air_date':'2020-01-01'}]}
        metadata.request = request; self.service.metadata = metadata
        self.provider.search_tv.side_effect = lambda **kw: [{**self.release(digest=chr(96+kw['season'])), 'tmdbId':99, 'title':f"New.Harbor.S{kw['season']:02d}E01.1080p.WEB-DL"}]
        result = self.service.search_seasons(tmdb_id=99, seasons=[1,2])
        self.assertEqual([row['id'] for row in result['episodes']], [-101,-101])
        self.assertEqual(len({row['key'] for row in result['episodes']}), 2)
        self.assertEqual(len(result['recommended']), 2)
        with self.tv.store.connection() as db:
            self.assertFalse(db.execute('SELECT 1 FROM series WHERE tmdb_id=99').fetchone())

    def test_batch_retries_only_failed_member(self):
        self.provider.search_tv.return_value = [self.release(1, 'a'), self.release(2, 'b')]
        result = self.service.search(self.series, 1, episode_numbers=[1, 2])
        calls = []
        fail = [True]
        def submit(manager, candidate, metadata):
            calls.append(candidate['info_hash'])
            if candidate['info_hash'] == 'b'*40 and fail[0]: raise RuntimeError('fixture failure')
            return manager.jobs.upsert(candidate['info_hash'], {**metadata, 'state': 'validating'})
        self.service.submit_candidate = submit
        first = self.service.submit_batch(result['recommended'], 'batch-one')
        self.assertFalse(first['complete'])
        fail[0] = False
        second = self.service.submit_batch(result['recommended'], 'batch-one')
        self.assertTrue(second['complete'], second)
        self.assertEqual(calls.count('a'*40), 1)
        self.assertEqual(calls.count('b'*40), 2)

    def test_partial_scope_and_overlapping_releases_require_review(self):
        self.provider.search_tv.return_value = [self.release(1), self.release(1, 'b')]
        result = self.service.search(self.series, 1)
        with self.assertRaisesRegex(ValueError, 'overlap'):
            self.service.submit_batch([d['decision_token'] for d in result['decisions']], 'overlap')
        with self.assertRaisesRegex(ValueError, 'missing'):
            self.service.submit_batch(result['recommended'], 'partial')

    def test_selected_files_skip_other_episodes_before_resume(self):
        self.provider.search_tv.return_value = [{**self.release(), 'title': 'Harbor.Signals.S01.1080p.WEB-DL'}]
        decision = self.service.search(self.series, 1, episode_numbers=[1])['decisions'][0]
        submitted = self.service.submit(decision['decision_token'], 'selected')
        self.files = [{'index': i, 'name': f'Harbor.Signals.S01E{i+1:02d}.1080p.WEB-DL.mkv', 'size': 1000, 'priority': 1} for i in range(3)]
        def priority(_, indices, value):
            for i in indices: self.files[i]['priority'] = value
        self.manager.client.file_priority.side_effect = priority
        self.manager.process_completed()
        self.assertEqual([f['priority'] for f in self.files], [1, 0, 0])
        self.manager.client.resume.assert_called_once_with(self.hash)

    def test_partial_metadata_refresh_preserves_other_seasons(self):
        series = self.tv.series(self.series)
        rows = self.tv.episodes(self.series, 1)
        self.tv.refresh(series, rows, season_scope={1})
        self.assertTrue(all(not e['reconciliation_required'] for e in self.tv.episodes(self.series, 2)))

    def test_torrent_hash_uses_exact_info_bytes_and_rejects_invalid_metadata(self):
        info = b'd6:lengthi10e4:name5:a.mkve'
        self.assertEqual(torrent_content_hash(b'd4:info'+info+b'e'), hashlib.sha1(info).hexdigest())
        for data in [b'', b'not a torrent', b'd4:infoi1ee', b'd4:info'+info+b'ejunk']:
            with self.assertRaises(TorrentValidationError): torrent_content_hash(data)

    def test_title_aliases_numbers_and_multi_episode_names(self):
        for name, series in [
            ('1923.S01E01.1080p.WEB-DL', {'title':'1923'}),
            ('Harbor.Signals.S01E01E02.1080p.WEB-DL', {'title':'Harbor Signals'}),
            ('Puerto.S01E01.1080p.WEB-DL', {'title':'Harbor Signals','alternative_titles':['Puerto']})]:
            self.assertEqual(series_identity({'title':name}, series)['state'], 'matched')
        self.assertEqual(series_identity({'title':'Other.S01E01','tmdbId':4}, {'title':'Harbor','tmdb_id':4})['state'], 'conflict')

    def test_newly_owned_episode_requires_explicit_upgrade(self):
        decision=self.service.search(self.series,1,1)['decisions'][0]
        episode=self.tv.episodes(self.series,1)[0]
        self.tv.bind_file(self.file,[episode['id']],{'quality_class':'720p'},[self.manager.staging_dir])
        with self.assertRaisesRegex(ValueError,'now available'):
            self.service.submit(decision['decision_token'],'changed-owned')
        upgrade=self.service.search(self.series,1,1,upgrade=True)['decisions'][0]
        self.assertIn('intent',self.service.submit(upgrade['decision_token'],'upgrade'))

    def test_invalid_root_does_not_materialize_preview(self):
        decision=self.service.search(self.series,1,1)['decisions'][0]
        self.service.roots=lambda:[]
        with patch.object(self.service,'_materialize',wraps=self.service._materialize) as materialize:
            with self.assertRaisesRegex(ValueError,'library root'):
                self.service.submit(decision['decision_token'],'bad-root')
            materialize.assert_not_called()

    def test_episode_fallback_preserves_fast_season_results(self):
        calls=[]
        def search(**kw):
            calls.append(kw)
            n=kw.get('episode') or 1
            return {'items':[self.release(n, chr(96+n))], 'partial':False}
        self.provider.search_tv_report=search
        result=self.service.search(self.series,1)
        self.assertEqual(result['missing_episodes'],[])
        self.assertEqual([c.get('episode') for c in calls],[None,2,3])
        self.assertTrue(all(c['budget']<=5 for c in calls[1:]))

    def test_failed_episode_fallback_does_not_erase_season_results(self):
        def search(**kw):
            if kw.get('episode'): raise TimeoutError('fixture timeout')
            return {'items':[self.release()], 'partial':False}
        self.provider.search_tv_report=search
        result=self.service.search(self.series,1)
        self.assertTrue(result['search']['partial'])
        self.assertEqual(len(result['recommended']),1)
        self.assertEqual(result['decisions'][0]['candidate']['episode_numbers'],[1])

    def test_batch_recovers_intent_after_restart_before_outcome_save(self):
        from services.tv_acquisition import TVAcquisition
        self.provider.search_tv.return_value=[self.release(1)]
        result=self.service.search(self.series,1,episode_numbers=[1])
        token=result['recommended'][0]
        original=self.store.save_batch
        self.store.save_batch=Mock(side_effect=RuntimeError('power loss'))
        with self.assertRaisesRegex(RuntimeError,'power loss'):
            self.service.submit_batch([token],'crash')
        self.store.save_batch=original
        import time
        self.store.clock=lambda:time.time()+1000
        restarted=TVAcquisition(self.tv,self.store,lambda:self.provider,lambda:self.manager,lambda:[self.library])
        result=restarted.submit_batch([token],'crash')
        self.assertTrue(result['complete'],result)
        self.manager.client.add_magnet.assert_called_once()

    def test_acquisition_v1_migration_and_checkpoint_preserve_batch(self):
        from services.acquisition_store import AcquisitionRepository
        from services.tv_checkpoint import checkpoint,restore_offline
        import sqlite3
        from contextlib import closing
        backup=self.root/'acquisition-before.sqlite'
        with self.store.connection() as db:
            db.execute('DROP TABLE batches');db.execute('PRAGMA user_version=1');db.commit()
            with closing(sqlite3.connect(backup)) as copy: db.backup(copy)
        self.assertTrue(backup.is_file())
        self.store=AcquisitionRepository(self.store.path)
        self.service.acquisition=self.store
        self.store.batch('durable',['a'])
        self.store.save_batch({'request_key':'durable','items':[{'token':'a','state':'failed'}]})
        snapshot=self.root/'checkpoint'
        checkpoint(self.tv,self.store,self.manager,snapshot,acquisition_lock=self.service._lock)
        self.store.save_batch({'request_key':'durable','items':[]})
        restore_offline(snapshot,self.tv.store.path,self.store.path,self.manager.jobs.path,application_stopped=True)
        self.assertEqual(self.store.batch('durable',['a'])['items'][0]['state'],'failed')

    def test_swapped_resolved_hash_is_blocked_before_submission(self):
        self.provider.search_tv.return_value=[{**self.release(),'downloadUrl':'http://prowlarr.invalid/7/download'}]
        result=self.service.search(self.series,1,1)['decisions'][0]
        self.service.resolve_candidate=Mock(return_value={'info_hash':'b'*40,'transport_verified':True})
        with self.assertRaisesRegex(ValueError,'differs'):
            self.service.prepare(result['decision_token'])
        self.manager.client.add_magnet.assert_not_called()
        with self.store.connection() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM intents').fetchone()[0],0)

    def test_preview_tracks_only_on_download_and_other_seasons_stay_browsable(self):
        from services.tv_metadata import TVMetadata
        from services.tv_read_model import TVReadModel
        metadata=TVMetadata(self.tv,lambda:'fixture')
        raw={'id':99,'name':'Harbor Signals','first_air_date':'2020-01-01','seasons':[
            {'season_number':1,'episode_count':1,'air_date':'2020-01-01'},
            {'season_number':2,'episode_count':1,'air_date':'2021-01-01'}]}
        def request(path,**params):
            if path=='/tv/99':return raw
            if path=='/search/tv':return {'results':[raw]}
            if '/season/' in path:
                season=int(path.rsplit('/',1)[1])
                return {'episodes':[{'id':100+season,'season_number':season,'episode_number':1,'name':'Pilot','air_date':'2020-01-01'}]}
            raise AssertionError(path)
        metadata.request=request;self.service.metadata=metadata
        self.provider.search_tv.return_value=[self.release()]
        result=self.service.search(tmdb_id=99,season=1,episode_numbers=[1])
        def count():
            with self.tv.store.connection() as db:return db.execute('SELECT COUNT(*) FROM series').fetchone()[0]
        self.assertEqual(count(),1)
        submitted=self.service.submit_batch(result['recommended'],'preview')
        self.assertTrue(submitted['complete'], submitted)
        self.assertEqual(count(), 2)
        self.assertFalse((self.library / 'Harbor Signals (2020)').exists())
        self.assertEqual(count(), 2)
        with self.tv.store.connection() as db:saved=db.execute('SELECT id FROM series WHERE tmdb_id=99').fetchone()[0]
        self.assertEqual([s['number'] for s in TVReadModel(self.tv).detail(saved)['seasons']],[1,2])
        self.assertEqual(len(self.tv.episodes(saved)),1)
        self.provider.search_tv.return_value=[{**self.release(digest='b'),'title':'Harbor.Signals.S02E01.1080p.WEB-DL'}]
        second=self.service.search(saved,2,1)
        self.assertEqual(len(self.tv.episodes(saved)),1)
        outcome=self.service.submit_batch(second['recommended'],'preview-season-2')
        self.assertTrue(outcome['complete'],outcome)
        self.assertEqual(len(self.tv.episodes(saved)),2)

    def test_existing_explicit_automatic_upgrade_policy_is_preserved(self):
        episode=self.tv.episodes(self.series,1)[0]
        self.tv.bind_file(self.file,[episode['id']],{'quality_class':'720p'},[self.manager.staging_dir])
        profile=self.store.profile('safe-hd');profile['automatic_upgrades']=True;self.store.save_profile(profile)
        decision=self.service.search(self.series,1,1,manual=False)['decisions'][0]
        self.assertTrue(decision['accepted'],decision['reasons'])
        self.assertIn('intent',self.service.submit(decision['decision_token'],'existing-auto-policy'))

    def test_torrent_retry_recovers_lost_acknowledgement_without_second_add(self):
        from services.qbittorrent import QBittorrentError
        self.manager.client.parse_torrent_metadata.return_value={'hash':self.hash,'info':{'name':self.filename,'length':self.file.stat().st_size}}
        present=[]
        self.manager.client.torrents.side_effect=lambda:list(present)
        def lost_ack(*args,**kwargs):
            present.append(self.torrent)
            raise QBittorrentError('connection lost after client accepted file')
        self.manager.client.add_torrent.side_effect=lost_ack
        self.service.submit_candidate=lambda manager,candidate,metadata:manager.submit_torrent(b'fixture','fixture.torrent',metadata)
        decision=self.service.search(self.series,1,1)['decisions'][0]
        with self.assertRaisesRegex(QBittorrentError,'connection lost'):
            self.service.submit(decision['decision_token'],'torrent-lost-ack')
        self.assertIsNone(self.manager.jobs.get(self.hash))
        result=self.service.submit(decision['decision_token'],'torrent-lost-ack')
        self.assertEqual(result['job']['state'],'validating')
        self.manager.client.add_torrent.assert_called_once()
        self.manager.client.pause.assert_called_once_with(self.hash)
        self.manager.client.resume.assert_not_called()

    def test_torrent_collision_cannot_be_adopted_by_retrying_rejected_intent(self):
        self.manager.client.parse_torrent_metadata.return_value={'hash':self.hash,'info':{'name':self.filename,'length':self.file.stat().st_size}}
        self.manager.client.torrents.return_value=[self.torrent]
        self.service.submit_candidate=lambda manager,candidate,metadata:manager.submit_torrent(b'fixture','fixture.torrent',metadata)
        decision=self.service.search(self.series,1,1)['decisions'][0]
        with self.assertRaisesRegex(TorrentValidationError,'outside this acquisition'):
            self.service.submit(decision['decision_token'],'existing-external-torrent')
        with self.assertRaisesRegex(ValueError,'failed validation'):
            self.service.submit(decision['decision_token'],'existing-external-torrent')
        with self.service.acquisition.connection() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM intent_claims').fetchone()[0],0)
        self.assertIsNone(self.manager.jobs.get(self.hash))
        self.manager.client.add_torrent.assert_not_called()
        self.manager.client.pause.assert_not_called()
        self.manager.client.resume.assert_not_called()

    def test_combined_file_extras_need_specific_choice(self):
        self.provider.search_tv.return_value=[{**self.release(),'title':'Harbor.Signals.S01E01E02.1080p.WEB-DL'}]
        decision=self.service.search(self.series,1,episode_numbers=[1])['decisions'][0]
        job={'tv_request':decision['request'],'decision_token':decision['decision_token'],
             'profile_id':decision['profile_id'],'profile_version':decision['profile_version'],'expected_info_hash':self.hash}
        files=[{'name':'Harbor.Signals.S01E01E02.1080p.WEB-DL.mkv','size':1000}]
        with self.assertRaisesRegex(TorrentValidationError,'explicitly allow extras'):
            self.service.validate_manifest(job,files)
        prepared=self.service.prepare(decision['decision_token'],allow_extras=True)
        result=self.service.validate_manifest({**job,'decision_token':prepared['decision_token']},files)
        self.assertEqual(result['episode_ids'],[self.tv.episodes(self.series,1)[0]['id']])
