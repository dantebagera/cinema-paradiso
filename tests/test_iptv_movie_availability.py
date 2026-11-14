import json
import io
import sys
import sqlite3
import tempfile
import unittest
from pathlib import Path
from contextlib import closing, contextmanager
from unittest.mock import patch, Mock

from flask import Flask

from services.iptv_movie_store import IPTVMovieStore, source_key
from services.iptv_provider_manager import IPTVProviderManager
from services.iptv_routes import register_iptv_routes
from services.iptv_tmdb import normalize_tmdb_movie
from tests.iptv_movie_fixtures import tmdb_payload


class MovieAvailabilityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.provider_id = "a" * 32
        self.provider_root = self.root / "iptv" / "providers" / self.provider_id
        self.store = IPTVMovieStore(self.provider_root, self.provider_id)
        self.store.project_sources([
            {"item_id": "1", "name": "First (2024)"},
            {"item_id": "2", "name": "First (2024) 4K"},
            {"item_id": "3", "name": "Other (2024)"},
        ], 1)
        for item in ("1", "2"):
            self.store.apply_match("source:" + source_key(item),
                                   normalize_tmdb_movie(tmdb_payload()), manual=True)
        with self.store.connection() as connection:
            connection.execute("UPDATE source_classifications SET category='film'")
        self.registry = {"schema_version": 1, "last_selected_provider_id": self.provider_id,
                         "providers": [{"provider_id": self.provider_id, "name": "Lionz"}]}
        (self.root / "iptv" / "providers.json").write_text(json.dumps(self.registry))

    def lookup(self):
        return IPTVMovieStore.lookup_availability(self.provider_root, self.provider_id, [550, 999])

    def test_only_available_accepted_films_establish_presence(self):
        result = self.lookup()
        self.assertEqual(result["state"], "ready")
        self.assertEqual(result["matches"], {"550": {"movie_key": "tmdb:550", "source_count": 2}})
        with self.store.connection() as connection:
            connection.execute("UPDATE movie_sources SET available=0 WHERE source_id='1'")
            connection.execute("UPDATE source_classifications SET category='sports' WHERE source_key=?",
                               (source_key("2"),))
        self.assertEqual(self.lookup()["matches"], {})

    def test_schema_three_and_four_are_read_only(self):
        with self.store.connection() as connection:
            connection.execute("UPDATE movie_meta SET value='3' WHERE key='schema_version'")
        with patch.object(IPTVMovieStore, "__init__", side_effect=AssertionError("initialization")):
            self.assertEqual(self.lookup()["matches"]["550"]["source_count"], 2)
            result = IPTVMovieStore.lookup_sources(self.provider_root, self.provider_id, 550)
        self.assertEqual({row["item_id"] for row in result["items"]}, {"1", "2"})
        with closing(sqlite3.connect(self.store.database_path)) as connection:
            self.assertEqual(connection.execute("SELECT value FROM movie_meta WHERE key='schema_version'").fetchone()[0], "3")

    def test_readonly_lookup_observes_wal(self):
        with self.store.connection() as writer:
            writer.execute("UPDATE movie_sources SET available=0 WHERE source_id='1'")
            writer.commit()
            self.assertEqual(self.lookup()["matches"]["550"]["source_count"], 1)

    def test_missing_catalog_is_unknown_and_is_not_created(self):
        missing_id = "b" * 32
        missing = self.provider_root.parent / missing_id
        result = IPTVMovieStore.lookup_availability(missing, missing_id, [550])
        self.assertEqual(result["state"], "unknown")
        self.assertFalse(missing.exists())

    def test_all_providers_and_failure_isolation_without_initialization(self):
        self.registry["providers"].append({"provider_id": "b" * 32, "name": "EgySat"})
        (self.root / "iptv" / "providers.json").write_text(json.dumps(self.registry))
        with patch.object(IPTVProviderManager, "__init__", side_effect=AssertionError("manager init")):
            result = IPTVProviderManager.movie_availability(self.root, [550])
        self.assertEqual([p["name"] for p in result["providers"]], ["Lionz", "EgySat"])
        self.assertEqual([p["state"] for p in result["providers"]], ["ready", "unknown"])
        self.assertNotIn("password", json.dumps(result))

    def test_cold_availability_route_and_input_validation(self):
        app = Flask(__name__)
        register_iptv_routes(app, lambda: self.fail("manager initialized"),
                             data_root_provider=lambda: self.root)
        client = app.test_client()
        response = client.post("/api/iptv/movies/availability", json={"tmdb_ids": [550, 999]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["providers"][0]["matches"]["550"]["source_count"], 2)
        for body in ({}, {"tmdb_ids": [True]}, {"tmdb_ids": [0]}, {"tmdb_ids": ["550"]},
                     {"tmdb_ids": list(range(1, 102))}, {"tmdb_ids": [550], "url": "bad"}):
            self.assertEqual(client.post("/api/iptv/movies/availability", json=body).status_code, 400)
        sources = client.post("/api/iptv/movies/sources",
                              json={"provider_id": self.provider_id, "tmdb_id": 550})
        self.assertEqual(sources.status_code, 200)
        self.assertEqual(len(sources.json["items"]), 2)

    def test_absent_registry_is_empty_without_creation(self):
        empty = self.root / "absent"
        result = IPTVProviderManager.movie_availability(empty, [550])
        self.assertEqual(result["providers"], [])
        self.assertFalse(empty.exists())

    def test_lookup_performs_no_network_requests_or_catalog_writes(self):
        before = self.store.database_path.read_bytes()
        with patch("urllib.request.urlopen", side_effect=AssertionError("online lookup")):
            result = IPTVProviderManager.movie_availability(self.root, [550])
        self.assertEqual(result["providers"][0]["state"], "ready")
        self.assertEqual(self.store.database_path.read_bytes(), before)

    def test_corrupt_registry_does_not_become_a_negative(self):
        (self.root / "iptv" / "providers.json").write_text("broken")
        with self.assertRaises(RuntimeError):
            IPTVProviderManager.movie_availability(self.root, [550])

    def test_provider_rename_removal_and_unaccepted_identity_refresh_from_disk(self):
        self.registry['providers'][0]['name'] = 'Renamed provider'
        (self.root / 'iptv/providers.json').write_text(json.dumps(self.registry))
        self.assertEqual(IPTVProviderManager.movie_availability(self.root, [550])['providers'][0]['name'], 'Renamed provider')
        with self.store.connection() as connection:
            connection.execute("UPDATE source_matches SET state='ambiguous' WHERE tmdb_id=550")
        self.assertEqual(self.lookup()['matches'], {})
        self.registry['providers'] = []
        (self.root / 'iptv/providers.json').write_text(json.dumps(self.registry))
        self.assertEqual(IPTVProviderManager.movie_availability(self.root, [550])['providers'], [])
        with self.assertRaises(KeyError):
            IPTVProviderManager.movie_sources(self.root, self.provider_id, 550)

    def test_unknown_catalog_failures_never_report_absence(self):
        with self.store.connection() as connection:
            connection.execute("UPDATE movie_meta SET value='2' WHERE key='schema_version'")
        self.assertEqual(self.lookup()['state'], 'unknown')
        # v2 predates source_classifications; migration would be needed to decide Film eligibility.
        broken_id = 'd' * 32
        broken = self.provider_root.parent / broken_id
        broken.mkdir()
        (broken / 'movies.sqlite').write_bytes(b'corrupt sqlite fixture')
        self.assertEqual(IPTVMovieStore.lookup_availability(broken, broken_id, [550])['state'], 'unknown')
        with patch.object(IPTVMovieStore, '_read_catalog', side_effect=sqlite3.OperationalError('database is locked')):
            self.assertEqual(self.lookup()['state'], 'unknown')

    def test_batch_lookup_starts_from_requested_identity_index(self):
        statements = []
        reader = IPTVMovieStore._read_catalog

        @contextmanager
        def traced(*args):
            with reader(*args) as connection:
                connection.set_trace_callback(statements.append)
                yield connection

        with patch.object(IPTVMovieStore, "_read_catalog", traced):
            IPTVMovieStore.lookup_availability(self.provider_root, self.provider_id, [550] + list(range(2000, 2099)))
        query = next(sql for sql in statements if "COUNT(*) source_count" in sql)
        with closing(sqlite3.connect(self.store.database_path)) as connection:
            plan = list(connection.execute("EXPLAIN QUERY PLAN " + query))
        self.assertIn("SEARCH m USING INDEX idx_source_matches_tmdb", plan[0][3])

    def test_schema_three_read_to_raw_playback_keeps_movie_database_unchanged(self):
        # Build the pre-v4 read shape independently: no status projection or work-title columns.
        provider_id = 'c' * 32
        root = self.provider_root.parent / provider_id
        root.mkdir()
        database = root / 'movies.sqlite'
        text_columns = ('provider_title provider_rating provider_poster_url provider_backdrop_url '
                        'provider_plot provider_cast provider_director provider_genre provider_duration '
                        'container_extension playlist_id playlist_name quality_claim dubbed_claim subtitled_claim').split()
        with closing(sqlite3.connect(database)) as connection:
            connection.executescript('''
                CREATE TABLE movie_meta(key TEXT PRIMARY KEY,value TEXT);
                INSERT INTO movie_meta VALUES('schema_version','3'),('source_catalog_generation','1'),('movie_generation','1');
                CREATE TABLE source_matches(source_key TEXT PRIMARY KEY,tmdb_id INTEGER,state TEXT);
                CREATE INDEX idx_source_matches_tmdb ON source_matches(tmdb_id,state);
                CREATE TABLE source_classifications(source_key TEXT PRIMARY KEY,category TEXT);
            ''')
            connection.execute('CREATE TABLE movie_sources(source_key TEXT PRIMARY KEY,source_id TEXT,'
                               'provider_year INTEGER,available INTEGER,position INTEGER,last_watched REAL,watched_completed INTEGER,'
                               + ','.join(column + " TEXT DEFAULT ''" for column in text_columns) + ')')
            connection.execute("INSERT INTO movie_sources(source_key,source_id,provider_title,container_extension,available,position) VALUES('movie:7','7','Schema Three Movie','mkv',1,0)")
            connection.execute("INSERT INTO source_matches VALUES('movie:7',550,'matched-manual')")
            connection.execute("INSERT INTO source_classifications VALUES('movie:7','film')")
            connection.commit()
        self.registry['providers'].append({'provider_id': provider_id, 'name': 'Schema Three'})
        (self.root / 'iptv/providers.json').write_text(json.dumps(self.registry))
        manager = IPTVProviderManager(self.root, ffmpeg_path=sys.executable, migrate_legacy=False)
        self.addCleanup(manager.close)
        raw = manager.service(provider_id)
        raw.save_config('https://provider.example', 'fixture-user', 'fixture-password')
        raw.store.replace_catalog({'movie': {'categories': [], 'items': [{'stream_id': '7', 'name': 'Schema Three Movie', 'container_extension': 'mkv'}]}})
        app = Flask(__name__)
        register_iptv_routes(app, lambda: manager, data_root_provider=lambda: self.root)
        client = app.test_client()
        before = database.read_bytes()
        with patch.object(manager, 'movie_service', side_effect=AssertionError('movie initialization')):
            availability = client.post('/api/iptv/movies/availability', json={'tmdb_ids': [550]}).json
            self.assertEqual(availability['providers'][1]['matches']['550']['source_count'], 1)
            response = client.post('/api/iptv/movies/sources', json={'provider_id': provider_id, 'tmdb_id': 550})
            self.assertEqual(response.status_code, 200)
            source = response.json['items'][0]

            def ffmpeg(command, **kwargs):
                Path(command[-1]).write_text('#EXTM3U\n')
                return Mock(stderr=io.BytesIO(), poll=Mock(return_value=None))

            with patch('services.iptv_service.subprocess.Popen', side_effect=ffmpeg), patch.object(raw, '_drain_process_stderr'):
                playback = client.post(f'/api/iptv/providers/{provider_id}/playback', json={
                    'kind': 'movie', 'item_id': source['item_id'], 'extension': source['container_extension'], 'title': source['name']})
            self.assertEqual(playback.status_code, 200, playback.json)
            token = playback.json['token']
            self.assertEqual(raw._sessions[token]['item_id'], '7')
            self.assertTrue(raw._sessions[token]['source_url'].endswith('/7.mkv'))
            self.assertEqual(client.delete(f'/api/iptv/providers/{provider_id}/playback/{token}').status_code, 200)
        self.assertEqual(database.read_bytes(), before)
        self.assertFalse((root / 'migration-backups').exists())
