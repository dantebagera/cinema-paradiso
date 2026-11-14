"""Season-first Follow contracts exercised against real disposable owners."""
import unittest
from unittest.mock import Mock

from tests import test_verified_tv_acquisition as fixtures
from services.tv_filename_parser import parse_episode_name, series_identity, resolve_episode_claim
from services.tv_monitoring import TVMonitoring


class ReleaseRecognitionTests(unittest.TestCase):
    def test_redundant_season_title_preserves_year_and_coverage(self):
        title = 'Louie (2010) Season 2 S02 (1080p BluRay x265 HEVC 10bit AAC 5.1 Garshasp)'
        claim = parse_episode_name(title)
        self.assertEqual((claim['scope'], claim['season_number'], claim['series_title']), ('season', 2, 'Louie (2010)'))
        identity = series_identity({'title': title}, {'title':'Louie', 'first_air_date':'2010-06-29'}, ambiguous=True)
        self.assertEqual((identity['state'], identity['title'], identity['year']), ('matched', 'Louie', '2010'))

    def test_contradictory_seasons_cannot_claim_an_episode(self):
        for title in ('Louie (2010) Season 2 S03 BluRay', 'Louie Season 2 S03E01.mkv', 'Louie (2010) Season 2 3x01 1080p BluRay'):
            claim = parse_episode_name(title)
            self.assertTrue(claim.get('contradictory'))
            self.assertEqual(series_identity({'title':title}, {'title':'Louie'})['state'], 'conflict')
            self.assertEqual(resolve_episode_claim(claim, [{'id':1,'season_number':3,'episode_number':1}])['episode_ids'], [])

    def test_existing_numbering_and_identity_remain_distinct(self):
        for title, scope, season, episodes in (
            ('The.100.S02.1080p.BluRay', 'season', 2, []),
            ('1923.S01E01.mkv', 'episode', 1, [1]),
            ('Show.S02E01-E03.mkv', 'episode', 2, [1,2,3]),
            ('Show.1x02.mkv', 'episode', 1, [2]),
            ('Show.2020.01.02.mkv', 'daily', None, []),
            ('Show 02 title.mkv', 'absolute', None, []),
            ('Show Season 2 Episode 3.mkv', 'episode', 2, [3]),
        ):
            with self.subTest(title=title):
                claim = parse_episode_name(title)
                self.assertEqual((claim['scope'], claim['season_number'], claim['episode_numbers']), (scope, season, episodes))
        self.assertEqual(series_identity({'title':'1923.S01.1080p'}, {'title':'1923'})['state'], 'matched')
        self.assertEqual(series_identity({'title':'Louie.S02.1080p'}, {'title':'Louie'}, ambiguous=True)['state'], 'review')


