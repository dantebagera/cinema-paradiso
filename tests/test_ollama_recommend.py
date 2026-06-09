import json
import unittest
from unittest.mock import patch

import app


class FakeOllamaResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps({
            "message": {
                "content": json.dumps({
                    "recommendations": [
                        {"title": f"Movie {index}", "year": "2000", "reason": "Matches the prompt."}
                        for index in range(10)
                    ]
                })
            }
        }).encode()


class OllamaRecommendTest(unittest.TestCase):
    def test_prompt_requests_exactly_ten_recommendations(self):
        captured = {}
        original_url = app._ollama_url
        original_model = app._ollama_model
        app._ollama_url = "http://ollama.test"
        app._ollama_model = "local-model"

        def fake_urlopen(request, timeout=0):
            captured["body"] = json.loads(request.data.decode())
            return FakeOllamaResponse()

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

        self.assertEqual(response.status_code, 200)
        system_message = captured["body"]["messages"][0]["content"]
        self.assertIn("Give exactly 10 recommendations.", system_message)
        self.assertEqual(len(response.get_json()["results"]), 10)


if __name__ == "__main__":
    unittest.main()
