"""Approved homes, not release labels or numeric IDs, determine TV placement."""
from pathlib import Path
from contextlib import closing
import sqlite3
import tempfile
import unittest

from services.tv_catalog_repository import TVCatalogRepository


class TVImportDestinationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.library = self.root / 'tv'
        self.library.mkdir()
        self.tv = TVCatalogRepository(self.root / 'tv.sqlite')
        self.series = self.tv.refresh({'tmdb_id': 823456, 'title': 'Independent Fixture'}, [
            {'season_number': season, 'episode_number': number, 'air_date': '2020-01-01'}
            for season in (1, 27, 28) for number in (1, 2)])

    def home(self, name='Collection', season_name='Season 27', season=27):
        home = self.library / name
        folder = home / season_name
        folder.mkdir(parents=True)
        self.tv.approve_path(home, 'folder', self.series)
        media = folder / 'existing.mkv'
        media.write_bytes(b'existing episode')
        episode = self.tv.episodes(self.series, season)[0]
        self.tv.bind_files([{'path': media, 'episode_ids': [episode['id']], 'facts': {}}], [self.library])
        return home, folder

    def resolve(self, season=27):
        return self.tv.resolve_import_destination(self.series, season, [self.library])

    def test_hierarchy_wins_over_flat_approved_release_directory_without_creating_folders(self):
        home, folder = self.home()
        flat = self.library / '823456'
        flat.mkdir()
        self.tv.approve_path(flat, 'folder', self.series)
        source = flat / 'flat.mkv'
        source.write_bytes(b'flat episode')
        self.tv.bind_file(source, [self.tv.episodes(self.series, 27)[1]['id']], {}, [self.library])
        result = self.resolve()
        self.assertEqual((result['state'], result['show_home'], result['path']), ('ready', str(home), str(folder)))
        next_season = self.resolve(28)
        self.assertEqual(next_season['path'], str(home / 'Season 28'))
        self.assertFalse((home / 'Season 28').exists())
        with self.tv.store.connection() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM tv_import_homes').fetchone()[0], 0)

    def test_south_park_shape_uses_structure_not_title_or_id(self):
        home, folder = self.home('South Park')
        numeric = self.library / '2190'
        numeric.mkdir()
        self.tv.approve_path(numeric, 'folder', self.series)
        self.assertEqual(self.resolve()['path'], str(folder))

    def test_padded_convention_survives_explicit_preference_and_database_reopen(self):
        home, _ = self.home(season_name='Season 01', season=1)
        self.tv.set_import_home(self.series, home, [self.library])
        reopened = TVCatalogRepository(self.tv.store.path)
        result = reopened.resolve_import_destination(self.series, 28, [self.library])
        self.assertEqual(result['path'], str(home / 'Season 28'))
        self.assertEqual(self.resolve(1)['path'], str(home / 'Season 01'))

    def test_credible_home_ambiguity_requires_explicit_approved_choice(self):
        first, _ = self.home('First')
        second, season = self.home('Second')
        result = self.resolve()
        self.assertEqual(result['state'], 'needs_choice')
        self.assertIsNone(result['path'])
        self.assertEqual(set(result['candidates']), {str(first), str(second)})
        self.tv.set_import_home(self.series, second, [self.library])
        self.assertEqual(self.resolve()['path'], str(season))

    def test_no_home_and_flat_layout_do_not_guess_a_title_or_id_path(self):
        self.assertEqual(self.resolve()['state'], 'needs_home')
        flat = self.library / 'Collection'
        flat.mkdir()
        self.tv.approve_path(flat, 'folder', self.series)
        self.assertEqual(self.resolve()['state'], 'needs_home')
        with self.assertRaises(ValueError):
            self.tv.set_import_home(self.series, self.library / 'unapproved', [self.library])

    def test_excluded_or_outside_home_is_not_usable(self):
        home, folder = self.home()
        self.tv.set_import_home(self.series, home, [self.library])
        self.tv.exclude_path(folder, 'folder', 'not an import destination')
        self.assertNotEqual(self.resolve()['state'], 'ready')
        self.assertNotEqual(self.tv.resolve_import_destination(self.series, 27, [self.root / 'other'])['state'], 'ready')

    def test_excluded_extras_do_not_disqualify_home_but_excluded_season_still_blocks(self):
        home, folder = self.home()
        extras = home / 'Extras'
        extras.mkdir()
        ignored = extras / 'bonus.mkv'
        ignored.write_bytes(b'excluded extra')
        self.tv.exclude_path(ignored, 'file', 'Not an episode')
        self.assertEqual(self.resolve()['path'], str(folder))
        self.tv.set_import_home(self.series, home, [self.library])
        self.assertEqual(self.resolve()['state'], 'ready')
        self.tv.exclude_path(folder, 'folder', 'Do not import here')
        self.assertNotEqual(self.resolve()['state'], 'ready')

    def test_other_series_assignment_blocks_overlapping_destination(self):
        home, folder = self.home()
        other = self.tv.refresh({'tmdb_id': 88, 'title': 'Other'}, [])
        self.tv.approve_path(folder, 'folder', other)
        self.assertNotEqual(self.resolve()['state'], 'ready')
        with self.assertRaises(ValueError):
            self.tv.set_import_home(other, home, [self.library])

    def test_conflicting_conventions_and_unproved_specials_require_review(self):
        home, _ = self.home(season_name='Season 01', season=1)
        (home / 'Season 2').mkdir()
        self.assertNotEqual(self.resolve(28)['state'], 'ready')
        self.assertNotEqual(self.resolve(0)['state'], 'ready')

    def test_schema_four_upgrade_and_restore_preserve_bindings(self):
        self.home()
        backup = self.root / 'v4.sqlite'
        self.tv.store.backup(backup)
        with closing(sqlite3.connect(backup)) as db:
            db.execute('DROP TABLE tv_import_homes')
            db.execute('PRAGMA user_version=4')
            db.commit()
        upgraded = TVCatalogRepository(backup)
        self.assertEqual(upgraded.store.audit()['schema_version'], 5)
        self.assertTrue(upgraded.episodes(self.series, 27)[0]['available'])
        with closing(sqlite3.connect(backup)) as db:
            db.execute('DROP TABLE tv_import_homes')
            db.execute('PRAGMA user_version=4')
            db.commit()
        self.tv.store.restore(backup)
        self.assertEqual(self.tv.store.audit()['schema_version'], 5)
        self.assertEqual(self.resolve()['state'], 'ready')
