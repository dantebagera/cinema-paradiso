import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import app
from services.library_startup_catchup import LibraryStartupCatchup
from services.media_file_facts import MediaFileFacts


class LibraryIngestionPathsTest(unittest.TestCase):
    def test_file_replacement_during_provider_work_discards_obsolete_facts(self):
        movie = self.movies_a / 'Replaced.During.Lookup.2008.mkv'
        movie.write_bytes(b'old')
        os.utime(movie, (time.time() - 30, time.time() - 30))
        store = app.AppMetadataStore(self.data)
        store.save_authority_state({'active_provider': 'tmdb'})
        measured = self._probe(movie)
        def delayed(*args, **kwargs):
            movie.write_bytes(b'new replacement payload')
            return app._identity_resolution('accepted', {'tmdb_id': '778901', 'title': 'Obsolete Physical Facts', 'year': '2008'}, {'outcome': 'accepted'}, source='auto_tmdb')
        with patch('app.probe_media_file', return_value=measured), patch('app._resolve_tmdb_identity', side_effect=delayed):
            result = app._library_ingestion_coordinator().reconcile_paths_now([movie])
        record = store.catalog.get_record('app_metadata/files.json', store._key(movie))
        self.assertFalse(record.get('metadata_accepted'))
        self.assertNotEqual(record.get('movie_view_publication'), 'ready')
        self.assertEqual(result['pending'], 1)
        self.assertLessEqual(len(app._library_ingestion_coordinator()._pending), 1)

    def test_reused_probe_facts_cannot_restore_old_unaccepted_identity(self):
        movie = self.movies_a / 'Reusable.Facts.2007.mkv'
        movie.write_bytes(b'fixture')
        os.utime(movie, (time.time() - 30, time.time() - 30))
        store = app.AppMetadataStore(self.data)
        store.save_authority_state({'active_provider': 'tmdb'})
        with patch('app.probe_media_file', return_value=self._probe(movie)):
            facts = app._metadata_file_facts(str(movie))
        store.update_file_record(str(movie), {**facts, 'ingest_status': 'stable', 'identity_status': 'unmatched', 'metadata_status': 'pending', 'metadata_accepted': False, 'tmdb_id': '', 'enrichment_status': 'incomplete', 'movie_view_publication': 'pending'})
        metadata = {'tmdb_id': '756789', 'title': 'Reusable Facts', 'year': '2007', 'plot': 'Newly accepted metadata.', 'cast': [], 'directors': [], 'writers': [], 'keywords': [], 'certification': ''}
        resolution = app._identity_resolution('accepted', metadata, {'outcome': 'accepted'}, source='auto_tmdb')
        with patch('app._resolve_tmdb_identity', return_value=resolution), patch('app.probe_media_file') as probe:
            app._library_ingestion_coordinator().reconcile_paths_now([movie], require_publication=True)
        record = store.catalog.get_record('app_metadata/files.json', store._key(movie))
        self.assertTrue(record['metadata_accepted'])
        self.assertEqual(record['tmdb_id'], '756789')
        self.assertEqual(record['identity_status'], 'accepted')
        probe.assert_not_called()
        payload = app.app.test_client().get('/api/library?view=cards').get_json()
        self.assertEqual([item['canonical_metadata']['tmdb_id'] for item in payload['items']], ['756789'])
        self.assertEqual(payload['items'][0]['canonical_metadata']['enrichment_status'], 'complete')

    def test_job_hint_cannot_replace_manual_identity_during_final_card_work(self):
        movie = self.movies_a / 'Protected.Identity.2005.mkv'
        movie.write_bytes(b'fixture')
        os.utime(movie, (time.time() - 30, time.time() - 30))
        store = app.AppMetadataStore(self.data)
        store.save_authority_state({'active_provider': 'tmdb'})
        identity = {'tmdb_id': '712345', 'title': 'Protected Identity', 'year': '2005', 'plot': 'Protected manual metadata.'}
        store.apply_tmdb_match(str(movie), identity)
        with patch('app.probe_media_file', return_value=self._probe(movie)), patch('app._fetch_tmdb_metadata_by_id', return_value=identity):
            app._library_ingestion_coordinator().reconcile_paths_now([movie], require_publication=True,
                identity_hints={str(movie): {'tmdb_id': '798765', 'title': 'Other Film', 'year': '2011'}})
        record = store.catalog.get_record('app_metadata/files.json', store._key(movie))
        self.assertEqual(record['tmdb_id'], '712345')
        self.assertTrue(record['manual_lock'])
        self.assertEqual(store.get_manual_match(str(movie))['tmdb_id'], '712345')

    def test_manual_choice_arriving_during_provider_work_discards_obsolete_result(self):
        movie = self.movies_a / 'Delayed.Provider.2006.mkv'
        movie.write_bytes(b'fixture')
        os.utime(movie, (time.time() - 30, time.time() - 30))
        store = app.AppMetadataStore(self.data)
        store.save_authority_state({'active_provider': 'tmdb'})
        manual = {'tmdb_id': '723456', 'title': 'New Manual Choice', 'year': '2006', 'plot': 'Manual choice arrived during external work.'}
        def delayed(*args, **kwargs):
            app.AppMetadataStore(self.data).apply_tmdb_match(str(movie), manual)
            return {'outcome': 'accepted', 'metadata': {'tmdb_id': '734567', 'title': 'Obsolete Answer', 'year': '2006'}, 'decision': {}}
        with patch('app.probe_media_file', return_value=self._probe(movie)), patch('app._resolve_tmdb_identity', side_effect=delayed):
            result = app._library_ingestion_coordinator().reconcile_paths_now([movie])
        record = store.catalog.get_record('app_metadata/files.json', store._key(movie))
        self.assertEqual(record['tmdb_id'], '723456')
        self.assertEqual(store.get_manual_match(str(movie))['tmdb_id'], '723456')
        self.assertTrue(record['manual_lock'])
        self.assertEqual(result['pending'], 1)
        self.assertNotEqual(record.get('movie_view_publication'), 'ready')

    def test_download_provider_failure_before_hint_retains_original_error(self):
        movie = self.movies_a / 'Provider.Timeout.2004.mkv'
        movie.write_bytes(b'fixture')
        with patch('app.urllib.request.urlopen', side_effect=TimeoutError('synthetic provider timeout')):
            with self.assertRaisesRegex(TimeoutError, 'synthetic provider timeout'):
                app._apply_completed_download_identity({'tmdb_id': '700987', 'paths': [str(movie)]})

    def test_known_path_never_reads_whole_core_documents_or_inventory(self):
        movie = self.movies_a / 'Bounded.Library.2003.mkv'
        movie.write_bytes(b'fixture')
        os.utime(movie, (time.time() - 30, time.time() - 30))
        store = app.AppMetadataStore(self.data)
        store.save_authority_state({'active_provider': 'filename'})
        coordinator = app._library_ingestion_coordinator()
        original_read = app.AppMetadataStore._read_json
        def bounded_read(owner, path, fallback):
            if Path(path).name in {'files.json', 'tmdb_metadata.json', 'plex_metadata.json', 'library_inventory.json'}:
                raise AssertionError('whole core document read: ' + str(path))
            return original_read(owner, path, fallback)
        with patch.object(app.AppMetadataStore, 'snapshot', side_effect=AssertionError('whole snapshot')), patch.object(app.AppMetadataStore, '_read_json', bounded_read), patch('app.probe_media_file', return_value=self._probe(movie)):
            result = coordinator.reconcile_paths_now([str(movie)])
        self.assertEqual(result['checked'], 1)
        self.assertEqual(result['review'], 1)

    def setUp(self):
        self.dispatcher_patch = patch('services.library_ingestion.LibraryIngestionCoordinator._ensure_dispatcher_locked')
        self.dispatcher_patch.start()
        if os.environ.get("CP_TEST_MODE") != "1":
            raise RuntimeError("Gate 2 tests require CP_TEST_MODE=1")
        declared = Path(os.environ["CP_TEST_ROOT"]).resolve()
        temporary = Path(tempfile.gettempdir()).resolve()
        if declared != temporary and temporary not in declared.parents:
            raise RuntimeError("CP_TEST_ROOT must be inside the system temporary directory")
        self.workspace = tempfile.TemporaryDirectory(dir=declared)
        self.root = Path(self.workspace.name)
        self.movies_a = self.root / "movies-a"
        self.movies_b = self.root / "movies-b"
        self.data = self.root / "user-data"
        self.movies_a.mkdir()
        self.movies_b.mkdir()
        self.data.mkdir()
        self.original = (
            app._movies_dirs,
            app._movies_dir,
            app._user_data_dir,
            app._tmdb_key,
            app._library_ingestion_coordinator_instance,
        )
        app._movies_dirs = [str(self.movies_a), str(self.movies_b)]
        app._movies_dir = str(self.movies_a)
        app._user_data_dir = str(self.data)
        app._tmdb_key = "isolated-test-key"
        app._library_ingestion_coordinator_instance = None

    def tearDown(self):
        coordinator = app._library_ingestion_coordinator_instance
        if coordinator is not None:
            coordinator.checkpoint_for_shutdown(timeout_seconds=2)
        (
            app._movies_dirs,
            app._movies_dir,
            app._user_data_dir,
            app._tmdb_key,
            app._library_ingestion_coordinator_instance,
        ) = self.original
        self.workspace.cleanup()
        self.dispatcher_patch.stop()

    @staticmethod
    def _probe(movie):
        stat_result = movie.stat()
        return MediaFileFacts(
            probe_status="ok",
            probe_size=stat_result.st_size,
            probe_modified_time=stat_result.st_mtime,
            quality_class="1080p",
            quality_source="measured",
        )

    def test_exact_path_reconciliation_never_walks_either_library_root(self):
        movie = self.movies_a / "Target.2026.1080p.mkv"
        movie.write_bytes(b"isolated fixture")
        os.utime(movie, (time.time() - 30, time.time() - 30))
        sentinel = self.movies_b / "must-not-be-seen.mkv"
        sentinel.write_bytes(b"sentinel")
        measured = self._probe(movie)

        with patch("app._file_copy_is_stable", return_value=True), patch(
            "app._migrate_metadata_path", return_value="matched"
        ), patch("app.probe_media_file", return_value=measured), patch(
            "services.library_ingestion.os.walk",
            side_effect=AssertionError("known path caused a filesystem walk"),
        ):
            result = app._library_ingestion_coordinator().reconcile_paths_now([movie])

        self.assertEqual(result["checked"], 1)
        self.assertEqual(result["matched"], 1)
        inventory = app.AppMetadataStore(self.data).get_library_inventory()
        self.assertIn(app._norm(str(movie)), inventory)
        self.assertNotIn(app._norm(str(sentinel)), inventory)

    def test_directory_reconciliation_walks_only_the_named_directory(self):
        bounded = self.movies_a / "Bounded Movie 2026"
        bounded.mkdir()
        movie = bounded / "Bounded.Movie.2026.mkv"
        movie.write_bytes(b"isolated fixture")
        os.utime(movie, (time.time() - 30, time.time() - 30))
        measured = self._probe(movie)
        walks = []

        def bounded_walk(directory):
            walks.append(os.path.abspath(str(directory)))
            yield str(bounded), [], [movie.name]

        with patch("app._file_copy_is_stable", return_value=True), patch(
            "app._migrate_metadata_path", return_value="matched"
        ), patch("app.probe_media_file", return_value=measured), patch(
            "services.library_ingestion.os.walk", side_effect=bounded_walk
        ):
            result = app._library_ingestion_coordinator().reconcile_directories_now(
                [bounded]
            )

        self.assertEqual(walks, [os.path.abspath(str(bounded))])
        self.assertEqual(result["matched"], 1)

    def test_path_outside_configured_roots_fails_before_stat_or_probe(self):
        external = self.root / "outside.mkv"
        external.write_bytes(b"outside")
        with patch("services.library_ingestion.os.stat") as stat_call, patch(
            "app.probe_media_file"
        ) as probe:
            with self.assertRaisesRegex(ValueError, "outside configured library roots"):
                app._library_ingestion_coordinator().reconcile_paths_now([external])
        stat_call.assert_not_called()
        probe.assert_not_called()

    def test_targeted_then_full_reconcile_is_idempotent_for_unchanged_file(self):
        movie = self.movies_a / "Parity.2026.1080p.mkv"
        movie.write_bytes(b"isolated fixture")
        os.utime(movie, (time.time() - 30, time.time() - 30))
        measured = self._probe(movie)

        with patch("app._file_copy_is_stable", return_value=True), patch(
            "app._migrate_metadata_path", return_value="matched"
        ), patch("app.probe_media_file", return_value=measured):
            targeted = app._library_ingestion_coordinator().reconcile_paths_now([movie])
            before = app.AppMetadataStore(self.data).snapshot()["files"][app._norm(str(movie))]
            full = app._library_ingestion_coordinator().reconcile_all_now()
            after = app.AppMetadataStore(self.data).snapshot()["files"][app._norm(str(movie))]

        self.assertEqual(targeted["matched"], 1)
        self.assertEqual(full["checked"], 0)
        self.assertEqual(before, after)

    def test_library_inventory_bookkeeping_never_advances_catalog_generations(self):
        store = app.AppMetadataStore(self.data)
        repository = store.catalog
        before = {
            "global": repository.generation(),
            "media": repository.generation("media"),
            "canonical": repository.catalog_meta("canonical_media_generation"),
        }
        inventory = {
            app._norm(str(self.movies_a / "Operational.2026.mkv")): {
                "path": str(self.movies_a / "Operational.2026.mkv"),
                "size": 123,
                "modified_time": 456,
            }
        }

        store.save_library_inventory(inventory)
        store.save_library_inventory(inventory)

        after = {
            "global": repository.generation(),
            "media": repository.generation("media"),
            "canonical": repository.catalog_meta("canonical_media_generation"),
        }
        self.assertEqual(after, before)
        self.assertTrue(store.has_library_inventory())
        self.assertEqual(store.get_library_inventory(), inventory)

    def test_populated_upgrade_startup_does_not_reprobe_or_reenrich_unchanged_card(self):
        movie = self.movies_a / "Legacy.Accepted.2009.1080p.mkv"
        movie.write_bytes(b"unchanged legacy fixture")
        os.utime(movie, (time.time() - 30, time.time() - 30))
        stat_result = movie.stat()
        store = app.AppMetadataStore(self.data)
        store.save_authority_state({"active_provider": "tmdb"})
        store.update_file_record(str(movie), {
            "filename": movie.name,
            "identity_status": "accepted",
            "identity_title": "Legacy Accepted",
            "identity_year": "2009",
            "identity_source": "manual_tmdb",
            "manual_lock": True,
            "metadata_status": "accepted",
            "metadata_accepted": True,
            "display_provider": "tmdb",
            "tmdb_id": "1208922",
            "enrichment_status": "complete",
            "ingest_status": "stable",
            "size": stat_result.st_size,
            "modified_time": stat_result.st_mtime,
        })
        store.save_library_inventory({
            app._norm(str(movie)): {
                "path": str(movie),
                "size": stat_result.st_size,
                "modified_time": stat_result.st_mtime,
            }
        })
        repository = store.catalog
        self.assertEqual(repository.catalog_meta(
            LibraryStartupCatchup.META_KEY, ""
        ), "")
        before = {
            "global": repository.generation(),
            "media": repository.generation("media"),
            "canonical": repository.catalog_meta("canonical_media_generation"),
        }

        with patch("app.probe_media_file") as probe, patch(
            "app._reconcile_library_path"
        ) as reconcile_path, patch("app.urllib.request.urlopen") as provider:
            result = LibraryStartupCatchup(
                lambda: [str(self.movies_a)],
                app._library_ingestion_coordinator(),
                repository,
            ).run_once()

        after = {
            "global": repository.generation(),
            "media": repository.generation("media"),
            "canonical": repository.catalog_meta("canonical_media_generation"),
        }
        self.assertEqual(result["result"]["checked"], 0)
        self.assertEqual(after, before)
        self.assertTrue(repository.catalog_meta(LibraryStartupCatchup.META_KEY, ""))
        probe.assert_not_called()
        reconcile_path.assert_not_called()
        provider.assert_not_called()

    def test_bounded_directory_reconciliation_prunes_deleted_file_only_in_scope(self):
        directory = self.movies_a / "Offline Delete"
        directory.mkdir()
        movie = directory / "Offline.Delete.2026.mkv"
        movie.write_bytes(b"isolated fixture")
        os.utime(movie, (time.time() - 30, time.time() - 30))
        outside = self.movies_b / "Preserve.2025.mkv"
        outside.write_bytes(b"outside fixture")
        os.utime(outside, (time.time() - 30, time.time() - 30))
        measured_movie = self._probe(movie)
        measured_outside = self._probe(outside)

        with patch("app._file_copy_is_stable", return_value=True), patch(
            "app._migrate_metadata_path", return_value="matched"
        ), patch(
            "app.probe_media_file",
            side_effect=[measured_movie, measured_outside],
        ):
            coordinator = app._library_ingestion_coordinator()
            coordinator.reconcile_paths_now([movie, outside])

        movie.unlink()
        result = coordinator.reconcile_directories_now(
            [directory],
            enrich_accepted=False,
        )
        snapshot = app.AppMetadataStore(self.data).snapshot()["files"]
        inventory = app.AppMetadataStore(self.data).get_library_inventory()

        self.assertEqual(result["removed"], 1)
        self.assertNotIn(app._norm(str(movie)), snapshot)
        self.assertNotIn(app._norm(str(movie)), inventory)
        self.assertIn(app._norm(str(outside)), snapshot)
        self.assertIn(app._norm(str(outside)), inventory)


if __name__ == "__main__":
    unittest.main()
