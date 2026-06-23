from pathlib import Path
import json
import unittest


class QBittorrentUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.source = (root / "src" / "App.jsx").read_text(encoding="utf-8")
        cls.backend_source = (root / "app.py").read_text(encoding="utf-8")

    def test_sidebar_has_downloads_navigation(self):
        self.assertIn("id: 'downloads'", self.source)
        self.assertNotIn("if (id === 'downloads')", self.source)
        self.assertIn("activeSection === 'downloads'", self.source)

    def test_sidebar_has_help_navigation(self):
        self.assertIn("id: 'help'", self.source)
        self.assertIn("label: 'Help'", self.source)
        self.assertIn("activeSection === 'help'", self.source)

    def test_help_workspace_documents_optional_integrations(self):
        self.assertIn("function HelpWorkspace()", self.source)
        for text in ["Plex", "Prowlarr", "TMDB", "Ollama", "qBittorrent", "Open Settings"]:
            self.assertIn(text, self.source)

    def test_help_workspace_contains_medium_cp_manual(self):
        self.assertIn("Cinema Paradiso Manual", self.source)
        for text in [
            "Quick Start",
            "Home dashboard",
            "Library workspace",
            "Cleanup workspace",
            "Discover workspace",
            "Downloads workspace",
            "Settings workspace",
            "Safety rules",
            "What CP does",
            "What CP will not do"
        ]:
            self.assertIn(text, self.source)

    def test_downloads_workspace_keeps_cp_shell_and_frames_qbittorrent(self):
        self.assertIn("function DownloadsWorkspace()", self.source)
        self.assertIn('title="qBittorrent Downloads"', self.source)
        self.assertIn('src="/qbittorrent/"', self.source)
        self.assertIn("@app.route('/qbittorrent/')", self.backend_source)

    def test_downloads_header_credits_qbittorrent_with_official_icon(self):
        self.assertIn('src="/qbittorrent/images/qbittorrent32.png"', self.source)
        self.assertIn("Powered by qBittorrent", self.source)
        self.assertIn("downloads-title-credit", self.source)

    def test_torrent_results_submit_to_embedded_api(self):
        self.assertIn("'/api/qbittorrent/submit'", self.source)
        self.assertIn("{mode === 'system' ? 'Open magnet' : 'Download'}", self.source)
        self.assertNotIn("Send to qBittorrent", self.source)

    def test_indexer_cards_receive_notify_for_torrent_submission(self):
        component = self.source.split("function IndexerMovieCard({", 1)[1].split("}) {", 1)[0]
        self.assertIn("notify,", component)

    def test_prowlarr_download_url_is_not_opened_in_new_tab(self):
        self.assertNotIn("href={actionUrl} target=\"_blank\"", self.source)
        self.assertIn("Open source page", self.source)
        self.assertIn("Open externally", self.source)

    def test_qbittorrent_dynamic_views_are_proxied(self):
        self.assertIn("@app.route('/views/<path:filename>')", self.backend_source)

    def test_settings_expose_torrent_mode_and_storage_paths(self):
        self.assertIn("Torrent handling", self.source)
        self.assertIn("Movie download folder", self.source)
        self.assertIn("Incomplete downloads folder", self.source)

    def test_settings_no_longer_show_qbittorrent_install_or_update_buttons(self):
        self.assertNotIn('label="Install qBittorrent"', self.source)
        self.assertNotIn('label="Update qBittorrent"', self.source)
        self.assertNotIn("runQbittorrentAction('install')", self.source)
        self.assertNotIn("runQbittorrentAction('update')", self.source)

    def test_settings_show_bundled_qbittorrent_runtime_text(self):
        self.assertIn("Bundled qBittorrent", self.source)
        self.assertIn("Open Downloads", self.source)

    def test_readme_and_package_document_265_bundled_qbt_and_help(self):
        root = Path(__file__).resolve().parents[1]
        readme = (root / "README.md").read_text(encoding="utf-8")
        changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
        package = json.loads((root / "package.json").read_text(encoding="utf-8"))

        self.assertEqual(package["version"], "2.6.5")
        self.assertIn("v2.6.5", readme)
        self.assertIn("Help", readme)
        self.assertIn("bundled qbittorrent", readme.lower())
        self.assertIn("v2.6.5", changelog)
        self.assertIn("Help", changelog)


if __name__ == "__main__":
    unittest.main()
