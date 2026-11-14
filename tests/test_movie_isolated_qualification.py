"""Additional bounded qualification against disposable SQLite/processes only."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from services.catalog_repository import CatalogRepository


class MovieIsolatedQualificationTest(unittest.TestCase):
    def setUp(self):
        declared = Path(os.environ['CP_TEST_ROOT']).resolve()
        if os.environ.get('CP_TEST_MODE') != '1' or Path(tempfile.gettempdir()).resolve() not in declared.parents:
            raise RuntimeError('Temporary test root required')
        self.root = Path(tempfile.mkdtemp(prefix='qualification-', dir=declared))

    def worker(self, root, mode, *options, crash=False):
        command = [sys.executable, '-m', 'tests.movie_retry_restart_worker', mode, str(root), *options]
        if not crash:
            result = subprocess.run(command, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        marker = root / 'checkpoint.json'
        deadline = time.monotonic() + 15
        try:
            checkpoint = None
            while process.poll() is None and time.monotonic() < deadline:
                try:
                    checkpoint = json.loads(marker.read_text())
                    break
                except (FileNotFoundError, json.JSONDecodeError):
                    time.sleep(.02)
            self.assertIsNotNone(checkpoint, 'Worker never reached boundary')
            # Kill the actual worker, which can be a child of Windows' venv launcher.
            os.kill(checkpoint['pid'], signal.SIGTERM)
            process.communicate(timeout=5)
            self.assertNotEqual(process.returncode, 0)
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)

    def test_a_real_termination_keeps_durable_stage_reservations_and_handoff(self):
        boundaries = ['before-reservation', 'after-reservation', 'during-facts',
                      'provider-after-own-write', 'last-asset-attempt', 'persisted-handoff-before-sibling']
        evidence = []
        for boundary in boundaries:
            with self.subTest(boundary=boundary):
                root = self.root / boundary
                root.mkdir()
                self.worker(root, 'crash', '--boundary', boundary, crash=True)
                repository = CatalogRepository(root / 'data', root / 'catalog.sqlite')
                key = os.path.normcase(str(root / 'Example.mkv'))
                before = repository.get_record('app_metadata/files.json', key)['_ingestion_retry']
                repository.close(flush=False)
                self.worker(root, 'resume')
                report = json.loads((root / 'resumed.json').read_text())
                after = report['ledger']
                self.assertEqual(after['first_observed_at'], 1000.0)
                self.assertTrue(after['require_publication'])
                if boundary == 'before-reservation':
                    self.assertEqual(before['attempts'], {})
                    self.assertEqual(after['attempts']['facts'], 1)
                elif boundary == 'last-asset-attempt':
                    self.assertEqual(before['attempts']['assets'], 4)
                    self.assertEqual(after['attempts']['assets'], 4)
                    self.assertEqual(after['state'], 'blocked')
                elif boundary == 'persisted-handoff-before-sibling':
                    self.assertEqual(after['attempts']['provider'], 1)
                    self.assertEqual(after['source_identity'], before['source_identity'])
                    self.assertIn('Sibling.mkv', [Path(work['value']).name for work in report['pending']])
                else:
                    stage = 'provider' if boundary.startswith('provider') else 'facts'
                    self.assertEqual(before['attempts'][stage], 1)
                    self.assertEqual(after['attempts'][stage], 1)
                    self.assertEqual(after['state'], 'waiting')
                    self.assertEqual(after['next_due_at'], 1001.0)
                    self.assertEqual(after['last_error'], 'interrupted_attempt')
                    if stage == 'provider':
                        self.assertEqual(report['record']['tmdb_id'], '745678')
                self.assertNotEqual(report['record'].get('movie_view_publication'), 'ready')
                evidence.append({'boundary': boundary, 'before': before, 'after': after})
        (self.root / 'crash-evidence.json').write_text(json.dumps(evidence, indent=2))

    def test_b_simultaneous_inventory_writers_preserve_each_other_and_generation(self):
        database = self.root / 'inventory.sqlite'
        first = CatalogRepository(self.root / 'data', database)
        first.activate_from_json()
        first.replace_operational_document('app_metadata/library_inventory.json', {
            'files': {'keep': {'size': 9}, 'remove-in-scope': {'size': 1}}, 'cutoff': 123})
        second = CatalogRepository(self.root / 'data', database)
        generation = first.generation()
        gate = threading.Barrier(2)
        def writer(repository, name, removed):
            gate.wait(timeout=2)
            return repository.patch_inventory({name: {'size': 7}}, removed)
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = [pool.submit(writer, first, 'Léon - العربية', ['remove-in-scope']),
                           pool.submit(writer, second, 'other-owner', [])]
                self.assertEqual([future.result(timeout=5) for future in results], [True, True])
            result = first.read_document('app_metadata/library_inventory.json', {})
            self.assertEqual(result, {'files': {'keep': {'size': 9}, 'Léon - العربية': {'size': 7}, 'other-owner': {'size': 7}}, 'cutoff': 123})
            self.assertEqual(first.generation(), generation)
            with patch.object(first, 'schedule_export') as export:
                self.assertFalse(first.patch_inventory({'other-owner': {'size': 7}}, []))
                export.assert_not_called()
        finally:
            first.close(flush=False)
            second.close(flush=False)

    def test_z_equal_due_retry_admission_order_survives_real_process_restart(self):
        self.worker(self.root, 'order-seed', crash=True)
        self.worker(self.root, 'order-recover', '--clock', '1003')
        actual = json.loads((self.root / 'order.json').read_text())
        self.assertEqual(actual, ['A', 'B', 'C'], 'Restart must retain retry admission order, not original file discovery order')

    def test_c_admission_sequence_is_atomic_operational_and_survives_json_restore(self):
        repository = CatalogRepository(self.root / 'data', self.root / 'catalog.sqlite')
        repository.activate_from_json()
        second = CatalogRepository(self.root / 'data', self.root / 'catalog.sqlite')
        generation = repository.generation()
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                orders = [pool.submit(owner.next_retry_admission_order) for owner in [repository, second] * 5]
                self.assertEqual(sorted(f.result(timeout=5) for f in orders), list(range(1, 11)))
            self.assertEqual(repository.generation(), generation)
            repository.store.import_documents({'app_metadata/files.json': {'files': {'restored': {
                'path': 'restored', '_ingestion_retry': {'revision': 1, 'admission_order': 50}}}}}, {})
            self.assertEqual(repository.next_retry_admission_order(), 51)
        finally:
            repository.close(flush=False)
            second.close(flush=False)

    def test_e_equal_durable_deadlines_dispatch_fifo_despite_conversion_jitter(self):
        from dataclasses import replace
        from services.library_ingestion import LibraryIngestionCoordinator
        from tests.test_library_ingestion_queue import _dependencies
        coordinator = LibraryIngestionCoordinator(replace(_dependencies(self.root),
            monotonic=lambda: 2003.0, wall_time=lambda: 1003.0))
        coordinator._ensure_dispatcher_locked = lambda: None
        paths = [self.root / 'A.mkv', self.root / 'B.mkv']
        coordinator.reconcile_paths(paths, 'observer:created')
        for index, item in enumerate(coordinator._pending.values()):
            item.update(retry_due_at=1002.0, not_before=2001.999 - index * .001)
        calls = []
        coordinator._run_path_episode = lambda item: (calls.append(Path(item['value']).stem) or {}, None)
        coordinator._accepting = False
        coordinator._dispatch()
        self.assertEqual(calls, ['A', 'B'])

    def test_d_durable_path_order_does_not_reorder_mixed_in_memory_work(self):
        from dataclasses import replace
        from services.library_ingestion import LibraryIngestionCoordinator
        from tests.test_library_ingestion_queue import _dependencies
        repository = CatalogRepository(self.root / 'data', self.root / 'catalog.sqlite')
        repository.activate_from_json()
        with repository.store.transaction() as connection:
            connection.execute("INSERT OR REPLACE INTO catalog_meta VALUES('retry_admission_order','100')")
        path = self.root / 'First.mkv'
        path.write_bytes(b'fixture')
        directory = self.root / 'Later'
        directory.mkdir()
        coordinator = LibraryIngestionCoordinator(replace(_dependencies(self.root),
            retry_repository=lambda: repository, monotonic=lambda: 1000.0))
        coordinator._ensure_dispatcher_locked = lambda: None
        try:
            coordinator.reconcile_paths([str(path)], 'observer:created')
            coordinator.reconcile_directories([str(directory)], 'observer:created')
            ordered = sorted(coordinator._pending.values(), key=lambda work: (work['not_before'], work['order']))
            self.assertEqual([work['type'] for work in ordered], ['path', 'directory'])
            self.assertEqual(ordered[0]['admission_order'], 101)
        finally:
            repository.close(flush=False)
