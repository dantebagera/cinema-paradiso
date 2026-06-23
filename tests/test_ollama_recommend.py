import json
import unittest
from unittest.mock import patch

import app


class FakeOllamaResponse:
    def __init__(self, recommendations=None):
        self.recommendations = recommendations or [
            {"title": f"Movie {index}", "year": "2000", "reason": "Matches the prompt."}
            for index in range(10)
        ]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps({
            "message": {
                "content": json.dumps({
                    "recommendations": self.recommendations
                })
            }
        }).encode()


class OllamaRecommendTest(unittest.TestCase):
    def test_config_exposes_and_saves_candidate_limit(self):
        original_url = app._ollama_url
        original_model = app._ollama_model
        original_limit = app._ollama_candidate_limit
        app._ollama_url = "http://ollama.test"
        app._ollama_model = "local-model"
        app._ollama_candidate_limit = app.OLLAMA_CANDIDATE_LIMIT_DEFAULT
        client = app.app.test_client()

        try:
            response = client.get("/api/ollama/config")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()["candidate_limit"], 15)

            with patch("app._save_config"):
                response = client.post(
                    "/api/ollama/config",
                    json={"url": "http://new-ollama.test/", "model": "new-model", "candidate_limit": 7}
                )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(app._ollama_url, "http://new-ollama.test")
            self.assertEqual(app._ollama_model, "new-model")
            self.assertEqual(app._ollama_candidate_limit, 7)
        finally:
            app._ollama_url = original_url
            app._ollama_model = original_model
            app._ollama_candidate_limit = original_limit

    def test_config_rejects_invalid_candidate_limit(self):
        original_limit = app._ollama_candidate_limit
        app._ollama_candidate_limit = app.OLLAMA_CANDIDATE_LIMIT_DEFAULT
        try:
            response = app.app.test_client().post(
                "/api/ollama/config",
                json={"url": "http://ollama.test", "model": "local-model", "candidate_limit": 51}
            )
        finally:
            app._ollama_candidate_limit = original_limit

        self.assertEqual(response.status_code, 400)
        self.assertIn("candidate_limit", response.get_json()["error"])

    def test_config_preserves_candidate_limit_when_omitted(self):
        original_url = app._ollama_url
        original_model = app._ollama_model
        original_limit = app._ollama_candidate_limit
        app._ollama_url = "http://ollama.test"
        app._ollama_model = "local-model"
        app._ollama_candidate_limit = 6

        try:
            with patch("app._save_config"):
                response = app.app.test_client().post(
                    "/api/ollama/config",
                    json={"url": "http://new-ollama.test", "model": "new-model"}
                )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(app._ollama_candidate_limit, 6)
        finally:
            app._ollama_url = original_url
            app._ollama_model = original_model
            app._ollama_candidate_limit = original_limit

    def test_prompt_uses_candidate_limit_and_caps_deduped_results(self):
        captured = {}
        original_url = app._ollama_url
        original_model = app._ollama_model
        original_limit = app._ollama_candidate_limit
        original_tmdb_key = app._tmdb_key
        app._ollama_url = "http://ollama.test"
        app._ollama_model = "local-model"
        app._ollama_candidate_limit = 3
        app._tmdb_key = ""

        recommendations = [
            {"title": "Carrie", "year": "1976", "reason": "King adaptation."},
            {"title": "carrie", "year": "1976", "reason": "Duplicate casing."},
            {"title": "The Shining", "year": "1980", "reason": "Haunted hotel."},
            {"title": "Misery", "year": "1990", "reason": "Psychological thriller."},
            {"title": "The Mist", "year": "2007", "reason": "Creature horror."},
        ]

        def fake_urlopen(request, timeout=0):
            captured["body"] = json.loads(request.data.decode())
            return FakeOllamaResponse(recommendations)

        try:
            with patch("app.urllib.request.urlopen", side_effect=fake_urlopen), \
                 patch("app._ollama_enrich_with_tmdb", return_value=None):
                response = app.app.test_client().post(
                    "/api/ollama/recommend",
                    json={"prompt": "warm crime movie"}
                )
        finally:
            app._ollama_url = original_url
            app._ollama_model = original_model
            app._ollama_candidate_limit = original_limit
            app._tmdb_key = original_tmdb_key

        self.assertEqual(response.status_code, 200)
        system_message = captured["body"]["messages"][0]["content"]
        self.assertIn("Return at most 3 feature-length movie candidates.", system_message)
        self.assertIn("Exclude TV series, miniseries, episodes, books, games, and unreleased films.", system_message)
        self.assertNotIn("Give exactly 10 recommendations.", system_message)
        results = response.get_json()["results"]
        self.assertEqual([item["title"] for item in results], ["Carrie", "The Shining", "Misery"])


if __name__ == "__main__":
    unittest.main()
