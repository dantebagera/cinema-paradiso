import json
from pathlib import Path
import tempfile
import unittest

from services.tv_catalog_repository import TVCatalogRepository
from services.tv_read_model import TVReadModel


class TVCatalogTests(unittest.TestCase):
    def version_fixture(self):
        from services.tv_playback import TVPlayback
        rows = self.repo.episodes(self.series_id, 1)[:2]
        files = []
        for row in rows:
            pair = []
            for name, quality in [('z-low', '720p'), ('a-high', '1080p')]:
                path = self.root / f'{row["id"]}-{name}.mkv'
                path.write_bytes(b'synthetic')
                pair.append(self.repo.bind_file(path, [row['id']], {'quality_class': quality}, [self.root]))
            files.append(pair)
        return rows, files, TVPlayback(self.repo, lambda: [self.root])

    def version_paths(self, rows, playback):
        yield playback
        if hasattr(self.repo, 'library_read_context'):
            from types import SimpleNamespace
            from services.tv_playback import TVPlayback
            context = self.repo.library_read_context()
            yield TVPlayback(SimpleNamespace(episode=self.repo.episode, series=self.repo.series,
                episodes=lambda *a, **kw: self.repo.library_episode_rows(*a, **kw, read_context=context)), lambda: [self.root])

    def test_version_order_and_default_target_are_preserved(self):
        rows, files, playback = self.version_fixture()
        self.assertEqual(files, [[1, 2], [3, 4]])
        for adapter in self.version_paths(rows, playback):
            values = adapter.repository.episodes(self.series_id, 1)[:2]
            self.assertEqual([[v['file_id'] for v in row['versions']] for row in values], [[1, 2], [3, 4]])
            for row, pair in zip(rows, files):
                self.assertEqual(adapter.target(row['id']), f'tv:episode:{row["id"]}:file:{pair[0]}')

    def test_saved_and_explicit_versions_are_preserved(self):
        rows, files, playback = self.version_fixture()
        self.repo.save_progress(rows[0]['id'], files[0][1], position_ms=123)
        for adapter in self.version_paths(rows, playback):
            self.assertEqual(adapter.target(rows[0]['id']), f'tv:episode:{rows[0]["id"]}:file:2')
            self.assertEqual(adapter.target(rows[0]['id'], 1), f'tv:episode:{rows[0]["id"]}:file:1')

    def test_unavailable_version_selection_is_preserved(self):
        from services.player_catalog import PlayerMediaError
        rows, files, playback = self.version_fixture()
        self.repo.save_progress(rows[0]['id'], 2)
        (self.root/f'{rows[0]["id"]}-a-high.mkv').unlink()
        for adapter in self.version_paths(rows, playback):
            self.assertEqual(adapter.target(rows[0]['id']), f'tv:episode:{rows[0]["id"]}:file:1')
            with self.assertRaisesRegex(PlayerMediaError, 'Episode file is missing'):
                adapter.target(rows[0]['id'], 2)
        (self.root/f'{rows[0]["id"]}-z-low.mkv').unlink()
        for adapter in self.version_paths(rows, playback):
            with self.assertRaisesRegex(PlayerMediaError, 'Episode file is missing'):
                adapter.target(rows[0]['id'])

    def test_queue_preserves_current_and_successor_file_keys(self):
        rows, files, playback = self.version_fixture()
        current = {'episode_id': rows[0]['id'], 'path_key': f'tv:episode:{rows[0]["id"]}:file:2'}
        for unavailable in (False, True):
            if unavailable:
                for name in ('z-low', 'a-high'): (self.root/f'{rows[1]["id"]}-{name}.mkv').unlink()
            for adapter in self.version_paths(rows, playback):
                queue = adapter.queue(current)
                expected = [{'path_key': current['path_key'], 'title': f'{rows[0]["code"]} · {rows[0]["title"]}',
                             'section': 'Season 1', 'available': True, 'reason': ''},
                            {'path_key': f'missing:tv:{rows[1]["id"]}' if unavailable else f'tv:episode:{rows[1]["id"]}:file:3',
                             'title': f'{rows[1]["code"]} · {rows[1]["title"]}', 'section': 'Season 1',
                             'available': not unavailable, 'reason': 'Episode is missing locally' if unavailable else ''}]
                remaining = self.repo.episodes(self.series_id)
                for row in remaining:
                    if row['season_number'] == 0 or row['id'] in {r['id'] for r in rows}: continue
                    reason = 'Episode has not aired' if not row['released'] else 'Episode is missing locally'
                    expected.append({'path_key':f'missing:tv:{row["id"]}', 'title':f'{row["code"]} · {row["title"]}',
                                     'section':f'Season {row["season_number"]}', 'available':False,'reason':reason})
                self.assertEqual(queue,{'title':self.fixture['series']['title'],'items':expected})

    def test_stored_unavailable_versions_remain_unplayable_when_files_exist(self):
        from services.player_catalog import PlayerMediaError
        rows, files, playback = self.version_fixture()
        self.repo.save_progress(rows[0]['id'], files[0][1])
        with self.repo.store.transaction() as db:
            db.execute('UPDATE media_files SET available=0 WHERE id=?', (files[0][1],))
        self.assertTrue((self.root/f'{rows[0]["id"]}-a-high.mkv').is_file())
        for adapter in self.version_paths(rows, playback):
            self.assertEqual(adapter.target(rows[0]['id']), f'tv:episode:{rows[0]["id"]}:file:1')
            with self.assertRaisesRegex(PlayerMediaError, 'Episode file is missing'):
                adapter.target(rows[0]['id'], files[0][1])
        with self.repo.store.transaction() as db:
            db.execute('UPDATE media_files SET available=0 WHERE id=?', (files[0][0],))
        self.assertTrue((self.root/f'{rows[0]["id"]}-z-low.mkv').is_file())
        for adapter in self.version_paths(rows, playback):
            with self.assertRaisesRegex(PlayerMediaError, 'Episode file is missing'):
                adapter.target(rows[0]['id'])

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
