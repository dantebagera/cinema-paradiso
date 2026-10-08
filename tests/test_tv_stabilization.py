import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock

from services.advanced_search import normalize_query
from services.acquisition_profiles import default_profile
from services.source_search import ProwlarrClient
from services.streaming_templates import effective_tv_template
from services.tv_catalog_repository import TVCatalogRepository
from services.tv_metadata import TVMetadata
from services.tv_read_model import TVReadModel
from services.tv_search import TVSearch


def query(scope='library', **criteria):
    return {'version': 1, 'scope': scope, 'mode': 'advanced', 'groups': [
        {'type': kind, 'values': values, **({'join': 'or'} if kind in {'genre', 'person', 'keyword', 'resolution', 'library_source'} else {})}
        for kind, values in criteria.items()]}


class SearchTransportTests(unittest.TestCase):
    def provider(self):
        provider = ProwlarrClient('http://fixture.invalid', 'fixture')
        provider._request_json = Mock(return_value=[
            {'id': i, 'name': str(i), 'enable': True, 'capabilities': {'categories': [{'id': c}]}}
            for i, c in [(1, 2000), (2, 5000), (3, 5030)]])
        return provider

    def test_fast_result_survives_stalled_indexer_and_deadline(self):
        provider = self.provider()
        finished = threading.Event()
        def search(**kw):
            if kw['indexer_ids'] == [3]:
                finished.wait(.6)
                return []
            return [{'title': 'Fast result'}]
        provider.search_tv = search
        start = time.monotonic()
        try:
            result = provider.search_tv_report(tmdb_tv_id=4, title='Series', season=1, budget=.1)
            self.assertLess(time.monotonic()-start, .5)
            self.assertEqual(result['items'], [{'title': 'Fast result'}])
            self.assertTrue(result['partial'])
            self.assertEqual([r['state'] for r in result['sources']], ['complete', 'timeout'])
        finally:
            finished.set()

    def test_empty_custom_selection_never_broadcasts(self):
        provider = self.provider(); provider.search_tv = Mock()
        result = provider.search_tv_report(indexer_ids=[], tmdb_tv_id=4, title='Series')
        provider.search_tv.assert_not_called()
        self.assertIn('No enabled TV', result['notice'])

    def test_failures_are_explicit_without_exposing_provider_urls(self):
        provider = self.provider(); provider.search_tv = Mock(side_effect=ValueError('secret URL'))
        result = provider.search_tv_report(tmdb_tv_id=4, title='Series')
        self.assertTrue(result['partial']); self.assertEqual(result['items'], [])
        self.assertNotIn('secret', json.dumps(result))
        self.assertEqual({r['state'] for r in result['sources']}, {'failed'})

    def test_custom_selection_only_calls_capable_selected_indexer(self):
        provider = self.provider(); provider.search_tv = Mock(return_value=[])
        result = provider.search_tv_report(indexer_ids=['1', '2'], tmdb_tv_id=4, title='Series')
        self.assertFalse(result['partial']); self.assertEqual(provider.search_tv.call_args.kwargs['indexer_ids'], [2])

    def test_malformed_provider_payload_is_a_failure_not_empty_success(self):
        provider = self.provider(); provider.search_tv = Mock(return_value={'error':'bad payload'})
        result = provider.search_tv_report(tmdb_tv_id=4, title='Series')
        self.assertTrue(result['partial']); self.assertEqual(result['items'], [])


class TVSearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.repo = TVCatalogRepository(self.root/'tv.sqlite')
        self.metadata = TVMetadata(self.repo, lambda: '')
        self.search = TVSearch(TVReadModel(self.repo), self.metadata, profile=default_profile)
        self.raw = {'id': 7, 'name': 'Café Harbor', 'original_name': 'Original Harbor', 'first_air_date': '2020-01-01',
                    'genres': [{'id': 18, 'name': 'Drama'}], 'origin_country': ['GB'], 'original_language': 'en',
                    'episode_run_time': [45], 'vote_average': 8.2, 'vote_count': 1000, 'keywords': {'results': [{'id': 55, 'name': 'Sea'}]},
                    'created_by': [{'id': 8, 'name': 'Creator One'}],
                    'aggregate_credits': {'cast': [{'id': 9, 'name': 'Actor One', 'roles': [{'character': 'Sailor'}]}], 'crew': [{'id': 10, 'name': 'Writer One', 'department': 'Writing', 'jobs': [{'job': 'Writer'}]}]},
                    'seasons': [{'season_number': 1, 'air_date': '2020-01-01'}],
                    'videos': {'results': [{'key': 'abc123', 'site': 'YouTube', 'type': 'Trailer', 'official': True}]}}
        self.id = self.repo.refresh(self.metadata.normalize(self.raw), [{'season_number': 1, 'episode_number': 1, 'title': 'Pilot', 'air_date': '2020-01-01'}], self.metadata.credits(self.raw))
        assigned = self.root / 'Café Harbor'; assigned.mkdir()
        self.repo.approve_path(assigned, 'folder', self.id)

    def test_combined_criteria_original_title_and_accent_normalization(self):
        criteria = {'title': [{'text': 'cafe'}], 'genre': [{'id': '18', 'label': 'Drama'}],
                    'year': [{'operator': 'between', 'from': 2019, 'to': 2021}], 'rating': [{'operator': 'at_least', 'value': 8}],
                    'runtime': [{'preset': 'custom', 'from': 40, 'to': 50}], 'language': [{'id': 'en', 'label': 'English'}],
                    'country': [{'id': 'GB', 'label': 'UK'}], 'person': [{'id': '8', 'label': 'Creator One', 'role': 'creator'}],
                    'keyword': [{'id': '55', 'label': 'Sea'}]}
        self.assertEqual(self.search.library(query(**criteria))['total'], 1)
        self.assertEqual(self.search.library(query(title=[{'text': 'original'}]))['total'], 1)
        criteria['genre'][0]['exclude'] = True
        self.assertEqual(self.search.library(query(**criteria))['total'], 0)
        with self.assertRaises(ValueError): normalize_query(query(person=[{'id':'8', 'label':'Creator', 'role':'creator'}]))

    def test_library_filters_before_pagination_and_preserves_extra_filters(self):
        for n in range(8, 35):
            self.repo.refresh({**self.metadata.normalize(self.raw), 'tmdb_id': n, 'title': f'Other {n}', 'rating': 1}, [])
        result = self.search.library(query(rating=[{'operator':'at_least','value':8}]), page_size=1)
        self.assertEqual(result['total'], 1); self.assertEqual(result['items'][0]['id'], self.id)
        self.assertEqual(self.search.library(query(), extras={'genre': 'Comedy'})['total'], 0)

    def test_in_progress_is_tv_only_and_tracks_unfinished_series(self):
        value = {'id': 'in_progress', 'label': 'In progress'}
        with self.assertRaises(ValueError):
            normalize_query(query(viewing_status=[value]))
        episodes = [
            {'season_number': 1, 'episode_number': number, 'title': f'Episode {number}', 'air_date': '2020-01-01'}
            for number in (1, 2)
        ]
        self.repo.refresh(self.metadata.normalize(self.raw), episodes, self.metadata.credits(self.raw))
        matches = lambda: self.search.library(query(viewing_status=[value]))['total']
        self.assertEqual(matches(), 0)
        first, second = self.repo.episodes(self.id)
        self.repo.save_progress(first['id'], position_ms=1000, duration_ms=10000)
        self.assertEqual(matches(), 1)
        self.repo.save_progress(first['id'], completed=True)
        self.assertEqual(matches(), 1)
        self.repo.save_progress(second['id'], completed=True)
        self.assertEqual(matches(), 0)

    def test_watchlist_ownership_quality_and_profile_use_available_files(self):
        episode = self.repo.episodes(self.id)[0]; path = self.root/'pilot.WEB-DL.mkv'; path.write_bytes(b'fixture')
        self.repo.bind_file(path, [episode['id']], {'quality_class':'720p', 'audio_tracks_json':'[{"language":"en"}]'}, [self.root])
        self.assertEqual(self.search.library(query(resolution=[{'id':'upgrade','label':'Upgrade'}]))['total'], 1)
        with self.repo.store.transaction() as db: db.execute('INSERT INTO series_curation VALUES(?,1)', (self.id,))
        self.assertEqual(self.search.library(query(viewing_status=[{'id':'watchlist','label':'Watchlist'}]))['total'],1)
        self.assertEqual(self.search.library(query(library_source=[{'id':'web_dl','label':'WEB-DL'}]))['total'],1)
        self.assertEqual(self.search.library(query(), extras={'language': 'English'})['total'],1)
        path.unlink()
        self.assertEqual(self.search.library(query(resolution=[{'id':'720p','label':'720p'}]))['total'],0)

    def test_unknown_runtime_is_not_zero_and_roles_are_distinct(self):
        self.assertEqual(self.search.library(query(person=[{'id':'8','label':'Creator','role':'actor'}]))['total'],0)
        self.assertEqual(self.search.library(query(person=[{'id':'10','label':'Writer','role':'writer'}]))['total'],1)
        self.assertEqual(self.search.options('library')['genre'], [{'id':'18','label':'Drama'}])
        self.assertEqual(self.search.identities('library','keyword','sea'), [{'id':'55','label':'Sea'}])

    def test_sort_accepts_zero_values_and_unknown_metadata(self):
        for row in ({'tmdb_id': 8, 'title': 'Zero', 'rating': 0}, {'tmdb_id': 9, 'title': 'Unknown'}):
            series_id = self.repo.refresh(row, [])
            folder = self.root / row['title']; folder.mkdir()
            self.repo.approve_path(folder, 'folder', series_id)
        result = self.search.library({**query(), 'sort': {'key': 'rating', 'direction': 'desc'}})
        self.assertEqual([r['title'] for r in result['items']], ['Café Harbor', 'Zero', 'Unknown'])
        self.assertEqual(self.search.library(query(runtime=[{'preset':'short'}]))['total'], 1)

    def test_better_version_of_same_episode_satisfies_upgrade_cutoff(self):
        episode = self.repo.episodes(self.id)[0]
        for quality in ('720p', '1080p'):
            path = self.root/f'{quality}.mkv'; path.write_bytes(b'fixture')
            self.repo.bind_file(path, [episode['id']], {'quality_class': quality}, [self.root])
        self.assertEqual(self.search.library(query(resolution=[{'id':'upgrade', 'label':'Upgrade'}]))['total'],0)

    def test_discover_watched_uses_local_released_episode_count(self):
        from services.tv_search import matches
        q=TVSearch.normalize(query('discover',viewing_status=[{'id':'watched','label':'Watched'}]),'discover')
        self.assertTrue(matches({'released_count':3,'completed_count':3,'listed_episode_count':10},q))
        self.assertFalse(matches({'released_count':3,'completed_count':2,'listed_episode_count':10},q))

    def test_series_status_is_tv_discover_only_and_uses_tmdb_status_ids(self):
        status = {'id': '3', 'label': 'Ended'}
        with self.assertRaises(ValueError):
            normalize_query(query('discover', tv_status=[status]))
        with self.assertRaises(ValueError):
            TVSearch.normalize(query('library', tv_status=[status]), 'library')
        with self.assertRaises(ValueError):
            TVSearch.normalize(query('discover', tv_status=[{'id': '6', 'label': 'Other'}]), 'discover')
        self.metadata.request = Mock(return_value={
            'results': [{**self.raw, 'status': ''}], 'total_pages': 1, 'total_results': 1,
        })
        self.metadata.display = lambda row, deadline=None: row
        result = self.search.discover(query('discover', tv_status=[status]))
        self.assertEqual(result['total'], 1)
        self.assertEqual(result['items'][0]['status'], 'Ended')
        provider_call = next(call for call in self.metadata.request.call_args_list if call.args[0] == '/discover/tv')
        self.assertEqual(provider_call.kwargs['with_status'], '3')

    def test_title_plus_status_checks_series_detail_before_counting_matches(self):
        status = {'id': '3', 'label': 'Ended'}
        summary = {key: value for key, value in self.raw.items() if key != 'status'}
        def request(path, **params):
            if path == '/search/tv':
                results = [summary] if params['page'] == 1 else [{**summary, 'id': 8, 'name': 'Harbor Two'}]
                return {'results': results, 'total_pages': 2, 'total_results': 2}
            if path.startswith('/tv/'):
                return {**self.raw, 'id': int(path.rsplit('/', 1)[1]),
                        'status': 'Ended' if path.endswith('/8') else 'Returning Series'}
            raise AssertionError(path)
        self.metadata.request = request
        self.metadata.display = lambda row, deadline=None: row
        result = self.search.discover(query('discover', title=[{'text': 'Harbor'}], tv_status=[status]), page_size=1)
        self.assertTrue(result['complete'])
        self.assertEqual(result['total'], 1)
        self.assertEqual(result['total_pages'], 1)
        self.assertFalse(result['has_next'])
        self.assertEqual([row['tmdb_id'] for row in result['items']], [8])

    def test_local_legacy_query_works_without_metadata_client(self):
        result=TVReadModel(self.repo).library()
        self.assertEqual(result['total'],1)
        self.assertEqual(result['items'][0]['title'],'Café Harbor')

    def test_failed_detail_is_retryable_and_not_a_complete_zero(self):
        failed=[True]
        def request(path,**params):
            if path=='/search/tv':return {'results':[self.raw],'total_pages':1,'total_results':1}
            if path=='/tv/7':
                if failed[0]:raise OSError('offline')
                return self.raw
            if path=='/configuration/languages':return []
            raise AssertionError(path)
        self.metadata.request=request
        q=query('discover',title=[{'text':'Harbor'}],keyword=[{'id':'55','label':'Sea'}])
        first=self.search.discover(q)
        self.assertFalse(first['complete']);self.assertIsNone(first['total'])
        self.assertTrue(first['continue_scan']);self.assertFalse(first['has_next'])
        failed[0]=False
        second=self.search.discover(q)
        self.assertTrue(second['complete']);self.assertEqual(second['total'],1)

    def test_empty_provider_pages_continue_before_pagination(self):
        def request(path,**params):
            if path=='/configuration/languages':return []
            return {'results':[self.raw] if params['page']==4 else [],'total_pages':4,'total_results':1}
        self.metadata.request=request
        q=query('discover',title=[{'text':'Harbor'}])
        first=self.search.discover(q)
        self.assertTrue(first['continue_scan']);self.assertFalse(first['has_next'])
        second=self.search.discover(q)
        self.assertTrue(second['complete']);self.assertEqual(second['items'][0]['tmdb_id'],7)

    def test_person_search_combines_roles_with_keyword_and_runtime(self):
        def request(path, **params):
            if path == '/person/8/tv_credits': return {'crew': [{**self.raw, 'job':'Creator'}]}
            if path == '/tv/7': return self.raw
            if path == '/configuration/languages': return [{'iso_639_1':'en','english_name':'English'}]
            raise AssertionError(path)
        self.metadata.request = request
        result = self.search.discover(query('discover', person=[{'id':'8','label':'Creator One','role':'creator'}],
                                            keyword=[{'id':'55','label':'Sea'}], runtime=[{'preset':'short'}]))
        self.assertEqual([r['tmdb_id'] for r in result['items']], [7])
        self.assertTrue(result['complete'])
        self.assertEqual(result['total'], 1)

    def test_provider_query_mapping_and_filtered_page_totals_are_honest(self):
        self.metadata.request = Mock(return_value={'results':[self.raw], 'total_pages':3, 'total_results':60})
        result = self.search.discover(query('discover', genre=[{'id':'18','label':'Drama'}], year=[{'operator':'exactly','value':2020}]))
        self.assertEqual(result['total'],60)
        provider_call = next(c for c in self.metadata.request.call_args_list if c.args[0] == '/discover/tv')
        self.assertEqual(provider_call.kwargs['first_air_date.gte'],'2020-01-01')
        result = self.search.discover(query('discover', keyword=[{'id':'55','label':'Sea'}], availability=[{'id':'unowned','label':'Not owned'}]), page=2)
        self.assertEqual(result['items'], []); self.assertEqual(result['total'], 1); self.assertEqual(result['page'],2)
        self.assertEqual(result['total_pages'],1); self.assertTrue(result['complete'])

    def test_discover_full_row_pages_cross_tmdb_page_boundaries_without_skips(self):
        rows = [{**self.raw, 'id': identity, 'name': f'Series {identity}'} for identity in range(1, 88)]
        requested = []
        def request(path, **params):
            self.assertEqual(path, '/trending/tv/week')
            provider_page = params['page']
            requested.append(provider_page)
            return {'results': rows[(provider_page-1)*20:provider_page*20],
                    'total_pages': 5, 'total_results': len(rows)}
        self.metadata.request = request
        self.metadata.display = lambda row, deadline=None: row
        query_value = query('discover')
        for size, expected_pages in [(39, 3), (40, 3)]:
            pages = [self.search.discover(query_value, page=number, page_size=size)
                     for number in range(1, expected_pages + 1)]
            self.assertEqual([page['page_size'] for page in pages], [size] * expected_pages)
            self.assertEqual([page['total_pages'] for page in pages], [expected_pages] * expected_pages)
            self.assertEqual([row['tmdb_id'] for page in pages for row in page['items']], list(range(1, 88)))
            self.assertEqual([page['has_next'] for page in pages], [True, True, False])
        self.assertIn(2, requested)
        self.assertIn(4, requested)

    def test_filtered_discover_uses_logical_page_size_for_scan_and_totals(self):
        rows = [{**self.raw, 'id': identity, 'name': f'Series {identity}'} for identity in range(1, 46)]
        def request(path, **params):
            self.assertEqual(path, '/search/tv')
            provider_page = params['page']
            return {'results': rows[(provider_page-1)*20:provider_page*20],
                    'total_pages': 3, 'total_results': len(rows)}
        self.metadata.request = request
        self.metadata.display = lambda row, deadline=None: row
        query_value = query('discover', title=[{'text': 'Series'}])
        first = self.search.discover(query_value, page=1, page_size=39)
        second = self.search.discover(query_value, page=2, page_size=39)
        self.assertEqual([row['tmdb_id'] for row in first['items'] + second['items']], list(range(1, 46)))
        self.assertEqual([len(first['items']), len(second['items'])], [39, 6])
        self.assertTrue(first['has_next'])
        self.assertFalse(second['has_next'])
        self.assertEqual(second['total_pages'], 2)
        self.assertEqual(second['total'], 45)

    def test_preview_is_read_only_and_uses_series_identity_for_stream(self):
        self.metadata.request = Mock(return_value={**self.raw,'id':99})
        preview = self.metadata.preview(99)
        self.assertEqual(preview['stream_target']['tmdb_id'],99)
        self.assertEqual(preview['trailer_url'],'https://www.youtube.com/watch?v=abc123')
        with self.repo.store.connection() as db: self.assertEqual(db.execute('SELECT COUNT(*) FROM series').fetchone()[0],1)

    def test_v1_migration_preserves_identity_and_progress(self):
        ep = self.repo.episodes(self.id)[0]; self.repo.save_progress(ep['id'], completed=True)
        with self.repo.store.connection() as db:
            db.execute('DROP TABLE series_curation'); db.execute('PRAGMA user_version=1')
        old_backup = self.root/'v1-backup.sqlite'
        self.repo.store.backup(old_backup)
        reopened = TVCatalogRepository(self.root/'tv.sqlite')
        self.assertTrue(reopened.episodes(self.id)[0]['completed'])
        self.assertEqual(reopened.store.audit()['schema_version'],6)
        reopened.store.restore(old_backup)
        self.assertTrue(reopened.episodes(self.id)[0]['completed'])
        self.assertFalse(reopened.series(self.id)['watchlisted'])


