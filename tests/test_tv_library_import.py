from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import app

from services.tv_catalog_repository import TVCatalogRepository
from services.tv_filename_parser import parse_episode_name
from services.tv_ingestion import TVIngestion


class TVLibraryImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = TVCatalogRepository(self.root / 'tv-catalog.sqlite')
        self.harbor = self.repo.refresh(
            {'tmdb_id': 900001, 'title': 'Harbor Signals', 'seasons': [{'season_number': 1}]},
            [{'season_number': 1, 'episode_number': n, 'title': f'Episode {n}'} for n in range(1, 4)],
        )
        self.alien = self.repo.refresh(
            {'tmdb_id': 900002, 'title': 'Alien Show', 'seasons': [{'season_number': 1}]},
            [{'season_number': 1, 'episode_number': 2, 'title': 'Episode 2'}],
        )
        self.ingestion = TVIngestion(self.repo, lambda: [self.root], probe=lambda _: {'probe_status': 'ok'})

    def tearDown(self):
        self.temp.cleanup()

    def file(self, folder, name):
        path = self.root / folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'fixture')
        return path

    def test_inventory_is_read_only_and_mixed_title_requires_review(self):
        folder = self.root / 'Mixed'
        own = self.file('Mixed', 'Harbor.Signals.S01E01.mkv')
        other = self.file('Mixed', 'Alien.Show.S01E02.mkv')
        self.file('Mixed', 'unparsed.mkv')
        snapshot = self.ingestion.inventory()
        self.assertEqual(snapshot['total'], 3)
        self.assertEqual(len(snapshot['groups'][0]['files']), 3)
        self.assertEqual(self.repo.path_assignments(), [])
        self.ingestion.approve(folder, 'folder', self.harbor)
        result = self.ingestion.scan_approved()
        self.assertEqual(result, {'accepted': 1, 'unchanged': 0, 'needs_review': 2, 'ignored': 0, 'unassigned': 0, 'total': 3})
        self.assertEqual(self.repo.episodes(self.harbor, 1)[0]['versions'][0]['path'], str(own))
        self.assertFalse(self.repo.episodes(self.harbor, 1)[1]['versions'])
        self.assertEqual(self.ingestion.scan_approved()['unchanged'], 1)
        self.ingestion.approve(other, 'file', self.alien)
        self.assertEqual(self.ingestion.scan_approved()['accepted'], 1)
        self.assertEqual(self.repo.episodes(self.alien, 1)[0]['versions'][0]['path'], str(other))

    def test_unapproved_paths_are_not_linked_and_approval_stays_within_root(self):
        self.file('Unapproved', 'Harbor.Signals.S01E01.mkv')
        self.assertEqual(self.ingestion.scan_approved()['unassigned'], 1)
        self.assertFalse(self.repo.episodes(self.harbor, 1)[0]['versions'])
        with self.assertRaises(ValueError):
            self.ingestion.approve(self.root.parent, 'folder', self.harbor)

    def test_nested_show_folder_blocks_a_parent_assignment(self):
        parent = self.root / 'Harbor Signals'
        child = parent / 'Alien Show'
        path = self.file('Harbor Signals/Alien Show', 'S01E02.mkv')
        self.ingestion.approve(parent, 'folder', self.harbor)
        self.assertEqual(self.ingestion.scan_approved()['needs_review'], 1)
        self.assertFalse(self.repo.episodes(self.harbor, 1)[1]['versions'])
        self.assertIn(str(child), [row['path'] for row in self.ingestion.inventory()['groups'][0]['subfolders']])
        self.ingestion.approve(child, 'folder', self.alien)
        self.assertEqual(self.ingestion.scan_approved()['accepted'], 1)
        self.assertEqual(self.repo.episodes(self.alien, 1)[0]['versions'][0]['path'], str(path))

    def test_annotated_season_folder_and_absolute_episode_number_bind(self):
        folder = self.root / 'Harbor Signals'
        path = self.file('Harbor Signals/Season 1 - (2024-25)', '[Group] Harbor Signals - 001 - Pilot.mkv')
        self.ingestion.approve(folder, 'folder', self.harbor)
        self.assertEqual(self.ingestion.scan_approved()['accepted'], 1)
        self.assertEqual(self.repo.episodes(self.harbor, 1)[0]['versions'][0]['path'], str(path))
        claim = parse_episode_name('Planet.Earth.01.From.Pole.to.Pole.2006.1080p.HDDVD.x264-AJP.mkv')
        self.assertEqual((claim['series_title'], claim['absolute_number']), ('Planet.Earth', 1))

    def test_season_episode_words_and_number_only_files_bind_in_single_season_folder(self):
        folder = self.root / 'Harbor Signals'
        first = self.file('Harbor Signals/Season 1', 'Harbor Signals Season 01 Episode 01 - Pilot.mp4')
        second = self.file('Harbor Signals/Season 1', '02 - Second.mp4')
        self.ingestion.approve(folder, 'folder', self.harbor)
        self.assertEqual(self.ingestion.scan_approved()['accepted'], 2)
        self.assertEqual(self.repo.episodes(self.harbor, 1)[0]['versions'][0]['path'], str(first))
        self.assertEqual(self.repo.episodes(self.harbor, 1)[1]['versions'][0]['path'], str(second))
        self.assertEqual(parse_episode_name('10 - Love.mkv')['absolute_number'], 10)

    def test_numbered_documentary_parts_and_same_show_miniseries_folder(self):
        folder = self.root / 'Harbor Signals'
        first = self.file('Harbor Signals/Harbor Signals - Mini-Series', '01 Harbor Signals - Part 1.mp4')
        self.ingestion.approve(folder, 'folder', self.harbor)
        self.assertEqual(self.ingestion.scan_approved()['accepted'], 1)
        self.assertEqual(self.repo.episodes(self.harbor, 1)[0]['versions'][0]['path'], str(first))
        claim = parse_episode_name('BBC.Harbor.Signals.2of3.The.Journey.avi')
        self.assertEqual((claim['series_title'], claim['absolute_number'], claim['absolute_total']), ('Harbor.Signals', 2, 3))

    def test_absolute_number_requires_one_regular_season_and_matching_title(self):
        folder = self.root / 'Harbor Signals'
        self.file('Harbor Signals/Season 1', 'Alien Show - 001.mkv')
        self.ingestion.approve(folder, 'folder', self.harbor)
        self.assertEqual(self.ingestion.scan_approved()['needs_review'], 1)
        self.assertFalse(self.repo.episodes(self.harbor, 1)[0]['versions'])
        multi = self.repo.refresh(
            {'tmdb_id': 900003, 'title': 'Two Seasons', 'seasons': [{'season_number': 1}, {'season_number': 2}]},
            [{'season_number': 1, 'episode_number': 1}, {'season_number': 2, 'episode_number': 1}],
        )
        second = self.file('Two Seasons', 'Two Seasons - 001.mkv')
        self.ingestion.approve(second.parent, 'folder', multi)
        self.assertEqual(self.ingestion.scan_approved()['needs_review'], 2)
        self.assertFalse(self.repo.episodes(multi, 1)[0]['versions'])

    def test_folder_alias_and_explicit_season_resolve_absolute_episode(self):
        multi = self.repo.refresh(
            {'tmdb_id': 900004, 'title': 'Harbor Signals', 'seasons': [{'season_number': 1}, {'season_number': 2}]},
            [{'season_number': 1, 'episode_number': 1}, {'season_number': 2, 'episode_number': 1}],
        )
        folder = self.root / 'Harbor Signals (Port Messages) SE01'
        path = self.file(folder.name, 'Port.Messages.01.Pilot.mkv')
        self.ingestion.approve(folder, 'folder', multi)
        self.assertEqual(self.ingestion.scan_approved()['accepted'], 1)
        self.assertEqual(self.repo.episodes(multi, 1)[0]['versions'][0]['path'], str(path))
        self.assertFalse(self.repo.episodes(multi, 2)[0]['versions'])

    def test_fixed_match_closes_prior_review_and_extras_stay_unbound(self):
        folder = self.root / 'Harbor Signals'
        episode = self.file('Harbor Signals/Season 1 - (2024-25)', 'Harbor.Signals.S01E01.mkv')
        extra = self.file('Harbor Signals/Featurettes', 'Harbor.Signals.S01E02.mkv')
        self.ingestion.approve(folder, 'folder', self.harbor)
        self.repo.review({'series_id': self.harbor, 'path': str(episode), 'claim': parse_episode_name(episode.name)}, 'Prior false review')
        self.repo.review({'series_id': self.harbor, 'path': str(extra), 'claim': parse_episode_name(extra.name)}, 'Prior false review')
        result = self.ingestion.scan_approved()
        self.assertEqual((result['accepted'], result['ignored']), (1, 1))
        with self.repo.store.connection() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM ingestion_candidates WHERE state='needs_review'").fetchone()[0], 0)
        self.assertFalse(self.repo.episodes(self.harbor, 1)[1]['versions'])

    def test_repeated_review_keeps_one_open_item_per_series_and_file(self):
        path = self.file('Harbor Signals', 'unknown.mkv')
        first = {'series_id': self.harbor, 'path': str(path), 'claim': {'scope': 'unknown'}}
        second = {'series_id': self.harbor, 'path': str(path), 'claim': {'scope': 'absolute', 'absolute_number': 1}}
        self.repo.review(first, 'Old parser')
        self.repo.review(second, 'New parser')
        with self.repo.store.connection() as db:
            rows = db.execute("SELECT payload,reason FROM ingestion_candidates WHERE state='needs_review'").fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['reason'], 'New parser')

    def test_reassignment_keeps_existing_binding_and_requests_review(self):
        folder = self.root / 'Harbor Signals'
        path = self.file('Harbor Signals', 'S01E02.mkv')
        self.ingestion.approve(folder, 'folder', self.harbor)
        self.assertEqual(self.ingestion.scan_approved()['accepted'], 1)
        self.ingestion.approve(path, 'file', self.alien)
        self.assertEqual(self.ingestion.scan_approved()['needs_review'], 1)
        self.assertEqual(self.repo.episodes(self.harbor, 1)[1]['versions'][0]['path'], str(path))
        self.assertFalse(self.repo.episodes(self.alien, 1)[0]['versions'])

    def test_episode_title_containing_trailer_is_not_an_extra(self):
        claim = parse_episode_name('South.Park.S06E05.The.New.Terrance.and.Phillip.Movie.Trailer.mkv')
        self.assertFalse(claim['ignored'])
        self.assertTrue(parse_episode_name('South.Park.S06E05.trailer.mkv')['ignored'])
        self.assertTrue(parse_episode_name('Harbor.Signals.S01E02.sample.mkv')['ignored'])

    def test_assignments_survive_repository_reopen(self):
        folder = self.root / 'Harbor'
        self.file('Harbor', 'Harbor.Signals.S01E01.mkv')
        self.ingestion.approve(folder, 'folder', self.harbor)
        reopened = TVCatalogRepository(self.root / 'tv-catalog.sqlite')
        self.assertEqual(reopened.path_assignments()[0]['series_id'], self.harbor)
        self.assertEqual(reopened.store.audit()['schema_version'], 4)

    def test_v2_catalog_migrates_without_losing_episodes(self):
        with self.repo.store.connection() as db:
            db.execute('DROP TABLE tv_path_assignments')
            db.execute('PRAGMA user_version=2')
        reopened = TVCatalogRepository(self.root / 'tv-catalog.sqlite')
        self.assertEqual(reopened.store.audit()['schema_version'], 4)
        self.assertEqual(len(reopened.episodes(self.harbor, 1)), 3)
        self.assertEqual(reopened.path_assignments(), [])

    def test_http_inventory_approval_and_scan_use_the_same_ingestion_owner(self):
        folder = self.root / 'Harbor'
        self.file('Harbor', 'Harbor.Signals.S01E01.mkv')
        services = {'repository': self.repo, 'ingestion': self.ingestion}
        key = Path(app._user_data_dir).resolve() / 'tv-catalog.sqlite'
        with patch.object(app, '_tv_enabled', True), patch.dict(app._tv_services._instances, {key: services}):
            client = app.app.test_client()
            inventory = client.get('/api/tv/library/inventory')
            self.assertEqual(inventory.status_code, 200)
            self.assertEqual(inventory.json['total'], 1)
            self.assertFalse(self.repo.episodes(self.harbor, 1)[0]['versions'])
            approved = client.post('/api/tv/library/assignments', json={
                'path': str(folder), 'kind': 'folder', 'series_id': self.harbor})
            self.assertEqual(approved.status_code, 200)
            scanned = client.post('/api/tv/library/scan', json={})
            self.assertEqual(scanned.status_code, 200)
            self.assertEqual(scanned.json['accepted'], 1)


if __name__ == '__main__':
    unittest.main()