class SeasonPlanningTests(unittest.TestCase):
    setUp = fixtures.TVAcquisitionTests.setUp
    tearDown = fixtures.TVAcquisitionTests.tearDown

    def release(self, title, digest='a', **extra):
        return {'title':title, 'tmdbId':900001, 'infoHash':digest*40,
                'magnetUrl':'magnet:?xt=urn:btih:'+digest*40, 'indexerId':7,
                'seeders':20, 'size':1000, **extra}

    def test_http_in_magnet_field_uses_existing_resolver(self):
        row = self.release(self.filename, magnetUrl='http://prowlarr.invalid/7/download')
        self.provider.search_tv.return_value = [row]
        self.service.resolve_candidate = Mock(return_value={'info_hash':self.hash,'magnet_url':'magnet:?xt=urn:btih:'+self.hash,'download_url':'','transport_verified':True})
        for manual in (True, False):
            review = self.service.search(self.series,1,1,manual=manual)
            self.assertTrue(review['decisions'][0]['candidate']['transport_verified'])
            self.assertTrue(self.service.prepare(review['decisions'][0]['decision_token'])['accepted'])
        self.assertEqual(self.service.resolve_candidate.call_count, 2)
        self.manager.client.add_magnet.assert_not_called()

    def test_disagreeing_hash_and_wrong_origin_cannot_resolve(self):
        for row in (self.release(self.filename, infoHash='b'*40),
                    self.release(self.filename, magnetUrl='https://untrusted.invalid/download')):
            self.provider.search_tv.return_value = [row]
            result = self.service.select_automatic(self.service.search(self.series,1,1,manual=False))
            self.assertIsNone(result['decision'])
        self.manager.client.add_magnet.assert_not_called()

    def test_automatic_batch_singletons_cover_their_own_subset(self):
        self.provider.search_tv.return_value = [self.release(self.filename), self.release('Harbor.Signals.S01E02.1080p.WEB-DL', 'b')]
        review = self.service.search(self.series,1,manual=False)
        self.assertEqual([len(row['covered_episodes']) for row in review['decisions']], [1,1])
        self.assertTrue(all(row['accepted'] for row in review['decisions']))

    def task(self):
        self.now = [1800000000.0]
        self.monitor = TVMonitoring(self.tv,self.store,self.service,clock=lambda:self.now[0])
        draft = self.monitor.save_task(self.series,scope='season',season=1)
        return self.monitor.start_task(draft['id'])

    def test_follow_prefers_one_pack_and_associates_every_target(self):
        task = self.task()
        self.provider.search_tv.return_value = [self.release('Harbor.Signals.S01.1080p.WEB-DL'),
            self.release(self.filename,'b')]
        result = self.monitor.run_once(limit=1,submit=True)
        self.assertEqual(self.provider.search_tv.call_args.kwargs['episode'], None)
        self.assertEqual(self.provider.search_tv.call_count, 1)
        rows = self.monitor.task(task['id'])['episodes']
        self.assertEqual({row['state'] for row in rows}, {'queued'})
        self.assertEqual(len({row['intent_id'] for row in rows}), 1)
        self.manager.client.add_magnet.assert_called_once()
        self.assertEqual(len(result), 1)

    def test_full_pack_can_cover_non_due_siblings_without_early_episode_queries(self):
        task = self.task()
        with self.store.transaction() as db:
            db.execute('UPDATE tv_task_episodes SET next_retry=? WHERE task_id=? AND episode_id<>?', (self.now[0]+7000,task['id'],task['episodes'][0]['episode_id']))
        self.provider.search_tv.return_value = [self.release('Harbor.Signals.S01.1080p.WEB-DL')]
        self.monitor.run_once(limit=1,submit=True)
        self.assertEqual(self.monitor.task(task['id'])['counts']['queued'], 3)
        self.assertEqual(self.provider.search_tv.call_count, 1)

    def test_failed_season_search_does_not_reset_non_due_clocks(self):
        task = self.task()
        due = task['episodes'][0]['episode_id']
        with self.store.transaction() as db:
            db.execute('UPDATE tv_task_episodes SET next_retry=?,last_search=12 WHERE task_id=? AND episode_id<>?', (self.now[0]+7000,task['id'],due))
        self.provider.search_tv.return_value = []
        self.monitor.run_once(limit=1,submit=True)
        rows = self.monitor.task(task['id'])['episodes']
        self.assertEqual(rows[0]['next_retry'], self.now[0]+18000)
        self.assertTrue(all(row['next_retry']==self.now[0]+7000 and row['last_search']==12 for row in rows[1:]))

    def test_pack_submission_failure_keeps_all_associations_for_recovery(self):
        task = self.task()
        self.manager.client.torrents.return_value = []
        self.provider.search_tv.return_value = [self.release('Harbor.Signals.S01.1080p.WEB-DL')]
        self.service.submit_candidate = Mock(side_effect=RuntimeError('lost acknowledgement'))
        self.monitor.run_once(limit=1,submit=True)
        rows = self.monitor.task(task['id'])['episodes']
        self.assertTrue(all(row['intent_id'] for row in rows))
        self.assertEqual(len({row['intent_id'] for row in rows}), 1)
        self.service.submit_candidate = None
        self.now[0] += 18000
        self.monitor.run_once(limit=1,submit=True)
        self.manager.client.add_magnet.assert_called_once()
        self.assertEqual(self.monitor.task(task['id'])['counts']['queued'], 3)

    def test_cancellation_during_search_prevents_reservation_and_add(self):
        task = self.task()
        def search(**kwargs):
            preview = self.monitor.cancel_preview(task['id'])
            self.monitor.cancel_task(task['id'],'keep',preview['token'])
            return [self.release('Harbor.Signals.S01.1080p.WEB-DL')]
        self.provider.search_tv.side_effect = search
        self.monitor.run_once(limit=1,submit=True)
        self.manager.client.add_magnet.assert_not_called()
        self.assertEqual(self.monitor.task(task['id'])['state'],'cancelled')

    def test_non_due_singleton_is_not_prepared_in_a_season_plan(self):
        task = self.task()
        self.provider.search_tv.return_value = [self.release('Harbor.Signals.S01E02.1080p.WEB-DL','b',infoHash='',magnetUrl='',downloadUrl='http://prowlarr.invalid/7/download')]
        review = self.service.search(self.series,1,manual=False)
        self.service.resolve_candidate = Mock()
        result = self.service.select_automatic_plan(review,due_episode_ids=[task['episodes'][0]['episode_id']])
        self.assertEqual(result['decisions'], [])
        self.service.resolve_candidate.assert_not_called()

    def test_crash_before_association_recovers_reserved_pack_once(self):
        task = self.task()
        self.manager.client.torrents.return_value = []
        self.provider.search_tv.return_value = [self.release('Harbor.Signals.S01.1080p.WEB-DL')]
        prepared = self.service.select_automatic_plan(self.service.search(self.series,1,manual=False),due_episode_ids=task['target_episode_ids'])['decisions'][0]
        key = f'task:{task["id"]}:season:1:{prepared["decision_token"][:24]}'
        reservation = self.service.reserve_intent(prepared['decision_token'],key)
        self.assertEqual(self.monitor.task(task['id'])['counts']['queued'],0)
        restarted = TVMonitoring(self.tv,self.store,self.service,clock=lambda:self.now[0])
        restarted.run_once(submit=True)
        rows = restarted.task(task['id'])['episodes']
        self.assertEqual({row['intent_id'] for row in rows},{reservation['intent']['id']})
        self.manager.client.add_magnet.assert_called_once()

    def test_reserved_unassociated_pack_can_be_cancelled_without_client_add(self):
        task = self.task()
        self.manager.client.torrents.return_value = []
        self.provider.search_tv.return_value = [self.release('Harbor.Signals.S01.1080p.WEB-DL')]
        decision = self.service.search(self.series,1,manual=False)['decisions'][0]
        reservation = self.service.reserve_intent(decision['decision_token'],f'task:{task["id"]}:season:1:{decision["decision_token"][:24]}')
        preview = self.monitor.cancel_preview(task['id'])
        self.assertEqual(len(preview['transfers']),1)
        self.monitor.cancel_task(task['id'],'keep',preview['token'])
        with self.store.connection() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM intent_claims WHERE intent_id=?',(reservation['intent']['id'],)).fetchone()[0],0)
        self.manager.client.add_magnet.assert_not_called()

    def test_actual_lost_acknowledgement_adopts_owned_job_without_another_add(self):
        task = self.task()
        self.manager.client.torrents.return_value = []
        self.provider.search_tv.return_value = [self.release('Harbor.Signals.S01.1080p.WEB-DL')]
        def lose_ack(manager,candidate,metadata):
            manager.submit_magnet(candidate['magnet_url'],metadata)
            raise RuntimeError('acknowledgement lost after owned job was saved')
        self.service.submit_candidate = lose_ack
        self.monitor.run_once(limit=1,submit=True)
        self.service.submit_candidate = None
        self.now[0] += 18000
        self.monitor.run_once(submit=True)
        self.manager.client.add_magnet.assert_called_once()
        self.assertEqual(self.monitor.task(task['id'])['counts']['queued'],3)

    def test_quality_precedes_coverage_and_gaps_do_not_overlap(self):
        task = self.task()
        self.provider.search_tv.return_value = [self.release('Harbor.Signals.S01.720p.WEB-DL'),self.release(self.filename,'b')]
        result = self.service.select_automatic_plan(self.service.search(self.series,1,manual=False),due_episode_ids=task['target_episode_ids'])
        self.assertEqual([row['candidate']['info_hash'] for row in result['decisions']],['b'*40])
        self.assertEqual(len(result['missing_episodes']),2)

    def test_per_episode_fallback_after_season_query_fills_disjoint_gaps(self):
        task = self.task()
        def search(**kwargs):
            number = kwargs['episode']
            return [] if number is None else [self.release(f'Harbor.Signals.S01E{number:02d}.1080p.WEB-DL',chr(96+number))]
        self.provider.search_tv.side_effect = search
        self.monitor.run_once(limit=4,submit=True)
        self.assertEqual([call.kwargs['episode'] for call in self.provider.search_tv.call_args_list],[None,1,2,3])
        self.assertEqual(self.monitor.task(task['id'])['counts']['queued'],3)
        self.assertEqual(self.manager.client.add_magnet.call_count,3)

    def test_pack_found_by_gap_query_is_planned_once_for_the_remaining_season(self):
        task = self.task()
        self.provider.search_tv.side_effect = lambda **kwargs: [] if kwargs['episode'] is None else [self.release('Harbor.Signals.S01.1080p.WEB-DL')]
        self.monitor.run_once(limit=4,submit=True)
        self.assertEqual(self.monitor.task(task['id'])['counts']['queued'],3)
        self.assertEqual([call.kwargs['episode'] for call in self.provider.search_tv.call_args_list],[None,1])
        self.manager.client.add_magnet.assert_called_once()

    def test_deferred_gap_pack_keeps_full_scope_and_covers_non_due_trigger(self):
        task = self.task()
        self.provider.search_tv.side_effect = lambda **kwargs: [] if kwargs['episode'] is None else [self.release('Harbor.Signals.S01.1080p.WEB-DL')]
        self.monitor.run_once(limit=1,submit=True)
        self.monitor.run_once(limit=4,submit=True)
        self.assertEqual(self.monitor.task(task['id'])['counts']['queued'],3)
        self.assertEqual([call.kwargs['episode'] for call in self.provider.search_tv.call_args_list],[None,2])
        self.manager.client.add_magnet.assert_called_once()

    def assert_overlapping_gap_pack_is_not_retargeted(self, first_limit):
        task = self.task()
        self.provider.search_tv.side_effect = lambda **kwargs: [self.release(self.filename)] if kwargs['episode'] is None else [self.release('Harbor.Signals.S01.720p.WEB-DL','b')]
        self.monitor.run_once(limit=first_limit,submit=True)
        if first_limit==1: self.monitor.run_once(limit=4,submit=True)
        self.assertEqual(self.monitor.task(task['id'])['counts']['queued'],1)
        self.manager.client.add_magnet.assert_called_once()
        self.assertIsNone(self.manager.jobs.get('b'*40))

    def test_gap_pack_overlapping_an_earlier_singleton_is_not_retargeted(self):
        self.assert_overlapping_gap_pack_is_not_retargeted(4)

    def test_deferred_gap_pack_overlapping_a_prior_pass_is_not_retargeted(self):
        self.assert_overlapping_gap_pack_is_not_retargeted(1)

    def test_deferred_group_revalidates_new_local_ownership_without_redownload(self):
        task = self.task()
        self.provider.search_tv.side_effect = lambda **kwargs: [] if kwargs['episode'] is None else [self.release('Harbor.Signals.S01.1080p.WEB-DL')]
        self.monitor.run_once(limit=1,submit=True)
        owned = self.home / 'Season 01' / self.filename
        owned.write_bytes(b'episode acquired elsewhere')
        self.tv.bind_file(owned,[task['target_episode_ids'][0]],{'probe_status':'ok','quality_class':'1080p'},[self.library])
        self.monitor.run_once(limit=4,submit=True)
        counts = self.monitor.task(task['id'])['counts']
        self.assertEqual((counts['acquired'],counts['queued']),(1,0))
        self.manager.client.add_magnet.assert_not_called()

    def test_season_search_budget_defers_fallback_without_extra_queries(self):
        task = self.task()
        instant = [0.0]
        self.monitor.monotonic = self.service.monotonic = lambda:instant[0]
        def search(**kwargs):
            instant[0] += 31
            return []
        self.provider.search_tv.side_effect = search
        self.monitor.run_once(limit=4,submit=True)
        self.assertEqual(self.provider.search_tv.call_count,1)
        self.assertEqual(self.monitor.task(task['id'])['episodes'][0]['next_retry'],self.now[0]+18000)

    def test_worker_deadline_defers_unsearched_task_without_timestamp_change(self):
        task = self.task()
        times = iter([0.0,901.0,901.0,901.0,901.0])
        self.monitor.monotonic = lambda:next(times,901.0)
        self.monitor.run_once(submit=True)
        self.assertTrue(all(row['last_search'] is None and row['next_retry']==0 for row in self.monitor.task(task['id'])['episodes']))
        self.provider.search_tv.assert_not_called()

    def test_bounded_fallback_continues_later_gaps_instead_of_repeating_the_first_four(self):
        import json
        from pathlib import Path
        raw = json.loads((Path(__file__).parent/'fixtures/native_tv_cases.json').read_text())
        raw['series']['seasons'][1]['episode_count'] = 7
        raw['episodes'] += [{'season_number':1,'episode_number':n,'title':f'Episode {n}','air_date':'2020-01-04'} for n in (4,5,6,7)]
        self.tv.refresh(raw['series'],raw['episodes'])
        task = self.task()
        self.manager.client.torrents.return_value = []
        def search(**kwargs):
            number = kwargs['episode']
            return [] if number is None or number<5 else [self.release(f'Harbor.Signals.S01E{number:02d}.1080p.WEB-DL',f'{number:x}')]
        self.provider.search_tv.side_effect = search
        self.monitor.run_once(limit=5,submit=True)
        deferred = self.monitor.task(task['id'])['episodes'][4:]
        self.assertTrue(all(row['last_search'] is None and row['next_retry']==0 for row in deferred))
        self.monitor.run_once(limit=5,submit=True)
        self.assertEqual([call.kwargs['episode'] for call in self.provider.search_tv.call_args_list],[None,1,2,3,4,5,6,7])
        self.assertEqual(self.monitor.task(task['id'])['counts']['queued'],3)

    def test_pack_transfer_recovery_failure_is_review_with_intent_preserved(self):
        task = self.task()
        self.provider.search_tv.return_value = [self.release('Harbor.Signals.S01.1080p.WEB-DL')]
        self.monitor.run_once(limit=1,submit=True)
        intent_id = self.monitor.task(task['id'])['episodes'][0]['intent_id']
        self.store.event(intent_id,'import_needs_review',state='import_pending')
        self.manager.jobs.upsert(self.hash,{'state':'needs_review','last_error':'Destination changed during import'})
        self.monitor.run_once(submit=True)
        rows = self.monitor.task(task['id'])['episodes']
        self.assertEqual({row['state'] for row in rows},{'needs_review'})
        self.assertTrue(all('Destination changed' in row['error'] for row in rows))
        self.assertEqual({row['intent_id'] for row in rows},{intent_id})
        self.assertEqual(self.provider.search_tv.call_count,1)

    def test_grouping_excludes_owned_unreleased_claimed_partial_and_bulk_scopes(self):
        # Each boundary has its own disposable store and real worker pass.
        for boundary in ('owned','unreleased','claimed','episodes','bulk','excluded'):
            with self.subTest(boundary=boundary):
                fixture = fixtures.TVAcquisitionTests()
                fixture.setUp()
                try:
                    rows = fixture.tv.episodes(fixture.series,1)
                    if boundary == 'owned':
                        owned = fixture.home / 'Season 01' / fixture.filename
                        owned.write_bytes(b'previously verified episode')
                        fixture.tv.bind_file(owned,[rows[0]['id']],{'probe_status':'ok','quality_class':'1080p'},[fixture.library])
                    elif boundary == 'unreleased':
                        with fixture.tv.store.transaction() as db:
                            db.execute('UPDATE episodes SET air_date="2099-01-01" WHERE id=?',(rows[-1]['id'],))
                    elif boundary == 'claimed':
                        fixture.provider.search_tv.return_value = [self.release('Harbor.Signals.S01E03.1080p.WEB-DL')]
                        decision = fixture.service.search(fixture.series,1,3)['decisions'][0]
                        fixture.service.reserve_intent(decision['decision_token'],'manual-boundary')
                    monitor = TVMonitoring(fixture.tv,fixture.store,fixture.service)
                    scope = {'scope':'episodes','selected_episodes':[row['id'] for row in rows[:2]]} if boundary=='episodes' else {'scope':'series' if boundary=='bulk' else 'season','season':1}
                    draft = monitor.save_task(fixture.series,kind='bulk' if boundary=='bulk' else 'follow',**scope)
                    task = monitor.start_task(draft['id'])
                    if boundary=='excluded':
                        with fixture.store.transaction() as db:
                            db.execute('INSERT INTO tv_task_exclusions VALUES(?,1)',(task['id'],))
                    fixture.provider.search_tv.reset_mock()
                    fixture.provider.search_tv.return_value = []
                    monitor.run_once(limit=10,submit=True)
                    self.assertTrue(all(call.kwargs['episode'] is not None for call in fixture.provider.search_tv.call_args_list))
                    self.assertEqual(monitor.task(task['id'])['counts']['queued'],0)
                finally:
                    fixture.tearDown()

    def test_missing_snapshot_never_expands_when_later_episode_metadata_arrives(self):
        task = self.task()
        import json
        from pathlib import Path
        raw = json.loads((Path(__file__).parent/'fixtures/native_tv_cases.json').read_text())
        raw['series']['seasons'][1]['episode_count'] = 4
        raw['episodes'].append({'season_number':1,'episode_number':4,'title':'Newly released','air_date':'2020-01-04'})
        self.tv.refresh(raw['series'],raw['episodes'])
        self.provider.search_tv.return_value = []
        self.monitor.run_once(limit=10,submit=True)
        fresh = self.monitor.task(task['id'])
        self.assertEqual(fresh['target_episode_ids'],task['target_episode_ids'])
        self.assertEqual([call.kwargs['episode'] for call in self.provider.search_tv.call_args_list],[1,2,3])

    def test_thirteen_episode_pack_verifies_every_binding_and_cleans_staging_once(self):
        import json
        from pathlib import Path
        raw = json.loads((Path(__file__).parent/'fixtures/native_tv_cases.json').read_text())
        raw['series']['seasons'][1]['episode_count'] = 13
        raw['episodes'] += [{'season_number':1,'episode_number':n,'title':f'Episode {n}','air_date':'2020-01-04'} for n in range(4,14)]
        self.tv.refresh(raw['series'],raw['episodes'])
        self.files, paths = [],[]
        for number in range(1,14):
            path = self.manager.staging_dir / f'Harbor.Signals.S01E{number:02d}.1080p.WEB-DL.mkv'
            path.write_bytes(b'synthetic verified episode')
            paths.append(path)
            self.files.append({'name':path.name,'size':path.stat().st_size})
        self.provider.search_tv.return_value = [self.release('Harbor.Signals.S01.1080p.WEB-DL',size=sum(row['size'] for row in self.files))]
        task = self.task()
        self.monitor.run_once(limit=1,submit=True)
        self.assertEqual(self.monitor.task(task['id'])['counts']['queued'],13)
        self.manager.process_completed()
        self.torrent['progress'] = 1
        result = self.manager.process_completed()[0]
        self.assertEqual(result['state'],'imported',result.get('last_error'))
        self.assertEqual(result['tv_import']['imported_files'],13)
        self.monitor.run_once(submit=True)
        self.assertEqual(self.monitor.task(task['id'])['counts']['acquired'],13)
        self.assertEqual(self.monitor.task(task['id'])['state'],'completed')
        self.assertTrue(all(not path.exists() for path in paths))
        self.manager.client.add_magnet.assert_called_once()
        self.assertEqual(len(list(self.home.rglob('*.mkv'))),13)


