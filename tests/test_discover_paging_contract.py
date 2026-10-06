"""Discover page counts are a returned-result contract, not just a request size."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import threading
import unittest
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

import app


def query(groups=None):
    return {"version": 1, "scope": "discover", "mode": "advanced",
            "groups": groups or [], "sort": {"key": "auto", "direction": "desc"},
            "feed": "popular"}


def movie(identity):
    return {"id": identity, "title": f"Movie {identity}", "release_date": "2024-01-01",
            "genre_ids": [18], "vote_average": 8.0, "vote_count": 100,
            "original_language": "en"}


class DiscoverPagingContractTests(unittest.TestCase):
    def setUp(self):
        self.batches = [list(range(1, 21)), list(range(20, 40)), list(range(39, 59)),
                        list(range(58, 78)), list(range(77, 82))]
        self.fetched = []
        self.fetch_lock = threading.Lock()
        self.sort = 'auto'
        app._tmdb_discover_window_cache.clear()
        self.addCleanup(app._tmdb_discover_window_cache.clear)
        for patcher in (patch.object(app, '_tmdb_key', 'isolated-test-key'),
                        patch.object(app, '_ensure_tmdb_genres'),
                        patch.object(app, '_tmdb_fetch_provider_page', side_effect=self.provider)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def provider(self, url):
        page = int(parse_qs(urlparse(url).query)['page'][0])
        with self.fetch_lock:
            self.fetched.append(page)
        return {'page': page, 'results': [movie(i) for i in self.batches[page - 1]],
                'total_pages': len(self.batches), 'total_results': sum(map(len, self.batches))}

    def request_page(self, route, page, size, groups=None):
        request_query = query(groups)
        request_query['sort']['key'] = self.sort
        with app.app.test_client() as client:
            response = (client.get(f'/api/tmdb/discover?list=popular&page={page}&page_size={size}')
                        if route == 'native' else client.post('/api/tmdb/discover/advanced',
                        json={'query': request_query, 'page': page, 'page_size': size}))
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()

    @staticmethod
    def identities(payload):
        return [int(item['tmdb_id']) for item in payload['results']]

    def test_overlaps_fill_every_nonfinal_page_and_preserve_the_entire_remainder(self):
        for route in ('native', 'advanced'):
            for size in (39, 40):
                with self.subTest(route=route, size=size):
                    pages = [self.request_page(route, n, size) for n in (1, 2, 3)]
                    self.assertEqual([len(p['results']) for p in pages], [size, size, 81 - 2 * size])
                    self.assertEqual([i for p in pages for i in self.identities(p)], list(range(1, 82)))
                    self.assertTrue(pages[0]['has_next'])
                    self.assertTrue(pages[1]['has_next'])
                    self.assertFalse(pages[2]['has_next'])
                    self.assertEqual(pages[2]['total_pages'], 3)
                    self.assertEqual(pages[2]['total_results'], 81)

    def test_page_order_and_layout_changes_do_not_change_the_unique_stream(self):
        for route in ('native', 'advanced'):
            with self.subTest(route=route):
                second = self.request_page(route, 2, 39)
                first = self.request_page(route, 1, 39)
                collapsed = self.request_page(route, 2, 40)
                self.assertEqual(self.identities(first), list(range(1, 40)))
                self.assertEqual(self.identities(second), list(range(40, 79)))
                self.assertEqual(self.identities(collapsed), list(range(41, 81)))
                self.assertEqual(self.identities(self.request_page(route, 2, 39)), self.identities(second))

    def test_small_empty_and_exact_multiple_results_have_no_phantom_next_page(self):
        for count in (0, 3, 39, 40, 78, 80):
            for route in ('native', 'advanced'):
                for size in (39, 40):
                    with self.subTest(count=count, route=route, size=size):
                        app._tmdb_discover_window_cache.clear()
                        ids = list(range(1, count + 1))
                        self.batches = [ids[i:i + 20] for i in range(0, count, 20)] or [[]]
                        final_page = max(1, (count + size - 1) // size)
                        payload = self.request_page(route, final_page, size)
                        self.assertEqual(self.identities(payload), ids[(final_page - 1) * size:])
                        self.assertFalse(payload['has_next'])
                        self.assertEqual(payload['total_results'], count)
                        self.assertEqual(payload['total_pages'], final_page)

    def test_title_filter_pages_fill_before_slicing_and_keep_final_matches(self):
        groups = [{'type': 'title', 'values': [{'text': 'Movie'}]},
                  {'type': 'genre', 'join': 'or', 'values': [{'id': '18', 'label': 'Drama'}]}]
        pages = [self.request_page('advanced', n, 39, groups) for n in (1, 2, 3)]
        self.assertEqual([len(p['results']) for p in pages], [39, 39, 3])
        self.assertEqual(set(i for p in pages for i in self.identities(p)), set(range(1, 82)))
        self.assertFalse(pages[-1]['has_next'])

    def test_concurrent_requests_keep_complete_identical_pages(self):
        with ThreadPoolExecutor(max_workers=4) as executor:
            pages = list(executor.map(lambda _: self.request_page('advanced', 2, 39), range(4)))
        self.assertTrue(all(self.identities(p) == list(range(40, 79)) for p in pages))
        self.assertEqual(sorted(self.fetched), list(range(1, 6)))

    def test_local_ownership_filter_fills_pages_before_slicing(self):
        ids = list(range(1, 163))
        self.batches = [ids[i:i + 20] for i in range(0, len(ids), 20)]
        groups = [{'type': 'availability', 'values': [{'id': 'owned', 'label': 'Owned'}]}]
        with patch.object(app, '_find_owned_curation_movies', side_effect=lambda summaries: [
                {'path': 'isolated-test.mkv'} if int(m['tmdb_id']) % 2 == 0 else None
                for m in summaries]):
            pages = [self.request_page('advanced', n, 39, groups) for n in (1, 2, 3)]
        self.assertEqual([len(p['results']) for p in pages], [39, 39, 3])
        self.assertEqual([i for p in pages for i in self.identities(p)], list(range(2, 163, 2)))
        self.assertFalse(pages[-1]['has_next'])

    def test_sorted_title_pages_publish_one_complete_stable_order(self):
        self.batches = [list(range(n, n + 20)) for n in (1, 21, 41, 61)]
        self.sort = 'title.asc'
        groups = [{'type': 'title', 'values': [{'text': 'Movie'}]}]
        original = self.provider

        def sorted_provider(url):
            data = original(url)
            for item in data['results']:
                item['title'] = f'Movie {"Z" if item["id"] <= 40 else "A"}{item["id"]:03d}'
            return data

        with patch.object(app, '_tmdb_fetch_provider_page', side_effect=sorted_provider):
            pages = [self.request_page('advanced', n, 39, groups) for n in (1, 2, 3)]
            revisited = self.request_page('advanced', 1, 39, groups)
        expected = list(range(41, 81)) + list(range(1, 41))
        self.assertEqual([i for p in pages for i in self.identities(p)], expected)
        self.assertEqual(self.identities(revisited), expected[:39])
        self.assertEqual([len(p['results']) for p in pages], [39, 39, 2])

    def test_sorted_title_scan_budget_does_not_publish_an_unfinished_order(self):
        self.batches = [list(range(n, n + 20)) for n in range(1, 421, 20)]
        self.sort = 'title.asc'
        groups = [{'type': 'title', 'values': [{'text': 'Movie'}]}]
        first = self.request_page('advanced', 1, 39, groups)
        self.assertTrue(first['budget_exhausted'])
        self.assertTrue(first['retryable'])
        self.assertEqual(first['results'], [])
        second = self.request_page('advanced', 1, 39, groups)
        self.assertTrue(second['budget_exhausted'])
        final = self.request_page('advanced', 1, 39, groups)
        self.assertFalse(final['budget_exhausted'])
        self.assertEqual(len(final['results']), 39)
        self.assertEqual(final['total_results'], 420)

    def test_active_snapshot_cannot_expire_during_a_provider_request(self):
        entered, resume = threading.Event(), threading.Event()
        registered = threading.Event()
        original = self.provider
        original_entry = app._tmdb_discover_cache_entry
        callers = [0]
        clock = [100]

        @contextmanager
        def cache_entry(key):
            with original_entry(key) as entry:
                with self.fetch_lock:
                    callers[0] += 1
                    if callers[0] == 2:
                        registered.set()
                yield entry

        def provider(url):
            page = int(parse_qs(urlparse(url).query)['page'][0])
            if page == 1:
                entered.set()
                self.assertTrue(resume.wait(5))
            return original(url)

        with patch.object(app.time, 'monotonic', side_effect=lambda: clock[0]), \
                patch.object(app, '_tmdb_fetch_provider_page', side_effect=provider), \
                patch.object(app, '_tmdb_discover_cache_entry', side_effect=cache_entry), \
                ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(self.request_page, 'advanced', 1, 39)
            self.assertTrue(entered.wait(5))
            clock[0] += app.TMDB_DISCOVER_WINDOW_CACHE_TTL_SECONDS + 1
            second = executor.submit(self.request_page, 'advanced', 1, 39)
            self.assertTrue(registered.wait(5))
            for future in (first, second):
                self.assertFalse(future.done())
            resume.set()
            self.assertEqual(self.identities(first.result()), self.identities(second.result()))
        self.assertEqual(self.fetched.count(1), 1)

    def test_cache_capacity_evicts_idle_queries_and_preserves_active_snapshot(self):
        with patch.object(app, 'TMDB_DISCOVER_WINDOW_CACHE_LIMIT', 2):
            with app._tmdb_discover_cache_entry('active') as active:
                with app._tmdb_discover_cache_entry('idle'):
                    pass
                with app._tmdb_discover_cache_entry('new'):
                    self.assertEqual(len(app._tmdb_discover_window_cache), 2)
                    self.assertIs(app._tmdb_discover_window_cache['active'], active)
                    self.assertNotIn('idle', app._tmdb_discover_window_cache)

    def test_provider_limit_keeps_all_reachable_final_movies_without_fetching_page_501(self):
        self.batches = [list(range((n - 1) * 20 + 1, n * 20 + 1)) for n in range(1, 701)]
        payload = self.request_page('advanced', 250, 40)
        self.assertEqual(self.identities(payload), list(range(9961, 10001)))
        self.assertFalse(payload['has_next'])
        self.assertEqual(payload['provider_total_pages'], 700)
        self.assertEqual(payload['total_pages'], 250)
        self.assertEqual(self.fetched, list(range(1, 501)))

    def test_expired_query_snapshot_starts_a_new_unique_stream(self):
        with patch.object(app.time, 'monotonic', return_value=100):
            self.assertEqual(len(self.request_page('advanced', 1, 39)['results']), 39)
        self.batches = [[900, 901, 902]]
        with patch.object(app.time, 'monotonic', return_value=100 + app.TMDB_DISCOVER_WINDOW_CACHE_TTL_SECONDS):
            payload = self.request_page('advanced', 1, 39)
        self.assertEqual(self.identities(payload), [900, 901, 902])
        self.assertFalse(payload['has_next'])

    def test_failed_provider_batch_is_retried_without_skipping_or_losing_prior_movies(self):
        original = self.provider
        failed = False

        def provider(url):
            nonlocal failed
            page = int(parse_qs(urlparse(url).query)['page'][0])
            if page == 3 and not failed:
                failed = True
                raise TimeoutError('isolated provider timeout')
            return original(url)

        with patch.object(app, '_tmdb_fetch_provider_page', side_effect=provider):
            with app.app.test_client() as client:
                failed_response = client.post('/api/tmdb/discover/advanced',
                    json={'query': query(), 'page': 2, 'page_size': 39})
            self.assertEqual(failed_response.status_code, 502)
            payload = self.request_page('advanced', 2, 39)
        self.assertEqual(self.identities(payload), list(range(40, 79)))
        self.assertEqual(self.fetched, list(range(1, 6)))


if __name__ == '__main__':
    unittest.main()
