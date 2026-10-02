import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app


class StartupBackgroundOwnershipTest(unittest.TestCase):
    def test_awards_test_mode_has_no_automatic_source_reads_or_worker(self):
        with patch('app.MovieAwardsRefresh') as refresh, patch('app.RuntimeAwardsSources') as sources:
            app._start_movie_awards_refresh()
        refresh.assert_not_called();sources.assert_not_called()

    def test_awards_start_once_and_shutdown_stop_only_owned_worker(self):
        old=app._movie_awards_refresh_instance
        try:
            app._movie_awards_refresh_instance=None
            with patch.object(app,'_TEST_MODE',False),patch('app.MovieAwardsRefresh') as refresh,patch('app.RuntimeAwardsSources'):
                app._start_movie_awards_refresh();app._start_movie_awards_refresh()
                refresh.assert_called_once();refresh.return_value.start.assert_called_once()
                app._stop_movie_awards_refresh();app._stop_movie_awards_refresh()
                refresh.return_value.stop.assert_called_once()
        finally:app._movie_awards_refresh_instance=old

    def setUp(self):
        if os.environ.get("CP_TEST_MODE") != "1":
            raise RuntimeError("Startup ownership tests require CP_TEST_MODE=1")
        declared = Path(os.environ["CP_TEST_ROOT"]).resolve()
        temporary = Path(tempfile.gettempdir()).resolve()
        if declared != temporary and temporary not in declared.parents:
            raise RuntimeError("CP_TEST_ROOT must be temporary")
        self.workspace = tempfile.TemporaryDirectory(dir=declared)
        self.original_user_data = app._user_data_dir
        app._user_data_dir = str(Path(self.workspace.name) / "user-data")

    def tearDown(self):
        app._user_data_dir = self.original_user_data
        self.workspace.cleanup()

    def test_normal_background_start_has_no_automatic_global_artwork_mutation(self):
        repository = app._catalog_repository()
        before = (repository.generation(), repository.generation("media"))
        with patch("app._start_library_reconcile") as reconcile, patch(
            "app._library_observer"
        ) as observer, patch("app.LibraryStartupCatchup") as catchup, patch(
            "app.threading.Thread"
        ) as thread, patch("app.threading.Timer") as timer, patch(
            "app._media_asset_service"
        ) as asset_service:
            app._start_background_services()

        reconcile.assert_called_once_with()
        observer.return_value.start.assert_called_once_with()
        catchup.assert_called_once()
        self.assertEqual(thread.call_count, 3)
        timer.assert_not_called()
        asset_service.assert_not_called()
        self.assertEqual(
            (repository.generation(), repository.generation("media")),
            before,
        )


if __name__ == "__main__":
    unittest.main()
