import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class IPTVUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_source = (ROOT / "src" / "App.jsx").read_text(encoding="utf-8")
        cls.workspace_source = (ROOT / "src" / "features" / "iptv" / "IPTVWorkspace.jsx").read_text(encoding="utf-8")
        cls.lists_source = (ROOT / "src" / "features" / "iptv" / "IPTVListsWorkspace.jsx").read_text(encoding="utf-8")
        cls.api_source = (ROOT / "src" / "api" / "iptv.js").read_text(encoding="utf-8")
        cls.player_source = (ROOT / "src" / "features" / "iptv" / "IPTVPlayer.jsx").read_text(encoding="utf-8")
        cls.settings_source = (ROOT / "src" / "features" / "settings" / "SettingsWorkspace.jsx").read_text(encoding="utf-8")

    def test_iptv_is_a_first_class_lazy_workspace(self):
        self.assertIn("const IPTVWorkspace = lazy", self.app_source)
        self.assertIn("id: 'iptv'", self.app_source)
        self.assertIn("<IPTVWorkspace notify={notify}", self.app_source)

    def test_workspace_keeps_provider_sections_and_ownership_actions_separate(self):
        for label in ("Live TV", "Movies", "Series", "Favorites", "My Lists"):
            self.assertIn(label, self.workspace_source)
        self.assertIn("All provider categories", self.workspace_source)
        self.assertNotIn("Owned", self.workspace_source)
        self.assertNotIn("Find Torrent", self.workspace_source)

    def test_favorites_are_visible_and_support_a_mixed_default_view(self):
        self.assertIn("useState('all')", self.workspace_source)
        self.assertIn("['all', 'All']", self.workspace_source)
        self.assertIn("cornerControls={<div className=\"iptv-movie-corner-actions\"", self.workspace_source)
        self.assertIn("function FavoritesView", self.workspace_source)
        self.assertIn("No favorites yet", self.workspace_source)

    def test_custom_lists_support_mixed_media_crud_and_manual_order(self):
        for label in ("New list", "Rename", "Delete", "Channels", "Movies", "Series"):
            self.assertIn(label, self.lists_source)
        self.assertIn("IPTVListPickerModal", self.workspace_source)
        self.assertIn("moveListItem", self.api_source)
        self.assertIn("setListItem", self.api_source)
        self.assertIn("Unavailable from provider", self.lists_source)

    def test_saved_iptv_credentials_are_loaded_redacted(self):
        self.assertIn("username_hint", self.settings_source)
        self.assertIn("password: ''", self.settings_source)
        self.assertIn("Allow invalid provider TLS certificate", self.settings_source)

    def test_live_player_keeps_headroom_and_recovers_bounded_failures(self):
        self.assertIn("initialLiveManifestSize: 1", self.player_source)
        self.assertIn("bufferedSeconds >= 12", self.player_source)
        self.assertIn("tryStartLivePlayback(true), 15000", self.player_source)
        self.assertIn("The provider is not sending enough data", self.player_source)
        self.assertIn("liveSyncDuration: 12", self.player_source)
        self.assertIn("liveMaxLatencyDuration: 30", self.player_source)
        self.assertIn("maxBufferLength: 30", self.player_source)
        self.assertIn("networkRecoveryAttempts < 3", self.player_source)
        self.assertIn("mediaRecoveryAttempts < 2", self.player_source)
        self.assertIn("hls?.startLoad()", self.player_source)
        self.assertIn("hls.recoverMediaError()", self.player_source)


if __name__ == "__main__":
    unittest.main()
