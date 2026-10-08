import json
from pathlib import Path
import tempfile
import unittest

from services.tv_catalog_repository import TVCatalogRepository
from services.tv_read_model import TVReadModel


class TVCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.fixture = json.loads((Path(__file__).parent / 'fixtures/native_tv_cases.json').read_text())
        self.repo = TVCatalogRepository(self.root / 'tv-catalog.sqlite')
        self.series_id = self.repo.refresh(self.fixture['series'], self.fixture['episodes'], [{'tmdb_id': 8, 'name': 'Test Person', 'role': 'Creator'}])

    def tearDown(self):
        self.temp.cleanup()

    def test_refresh_restart_and_backup_preserve_multiple_versions_progress_and_people(self):
        episode = self.repo.episodes(self.series_id, 1)[0]
        first = self.root / 'first.mkv'
        second = self.root / 'second.mkv'
        first.write_bytes(b'first synthetic video')
        second.write_bytes(b'second synthetic video')
        file_id = self.repo.bind_file(first, [episode['id']], {'quality_class': '1080p'}, [self.root])
        self.repo.bind_file(second, [episode['id']], {'quality_class': '720p'}, [self.root])
        self.repo.save_progress(episode['id'], file_id, position_ms=1000, duration_ms=5000)
        self.repo.refresh(self.fixture['series'], self.fixture['episodes'], [{'tmdb_id': 8, 'name': 'Test Person', 'role': 'Creator'}])
        reopened = TVCatalogRepository(self.root / 'tv-catalog.sqlite')
        rows = reopened.episodes(self.series_id, 1)
        self.assertEqual(len(rows[0]['versions']), 2)
        self.assertEqual(rows[0]['position_ms'], 1000)
        self.assertEqual(reopened.series(self.series_id)['cast'][0]['tmdb_id'], 8)
        backup = self.root / 'backup.sqlite'
        reopened.store.backup(backup)
        reopened.save_progress(episode['id'], file_id, completed=True)
        reopened.store.restore(backup)
        self.assertFalse(reopened.episodes(self.series_id, 1)[0]['completed'])
        self.assertEqual(reopened.store.audit(), {
            'integrity': 'ok', 'foreign_keys': [], 'schema_version': 6,
            'orphans': {'episodes': 0, 'files': 0, 'bindings': 0, 'identities': 0, 'progress': 0},
        })
        self.assertFalse((self.root / 'catalog.sqlite').exists())

    def test_multi_episode_file_has_independent_watched_state(self):
        episodes = self.repo.episodes(self.series_id, 1)
        path = self.root / 'double.mkv'
        path.write_bytes(b'two episodes')
        file_id = self.repo.bind_file(path, [row['id'] for row in episodes[:2]], {}, [self.root])
        self.repo.save_progress(episodes[0]['id'], file_id, completed=True)
        rows = self.repo.episodes(self.series_id, 1)
        self.assertTrue(rows[0]['completed'])
        self.assertFalse(rows[1]['completed'])
        self.assertEqual(rows[0]['versions'][0]['file_id'], rows[1]['versions'][0]['file_id'])

    def test_file_inventory_keeps_one_physical_row_with_all_episode_bindings(self):
        episodes = self.repo.episodes(self.series_id, 1)
        path = self.root / 'double.mkv'
        path.write_bytes(b'two episodes')
        file_id = self.repo.bind_file(path, [row['id'] for row in episodes[:2]], {'quality_class': '1080p'}, [self.root])
        read = TVReadModel(self.repo)
        result = read.files(page=1, page_size=1)
        self.assertEqual(result['total'], 1)
        self.assertEqual(result['items'][0]['file_id'], file_id)
        self.assertEqual(result['items'][0]['filename'], 'double.mkv')
        self.assertEqual(result['items'][0]['facts']['quality_class'], '1080p')
        self.assertEqual(len(result['items'][0]['episodes']), 2)
        self.assertEqual(read.files(query='double')['total'], 1)
        self.assertEqual(read.files(query='nonexistent')['total'], 0)

    def test_renumbered_provider_episode_is_quarantined_without_losing_bindings(self):
        episodes = [dict(row, provider_id=str(i + 100)) for i, row in enumerate(self.fixture['episodes'])]
        self.repo.refresh(self.fixture['series'], episodes)
        changed = [dict(row) for row in episodes]
        changed[1]['episode_number'] = 9
        self.repo.refresh(self.fixture['series'], changed)
        original = self.repo.episodes(self.series_id, 1)[0]
        self.assertEqual(original['episode_number'], 1)
        self.assertTrue(original['reconciliation_required'])
        from services.tv_read_model import TVReadModel
        detail = TVReadModel(self.repo).detail(self.series_id)
        self.assertFalse(detail['primary_action']['playable'])
        self.assertFalse(detail['stream_target']['released'])
        self.assertFalse(any(row['episode_number'] == 9 for row in self.repo.episodes(self.series_id, 1)))

    def test_stale_progress_cannot_overwrite_rewatch(self):
        episode_id = self.repo.episodes(self.series_id, 1)[0]['id']
        self.repo.save_progress(episode_id, completed=True)
        result = self.repo.save_progress(episode_id, restart=True)
        self.assertEqual(result['revision'], 1)
        self.assertFalse(self.repo.save_progress(episode_id, completed=True, expected_revision=0)['accepted'])

    def test_invalid_binding_and_duplicate_metadata_do_not_publish(self):
        path = self.root / 'video.mkv'
        path.write_bytes(b'video')
        with self.assertRaises(ValueError):
            self.repo.bind_file(path, [9999], {}, [self.root])
        with self.assertRaises(ValueError):
            self.repo.refresh(self.fixture['series'], self.fixture['episodes'] * 2)
        with self.repo.store.connection() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM media_files').fetchone()[0], 0)
