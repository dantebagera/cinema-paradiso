"""Disposable, owner-level regressions for bounded Movie publication work."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.catalog_repository import CatalogRepository
from services.library_ingestion import LibraryIngestionCoordinator
from tests.test_library_ingestion_queue import _dependencies
from dataclasses import replace
from unittest.mock import Mock
import threading


class RetryRepositoryTest(unittest.TestCase):
    def _episode_fixture(self):
        path = Path(self.key)
        path.write_bytes(b'fixture')
        clock = [1000.0]
        store = Mock()
        store.catalog = self.repository
        store._key.side_effect = lambda value: os.path.normcase(str(value))
        store.snapshot_for_paths.side_effect = lambda paths: {'files': {self.key: self.repository.get_record('app_metadata/files.json', self.key)}, 'manual_matches': {}, 'tmdb_movies': {}, 'plex_files': {}, 'poster_overrides': [], 'metadata_overrides': []}
        store.update_file_record.side_effect = lambda value, patch: self.repository.upsert_record('app_metadata/files.json', store._key(value), {**self.repository.get_record('app_metadata/files.json', store._key(value)), **patch})
        deps = replace(_dependencies(self.root), store=lambda: store, retry_repository=lambda: self.repository,
                       wall_time=lambda: clock[0], metadata_file_facts=lambda p, probe=False: {'path': str(p), 'size': path.stat().st_size, 'modified_time': path.stat().st_mtime})
        item = {'type': 'path', 'value': str(path), 'reason': 'qbittorrent', 'correlation_id': 'synthetic', 'require_publication': True}
        return deps, clock, item

    def test_asset_budget_survives_each_restart_and_own_failure_writes(self):
        deps, clock, item = self._episode_fixture()
        calls = []
        def fail(paths):
            ledger = self._read_ledger()
            self.assertEqual(ledger['attempts']['assets'], len(calls) % 4 + 1)
            self.assertEqual(ledger['state'], 'running')
            calls.append(paths)
            raise RuntimeError('temporary poster failure')
        deps = replace(deps, prepare_final_card_assets=fail)
        for _ in range(6):
            coordinator = LibraryIngestionCoordinator(deps)
            coordinator.reconcile_paths_now = lambda paths, **kwargs: {'checked': 1, '_matched_paths': list(paths)}
            coordinator._run_path_episode(item)
            clock[0] += 40
        self.assertEqual(len(calls), 4)
        self.assertEqual(self._read_ledger()['state'], 'blocked')
        self.assertEqual(self._read_ledger()['attempts']['assets'], 4)
        self.repository.upsert_record('app_metadata/files.json', self.key, {**self.repository.get_record('app_metadata/files.json', self.key), 'observed_at': 9999, 'poster_error': 'changed error'})
        coordinator._run_path_episode(item)
        self.assertEqual(len(calls), 4)
        coordinator._rearm_path(item['value'])
        coordinator._run_path_episode(item)
        self.assertEqual(len(calls), 5)

    def _read_ledger(self):
        return self.repository.get_record('app_metadata/files.json', self.key).get('_ingestion_retry', {})

    def test_crash_after_last_reservation_does_not_grant_fifth_asset_attempt(self):
        deps, clock, item = self._episode_fixture()
        coordinator = LibraryIngestionCoordinator(deps)
        coordinator.reconcile_paths_now = lambda paths, **kwargs: {'checked': 1, '_matched_paths': list(paths)}
        def crash(paths):
            raise KeyboardInterrupt('simulated process exit')
        deps = replace(deps, prepare_final_card_assets=crash)
        for _ in range(4):
            coordinator = LibraryIngestionCoordinator(deps)
            coordinator.reconcile_paths_now = lambda paths, **kwargs: {'checked': 1, '_matched_paths': list(paths)}
            with self.assertRaises(KeyboardInterrupt):
                coordinator._run_path_episode(item)
            recovered = LibraryIngestionCoordinator(deps)
            recovered._run_path_episode(item)
            clock[0] += 40
        never = Mock()
        recovered = LibraryIngestionCoordinator(replace(deps, prepare_final_card_assets=never))
        recovered._run_path_episode(item)
        never.assert_not_called()
        self.assertEqual(self._read_ledger()['state'], 'blocked')
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT'])
        self.root = Path(self.workspace.name)
        self.repository = CatalogRepository(self.root / 'data', self.root / 'catalog.sqlite')
        self.repository.activate_from_json()
        self.key = os.path.normcase(str(self.root / 'Example.mkv'))
        self.repository.upsert_record('app_metadata/files.json', self.key, {'path': self.key, 'size': 7})

    def tearDown(self):
        self.repository.close(flush=False)
        self.workspace.cleanup()

    def test_crash_after_own_identity_write_keeps_reserved_provider_attempt(self):
        deps, clock, item = self._episode_fixture()
        coordinator = LibraryIngestionCoordinator(deps)
        source = {'tmdb_id': '745678', 'paths': [self.key]}
        item['source_identity'] = source
        state = {'version': 1, 'revision': 0, 'state': 'waiting', 'stage': 'provider', 'attempts': {}, 'first_observed_at': clock[0], 'source_identity': source, 'require_publication': True, 'evidence_signature': coordinator._episode_signature(self.key, source)}
        coordinator._write_episode(self.key, state)
        self.assertTrue(coordinator._reserve(self.key, state, 'provider'))
        row = self.repository.get_record('app_metadata/files.json', self.key)
        self.repository.upsert_record('app_metadata/files.json', self.key, {**row, 'tmdb_id': '745678', 'identity_status': 'accepted', 'identity_source': 'download_submission'})
        restarted = LibraryIngestionCoordinator(deps)
        restarted._run_path_episode(item)
        after = self._read_ledger()
        self.assertEqual(after['attempts']['provider'], 1)
        self.assertEqual(after['first_observed_at'], 1000)
        self.assertEqual(after['state'], 'waiting')
        self.assertEqual(after['evidence_signature'], restarted._episode_signature(self.key, source))

    def test_bounded_rows_are_independent_and_unknown_is_empty(self):
        with patch.object(self.repository, 'read_document', side_effect=AssertionError('whole document')):
            rows = self.repository.get_records('app_metadata/files.json', [self.key, 'missing'])
        self.assertEqual(set(rows), {self.key})
        rows[self.key]['size'] = 99
        self.assertEqual(self.repository.get_record('app_metadata/files.json', self.key)['size'], 7)

    def test_live_provider_reservation_is_not_treated_as_crashed_by_another_caller(self):
        deps, clock, item = self._episode_fixture()
        entered, release = threading.Event(), threading.Event()
        def resolve(source):
            entered.set()
            self.assertTrue(release.wait(2))
            return {'state': 'deferred', 'paths': []}
        coordinator = LibraryIngestionCoordinator(replace(deps, resolve_source_identity=resolve))
        coordinator._ensure_dispatcher_locked = lambda: None
        coordinator.reconcile_paths_now = lambda paths, **kwargs: {'checked': 1, 'review': 1}
        item['source_identity'] = {'tmdb_id': '767890', 'paths': [self.key]}
        worker = threading.Thread(target=lambda: coordinator._run_path_episode(item))
        worker.start()
        self.assertTrue(entered.wait(2))
        before = self._read_ledger()
        try:
            result, due = coordinator._run_path_episode(dict(item))
            after = self._read_ledger()
            self.assertEqual(after, before)
            self.assertEqual(result.get('pending'), 1)
        finally:
            release.set()
            worker.join(2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(self._read_ledger()['attempts']['provider'], 1)
        self.assertNotEqual(self._read_ledger().get('last_error'), 'interrupted_attempt')

    def test_persisted_deferred_handoff_readmits_unrecorded_sibling_after_restart(self):
        deps, clock, item = self._episode_fixture()
        other = str(self.root / 'Sibling.mkv')
        source = {'paths': [self.key, other]}
        coordinator = LibraryIngestionCoordinator(deps)
        state = {'version': 1, 'revision': 0, 'state': 'complete', 'stage': 'assets', 'attempts': {'provider': 1}, 'first_observed_at': clock[0], 'source_identity': source, 'require_publication': True, 'handoff': {'state': 'deferred', 'paths': []}, 'evidence_signature': coordinator._episode_signature(self.key, source)}
        coordinator._write_episode(self.key, state)
        restarted = LibraryIngestionCoordinator(deps)
        restarted._ensure_dispatcher_locked = lambda: None
        restarted._run_path_episode({**item, 'source_identity': source})
        self.assertIn('path:' + restarted.normalize_path(other), restarted._pending)

    def test_blocked_rows_do_not_consume_restart_recovery_capacity(self):
        first = self.key
        state = {'version': 1, 'revision': 1, 'state': 'blocked'}
        self.repository.patch_file_operational(first, expected_revision=0, retry_state=state)
        waiting = self.key + '.waiting'
        self.repository.upsert_record('app_metadata/files.json', waiting, {'path': waiting})
        self.repository.patch_file_operational(waiting, expected_revision=0, retry_state={**state, 'state': 'waiting'})
        self.assertEqual([row['path'] for row in self.repository.retry_records(1)], [waiting])

    def test_revision_conflict_rereads_and_schedules_one_bounded_retry(self):
        deps, clock, item = self._episode_fixture()
        coordinator = LibraryIngestionCoordinator(deps)
        with patch.object(self.repository, 'patch_file_operational', return_value=False):
            result, due = coordinator._run_path_episode(item)
            self.assertEqual(result['pending'], 1)
            self.assertIsNotNone(due)
            result, due = coordinator._run_path_episode(item)
            self.assertEqual(result['failed'], 1)
            self.assertIsNone(due)
        self.assertEqual(coordinator._last_error, 'retry_revision_conflict')
        self.assertEqual(len(coordinator._dirty_roots), 1)

    def test_inventory_patch_preserves_sibling_fields_and_generation(self):
        self.repository.replace_operational_document('app_metadata/library_inventory.json', {'files': {'other': {'size': 9}}, 'cutoff': 123})
        generation = self.repository.generation()
        self.repository.patch_inventory({self.key: {'size': 7}}, [])
        self.assertEqual(self.repository.inventory_entries([self.key, 'missing']), {self.key: {'size': 7}})
        doc = self.repository.read_document('app_metadata/library_inventory.json', {})
        self.assertEqual(doc['cutoff'], 123)
        self.assertEqual(doc['files']['other'], {'size': 9})
        self.assertEqual(self.repository.generation(), generation)
        unicode_key = str(self.root / 'Léon - العربية.mkv')
        self.repository.patch_inventory({unicode_key: {'size': 4}}, [])
        self.assertEqual(self.repository.inventory_entries([unicode_key]), {unicode_key: {'size': 4}})
        self.repository.patch_inventory({}, [unicode_key])
        self.assertEqual(self.repository.inventory_entries([unicode_key]), {})

    def test_conditional_ledger_patch_is_operational_and_survives_stale_writers(self):
        stale = self.repository.get_record('app_metadata/files.json', self.key)
        generation = self.repository.generation()
        ledger = {'version': 1, 'revision': 1, 'state': 'running', 'attempts': {'assets': 1}}
        with patch.object(self.repository.store.canonical, 'sync_changes', side_effect=AssertionError('canonical write')):
            self.assertTrue(self.repository.patch_file_operational(self.key, expected_revision=0, retry_state=ledger))
        self.assertEqual(self.repository.generation(), generation)
        self.assertFalse(self.repository.patch_file_operational(self.key, expected_revision=0, retry_state=ledger))
        self.repository.upsert_record('app_metadata/files.json', self.key, {**stale, 'size': 8})
        self.assertEqual(self.repository.get_record('app_metadata/files.json', self.key)['_ingestion_retry'], ledger)
        self.repository.replace_document('app_metadata/files.json', {'files': {self.key: stale}})
        self.assertEqual(self.repository.get_record('app_metadata/files.json', self.key)['_ingestion_retry'], ledger)
        moved = self.key + '.moved'
        self.repository.migrate_path_records(self.key, moved, moved, {'_ingestion_retry': {'revision': 0}})
        self.assertEqual(self.repository.get_record('app_metadata/files.json', moved)['_ingestion_retry'], ledger)
        self.assertFalse(self.repository.patch_file_operational('missing', expected_revision=0, retry_state=ledger))

    def test_publication_status_cannot_publish_or_accept_legacy_visibility(self):
        before = self.repository.generation()
        status = self.repository.publication_status([self.key])[self.key]
        self.assertTrue(status['legacy_visible'])
        self.assertFalse(status['eligible_to_publish'])
        self.assertFalse(status['publication_committed'])
        self.assertIn('facts', status['required_stages'])
        self.assertEqual(self.repository.final_card_publication([self.key]), [])
        self.assertEqual(before, self.repository.generation())

    def test_provider_failure_reserves_before_side_effect_and_poll_restart_cannot_reset(self):
        path = Path(self.key)
        path.write_bytes(b'fixture')
        store = Mock()
        store.catalog = self.repository
        store._key.side_effect = lambda value: os.path.normcase(str(value))
        store.snapshot_for_paths.side_effect = lambda paths: {'files': {self.key: self.repository.get_record('app_metadata/files.json', self.key)}, 'manual_matches': {}, 'tmdb_movies': {}, 'plex_files': {}, 'poster_overrides': [], 'metadata_overrides': []}
        store.update_file_record.side_effect = lambda value, patch: self.repository.upsert_record('app_metadata/files.json', store._key(value), {**self.repository.get_record('app_metadata/files.json', store._key(value)), **patch})
        deps = _dependencies(self.root)
        calls = []
        def resolve(source):
            state = self.repository.get_record('app_metadata/files.json', self.key)['_ingestion_retry']
            self.assertEqual(state['state'], 'running')
            self.assertEqual(state['attempts']['provider'], len(calls) + 1)
            calls.append(source)
            raise ValueError('permanent invalid provider identity')
        deps = replace(deps, store=lambda: store, retry_repository=lambda: self.repository, resolve_source_identity=resolve,
                       metadata_file_facts=lambda p, probe=False: {'path': str(p), 'size': 7, 'modified_time': path.stat().st_mtime})
        coordinator = LibraryIngestionCoordinator(deps)
        coordinator._ensure_dispatcher_locked = lambda: None
        source = {'tmdb_id': '314159', 'paths': [str(path)]}
        coordinator.reconcile_paths([str(path)], 'qbittorrent', require_publication=True, source_identity=source)
        item = next(iter(coordinator._pending.values()))
        coordinator._run_path_episode(item)
        ledger = self.repository.get_record('app_metadata/files.json', self.key)['_ingestion_retry']
        self.assertEqual(ledger['state'], 'blocked')
        self.assertTrue(ledger['require_publication'])
        for _ in range(5):
            coordinator.reconcile_paths([str(path)], 'qbittorrent', require_publication=True, source_identity=source)
            coordinator._run_path_episode(item)
        restarted = LibraryIngestionCoordinator(deps)
        restarted._run_path_episode(item)
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.repository.get_record('app_metadata/files.json', self.key)['_ingestion_retry']['attempts'], {'provider': 1})
