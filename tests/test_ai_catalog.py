import threading
import unittest
from services.ai_catalog import AICatalog, movie_scope_decision
from tests.test_company_discovery import studio_query


class CatalogueTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.rows = [
            {'id': 1, 'title': 'Later', 'release_date': '2001-01-01', 'runtime': 95, 'production_companies': [{'id': 10}, {'id': 20}], 'genre_ids': [18]},
            {'id': 2, 'title': 'Long documentary', 'release_date': '1999-01-01', 'runtime': 180, 'production_companies': [{'id': 10}, {'id': 20}], 'genre_ids': [99]},
            {'id': 3, 'title': 'Short', 'release_date': '2000-01-01', 'runtime': 15, 'production_companies': [{'id': 10}, {'id': 20}], 'genre_ids': [18]},
            {'id': 4, 'title': 'Unknown runtime', 'release_date': '2000-01-01', 'runtime': None, 'production_companies': [{'id': 10}, {'id': 20}], 'genre_ids': [18]},
            {'id': 5, 'title': 'Wrong studio', 'release_date': '2000-01-01', 'runtime': 90, 'production_companies': [{'id': 77}], 'genre_ids': [18]},
        ]
        self.catalogue = AICatalog(self.get, details=lambda identity: next(r for r in self.rows if str(r['id']) == str(identity)),
            person_seed=lambda plan: None, filter_local=lambda rows, groups: rows)

    def get(self, endpoint, params):
        self.calls.append((endpoint, params))
        page = params.get('page', 1)
        return {'results': self.rows[(page - 1) * 2:page * 2], 'page': page, 'total_pages': 3, 'total_results': 5}

    def test_full_pagination_global_sort_long_films_and_unknowns(self):
        result = self.catalogue.collect(studio_query(), requested_count=None, cancel=threading.Event())
        self.assertEqual([m['id'] for m in result.movies], [2, 1])
        self.assertEqual(result.unresolved_count, 1)
        self.assertEqual(result.coverage, 'partial')
        self.assertEqual(result.fetched_pages, 3)
        self.assertEqual(result.excluded_count, 2)

    def test_person_seed_still_applies_every_company_year_genre_and_local_condition(self):
        self.catalogue.person_seed = lambda plan: self.rows
        query = studio_query()
        query['groups'] += [
            {'type': 'person', 'join': 'or', 'values': [{'id': '9', 'label': 'Fixture Director', 'role': 'director'}]},
            {'type': 'year', 'values': [{'operator': 'at_most', 'value': 2000}]},
            {'type': 'availability', 'values': [{'id': 'unowned', 'label': 'Unowned'}]}]
        local_calls = []
        self.catalogue.filter_local = lambda rows, groups: local_calls.append(groups) or rows
        result = self.catalogue.collect(query, requested_count=None, cancel=threading.Event())
        self.assertEqual([m['id'] for m in result.movies], [2])
        self.assertTrue(local_calls)
        self.assertEqual(local_calls[0][0]['type'], 'availability')

    def test_failed_page_is_partial_not_a_complete_prefix(self):
        original = self.catalogue.provider_get
        def get(endpoint, params):
            if params.get('page') == 2:
                raise RuntimeError('synthetic provider unavailable')
            return original(endpoint, params)
        self.catalogue.provider_get = get
        result = self.catalogue.collect(studio_query(), requested_count=None, cancel=threading.Event())
        self.assertEqual(result.coverage, 'partial')
        self.assertEqual(result.reason, 'provider_page_failed')
        self.assertFalse(result.can_prepare_all)

    def test_explicit_continuation_resumes_failed_provider_page_with_exact_scope(self):
        state = []
        original = self.catalogue.provider_get
        self.catalogue.provider_get = lambda endpoint, params: original(endpoint, params) if params['page'] == 1 else (_ for _ in ()).throw(RuntimeError('offline'))
        first = self.catalogue.collect(studio_query(), cancel=threading.Event(), checkpoint=state.append)
        self.assertEqual(first.coverage, 'partial')
        self.catalogue.provider_get = original
        self.calls.clear()
        result = self.catalogue.collect(studio_query(), cancel=threading.Event(), resume=state[-1])
        self.assertEqual([params['page'] for endpoint, params in self.calls], [1, 2, 3])  # Recheck provider evidence before resuming.
        self.assertEqual([row['id'] for row in result.movies], [2, 1])
        changed = studio_query()
        changed['sort']['key'] = 'title.asc'
        with self.assertRaises(ValueError):
            self.catalogue.collect(changed, cancel=threading.Event(), resume=state[-1])

    def test_company_resolution_keeps_namesakes_and_later_pages_without_choosing_first(self):
        self.catalogue.provider_get = lambda endpoint, params: {'page': params['page'], 'total_pages': 2,
            'total_results': 2, 'results': [{'id': params['page'], 'name': 'Same Studio', 'origin_country': 'US' if params['page'] == 1 else 'JP'}]}
        first = self.catalogue.resolve_company('Same Studio', page=1)
        second = self.catalogue.resolve_company('Same Studio', page=2)
        self.assertEqual(first['candidates'][0]['country'], 'US')
        self.assertEqual(second['candidates'][0]['country'], 'JP')
        self.assertEqual(first['next_page'], 2)
        self.assertNotIn('selected_id', first)

    def test_unknown_release_runtime_and_tv_are_not_fabricated_eligible(self):
        for row in [{'runtime': 90}, {'release_date': '2001-01-01'}, {'runtime': 90, 'release_date': '2001-01-01', 'media_type': 'tv'}]:
            self.assertNotEqual(movie_scope_decision(row), 'eligible')

    def test_overlapping_provider_pages_cannot_prove_a_missing_member_complete(self):
        self.catalogue.provider_get = lambda endpoint, params: {'page': params['page'], 'total_pages': 2,
            'total_results': 3, 'results': self.rows[:2]}
        result = self.catalogue.collect(studio_query(), requested_count=None, cancel=threading.Event())
        self.assertEqual(result.coverage, 'partial')
        self.assertEqual(result.reason, 'provider_membership_changed')

    def test_global_sort_precedes_top_n_and_factual_genres_have_no_hidden_vote_floor(self):
        result = self.catalogue.collect(studio_query(), requested_count=1, cancel=threading.Event())
        self.assertEqual([row['id'] for row in result.movies], [2])
        query = studio_query()
        query['groups'] = [{'type': 'genre', 'join': 'or', 'values': [{'id': '18', 'label': 'Drama'}]}]
        def low_vote_provider(endpoint, params):
            rows = [{**self.rows[0], 'vote_count': 1}] if params.get('vote_count.gte', 0) <= 1 else []
            return {'page': 1, 'total_pages': 1, 'total_results': len(rows), 'results': rows}
        self.catalogue.provider_get = low_vote_provider
        result = self.catalogue.collect(query, requested_count=None, cancel=threading.Event())
        self.assertEqual([row['id'] for row in result.movies], [1])

    def test_provider_page_limit_is_partial_and_never_fetches_an_illegal_page(self):
        self.catalogue.provider_get = lambda endpoint, params: {'page': params['page'], 'total_pages': 501,
            'total_results': 0, 'results': []}
        result = self.catalogue.collect(studio_query(), requested_count=None, cancel=threading.Event())
        self.assertEqual(result.fetched_pages, 500)
        self.assertEqual(result.reason, 'provider_page_limit')
        self.assertEqual(result.coverage, 'partial')
