import os
import re
import stat
import shutil
import time
import urllib.request
import urllib.parse
import json as _json
from pathlib import Path
from flask import Flask, jsonify, request, make_response, send_from_directory
from send2trash import send2trash

app = Flask(__name__)
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Config file stored next to app.py
_CONFIG_FILE = os.path.join(_BASE_DIR, 'config.json')

def _load_config():
    if os.path.exists(_CONFIG_FILE):
        try:
            with open(_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return _json.load(f)
        except Exception:
            pass
    return {}

def _save_config(data):
    try:
        with open(_CONFIG_FILE, 'w', encoding='utf-8') as f:
            _json.dump(data, f, indent=2)
    except Exception:
        pass

_cfg = _load_config()
def _coerce_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {'1', 'true', 'yes', 'on'}:
        return True
    if text in {'0', 'false', 'no', 'off'}:
        return False
    return default

def _coerce_movie_dirs(config):
    raw_dirs = config.get('movies_dirs')
    if isinstance(raw_dirs, list):
        dirs = [str(path or '').strip() for path in raw_dirs if str(path or '').strip()]
    else:
        dirs = []
    legacy_dir = str(config.get('movies_dir', r"E:\Movies") or '').strip()
    if legacy_dir and legacy_dir not in dirs:
        dirs.insert(0, legacy_dir)
    seen = set()
    result = []
    for path in dirs:
        norm = os.path.normcase(os.path.normpath(path))
        if norm not in seen:
            seen.add(norm)
            result.append(path)
    return result or [r"E:\Movies"]

_movies_dirs    = _coerce_movie_dirs(_cfg)
_movies_dir     = _movies_dirs[0]
_prowlarr_url   = _cfg.get('prowlarr_url', '')
_prowlarr_key   = _cfg.get('prowlarr_key', '')
_tmdb_key       = _cfg.get('tmdb_key', '')
_tmdb_include_adult = _coerce_bool(_cfg.get('tmdb_include_adult'), False)
_library_show_adult = _coerce_bool(_cfg.get('library_show_adult'), True)
_plex_url       = _cfg.get('plex_url', 'http://localhost:32400')
_plex_token     = _cfg.get('plex_token', '')
_ollama_url     = _cfg.get('ollama_url', 'http://localhost:11434')
_ollama_model   = _cfg.get('ollama_model', 'gemma4:31b-cloud')
_user_data_dir  = _cfg.get('user_data_dir', os.path.join(_BASE_DIR, 'data'))
_tmdb_cache_dir = _cfg.get('tmdb_cache_dir', os.path.join(_BASE_DIR, 'cache'))
_plex_cache     = {}   # _norm(file_path) -> {plex_title, plex_year, plex_genres}
_plex_unmatched = {}   # _norm(path) -> {rating_key, plex_title}  (Plex has file but no metadata)
_plex_matched_by_fname   = {}  # filename.lower() -> matched entry   (path-mismatch fallback)
_plex_unmatched_by_fname = {}  # filename.lower() -> unmatched entry (path-mismatch fallback)

def _norm(path):
    """Normalise a file path for use as a cache key.
    Uses normcase so Windows drive-letter case differences don't cause misses.
    e.g. Plex returns 'e:\\...' while os.walk gives 'E:\\...'
    """
    return os.path.normcase(os.path.normpath(path))
_plex_section_ids = [] # movie section keys — used for triggering rescans
_metadata_cache  = {}  # "{title}_{year}" -> {poster_url, genres, plot, tmdb_rating} — memory-only
_tmdb_genres     = {}  # genre_id -> genre_name, lazy-loaded once from TMDB
_TMDB_CACHE_DIR = _tmdb_cache_dir
_TMDB_LIBRARY_CACHE_FILE = os.path.join(_TMDB_CACHE_DIR, 'tmdb_library_cache.json')
_TMDB_COLLECTION_CACHE_FILE = os.path.join(_TMDB_CACHE_DIR, 'tmdb_collection_cache.json')


def _tmdb_image_url(path, size='w185'):
    return f"https://image.tmdb.org/t/p/{size}{path}" if path else ''


def _load_tmdb_library_cache():
    try:
        with open(_TMDB_LIBRARY_CACHE_FILE, 'r', encoding='utf-8') as f:
            data = _json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_tmdb_library_cache(data):
    try:
        os.makedirs(_TMDB_CACHE_DIR, exist_ok=True)
        with open(_TMDB_LIBRARY_CACHE_FILE, 'w', encoding='utf-8') as f:
            _json.dump(data, f, indent=2)
    except Exception:
        pass


def _load_tmdb_collection_cache():
    try:
        with open(_TMDB_COLLECTION_CACHE_FILE, 'r', encoding='utf-8') as f:
            data = _json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_tmdb_collection_cache(data):
    try:
        os.makedirs(_TMDB_CACHE_DIR, exist_ok=True)
        with open(_TMDB_COLLECTION_CACHE_FILE, 'w', encoding='utf-8') as f:
            _json.dump(data, f, indent=2)
    except Exception:
        pass


_tmdb_library_cache = _load_tmdb_library_cache()
_tmdb_collection_cache = _load_tmdb_collection_cache()


def _movie_identity_key(movie):
    tmdb_id = str(movie.get('tmdb_id', '') or '').strip()
    if tmdb_id:
        return f"tmdb:{tmdb_id}"
    imdb_id = str(movie.get('imdb_id', '') or '').strip()
    if imdb_id:
        return f"imdb:{imdb_id.lower()}"
    path = str(movie.get('path', '') or '').strip()
    if path:
        return f"path:{_norm(path)}"
    title = re.sub(r'\s+', ' ', str(movie.get('title', '') or '').lower()).strip()
    year = str(movie.get('year', '') or '').strip()
    return f"title:{title}|{year}"


def _normalize_curated_movie(movie):
    return {
        'tmdb_id': str(movie.get('tmdb_id', '') or ''),
        'imdb_id': str(movie.get('imdb_id', '') or ''),
        'title': str(movie.get('title', '') or ''),
        'year': str(movie.get('year', '') or ''),
        'path': str(movie.get('path', '') or ''),
        'poster_url': str(movie.get('poster_url', '') or ''),
    }


class UserCurationStore:
    def __init__(self, base_dir):
        self.base_dir = Path(base_dir)
        self.collections_file = self.base_dir / 'user_collections.json'
        self.lists_file = self.base_dir / 'user_lists.json'
        self.followed_file = self.base_dir / 'followed_releases.json'

    def _read_json(self, path, fallback):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = _json.load(f)
            return data if isinstance(data, type(fallback)) else fallback
        except Exception:
            return fallback

    def _write_json(self, path, data):
        self.base_dir.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            _json.dump(data, f, indent=2)

    def _collections(self):
        data = self._read_json(self.collections_file, {'overrides': {}})
        data.setdefault('overrides', {})
        return data

    def _save_collections(self, data):
        self._write_json(self.collections_file, data)

    def _lists(self):
        data = self._read_json(self.lists_file, {'lists': []})
        data.setdefault('lists', [])
        return data

    def _save_lists(self, data):
        self._write_json(self.lists_file, data)

    def _followed(self):
        data = self._read_json(self.followed_file, {'movies': []})
        data.setdefault('movies', [])
        return data

    def _save_followed(self, data):
        self._write_json(self.followed_file, data)

    def effective_collection(self, tmdb_collection):
        collection_id = str(tmdb_collection.get('id', '') or '')
        overrides = self._collections().get('overrides', {})
        override = overrides.get(collection_id)
        if override:
            return {
                **tmdb_collection,
                **override,
                'id': collection_id,
                'source': 'User',
                'is_edited': True,
            }
        return {
            **tmdb_collection,
            'source': 'TMDB',
            'is_edited': False,
        }

    def save_collection_override(self, collection_id, original_collection, parts):
        collection_id = str(collection_id)
        data = self._collections()
        override = {
            'id': collection_id,
            'name': original_collection.get('name', ''),
            'parts': [_normalize_curated_movie(movie) for movie in parts],
            'updated_at': time.time(),
        }
        data['overrides'][collection_id] = override
        self._save_collections(data)
        return {**override, 'source': 'User', 'is_edited': True}

    def reset_collection(self, collection_id):
        data = self._collections()
        existed = str(collection_id) in data['overrides']
        data['overrides'].pop(str(collection_id), None)
        self._save_collections(data)
        return existed

    def list_all(self):
        return self._lists()['lists']

    def create_list(self, name):
        data = self._lists()
        clean_name = re.sub(r'\s+', ' ', str(name or '').strip())
        if not clean_name:
            raise ValueError('List name is required')
        list_id = re.sub(r'[^a-z0-9]+', '-', clean_name.lower()).strip('-') or f"list-{int(time.time())}"
        existing_ids = {item.get('id') for item in data['lists']}
        base_id = list_id
        suffix = 2
        while list_id in existing_ids:
            list_id = f"{base_id}-{suffix}"
            suffix += 1
        created = {'id': list_id, 'name': clean_name, 'movies': [], 'created_at': time.time(), 'updated_at': time.time()}
        data['lists'].append(created)
        self._save_lists(data)
        return created

    def rename_list(self, list_id, name):
        data = self._lists()
        target = self._find_list(data, list_id)
        if target is None:
            raise KeyError('List not found')
        clean_name = re.sub(r'\s+', ' ', str(name or '').strip())
        if not clean_name:
            raise ValueError('List name is required')
        target['name'] = clean_name
        target['updated_at'] = time.time()
        self._save_lists(data)
        return target

    def delete_list(self, list_id):
        data = self._lists()
        before = len(data['lists'])
        data['lists'] = [item for item in data['lists'] if item.get('id') != list_id]
        self._save_lists(data)
        return len(data['lists']) != before

    def _find_list(self, data, list_id):
        for item in data['lists']:
            if item.get('id') == list_id:
                return item
        return None

    def add_movie_to_list(self, list_id, movie):
        data = self._lists()
        target = self._find_list(data, list_id)
        if target is None:
            raise KeyError('List not found')
        normalized = _normalize_curated_movie(movie)
        key = _movie_identity_key(normalized)
        movies = target.setdefault('movies', [])
        if all(_movie_identity_key(existing) != key for existing in movies):
            movies.append(normalized)
        target['updated_at'] = time.time()
        self._save_lists(data)
        return target

    def remove_movie_from_list(self, list_id, movie):
        data = self._lists()
        target = self._find_list(data, list_id)
        if target is None:
            raise KeyError('List not found')
        key = _movie_identity_key(_normalize_curated_movie(movie))
        target['movies'] = [existing for existing in target.get('movies', []) if _movie_identity_key(existing) != key]
        target['updated_at'] = time.time()
        self._save_lists(data)
        return target

    def lists_for_movie(self, movie):
        key = _movie_identity_key(_normalize_curated_movie(movie))
        result = []
        for item in self._lists()['lists']:
            if any(_movie_identity_key(existing) == key for existing in item.get('movies', [])):
                result.append({'id': item.get('id'), 'name': item.get('name')})
        return result

    def followed_all(self):
        return self._followed()['movies']

    def follow_movie(self, movie):
        data = self._followed()
        normalized = _normalize_curated_movie(movie)
        key = _movie_identity_key(normalized)
        now = time.time()
        existing = next((item for item in data['movies'] if _movie_identity_key(item) == key), None)
        if existing:
            existing.update({k: v for k, v in normalized.items() if v})
            existing['updated_at'] = now
            self._save_followed(data)
            return existing
        created = {
            **normalized,
            'status': 'watching',
            'followed_at': now,
            'updated_at': now,
            'last_checked': 0,
            'best_release': {},
        }
        data['movies'].insert(0, created)
        self._save_followed(data)
        return created

    def unfollow_movie(self, movie):
        data = self._followed()
        key = _movie_identity_key(_normalize_curated_movie(movie))
        before = len(data['movies'])
        data['movies'] = [item for item in data['movies'] if _movie_identity_key(item) != key]
        self._save_followed(data)
        return len(data['movies']) != before

    def save_followed_all(self, movies):
        data = {'movies': movies}
        self._save_followed(data)
        return movies


def _curation_store():
    return UserCurationStore(Path(_user_data_dir))


def _fetch_enabled_prowlarr_indexers():
    if not _prowlarr_url or not _prowlarr_key:
        raise RuntimeError('Prowlarr not configured')
    idx_req = urllib.request.Request(
        f"{_prowlarr_url}/api/v1/indexer",
        headers={'X-Api-Key': _prowlarr_key, 'Accept': 'application/json'}
    )
    with urllib.request.urlopen(idx_req, timeout=8) as idx_resp:
        indexers = _json.loads(idx_resp.read().decode())
    enabled = []
    for ix in indexers:
        if ix.get('enable', True):
            enabled.append({
                'id': str(ix.get('id', '')),
                'name': ix.get('name', ''),
            })
    return [ix for ix in enabled if ix['id']]


class AppMetadataStore:
    def __init__(self, base_dir):
        self.base_dir = Path(base_dir) / 'app_metadata'
        self.files_file = self.base_dir / 'files.json'
        self.tmdb_metadata_file = self.base_dir / 'tmdb_metadata.json'
        self.plex_metadata_file = self.base_dir / 'plex_metadata.json'
        self.manual_matches_file = self.base_dir / 'manual_matches.json'
        self.conflicts_file = self.base_dir / 'conflicts.json'

    def _read_json(self, path, fallback):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = _json.load(f)
            return data if isinstance(data, type(fallback)) else fallback
        except Exception:
            return fallback

    def _write_json(self, path, data):
        self.base_dir.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            _json.dump(data, f, indent=2)

    def _key(self, path):
        return _norm(str(path or ''))

    def record_file(self, path, facts):
        data = self._read_json(self.files_file, {'files': {}})
        data.setdefault('files', {})
        key = self._key(path)
        data['files'][key] = {**(facts or {}), 'path': str(path or ''), 'updated_at': time.time()}
        self._write_json(self.files_file, data)
        return data['files'][key]

    def save_tmdb_metadata(self, metadata):
        tmdb_id = str((metadata or {}).get('tmdb_id', '') or '').strip()
        if not tmdb_id:
            return {}
        data = self._read_json(self.tmdb_metadata_file, {'movies': {}})
        data.setdefault('movies', {})
        current = data['movies'].get(tmdb_id, {})
        saved = {**current, **metadata, 'tmdb_id': tmdb_id, 'updated_at': time.time()}
        data['movies'][tmdb_id] = saved
        self._write_json(self.tmdb_metadata_file, data)
        return saved

    def get_tmdb_metadata(self, tmdb_id):
        data = self._read_json(self.tmdb_metadata_file, {'movies': {}})
        return data.get('movies', {}).get(str(tmdb_id or ''), {})

    def snapshot(self):
        return {
            'files': self._read_json(self.files_file, {'files': {}}).get('files', {}),
            'tmdb_movies': self._read_json(self.tmdb_metadata_file, {'movies': {}}).get('movies', {}),
            'plex_files': self._read_json(self.plex_metadata_file, {'files': {}}).get('files', {}),
            'manual_matches': self._read_json(self.manual_matches_file, {'matches': {}}).get('matches', {}),
            'conflicts': self._read_json(self.conflicts_file, {'conflicts': {}}).get('conflicts', {}),
        }

    def get_tmdb_metadata_from_snapshot(self, tmdb_id, snapshot):
        return (snapshot or {}).get('tmdb_movies', {}).get(str(tmdb_id or ''), {})

    def get_manual_match_from_snapshot(self, path, snapshot):
        return (snapshot or {}).get('manual_matches', {}).get(self._key(path), {})

    def save_plex_metadata(self, path, metadata):
        data = self._read_json(self.plex_metadata_file, {'files': {}})
        data.setdefault('files', {})
        key = self._key(path)
        data['files'][key] = {**(metadata or {}), 'path': str(path or ''), 'updated_at': time.time()}
        self._write_json(self.plex_metadata_file, data)
        return data['files'][key]

    def get_plex_metadata(self, path):
        data = self._read_json(self.plex_metadata_file, {'files': {}})
        return data.get('files', {}).get(self._key(path), {})

    def apply_tmdb_match(self, path, tmdb_metadata):
        metadata = self.save_tmdb_metadata(_normalize_tmdb_metadata(tmdb_metadata))
        tmdb_id = str(metadata.get('tmdb_id', '') or '').strip()
        if not tmdb_id:
            raise ValueError('tmdb_id is required')
        data = self._read_json(self.manual_matches_file, {'matches': {}})
        data.setdefault('matches', {})
        key = self._key(path)
        match = {
            'path': str(path or ''),
            'provider': 'tmdb',
            'source': 'manual_tmdb',
            'tmdb_id': tmdb_id,
            'title': metadata.get('title', ''),
            'year': str(metadata.get('year', '') or ''),
            'imdb_id': str(metadata.get('imdb_id', '') or ''),
            'poster_url': metadata.get('poster_url', ''),
            'accepted': True,
            'updated_at': time.time(),
        }
        data['matches'][key] = match
        self._write_json(self.manual_matches_file, data)
        return match

    def apply_plex_match(self, path, plex_metadata):
        saved = self.save_plex_metadata(path, plex_metadata)
        data = self._read_json(self.manual_matches_file, {'matches': {}})
        data.setdefault('matches', {})
        key = self._key(path)
        match = {
            'path': str(path or ''),
            'provider': 'plex',
            'source': 'manual_plex',
            'rating_key': str((plex_metadata or {}).get('rating_key', '') or ''),
            'accepted': True,
            'updated_at': time.time(),
        }
        data['matches'][key] = match
        self._write_json(self.manual_matches_file, data)
        return {**match, **saved}

    def get_manual_match(self, path):
        data = self._read_json(self.manual_matches_file, {'matches': {}})
        return data.get('matches', {}).get(self._key(path), {})

    def record_conflict(self, path, conflict):
        data = self._read_json(self.conflicts_file, {'conflicts': {}})
        data.setdefault('conflicts', {})
        key = self._key(path)
        data['conflicts'][key] = {**(conflict or {}), 'path': str(path or ''), 'updated_at': time.time()}
        self._write_json(self.conflicts_file, data)
        return data['conflicts'][key]


def _metadata_store():
    return AppMetadataStore(Path(_user_data_dir))


def _year_from_movie(movie, fallback=''):
    release = str((movie or {}).get('release_date', '') or '')
    year = str((movie or {}).get('year', '') or '')
    return release[:4] if release else year or str(fallback or '')


def _normalize_tmdb_genres(raw):
    if not raw:
        return []
    genres = []
    for item in raw:
        if isinstance(item, dict):
            name = item.get('name')
            if name:
                genres.append(name)
        elif isinstance(item, int) and item in _tmdb_genres:
            genres.append(_tmdb_genres[item])
        elif isinstance(item, str):
            genres.append(item)
    return genres[:5]


def _normalize_tmdb_metadata(movie):
    movie = movie or {}
    tmdb_id = str(movie.get('tmdb_id', '') or movie.get('id', '') or '').strip()
    poster = movie.get('poster_url') or _tmdb_image_url(movie.get('poster_path'), 'w342')
    backdrop = movie.get('backdrop_url') or _tmdb_image_url(movie.get('backdrop_path'), 'w780')
    vote = movie.get('tmdb_rating', '')
    if not vote:
        raw_vote = movie.get('vote_average', 0)
        vote = f"{raw_vote:.1f}" if isinstance(raw_vote, (int, float)) and raw_vote else ''
    vote_count = movie.get('tmdb_vote_count', movie.get('vote_count', 0) or 0)
    try:
        vote_count = int(vote_count or 0)
    except Exception:
        vote_count = 0
    lang = movie.get('original_language', '')
    country = movie.get('country', '')
    countries = movie.get('origin_country') or movie.get('production_countries') or []
    if not country and countries:
        first = countries[0]
        country = first.get('iso_3166_1', '') if isinstance(first, dict) else str(first or '')
    if not country and lang:
        country = _LANG_COUNTRY.get(lang, '')
    return {
        'tmdb_id': tmdb_id,
        'imdb_id': str(movie.get('imdb_id', '') or ''),
        'title': movie.get('title') or movie.get('name') or '',
        'year': _year_from_movie(movie),
        'poster_url': poster,
        'backdrop_url': backdrop,
        'genres': _normalize_tmdb_genres(movie.get('genres') or movie.get('genre_ids') or []),
        'tmdb_rating': str(vote or ''),
        'tmdb_vote_count': vote_count,
        'plot': movie.get('plot') or movie.get('overview', ''),
        'language': movie.get('language') or _LANG_NAMES.get(lang, lang.upper() if lang else ''),
        'country': country,
        'country_flag': movie.get('country_flag') or _country_flag(country),
        'release_date': movie.get('release_date', '') or '',
        'runtime': movie.get('runtime'),
        'tagline': movie.get('tagline', ''),
        'directors': movie.get('directors', []),
        'director': movie.get('director', {}),
        'cast': movie.get('cast', []),
        'collection': movie.get('collection', {}),
        'trailer_url': movie.get('trailer_url', ''),
        'match_source': movie.get('match_source', ''),
        'adult': bool(movie.get('adult', False)),
    }


def _same_public_identity(left_title, left_year, right_title, right_year):
    left = _norm_movie_title(left_title)
    right = _norm_movie_title(right_title)
    if not left or not right or left != right:
        return False
    left_year = str(left_year or '').strip()
    right_year = str(right_year or '').strip()
    return not left_year or not right_year or left_year == right_year


def _tmdb_is_auto_accepted(file_facts, tmdb_data):
    if not tmdb_data:
        return False
    if tmdb_data.get('match_source') == 'plex_tmdb_id':
        return True
    return _same_public_identity(
        file_facts.get('parsed_title', ''),
        file_facts.get('parsed_year', ''),
        tmdb_data.get('title', ''),
        tmdb_data.get('year', ''),
    )


def _metadata_is_pending(file_facts):
    try:
        added_time = float((file_facts or {}).get('added_time') or 0)
    except Exception:
        added_time = 0
    if not added_time:
        return False
    return max(0, time.time() - added_time) < _METADATA_PENDING_SECONDS


def _plex_to_canonical(plex_data, source='plex'):
    return {
        'accepted': True,
        'status': 'accepted',
        'source': source,
        'title': plex_data.get('plex_title', ''),
        'year': str(plex_data.get('plex_year', '') or ''),
        'tmdb_id': str(plex_data.get('tmdb_id', '') or ''),
        'imdb_id': str(plex_data.get('imdb_id', '') or ''),
        'plex_guid': str(plex_data.get('plex_guid', '') or ''),
        'poster_url': plex_data.get('plex_poster', ''),
        'genres': plex_data.get('plex_genres', []),
        'plot': plex_data.get('plex_summary', ''),
        'summary': plex_data.get('plex_summary', ''),
        'rating': plex_data.get('plex_rating', ''),
        'plex_rating': plex_data.get('plex_rating', ''),
        'tmdb_rating': '',
        'tmdb_vote_count': 0,
        'language': plex_data.get('plex_language', ''),
        'country': plex_data.get('plex_country', ''),
        'country_flag': plex_data.get('plex_country_flag', ''),
        'directors': plex_data.get('plex_directors', []),
        'director': (plex_data.get('plex_directors') or [{}])[0] if plex_data.get('plex_directors') else {},
        'cast': plex_data.get('plex_cast', []),
    }


def _tmdb_to_canonical(tmdb_data, source='tmdb'):
    metadata = _normalize_tmdb_metadata(tmdb_data)
    return {
        **metadata,
        'accepted': True,
        'status': 'accepted',
        'source': source,
        'summary': metadata.get('plot', ''),
        'rating': metadata.get('tmdb_rating', ''),
    }


def _build_canonical_metadata(file_facts, plex_data=None, tmdb_data=None, manual_match=None):
    file_facts = file_facts or {}
    plex_data = plex_data or {}
    tmdb_data = tmdb_data or {}
    manual_match = manual_match or {}
    has_plex = bool(plex_data.get('plex_title'))
    has_tmdb = bool(tmdb_data.get('tmdb_id') and tmdb_data.get('title'))

    if manual_match.get('provider') == 'tmdb' and has_tmdb:
        return _tmdb_to_canonical(tmdb_data, 'manual_tmdb')

    if manual_match.get('provider') == 'plex' and has_plex and not has_tmdb:
        return _plex_to_canonical(plex_data, 'manual_plex')

    if has_plex and has_tmdb and tmdb_data.get('match_source') != 'plex_tmdb_id':
        if not _same_public_identity(
            plex_data.get('plex_title', ''),
            plex_data.get('plex_year', ''),
            tmdb_data.get('title', ''),
            tmdb_data.get('year', ''),
        ):
            return {
                'accepted': False,
                'status': 'conflict',
                'source': '',
                'title': '',
                'year': '',
                'tmdb_id': str(tmdb_data.get('tmdb_id', '') or ''),
                'plex_title': plex_data.get('plex_title', ''),
                'plex_year': str(plex_data.get('plex_year', '') or ''),
                'tmdb_title': tmdb_data.get('title', ''),
                'tmdb_year': str(tmdb_data.get('year', '') or ''),
            }

    if has_tmdb and _tmdb_is_auto_accepted(file_facts, tmdb_data):
        return _tmdb_to_canonical(tmdb_data, 'tmdb')

    if has_tmdb:
        return {
            **_tmdb_to_canonical(tmdb_data, 'tmdb_candidate'),
            'accepted': False,
            'status': 'needs_review',
            'source': '',
        }

    if has_plex:
        return _plex_to_canonical(plex_data, 'plex')

    status = 'pending' if _metadata_is_pending(file_facts) else 'unmatched'
    return {
        'accepted': False,
        'status': status,
        'source': '',
        'title': '',
        'year': '',
        'tmdb_id': '',
        'imdb_id': '',
        'poster_url': '',
        'genres': [],
        'plot': '',
        'summary': '',
        'rating': '',
        'tmdb_rating': '',
        'tmdb_vote_count': 0,
    }
_TV_RE = re.compile(
    r'(?:s\d{1,2}e\d{1,2}|\d{1,2}x\d{2}|season[\s._-]*\d|episode[\s._-]*\d'
    r'|\bep[\s._-]*\d{1,3}\b|complete[\s._-]+series|\bcomplete[\s._-]+season)',
    re.IGNORECASE
)
_MOVIE_FOLDER_RE = re.compile(r'\b(19|20)\d{2}\b')  # folder name looks like a movie title
_LANG_NAMES = {
    'en':'English','fr':'French','es':'Spanish','de':'German','it':'Italian',
    'pt':'Portuguese','ru':'Russian','ja':'Japanese','ko':'Korean','zh':'Chinese',
    'ar':'Arabic','hi':'Hindi','tr':'Turkish','nl':'Dutch','sv':'Swedish',
    'pl':'Polish','da':'Danish','fi':'Finnish','no':'Norwegian','th':'Thai',
    'vi':'Vietnamese','id':'Indonesian','cs':'Czech','hu':'Hungarian','ro':'Romanian',
}
_LANG_COUNTRY = {
    'en':'US','fr':'FR','es':'ES','de':'DE','it':'IT','pt':'PT','ru':'RU',
    'ja':'JP','ko':'KR','zh':'CN','ar':'SA','hi':'IN','tr':'TR','nl':'NL',
    'sv':'SE','pl':'PL','da':'DK','fi':'FI','no':'NO','th':'TH','vi':'VN',
    'id':'ID','cs':'CZ','hu':'HU','ro':'RO',
}
def _country_flag(code):
    if not code or len(code) != 2: return ''
    return chr(ord(code[0].upper())+127397) + chr(ord(code[1].upper())+127397)

_res_cache = {}  # (abspath, mtime) -> resolution_str  — resolution probe cache
_res_cache_reprobe = set()  # legacy cache entries that need one width-aware probe
_RES_CACHE_FILE  = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'res_cache.json')
_RES_CACHE_VERSION = 2
_library_status  = ''  # live status string polled by the browser during a scan
_plex_cache_time = 0.0
_PLEX_TTL        = 300  # seconds before auto-refresh
_library_cache   = {}   # keys: items, plex_enabled, plex_cached, time
_LIBRARY_TTL     = 300  # seconds — same as Plex TTL
_METADATA_PENDING_SECONDS = 10 * 60

