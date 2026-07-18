import unittest
from pathlib import Path

from trial_server import (
    build_shell_html,
    build_upstream_headers,
    inject_sidebar,
    rewrite_location,
)


class TrialServerTests(unittest.TestCase):
    def test_shell_contains_download_link_to_top_level_qbt_page(self):
        html = build_shell_html()

        self.assertIn('id="downloads-link"', html)
        self.assertIn('href="/downloads"', html)
        self.assertNotIn("<iframe", html)

    def test_download_page_injects_sidebar_into_qbittorrent_document(self):
        html = "<html><head><title>qBittorrent</title></head><body><main>QBT</main></body></html>"

        embedded = inject_sidebar(html)

        self.assertIn('id="cp-test-sidebar"', embedded)
        self.assertIn("<main>QBT</main>", embedded)
        self.assertIn("padding-left: 160px", embedded)

    def test_proxy_rewrites_browser_origin_for_qbittorrent(self):
        headers = build_upstream_headers(
            {
                "Host": "127.0.0.1:8090",
                "Origin": "http://127.0.0.1:8090",
                "Referer": "http://127.0.0.1:8090/shell",
                "Connection": "keep-alive",
            }
        )

        self.assertEqual(headers["Host"], "127.0.0.1:8080")
        self.assertEqual(headers["Origin"], "http://127.0.0.1:8080")
        self.assertEqual(headers["Referer"], "http://127.0.0.1:8080/shell")
        self.assertNotIn("Connection", headers)

    def test_proxy_rewrites_upstream_redirect_to_test_origin(self):
        self.assertEqual(
            rewrite_location("http://127.0.0.1:8080/login"),
            "http://127.0.0.1:8090/login",
        )

    def test_launcher_forces_the_webui_port(self):
        launcher = Path(__file__).with_name("run-trial.ps1").read_text(encoding="utf-8")

        self.assertIn("--webui-port=8080", launcher)

    def test_launcher_does_not_overwrite_a_running_runtime(self):
        launcher = Path(__file__).with_name("run-trial.ps1").read_text(encoding="utf-8")

        self.assertIn("$RuntimeNeedsCopy", launcher)
        self.assertIn("Wait-Process", launcher)

    def test_launcher_sets_required_webui_credentials(self):
        launcher = Path(__file__).with_name("run-trial.ps1").read_text(encoding="utf-8")

        self.assertIn("WebUI\\Username=admin", launcher)
        self.assertIn("WebUI\\Password_PBKDF2=", launcher)


if __name__ == "__main__":
    unittest.main()
