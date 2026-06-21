import io
import json
import unittest
import urllib.error
import urllib.parse

from services.plex_match import PlexMatchAdapter, PlexMatchError


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


def plex_payload(*results):
    return {"MediaContainer": {"SearchResult": list(results)}}


class PlexMatchAdapterTest(unittest.TestCase):
    def test_builds_one_valid_manual_query_and_sends_token_in_header(self):
        requests = []

        def open_url(request, timeout):
            requests.append((request, timeout))
            return FakeResponse(plex_payload())

        adapter = PlexMatchAdapter("http://plex.test", "secret-token", open_url=open_url)
        adapter.search("42", title="Alien", year="1979")

        request, timeout = requests[0]
        parsed = urllib.parse.urlparse(request.full_url)
        query = urllib.parse.parse_qs(parsed.query)
        self.assertNotIn("&&", request.full_url)
        self.assertEqual(query["manual"], ["1"])
        self.assertEqual(query["title"], ["Alien"])
        self.assertEqual(query["year"], ["1979"])
        self.assertNotIn("X-Plex-Token", query)
        self.assertEqual(request.get_header("X-plex-token"), "secret-token")
        self.assertEqual(timeout, 15)

    def test_merges_title_imdb_and_tmdb_queries_with_rich_results(self):
        payloads = {
            "Alien": plex_payload(
                {
                    "guid": "plex://movie/alien",
                    "name": "Alien",
                    "year": 1979,
                    "thumb": "https://images.plex.tv/alien.jpg",
                    "summary": "Crew encounters a hostile life-form.",
                },
                {"guid": "plex://movie/other", "name": "Alien Nation", "year": 1988},
            ),
            "imdb-tt0078748": plex_payload(
                {
                    "guid": "plex://movie/alien",
                    "name": "Alien",
                    "year": 1979,
                    "thumb": "https://images.plex.tv/alien.jpg",
                    "summary": "Crew encounters a hostile life-form.",
                }
            ),
            "tmdb-348": plex_payload(
                {
                    "guid": "plex://movie/alien",
                    "name": "Alien",
                    "year": 1979,
                    "thumb": "https://images.plex.tv/alien.jpg",
                    "summary": "Crew encounters a hostile life-form.",
                }
            ),
        }

        def open_url(request, timeout):
            query = urllib.parse.parse_qs(urllib.parse.urlparse(request.full_url).query)
            return FakeResponse(payloads[query["title"][0]])

        adapter = PlexMatchAdapter("http://plex.test", "token", open_url=open_url)
        results = adapter.search(
            "42",
            title="Alien",
            year="1979",
            imdb_id="tt0078748",
            tmdb_id="348",
        )

        self.assertEqual(len(results), 2)
        alien = results[0]
        self.assertEqual(alien["guid"], "plex://movie/alien")
        self.assertEqual(alien["rank"], 1)
        self.assertEqual(alien["poster_url"], "https://images.plex.tv/alien.jpg")
        self.assertIn("hostile life-form", alien["summary"])
        self.assertEqual(
            alien["query_sources"],
            ["imdb_id", "tmdb_id", "title_year"],
        )
        self.assertTrue(alien["exact_external_id"])
        self.assertIn("Exact IMDb identity", alien["match_reasons"])
        self.assertIn("Exact TMDB identity", alien["match_reasons"])

    def test_limits_results_to_twenty_and_rejects_malformed_payload(self):
        results = [
            {"guid": f"plex://movie/{index}", "name": f"Movie {index}", "year": 2000 + index}
            for index in range(25)
        ]
        adapter = PlexMatchAdapter(
            "http://plex.test",
            "token",
            open_url=lambda request, timeout: FakeResponse(plex_payload(*results)),
        )
        self.assertEqual(len(adapter.search("42", title="Movie")), 20)

        malformed = PlexMatchAdapter(
            "http://plex.test",
            "token",
            open_url=lambda request, timeout: FakeResponse({"MediaContainer": {"SearchResult": "bad"}}),
        )
        with self.assertRaisesRegex(PlexMatchError, "malformed"):
            malformed.search("42", title="Movie")

    def test_http_error_is_sanitized_and_never_exposes_token(self):
        body = b'{"error":"agent failed for X-Plex-Token=secret-token"}'
        error = urllib.error.HTTPError(
            "http://plex.test/request?X-Plex-Token=secret-token",
            400,
            "Bad Request",
            {},
            io.BytesIO(body),
        )
        adapter = PlexMatchAdapter(
            "http://plex.test",
            "secret-token",
            open_url=lambda request, timeout: (_ for _ in ()).throw(error),
        )

        with self.assertRaises(PlexMatchError) as raised:
            adapter.search("42", title="Alien")

        self.assertEqual(raised.exception.status, 400)
        self.assertIn("Plex returned HTTP 400", str(raised.exception))
        self.assertNotIn("secret-token", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