def _all_config():
    return {
        'movies_dir': _movies_dir,
        'movies_dirs': _movies_dirs,
        'prowlarr_url': _prowlarr_url,
        'prowlarr_key': _prowlarr_key,
        'plex_url': _plex_url,
        'plex_token': _plex_token,
        'tmdb_key': _tmdb_key,
        'tmdb_include_adult': _tmdb_include_adult,
        'library_show_adult': _library_show_adult,
        'ollama_url': _ollama_url,
        'ollama_model': _ollama_model,
        'user_data_dir': _user_data_dir,
        'tmdb_cache_dir': _tmdb_cache_dir,
    }

VIDEO_EXTENSIONS = {'.mkv', '.mp4', '.avi', '.m4v', '.mov', '.wmv', '.flv', '.ts', '.m2ts', '.iso'}

try:
    from pymediainfo import MediaInfo as _MediaInfo
    _MEDIAINFO_AVAILABLE = True
except ImportError:
    _MediaInfo = None
    _MEDIAINFO_AVAILABLE = False


def get_movies_dir():
    return _movies_dir


def get_movies_dirs():
    return list(_movies_dirs)


def _metadata_cache_revision():
    store = _metadata_store()
    revision = []
    for path in (
        store.files_file,
        store.tmdb_metadata_file,
        store.plex_metadata_file,
        store.manual_matches_file,
        store.conflicts_file,
    ):
        try:
            stat = path.stat()
            revision.append((path.name, stat.st_mtime_ns, stat.st_size))
        except OSError:
            revision.append((path.name, 0, 0))
    return tuple(revision)


def _library_cache_key():
    return (
        tuple(_norm(path) for path in get_movies_dirs()),
        _metadata_cache_revision(),
    )


def _iter_movie_roots():
    for root in get_movies_dirs():
        if root and os.path.isdir(root):
            yield root


def _iter_video_files():
    for movies_dir in _iter_movie_roots():
        for root, _, files in os.walk(movies_dir):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in VIDEO_EXTENSIONS:
                    yield movies_dir, root, file, os.path.join(root, file)


def _walk_movie_dirs():
    for movies_dir in _iter_movie_roots():
        for root, dirs, files in os.walk(movies_dir):
            yield movies_dir, root, dirs, files


def _path_library_root(path):
    abs_path = os.path.abspath(path)
    for root in _iter_movie_roots():
        abs_root = os.path.abspath(root)
        if abs_path == abs_root or abs_path.startswith(abs_root + os.sep):
            return abs_root
    return ''


def _path_inside_library(path):
    return bool(_path_library_root(path))


def _classify_dimensions(width, height):
    """Classify actual video dimensions, allowing normal cinematic crop."""
    w = int(width or 0)
    h = int(height or 0)
    if w >= 3800 or h >= 2000:
        return '4K'
    if w >= 1900 or h >= 1000:
        return '1080p'
    if w >= 1200 or h >= 700:
        return '720p'
    if w >= 700 or h >= 450:
        return '480p'
    if h > 0:
        return f'{h}p'
    return None


def _probe_resolution(filepath):
    """Use pymediainfo to read actual video dimensions. Returns resolution string or None."""
    if not _MEDIAINFO_AVAILABLE:
        return None
    try:
        info = _MediaInfo.parse(filepath)
        for track in info.tracks:
            if track.track_type == 'Video':
                w = int(track.width or 0)
                h = int(track.height or 0)
                return _classify_dimensions(w, h)
        return None
    except Exception:
        return None


def get_resolution_from_file(filepath):
    """Return resolution string for a video file.
    Probes actual video stream dimensions first so cropped 1080p files are not
    mislabeled as 720p. Falls back to filename parsing when probing is not
    available.
    Falls back gracefully if pymediainfo is not installed."""
    filename = os.path.basename(filepath)
    filename_res = get_resolution(filename)
    # Probe with mediainfo before trusting filename-derived resolution.
    try:
        mtime = os.path.getmtime(filepath)
    except OSError:
        return filename_res
    key = (os.path.abspath(filepath), mtime)
    if key in _res_cache and key not in _res_cache_reprobe:
        return _res_cache[key]
    probed = _probe_resolution(filepath)
    result = probed if probed else filename_res
    _res_cache[key] = result
    _res_cache_reprobe.discard(key)
    return result


def get_resolution_rank_str(resolution):
    """Return numeric rank for an already-resolved resolution string."""
    order = {'4K': 4, '1080p': 3, '720p': 2, '480p': 1, 'Unknown': 0}
    return order.get(resolution, 0)


def _load_res_cache():
    """Load persisted resolution cache from disk into _res_cache."""
    global _res_cache, _res_cache_reprobe
    try:
        with open(_RES_CACHE_FILE, 'r', encoding='utf-8') as f:
            data = _json.load(f)
        if not isinstance(data, dict):
            return
        if data.get('_version') == _RES_CACHE_VERSION:
            entries = data.get('entries', {})
            legacy = False
        else:
            entries = data
            legacy = True
        for path, v in entries.items():
            if not isinstance(v, dict) or 'mtime' not in v or 'res' not in v:
                continue
            res = v['res']
            if legacy and res == '720p':
                filename_res = get_resolution(os.path.basename(path))
                path_has_1080_hint = bool(re.search(r'(^|[^\d])1080p?([^\d]|$)', path, re.IGNORECASE))
                if filename_res == 'Unknown' and path_has_1080_hint:
                    res = '1080p'
            key = (path, float(v['mtime']))
            _res_cache[key] = res
    except Exception:
        pass


def _save_res_cache():
    """Persist resolution cache to disk so probed results survive app restarts."""
    try:
        data = {'_version': _RES_CACHE_VERSION, 'entries': {}}
        for (path, mtime), res in _res_cache.items():
            data['entries'][path] = {'mtime': mtime, 'res': res}
        with open(_RES_CACHE_FILE, 'w', encoding='utf-8') as f:
            _json.dump(data, f, indent=2)
    except Exception:
        pass


_load_res_cache()  # populate cache from disk at startup

