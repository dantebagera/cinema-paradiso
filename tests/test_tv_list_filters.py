import json
from pathlib import Path
import tempfile
import unittest
from flask import Flask
from types import SimpleNamespace

from services.tv_catalog_repository import TVCatalogRepository
from services.tv_read_model import TVReadModel
from services.tv_routes import register_tv_routes


class TVListFilterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = TVCatalogRepository(Path(self.temp.name) / 'tv.sqlite')
        fixture = json.loads((Path(__file__).parent / 'fixtures/native_tv_cases.json').read_text())
        self.ids = []
        for index, (title, genre, country, year, rating, votes) in enumerate([
            ('Alpha', 'Drama', 'US', 2020, 6, 100),
            ('Zulu', 'Drama', 'GB', 2024, 8.5, 5000),
            ('Beta', 'Drama', 'GB', 2022, 9, 9000),
            ('Outside this list', 'Drama', 'GB', 2023, 10, 10000)
        ]):
            metadata = {**fixture['series'], 'tmdb_id': 91000 + index, 'title': title, 'genres': [genre], 'origin_country': [country], 'first_air_date': f'{year}-01-01', 'rating': rating, 'votes': votes}
            self.ids.append(self.repo.refresh(metadata, fixture['episodes']))
        self.list_id = self.repo.create_tv_list('Selected shows')['id']
        self.repo.set_tv_list_members(self.list_id, self.ids[:3], True)
        self.read = TVReadModel(self.repo)
        application = Flask(__name__)
        register_tv_routes(application, lambda: {'read': self.read, 'repository': self.repo},
                           lambda: True, SimpleNamespace())
        self.client = application.test_client()

    def query(self, groups=None, sort='auto'):
        return {'version': 1, 'scope': 'discover', 'media_type': 'tv', 'mode': 'simple', 'feed': 'catalog', 'groups': groups or [], 'sort': {'key': sort, 'direction': 'desc'}}

    def test_filters_and_sort_run_before_paging_and_preserve_list_membership(self):
        groups = [
            {'type': 'genre', 'values': [{'id': '18', 'label': 'Drama'}]},
            {'type': 'country', 'values': [{'id': 'GB', 'label': 'United Kingdom'}]},
            {'type': 'year', 'values': [{'operator': 'between', 'from': 2021, 'to': 2025}]},
            {'type': 'rating', 'values': [{'operator': 'at_least', 'value': 8}]},
            {'type': 'minimum_votes', 'values': [{'value': 1000}]}
        ]
        first = self.read.tv_lists(list_id=self.list_id, criteria=self.query(groups, 'vote_count.desc'), page_size=1)
        second = self.read.tv_lists(list_id=self.list_id, criteria=self.query(groups, 'vote_count.desc'), page_size=1, page=2)
        self.assertEqual(first['total'], 2)
        self.assertEqual(first['total_pages'], 2)
        self.assertEqual(first['items'][0]['title'], 'Beta')
        self.assertEqual(second['items'][0]['title'], 'Zulu')
        self.assertEqual(self.read.tv_lists(list_id=self.list_id)['total'], 3)

    def test_invalid_criteria_are_rejected_and_title_search_intersects_filters(self):
        with self.assertRaises(ValueError):
            self.read.tv_lists(list_id=self.list_id, criteria=self.query(sort='unknown'))
        result = self.read.tv_lists(list_id=self.list_id, query='Zulu', criteria=self.query([{'type': 'rating', 'values': [{'operator': 'at_least', 'value': 9}]}]))
        self.assertEqual(result['total'], 0)

    def test_route_filters_before_paging_and_leaves_membership_intact(self):
        response = self.client.get('/api/tv/lists', query_string={
            'list_id': self.list_id, 'page_size': 1,
            'criteria': json.dumps(self.query([
                {'type': 'rating', 'values': [{'operator': 'at_least', 'value': 9}]}
            ]))
        })
        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertEqual(result['total'], 1)
        self.assertEqual(result['total_pages'], 1)
        self.assertEqual([row['title'] for row in result['items']], ['Beta'])
        self.assertEqual(self.client.get('/api/tv/lists', query_string={
            'list_id': self.list_id
        }).get_json()['total'], 3)

    def test_route_rejects_invalid_criteria_instead_of_ignoring_them(self):
        invalid = ['{', 'null', '[]', json.dumps({**self.query(), 'media_type': 'movie'}),
                   json.dumps({**self.query(), 'scope': 'library'}),
                   json.dumps(self.query(sort='unknown')),
                   json.dumps(self.query([{'type': 'invented', 'values': []}]))]
        for criteria in invalid:
            with self.subTest(criteria=criteria):
                response = self.client.get('/api/tv/lists', query_string={
                    'list_id': self.list_id, 'criteria': criteria
                })
                self.assertEqual(response.status_code, 400)
                self.assertIn('error', response.get_json())

    def test_empty_auto_criteria_matches_omitted_default_and_unknown_rating_is_excluded(self):
        default = self.read.tv_lists(list_id=self.list_id)
        self.assertEqual(self.read.tv_lists(list_id=self.list_id, criteria=self.query()), default)
        self.repo.refresh({'tmdb_id': 91003, 'title': 'Unknown rating'}, [])
        self.repo.set_tv_list_members(self.list_id, [self.ids[3]], True)
        result = self.read.tv_lists(list_id=self.list_id, criteria=self.query([
            {'type': 'rating', 'values': [{'operator': 'at_least', 'value': 8}]}
        ]))
        self.assertEqual([row['title'] for row in result['items']], ['Beta', 'Zulu'])


if __name__ == '__main__':
    unittest.main()