class StreamingDefaultTests(unittest.TestCase):
    def test_known_movie_provider_supplies_tv_template_without_altering_custom_provider(self):
        self.assertEqual(effective_tv_template('https://streamimdb.ru/embed/movie/{tmdb_id}'), 'https://streamimdb.ru/embed/tv/{tmdb_id}/{season_number}/{episode_number}')
        self.assertEqual(effective_tv_template('https://another.invalid/embed/movie/{tmdb_id}'), '')
        override = 'https://fixture.invalid/{tmdb_id}/{season_number}/{episode_number}'
        self.assertEqual(effective_tv_template('https://streamimdb.ru/embed/movie/{tmdb_id}', override), override)

    def test_config_read_derives_tv_default_without_saving_settings(self):
        import app
        from unittest.mock import patch
        with patch.object(app, '_tv_enabled', True), patch.object(app, '_streaming_tv_url_template', ''), patch.object(app, '_streaming_url_template', 'https://streamimdb.ru/embed/movie/{tmdb_id}'), patch.object(app, '_save_config') as save:
            data = app.app.test_client().get('/api/streaming/config')
            self.assertEqual(data.status_code, 200)
            self.assertEqual(data.json['tv_url_template'], 'https://streamimdb.ru/embed/tv/{tmdb_id}/{season_number}/{episode_number}')
            save.assert_not_called()


if __name__ == '__main__': unittest.main()
