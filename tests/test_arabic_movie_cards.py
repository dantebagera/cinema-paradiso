import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app
from services.catalog_store import CatalogStore
from services.curation_store import normalize_curated_movie
from services.playback_history import PlaybackHistoryService, PlaybackHistoryStore
from services.player_config import PlayerConfig
from tests.test_canonical_catalog import _file


class ArabicMovieCardsTest(unittest.TestCase):
    def test_continue_watching_carries_saved_original_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            media = Path(directory) / 'movie.mkv'
            media.write_bytes(b'fixture')
            key = str(media).lower()
            store = CatalogStore(Path(directory) / 'catalog.sqlite')
            store.import_documents({
                'app_metadata/files.json': {'files': {key: _file(str(media), '12345', 'Accepted English', '2014')}},
                'app_metadata/tmdb_metadata.json': {'movies': {'12345': {
                    'tmdb_id': '12345', 'title': 'English', 'original_title': 'الفيل الأزرق', 'original_language': 'ar',
                }}},
            }, {})
            history = PlaybackHistoryStore(store)
            row = history.begin_session(key, 'tmdb:12345')
            history.save(key, row['revision'], position_ms=120000, duration_ms=600000, completion_threshold=0.9)
            service = PlaybackHistoryService(history, PlayerConfig({'resume_enabled': True}), lambda: None)
            movie = service.continue_watching()[0]
            self.assertEqual(movie['title'], 'Accepted English')
            self.assertEqual(movie['original_title'], 'الفيل الأزرق')
            self.assertEqual(movie['original_language'], 'ar')

    def test_ai_movie_projection_keeps_original_fields(self):
        movie = app._ai_control_tmdb_movie_payload({'id': 1, 'title': 'English', 'original_title': 'عربي', 'original_language': 'ar'})
        self.assertEqual(movie['original_title'], 'عربي')
        self.assertEqual(movie['original_language'], 'ar')

    def test_provider_search_and_discover_keep_original_fields(self):
        raw = {'id': 12345, 'title': 'English title', 'original_title': 'الفيل الأزرق',
               'original_language': 'ar', 'release_date': '2014-01-01', 'genre_ids': []}
        window = {'results': [raw], 'page': 1, 'total_pages': 1, 'total_results': 1}
        with patch.object(app, '_tmdb_key', 'fixture'), patch.object(app, '_ensure_tmdb_genres'), \
                patch.object(app, '_tmdb_fetch_page_window', return_value=window), \
                patch.object(app, '_tmdb_discover_window', return_value=window):
            for route in ['/api/tmdb/search?q=Elephant', '/api/tmdb/discover']:
                response = app.app.test_client().get(route)
                self.assertEqual(response.status_code, 200, response.json)
                movie = response.json['results'][0]
                self.assertEqual(movie['original_title'], raw['original_title'])
                self.assertEqual(movie['original_language'], 'ar')
                self.assertEqual(movie['title'], 'English title')

    def test_saved_library_projection_keeps_original_metadata_without_changing_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            store = CatalogStore(Path(directory) / 'catalog.sqlite')
            path = 'e:/movies/arabic.mkv'
            store.import_documents({
                'app_metadata/files.json': {'files': {path: _file(path, '12345', 'Accepted English', '2014')}},
                'app_metadata/tmdb_metadata.json': {'movies': {'12345': {
                    'tmdb_id': '12345', 'title': 'Provider English', 'original_title': 'الفيل الأزرق',
                    'original_language': 'ar', 'language': 'Arabic', 'year': '2014',
                }}},
            }, backup_manifest={})
            candidate = store.owned_movie_candidate(path_key=path)
            canonical = candidate['relational_canonical']
            self.assertEqual(canonical['original_title'], 'الفيل الأزرق')
            self.assertEqual(canonical['original_language'], 'ar')
            self.assertEqual(canonical['title'], 'Accepted English')

    def test_plex_selected_artwork_keeps_original_tmdb_title_for_display(self):
        with tempfile.TemporaryDirectory() as directory:
            store = CatalogStore(Path(directory) / 'catalog.sqlite')
            path = 'e:/movies/arabic.mkv'
            file = {**_file(path, '12345', 'Accepted English', '2014'), 'display_provider': 'plex'}
            store.import_documents({
                'app_metadata/files.json': {'files': {path: file}},
                'app_metadata/tmdb_metadata.json': {'movies': {'12345': {
                    'tmdb_id': '12345', 'title': 'Provider English', 'original_title': 'الفيل الأزرق',
                    'original_language': 'ar', 'year': '2014',
                }}},
                'app_metadata/plex_metadata.json': {'files': {path: {'plex_title': 'Plex English', 'plex_year': '2014', 'plex_poster': '/plex.jpg', 'tmdb_id': '12345'}}},
            }, {})
            canonical = store.owned_movie_candidate(path_key=path)['relational_canonical']
            self.assertEqual(canonical['original_title'], 'الفيل الأزرق')
            self.assertEqual(canonical['original_language'], 'ar')
            self.assertEqual(canonical['poster_url'], '/plex.jpg')
            self.assertEqual(canonical['selected_provider'], 'plex')

    def test_curated_entries_preserve_original_names(self):
        result = normalize_curated_movie({'title': 'English', 'original_title': 'عربي', 'original_language': 'ar'})
        self.assertEqual(result['original_title'], 'عربي')
        self.assertEqual(result['original_language'], 'ar')
