from pathlib import Path
import tempfile
import unittest

from services.tv_catalog_repository import TVCatalogRepository
from services.tv_ingestion import TVIngestion
from services.tv_library_discovery import TVLibraryDiscovery, candidate_units


class FakeMetadata:
    def __init__(self, repository):
        self.repository = repository
        self.shows = {
            196322: {'id': 196322, 'name': 'Dark Matter', 'first_air_date': '2024-05-08'},
            62425: {'id': 62425, 'name': 'Dark Matter', 'first_air_date': '2015-06-12'},
            37863: {'id': 37863, 'name': 'Fullmetal Alchemist', 'first_air_date': '2003-10-04'},
            31911: {'id': 31911, 'name': 'Fullmetal Alchemist: Brotherhood', 'first_air_date': '2009-04-05'},
            3051: {'id': 3051, 'name': 'Lost in Space', 'first_air_date': '1965-09-15'},
            75758: {'id': 75758, 'name': 'Lost in Space', 'first_air_date': '2018-04-13'},
        }

    def request(self, path, **params):
        if path.startswith('/tv/'):
            return self.shows[int(path.rsplit('/', 1)[1])]
        if path == '/search/tv':
            query = params['query'].casefold()
            ids = ([37863, 31911] if 'fullmetal' in query else
                   [3051, 75758] if 'lost in space' in query else [])
            return {'results': [self.shows[value] for value in ids]}
        raise AssertionError(path)

    def refresh(self, tmdb_id, *, season_scope=None):
        row = self.shows[tmdb_id]
        return self.repository.refresh(
            {'tmdb_id': tmdb_id, 'title': row['name'], 'first_air_date': row['first_air_date'],
             'seasons': [{'season_number': 1}]},
            [{'season_number': 1, 'episode_number': 1, 'title': 'Episode 1'}],
            season_scope=season_scope,
        )


class TVLibraryDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repository = TVCatalogRepository(self.root / 'catalog.sqlite')
        self.ingestion = TVIngestion(self.repository, lambda: [self.root], probe=lambda _: {'probe_status': 'ok'})
        self.owner = TVLibraryDiscovery(self.ingestion, FakeMetadata(self.repository), self.repository)

    def tearDown(self):
        self.temp.cleanup()

    def file(self, folder, name):
        path = self.root / folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'fixture')
        return path

    def test_unique_year_and_numeric_tv_identity_create_cards_without_manual_mapping(self):
        dark = self.file('196322', 'Dark.Matter.2024.S01E01.mkv')
        self.file('[Anime Time] Fullmetal Alchemist (2003) (Anime+Movie)', 'Fullmetal.Alchemist.01.mkv')
        self.file('[Anime Time] Fullmetal Alchemist (2003) (Anime+Movie)', 'Fullmetal.Alchemist.02.mkv')
        self.file('Lost In Space Season 1', 'Lost.In.Space.S01E01.mkv')
        result = self.owner.run()
        self.assertEqual(result['identified'], 2)
        self.assertEqual(result['review'], 1)
        self.assertEqual({row['tmdb_id'] for row in self.repository.path_assignments()}, {196322, 37863})
        self.assertEqual(self.ingestion.scan_approved()['accepted'], 2)
        self.assertEqual(self.repository.episodes(1, 1)[0]['versions'][0]['path'], str(dark))
        self.assertEqual(len(self.repository.path_assignments()), 2)

    def test_collection_children_are_separate_candidate_units(self):
        self.file('TV Collection/First Show', 'S01E01.mkv')
        self.file('TV Collection/First Show', 'S01E02.mkv')
        self.file('TV Collection/Second Show', 'S01E01.mkv')
        self.file('TV Collection/Second Show', 'S01E02.mkv')
        units = candidate_units(self.ingestion.inventory())
        self.assertEqual({Path(row['path']).name for row in units}, {'First Show', 'Second Show'})


if __name__ == '__main__':
    unittest.main()
