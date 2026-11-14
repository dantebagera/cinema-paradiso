"""Upcoming is an API result contract, including replacements before paging."""
import copy
import datetime
import unittest
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

import app


class CalendarDate(datetime.date):
    current = datetime.date(2026, 10, 12)

    @classmethod
    def today(cls):
        return cls.current


def movie(identity, release='2026-10-12'):
    return {'id': identity, 'title': f'Upcoming {identity:03}', 'release_date': release,
            'genre_ids': [18], 'vote_average': 8, 'vote_count': 100,
            'original_language': 'en', 'popularity': 1000 - identity}


class UpcomingDiscoverTests(unittest.TestCase):
    def setUp(self):
        CalendarDate.current = datetime.date(2026, 10, 12)
        self.rows = [movie(1, '2026-10-11'), movie(2), movie(3, '2026-10-13'),
                     movie(4, ''), movie(5, '2026-02-30'), movie(6, '20261013'),
                     movie(7, None), movie(8, 'unknown')]
        self.urls = []
        app._tmdb_discover_window_cache.clear()
        self.addCleanup(app._tmdb_discover_window_cache.clear)
        for patcher in (patch.object(app, '_tmdb_key', 'isolated-upcoming-key'),
                        patch.object(app, '_tmdb_genres', {18: 'Drama'}),
                        patch.object(app, '_ensure_tmdb_genres'),
                        patch.object(app.datetime, 'date', CalendarDate),
                        patch.object(app, '_tmdb_fetch_provider_page', side_effect=self.provider)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def provider(self, url):
        self.urls.append(url)
        page = int(parse_qs(urlparse(url).query)['page'][0])
        return {'page': page, 'results': copy.deepcopy(self.rows[(page - 1) * 20:page * 20]),
                'total_pages': max(1, (len(self.rows) + 19) // 20), 'total_results': len(self.rows)}

    def request(self, route='advanced', page=1, size=40, groups=None, sort='auto', feed='upcoming', **native):
        with app.app.test_client() as client:
            if route == 'native':
                response = client.get('/api/tmdb/discover', query_string={
                    'list': feed, 'page': page, 'page_size': size, **native})
            else:
                response = client.post('/api/tmdb/discover/advanced', json={
                    'query': {'version': 1, 'scope': 'discover', 'mode': 'advanced',
                              'feed': feed, 'groups': groups or [],
                              'sort': {'key': sort, 'direction': 'asc' if sort == 'title.asc' else 'desc'}},
                    'page': page, 'page_size': size})
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()

    @staticmethod
    def ids(payload):
        return [int(row['tmdb_id']) for row in payload['results']]

    def test_both_upcoming_routes_keep_today_and_future_and_reject_unknown_or_invalid_dates(self):
        for route in ('native', 'advanced'):
            with self.subTest(route=route):
                result = self.request(route)
                self.assertEqual(self.ids(result), [2, 3])
                self.assertEqual(result['total_results'], 2)
                self.assertEqual(result['total_pages'], 1)
                self.assertEqual(result['total_scope'], 'exact')
                self.assertFalse(result['has_next'])

    def test_replacements_fill_39_and_40_card_pages_without_losing_final_matches(self):
        self.rows = []
        for identity in range(1, 82):
            self.rows.extend([movie(identity + 1000, '2026-10-11'), movie(identity)])
            if identity % 10 == 0:
                self.rows.append(movie(identity))
        for route in ('native', 'advanced'):
            for size in (39, 40):
                app._tmdb_discover_window_cache.clear()
                with self.subTest(route=route, size=size):
                    pages = [self.request(route, page, size) for page in (1, 2, 3)]
                    self.assertEqual([len(p['results']) for p in pages], [size, size, 81 - size * 2])
                    self.assertEqual([i for p in pages for i in self.ids(p)], list(range(1, 82)))
                    self.assertTrue(pages[0]['has_next'])
                    self.assertFalse(pages[2]['has_next'])
                    self.assertEqual(pages[2]['total_results'], 81)
                    self.assertEqual(pages[2]['total_pages'], 3)
                    self.assertEqual(self.ids(self.request(route, 1, size)), list(range(1, size + 1)))

    def test_native_home_request_finishes_sparse_finite_feed_beyond_local_scan_budget(self):
        self.rows = [movie(i, '2026-10-11') for i in range(1, 241)] + [movie(300)]
        result = self.request('native', size=100)
        self.assertEqual(self.ids(result), [300])
        self.assertFalse(result['budget_exhausted'])
        self.assertEqual(result['total_results'], 1)
        self.assertFalse(result['has_next'])

    def test_additional_provider_criteria_keep_the_upcoming_floor(self):
        cases = [([], 'popularity.desc'),
                 ([{'type': 'genre', 'values': [{'id': '18', 'label': 'Drama'}]}], 'auto'),
                 ([{'type': 'year', 'values': [{'operator': 'at_least', 'value': 2020}]}], 'auto')]
        for groups, sort in cases:
            with self.subTest(groups=groups, sort=sort):
                app._tmdb_discover_window_cache.clear()
                self.urls.clear()
                result = self.request(groups=groups, sort=sort)
                self.assertEqual(self.ids(result), [2, 3])
                url = urlparse(self.urls[0])
                self.assertEqual(url.path, '/3/discover/movie')
                self.assertEqual(parse_qs(url.query)['primary_release_date.gte'], ['2026-10-12'])

    def test_later_year_floor_and_native_criteria_are_intersected(self):
        self.rows = [movie(1, '2030-01-01')]
        for route in ('native', 'advanced'):
            with self.subTest(route=route):
                app._tmdb_discover_window_cache.clear()
                self.urls.clear()
                self.request(route, groups=[{'type': 'year', 'values': [{'operator': 'at_least', 'value': 2030}]}], year_from='2030')
                self.assertEqual(parse_qs(urlparse(self.urls[0]).query)['primary_release_date.gte'], ['2030-01-01'])

    def test_native_filtered_route_also_removes_past_dates(self):
        self.assertEqual(self.ids(self.request('native', genre='18')), [2, 3])
        self.assertEqual(parse_qs(urlparse(self.urls[0]).query)['primary_release_date.gte'], ['2026-10-12'])

    def test_upcoming_title_and_ownership_paths_enforce_the_same_date_rule(self):
        groups_list = [[{'type': 'title', 'values': [{'text': 'Upcoming'}]}],
                       [{'type': 'availability', 'values': [{'id': 'unowned', 'label': 'Not owned'}]}]]
        with patch.object(app, '_find_owned_curation_movies', side_effect=lambda rows: [None] * len(rows)):
            for groups in groups_list:
                with self.subTest(groups=groups):
                    self.assertEqual(self.ids(self.request(groups=groups)), [2, 3])

    def test_person_credits_are_filtered_before_counting_and_paging(self):
        groups = [{'type': 'person', 'values': [{'id': '10', 'label': 'Actor', 'role': 'actor'}]}]
        with patch.object(app, '_tmdb_person_credit_ids', return_value=({str(r['id']) for r in self.rows}, self.rows)):
            first = self.request(size=1, groups=groups)
            second = self.request(page=2, size=1, groups=groups)
        self.assertEqual(self.ids(first), [2])
        self.assertEqual(self.ids(second), [3])
        self.assertEqual(first['total_results'], 2)
        self.assertFalse(second['has_next'])

    def test_calendar_rollover_invalidates_upcoming_snapshot(self):
        for route in ('native', 'advanced'):
            with self.subTest(route=route):
                CalendarDate.current = datetime.date(2026, 10, 12)
                self.assertEqual(self.ids(self.request(route)), [2, 3])
                CalendarDate.current = datetime.date(2026, 10, 13)
                self.assertEqual(self.ids(self.request(route)), [3])

    def test_ineligible_duplicate_credit_cannot_hide_a_later_eligible_movie(self):
        groups = [{'type': 'person', 'values': [{'id': '10', 'label': 'Actor', 'role': 'actor'}]}]
        credits = [movie(1, ''), movie(1), movie(2, '2026-10-11'), movie(2, '2026-10-13')]
        with patch.object(app, '_tmdb_person_credit_ids', return_value=({'1', '2'}, credits)):
            result = self.request(groups=groups)
        self.assertEqual(self.ids(result), [1, 2])
        self.assertEqual(result['total_results'], 2)

    def test_unfinished_local_scan_is_retryable_then_exposes_only_proven_final_matches(self):
        self.rows = [movie(i, '2026-10-11') for i in range(1, 221)] + [movie(300)]
        groups = [{'type': 'title', 'values': [{'text': 'Upcoming'}]}]
        first = self.request(groups=groups)
        self.assertEqual(first['results'], [])
        self.assertTrue(first['budget_exhausted'])
        self.assertTrue(first['retryable'])
        self.assertIsNone(first['total_results'])
        final = self.request(groups=groups)
        self.assertEqual(self.ids(final), [300])
        self.assertEqual(final['total_results'], 1)
        self.assertFalse(final['has_next'])

    def test_non_upcoming_feeds_still_return_historical_and_unknown_dates(self):
        for route in ('native', 'advanced'):
            with self.subTest(route=route):
                self.assertEqual(self.ids(self.request(route, feed='popular')), list(range(1, 9)))

    def test_provider_failure_does_not_commit_partial_batch_and_retry_fills_page(self):
        self.rows = []
        for identity in range(1, 82):
            self.rows.extend([movie(identity + 1000, '2026-10-11'), movie(identity)])
        for route in ('native', 'advanced'):
            app._tmdb_discover_window_cache.clear()
            failed = [False]

            def flaky_provider(url):
                if parse_qs(urlparse(url).query)['page'] == ['2'] and not failed[0]:
                    failed[0] = True
                    raise RuntimeError('Isolated provider failure')
                return self.provider(url)

            with self.subTest(route=route), patch.object(app, '_tmdb_fetch_provider_page', side_effect=flaky_provider):
                with app.app.test_client() as client:
                    response = (client.get('/api/tmdb/discover?list=upcoming&page_size=40') if route == 'native'
                                else client.post('/api/tmdb/discover/advanced', json={
                                    'query': {'version': 1, 'scope': 'discover', 'mode': 'simple',
                                              'groups': [], 'feed': 'upcoming',
                                              'sort': {'key': 'auto', 'direction': 'desc'}},
                                    'page': 1, 'page_size': 40}))
                self.assertGreaterEqual(response.status_code, 500)
                self.assertIn('error', response.get_json())
                retried = self.request(route)
                self.assertEqual(self.ids(retried), list(range(1, 41)))
                self.assertTrue(retried['has_next'])

    def test_empty_and_exact_multiple_have_no_phantom_next_page(self):
        for count in (0, 3, 40, 80):
            self.rows = [movie(i) for i in range(1, count + 1)] + [movie(900, '2026-10-11')]
            for route in ('native', 'advanced'):
                app._tmdb_discover_window_cache.clear()
                with self.subTest(count=count, route=route):
                    final = self.request(route, page=max(1, (count + 39) // 40))
                    self.assertFalse(final['has_next'])
                    self.assertEqual(final['total_results'], count)


if __name__ == '__main__':
    unittest.main()
