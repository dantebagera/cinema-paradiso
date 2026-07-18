import json
import os
import tempfile
import time
import unittest
from pathlib import Path

import app
from tools.catalog_json_shadow_compare import compare_json_shadow


class CatalogJsonShadowCompareTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original_user_data_dir = app._user_data_dir
        self.original_repositories = dict(app._catalog_repository_cache)
        app._user_data_dir = self.tmp.name
        app._catalog_repository_cache.clear()
        self.store = app.AppMetadataStore(Path(self.tmp.name))
        self.path = 'E:/Movies/Legacy Shadow.2024.mkv'
        self.store.apply_tmdb_match(self.path, {
            'tmdb_id': '42',
            'imdb_id': 'tt0000042',
            'title': 'Legacy Shadow',
            'year': '2024',
            'plot': 'Persisted plot.',
            'genres': ['Drama'],
        })
        self.store.update_file_record(self.path, {'filename': 'Legacy Shadow.2024.mkv', 'resolution': '1080p'})
        self.store.save_plex_metadata(self.path, {'plex_title': 'Legacy Shadow', 'plex_year': '2024', 'plex_summary': 'Plex summary.'})
        self._write_literal_json_snapshot()

    def tearDown(self):
        app._catalog_repository_cache.clear()
        app._catalog_repository_cache.update(self.original_repositories)
        app._user_data_dir = self.original_user_data_dir
        self.tmp.cleanup()

    def _write_literal_json_snapshot(self):
        documents = {
            'files.json': ('app_metadata/files.json', {'files': {}}),
            'tmdb_metadata.json': ('app_metadata/tmdb_metadata.json', {'movies': {}}),
            'plex_metadata.json': ('app_metadata/plex_metadata.json', {'files': {}}),
            'manual_matches.json': ('app_metadata/manual_matches.json', {'matches': {}}),
            'poster_overrides.json': ('app_metadata/poster_overrides.json', {'overrides': []}),
            'metadata_overrides.json': ('app_metadata/metadata_overrides.json', {'overrides': []}),
        }
        base = Path(self.tmp.name) / 'app_metadata'
        base.mkdir(parents=True, exist_ok=True)
        for filename, (document, fallback) in documents.items():
            payload = self.store.catalog.read_document(document, fallback)
            (base / filename).write_text(json.dumps(payload), encoding='utf-8')

    def test_literal_json_and_sql_canonical_records_match_without_provider_calls(self):
        report = compare_json_shadow(self.tmp.name)

        self.assertTrue(report['passed'])
        self.assertEqual(report['checked_records'], 1)
        self.assertEqual(report['provider_calls'], 0)
        self.assertEqual(report['post_snapshot_document_changes'], [])

    def test_literal_json_difference_is_reported_without_mutating_sql(self):
        files_path = Path(self.tmp.name) / 'app_metadata' / 'files.json'
        payload = json.loads(files_path.read_text(encoding='utf-8'))
        record = next(iter(payload['files'].values()))
        record['identity_title'] = 'Wrong legacy title'
        files_path.write_text(json.dumps(payload), encoding='utf-8')

        report = compare_json_shadow(self.tmp.name)
        sql_record = self.store.catalog.get_record('app_metadata/files.json', app._norm(self.path), {})

        self.assertFalse(report['passed'])
        self.assertEqual(len(report['violations']['canonical']), 1)
        self.assertEqual(len(report['violations']['document_changed']), 1)
        self.assertEqual(sql_record['identity_title'], 'Legacy Shadow')

    def test_sql_record_created_after_the_frozen_json_snapshot_is_reported_but_not_a_parity_failure(self):
        new_path = 'E:/Movies/Added After Snapshot.2025.mkv'
        self.store.apply_tmdb_match(new_path, {
            'tmdb_id': '43',
            'title': 'Added After Snapshot',
            'year': '2025',
        })
        self.store.update_file_record(new_path, {'filename': 'Added After Snapshot.2025.mkv'})

        report = compare_json_shadow(self.tmp.name)

        self.assertTrue(report['passed'])
        self.assertEqual(len(report['post_snapshot_sql_only']), 1)
        self.assertEqual(len(report['post_snapshot_document_changes']), 3)
        self.assertEqual(report['record_counts']['differences'], {})

    def test_sql_record_older_than_the_frozen_json_snapshot_remains_a_failure(self):
        new_path = 'E:/Movies/Unexpected SQL Only.2025.mkv'
        self.store.apply_tmdb_match(new_path, {
            'tmdb_id': '44',
            'title': 'Unexpected SQL Only',
            'year': '2025',
        })
        self.store.update_file_record(new_path, {'filename': 'Unexpected SQL Only.2025.mkv'})
        files_path = Path(self.tmp.name) / 'app_metadata' / 'files.json'
        future = time.time() + 60
        os.utime(files_path, (future, future))

        report = compare_json_shadow(self.tmp.name)

        self.assertFalse(report['passed'])
        self.assertEqual(len(report['violations']['sql_only']), 1)
        self.assertEqual(len(report['violations']['document_sql_only']), 3)


if __name__ == '__main__':
    unittest.main()
