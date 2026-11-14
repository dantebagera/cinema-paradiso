import os
import tempfile
import unittest
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
import services.catalog_store as module
from services.catalog_store import CatalogStore
from tests import test_catalog_store as fixtures
from services.catalog_repository import CatalogRepository


class LibrarySearchContractTest(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT'])
        self.store = CatalogStore(Path(self.workspace.name) / 'catalog.sqlite')
        self.store.initialize()
        documents = fixtures.CatalogStoreTest()._paging_documents(125)
        self.store.import_documents(documents, {})

    def tearDown(self):
        self.workspace.cleanup()

    def test_page_matches_frozen_two_statement_selection_and_total(self):
        for text in ('Movie', 'test', '1981', '!!!', 'nonexistent', ''):
            for sort in ('title', 'added', 'rating', 'year-desc', 'size', 'filename'):
                filters = {'query': text, 'sort': sort}
                cte = self.store._library_effective_cte()
                where, params = self.store._library_filter_sql(filters)
                rank, rank_params = self.store._library_search_rank_sql(text)
                connection = self.store.connect()
                try:
                    expected = [row[0] for row in connection.execute(f"{cte} SELECT e.path_key FROM effective e{where} ORDER BY {rank + ',' if rank else ''} {self.store._library_sort_sql(sort)}", [*params, *rank_params])]
                finally:
                    connection.close()
                result = self.store.library_page(filters, page=999, page_size=40)
                page = max(1, (len(expected) + 39) // 40)
                self.assertEqual(result['total'], len(expected), (text, sort))
                self.assertEqual(result['page'], page)
                self.assertEqual([row['path_key'] for row in result['candidates']], expected[(page - 1)*40:page*40])

    def test_count_and_page_share_one_materialized_match(self):
        statements = []
        connect = self.store.connect
        def traced():
            connection = connect(); connection.set_trace_callback(statements.append); return connection
        with patch.object(self.store, 'connect', traced):
            self.store.library_page({'query': 'Movie'})
        matching = [sql for sql in statements if 'matched AS MATERIALIZED' in sql]
        self.assertEqual(len(matching), 1)
        self.assertRegex(matching[0], r'COUNT\(\*\).*FROM matched')

    def test_normalization_memo_is_bounded_and_pure(self):
        cache = module.SearchNormalizationMemo(max_entries=2, max_bytes=4096, max_input_bytes=1024)
        compute = module._uncached_catalog_search_key
        self.assertEqual(cache.get(' LÉON  - 1994 ', compute), 'leon1994')
        self.assertEqual(cache.get('العربية', compute), compute('العربية'))
        cache.get('third', compute)
        self.assertLessEqual(cache.info()['entries'], 2)
        self.assertLessEqual(cache.info()['bytes'], 4096)
        before = cache.info()['entries']
        cache.get('x' * 4096, compute)
        self.assertEqual(cache.info()['entries'], before)
        self.assertEqual(cache.get(' LÉON  - 1994 ', compute), compute(' LÉON  - 1994 '))

    def test_read_context_remains_coherent_while_writer_finishes(self):
        repository = CatalogRepository(Path(self.workspace.name) / 'data', self.store.database_path)
        try:
            with repository.library_read_context() as context:
                old = repository.library_page({'query': 'Renamed'}, read_context=context)
                generation = context['generation']
                key = context['connection'].execute('SELECT path_key FROM media_files ORDER BY path_key LIMIT 1').fetchone()[0]
                record = repository.get_record('app_metadata/files.json', key)
                with ThreadPoolExecutor(max_workers=1) as worker:
                    changed = worker.submit(repository.upsert_record, 'app_metadata/files.json', key, {**record, 'filename': 'Renamed.mkv'})
                    changed.result(timeout=2)
                during = repository.library_page({'query': 'Renamed'}, read_context=context)
                self.assertEqual(old['total'], 0)
                self.assertEqual(during['total'], 0)
                self.assertEqual(during['catalog_generation'], generation)
            fresh = repository.library_page({'query': 'Renamed'})
            self.assertEqual(fresh['total'], 1)
            self.assertGreater(fresh['catalog_generation'], generation)
        finally:
            repository.close(flush=False)

    def test_normalization_miss_does_not_lock_out_unrelated_work_or_cache_errors(self):
        cache = module.SearchNormalizationMemo()
        entered, release = threading.Event(), threading.Event()
        def slow(value):
            entered.set()
            self.assertTrue(release.wait(2))
            return value
        with ThreadPoolExecutor(max_workers=2) as workers:
            first = workers.submit(cache.get, 'slow', slow)
            self.assertTrue(entered.wait(2))
            try:
                self.assertEqual(workers.submit(cache.get, 'other', str.upper).result(timeout=1), 'OTHER')
            finally:
                release.set()
            self.assertEqual(first.result(), 'slow')
        def broken(value):
            raise ValueError('synthetic normalization failure')
        with self.assertRaises(ValueError):
            cache.get('failed', broken)
        self.assertEqual(cache.get('failed', str.upper), 'FAILED')
