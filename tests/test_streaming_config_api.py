import unittest
from unittest.mock import patch

import app


class StreamingConfigApiTests(unittest.TestCase):
    def setUp(self):
        self.original = {
            "enabled": app._streaming_enabled,
            "label": app._streaming_label,
            "template": app._streaming_url_template,
        }
        app._streaming_enabled = True
        app._streaming_label = "Stream"
        app._streaming_url_template = "https://streamimdb.ru/embed/movie/{tmdb_id}"
        self.client = app.app.test_client()
        self.save_patch = patch.object(app, "_save_config")
        self.save_config = self.save_patch.start()

    def tearDown(self):
        self.save_patch.stop()
        app._streaming_enabled = self.original["enabled"]
        app._streaming_label = self.original["label"]
        app._streaming_url_template = self.original["template"]

    def test_streaming_config_defaults_to_enabled_tmdb_template(self):
        response = self.client.get("/api/streaming/config")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {
            "enabled": True,
            "label": "Stream",
            "url_template": "https://streamimdb.ru/embed/movie/{tmdb_id}",
        })

    def test_streaming_config_persists_custom_template(self):
        response = self.client.post("/api/streaming/config", json={
            "enabled": False,
            "label": "Watch",
            "url_template": "https://example.test/title/{imdb_id}",
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {
            "success": True,
            "enabled": False,
            "label": "Watch",
            "url_template": "https://example.test/title/{imdb_id}",
        })
        self.save_config.assert_called_once()
        saved = self.save_config.call_args.args[0]
        self.assertEqual(saved["streaming_enabled"], False)
        self.assertEqual(saved["streaming_label"], "Watch")
        self.assertEqual(saved["streaming_url_template"], "https://example.test/title/{imdb_id}")

    def test_streaming_config_requires_http_url_when_template_present(self):
        response = self.client.post("/api/streaming/config", json={
            "enabled": True,
            "label": "Stream",
            "url_template": "javascript:alert(1)",
        })

        self.assertEqual(response.status_code, 400)
        self.assertIn("http", response.get_json()["error"].lower())


if __name__ == "__main__":
    unittest.main()
