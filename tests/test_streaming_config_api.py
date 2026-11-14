import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import app


class StreamingConfigApiTests(unittest.TestCase):
    def setUp(self):
        self.original = {
            "enabled": app._streaming_enabled,
            "label": app._streaming_label,
            "template": app._streaming_url_template,
            "tv_template": app._streaming_tv_url_template,
            "tv_enabled": app._tv_enabled,
        }
        app._streaming_enabled = True
        app._streaming_label = "Stream"
        app._streaming_url_template = "https://streamimdb.ru/embed/movie/{tmdb_id}"
        app._streaming_tv_url_template = ""
        app._tv_enabled = False
        self.client = app.app.test_client()
        self.save_patch = patch.object(app, "_save_config")
        self.save_config = self.save_patch.start()

    def tearDown(self):
        self.save_patch.stop()
        app._streaming_enabled = self.original["enabled"]
        app._streaming_label = self.original["label"]
        app._streaming_url_template = self.original["template"]
        app._streaming_tv_url_template = self.original["tv_template"]
        app._tv_enabled = self.original["tv_enabled"]

    def test_movie_sources_include_builtins_custom_and_respect_disabled(self):
        app._streaming_url_template = 'https://custom.example/{imdb_id}'
        data = self.client.get('/api/streaming/config').json
        self.assertEqual([source['id'] for source in data['movie_sources']], ['custom', 'streamimdb', 'vsembed'])
        self.assertEqual(data['movie_sources'][0]['url_template'], app._streaming_url_template)
        app._streaming_enabled = False
        self.assertEqual(self.client.get('/api/streaming/config').json['movie_sources'], [])

    def test_streaming_config_defaults_to_enabled_tmdb_template(self):
        response = self.client.get("/api/streaming/config")

        self.assertEqual(response.status_code, 200)
        self.assertEqual({key: response.json[key] for key in ("enabled", "label", "url_template")}, {
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
        self.assertEqual({key: response.json[key] for key in ("success", "enabled", "label", "url_template")}, {
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

    def test_default_exposes_both_named_providers_without_saving(self):
        data = self.client.get('/api/streaming/config').json
        self.assertEqual(data['provider'], 'streamimdb')
        self.assertEqual(data['providers'], [
            {'id': 'streamimdb', 'label': 'StreamIMDB',
             'url_template': 'https://streamimdb.ru/embed/movie/{tmdb_id}',
             'tv_url_template': 'https://streamimdb.ru/embed/tv/{tmdb_id}/{season_number}/{episode_number}'},
            {'id': 'vsembed', 'label': 'VSEmbed',
             'url_template': 'https://vsembed.ru/embed/movie/{tmdb_id}/',
             'tv_url_template': 'https://vsembed.ru/embed/tv/{tmdb_id}/{season_number}-{episode_number}'},
        ])
        self.save_config.assert_not_called()

    def test_selected_provider_sets_and_persists_both_templates(self):
        for provider, movie_url, tv_url in [
            ('vsembed', 'https://vsembed.ru/embed/movie/{tmdb_id}/',
             'https://vsembed.ru/embed/tv/{tmdb_id}/{season_number}-{episode_number}'),
            ('streamimdb', 'https://streamimdb.ru/embed/movie/{tmdb_id}',
             'https://streamimdb.ru/embed/tv/{tmdb_id}/{season_number}/{episode_number}'),
        ]:
            with self.subTest(provider=provider):
                response = self.client.post('/api/streaming/config', json={
                    'provider': provider, 'enabled': False, 'label': 'Watch',
                    'url_template': 'https://stale.invalid/{imdb_id}',
                    'tv_url_template': 'https://stale.invalid/invalid',
                })
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json['provider'], provider)
                self.assertEqual(response.json['url_template'], movie_url)
                self.assertEqual(response.json['tv_url_template'], tv_url)
                self.assertFalse(response.json['enabled'])
                self.assertEqual(response.json['label'], 'Watch')
                saved = self.save_config.call_args.args[0]
                self.assertEqual(saved['streaming_url_template'], movie_url)
                self.assertEqual(saved['streaming_tv_url_template'], tv_url)
                self.assertNotIn('streaming_provider', saved)
                self.assertEqual(self.client.get('/api/streaming/config').json['provider'], provider)

    def test_legacy_templates_identify_provider_after_reload_without_a_provider_flag(self):
        app._streaming_url_template = 'https://vsembed.ru/embed/movie/{tmdb_id}/'
        app._streaming_tv_url_template = 'https://vsembed.ru/embed/tv/{tmdb_id}/{season_number}-{episode_number}'
        self.assertEqual(self.client.get('/api/streaming/config').json['provider'], 'vsembed')
        self.save_config.assert_not_called()

    def test_custom_urls_and_explicit_tv_override_are_preserved(self):
        movie = 'https://example.test/movie/{imdb_id}'
        tv = 'https://example.test/tv/{tmdb_id}/{season_number}/{episode_number}'
        response = self.client.post('/api/streaming/config', json={
            'provider': 'custom', 'url_template': movie, 'tv_url_template': tv,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['provider'], 'custom')
        self.assertEqual(response.json['url_template'], movie)
        self.assertEqual(response.json['tv_url_template'], tv)
        app._streaming_url_template = 'https://streamimdb.ru/embed/movie/{tmdb_id}'
        data = self.client.get('/api/streaming/config').json
        self.assertEqual(data['provider'], 'custom')
        self.assertEqual(data['tv_url_template'], tv)

    def test_invalid_selection_or_custom_template_does_not_mutate_saved_state(self):
        before = self.client.get('/api/streaming/config').json
        for payload in [
            {'provider': 'unknown'}, {'provider': None}, {'provider': ['vsembed']}, ['vsembed'],
            [], False, 0, None,
            {'provider': 'custom', 'url_template': 'javascript:alert(1)'},
            {'provider': 'custom', 'url_template': 'http://['},
            {'provider': 'custom', 'url_template': 'https://'},
            {'provider': 'custom', 'url_template': 'https://example.test/{tmdb_id}', 'tv_url_template': 'https://example.test/{tmdb_id}'},
        ]:
            with self.subTest(payload=payload):
                response = self.client.post('/api/streaming/config', json=payload)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(self.client.get('/api/streaming/config').json, before)
                self.save_config.assert_not_called()

    def test_known_vsembed_movie_template_derives_tv_without_config_write(self):
        app._tv_enabled = True
        app._streaming_url_template = 'https://vsembed.ru/embed/movie/{tmdb_id}/'
        data = self.client.get('/api/streaming/config').json
        self.assertEqual(data['provider'], 'vsembed')
        self.assertEqual(data['tv_url_template'], 'https://vsembed.ru/embed/tv/{tmdb_id}/{season_number}-{episode_number}')
        self.save_config.assert_not_called()

    def test_selected_provider_survives_a_fresh_backend_process(self):
        with tempfile.TemporaryDirectory(prefix='cp-streaming-restart-') as root:
            environment = {**os.environ, 'CP_TEST_MODE': '1', 'CP_TEST_ROOT': root,
                           'CP_TEST_DIST_DIR': str(Path(root) / 'dist')}
            for operation in [
                "response = client.post('/api/streaming/config', json={'provider': 'vsembed'})",
                "response = client.get('/api/streaming/config')",
            ]:
                script = "import app, json; client = app.app.test_client(); " + operation + "; assert response.status_code == 200; print(json.dumps(response.json))"
                result = subprocess.run([sys.executable, '-c', script], env=environment,
                                        cwd=Path(__file__).resolve().parents[1], capture_output=True,
                                        text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr)
                data = json.loads(result.stdout)
                self.assertEqual(data['provider'], 'vsembed')
                self.assertEqual(data['url_template'], 'https://vsembed.ru/embed/movie/{tmdb_id}/')
                self.assertEqual(data['tv_url_template'], 'https://vsembed.ru/embed/tv/{tmdb_id}/{season_number}-{episode_number}')
            saved = json.loads(Path(root, 'config.json').read_text(encoding='utf-8'))
            self.assertEqual(saved['streaming_url_template'], 'https://vsembed.ru/embed/movie/{tmdb_id}/')
            self.assertNotIn('streaming_provider', saved)


if __name__ == "__main__":
    unittest.main()
