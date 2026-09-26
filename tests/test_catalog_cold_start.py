import concurrent.futures
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import app


class CatalogColdStartTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)

    def tearDown(self):
        key = str(self.root.resolve())
        repository = app._catalog_repository_cache.pop(key, None)
        if repository:
            repository.close(flush=False)
        lease = app._catalog_writer_lease_cache.pop(key, None)
        if lease:
            lease.close()
        self.directory.cleanup()

    def test_simultaneous_first_requests_share_one_usable_catalog(self):
        barrier = threading.Barrier(8)

        def request(_):
            barrier.wait(timeout=10)
            repository = app._catalog_repository_for(self.root)
            return repository, repository.generation('media')

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(request, range(8)))
        self.assertEqual(len({id(row[0]) for row in results}), 1)
        self.assertEqual(len({row[1] for row in results}), 1)

    def test_failed_initialization_releases_lease_and_can_retry(self):
        with patch.object(app.CatalogRepository, 'activate_from_json', side_effect=RuntimeError('failed migration')):
            with self.assertRaisesRegex(RuntimeError, 'failed migration'):
                app._catalog_repository_for(self.root)
        self.assertNotIn(str(self.root.resolve()), app._catalog_repository_cache)
        repository = app._catalog_repository_for(self.root)
        self.assertIsInstance(repository.generation('media'), int)
