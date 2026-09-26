"""TMDB TV normalization; provider outages never erase accepted local data."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import threading
import time
import urllib.parse
from urllib.error import HTTPError, URLError
import urllib.request


class TVMetadata:
    def __init__(self, repository, key_provider, opener=None, *, max_workers=4, cache_ttl=300, clock=time.time, sleeper=time.sleep):
        self.repository, self.key_provider = repository, key_provider
        self.opener = opener
        self.max_workers = min(8, max(1, int(max_workers)))
        self.cache_ttl, self.clock, self.sleeper = max(0, int(cache_ttl)), clock, sleeper
        self._cache, self._cache_lock = {}, threading.RLock()
        self._request_locks = {}
        self._failures = {}

    def request(self, path, *, _timeout=15, _attempts=3, _deadline=None, **params):
        cache_key = (path, tuple(sorted((name, str(value)) for name, value in params.items())))
        with self._cache_lock:
            entry = self._request_locks.setdefault(cache_key, [threading.Lock(), 0])
            entry[1] += 1
        acquired = False
        try:
            acquired = entry[0].acquire(timeout=max(0, _deadline-time.monotonic()) if _deadline else -1)
            if not acquired:
                raise TimeoutError('Metadata search time budget reached')
            failure = self._failures.get(cache_key)
            if failure and time.monotonic()-failure < 10:
                raise OSError('Metadata provider temporarily unavailable')
            if _deadline:
                _timeout = min(_timeout, _deadline-time.monotonic())
                if _timeout <= 0: raise TimeoutError('Metadata search time budget reached')
                _attempts = 1
            try:
                return self._request(path, _timeout=_timeout, _attempts=_attempts, **params)
            except OSError:
                self._failures[cache_key] = time.monotonic()
                raise
        finally:
            if acquired: entry[0].release()
            with self._cache_lock:
                entry[1] -= 1
                if not entry[1]: self._request_locks.pop(cache_key, None)
                self._failures = {k:v for k,v in self._failures.items() if time.monotonic()-v < 10}

    def _request(self, path, *, _timeout=15, _attempts=3, **params):
        key = self.key_provider()
        if not key:
            raise ValueError('TMDB is not configured')
        cache_key = (path, tuple(sorted((name, str(value)) for name, value in params.items())))
        with self._cache_lock:
            cached = self._cache.get(cache_key)
            if cached and self.clock() - cached[0] <= self.cache_ttl:
                return cached[1]
        query = urllib.parse.urlencode({'api_key': key, **params})
        opener = self.opener or urllib.request.urlopen
        last_error = None
        for attempt in range(_attempts):
            try:
                with opener(f'https://api.themoviedb.org/3{path}?{query}', timeout=_timeout) as response:
                    payload = json.loads(response.read())
                with self._cache_lock:
                    self._cache[cache_key] = (self.clock(), payload)
                return payload
            except HTTPError as error:
                last_error = error
                if error.code != 429 and error.code < 500:
                    raise
                retry_after = error.headers.get('Retry-After') if error.headers else None
                try:
                    delay = min(30, max(1, int(retry_after or 2 ** attempt)))
                except (TypeError, ValueError):
                    delay = min(30, 2 ** attempt)
            except URLError as error:
                last_error = error
                delay = min(30, 2 ** attempt)
            if attempt == _attempts - 1:
                raise last_error
            self.sleeper(delay)

    @staticmethod
    def credits(row):
        source = row.get('aggregate_credits') or row.get('credits') or {}
        result = []
        for position, person in enumerate(sorted(source.get('cast', []), key=lambda p: p.get('order', 999999))):
            roles = person.get('roles') or [{'character': person.get('character') or 'Cast'}]
            result.append({'tmdb_id': person['id'], 'name': person['name'], 'kind': 'actor',
                           'role': ', '.join(r['character'] for r in roles if r.get('character')) or 'Cast',
                           'order': person.get('order', position), 'portrait_url': 'https://image.tmdb.org/t/p/w185' + person['profile_path'] if person.get('profile_path') else ''})
        for person in source.get('crew', []):
            for job in person.get('jobs') or [person]:
                kind = 'director' if job.get('job') == 'Director' else 'writer' if person.get('department') == 'Writing' else None
                if kind:
                    result.append({'tmdb_id': person['id'], 'name': person['name'], 'kind': kind, 'role': job.get('job', kind.title())})
        result.extend({'tmdb_id': p['id'], 'name': p['name'], 'kind': 'creator', 'role': 'Creator'} for p in row.get('created_by', []))
        return list({(p['tmdb_id'], p['kind'], p['role']): p for p in result}.values())

    @staticmethod
    def normalize(row):
        return {'tmdb_id': int(row['id']), 'title': row.get('name') or row.get('original_name') or 'Untitled series',
                'overview': row.get('overview', ''), 'first_air_date': row.get('first_air_date', ''),
                'last_air_date': row.get('last_air_date', ''), 'status': row.get('status', ''),
                'rating': row.get('vote_average'), 'votes': row.get('vote_count'),
                 'genres': [genre['name'] for genre in row.get('genres', [])],
                'genre_ids': [g['id'] for g in row.get('genres', [])] or row.get('genre_ids', []),
                'genre_records': row.get('genres', []), 'original_title': row.get('original_name', ''),
                'original_language': row.get('original_language', ''), 'origin_country': row.get('origin_country', []),
                'listed_episode_count': row.get('number_of_episodes'), 'season_count': row.get('number_of_seasons'),
                'runtime': next(iter(row.get('episode_run_time') or []), None), 'popularity': row.get('popularity', 0),
                'credits_loaded': 'aggregate_credits' in row or 'credits' in row,
                'keywords': row.get('keywords', {}).get('results', []), 'credits': TVMetadata.credits(row),
                'alternative_titles': [r['title'] for r in row.get('alternative_titles', {}).get('results', [])],
                'trailer_url': TVMetadata.trailer(row),
                'poster_url': 'https://image.tmdb.org/t/p/w342' + row['poster_path'] if row.get('poster_path') else '',
                'backdrop_url': 'https://image.tmdb.org/t/p/w1280' + row['backdrop_path'] if row.get('backdrop_path') else '',
                'seasons': row.get('seasons', []), 'external_ids': row.get('external_ids', {})}

    def display(self, row, *, deadline=None):
        """Normalize summary labels without fetching every series detail."""
        row = dict(row)
        try:
            if row.get('genre_ids') and not row.get('genres'):
                lookup = {g['id']: g['name'] for g in self.request('/genre/tv/list', _timeout=5, _attempts=1, _deadline=deadline).get('genres', [])}
                row['genres'] = [lookup[g] for g in row['genre_ids'] if g in lookup]
            if row.get('original_language') and not row.get('original_language_name'):
                languages = {v['iso_639_1']: v.get('english_name') or v['iso_639_1'] for v in self.request('/configuration/languages', _timeout=5, _attempts=1, _deadline=deadline)}
                row['original_language_name'] = languages.get(row.get('original_language'), row.get('original_language', ''))
        except (OSError, ValueError, KeyError, TypeError):
            row.setdefault('original_language_name', row.get('original_language', ''))
        return row

    def refresh(self, tmdb_id, *, season_scope=None):
        tmdb_id = int(tmdb_id)
        if tmdb_id <= 0:
            raise ValueError('A TMDB TV identity is required')
        series = self.request(f'/tv/{tmdb_id}', append_to_response='external_ids,aggregate_credits,videos,keywords,alternative_titles')
        episodes = []
        seasons = [s for s in series.get('seasons', []) if season_scope is None or s['season_number'] in season_scope]
        if len(seasons) > 150:
            raise ValueError('Provider series exceeds the supported refresh bound')
        with ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix='tv-metadata') as pool:
            requests = {pool.submit(self.request, f"/tv/{tmdb_id}/season/{int(season['season_number'])}"): int(season['season_number']) for season in seasons}
            payloads = []
            for future in as_completed(requests):
                payloads.append((requests[future], future.result()))
        for _, data in sorted(payloads):
            for row in data.get('episodes', []):
                episodes.append({**row, 'provider_id': str(row['id']), 'title': row.get('name') or '', 'runtime': row.get('runtime')})
        return self.repository.refresh(self.display(self.normalize(series)), episodes, self.credits(series), season_scope=season_scope)

    @staticmethod
    def trailer(row):
        videos = [v for v in row.get('videos', {}).get('results', []) if v.get('site') == 'YouTube' and v.get('type') in {'Trailer', 'Teaser'} and v.get('key')]
        videos.sort(key=lambda v: (v.get('type') == 'Trailer', bool(v.get('official')), v.get('iso_639_1') == 'en'), reverse=True)
        return 'https://www.youtube.com/watch?v=' + videos[0]['key'] if videos else ''

    def preview(self, tmdb_id, *, fast=False, deadline=None):
        from services.tv_read_model import year_range
        from services.tv_catalog_repository import released
        tmdb_id = int(tmdb_id)
        if tmdb_id <= 0:
            raise ValueError('A TMDB TV identity is required')
        raw = self.request(f'/tv/{tmdb_id}', append_to_response='external_ids,aggregate_credits,videos,keywords,alternative_titles', _deadline=deadline, **({'_timeout': 5, '_attempts': 1} if fast else {}))
        row = self.display(self.normalize(raw), deadline=deadline)
        seasons = [{'number': s['season_number'], 'title': s.get('name') or f"Season {s['season_number']}", 'episodes': s.get('episode_count', 0), 'available': 0, 'completed': 0} for s in raw.get('seasons', [])]
        # A fresh viewer starts at the first released regular episode, not the latest.
        first_season = next((s for s in raw.get('seasons', []) if s['season_number'] > 0 and released(s.get('air_date'))), None)
        stream_target = {'tmdb_id': tmdb_id, 'season_number': first_season['season_number'], 'episode_number': 1, 'code': f"S{first_season['season_number']:02d}E01", 'released': True} if first_season else None
        return {**row, 'preview': True, 'cast': row['credits'], 'year_range': year_range(row), 'status_label': row['status'] or 'Status Unknown',
                'season_count': sum(s['number'] > 0 for s in seasons), 'episode_count': raw.get('number_of_episodes', 0),
                'available_count': 0, 'seasons': seasons, 'default_season': first_season['season_number'] if first_season else next((s['number'] for s in seasons), 0),
                'primary_action': {'playable': False, 'label': 'No local episodes', 'reason': 'Downloads add this show to your library automatically. Adding it manually does not start downloads.'}, 'stream_target': stream_target}

    def translation(self, tmdb_id, language='ar-SA'):
        tmdb_id = int(tmdb_id)
        if tmdb_id <= 0:
            raise ValueError('A TMDB TV identity is required')
        if language != 'ar-SA':
            raise ValueError('Only Arabic display is supported')
        row = self.request(f'/tv/{tmdb_id}', language=language)
        return {
            'title': row.get('name') or '',
            'overview': row.get('overview') or '',
            'genres': [genre['name'] for genre in row.get('genres', []) if genre.get('name')],
            'poster_url': 'https://image.tmdb.org/t/p/w342' + row['poster_path'] if row.get('poster_path') else '',
            'backdrop_url': 'https://image.tmdb.org/t/p/w1280' + row['backdrop_path'] if row.get('backdrop_path') else '',
        }

    def preview_season(self, tmdb_id, season):
        from services.tv_catalog_repository import released
        data = self.request(f'/tv/{int(tmdb_id)}/season/{int(season)}')
        return {'items': [{**r, 'title': r.get('name', ''), 'code': f"S{int(season):02d}E{r['episode_number']:02d}",
                           'released': released(r.get('air_date')), 'available': False, 'completed': False, 'versions': [],
                           'guest_stars': [{'name': p['name'], 'role': p.get('character', '')} for p in r.get('guest_stars', [])]} for r in data.get('episodes', [])], 'total_pages': 1}

    def discover(self, query='', page=1):
        from services.tv_search import TVSearch
        from services.tv_read_model import TVReadModel
        payload = {'version': 1, 'scope': 'discover', 'mode': 'simple', 'groups': [], 'feed': 'catalog'}
        if query:
            payload['groups'].append({'type': 'title', 'values': [{'text': query}]})
        return TVSearch(TVReadModel(self.repository), self).discover(payload, page)
