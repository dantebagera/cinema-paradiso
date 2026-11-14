import tempfile
import unittest
from pathlib import Path

from services.tv_catalog_repository import TVCatalogRepository
from services.tv_metadata import TVMetadata
from services.tv_read_model import TVReadModel


class TVCreditPortraitTests(unittest.TestCase):
    def test_aggregate_director_creator_and_writer_portraits_survive_catalog_storage(self):
        raw = {'id': 77, 'name': 'Credit Portraits', 'created_by': [
            {'id': 2, 'name': 'Creator', 'profile_path': '/creator.jpg'}],
            'aggregate_credits': {'cast': [], 'crew': [
                {'id': 1, 'name': 'Director', 'profile_path': '/director.jpg', 'jobs': [{'job': 'Director'}]},
                {'id': 3, 'name': 'Writer', 'department': 'Writing', 'profile_path': '/writer.jpg', 'jobs': [{'job': 'Screenplay'}]},
                {'id': 4, 'name': 'No Photo', 'jobs': [{'job': 'Director'}]},
            ]}}
        with tempfile.TemporaryDirectory() as root:
            repository = TVCatalogRepository(Path(root) / 'tv.sqlite')
            series_id = repository.refresh(TVMetadata.normalize(raw), [], TVMetadata.credits(raw))
            credits = {credit['tmdb_id']: credit for credit in TVReadModel(repository).detail(series_id)['cast']}
            for person_id, name in [(1, 'director'), (2, 'creator'), (3, 'writer')]:
                self.assertEqual(credits[person_id].get('portrait_url', ''), f'https://image.tmdb.org/t/p/w185/{name}.jpg')
            self.assertEqual(credits[4].get('portrait_url', ''), '')

    def test_regular_credits_keep_multiple_directors_with_their_own_portraits(self):
        credits = TVMetadata.credits({'credits': {'crew': [
            {'id': 1, 'name': 'First', 'job': 'Director', 'profile_path': '/first.jpg'},
            {'id': 2, 'name': 'Second', 'job': 'Director', 'profile_path': '/second.jpg'},
        ]}})
        self.assertEqual([credit['tmdb_id'] for credit in credits], [1, 2])
        self.assertTrue(credits[0].get('portrait_url', '').endswith('/first.jpg'))
        self.assertTrue(credits[1].get('portrait_url', '').endswith('/second.jpg'))


if __name__ == '__main__':
    unittest.main()
