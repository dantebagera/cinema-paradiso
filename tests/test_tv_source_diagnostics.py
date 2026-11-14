import json
import unittest
from tests import test_verified_tv_acquisition as fixtures
from services.acquisition_store import AcquisitionRepository
from services.tv_monitoring import TVMonitoring


class SourceDiagnosticsTests(unittest.TestCase):
    setUp = fixtures.TVAcquisitionTests.setUp
    tearDown = fixtures.TVAcquisitionTests.tearDown

    def test_wrong_show_with_manual_quality_is_rejected_without_review_action(self):
        self.provider.search_tv.return_value = [{'title':'Wrong.Show.S01E01.1080p.WEB-DL','infoHash':self.hash,'magnetUrl':'magnet:?xt=urn:btih:'+self.hash,'indexerId':7}]
        result = self.service.select_automatic(self.service.search(self.series,1,1,'cp-compatibility',manual=False))
        self.assertEqual(result['state'],'rejected_sources')
        self.assertIsNone(result['diagnostics']['candidates'][0]['review_action'])

    def test_returned_rejections_and_partial_sources_are_separate(self):
        self.provider.search_tv.return_value = [{ 'title':'Wrong.Show.S01E01.1080p.WEB-DL', 'indexerId':7 }]
        review = self.service.search(self.series,1,1,manual=False)
        review['search'] = {'partial':True,'sources':[{'id':7,'name':'Fixture','state':'complete','count':1},{'id':8,'name':'Failed','state':'timeout','count':0}]}
        result = self.service.select_automatic(review)
        self.assertEqual(result['state'],'rejected_sources')
        self.assertEqual(result['diagnostics']['result_count'],1)
        self.assertTrue(result['diagnostics']['partial'])
        self.assertEqual(result['diagnostics']['candidates'][0]['title'],'Wrong.Show.S01E01.1080p.WEB-DL')
        self.assertNotIn('Provider search did not complete',result['error'])

    def test_manual_quality_is_review_and_still_retries_in_five_hours(self):
        now = [1800000000.0]
        monitor = TVMonitoring(self.tv,self.store,self.service,clock=lambda:now[0])
        draft = monitor.save_task(self.series,scope='episodes',action='selected',selected_episodes=[self.tv.episodes(self.series,1)[0]['id']],profile_id='cp-compatibility')
        # Continuing Missing uses the fixed episode set, without season grouping.
        with self.store.transaction() as db:
            db.execute('UPDATE tv_tasks SET action="missing" WHERE id=?',(draft['id'],))
        task = monitor.start_task(draft['id'])
        monitor.run_once(submit=True)
        row = monitor.task(task['id'])['episodes'][0]
        self.assertEqual(row['state'],'needs_review')
        self.assertIsNone(row['intent_id'])
        self.assertEqual(row['next_retry'],now[0]+18000)
        self.assertEqual(monitor.task(task['id'])['counts']['review'],1)
        self.assertEqual(row['source_diagnostics']['state'],'review_required')
        self.assertNotIn('http',json.dumps(row['source_diagnostics']))
        notifications = self.store.notifications()['unread']
        now[0] += 17999
        monitor.run_once(submit=True)
        self.assertEqual(self.provider.search_tv.call_count,1)
        now[0] += 1
        monitor.run_once(submit=True)
        self.assertEqual(self.provider.search_tv.call_count,2)
        self.assertEqual(self.store.notifications()['unread'],notifications)
        self.provider.search_tv.return_value[0]['title'] = 'Harbor.Signals.S01E01.1080p.BluRay.mkv'
        now[0] += 18000
        monitor.run_once(submit=True)
        self.assertEqual(monitor.task(task['id'])['counts']['queued'],1)
        self.manager.client.add_magnet.assert_called_once()

    def test_diagnostics_bound_candidates_redact_links_and_classify_empty_results(self):
        row = {'title':'Wrong.Show.S01E01.1080p.WEB-DL','indexerId':7,'indexer':'http://private.invalid/?apikey=secret'}
        self.provider.search_tv.return_value = [{**row,'title':f'Wrong.Show.{number}.S01E01.1080p.WEB-DL'} for number in range(21)]
        review = self.service.search(self.series,1,1,manual=False)
        review['search'] = {'partial':True,'sources':[{'id':number,'name':f'Failed {number}','state':'timeout','count':0} for number in (8,9,10)]}
        summary = self.service.select_automatic(review)['diagnostics']
        self.assertEqual(summary['result_count'],21)
        self.assertEqual(len(summary['candidates']),5)
        self.assertEqual(len(summary['sources']),3)
        self.assertNotIn('secret',json.dumps(summary))
        for partial, expected in ((False,'no_results'),(True,'provider_failed')):
            self.assertEqual(self.service.select_automatic({'decisions':[],'search':{'partial':partial}})['state'],expected)

    def test_version_three_migrates_once_without_resetting_existing_data(self):
        self.store.save_profile({**self.store.profile('safe-hd'),'name':'Retained customized profile'},make_default=True)
        monitor = TVMonitoring(self.tv,self.store,self.service)
        task = monitor.start_task(monitor.save_task(self.series,scope='season',season=1)['id'])
        decision = self.service.search(self.series,1,1)['decisions'][0]
        intent = self.service.reserve_intent(decision['decision_token'],'migration-tv')['intent']
        movie_decision = {**decision,'decision_token':'movie-migration','target':'movie:tmdb:movie:123','covered_episodes':[]}
        self.store.record_decision(movie_decision)
        self.store.intent('migration-movie',movie_decision)
        with self.store.transaction() as db:
            db.execute('UPDATE tv_task_episodes SET state="queued",intent_id=?,next_retry=18000,last_search=42 WHERE task_id=? AND episode_id=?',(intent['id'],task['id'],task['target_episode_ids'][0]))
        self.store.notify(media_type='movie',source='migration',task_id=None,event_key='movie-kept',severity='info',title='Keep Movie notification',body='Existing Movie data',link='/library')
        tables = ('profiles','settings','tv_tasks','intents','intent_claims','events','notification_events')
        with self.store.connection() as db:
            before_rows = {table:[tuple(row) for row in db.execute(f'SELECT * FROM {table} ORDER BY rowid')] for table in tables}
            episode_rows = [tuple(row)[:-1] for row in db.execute('SELECT * FROM tv_task_episodes ORDER BY episode_id')]
        with self.store.connection() as db:
            columns = {row[1] for row in db.execute('PRAGMA table_info(tv_task_episodes)')}
            if 'source_diagnostics' in columns:
                db.execute('ALTER TABLE tv_task_episodes DROP COLUMN source_diagnostics')
            db.execute('PRAGMA user_version=3')
            db.commit()
        before = self.store.profiles()
        for _ in range(2):
            AcquisitionRepository(self.store.path)
        with self.store.connection() as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],4)
            self.assertIn('source_diagnostics',{row[1] for row in db.execute('PRAGMA table_info(tv_task_episodes)')})
            self.assertEqual({table:[tuple(row) for row in db.execute(f'SELECT * FROM {table} ORDER BY rowid')] for table in tables},before_rows)
            self.assertEqual([tuple(row)[:-1] for row in db.execute('SELECT * FROM tv_task_episodes ORDER BY episode_id')],episode_rows)
            self.assertEqual({row[0] for row in db.execute('SELECT source_diagnostics FROM tv_task_episodes')},{'{}'})
        self.assertEqual(self.store.profiles(),before)
        with self.store.connection() as db:
            db.execute('PRAGMA user_version=5'); db.commit()
        with self.assertRaisesRegex(ValueError,'newer'):
            AcquisitionRepository(self.store.path)