def parse_movie_title(filename):
    """Return a (title, year) key so remakes with the same name are not grouped together."""
    name = os.path.splitext(filename)[0]

    # Extract year — handles: .2003. / (2003) / [2003] / {2003} / _2003_ / -2003- / space
    year_match = re.search(r'[\.\s_\-\(\[\{]((19|20)\d{2})[\.\s_\-\)\]\}]', name)
    year = year_match.group(1) if year_match else ''

    if year_match:
        name = name[:year_match.start()]
    else:
        name = re.sub(
            r'[\.\s_\-]*(1080p|720p|480p|2160p|4k|uhd|bluray|blu-ray|bdrip|bdremux|'
            r'hdrip|webrip|web-dl|dvdrip|hdtv|x264|x265|hevc|avc|aac|dts|ac3|h264|h265|'
            r'10bit|remux|extended|theatrical|remastered|directors\.cut).*',
            '', name, flags=re.IGNORECASE
        )

    name = re.sub(r'[\._\-]', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip().lower()
    return (name, year)


def get_resolution(filename):
    name = filename.lower()
    if '2160p' in name or '4k' in name or 'uhd' in name:
        return '4K'
    elif '1080p' in name or re.search(r'[\.\-_ \[\(]1080[\.\-_ \]\)\[]', name):
        return '1080p'
    elif '720p' in name or re.search(r'[\.\-_ \[\(]720[\.\-_ \]\)\[]', name):
        return '720p'
    elif '480p' in name or re.search(r'[\.\-_ \[\(]480[\.\-_ \]\)\[]', name):
        return '480p'
    return 'Unknown'


def get_rip_rank(rip_source):
    order = {
        'BD Remux': 9, 'Remux': 8, 'Blu-ray': 7, 'BDRip': 6,
        'WEB-DL': 5, 'WEBRip': 4, 'HDRip': 3, 'HDTV': 2,
        'DVDRip': 1, 'DVDScr': 0, 'CAMRip': -1, 'HDCAM': -2, 'Unknown': -3,
    }
    return order.get(rip_source, -3)


def get_resolution_rank(filename):
    order = {'4K': 4, '1080p': 3, '720p': 2, '480p': 1, 'Unknown': 0}
    return order.get(get_resolution(filename), 0)


def get_rip_source(filename):
    name = filename.lower()
    # Order matters — check more specific terms first
    if 'bdremux' in name or 'bd remux' in name:
        return 'BD Remux'
    elif 'bluray' in name or 'blu-ray' in name or 'bluray' in name:
        return 'Blu-ray'
    elif 'bdrip' in name or 'bdrip' in name:
        return 'BDRip'
    elif 'web-dl' in name or 'webdl' in name:
        return 'WEB-DL'
    elif 'webrip' in name or 'web-rip' in name:
        return 'WEBRip'
    elif 'hdrip' in name:
        return 'HDRip'
    elif 'hdtv' in name:
        return 'HDTV'
    elif 'dvdrip' in name or 'dvd-rip' in name:
        return 'DVDRip'
    elif 'dvdscr' in name or 'dvd-scr' in name:
        return 'DVDScr'
    elif 'hdcam' in name:
        return 'HDCAM'
    elif 'camrip' in name or 'cam-rip' in name or name.endswith('.cam'):
        return 'CAMRip'
    elif 'remux' in name:
        return 'Remux'
    return 'Unknown'


def format_size(size):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"


def _norm_movie_title(t):
    if not t:
        return ''
    t = str(t).lower()
    t = re.sub(r'[^\w\s]', '', t)
    t = re.sub(r'\s+', ' ', t).strip()
    t = re.sub(r'^(the|a|an) ', '', t)
    return t


_GOOD_RELEASE_SOURCES = {'WEB-DL', 'WEBRip', 'Blu-ray', 'BDRip', 'BD Remux', 'Remux'}
_BAD_RELEASE_RE = re.compile(
    r'(^|[.\-_\s\[\(])(cam|camrip|hdcam|ts|hdts|telesync|tc|telecine|scr|screener|dvdscr)([.\-_\s\]\)]|$)',
    re.IGNORECASE
)


def _proper_release_from_title(title):
    if not title or _BAD_RELEASE_RE.search(title):
        return None
    source = get_rip_source(title)
    resolution = get_resolution(title)
    if source not in _GOOD_RELEASE_SOURCES or get_resolution_rank_str(resolution) < 3:
        return None
    return {'source': source, 'resolution': resolution}


def _find_owned_movie(movie):
    title = str(movie.get('title', '') or '').strip()
    year = str(movie.get('year', '') or '').strip()
    if not title:
        return None
    cache_key = _library_cache_key()
    if not any(True for _ in _iter_movie_roots()):
        return None
    _auto_sync_plex(force=False)
    target_title = _norm_movie_title(title)
    best = None

    def consider(candidate_title, candidate_year, path, filename, size=0):
        nonlocal best
        if not candidate_title:
            return
        if _norm_movie_title(candidate_title) != target_title:
            return
        if year and candidate_year and str(candidate_year) != year:
            return
        if year and not candidate_year:
            return
        resolution = get_resolution_from_file(path)
        current = {
            'found': True,
            'path': path,
            'filename': filename,
            'resolution': resolution,
            'size_human': format_size(size) if size else '',
        }
        if best is None or get_resolution_rank_str(resolution) > get_resolution_rank_str(best.get('resolution')):
            best = current

    if (_library_cache.get('items') is not None
            and _library_cache.get('dir') == cache_key
            and time.time() - _library_cache.get('time', 0) < _LIBRARY_TTL):
        for item in _library_cache['items']:
            path = item.get('path', '')
            if not path or not os.path.isfile(path):
                continue
            parsed_title, parsed_year = parse_movie_title(item.get('filename', '') or item.get('title', ''))
            identity_title = item.get('plex_title') or parsed_title
            identity_year = str(item.get('plex_year') or parsed_year or '')
            consider(identity_title, identity_year, path, item.get('filename', os.path.basename(path)), NumberSafe(item.get('size')))
        return best

    for _, _, file, full_path in _iter_video_files():
        try:
            size = os.path.getsize(full_path)
        except OSError:
            size = 0
        plex_data = _plex_cache.get(_norm(full_path), {})
        if plex_data.get('plex_title'):
            consider(plex_data.get('plex_title'), str(plex_data.get('plex_year', '') or ''), full_path, file, size)
        parsed_title, parsed_year = parse_movie_title(file)
        consider(parsed_title, parsed_year, full_path, file, size)
    return best


def NumberSafe(value):
    try:
        return int(value or 0)
    except Exception:
        return 0


def _find_best_followed_release(movie):
    if not _prowlarr_url or not _prowlarr_key:
        return None
    title = str(movie.get('title', '') or '').strip()
    year = str(movie.get('year', '') or '').strip()
    if not title:
        return None
    query = f"{title} {year}".strip()
    try:
        indexer_ids = []
        try:
            idx_req = urllib.request.Request(
                f"{_prowlarr_url}/api/v1/indexer",
                headers={'X-Api-Key': _prowlarr_key, 'Accept': 'application/json'}
            )
            with urllib.request.urlopen(idx_req, timeout=8) as idx_resp:
                indexers = _json.loads(idx_resp.read().decode())
            indexer_ids = [str(ix['id']) for ix in indexers if ix.get('enable', True)]
        except Exception:
            pass
        parts = [('query', query), ('type', 'search'), ('categories', '2000'), ('limit', '100')]
        parts += [('indexerIds', iid) for iid in indexer_ids]
        url = f"{_prowlarr_url}/api/v1/search?{urllib.parse.urlencode(parts)}"
        req = urllib.request.Request(url, headers={'X-Api-Key': _prowlarr_key, 'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=25) as resp:
            results = _json.loads(resp.read().decode())
    except Exception:
        return None

    candidates = []
    for r in results:
        torrent_title = r.get('title', '')
        if _TV_RE.search(torrent_title):
            continue
        quality = _proper_release_from_title(torrent_title)
        if not quality:
            continue
        size = NumberSafe(r.get('size'))
        candidates.append({
            'title': torrent_title,
            'resolution': quality['resolution'],
            'source': quality['source'],
            'seeders': NumberSafe(r.get('seeders')),
            'size_bytes': size,
            'size_human': format_size(size) if size else '?',
            'indexer': r.get('indexer', ''),
            'magnet_url': r.get('magnetUrl', ''),
            'download_url': r.get('downloadUrl', ''),
            'info_url': r.get('infoUrl', ''),
        })
    if not candidates:
        return None
    candidates.sort(key=lambda item: (
        get_resolution_rank_str(item.get('resolution')),
        get_rip_rank(item.get('source')),
        NumberSafe(item.get('seeders')),
        NumberSafe(item.get('size_bytes')),
    ), reverse=True)
    return candidates[0]


def _sort_followed_releases(items):
    status_rank = {'available': 0, 'watching': 1, 'owned': 2}
    return sorted(items, key=lambda item: (
        status_rank.get(item.get('status'), 3),
        -float(item.get('updated_at') or item.get('followed_at') or 0),
    ))


def _check_followed_releases():
    store = _curation_store()
    current = store.followed_all()
    checked = []
    removed_owned = []
    newly_available = []
    now = time.time()
    for item in current:
        before_status = item.get('status', 'watching')
        owned = _find_owned_movie(item)
        if owned:
            removed_owned.append({**item, 'status': 'owned', 'owned': owned, 'updated_at': now, 'last_checked': now})
            continue
        best_release = _find_best_followed_release(item)
        updated = {**item, 'last_checked': now}
        if best_release:
            updated['status'] = 'available'
            updated['best_release'] = best_release
            updated['updated_at'] = now if before_status != 'available' else item.get('updated_at', now)
            if before_status != 'available':
                newly_available.append(updated)
        else:
            updated['status'] = 'watching'
            updated['best_release'] = {}
        checked.append(updated)
    checked = _sort_followed_releases(checked)
    store.save_followed_all(checked)
    return {
        'movies': checked,
        'removed_owned': removed_owned,
        'newly_available': newly_available,
        'checked_at': now,
    }


def _scan_duplicates_legacy(movies_dir):
    # If Plex assigns more than this many files to the same title+year it has
    # almost certainly bulk-mis-matched them (e.g. whole folder → one wrong film).
    # Fall back to filename parsing for those files.
    MAX_PLEX_GROUP = 4

    groups     = {}   # title_key -> [file_dict, ...]
    plex_keyed = set()  # title keys that came from Plex metadata

    for root, dirs, files in os.walk(movies_dir):
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext not in VIDEO_EXTENSIONS:
                continue
            full_path = os.path.join(root, file)
            try:
                size = os.path.getsize(full_path)
            except OSError:
                size = 0
            # Prefer Plex metadata title/year — matches exactly what Plex considers a duplicate.
            # Fall back to filename parsing for files not yet in Plex.
            plex_data = _plex_cache.get(_norm(full_path), {})
            if plex_data.get('plex_title'):
                title_key = (plex_data['plex_title'].strip().lower(), str(plex_data.get('plex_year', '')))
                plex_keyed.add(title_key)
            else:
                title_key = parse_movie_title(file)
            if not title_key[0]:
                continue
            res = get_resolution_from_file(full_path)
            groups.setdefault(title_key, []).append({
                'path': full_path,
                'filename': file,
                'size': size,
                'size_human': format_size(size),
                'resolution': res,
                'resolution_rank': get_resolution_rank_str(res),
                'rip_source': get_rip_source(file),
            })

    # Detect Plex bulk mis-matches: a Plex-derived group with > MAX_PLEX_GROUP files
    # means Plex tagged an entire folder as the same movie (wrong). Re-bucket those
    # files by filename so they appear as individual titles instead.
    for bad_key in [k for k in plex_keyed if len(groups.get(k, [])) > MAX_PLEX_GROUP]:
        for entry in groups.pop(bad_key):
            fallback_key = parse_movie_title(entry['filename'])
            if fallback_key[0]:
                groups.setdefault(fallback_key, []).append(entry)

    duplicates = []
    total_wasted = 0
    for (title, year), files in groups.items():
        if len(files) < 2:
            continue
        files_sorted = sorted(files, key=lambda x: (x['resolution_rank'], get_rip_rank(x['rip_source']), x['size']), reverse=True)
        # Wasted space = all copies except the best one
        wasted = sum(f['size'] for f in files_sorted[1:])
        total_wasted += wasted
        display_title = title.title() + (f' ({year})' if year else '')
        duplicates.append({
            'title': display_title,
            'files': files_sorted,
            'wasted': wasted,
            'wasted_human': format_size(wasted),
        })
    duplicates.sort(key=lambda x: x['title'])

    extra_copies = sum(len(d['files']) - 1 for d in duplicates)
    stats = {
        'groups': len(duplicates),
        'extra_copies': extra_copies,
        'wasted_human': format_size(total_wasted),
        'wasted_bytes': total_wasted,
    }
    return duplicates, stats


def scan_duplicates(movies_dirs):
    # Multi-root duplicate scanner. Groups are built across every configured
    # library root, so copies on different drives still compare against each other.
    MAX_PLEX_GROUP = 4
    groups = {}
    plex_keyed = set()
    roots = movies_dirs if isinstance(movies_dirs, (list, tuple)) else [movies_dirs]

    for movies_dir in roots:
        if not any(True for _ in _iter_movie_roots()):
            continue
        for root, _, files in os.walk(movies_dir):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext not in VIDEO_EXTENSIONS:
                    continue
                full_path = os.path.join(root, file)
                try:
                    size = os.path.getsize(full_path)
                except OSError:
                    size = 0
                plex_data = _plex_cache.get(_norm(full_path), {})
                if plex_data.get('plex_title'):
                    title_key = (plex_data['plex_title'].strip().lower(), str(plex_data.get('plex_year', '')))
                    plex_keyed.add(title_key)
                else:
                    title_key = parse_movie_title(file)
                if not title_key[0]:
                    continue
                res = get_resolution_from_file(full_path)
                groups.setdefault(title_key, []).append({
                    'path': full_path,
                    'filename': file,
                    'size': size,
                    'size_human': format_size(size),
                    'resolution': res,
                    'resolution_rank': get_resolution_rank_str(res),
                    'rip_source': get_rip_source(file),
                    'library_root': movies_dir,
                })

    for bad_key in [k for k in plex_keyed if len(groups.get(k, [])) > MAX_PLEX_GROUP]:
        for entry in groups.pop(bad_key):
            fallback_key = parse_movie_title(entry['filename'])
            if fallback_key[0]:
                groups.setdefault(fallback_key, []).append(entry)

    duplicates = []
    total_wasted = 0
    for (title, year), files in groups.items():
        if len(files) < 2:
            continue
        files_sorted = sorted(
            files,
            key=lambda x: (x['resolution_rank'], get_rip_rank(x['rip_source']), x['size']),
            reverse=True
        )
        wasted = sum(f['size'] for f in files_sorted[1:])
        total_wasted += wasted
        display_title = title.title() + (f' ({year})' if year else '')
        duplicates.append({
            'title': display_title,
            'files': files_sorted,
            'wasted': wasted,
            'wasted_human': format_size(wasted),
        })
    duplicates.sort(key=lambda x: x['title'])

    extra_copies = sum(len(d['files']) - 1 for d in duplicates)
    stats = {
        'groups': len(duplicates),
        'extra_copies': extra_copies,
        'wasted_human': format_size(total_wasted),
        'wasted_bytes': total_wasted,
    }
    return duplicates, stats


def _auto_sync_plex(force=False):
    """Refresh _plex_cache if Plex is configured and cache is stale (>5 min). Silent on errors.
    Pass force=True to bypass the TTL and always fetch fresh data."""
    global _plex_cache, _plex_unmatched, _plex_matched_by_fname, _plex_unmatched_by_fname, \
           _plex_section_ids, _plex_cache_time, _library_cache
    if not _plex_url or not _plex_token:
        return
    if not force and time.time() - _plex_cache_time < _PLEX_TTL:
        return  # cache is still fresh
    try:
        _plex_cache, _plex_unmatched, _plex_matched_by_fname, _plex_unmatched_by_fname, \
            _plex_section_ids = _fetch_plex_library()
        _plex_cache_time = time.time()
        _library_cache = {}  # Plex data refreshed — bust library cache so titles update
    except Exception:
        pass  # don't break scan if Plex is unreachable


def _plex_person_list(item, field_name):
    people = []
    for person in item.get(field_name, []) or []:
        name = person.get('tag') or person.get('title') or person.get('name') or ''
        if not name:
            continue
        people.append({
            'id': str(person.get('id', '') or ''),
            'name': name,
            'character': person.get('role', '') if field_name == 'Role' else '',
            'profile_url': (
                f"{_plex_url}{person.get('thumb')}?X-Plex-Token={_plex_token}"
                if _plex_url and _plex_token and person.get('thumb') else ''
            ),
        })
    return people


def _extract_tmdb_id_from_plex_item(item):
    ids = [item.get('guid', '')]
    ids.extend(g.get('id', '') for g in item.get('Guid', []) or [])
    for value in ids:
        match = re.search(r'tmdb://(\d+)', str(value))
        if match:
            return match.group(1)
    return ''


def _extract_imdb_id_from_plex_item(item):
    ids = [item.get('guid', '')]
    ids.extend(g.get('id', '') for g in item.get('Guid', []) or [])
    for value in ids:
        match = re.search(r'imdb://(tt\d+)', str(value), re.IGNORECASE)
        if match:
            return match.group(1).lower()
    return ''


def _fetch_plex_library():
    """Fetch all movie file paths + metadata from Plex.
    Returns (matched_cache, unmatched_cache, matched_by_fname, unmatched_by_fname, section_ids).
    matched_cache:    normpath -> {plex_title, plex_year, plex_genres}
    unmatched_cache:  normpath -> {rating_key, plex_title}  (Plex has file but no match)
    matched_by_fname:   filename.lower() -> matched entry   (fallback for path-mismatch cases)
    unmatched_by_fname: filename.lower() -> unmatched entry (fallback for path-mismatch cases)
    section_ids: list of movie library section keys
    """
    if not _plex_url or not _plex_token:
        return {}, {}, {}, {}, []

    def plex_get(path):
        sep = '&' if '?' in path else '?'
        url = f"{_plex_url}{path}{sep}X-Plex-Token={_plex_token}"
        req = urllib.request.Request(url, headers={'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return _json.loads(resp.read().decode())

    data = plex_get('/library/sections')
    sections = data.get('MediaContainer', {}).get('Directory', [])
    movie_sections = [s['key'] for s in sections if s.get('type') == 'movie']

    matched = {}
    unmatched = {}
    matched_by_fname = {}
    unmatched_by_fname = {}
    for section_key in movie_sections:
        data = plex_get(f'/library/sections/{section_key}/all')
        for item in data.get('MediaContainer', {}).get('Metadata', []):
            guid        = item.get('guid', '')
            rating_key  = item.get('ratingKey', '')
            title       = item.get('title', '')
            year        = str(item.get('year', '')) if item.get('year') else ''
            genres      = [g['tag'] for g in item.get('Genre', [])]
            summary     = item.get('summary', '')
            rating      = str(item.get('rating', '') or item.get('audienceRating', '') or '')
            thumb       = item.get('thumb', '')
            tmdb_id     = _extract_tmdb_id_from_plex_item(item)
            imdb_id     = _extract_imdb_id_from_plex_item(item)
            directors   = _plex_person_list(item, 'Director')
            cast        = _plex_person_list(item, 'Role')[:7]
            is_local    = (not guid) or guid.startswith('local://')
            for media in item.get('Media', []):
                for part in media.get('Part', []):
                    fp = part.get('file', '')
                    if fp:
                        norm  = _norm(fp)
                        fname = os.path.basename(fp).lower()
                        if is_local:
                            entry = {'rating_key': rating_key, 'plex_title': title}
                            unmatched[norm] = entry
                            # filename fallback — only store first hit to avoid collisions
                            unmatched_by_fname.setdefault(fname, entry)
                        else:
                            lang = item.get('originalLanguage', '')
                            countries_raw = [c['tag'] for c in item.get('Country', [])]
                            lang_name    = _LANG_NAMES.get(lang, lang.upper() if lang else '')
                            cc           = _LANG_COUNTRY.get(lang, '')
                            flag         = _country_flag(cc) if cc else ''
                            entry = {'plex_title': title, 'plex_year': year, 'plex_genres': genres,
                                     'plex_summary': summary, 'plex_rating': rating, 'plex_thumb': thumb,
                                     'plex_language': lang_name,
                                     'plex_country_flag': flag,
                                     'plex_country': countries_raw[0] if countries_raw else '',
                                     'plex_directors': directors,
                                     'plex_cast': cast,
                                     'tmdb_id': tmdb_id,
                                     'imdb_id': imdb_id,
                                     'plex_guid': guid}
                            matched[norm] = entry
                            matched_by_fname.setdefault(fname, entry)
    return matched, unmatched, matched_by_fname, unmatched_by_fname, movie_sections


@app.route('/')
def index():
    dist_index = os.path.join(_BASE_DIR, 'dist', 'index.html')
    if os.path.exists(dist_index):
        return send_from_directory(os.path.join(_BASE_DIR, 'dist'), 'index.html')
    response = make_response(
        "React frontend has not been built. Run npm install and npm run build, or use run.bat on Windows.",
        503,
    )
    response.mimetype = "text/plain"
    return response


@app.route('/styleguide')
def styleguide_index():
    return index()


@app.route('/library')
@app.route('/cleanup')
@app.route('/discover')
@app.route('/settings')
def react_section_index():
    return index()


@app.route('/assets/<path:filename>')
def vite_assets(filename):
    return send_from_directory(os.path.join(_BASE_DIR, 'dist', 'assets'), filename)


@app.route('/api/plex/config', methods=['GET'])
def get_plex_config():
    return jsonify({'url': _plex_url, 'token': _plex_token})


@app.route('/api/plex/config', methods=['POST'])
def set_plex_config():
    global _plex_url, _plex_token
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    _plex_url   = data.get('url', 'http://localhost:32400').rstrip('/')
    _plex_token = data.get('token', '')
    _save_config(_all_config())
    return jsonify({'success': True})


@app.route('/api/plex/test')
def plex_test():
    if not _plex_url or not _plex_token:
        return jsonify({'error': 'URL or token missing — configure Plex first.'}), 400
    try:
        sep = '&' if '?' in '/library/sections' else '?'
        url = f"{_plex_url}/library/sections{sep}X-Plex-Token={_plex_token}"
        req = urllib.request.Request(url, headers={'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = _json.loads(resp.read().decode())
        sections = data.get('MediaContainer', {}).get('Directory', [])
        movie_libs = [s for s in sections if s.get('type') == 'movie']
        return jsonify({'success': True, 'movie_libraries': len(movie_libs), 'total_libraries': len(sections)})
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return jsonify({'error': 'Invalid token — Plex → Settings → General → Advanced → X-Plex-Token.'}), 401
        return jsonify({'error': f'Plex returned HTTP {e.code}'}), 502
    except Exception as e:
        return jsonify({'error': f'Cannot reach Plex: {e}'}), 502


@app.route('/api/plex/image')
def plex_image():
    url = request.args.get('url', '').strip()
    if not url:
        return '', 400
    # Security: only proxy to the configured Plex server — reject any other origin
    if not _plex_url or not url.startswith(_plex_url):
        return '', 403
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read()
            ct   = resp.headers.get('Content-Type', 'image/jpeg')
        response = make_response(data)
        response.headers['Content-Type']  = ct
        response.headers['Cache-Control'] = 'public, max-age=86400'
        return response
    except Exception:
        return '', 502


@app.route('/api/plex/sync')
def plex_sync():
    global _plex_cache, _plex_unmatched, _plex_matched_by_fname, _plex_unmatched_by_fname, \
           _plex_section_ids, _plex_cache_time, _library_cache
    if not _plex_url or not _plex_token:
        return jsonify({'error': 'Plex not configured.'}), 400
    try:
        _plex_cache, _plex_unmatched, _plex_matched_by_fname, _plex_unmatched_by_fname, \
            _plex_section_ids = _fetch_plex_library()
        _plex_cache_time = time.time()
        _library_cache = {}  # bust library cache so new language/country fields appear
        return jsonify({'success': True, 'cached': len(_plex_cache)})
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return jsonify({'error': 'Invalid Plex token.'}), 401
        return jsonify({'error': f'Plex returned HTTP {e.code}'}), 502
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/config', methods=['GET'])
def get_config():
    return jsonify({
        'directory': get_movies_dir(),
        'directories': get_movies_dirs(),
        'show_adult_movies': _library_show_adult,
    })


@app.route('/api/config', methods=['POST'])
def set_config():
    global _movies_dir, _movies_dirs, _library_cache, _library_show_adult
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'No directory provided'}), 400
    if isinstance(data.get('directories'), list):
        requested_dirs = [str(path or '').strip() for path in data.get('directories', []) if str(path or '').strip()]
    elif 'directory' in data:
        requested_dirs = [str(data.get('directory') or '').strip()]
    else:
        requested_dirs = []
    if not requested_dirs:
        return jsonify({'error': 'At least one movie directory is required'}), 400
    normalized_dirs = []
    seen = set()
    for path in requested_dirs:
        if not os.path.isdir(path):
            return jsonify({'error': f'Directory not found: {path}'}), 400
        norm = _norm(path)
        if norm in seen:
            continue
        abs_path = os.path.abspath(path)
        for existing in normalized_dirs:
            abs_existing = os.path.abspath(existing)
            try:
                common = os.path.commonpath([abs_path, abs_existing])
            except ValueError:
                common = ''
            if common == abs_existing or common == abs_path:
                return jsonify({'error': f'Library folders cannot be nested: {path}'}), 400
        seen.add(norm)
        normalized_dirs.append(path)
    _movies_dirs = normalized_dirs
    _movies_dir = _movies_dirs[0]
    if 'show_adult_movies' in data:
        _library_show_adult = _coerce_bool(data.get('show_adult_movies'), True)
    _library_cache = {}  # directory changed — bust library cache
    _save_config(_all_config())
    return jsonify({
        'success': True,
        'directory': _movies_dir,
        'directories': get_movies_dirs(),
        'show_adult_movies': _library_show_adult,
    })


@app.route('/api/app-data/config', methods=['GET', 'POST'])
def app_data_config():
    global _user_data_dir, _tmdb_cache_dir, _TMDB_CACHE_DIR, _TMDB_LIBRARY_CACHE_FILE, \
           _TMDB_COLLECTION_CACHE_FILE, _tmdb_library_cache, _tmdb_collection_cache
    if request.method == 'GET':
        return jsonify({'user_data_dir': _user_data_dir, 'tmdb_cache_dir': _tmdb_cache_dir})
    data = request.get_json(force=True, silent=True) or {}
    user_dir = str(data.get('user_data_dir', _user_data_dir) or '').strip()
    cache_dir = str(data.get('tmdb_cache_dir', _tmdb_cache_dir) or '').strip()
    if not user_dir or not cache_dir:
        return jsonify({'error': 'User data and TMDB cache folders are required'}), 400
    try:
        os.makedirs(user_dir, exist_ok=True)
        os.makedirs(cache_dir, exist_ok=True)
    except Exception as e:
        return jsonify({'error': f'Cannot create folder: {e}'}), 400
    _user_data_dir = user_dir
    _tmdb_cache_dir = cache_dir
    _TMDB_CACHE_DIR = _tmdb_cache_dir
    _TMDB_LIBRARY_CACHE_FILE = os.path.join(_TMDB_CACHE_DIR, 'tmdb_library_cache.json')
    _TMDB_COLLECTION_CACHE_FILE = os.path.join(_TMDB_CACHE_DIR, 'tmdb_collection_cache.json')
    _tmdb_library_cache = _load_tmdb_library_cache()
    _tmdb_collection_cache = _load_tmdb_collection_cache()
    _save_config(_all_config())
    return jsonify({'success': True, 'user_data_dir': _user_data_dir, 'tmdb_cache_dir': _tmdb_cache_dir})


@app.route('/api/prowlarr/config', methods=['GET'])
def get_prowlarr_config():
    return jsonify({'url': _prowlarr_url, 'key': _prowlarr_key})


@app.route('/api/prowlarr/config', methods=['POST'])
def set_prowlarr_config():
    global _prowlarr_url, _prowlarr_key
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    _prowlarr_url = data.get('url', '').rstrip('/')
    _prowlarr_key = data.get('key', '')
    _save_config(_all_config())
    return jsonify({'success': True})


@app.route('/api/prowlarr/test')
def prowlarr_test():
    if not _prowlarr_url or not _prowlarr_key:
        return jsonify({'error': 'URL or API key is missing — please fill in both fields and save.'}), 400
    try:
        url = f"{_prowlarr_url}/api/v1/indexer"
        req = urllib.request.Request(url, headers={'X-Api-Key': _prowlarr_key, 'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=8) as resp:
            indexers = _json.loads(resp.read().decode())
        return jsonify({'success': True, 'indexers': len(indexers)})
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return jsonify({'error': 'Invalid API key — check Prowlarr → Settings → General.'}), 401
        return jsonify({'error': f'Prowlarr returned HTTP {e.code}'}), 502
    except Exception as e:
        return jsonify({'error': f'Cannot reach Prowlarr: {e}'}), 502


@app.route('/api/prowlarr/search')
def prowlarr_search():
    if not _prowlarr_url or not _prowlarr_key:
        return jsonify({'error': 'Prowlarr not configured — click ⚙ Prowlarr in the header to enter your URL and API key.'}), 400
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'error': 'No query provided'}), 400
    try:
        # Fetch all enabled indexer IDs so every indexer is queried, not just the default subset
        indexer_ids = []
        try:
            idx_req = urllib.request.Request(
                f"{_prowlarr_url}/api/v1/indexer",
                headers={'X-Api-Key': _prowlarr_key, 'Accept': 'application/json'}
            )
            with urllib.request.urlopen(idx_req, timeout=8) as idx_resp:
                indexers = _json.loads(idx_resp.read().decode())
            indexer_ids = [str(ix['id']) for ix in indexers if ix.get('enable', True)]
        except Exception:
            pass  # fall back to Prowlarr default if indexer fetch fails

        qs = {'query': query, 'type': 'search', 'limit': 1000}
        if indexer_ids:
            qs['indexerIds'] = indexer_ids  # will be encoded as repeated params below
        # urllib.parse.urlencode doesn't handle lists — build manually
        parts = [(k, v) for k, v in qs.items() if k != 'indexerIds']
        parts += [('indexerIds', iid) for iid in indexer_ids]
        url = f"{_prowlarr_url}/api/v1/search?{urllib.parse.urlencode(parts)}"
        req = urllib.request.Request(url, headers={'X-Api-Key': _prowlarr_key, 'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=30) as resp:
            results = _json.loads(resp.read().decode())
        # Detect resolution from torrent title and format results (all resolutions)
        filtered = []
        for r in results:
            title = r.get('title', '')
            tl = title.lower()
            res = 'Unknown'
            res_rank = 0
            if '2160p' in tl or '4k' in tl or 'uhd' in tl:
                res, res_rank = '4K', 4
            elif '1080p' in tl or re.search(r'[\.\-_ \[\(]1080[\.\-_ \]\)\[]', tl):
                res, res_rank = '1080p', 3
            elif '720p' in tl or re.search(r'[\.\-_ \[\(]720[\.\-_ \]\)\[]', tl):
                res, res_rank = '720p', 2
            elif '480p' in tl or re.search(r'[\.\-_ \[\(]480[\.\-_ \]\)\[]', tl):
                res, res_rank = '480p', 1
            size = r.get('size', 0)
            filtered.append({
                'title': title,
                'indexer': r.get('indexer', ''),
                'size_human': format_size(size) if size else '?',
                'size': size,
                'seeders': r.get('seeders', 0),
                'resolution': res,
                'download_url': r.get('downloadUrl', ''),
                'magnet_url': r.get('magnetUrl', ''),
                'info_url': r.get('infoUrl', ''),
            })
        # Sort: resolution desc, then seeders desc
        filtered.sort(key=lambda x: (x['size'], x['seeders']), reverse=True)
        return jsonify({'results': filtered})
    except urllib.error.HTTPError as e:
        return jsonify({'error': f'Prowlarr returned HTTP {e.code}'}), 502
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/duplicates')
def get_duplicates():
    try:
        _auto_sync_plex(force=request.args.get('force_plex') == '1')
        duplicates, stats = scan_duplicates(get_movies_dirs())
        for group in duplicates:
            for f in group['files']:
                plex_data = _plex_cache.get(_norm(f['path']), {})
                f['plex_title']   = plex_data.get('plex_title', '')
                f['plex_year']    = plex_data.get('plex_year', '')
                f['plex_genres']  = plex_data.get('plex_genres', [])
                f['plex_matched'] = bool(plex_data)
        return jsonify({'duplicates': duplicates, 'directory': get_movies_dir(), 'directories': get_movies_dirs(), 'stats': stats,
                        'plex_enabled': bool(_plex_token), 'plex_cached': len(_plex_cache) > 0})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/open-file', methods=['POST'])
def open_file():
    data = request.get_json(silent=True)
    path = (data or {}).get('path', '').strip()
    if not path or not os.path.isfile(path):
        return jsonify({'error': 'File not found'}), 404
    try:
        os.startfile(path)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/delete', methods=['POST'])
def delete_file():
    data = request.get_json(silent=True)
    if not data or 'path' not in data:
        return jsonify({'error': 'No path provided'}), 400

    path = data['path']
    use_trash = data.get('trash', True)  # default: Recycle Bin
    abs_path = os.path.abspath(path)
    abs_dir = _path_library_root(abs_path)

    # Security: only allow deleting files inside a configured movie directory
    if not abs_dir:
        return jsonify({'error': 'Path is outside the allowed movies directory'}), 403

    if not os.path.isfile(abs_path):
        return jsonify({'error': 'File not found'}), 404

    try:
        # Clear read-only flag if set
        current_mode = os.stat(abs_path).st_mode
        if not (current_mode & stat.S_IWRITE):
            os.chmod(abs_path, current_mode | stat.S_IWRITE)

        if use_trash:
            send2trash(abs_path)
        else:
            os.remove(abs_path)

        # Clean up parent folder if no video files remain
        parent = os.path.dirname(abs_path)
        folder_removed = False
        if not use_trash and parent != abs_dir and os.path.isdir(parent):
            remaining_videos = [
                f for f in os.listdir(parent)
                if os.path.splitext(f)[1].lower() in VIDEO_EXTENSIONS
            ]
            if not remaining_videos:
                shutil.rmtree(parent, ignore_errors=True)
                folder_removed = True

        _library_cache.pop('items', None)  # bust library cache — file list changed
        return jsonify({'success': True, 'deleted': abs_path, 'folder_removed': folder_removed, 'folder': parent, 'trashed': use_trash})
    except PermissionError:
        return jsonify({
            'error': 'Access denied. The file may be open in Plex or another program. '
                     'Try pausing Plex Media Server and then delete again.'
        }), 500
    except OSError as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/library/status')
def library_status():
    return jsonify({'status': _library_status})


@app.route('/api/library')
def library():
    global _library_cache, _library_status
    force_plex = request.args.get('force_plex') == '1'
    refresh_metadata = request.args.get('refresh_metadata') == '1'
    try:
        _auto_sync_plex(force=force_plex)
        # Serve from cache if still fresh and directory hasn't changed
        if (not force_plex
                and not refresh_metadata
                and _library_cache.get('items') is not None
                and _library_cache.get('dir') == _library_cache_key()
                and time.time() - _library_cache.get('time', 0) < _LIBRARY_TTL):
            c = _library_cache
            return jsonify({'items': c['items'], 'count': len(c['items']),
                            'plex_enabled': c['plex_enabled'], 'plex_cached': c['plex_cached'],
                            'cached': True})
        _library_status = 'Scanning directory\u2026'
        total = sum(1 for _ in _iter_video_files())
        _library_status = f'Reading metadata for {total} files\u2026'
        items = []
        n = 0
        store = _metadata_store()
        metadata_snapshot = store.snapshot()
        for movies_dir, root, file, full_path in _iter_video_files():
            n += 1
            if n % 50 == 0:
                _library_status = f'Reading metadata\u2026 {n}\u00a0/\u00a0{total}'
            try:
                size = os.path.getsize(full_path)
                added_time = os.path.getctime(full_path)
                modified_time = os.path.getmtime(full_path)
            except OSError:
                size = 0
                added_time = 0
                modified_time = 0
            res = get_resolution_from_file(full_path)
            rip = get_rip_source(file)
            title_key = parse_movie_title(file)
            parsed_title, parsed_year = title_key
            fallback_title = parsed_title.title() if parsed_title else os.path.splitext(file)[0]
            display_title = fallback_title + (f' ({parsed_year})' if parsed_year else '')
            norm_path = _norm(full_path)
            plex_data = dict(_plex_cache.get(norm_path, {}) or _plex_matched_by_fname.get(file.lower(), {}) or {})
            plex_thumb = plex_data.get('plex_thumb', '')
            plex_poster = (
                f"{_plex_url}{plex_thumb}?X-Plex-Token={_plex_token}"
                if _plex_url and _plex_token and plex_thumb else ''
            )
            if plex_poster:
                plex_data['plex_poster'] = plex_poster
            file_facts = {
                'path': full_path,
                'filename': file,
                'library_root': movies_dir,
                'parsed_title': parsed_title,
                'parsed_year': parsed_year,
                'resolution': res,
                'rip_source': rip,
                'size': size,
                'added_time': added_time,
                'modified_time': modified_time,
            }
            manual_match = store.get_manual_match_from_snapshot(full_path, metadata_snapshot)
            tmdb_data = _tmdb_metadata_for_file(file_facts, plex_data=plex_data, store=store,
                                                refresh=refresh_metadata, snapshot=metadata_snapshot)
            canonical = _build_canonical_metadata(file_facts, plex_data=plex_data, tmdb_data=tmdb_data, manual_match=manual_match)
            items.append({
                'title': display_title,
                'filename': file,
                'path': full_path,
                'library_root': movies_dir,
                'resolution': res,
                'resolution_rank': get_resolution_rank_str(res),
                'rip_source': rip,
                'rip_rank': get_rip_rank(rip),
                'size': size,
                'size_human': format_size(size),
                'added_time': added_time,
                'modified_time': modified_time,
                'plex_title': plex_data.get('plex_title', ''),
                'plex_year': plex_data.get('plex_year', ''),
                'plex_genres': plex_data.get('plex_genres', []),
                'plex_summary': plex_data.get('plex_summary', ''),
                'plex_rating': plex_data.get('plex_rating', ''),
                'plex_language': plex_data.get('plex_language', ''),
                'plex_country_flag': plex_data.get('plex_country_flag', ''),
                'plex_country': plex_data.get('plex_country', ''),
                'plex_directors': plex_data.get('plex_directors', []),
                'plex_cast': plex_data.get('plex_cast', []),
                'tmdb_id': canonical.get('tmdb_id') or plex_data.get('tmdb_id', ''),
                'imdb_id': canonical.get('imdb_id') or plex_data.get('imdb_id', ''),
                'plex_guid': canonical.get('plex_guid') or plex_data.get('plex_guid', ''),
                'plex_poster': plex_poster,
                'plex_matched': bool(plex_data),
                'canonical_metadata': canonical,
                'metadata_status': canonical.get('status', 'unmatched'),
                'metadata_source': canonical.get('source', ''),
                'metadata_accepted': bool(canonical.get('accepted')),
            })
        _library_status = 'Sorting results\u2026'
        items.sort(key=lambda x: (-float(x.get('added_time') or 0), x['title']))
        _library_status = ''
        _save_res_cache()
        _library_cache['items'] = items
        _library_cache['plex_enabled'] = bool(_plex_token)
        _library_cache['plex_cached'] = len(_plex_cache) > 0
        _library_cache['time'] = time.time()
        _library_cache['dir'] = _library_cache_key()
        return jsonify({'items': items, 'count': len(items),
                        'plex_enabled': bool(_plex_token), 'plex_cached': len(_plex_cache) > 0})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def _ownership_keys(movie):
    keys = []
    tmdb_id = str((movie or {}).get('tmdb_id', '') or '').strip()
    imdb_id = str((movie or {}).get('imdb_id', '') or '').strip()
    plex_guid = str((movie or {}).get('plex_guid', '') or '').strip()
    title = _norm_movie_title((movie or {}).get('title', ''))
    year = str((movie or {}).get('year', '') or '').strip()
    if tmdb_id:
        keys.append(f"tmdb:{tmdb_id}")
    if imdb_id:
        keys.append(f"imdb:{imdb_id.lower()}")
    if plex_guid:
        keys.append(f"plex:{plex_guid.lower()}")
    if title:
        keys.append(f"title:{title}|{year}")
    return keys


def _library_check_v26():
    body = request.get_json(force=True, silent=True) or {}
    queries = body.get('movies', [])
    if not queries:
        return jsonify({'results': []})
    if not any(True for _ in _iter_movie_roots()):
        return jsonify({'results': [
            {'title': q.get('title', ''), 'year': str(q.get('year', '')),
             'tmdb_id': str(q.get('tmdb_id', '') or ''), 'imdb_id': str(q.get('imdb_id', '') or ''),
             'found': False, 'path': '', 'resolution': '', 'size_human': ''}
            for q in queries
        ]})

    _auto_sync_plex(force=False)
    store = _metadata_store()
    metadata_snapshot = store.snapshot()
    cache_key = _library_cache_key()
    if (_library_cache.get('items') is not None
            and _library_cache.get('dir') == cache_key
            and time.time() - _library_cache.get('time', 0) < _LIBRARY_TTL):
        items_src = _library_cache['items']
    else:
        items_src = []
        for _, _, file, full_path in _iter_video_files():
            try:
                size = os.path.getsize(full_path)
            except OSError:
                size = 0
            parsed_title, parsed_year = parse_movie_title(file)
            plex_data = dict(_plex_cache.get(_norm(full_path), {}) or _plex_matched_by_fname.get(file.lower(), {}) or {})
            file_facts = {'path': full_path, 'filename': file, 'parsed_title': parsed_title, 'parsed_year': parsed_year}
            tmdb_data = _tmdb_metadata_for_file(file_facts, plex_data=plex_data, store=store,
                                                refresh=False, snapshot=metadata_snapshot)
            canonical = _build_canonical_metadata(
                file_facts,
                plex_data=plex_data,
                tmdb_data=tmdb_data,
                manual_match=store.get_manual_match_from_snapshot(full_path, metadata_snapshot),
            )
            items_src.append({
                'path': full_path,
                'filename': file,
                'resolution': get_resolution(file),
                'size_human': format_size(size),
                'size': size,
                'plex_title': plex_data.get('plex_title', ''),
                'plex_year': str(plex_data.get('plex_year', '') or ''),
                'plex_matched': bool(plex_data),
                'canonical_metadata': canonical,
                'tmdb_id': canonical.get('tmdb_id') or plex_data.get('tmdb_id', ''),
                'imdb_id': canonical.get('imdb_id', ''),
                '_parsed_title': parsed_title,
                '_parsed_year': parsed_year,
            })

    lookup = {}
    for item in items_src:
        path = item.get('path', '')
        if not path or not os.path.isfile(path):
            continue
        parsed_title = item.get('_parsed_title')
        parsed_year = item.get('_parsed_year')
        if (not parsed_title or parsed_year is None) and item.get('filename'):
            parsed_title, parsed_year = parse_movie_title(item['filename'])
        canonical = item.get('canonical_metadata') or {}
        identity = {
            'tmdb_id': item.get('tmdb_id') or canonical.get('tmdb_id'),
            'imdb_id': item.get('imdb_id') or canonical.get('imdb_id'),
            'plex_guid': item.get('plex_guid') or canonical.get('plex_guid'),
            'title': canonical.get('title') or item.get('plex_title') or parsed_title,
            'year': canonical.get('year') or item.get('plex_year') or parsed_year,
        }
        entry = {
            'found': True,
            'title': identity.get('title', ''),
            'year': identity.get('year', ''),
            'tmdb_id': str(identity.get('tmdb_id', '') or ''),
            'imdb_id': str(identity.get('imdb_id', '') or ''),
            'path': path,
            'resolution': item.get('resolution', 'Unknown'),
            'size_human': item.get('size_human', ''),
        }
        for key in _ownership_keys(identity):
            existing = lookup.get(key)
            if existing is None or get_resolution_rank_str(entry['resolution']) > get_resolution_rank_str(existing.get('resolution')):
                lookup[key] = entry

    def find_match(query):
        for key in _ownership_keys(query):
            if key in lookup:
                return lookup[key]
        year = str(query.get('year', '') or '').strip()
        title = _norm_movie_title(query.get('title', ''))
        if title:
            exact = lookup.get(f"title:{title}|{year}")
            if exact:
                return exact
            if not year:
                prefix = f"title:{title}|"
                return next((value for key, value in lookup.items() if key.startswith(prefix)), None)
        return None

    results = []
    for q in queries:
        match = find_match(q)
        if match and match.get('path') and os.path.isfile(match['path']):
            results.append({
                'title': q.get('title', ''),
                'year': q.get('year', ''),
                'tmdb_id': str(q.get('tmdb_id', '') or match.get('tmdb_id', '') or ''),
                'imdb_id': str(q.get('imdb_id', '') or match.get('imdb_id', '') or ''),
                'found': True,
                'path': match['path'],
                'resolution': get_resolution_from_file(match['path']),
                'size_human': match.get('size_human', ''),
            })
        else:
            results.append({
                'title': q.get('title', ''),
                'year': q.get('year', ''),
                'tmdb_id': str(q.get('tmdb_id', '') or ''),
                'imdb_id': str(q.get('imdb_id', '') or ''),
                'found': False,
                'path': '',
                'resolution': '',
                'size_human': '',
            })
    return jsonify({'results': results})


@app.route('/api/library/check', methods=['POST'])
def library_check():
    return _library_check_v26()
    """Check which of the supplied movies exist in the local library.

    Request body: {"movies": [{"title": "Inception", "year": "2010"}, …]}
    Response:     {"results": [{"title": …, "year": …, "found": bool,
                                "path": …, "resolution": …, "size_human": …}]}
    Matching uses normalised title comparison (lowercase, no punctuation, no
    leading article) against plex_title+plex_year first, then parsed filename
    title+year.  Returns found:false for all entries when movies_dir is not set.
    """
    import re as _re_local

    def _norm_title(t):
        """Lowercase, strip punctuation, strip leading 'the/a/an '."""
        if not t:
            return ''
        t = str(t).lower()
        t = _re_local.sub(r'[^\w\s]', '', t)   # strip punctuation
        t = _re_local.sub(r'\s+', ' ', t).strip()
        t = _re_local.sub(r'^(the|a|an) ', '', t)
        return t

    try:
        body = request.get_json(force=True, silent=True) or {}
        queries = body.get('movies', [])
        if not queries:
            return jsonify({'results': []})

        cache_key = _library_cache_key()
        if not any(True for _ in _iter_movie_roots()):
            return jsonify({'results': [
                {'title': q.get('title', ''), 'year': str(q.get('year', '')),
                 'found': False, 'path': '', 'resolution': '', 'size_human': ''}
                for q in queries
            ]})

        # Build lookup: (norm_title, norm_year) -> best file info dict
        # Use library cache if fresh, else walk the directory (no deep scan needed)
        _auto_sync_plex(force=False)
        lookup = {}  # (norm_title, norm_year) -> {path, resolution, size_human}

        if (_library_cache.get('items') is not None
                and _library_cache.get('dir') == cache_key
                and time.time() - _library_cache.get('time', 0) < _LIBRARY_TTL):
            items_src = _library_cache['items']
        else:
            # Light scan: just filenames + plex cache, no resolution probing
            items_src = []
            for _, _, file, full_path in _iter_video_files():
                try:
                    size = os.path.getsize(full_path)
                except OSError:
                    size = 0
                # Ownership checks must stay fast. Use filename-derived
                # resolution for duplicate ranking, then probe only the
                # matched file before returning it.
                res = get_resolution(file)
                parsed_title, parsed_year = parse_movie_title(file)
                norm_path = _norm(full_path)
                plex_data = _plex_cache.get(norm_path, {})
                items_src.append({
                    'path': full_path,
                    'resolution': res,
                    'size_human': format_size(size),
                    'plex_title': plex_data.get('plex_title', ''),
                    'plex_year': str(plex_data.get('plex_year', '')),
                    'plex_matched': bool(plex_data),
                    '_parsed_title': parsed_title,
                    '_parsed_year': parsed_year,
                })

        for item in items_src:
            path = item.get('path', '')
            if not path or not os.path.isfile(path):
                continue
            parsed_title = item.get('_parsed_title')
            parsed_year = item.get('_parsed_year')
            if (not parsed_title or parsed_year is None) and item.get('filename'):
                parsed_title, parsed_year = parse_movie_title(item['filename'])
            if not parsed_title and item.get('title'):
                display_title, display_year = parse_movie_title(item['title'])
                parsed_title = display_title or item.get('title', '')
                parsed_year = parsed_year or display_year
            # Prefer Plex-matched title/year as primary key
            if item.get('plex_matched') and item.get('plex_title'):
                key = (_norm_title(item['plex_title']), str(item.get('plex_year', '')).strip())
            else:
                key = (_norm_title(parsed_title or ''),
                       str(parsed_year or '').strip())
            # Keep the highest-resolution copy per title
            existing = lookup.get(key)
            cur_rank = get_resolution_rank_str(item['resolution'])
            if existing is None or cur_rank > get_resolution_rank_str(existing['resolution']):
                lookup[key] = {
                    'path': item['path'],
                    'resolution': item['resolution'],
                    'size_human': item['size_human'],
                }

        results = []
        for q in queries:
            qt = _norm_title(q.get('title', ''))
            qy = str(q.get('year', '')).strip()
            # Try exact title+year first. Only fall back to title-only when the
            # query itself has no year; otherwise remakes/upcoming films can
            # false-match older local files.
            match = lookup.get((qt, qy))
            if match is None and not qy:
                for (kt, ky), v in lookup.items():
                    if kt == qt:
                        match = v
                        break
            if match and match.get('path') and os.path.isfile(match['path']):
                match_resolution = get_resolution_from_file(match['path'])
                results.append({
                    'title': q.get('title', ''),
                    'year': q.get('year', ''),
                    'found': True,
                    'path': match['path'],
                    'resolution': match_resolution,
                    'size_human': match['size_human'],
                })
            else:
                results.append({
                    'title': q.get('title', ''),
                    'year': q.get('year', ''),
                    'found': False,
                    'path': '',
                    'resolution': '',
                    'size_human': '',
                })
        return jsonify({'results': results})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/low-quality')
def low_quality():
    # Low quality = anything below 1080p (720p, 480p, Unknown resolution)
    MIN_RES_RANK = 3   # 1080p — only files BELOW this rank are flagged
    try:
        _auto_sync_plex(force=request.args.get('force_plex') == '1')
        items = []
        for movies_dir, root, file, full_path in _iter_video_files():
            try:
                size = os.path.getsize(full_path)
            except OSError:
                size = 0
            res = get_resolution_from_file(full_path)
            res_rank = get_resolution_rank_str(res)
            rip = get_rip_source(file)
            title_key = parse_movie_title(file)
            if not title_key[0]:
                continue
            is_low = res_rank < MIN_RES_RANK
            if is_low:
                display_title = title_key[0].title() + (f' ({title_key[1]})' if title_key[1] else '')
                norm_path = _norm(full_path)
                plex_data = _plex_cache.get(norm_path, {})
                items.append({
                    'title': display_title,
                    'filename': file,
                    'path': full_path,
                    'library_root': movies_dir,
                    'resolution': res,
                    'rip_source': rip,
                    'size': size,
                    'size_human': format_size(size),
                    'plex_title': plex_data.get('plex_title', ''),
                    'plex_year': plex_data.get('plex_year', ''),
                    'plex_genres': plex_data.get('plex_genres', []),
                    'plex_matched': bool(plex_data),
                })
        items.sort(key=lambda x: x['title'])
        return jsonify({'items': items, 'count': len(items),
                        'plex_enabled': bool(_plex_token), 'plex_cached': len(_plex_cache) > 0})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/smart-scan')
def smart_scan():
    try:
        duplicates, _ = scan_duplicates(get_movies_dirs())
        recommendations = []

        for group in duplicates:
            files = group['files']  # sorted best first by (resolution_rank, size)
            best = files[0]
            best_res_rank = best['resolution_rank']
            best_rip_rank = get_rip_rank(best['rip_source'])

            for f in files[1:]:
                reason = None
                skip_reason = None

                if f['resolution_rank'] < best_res_rank:
                    reason = f"Lower resolution ({f['resolution']} vs {best['resolution']})"

                elif f['resolution_rank'] == best_res_rank:
                    f_rip_rank = get_rip_rank(f['rip_source'])
                    if f_rip_rank < best_rip_rank:
                        if best['size'] > 0 and f['size'] > 0:
                            size_diff_pct = abs(best['size'] - f['size']) / max(best['size'], f['size']) * 100
                            if size_diff_pct < 5:
                                reason = f"Inferior source ({f['rip_source']} vs {best['rip_source']})"
                            else:
                                skip_reason = (
                                    f"Same resolution ({f['resolution']}) but inferior source "
                                    f"({f['rip_source']} vs {best['rip_source']}) — "
                                    f"size difference is {size_diff_pct:.1f}% (≥5%), manual review recommended"
                                )

                if reason:
                    recommendations.append({
                        'movie': group['title'],
                        'delete_path': f['path'],
                        'delete_filename': f['filename'],
                        'delete_resolution': f['resolution'],
                        'delete_rip': f['rip_source'],
                        'delete_size': f['size_human'],
                        'keep_filename': best['filename'],
                        'keep_resolution': best['resolution'],
                        'keep_rip': best['rip_source'],
                        'keep_size': best['size_human'],
                        'reason': reason,
                    })
                elif skip_reason:
                    recommendations.append({
                        'movie': group['title'],
                        'delete_path': None,  # skipped
                        'delete_filename': f['filename'],
                        'delete_resolution': f['resolution'],
                        'delete_rip': f['rip_source'],
                        'delete_size': f['size_human'],
                        'keep_filename': best['filename'],
                        'keep_resolution': best['resolution'],
                        'keep_rip': best['rip_source'],
                        'keep_size': best['size_human'],
                        'reason': skip_reason,
                        'skipped': True,
                    })

        return jsonify({'recommendations': recommendations})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/stats')
def library_stats():
    try:
        _auto_sync_plex(force=request.args.get('force_plex') == '1')
        all_files = []
        title_set = set()
        by_resolution = {}
        by_source = {}
        by_decade = {}
        RES_RANK = {'4K': 4, '1080p': 3, '720p': 2, '480p': 1, 'Unknown': 0}

        for movies_dir, root, file, full_path in _iter_video_files():
            try:
                size = os.path.getsize(full_path)
            except OSError:
                size = 0
            res = get_resolution_from_file(full_path)
            rip = get_rip_source(file)
            title_key = parse_movie_title(file)
            if not title_key[0]:
                continue
            title_set.add(title_key)
            display_title = title_key[0].title() + (f' ({title_key[1]})' if title_key[1] else '')
            all_files.append({
                'title': display_title,
                'path': full_path,
                'library_root': movies_dir,
                'size': size,
                'size_human': format_size(size),
                'resolution': res,
                'rip_source': rip,
                'year': title_key[1],
            })
            br = by_resolution.setdefault(res, {'count': 0, 'size': 0})
            br['count'] += 1
            br['size'] += size
            bs = by_source.setdefault(rip, {'count': 0, 'size': 0})
            bs['count'] += 1
            bs['size'] += size
            if title_key[1]:
                try:
                    decade = f"{(int(title_key[1]) // 10) * 10}s"
                except ValueError:
                    decade = 'Unknown'
            else:
                decade = 'Unknown'
            by_decade[decade] = by_decade.get(decade, 0) + 1

        # Duplicates
        duplicates, dup_stats = scan_duplicates(get_movies_dirs())

        # Low quality count
        lq_count = sum(1 for f in all_files if RES_RANK.get(f['resolution'], 0) < 3)

        total_size = sum(f['size'] for f in all_files)
        avg_size = total_size // len(all_files) if all_files else 0

        # Format sizes
        for k in by_resolution:
            by_resolution[k]['size_human'] = format_size(by_resolution[k]['size'])
        for k in by_source:
            by_source[k]['size_human'] = format_size(by_source[k]['size'])

        top_largest = sorted(all_files, key=lambda x: x['size'], reverse=True)[:10]

        plex_matched = None
        plex_unmatched = None
        if _plex_cache:
            plex_matched = sum(1 for f in all_files if _norm(f['path']) in _plex_cache)
            plex_unmatched = len(all_files) - plex_matched

        return jsonify({
            'total_files': len(all_files),
            'unique_titles': len(title_set),
            'total_size': total_size,
            'total_size_human': format_size(total_size),
            'avg_size': avg_size,
            'avg_size_human': format_size(avg_size),
            'duplicate_groups': dup_stats['groups'],
            'extra_copies': dup_stats['extra_copies'],
            'wasted_bytes': dup_stats['wasted_bytes'],
            'wasted_human': dup_stats['wasted_human'],
            'low_quality_count': lq_count,
            'by_resolution': by_resolution,
            'by_source': by_source,
            'by_decade': by_decade,
            'top_largest': top_largest,
            'plex_matched': plex_matched,
            'plex_unmatched': plex_unmatched,
            'plex_enabled': bool(_plex_token),
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── Fix Unmatched ──────────────────────────────────────────────────────────────

def _plex_rescan():
    """Trigger a Plex library refresh for all movie sections. Silent on errors."""
    if not _plex_url or not _plex_token or not _plex_section_ids:
        return
    for sid in _plex_section_ids:
        try:
            url = f"{_plex_url}/library/sections/{sid}/refresh?X-Plex-Token={_plex_token}"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=5):
                pass
        except Exception:
            pass


def _fmt_size(n):
    for unit in ('B', 'KB', 'MB', 'GB'):
        if n < 1024:
            return f'{n:.0f} {unit}'
        n /= 1024
    return f'{n:.1f} TB'


def _metadata_hint_for_unmatched(status, plex_entry, tmdb_data, rel_depth, unparseable):
    if status == 'pending':
        return 'Metadata is still settling for this new file — Plex or TMDB may accept it shortly'
    if status == 'conflict':
        return 'Plex and TMDB point to different movies — choose the correct metadata match'
    if status == 'needs_review':
        return 'TMDB found a possible match, but confidence is too low — review and apply the exact match'
    if plex_entry:
        return 'Plex found the file but has no metadata match — search Plex or choose a TMDB match'
    if tmdb_data:
        return 'TMDB candidate exists but is not accepted — review before applying it'
    if rel_depth > 1:
        return f'Folder is {rel_depth} levels deep — Plex may skip it. Use Fix Path if needed'
    if unparseable:
        return 'Filename cannot be parsed — rename it or search TMDB manually'
    return 'No accepted Plex or TMDB metadata — search TMDB or Plex to repair it'


def _fix_unmatched_v26():
    _auto_sync_plex(force=request.args.get('force_plex') == '1')
    refresh_metadata = request.args.get('refresh_metadata') == '1'
    store = _metadata_store()
    metadata_snapshot = store.snapshot()
    items = []
    for movies_dir, root, dirs, files in _walk_movie_dirs():
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext not in VIDEO_EXTENSIONS:
                continue
            full_path = os.path.join(root, file)
            norm_path = _norm(full_path)
            fname_lower = file.lower()
            title_key = parse_movie_title(file)
            unparseable = not title_key[0]
            suggested_title = title_key[0].title() if title_key[0] else ''
            suggested_year = title_key[1] if title_key else ''
            orig_res = get_resolution_from_file(full_path)
            orig_rip = get_rip_source(file)
            quality_tag = ' '.join(t for t in [orig_res, orig_rip] if t and t != 'Unknown')
            suggested_name = suggested_title + (f' ({suggested_year})' if suggested_year else '')
            if quality_tag:
                suggested_name += f' [{quality_tag}]'
            suggested_name = (suggested_name or os.path.splitext(file)[0]) + ext
            plex_entry = _plex_unmatched.get(norm_path) or _plex_unmatched_by_fname.get(fname_lower, {})
            plex_data = dict(_plex_cache.get(norm_path, {}) or _plex_matched_by_fname.get(fname_lower, {}) or {})
            plex_thumb = plex_data.get('plex_thumb', '')
            if plex_thumb and _plex_url and _plex_token:
                plex_data['plex_poster'] = f"{_plex_url}{plex_thumb}?X-Plex-Token={_plex_token}"
            try:
                added_time = os.path.getctime(full_path)
            except OSError:
                added_time = 0
            file_facts = {
                'path': full_path,
                'filename': file,
                'library_root': movies_dir,
                'parsed_title': title_key[0],
                'parsed_year': title_key[1],
                'resolution': orig_res,
                'rip_source': orig_rip,
                'added_time': added_time,
            }
            tmdb_data = _tmdb_metadata_for_file(file_facts, plex_data=plex_data, store=store,
                                                refresh=refresh_metadata, snapshot=metadata_snapshot)
            canonical = _build_canonical_metadata(
                file_facts,
                plex_data=plex_data,
                tmdb_data=tmdb_data,
                manual_match=store.get_manual_match_from_snapshot(full_path, metadata_snapshot),
            )
            if canonical.get('accepted'):
                continue
            rel_depth = len(os.path.relpath(full_path, movies_dir).split(os.sep)) - 1
            metadata_hint = _metadata_hint_for_unmatched(canonical.get('status'), plex_entry, tmdb_data, rel_depth, unparseable)
            try:
                file_size = _fmt_size(os.path.getsize(full_path))
            except OSError:
                file_size = '?'
            items.append({
                'filename': file,
                'path': full_path,
                'library_root': movies_dir,
                'suggested_title': suggested_title,
                'suggested_year': suggested_year,
                'suggested_name': suggested_name,
                'resolution': orig_res,
                'rip_source': orig_rip,
                'file_size': file_size,
                'folder': root,
                'depth': rel_depth,
                'fixable_path': rel_depth > 1,
                'in_plex': bool(plex_entry or plex_data),
                'rating_key': plex_entry.get('rating_key', ''),
                'plex_title': plex_entry.get('plex_title', '') or plex_data.get('plex_title', ''),
                'plex_year': plex_data.get('plex_year', ''),
                'plex_matched': bool(plex_data),
                'tmdb_id': canonical.get('tmdb_id', '') or tmdb_data.get('tmdb_id', ''),
                'tmdb_title': canonical.get('tmdb_title', '') or tmdb_data.get('title', ''),
                'tmdb_year': canonical.get('tmdb_year', '') or tmdb_data.get('year', ''),
                'tmdb_poster_url': tmdb_data.get('poster_url', ''),
                'metadata_status': canonical.get('status', 'unmatched'),
                'metadata_hint': metadata_hint,
                'unparseable': unparseable,
                'plex_hint': metadata_hint,
            })
    items.sort(key=lambda x: (x.get('metadata_status') != 'conflict', x['filename'].lower()))
    return jsonify({'items': items, 'count': len(items),
                    'plex_enabled': bool(_plex_token), 'tmdb_enabled': bool(_tmdb_key)})


@app.route('/api/fix-unmatched')
def fix_unmatched():
    return _fix_unmatched_v26()
    try:
        _auto_sync_plex(force=request.args.get('force_plex') == '1')
        items = []
        for movies_dir, root, dirs, files in _walk_movie_dirs():
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext not in VIDEO_EXTENSIONS:
                    continue
                full_path  = os.path.join(root, file)
                norm_path  = _norm(full_path)
                fname_lower = file.lower()
                # Skip if already matched — full-path lookup first, filename fallback second
                if norm_path in _plex_cache or fname_lower in _plex_matched_by_fname:
                    continue
                title_key = parse_movie_title(file)
                unparseable = not title_key[0]
                suggested_title = title_key[0].title() if title_key[0] else ''
                suggested_year  = title_key[1] if title_key else ''
                orig_res = get_resolution_from_file(full_path)
                orig_rip = get_rip_source(file)
                quality_tag = ' '.join(t for t in [orig_res, orig_rip] if t and t != 'Unknown')
                suggested_name = suggested_title + (f' ({suggested_year})' if suggested_year else '')
                if quality_tag:
                    suggested_name += f' [{quality_tag}]'
                suggested_name += ext
                # Look up Plex entry — full-path first, filename fallback second
                plex_entry = _plex_unmatched.get(norm_path) or \
                             _plex_unmatched_by_fname.get(fname_lower, {})
                rel_depth = len(os.path.relpath(full_path, movies_dir).split(os.sep)) - 1
                # Build a diagnostic hint so the UI can explain WHY the file is unmatched
                if plex_entry:
                    plex_hint = 'Plex found the file but has no metadata match — use Match in Plex'
                elif rel_depth > 1:
                    plex_hint = (f'Folder is {rel_depth} levels deep — Plex skips it. '
                                 'Use Fix Path to move it up')
                elif unparseable:
                    plex_hint = 'Filename cannot be parsed — rename it so Plex can identify it'
                else:
                    plex_hint = 'Plex has not indexed this file yet — try Scan Plex Library'
                items.append({
                    'filename': file,
                    'path': full_path,
                    'library_root': movies_dir,
                    'suggested_title': suggested_title,
                    'suggested_year':  suggested_year,
                    'suggested_name':  suggested_name,
                    'resolution': orig_res,
                    'rip_source': orig_rip,
                    'file_size': _fmt_size(os.path.getsize(full_path)),
                    'folder':    root,
                    'depth': rel_depth,
                    'fixable_path': rel_depth > 1,
                    'in_plex':    bool(plex_entry),
                    'rating_key': plex_entry.get('rating_key', ''),
                    'plex_title': plex_entry.get('plex_title', ''),
                    'unparseable': unparseable,
                    'plex_hint':   plex_hint,
                })
        items.sort(key=lambda x: x['filename'].lower())
        return jsonify({'items': items, 'count': len(items),
                        'plex_enabled': bool(_plex_token)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/rename-file', methods=['POST'])
def rename_file():
    data = request.get_json(silent=True)
    if not data or 'path' not in data:
        return jsonify({'error': 'No path provided'}), 400
    old_path  = data['path']
    new_title = data.get('title', '').strip()
    new_year  = data.get('year', '').strip()
    if not new_title:
        return jsonify({'error': 'Title is required'}), 400

    abs_old = os.path.abspath(old_path)
    abs_dir = _path_library_root(abs_old)
    if not abs_dir:
        return jsonify({'error': 'Path is outside the allowed movies directory'}), 403
    if not os.path.isfile(abs_old):
        return jsonify({'error': 'File not found'}), 404

    ext = os.path.splitext(abs_old)[1]
    orig_basename = os.path.basename(abs_old)
    orig_res = get_resolution_from_file(abs_old)
    orig_rip = get_rip_source(orig_basename)
    quality_tag = ' '.join(t for t in [orig_res, orig_rip] if t and t != 'Unknown')
    new_filename = new_title + (f' ({new_year})' if new_year else '')
    if quality_tag:
        new_filename += f' [{quality_tag}]'
    new_filename += ext
    # Strip characters not allowed in Windows filenames
    new_filename = re.sub(r'[<>:"/\\|?*]', '', new_filename).strip()
    new_path = os.path.join(os.path.dirname(abs_old), new_filename)

    if os.path.exists(new_path) and os.path.normpath(new_path) != os.path.normpath(abs_old):
        return jsonify({'error': f'A file named "{new_filename}" already exists in that folder'}), 409

    try:
        os.rename(abs_old, new_path)
        # Remove old path from caches
        old_norm = _norm(abs_old)
        _plex_cache.pop(old_norm, None)
        _plex_unmatched.pop(old_norm, None)
        _library_cache.pop('items', None)  # bust library cache — filename/path changed
        # Ask Plex to rescan so it picks up the renamed file
        _plex_rescan()
        return jsonify({'success': True, 'new_path': new_path, 'new_filename': new_filename})
    except OSError as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/plex/force-scan', methods=['POST'])
def plex_force_scan():
    global _plex_cache_time
    if not _plex_url or not _plex_token:
        return jsonify({'error': 'Plex not configured'}), 400
    try:
        _plex_rescan()
        _plex_cache_time = 0.0
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/fix-path', methods=['POST'])
def fix_path():
    """Move a file (or its containing folder) one directory level up so Plex can find it.
    When the parent folder contains only this one video file, the whole folder is moved
    so Plex retains the folder-name metadata hint (e.g. 'Batman (2010)') after the move.
    Only allowed on files that are NOT already in Plex's matched cache."""
    data = request.get_json(silent=True)
    if not data or 'path' not in data:
        return jsonify({'error': 'No path provided'}), 400

    abs_path = os.path.abspath(data['path'])
    abs_dir  = _path_library_root(abs_path)
    if not abs_dir:
        return jsonify({'error': 'Path is outside the allowed movies directory'}), 403
    if not os.path.isfile(abs_path):
        return jsonify({'error': 'File not found'}), 404

    # Safety: refuse to move files Plex already matched (full-path check + filename fallback)
    norm = _norm(abs_path)
    fname_lower = os.path.basename(abs_path).lower()
    if norm in _plex_cache or fname_lower in _plex_matched_by_fname:
        return jsonify({'error': 'This file is already matched in Plex — not moving it'}), 409

    parent      = os.path.dirname(abs_path)
    grandparent = os.path.dirname(parent)

    # Grandparent must still be inside (or equal to) the movies root
    if not (os.path.normpath(grandparent) == os.path.normpath(abs_dir) or
            os.path.normpath(grandparent).startswith(os.path.normpath(abs_dir) + os.sep)):
        return jsonify({'error': 'Cannot move file — destination would be outside library'}), 400

    # Decide: move entire folder or just the file?
    # Count video files in parent to decide.
    _JUNK = {'desktop.ini', 'thumbs.db', '.ds_store', 'folder.jpg', 'folder.png'}
    try:
        sibling_videos = [
            f for f in os.listdir(parent)
            if os.path.splitext(f)[1].lower() in VIDEO_EXTENSIONS
        ]
    except OSError:
        sibling_videos = [os.path.basename(abs_path)]

    try:
        parent_name = os.path.basename(parent)
        # Use whole-folder move only when:
        #   1. There is exactly one video in the folder (folder acts as a Plex hint), AND
        #   2. The folder name contains a year — i.e. it looks like a movie title.
        # Generic names like "Downloads", "1080p", "Featurettes" would be useless as a hint.
        use_folder_move = (len(sibling_videos) == 1 and
                           bool(_MOVIE_FOLDER_RE.search(parent_name)))

        if use_folder_move:
            # ── Whole-folder move ────────────────────────────────────────────
            # Move the folder one level up so Plex can discover it using the
            # folder name (e.g. "Batman (2010)") as a metadata hint.
            great_grandparent = os.path.dirname(grandparent)
            dest_folder = os.path.join(great_grandparent, parent_name)
            if os.path.normpath(dest_folder) == os.path.normpath(parent):
                return jsonify({'error': 'File is already at the correct depth — no move needed'}), 409
            if os.path.exists(dest_folder):
                return jsonify({'error': f'A folder named "{parent_name}" already exists in the destination'}), 409
            os.rename(parent, dest_folder)
            new_path = os.path.join(dest_folder, os.path.basename(abs_path))
            _plex_cache.pop(norm, None)
            _plex_unmatched.pop(norm, None)
        else:
            # ── File-only move (multiple videos, or generic folder name) ──────
            new_path = os.path.join(grandparent, os.path.basename(abs_path))
            if os.path.normpath(new_path) == os.path.normpath(abs_path):
                return jsonify({'error': 'File is already at the correct depth — no move needed'}), 409
            if os.path.exists(new_path):
                return jsonify({'error': f'A file named "{os.path.basename(abs_path)}" already exists in the destination folder'}), 409
            os.rename(abs_path, new_path)
            # Try to clean up junk files and remove folder if now empty
            try:
                for f in os.listdir(parent):
                    if f.lower() in _JUNK:
                        try:
                            os.remove(os.path.join(parent, f))
                        except OSError:
                            pass
            except OSError:
                pass
            try:
                os.rmdir(parent)
            except OSError:
                pass
            _plex_cache.pop(norm, None)
            _plex_unmatched.pop(norm, None)

        # Ask Plex to rescan so it picks up the new location
        _plex_rescan()
        return jsonify({'success': True, 'new_path': new_path})
    except OSError as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/plex/match-search')
def plex_match_search():
    if not _plex_url or not _plex_token:
        return jsonify({'error': 'Plex not configured'}), 400
    rating_key = request.args.get('rating_key', '').strip()
    title      = request.args.get('title', '').strip()
    year       = request.args.get('year', '').strip()
    if not rating_key:
        return jsonify({'error': 'rating_key is required'}), 400
    try:
        params = {k: v for k, v in {'title': title, 'year': year}.items() if v}
        qs = urllib.parse.urlencode(params)
        sep = '&' if qs else '?'
        url = f"{_plex_url}/library/metadata/{rating_key}/matches?{qs}{sep}X-Plex-Token={_plex_token}"
        req = urllib.request.Request(url, headers={'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = _json.loads(resp.read().decode())
        results = []
        for r in data.get('MediaContainer', {}).get('SearchResult', []):
            results.append({
                'name':  r.get('name', ''),
                'year':  str(r.get('year', '')),
                'guid':  r.get('guid', ''),
                'score': r.get('score', 0),
            })
        return jsonify({'results': results})
    except urllib.error.HTTPError as e:
        return jsonify({'error': f'Plex returned HTTP {e.code}'}), 502
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/plex/match-apply', methods=['POST'])
def plex_match_apply():
    global _plex_cache_time, _library_cache
    if not _plex_url or not _plex_token:
        return jsonify({'error': 'Plex not configured'}), 400
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    rating_key = data.get('rating_key', '').strip()
    guid       = data.get('guid', '').strip()
    name       = data.get('name', '').strip()
    path       = data.get('path', '').strip()
    if not rating_key or not guid:
        return jsonify({'error': 'rating_key and guid are required'}), 400
    try:
        # Apply the match
        params = urllib.parse.urlencode({'guid': guid, 'name': name})
        url = f"{_plex_url}/library/metadata/{rating_key}/match?{params}&X-Plex-Token={_plex_token}"
        req = urllib.request.Request(url, method='PUT')
        req.add_header('Content-Length', '0')
        with urllib.request.urlopen(req, timeout=15):
            pass
        # Refresh the item's metadata from the agent
        url2 = f"{_plex_url}/library/metadata/{rating_key}/refresh?X-Plex-Token={_plex_token}"
        req2 = urllib.request.Request(url2, method='PUT')
        req2.add_header('Content-Length', '0')
        with urllib.request.urlopen(req2, timeout=10):
            pass
        # Force plex cache refresh next time
        _plex_cache_time = 0.0
        if path:
            abs_path = os.path.abspath(path)
            if _path_library_root(abs_path):
                _metadata_store().apply_plex_match(abs_path, {
                    'rating_key': rating_key,
                    'plex_title': name,
                    'plex_year': str(data.get('year', '') or ''),
                    'plex_guid': guid,
                })
        _library_cache.pop('items', None)
        return jsonify({'success': True})
    except urllib.error.HTTPError as e:
        return jsonify({'error': f'Plex returned HTTP {e.code}'}), 502
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── TMDB / Trending ──────────────────────────────────────────────────────────

@app.route('/api/tmdb/config', methods=['GET'])
def get_tmdb_config():
    return jsonify({'key': _tmdb_key, 'include_adult': _tmdb_include_adult})


@app.route('/api/tmdb/config', methods=['POST'])
def set_tmdb_config():
    global _tmdb_key, _tmdb_include_adult, _tmdb_genres
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    _tmdb_key = data.get('key', '').strip()
    if 'include_adult' in data:
        _tmdb_include_adult = _coerce_bool(data.get('include_adult'), False)
    _tmdb_genres = {}  # reset genre cache when key changes
    _save_config(_all_config())
    return jsonify({'success': True})


@app.route('/api/tmdb/test')
def tmdb_test():
    key = request.args.get('key', _tmdb_key).strip()
    if not key:
        return jsonify({'error': 'No API key — enter your TMDB key in Settings.'}), 400
    try:
        url = f"https://api.themoviedb.org/3/configuration?api_key={urllib.parse.quote(key)}"
        req = urllib.request.Request(url, headers={'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=8) as resp:
            _json.loads(resp.read().decode())
        return jsonify({'success': True})
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return jsonify({'error': 'Invalid API key — check your TMDB account settings.'}), 401
        return jsonify({'error': f'TMDB returned HTTP {e.code}'}), 502
    except Exception as e:
        return jsonify({'error': f'Cannot reach TMDB: {e}'}), 502


def _ensure_tmdb_genres():
    """Lazy-load TMDB genre list into _tmdb_genres. Silent on error."""
    global _tmdb_genres
    if _tmdb_genres or not _tmdb_key:
        return
    try:
        url = f"https://api.themoviedb.org/3/genre/movie/list?api_key={urllib.parse.quote(_tmdb_key)}&language=en"
        req = urllib.request.Request(url, headers={'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = _json.loads(resp.read().decode())
        _tmdb_genres = {g['id']: g['name'] for g in data.get('genres', [])}
    except Exception:
        pass


def _tmdb_include_adult_value(value=None):
    return 'true' if _coerce_bool(value, _tmdb_include_adult) else 'false'


@app.route('/api/metadata')
def get_metadata():
    title = request.args.get('title', '').strip()
    year  = request.args.get('year', '').strip()
    if not title:
        return jsonify({'error': 'title is required'}), 400
    cache_key = f"{title.lower()}_{year}"
    if cache_key in _metadata_cache:
        return jsonify(_metadata_cache[cache_key])
    if not _tmdb_key:
        return jsonify({'poster_url': '', 'genres': [], 'plot': '', 'tmdb_rating': '', 'tmdb_vote_count': 0})
    _ensure_tmdb_genres()
    try:
        params = urllib.parse.urlencode({
            'query': title,
            'api_key': _tmdb_key,
            'language': 'en-US',
            'page': 1,
            'include_adult': _tmdb_include_adult_value(),
        })
        if year:
            params += '&year=' + urllib.parse.quote(year)
        url = f"https://api.themoviedb.org/3/search/movie?{params}"
        req = urllib.request.Request(url, headers={'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = _json.loads(resp.read().decode())
        results = data.get('results', [])
        result = results[0] if results else {}
        poster_path = result.get('poster_path', '')
        poster_url  = f"https://image.tmdb.org/t/p/w342{poster_path}" if poster_path else ''
        genre_ids   = result.get('genre_ids', [])
        genres      = [_tmdb_genres[gid] for gid in genre_ids if gid in _tmdb_genres][:3]
        plot        = result.get('overview', '')
        vote        = result.get('vote_average', 0)
        tmdb_rating = f"{vote:.1f}" if isinstance(vote, (int, float)) and vote else ''
        meta = {'poster_url': poster_url, 'genres': genres, 'plot': plot, 'tmdb_rating': tmdb_rating,
                'tmdb_vote_count': int(result.get('vote_count', 0) or 0), 'tmdb_id': result.get('id', None)}
        _metadata_cache[cache_key] = meta
        return jsonify(meta)
    except urllib.error.HTTPError as e:
        return jsonify({'error': f'TMDB returned HTTP {e.code}'}), 502
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/explore/browse')
def explore_browse():
    browse_query = request.args.get('q', '').strip()
    latest = request.args.get('latest') == '1'
    selected_indexer_id = request.args.get('indexer_id', '').strip()
    if not browse_query and not latest:
        return jsonify({'results': [], 'tmdb_enabled': bool(_tmdb_key), 'all_indexers': [], 'requires_query': True})
    if not _prowlarr_url or not _prowlarr_key:
        return jsonify({'error': 'Prowlarr not configured — click ⚙ Settings to enter your Prowlarr URL and API key.'}), 400
    try:
        # Fetch all enabled indexer IDs
        indexers = []
        try:
            indexers = _fetch_enabled_prowlarr_indexers()
        except Exception:
            pass
        indexer_ids = [ix['id'] for ix in indexers]
        if selected_indexer_id:
            if selected_indexer_id not in indexer_ids:
                return jsonify({'error': 'Selected indexer is not available in Prowlarr.'}), 400
            indexer_ids = [selected_indexer_id]
        indexer_names = [ix['name'] for ix in indexers]

        def _fetch(query=''):
            parts = [('query', query), ('type', 'search'), ('categories', '2000'), ('limit', '100')]
            parts += [('indexerIds', iid) for iid in indexer_ids]
            url = f"{_prowlarr_url}/api/v1/search?{urllib.parse.urlencode(parts)}"
            req = urllib.request.Request(url, headers={'X-Api-Key': _prowlarr_key, 'Accept': 'application/json'})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return _json.loads(resp.read().decode())

        results = _fetch(browse_query)
        if not browse_query and len(results) < 20:
            fallback = _fetch('2025')
            if len(fallback) > len(results):
                results = fallback

        # Build deduplicated movie list
        movies = {}  # key -> {parsed_title, parsed_year, variants[]}
        for r in results:
            title = r.get('title', '')
            # Skip TV episodes
            if _TV_RE.search(title):
                continue
            tl = title.lower()
            res = 'Unknown'
            if '2160p' in tl or '4k' in tl or 'uhd' in tl:
                res = '4K'
            elif '1080p' in tl or re.search(r'[\.\-_ \[\(]1080[\.\-_ \]\)\[]', tl):
                res = '1080p'
            elif '720p' in tl or re.search(r'[\.\-_ \[\(]720[\.\-_ \]\)\[]', tl):
                res = '720p'
            elif '480p' in tl or re.search(r'[\.\-_ \[\(]480[\.\-_ \]\)\[]', tl):
                res = '480p'
            parsed = parse_movie_title(title)
            parsed_title = parsed[0].title() if parsed[0] else title
            parsed_year  = parsed[1] or ''
            size = r.get('size', 0)
            variant = {
                'resolution': res,
                'seeders': r.get('seeders', 0),
                'magnet_url': r.get('magnetUrl', ''),
                'download_url': r.get('downloadUrl', ''),
                'info_url': r.get('infoUrl', ''),
                'indexer': r.get('indexer', ''),
                'size_human': format_size(size) if size else '?',
                'title': title,
            }
            key = f"{parsed_title.lower()}_{parsed_year}"
            if key not in movies:
                movies[key] = {'parsed_title': parsed_title, 'parsed_year': parsed_year, 'variants': [variant]}
            else:
                movies[key]['variants'].append(variant)

        # Sort variants within each movie by seeders desc; deduplicate by resolution (keep best per res)
        processed = []
        for m in movies.values():
            by_res = {}
            for v in m['variants']:
                r = v['resolution']
                if r not in by_res or v['seeders'] > by_res[r]['seeders']:
                    by_res[r] = v
            RES_ORDER = ['4K', '1080p', '720p', '480p', 'Unknown']
            variants  = [by_res[r] for r in RES_ORDER if r in by_res]
            best = variants[0]
            processed.append({
                'parsed_title': m['parsed_title'],
                'parsed_year':  m['parsed_year'],
                'best_seeders': best['seeders'],
                'best_resolution': best['resolution'],
                'indexer': best['indexer'],
                'variants': variants,
            })

        processed.sort(key=lambda x: x['best_seeders'], reverse=True)
        return jsonify({
            'results': processed[:100],
            'tmdb_enabled': bool(_tmdb_key),
            'all_indexers': sorted(indexer_names),
            'indexers': sorted(indexers, key=lambda ix: ix['name'].lower()),
            'selected_indexer_id': selected_indexer_id,
        })
    except urllib.error.HTTPError as e:
        return jsonify({'error': f'Prowlarr returned HTTP {e.code}'}), 502
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/explore/indexers')
def explore_indexers():
    if not _prowlarr_url or not _prowlarr_key:
        return jsonify({'error': 'Prowlarr not configured â€” click âš™ Settings to enter your Prowlarr URL and API key.'}), 400
    try:
        return jsonify({'indexers': sorted(_fetch_enabled_prowlarr_indexers(), key=lambda ix: ix['name'].lower())})
    except urllib.error.HTTPError as e:
        return jsonify({'error': f'Prowlarr returned HTTP {e.code}'}), 502
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/tmdb/discover')
def tmdb_discover():
    if not _tmdb_key:
        return jsonify({'error': 'TMDB key not configured — add it in ⚙ Settings.'}), 400
    list_name = request.args.get('list', 'trending_week')
    genre_id  = request.args.get('genre', '').strip()
    min_votes = request.args.get('min_votes', '').strip()
    year_from = request.args.get('year_from', '').strip()
    year_to = request.args.get('year_to', '').strip()
    min_rating = request.args.get('min_rating', '').strip()
    sort_override = request.args.get('sort', '').strip()
    try:
        page = max(1, min(int(request.args.get('page', '1')), 10))
    except ValueError:
        page = 1
    try:
        page_size = int(request.args.get('page_size', '20'))
    except ValueError:
        page_size = 20
    page_size = 40 if page_size >= 40 else 20

    # Sort strategy per list when using genre filter via /discover/movie
    _list_sort = {
        'trending_week': 'popularity.desc',
        'trending_today': 'popularity.desc',
        'now_playing':   'popularity.desc',
        'popular':       'popularity.desc',
        'upcoming':      'primary_release_date.desc',
        'top_rated':     'vote_average.desc',
        'best_all_time': 'vote_count.desc',
    }

    _ensure_tmdb_genres()
    try:
        advanced_discover = bool(genre_id or year_from or year_to or min_rating or min_votes or sort_override)
        tmdb_pages = [page]
        if page_size == 40:
            tmdb_pages = [(page - 1) * 2 + 1, (page - 1) * 2 + 2]

        if advanced_discover:
            sort_by = sort_override or _list_sort.get(list_name, 'popularity.desc')
            params = urllib.parse.urlencode({
                'api_key':        _tmdb_key,
                'language':       'en-US',
                'sort_by':        sort_by,
                'page':           tmdb_pages[0],
            })
            if genre_id:
                params += '&with_genres=' + urllib.parse.quote(genre_id)
            if min_votes:
                params += '&vote_count.gte=' + urllib.parse.quote(min_votes)
            elif genre_id:
                params += '&vote_count.gte=50'
            if year_from:
                params += '&primary_release_date.gte=' + urllib.parse.quote(f'{year_from}-01-01')
            if year_to:
                params += '&primary_release_date.lte=' + urllib.parse.quote(f'{year_to}-12-31')
            if min_rating:
                params += '&vote_average.gte=' + urllib.parse.quote(min_rating)
            if list_name == 'top_rated':
                params += '&vote_average.gte=6.0'
            elif list_name == 'best_all_time':
                params += f"&vote_average.gte=7.5&vote_count.gte={urllib.parse.quote(min_votes or '5000')}"
            url = f"https://api.themoviedb.org/3/discover/movie?{params}"
        elif list_name == 'best_all_time':
            params = urllib.parse.urlencode({
                'api_key':            _tmdb_key,
                'language':           'en-US',
                'sort_by':            'vote_count.desc',
                'vote_average.gte':   '7.5',
                'vote_count.gte':     min_votes or '5000',
                'page':               tmdb_pages[0],
            })
            url = f"https://api.themoviedb.org/3/discover/movie?{params}"
        elif list_name == 'trending_today':
            url = (f"https://api.themoviedb.org/3/trending/movie/day"
                   f"?api_key={urllib.parse.quote(_tmdb_key)}&language=en-US&page={tmdb_pages[0]}")
        else:
            endpoint_map = {
                'trending_week': 'https://api.themoviedb.org/3/trending/movie/week',
                'now_playing':   'https://api.themoviedb.org/3/movie/now_playing',
                'popular':       'https://api.themoviedb.org/3/movie/popular',
                'upcoming':      'https://api.themoviedb.org/3/movie/upcoming',
                'top_rated':     'https://api.themoviedb.org/3/movie/top_rated',
            }
            base_url = endpoint_map.get(list_name, endpoint_map['trending_week'])
            url = f"{base_url}?api_key={urllib.parse.quote(_tmdb_key)}&language=en-US&page={tmdb_pages[0]}"

        data = {'results': [], 'total_pages': 1, 'total_results': 0}
        urls = [url]
        if page_size == 40:
            if 'page=' in url:
                urls.append(re.sub(r'page=\d+', f'page={tmdb_pages[1]}', url))
            else:
                urls.append(url + f'&page={tmdb_pages[1]}')
        for index, page_url in enumerate(urls):
            req = urllib.request.Request(page_url, headers={'Accept': 'application/json'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                page_data = _json.loads(resp.read().decode())
            if index == 0:
                data['total_pages'] = page_data.get('total_pages', 1)
                data['total_results'] = page_data.get('total_results', 0)
            data['results'].extend(page_data.get('results', []))
        movies = []
        for m in data.get('results', []):
            poster_path = m.get('poster_path', '')
            release = m.get('release_date', '') or ''
            year    = release[:4] if release else ''
            genre_ids = m.get('genre_ids', [])
            genres  = [_tmdb_genres[gid] for gid in genre_ids if gid in _tmdb_genres][:3]
            vote    = m.get('vote_average', 0)
            lang    = m.get('original_language', '')
            countries = m.get('origin_country', [])
            country_code = countries[0] if countries else _LANG_COUNTRY.get(lang, '')
            movies.append({
                'tmdb_id':    m.get('id'),
                'title':      m.get('title', ''),
                'year':       year,
                'poster_url': f"https://image.tmdb.org/t/p/w342{poster_path}" if poster_path else '',
                'genres':     genres,
                'tmdb_rating': f"{vote:.1f}" if isinstance(vote, (int, float)) and vote else '',
                'tmdb_vote_count': int(m.get('vote_count', 0) or 0),
                'plot':       m.get('overview', ''),
                'language':   _LANG_NAMES.get(lang, lang.upper() if lang else ''),
                'country':    country_code,
                'country_flag': _country_flag(country_code),
                'adult': bool(m.get('adult', False)),
            })
        total_pages = int(data.get('total_pages', 1) or 1)
        if page_size == 40:
            total_pages = (total_pages + 1) // 2
        return jsonify({
            'results': movies[:page_size],
            'total_pages': min(total_pages, 10),
            'page': page,
            'total_results': data.get('total_results', len(movies)),
        })
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return jsonify({'error': 'Invalid TMDB API key — check Settings.'}), 401
        return jsonify({'error': f'TMDB returned HTTP {e.code}'}), 502
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/explore/search')
def explore_search():
    title = request.args.get('title', '').strip()
    year  = request.args.get('year', '').strip()
    if not title:
        return jsonify({'error': 'title required'}), 400
    if not _prowlarr_url or not _prowlarr_key:
        return jsonify({'error': 'Prowlarr not configured — add it in ⚙ Settings.'}), 400
    query = f"{title} {year}".strip()
    try:
        indexer_ids = []
        try:
            idx_req = urllib.request.Request(
                f"{_prowlarr_url}/api/v1/indexer",
                headers={'X-Api-Key': _prowlarr_key, 'Accept': 'application/json'}
            )
            with urllib.request.urlopen(idx_req, timeout=8) as idx_resp:
                indexers = _json.loads(idx_resp.read().decode())
            indexer_ids = [str(ix['id']) for ix in indexers if ix.get('enable', True)]
        except Exception:
            pass
        parts = [('query', query), ('type', 'search'), ('categories', '2000'), ('limit', '100')]
        parts += [('indexerIds', iid) for iid in indexer_ids]
        url = f"{_prowlarr_url}/api/v1/search?{urllib.parse.urlencode(parts)}"
        req = urllib.request.Request(url, headers={'X-Api-Key': _prowlarr_key, 'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=30) as resp:
            results = _json.loads(resp.read().decode())
        hd_variants = []
        fallback_variants = []
        for r in results:
            t = r.get('title', '')
            if _TV_RE.search(t):
                continue
            tl = t.lower()
            res = 'Unknown'
            if '2160p' in tl or '4k' in tl or 'uhd' in tl:
                res = '4K'
            elif '1080p' in tl or re.search(r'[.\-_ \[(]1080[.\-_ \])]', tl):
                res = '1080p'
            elif '720p' in tl or re.search(r'[.\-_ \[(]720[.\-_ \])]', tl):
                res = '720p'
            elif '480p' in tl or re.search(r'[.\-_ \[(]480[.\-_ \])]', tl):
                res = '480p'
            size = r.get('size', 0)
            seeders = r.get('seeders', 0)
            entry = {
                'resolution': res, 'seeders': seeders,
                'magnet_url': r.get('magnetUrl', ''),
                'download_url': r.get('downloadUrl', ''),
                'info_url': r.get('infoUrl', ''),
                'indexer': r.get('indexer', ''),
                'size_human': format_size(size) if size else '?',
                'size_bytes': size,
                'title': t,
            }
            if res in ('4K', '1080p'):
                hd_variants.append(entry)
            else:
                fallback_variants.append(entry)
        # Sort: 4K first, then 1080p, within group by seeders desc
        hd_variants.sort(key=lambda x: (0 if x['resolution'] == '4K' else 1, -x['seeders']))
        if hd_variants:
            variants = hd_variants
        else:
            fallback_variants.sort(key=lambda x: -x['seeders'])
            variants = fallback_variants
        return jsonify({'variants': variants})
    except urllib.error.HTTPError as e:
        return jsonify({'error': f'Prowlarr returned HTTP {e.code}'}), 502
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/tmdb/search')
def tmdb_search():
    if not _tmdb_key:
        return jsonify({'error': 'TMDB key not configured — add it in ⚙ Settings.'}), 400
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({'error': 'q (query) parameter required'}), 400
    year = request.args.get('year', '').strip()
    min_votes_raw = request.args.get('min_votes', '').strip()
    try:
        min_votes = int(min_votes_raw or 0)
    except ValueError:
        min_votes = 0
    try:
        page = max(1, min(int(request.args.get('page', '1')), 10))
    except ValueError:
        page = 1
    try:
        page_size = int(request.args.get('page_size', '20'))
    except ValueError:
        page_size = 20
    page_size = 40 if page_size >= 40 else 20
    _ensure_tmdb_genres()
    try:
        tmdb_pages = [page]
        if page_size == 40:
            tmdb_pages = [(page - 1) * 2 + 1, (page - 1) * 2 + 2]
        params = urllib.parse.urlencode({
            'query': q, 'api_key': _tmdb_key,
            'language': 'en-US',
            'page': tmdb_pages[0],
            'include_adult': _tmdb_include_adult_value(request.args.get('include_adult')),
        })
        if year:
            params += '&year=' + urllib.parse.quote(year)
        url = f"https://api.themoviedb.org/3/search/movie?{params}"
        data = {'results': [], 'total_pages': 1, 'total_results': 0}
        urls = [url]
        if page_size == 40:
            urls.append(re.sub(r'page=\d+', f'page={tmdb_pages[1]}', url))
        for index, page_url in enumerate(urls):
            req = urllib.request.Request(page_url, headers={'Accept': 'application/json'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                page_data = _json.loads(resp.read().decode())
            if index == 0:
                data['total_pages'] = page_data.get('total_pages', 1)
                data['total_results'] = page_data.get('total_results', 0)
            data['results'].extend(page_data.get('results', []))
        movies = []
        for m in data.get('results', []):
            vote_count = int(m.get('vote_count', 0) or 0)
            if min_votes and vote_count < min_votes:
                continue
            poster_path = m.get('poster_path', '')
            release = m.get('release_date', '') or ''
            year    = release[:4] if release else ''
            genre_ids = m.get('genre_ids', [])
            genres  = [_tmdb_genres[gid] for gid in genre_ids if gid in _tmdb_genres][:3]
            vote    = m.get('vote_average', 0)
            lang    = m.get('original_language', '')
            country_code = _LANG_COUNTRY.get(lang, '')
            movies.append({
                'tmdb_id':    m.get('id'),
                'title':      m.get('title', ''),
                'year':       year,
                'poster_url': f"https://image.tmdb.org/t/p/w342{poster_path}" if poster_path else '',
                'genres':     genres,
                'tmdb_rating': f"{vote:.1f}" if isinstance(vote, (int, float)) and vote else '',
                'tmdb_vote_count': vote_count,
                'plot':       m.get('overview', ''),
                'language':   _LANG_NAMES.get(lang, lang.upper() if lang else ''),
                'country':    country_code,
                'country_flag': _country_flag(country_code),
            })
        return jsonify({
            'results': movies[:page_size],
            'total_pages': min(((int(data.get('total_pages', 1) or 1) + 1) // 2) if page_size == 40 else int(data.get('total_pages', 1) or 1), 10),
            'page': page,
            'total_results': data.get('total_results', 0),
        })
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return jsonify({'error': 'Invalid TMDB API key — check Settings.'}), 401
        return jsonify({'error': f'TMDB returned HTTP {e.code}'}), 502
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/tmdb/match-apply', methods=['POST'])
def tmdb_match_apply():
    global _library_cache
    body = request.get_json(force=True, silent=True) or {}
    path = str(body.get('path', '') or '').strip()
    tmdb_id = str(body.get('tmdb_id', '') or '').strip()
    if not path:
        return jsonify({'error': 'path is required'}), 400
    if not tmdb_id:
        return jsonify({'error': 'tmdb_id is required'}), 400
    abs_path = os.path.abspath(path)
    if not _path_library_root(abs_path):
        return jsonify({'error': 'Path is outside the allowed movies directory'}), 403
    if not os.path.isfile(abs_path):
        return jsonify({'error': 'File not found'}), 404
    try:
        store = _metadata_store()
        metadata = _fetch_tmdb_metadata_by_id(tmdb_id, store=store, refresh=True, match_source='manual_tmdb')
        if not metadata:
            movie = body.get('movie') or body
            metadata = _normalize_tmdb_metadata({**movie, 'tmdb_id': tmdb_id, 'match_source': 'manual_tmdb'})
        match = store.apply_tmdb_match(abs_path, metadata)
        parsed_title, parsed_year = parse_movie_title(os.path.basename(abs_path))
        canonical = _build_canonical_metadata(
            {'path': abs_path, 'filename': os.path.basename(abs_path), 'parsed_title': parsed_title, 'parsed_year': parsed_year},
            plex_data=dict(_plex_cache.get(_norm(abs_path), {}) or {}),
            tmdb_data=store.get_tmdb_metadata(tmdb_id),
            manual_match=match,
        )
        store.record_file(abs_path, {
            'path': abs_path,
            'filename': os.path.basename(abs_path),
            'parsed_title': parsed_title,
            'parsed_year': parsed_year,
            'metadata_status': canonical.get('status', 'accepted'),
            'metadata_source': canonical.get('source', 'manual_tmdb'),
            'metadata_accepted': bool(canonical.get('accepted')),
            'tmdb_id': tmdb_id,
            'imdb_id': canonical.get('imdb_id', ''),
        })
        _library_cache.pop('items', None)
        return jsonify({'success': True, 'match': match, 'canonical_metadata': canonical})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/metadata/refresh', methods=['POST'])
def refresh_file_metadata():
    global _library_cache
    body = request.get_json(force=True, silent=True) or {}
    path = str(body.get('path', '') or '').strip()
    if not path:
        return jsonify({'error': 'path is required'}), 400
    abs_path = os.path.abspath(path)
    if not _path_library_root(abs_path):
        return jsonify({'error': 'Path is outside the allowed movies directory'}), 403
    if not os.path.isfile(abs_path):
        return jsonify({'error': 'File not found'}), 404
    try:
        store = _metadata_store()
        _auto_sync_plex(force=bool(body.get('force_plex')))
        parsed_title, parsed_year = parse_movie_title(os.path.basename(abs_path))
        plex_data = dict(_plex_cache.get(_norm(abs_path), {}) or _plex_matched_by_fname.get(os.path.basename(abs_path).lower(), {}) or {})
        file_facts = {'path': abs_path, 'filename': os.path.basename(abs_path), 'parsed_title': parsed_title, 'parsed_year': parsed_year}
        tmdb_data = _tmdb_metadata_for_file(file_facts, plex_data=plex_data, store=store, refresh=True)
        canonical = _build_canonical_metadata(
            file_facts,
            plex_data=plex_data,
            tmdb_data=tmdb_data,
            manual_match=store.get_manual_match(abs_path),
        )
        store.record_file(abs_path, {
            **file_facts,
            'metadata_status': canonical.get('status', 'unmatched'),
            'metadata_source': canonical.get('source', ''),
            'metadata_accepted': bool(canonical.get('accepted')),
            'tmdb_id': canonical.get('tmdb_id', ''),
            'imdb_id': canonical.get('imdb_id', ''),
        })
        _library_cache.pop('items', None)
        return jsonify({'success': True, 'canonical_metadata': canonical, 'tmdb_candidate': tmdb_data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def _normalize_tmdb_person(person, include_character=False):
    name = person.get('name', '')
    if not name:
        return None
    result = {
        'id': str(person.get('id', '') or ''),
        'name': name,
        'profile_url': _tmdb_image_url(person.get('profile_path')),
    }
    if include_character:
        result['character'] = person.get('character', '')
    return result


def _normalize_tmdb_details_payload(data):
    directors = []
    for person in data.get('credits', {}).get('crew', []) or []:
        if person.get('job') != 'Director':
            continue
        normalized = _normalize_tmdb_person(person)
        if normalized:
            directors.append(normalized)

    cast = []
    for person in (data.get('credits', {}).get('cast', []) or [])[:7]:
        normalized = _normalize_tmdb_person(person, include_character=True)
        if normalized:
            cast.append(normalized)

    collection = {}
    raw_collection = data.get('belongs_to_collection') or {}
    if raw_collection.get('id') and raw_collection.get('name'):
        collection = {
            'id': str(raw_collection.get('id')),
            'name': raw_collection.get('name', ''),
            'poster_url': _tmdb_image_url(raw_collection.get('poster_path')),
            'backdrop_url': _tmdb_image_url(raw_collection.get('backdrop_path'), 'w780'),
        }

    trailer_url = ''
    videos = data.get('videos', {}).get('results', []) or []
    official_trailers = [
        v for v in videos
        if v.get('site') == 'YouTube'
        and v.get('type') == 'Trailer'
        and v.get('key')
        and v.get('official', False)
    ]
    trailer = official_trailers[0] if official_trailers else next(
        (v for v in videos if v.get('site') == 'YouTube' and v.get('type') == 'Trailer' and v.get('key')),
        None
    )
    if trailer:
        trailer_url = f"https://www.youtube.com/watch?v={trailer.get('key')}"

    return {
        'director': directors[0] if directors else {},
        'directors': directors,
        'cast': cast,
        'collection': collection,
        'trailer_url': trailer_url,
        'runtime': data.get('runtime'),
        'tagline': data.get('tagline', ''),
    }


def _normalize_tmdb_movie_summary(movie, fallback_title='', fallback_year=''):
    normalized = _normalize_tmdb_metadata({
        **(movie or {}),
        'title': movie.get('title') or movie.get('name') or fallback_title,
        'year': _year_from_movie(movie, fallback_year),
    })
    normalized['genres'] = normalized.get('genres', [])[:3]
    return normalized


def _fetch_tmdb_metadata_by_id(tmdb_id, store=None, refresh=False, match_source=''):
    tmdb_id = str(tmdb_id or '').strip()
    if not tmdb_id:
        return {}
    store = store or _metadata_store()
    cached = store.get_tmdb_metadata(tmdb_id)
    if cached and not refresh:
        return {**cached, **({'match_source': match_source} if match_source else {})}
    if not _tmdb_key:
        return cached or {}
    try:
        safe_id = urllib.parse.quote(tmdb_id)
        url = (f"https://api.themoviedb.org/3/movie/{safe_id}"
               f"?api_key={urllib.parse.quote(_tmdb_key)}&language=en-US"
               f"&append_to_response=credits,videos")
        req = urllib.request.Request(url, headers={'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = _json.loads(resp.read().decode())
        metadata = _normalize_tmdb_metadata(raw)
        metadata.update(_normalize_tmdb_details_payload(raw))
        metadata['tmdb_id'] = tmdb_id
        if match_source:
            metadata['match_source'] = match_source
        return store.save_tmdb_metadata(metadata)
    except Exception:
        return cached or {}


def _search_tmdb_library_candidate(title, year='', store=None):
    title = str(title or '').strip()
    year = str(year or '').strip()
    if not title or not _tmdb_key:
        return {}
    _ensure_tmdb_genres()
    try:
        params = urllib.parse.urlencode({
            'query': title,
            'api_key': _tmdb_key,
            'language': 'en-US',
            'page': 1,
            'include_adult': _tmdb_include_adult_value(),
        })
        if year:
            params += '&year=' + urllib.parse.quote(year)
        url = f"https://api.themoviedb.org/3/search/movie?{params}"
        req = urllib.request.Request(url, headers={'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = _json.loads(resp.read().decode())
        results = data.get('results', []) or []
        if not results:
            return {}
        exact = next((movie for movie in results if _same_public_identity(title, year, movie.get('title', ''), _year_from_movie(movie))), None)
        selected = exact or results[0]
        summary = _normalize_tmdb_movie_summary(selected, title, year)
        summary['match_source'] = 'auto_tmdb' if exact else 'candidate_tmdb'
        if exact:
            return _fetch_tmdb_metadata_by_id(summary.get('tmdb_id'), store=store, match_source='auto_tmdb') or summary
        return summary
    except Exception:
        return {}


def _tmdb_metadata_for_file(file_facts, plex_data=None, store=None, refresh=False, snapshot=None):
    store = store or _metadata_store()
    path = file_facts.get('path', '')
    manual_match = store.get_manual_match_from_snapshot(path, snapshot) if snapshot is not None else store.get_manual_match(path)
    if manual_match.get('provider') == 'tmdb':
        tmdb_id = str(manual_match.get('tmdb_id', '') or '').strip()
        if snapshot is not None:
            cached = store.get_tmdb_metadata_from_snapshot(tmdb_id, snapshot) or {}
        else:
            cached = store.get_tmdb_metadata(tmdb_id) or {}
        if cached:
            return cached
        if refresh:
            fetched = _fetch_tmdb_metadata_by_id(tmdb_id, store=store, refresh=True, match_source='manual_tmdb')
            if fetched:
                return fetched
        fallback_title = str(manual_match.get('title') or file_facts.get('parsed_title') or '').strip()
        fallback_year = str(manual_match.get('year') or file_facts.get('parsed_year') or '').strip()
        if tmdb_id and fallback_title:
            return {
                'tmdb_id': tmdb_id,
                'imdb_id': str(manual_match.get('imdb_id', '') or ''),
                'title': fallback_title.title(),
                'year': fallback_year,
                'poster_url': manual_match.get('poster_url', ''),
                'genres': [],
                'plot': '',
                'summary': '',
                'tmdb_rating': '',
                'tmdb_vote_count': 0,
                'match_source': 'manual_tmdb',
            }
        return {}
    plex_tmdb_id = str((plex_data or {}).get('tmdb_id', '') or '').strip()
    if plex_tmdb_id:
        cached = (
            store.get_tmdb_metadata_from_snapshot(plex_tmdb_id, snapshot)
            if snapshot is not None else store.get_tmdb_metadata(plex_tmdb_id)
        ) or {}
        if cached:
            return {**cached, 'match_source': 'plex_tmdb_id'}
        if refresh:
            return _fetch_tmdb_metadata_by_id(plex_tmdb_id, store=store, refresh=True, match_source='plex_tmdb_id')
        return {}
    file_record = ((snapshot or {}).get('files', {}) if snapshot is not None
                   else store._read_json(store.files_file, {'files': {}}).get('files', {})).get(store._key(path), {})
    accepted_tmdb_id = str(file_record.get('tmdb_id', '') or '').strip()
    if accepted_tmdb_id:
        if snapshot is not None:
            return store.get_tmdb_metadata_from_snapshot(accepted_tmdb_id, snapshot) or {}
        return store.get_tmdb_metadata(accepted_tmdb_id) or {}
    if refresh:
        return _search_tmdb_library_candidate(file_facts.get('parsed_title', ''), file_facts.get('parsed_year', ''), store=store)
    return {}


def _normalize_tmdb_collection_payload(data):
    parts = []
    for movie in data.get('parts', []) or []:
        parts.append(_normalize_tmdb_movie_summary(movie))
    parts.sort(key=lambda item: item.get('release_date') or item.get('year') or '')
    return {
        'id': str(data.get('id', '') or ''),
        'name': data.get('name', ''),
        'poster_url': _tmdb_image_url(data.get('poster_path')),
        'backdrop_url': _tmdb_image_url(data.get('backdrop_path'), 'w780'),
        'parts': parts,
    }


@app.route('/api/tmdb/person_movies')
def tmdb_person_movies():
    person_id = request.args.get('person_id', '').strip()
    role = request.args.get('role', 'actor').strip().lower()
    if role not in ('actor', 'director'):
        role = 'actor'
    if not person_id or not _tmdb_key:
        return jsonify({'error': 'person_id and TMDB key required'}), 400
    try:
        page = max(1, min(int(request.args.get('page', '1')), 10))
    except ValueError:
        page = 1
    _ensure_tmdb_genres()
    try:
        safe_id = urllib.parse.quote(str(person_id))
        url = (f"https://api.themoviedb.org/3/person/{safe_id}/movie_credits"
               f"?api_key={urllib.parse.quote(_tmdb_key)}&language=en-US")
        req = urllib.request.Request(url, headers={'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = _json.loads(resp.read().decode())

        credits = raw.get('cast', []) or []
        if role == 'director':
            credits = [
                item for item in (raw.get('crew', []) or [])
                if item.get('job') == 'Director'
            ]

        movies = []
        seen = set()
        for item in credits:
            tmdb_id = str(item.get('id', '') or '')
            if not tmdb_id or tmdb_id in seen:
                continue
            seen.add(tmdb_id)
            movies.append(_normalize_tmdb_movie_summary(item))

        movies.sort(key=lambda item: (
            float(next((raw_item.get('popularity', 0) for raw_item in credits if str(raw_item.get('id', '') or '') == item.get('tmdb_id')), 0) or 0),
            item.get('release_date') or ''
        ), reverse=True)

        page_size = 20
        total_results = len(movies)
        total_pages = min(max(1, (total_results + page_size - 1) // page_size), 10)
        start = (page - 1) * page_size
        end = start + page_size
        return jsonify({
            'results': movies[start:end],
            'total_pages': total_pages,
            'page': page,
            'total_results': total_results,
            'role': role,
            'person_id': person_id,
        })
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return jsonify({'error': 'Invalid TMDB API key — check Settings.'}), 401
        return jsonify({'error': f'TMDB returned HTTP {e.code}'}), 502
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/tmdb/details')
def tmdb_details():
    global _tmdb_library_cache
    tmdb_id = request.args.get('tmdb_id', '').strip()
    refresh = request.args.get('refresh') == '1'
    if not tmdb_id or not _tmdb_key:
        return jsonify({'error': 'tmdb_id and TMDB key required'}), 400
    try:
        cached = _tmdb_library_cache.get(str(tmdb_id))
        if cached and not refresh:
            data = dict(cached.get('data', {}))
            data['cached'] = True
            data['fetched_at'] = cached.get('fetched_at', 0)
            return jsonify(data)

        safe_id = urllib.parse.quote(str(tmdb_id))
        url = (f"https://api.themoviedb.org/3/movie/{safe_id}"
               f"?api_key={urllib.parse.quote(_tmdb_key)}&language=en-US"
               f"&append_to_response=credits,videos")
        req = urllib.request.Request(url, headers={'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = _json.loads(resp.read().decode())

        details = _normalize_tmdb_details_payload(raw)
        details['tmdb_id'] = str(tmdb_id)
        fetched_at = time.time()
        _tmdb_library_cache[str(tmdb_id)] = {'fetched_at': fetched_at, 'data': details}
        _save_tmdb_library_cache(_tmdb_library_cache)
        result = dict(details)
        result['cached'] = False
        result['fetched_at'] = fetched_at
        return jsonify(result)
    except urllib.error.HTTPError as e:
        return jsonify({'error': f'TMDB returned HTTP {e.code}'}), 502
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/tmdb/collection')
def tmdb_collection():
    global _tmdb_collection_cache
    collection_id = request.args.get('collection_id', '').strip()
    refresh = request.args.get('refresh') == '1'
    if not collection_id or not _tmdb_key:
        return jsonify({'error': 'collection_id and TMDB key required'}), 400
    try:
        cached = _tmdb_collection_cache.get(str(collection_id))
        if cached and not refresh:
            data = _curation_store().effective_collection(dict(cached.get('data', {})))
            data['cached'] = True
            data['fetched_at'] = cached.get('fetched_at', 0)
            return jsonify(data)

        safe_id = urllib.parse.quote(str(collection_id))
        url = (f"https://api.themoviedb.org/3/collection/{safe_id}"
               f"?api_key={urllib.parse.quote(_tmdb_key)}&language=en-US")
        req = urllib.request.Request(url, headers={'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = _json.loads(resp.read().decode())

        tmdb_details = _normalize_tmdb_collection_payload(raw)
        fetched_at = time.time()
        _tmdb_collection_cache[str(collection_id)] = {'fetched_at': fetched_at, 'data': tmdb_details}
        _save_tmdb_collection_cache(_tmdb_collection_cache)
        result = _curation_store().effective_collection(tmdb_details)
        result['cached'] = False
        result['fetched_at'] = fetched_at
        return jsonify(result)
    except urllib.error.HTTPError as e:
        return jsonify({'error': f'TMDB returned HTTP {e.code}'}), 502
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/user/collection', methods=['POST'])
def save_user_collection():
    body = request.get_json(force=True, silent=True) or {}
    collection_id = str(body.get('collection_id', '') or '').strip()
    original = body.get('original') or {}
    parts = body.get('parts') or []
    if not collection_id or not original.get('name'):
        return jsonify({'error': 'collection_id and original collection are required'}), 400
    try:
        return jsonify(_curation_store().save_collection_override(collection_id, original, parts))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/user/collection/<collection_id>/reset', methods=['POST'])
def reset_user_collection(collection_id):
    try:
        reset = _curation_store().reset_collection(collection_id)
        return jsonify({'success': True, 'reset': reset})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/user/followed-releases', methods=['GET', 'POST', 'DELETE'])
def user_followed_releases():
    store = _curation_store()
    if request.method == 'GET':
        if request.args.get('check') == '1':
            return jsonify(_check_followed_releases())
        return jsonify({'movies': _sort_followed_releases(store.followed_all())})
    body = request.get_json(force=True, silent=True) or {}
    movie = body.get('movie') or body
    try:
        if request.method == 'POST':
            followed = store.follow_movie(movie)
            return jsonify({'movie': followed, 'movies': _sort_followed_releases(store.followed_all())})
        removed = store.unfollow_movie(movie)
        return jsonify({'success': True, 'removed': removed, 'movies': _sort_followed_releases(store.followed_all())})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/user/followed-releases/check', methods=['POST'])
def check_user_followed_releases():
    try:
        return jsonify(_check_followed_releases())
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/user/lists', methods=['GET', 'POST'])
def user_lists():
    store = _curation_store()
    if request.method == 'GET':
        movie = {
            'tmdb_id': request.args.get('tmdb_id', ''),
            'title': request.args.get('title', ''),
            'year': request.args.get('year', ''),
            'path': request.args.get('path', ''),
        }
        result = {'lists': store.list_all()}
        if any(movie.values()):
            result['movie_lists'] = store.lists_for_movie(movie)
        return jsonify(result)
    body = request.get_json(force=True, silent=True) or {}
    try:
        return jsonify(store.create_list(body.get('name', '')))
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/user/lists/<list_id>', methods=['PATCH', 'DELETE'])
def user_list_detail(list_id):
    store = _curation_store()
    try:
        if request.method == 'DELETE':
            return jsonify({'success': True, 'deleted': store.delete_list(list_id)})
        body = request.get_json(force=True, silent=True) or {}
        return jsonify(store.rename_list(list_id, body.get('name', '')))
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except KeyError:
        return jsonify({'error': 'List not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/user/lists/<list_id>/movies', methods=['POST', 'DELETE'])
def user_list_movies(list_id):
    body = request.get_json(force=True, silent=True) or {}
    movie = body.get('movie') or body
    try:
        if request.method == 'POST':
            return jsonify(_curation_store().add_movie_to_list(list_id, movie))
        return jsonify(_curation_store().remove_movie_from_list(list_id, movie))
    except KeyError:
        return jsonify({'error': 'List not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/tmdb/imdb_id')
def tmdb_imdb_id():
    tmdb_id = request.args.get('tmdb_id', '').strip()
    if not tmdb_id or not _tmdb_key:
        return jsonify({'error': 'tmdb_id and TMDB key required'}), 400
    try:
        url = (f"https://api.themoviedb.org/3/movie/{urllib.parse.quote(str(tmdb_id))}"
               f"?api_key={urllib.parse.quote(_tmdb_key)}&language=en-US")
        req = urllib.request.Request(url, headers={'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = _json.loads(resp.read().decode())
        imdb_id = data.get('imdb_id', '')
        if not imdb_id:
            return jsonify({'error': 'No IMDB ID found for this title'}), 404
        return jsonify({'imdb_id': imdb_id})
    except urllib.error.HTTPError as e:
        return jsonify({'error': f'TMDB returned HTTP {e.code}'}), 502
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── Ollama / Pick My Movie ───────────────────────────────────────────────────

@app.route('/api/ollama/config', methods=['GET'])
def get_ollama_config():
    return jsonify({'url': _ollama_url, 'model': _ollama_model})


@app.route('/api/ollama/config', methods=['POST'])
def set_ollama_config():
    global _ollama_url, _ollama_model
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    _ollama_url   = data.get('url', 'http://localhost:11434').strip().rstrip('/')
    _ollama_model = data.get('model', '').strip()
    _save_config(_all_config())
    return jsonify({'success': True})


@app.route('/api/ollama/test')
def ollama_test():
    url = request.args.get('url', _ollama_url).strip().rstrip('/')
    if not url:
        return jsonify({'error': 'No Ollama URL configured — add it in Settings.'}), 400
    try:
        req = urllib.request.Request(f"{url}/api/tags", headers={'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=8) as resp:
            _json.loads(resp.read().decode())
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': f'Cannot reach Ollama: {e}'}), 502


def _ollama_enrich_with_tmdb(title, year):
    """Search TMDB for a single title and return enriched movie dict. Returns None on failure."""
    if not _tmdb_key:
        return None
    _ensure_tmdb_genres()
    try:
        params = urllib.parse.urlencode({
            'query': title, 'api_key': _tmdb_key,
            'language': 'en-US', 'page': 1, 'include_adult': 'false',
            **(({'year': year}) if year else {})
        })
        url = f"https://api.themoviedb.org/3/search/movie?{params}"
        req = urllib.request.Request(url, headers={'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = _json.loads(resp.read().decode())
        results = data.get('results', [])
        if not results:
            return None
        m = results[0]
        poster_path = m.get('poster_path', '')
        release = m.get('release_date', '') or ''
        yr = release[:4] if release else year
        genre_ids = m.get('genre_ids', [])
        genres = [_tmdb_genres[gid] for gid in genre_ids if gid in _tmdb_genres][:3]
        vote = m.get('vote_average', 0)
        lang = m.get('original_language', '')
        country_code = _LANG_COUNTRY.get(lang, '')
        return {
            'tmdb_id':      m.get('id'),
            'title':        m.get('title', title),
            'year':         yr,
            'poster_url':   f"https://image.tmdb.org/t/p/w342{poster_path}" if poster_path else '',
            'genres':       genres,
            'tmdb_rating':  f"{vote:.1f}" if isinstance(vote, (int, float)) and vote else '',
            'tmdb_vote_count': int(m.get('vote_count', 0) or 0),
            'plot':         m.get('overview', ''),
            'language':     _LANG_NAMES.get(lang, lang.upper() if lang else ''),
            'country':      country_code,
            'country_flag': _country_flag(country_code),
        }
    except Exception:
        return None


@app.route('/api/ollama/recommend', methods=['POST'])
def ollama_recommend():
    if not _ollama_url or not _ollama_model:
        return jsonify({'error': 'Ollama not configured — add URL and model in Settings.'}), 400
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    prompt = data.get('prompt', '').strip()
    if not prompt:
        return jsonify({'error': 'Prompt cannot be empty.'}), 400

    system_msg = (
        'You are a movie recommendation expert. '
        'The user will describe a movie or what they want to watch by mood, memory, feeling, actors, or any detail. '
        'Return ONLY valid JSON with this exact shape: '
        '{"recommendations":[{"title":"...","year":"...","reason":"one sentence why this matches"}]}. '
        'Give exactly 10 recommendations. '
        'No markdown, no explanation, no extra text — only the JSON object.'
    )

    body = _json.dumps({
        'model': _ollama_model,
        'messages': [
            {'role': 'system', 'content': system_msg},
            {'role': 'user',   'content': prompt}
        ],
        'stream': False,
        'format': 'json'
    }).encode()

    try:
        req = urllib.request.Request(
            f"{_ollama_url}/api/chat",
            data=body,
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = _json.loads(resp.read().decode())
        parsed = _json.loads(raw['message']['content'])
        recs = parsed.get('recommendations', [])
    except _json.JSONDecodeError:
        return jsonify({'error': 'Ollama returned invalid JSON. Try a different prompt.'}), 502
    except urllib.error.HTTPError as e:
        return jsonify({'error': f'Ollama returned HTTP {e.code}'}), 502
    except Exception as e:
        return jsonify({'error': f'Cannot reach Ollama: {e}'}), 502

    results = []
    for rec in recs:
        title  = rec.get('title', '').strip()
        year   = rec.get('year', '').strip()
        reason = rec.get('reason', '')
        if not title:
            continue
        enriched = _ollama_enrich_with_tmdb(title, year)
        if enriched:
            enriched['reason'] = reason
            results.append(enriched)
        else:
            results.append({'title': title, 'year': year, 'reason': reason,
                            'poster_url': '', 'genres': [], 'tmdb_rating': '',
                            'tmdb_vote_count': 0, 'plot': '', 'tmdb_id': None})

    return jsonify({'results': results, 'model': _ollama_model})


if __name__ == '__main__':
    app.run(debug=False, port=5000, use_reloader=True)
