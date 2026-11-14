"""Remaining finite Movie qualification: real crash boundaries and read contracts."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from services.catalog_store import CatalogStore
from services.catalog_repository import CatalogRepository
from tests import test_catalog_store as paging_fixtures


class RemainingMovieQualificationTest(unittest.TestCase):
    def setUp(self):
        root = Path(os.environ['CP_TEST_ROOT']).resolve()
        if os.environ.get('CP_TEST_MODE') != '1' or Path(tempfile.gettempdir()).resolve() not in root.parents:
            raise RuntimeError('Isolated root required')
        self.root = Path(tempfile.mkdtemp(prefix='remaining-', dir=root))

    def test_a_publication_notification_and_ack_survive_real_process_termination(self):
        evidence = []
        for boundary in ['after-commit-before-event', 'after-event-before-ack', 'after-ack']:
            with self.subTest(boundary=boundary):
                root = self.root / boundary
                root.mkdir()
                command = [sys.executable, '-m', 'tests.movie_qualification_backend', 'crash', str(root), '--boundary', boundary]
                with (root / 'worker.log').open('wb') as log:
                    worker = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
                    checkpoint = None
                    try:
                        deadline = time.monotonic() + 20
                        while worker.poll() is None and time.monotonic() < deadline:
                            try:
                                checkpoint = json.loads((root / 'checkpoint.json').read_text())
                                break
                            except (FileNotFoundError, json.JSONDecodeError):
                                time.sleep(.02)
                        self.assertIsNotNone(checkpoint, (root / 'worker.log').read_text(errors='replace'))
                        os.kill(checkpoint['pid'], signal.SIGTERM)
                        worker.wait(timeout=5)
                    finally:
                        if worker.poll() is None:
                            worker.kill()
                            worker.wait(timeout=5)
                before_job = json.loads((root / 'job.json').read_text())
                published = (root / 'publication.jsonl').read_text().splitlines()
                self.assertEqual(len(published), 1)
                result = subprocess.run([sys.executable, '-m', 'tests.movie_qualification_backend', 'resume', str(root)],
                    capture_output=True, text=True, timeout=20)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                report = json.loads((root / 'backend-result.json').read_text())
                self.assertTrue(report['publication']['publication_committed'])
                self.assertFalse(report['job']['library_scan_pending'])
                self.assertEqual(report['library_api_status'], 200)
                self.assertEqual([card['canonical_metadata']['tmdb_id'] for card in report['library_api']['items']], ['810001'])
                self.assertEqual(report['followed_count_after_ownership'], 0)
                self.assertIn(report['reconnect_event']['type'], {'catalog-sync', 'catalog-ready'})
                self.assertEqual(report['reconnect_event']['generation'], report['generation'])
                self.assertEqual(report['poster_calls'], 1, 'Restart must reuse the already-ready poster')
                self.assertEqual(len((root / 'publication.jsonl').read_text().splitlines()), 1, 'No second publication mutation')
                if boundary != 'after-ack':
                    self.assertTrue(before_job['library_scan_pending'])
                    self.assertGreater(report['events'], 0, 'Already-ready monitor must recover the notification before ack')
                else:
                    self.assertFalse(before_job['library_scan_pending'])
                evidence.append({'boundary': boundary, 'before_job': before_job, 'recovered': report})
        (self.root / 'commit-event-ack-evidence.json').write_text(json.dumps(evidence, indent=2))

    def test_b_four_snapshot_branches_empty_selected_data_and_competing_overrides(self):
        evidence = []
        for selected, absent, token, fallback in [
                ('plex', '', 'plexneedle', False), ('tmdb', '', 'tmdbneedle', False),
                ('tmdb', 'tmdb', 'plexneedle', True), ('plex', 'plex', 'tmdbneedle', True)]:
            with self.subTest(selected=selected, absent=absent):
                documents = paging_fixtures.CatalogStoreTest()._paging_documents(1)
                key, record = next(iter(documents['app_metadata/files.json']['files'].items()))
                documents['app_metadata/tmdb_metadata.json']['movies']['1000']['plot'] = 'tmdbneedle'
                documents['app_metadata/plex_metadata.json']['files'][key] = {
                    'path': record['path'], 'tmdb_id': '1000', 'plex_title': 'Plex Source Title',
                    'plex_year': '1999', 'plex_summary': 'plexneedle', 'updated_at': 20}
                documents['app_metadata/metadata_overrides.json'] = {'overrides': [
                    {'id': 'older-path', 'identity_keys': ['path:' + record['path'].lower()], 'title': 'Older Override', 'year': '2001', 'updated_at': 10},
                    {'id': 'newer-global', 'identity_keys': ['tmdb:1000'], 'title': 'Newest Override', 'year': '2002', 'updated_at': 20}]}
                store = CatalogStore(self.root / f'{selected}-{absent or "present"}.sqlite')
                store.import_documents(documents, {})
                with store.transaction() as connection:
                    connection.execute('UPDATE canonical_movies SET selected_provider=?', (selected,))
                    if absent:
                        connection.execute('DELETE FROM provider_movie_snapshots WHERE provider=?', (absent,))
                page = store.library_page({'query': token, 'sort': 'title'})
                self.assertEqual(page['total'], 1)
                card = page['candidates'][0]['relational_canonical']
                self.assertEqual((card['title'], card['year'], card['plot']), ('Newest Override', '2002', token))
                self.assertEqual(card['fallback_active'], fallback)
                self.assertEqual(card['selected_provider_snapshot'], not fallback)
                self.assertEqual(store.library_selection_paths({'query': token}), [record['path']])
                self.assertEqual(store.library_page({'query': 'Newest Override'})['total'], 1)
                self.assertEqual(store.library_page({'query': 'Older Override'})['total'], 0)
                repository = CatalogRepository(self.root / 'data', store.database_path)
                try:
                    with store.library_read_context() as context:
                        before = store.library_page({'query': 'Newest Override'}, read_context=context)
                        with ThreadPoolExecutor(max_workers=1) as pool:
                            changed = pool.submit(repository.replace_document, 'app_metadata/metadata_overrides.json', {'overrides': [{
                                'id': 'concurrent-global', 'identity_keys': ['tmdb:1000'],
                                'title': 'Concurrent Override', 'year': '2003', 'updated_at': 30}]})
                            changed.result(timeout=2)
                        during = store.library_page({'query': 'Newest Override'}, read_context=context)
                        self.assertEqual(during['total'], 1)
                        self.assertEqual(during['catalog_generation'], before['catalog_generation'])
                        self.assertEqual(during['candidates'][0]['relational_canonical']['title'], 'Newest Override')
                    fresh = store.library_page({'query': 'Concurrent Override'})
                    self.assertEqual(fresh['total'], 1)
                    fresh_card = fresh['candidates'][0]['relational_canonical']
                    self.assertEqual((fresh_card['title'], fresh_card['year'], fresh_card['plot']), ('Concurrent Override', '2003', token))
                    self.assertEqual(store.library_page({'query': 'Newest Override'})['total'], 0)
                finally:
                    repository.close(flush=False)
                evidence.append({'selected_provider': selected, 'missing': absent, 'card': card, 'after_concurrent_override': fresh_card})
        # A present but empty selected snapshot must not silently switch provider.
        with store.transaction() as connection:
            connection.execute("UPDATE canonical_movies SET selected_provider='tmdb'")
            connection.execute("UPDATE provider_movie_snapshots SET plot='' WHERE provider='tmdb'")
        empty = store.library_page({'query': 'tmdbneedle'})
        self.assertEqual(empty['total'], 0)
        (self.root / 'snapshot-branches.json').write_text(json.dumps(evidence, indent=2))

    def test_c_named_file_reads_remain_bounded_among_four_thousand_movies(self):
        from tests.movie_qualification_backend import configure, seed_bulk
        prior = sorted(Path(os.environ['CP_TEST_ROOT']).glob('remaining-*/bounded-4000-reads.json'), key=lambda p: p.stat().st_mtime)
        prior_data = json.loads(prior[-1].read_text()) if prior else {}
        fixture_root = Path(prior_data.get('fixture_root', str(prior[-1].parent / 'bounded'))) if prior else self.root / 'bounded'
        fixture = configure(fixture_root)
        seed_bulk(fixture)
        app = fixture.app
        repository = fixture.store.catalog
        connection = repository.store.connect()
        count = connection.execute('SELECT COUNT(*) FROM media_files').fetchone()[0]
        connection.close()
        self.assertEqual(count, 4000)
        target = fixture.media / 'Search.Fixture.0000.mkv'
        stable = time.time() - 60
        os.utime(target, (stable, stable))
        fixture.store.apply_tmdb_match(str(target), fixture.store.get_tmdb_metadata('1000'))
        stats = {'returned_rows': 0, 'read_statements': 0, 'bounded_get_records': []}
        original_connect = repository.store.connect
        class Cursor:
            def __init__(self, cursor): self.cursor = cursor
            def __getattr__(self, name): return getattr(self.cursor, name)
            def fetchone(self):
                row = self.cursor.fetchone()
                stats['returned_rows'] += int(row is not None)
                return row
            def fetchall(self):
                rows = self.cursor.fetchall()
                stats['returned_rows'] += len(rows)
                return rows
            def __iter__(self):
                for row in self.cursor:
                    stats['returned_rows'] += 1
                    yield row
        class Connection:
            def __init__(self, connection): self.connection = connection
            def __getattr__(self, name): return getattr(self.connection, name)
            def execute(self, sql, parameters=()):
                if sql.lstrip().upper().startswith(('SELECT', 'WITH')): stats['read_statements'] += 1
                return Cursor(self.connection.execute(sql, parameters))
        original_records = repository.get_records
        def records(name, keys, **kwargs):
            keys = list(keys)
            result = original_records(name, keys, **kwargs)
            stats['bounded_get_records'].append({'document': name, 'keys': len(keys), 'rows': len(result)})
            self.assertLessEqual(len(keys), 2)
            self.assertLessEqual(len(result), 2)
            return result
        original_read = app.AppMetadataStore._read_json
        def read(owner, path, fallback):
            if Path(path).name in {'files.json','tmdb_metadata.json','plex_metadata.json','library_inventory.json'}:
                raise AssertionError('Whole core document requested')
            return original_read(owner, path, fallback)
        with patch.object(repository.store, 'connect', side_effect=lambda: Connection(original_connect())), \
                patch.object(repository, 'get_records', side_effect=records), \
                patch.object(app.AppMetadataStore, 'snapshot', side_effect=AssertionError('Whole snapshot')), \
                patch.object(app.AppMetadataStore, '_read_json', read), \
                patch('services.library_ingestion.os.walk', side_effect=AssertionError('Filesystem walk')):
            result = app._library_ingestion_coordinator().reconcile_paths_now([str(target)], require_publication=True)
        self.assertEqual(result['checked'], 1)
        self.assertEqual(result['matched'], 1)
        self.assertEqual(result['failed'], 0)
        self.assertTrue(repository.publication_status([str(target)])[fixture.store._key(target)]['publication_committed'])
        self.assertLess(stats['returned_rows'], 512)
        stats.update(catalogue_rows=count, named_paths=1, result=result,
                     fixture_root=str(fixture_root), publication_committed=True,
                     whole_core_documents=0, full_snapshots=0, filesystem_walks=0)
        (self.root / 'bounded-4000-reads.json').write_text(json.dumps(stats, indent=2))
