import tempfile
import unittest
from pathlib import Path
from services.movie_ratings_store import MovieRatingsStore, RatingsIdentityConflict


def observation(source='local_saved', **changes):
    return {'key': 'movie:plex:' + 'a' * 24, 'aliases': ['movie:tmdb:44012', 'movie:plex:' + 'a' * 24],
            'source': source, 'critics': 95, 'audience': 77, 'retrieved_at': 1000., 'sequence': 1000., **changes}


class RatingsStoreTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'ratings' / 'movie-ratings.sqlite'
        self.store = MovieRatingsStore(self.path)

    def tearDown(self): self.temp.cleanup()

    def test_missing_cache_read_does_not_create_files(self):
        self.assertEqual(self.store.read_many(['movie:tmdb:44012']), {})
        self.assertFalse(self.path.parent.exists())

    def test_cache_survives_restart_without_catalog(self):
        self.store.publish([observation()])
        result = MovieRatingsStore(self.path).read_many(['movie:tmdb:44012'])
        self.assertEqual(result['movie:tmdb:44012']['local_saved']['audience'], 77)
        self.assertFalse((Path(self.temp.name) / 'catalog.sqlite').exists())

    def test_online_observation_cannot_overwrite_owned_local_saved(self):
        self.store.publish([observation(), observation('online_cache', critics=20, sequence=2000.)])
        result = self.store.read_many(['movie:tmdb:44012'])['movie:tmdb:44012']
        self.assertEqual(result['local_saved']['critics'], 95)
        self.assertEqual(result['online_cache']['critics'], 20)

    def test_older_observation_cannot_replace_newer(self):
        self.store.publish([observation(sequence=2000.), observation(critics=10, sequence=1000.)])
        self.assertEqual(self.store.read_many(['movie:tmdb:44012'])['movie:tmdb:44012']['local_saved']['critics'], 95)

    def test_alias_conflict_does_not_merge_movies(self):
        self.store.publish([observation()])
        with self.assertRaises(RatingsIdentityConflict):
            self.store.publish([observation(key='movie:plex:' + 'b'*24, aliases=['movie:tmdb:44012', 'movie:plex:'+'b'*24])])
        self.assertEqual(self.store.read_many(['movie:tmdb:44012'])['movie:tmdb:44012']['local_saved']['critics'], 95)

    def test_old_epoch_cannot_publish(self):
        self.store.epoch = 2
        self.assertFalse(self.store.publish([observation()], expected_epoch=1))
        self.assertEqual(self.store.read_many(['movie:tmdb:44012']), {})

    def test_partial_sync_enriches_existing_aliases_without_losing_them(self):
        self.store.publish([observation()])
        self.store.publish([observation(aliases=['movie:plex:'+'a'*24], critics=94, sequence=2000.)])
        self.assertEqual(self.store.read_many(['movie:tmdb:44012'])['movie:tmdb:44012']['local_saved']['critics'], 94)


if __name__ == '__main__': unittest.main()
