"""Movie discovery over the shared YouTube HTTP owner; no inference or catalog writes."""
import copy
import html
import math
import re
import threading
import time
import unicodedata
import uuid
from collections import OrderedDict

from services.youtube_playlist import VIDEO_ID_PATTERN, YouTubePlaylistError


def arabic(value):
    return bool(re.search(r'[\u0621-\u064a\u066e-\u06d3]', str(value)))


def normalized(value):
    text = ''.join(c for c in unicodedata.normalize('NFKD', html.unescape(str(value))).casefold()
                   if not unicodedata.combining(c) and c != '\u0640')
    return ' '.join(re.sub(r'[^\w\s]', ' ', text).replace('_', ' ').split())


def duration_seconds(value):
    match = re.fullmatch(r'P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?)?', str(value or ''))
    if not match:
        return 0
    return sum(float(part or 0) * unit for part, unit in zip(match.groups(), (86400, 3600, 60, 1)))


def movie_profile(raw, identity):
    runtime = raw.get('runtime')
    if isinstance(runtime, bool) or not isinstance(runtime, (int, float)) or not math.isfinite(runtime) or runtime <= 0:
        raise YouTubePlaylistError('Movie runtime is missing. YouTube search requires a known runtime for the ±5% filter.')
    titles = [raw.get('original_title'), raw.get('title')]
    titles += [row.get('title') for row in (raw.get('alternative_titles') or {}).get('titles', [])]
    titles += [(row.get('data') or {}).get('title') for row in (raw.get('translations') or {}).get('translations', [])
               if row.get('iso_639_1') == 'ar']
    is_arabic = raw.get('original_language') == 'ar'
    if is_arabic:
        # Metadata can append an English translation to an otherwise Arabic name.
        titles = [re.sub(r'\s+', ' ', re.sub(r'[A-Za-z]+|[()\[\]]', ' ', str(title))).strip()
                  for title in titles if title and arabic(title)]
    titles = list(dict.fromkeys(str(title).strip() for title in titles if title and (not is_arabic or arabic(title))))[:8]
    if not titles:
        raise YouTubePlaylistError('Arabic movie title is missing. Add or refresh its movie metadata before searching.'
                                   if is_arabic else 'Movie title is missing.')
    return {'tmdb_id': identity, 'title': titles[0], 'titles': titles,
            'year': str(raw.get('release_date') or raw.get('year') or '')[:4],
            'arabic': is_arabic, 'runtime_seconds': runtime * 60}


class YouTubeMovieSearch:
    """Bounded transient searches, with per-session serialization and retryable pages."""
    def __init__(self, youtube, details, *, clock=time.monotonic, ttl=1800, max_sessions=128):
        self.youtube, self.details, self.clock = youtube, details, clock
        self.ttl, self.max_sessions = ttl, max_sessions
        self._sessions = OrderedDict()
        self._lock = threading.Lock()

    def _session(self, identity):
        with self._lock:
            session = self._sessions.get(identity)
            if session is None or self.clock() - session['updated'] >= self.ttl:
                self._sessions.pop(identity, None)
                raise YouTubePlaylistError('This YouTube search expired. Return to sources and open YouTube again.')
            session['updated'] = self.clock()
            self._sessions.move_to_end(identity)
            return session

    def _new(self, identity):
        if not isinstance(identity, str) or not re.fullmatch(r'[1-9][0-9]{0,10}', identity):
            raise YouTubePlaylistError('A valid movie identity is required.')
        try:
            raw = self.details(identity)
        except Exception as error:
            raise YouTubePlaylistError('Movie metadata is temporarily unavailable. Please retry.') from error
        profile = movie_profile(raw, identity)
        queries = []
        for title in profile['titles']:
            suffix = 'فيلم كامل' if profile['arabic'] else 'full movie'
            queries.extend([f'{title} {suffix}', ' '.join(filter(None, [title, profile['year']])), title])
        queries = list(dict.fromkeys(queries))
        session = {'search_id': uuid.uuid4().hex, 'movie': profile, 'updated': self.clock(),
                   'pending': [(query, '') for query in queries], 'attempted': [], 'completed_pages': set(),
                   'candidates': {}, 'lock': threading.RLock()}
        with self._lock:
            self._sessions[session['search_id']] = session
            while len(self._sessions) > self.max_sessions:
                self._sessions.popitem(last=False)
        return session

    def _snapshot(self, session):
        movie = session['movie']
        candidates = sorted(session['candidates'].values(), key=lambda v: (-v['title_score'], v['runtime_difference']))
        return copy.deepcopy({'search_id': session['search_id'], 'movie': movie,
            'runtime_seconds': movie['runtime_seconds'],
            'duration_range': [movie['runtime_seconds'] * .95, movie['runtime_seconds'] * 1.05],
            'candidates': candidates, 'has_more': bool(session['pending']),
            'queries': list(dict.fromkeys(session['attempted']))})

    def snapshot(self, search_id):
        session = self._session(search_id)
        with session['lock']:
            return self._snapshot(session)

    def _check_key(self):
        if not self.youtube.api_key:
            raise YouTubePlaylistError('Configure a YouTube API key in Settings to search for movies.')

    def search(self, *, tmdb_id=None, search_id=None):
        self._check_key()
        if bool(tmdb_id) == bool(search_id):
            raise YouTubePlaylistError('Supply a movie identity or an existing search, not both.')
        session = self._session(search_id) if search_id else self._new(str(tmdb_id))
        with session['lock']:
            if session['pending']:
                self._page(session, session['pending'][0])
            return self._snapshot(session)

    def _page(self, session, page, cancelled=lambda: False):
        query, token = page
        params = {'part': 'snippet', 'q': query, 'type': 'video', 'maxResults': 50, 'safeSearch': 'none'}
        if token:
            params['pageToken'] = token
        data = self.youtube._request_json('search', params)
        if cancelled():
            return
        ids = list(dict.fromkeys(str((item.get('id') or {}).get('videoId') or '') for item in data.get('items', [])))
        ids = [identity for identity in ids if VIDEO_ID_PATTERN.fullmatch(identity)]
        details = self.youtube._request_json('videos', {'part': 'snippet,contentDetails,status', 'id': ','.join(ids)}) if ids else {'items': []}
        if cancelled():
            return
        movie = session['movie']
        runtime = movie['runtime_seconds']
        additions = {}
        for raw in details.get('items', []):
            identity = str(raw.get('id') or '')
            seconds = duration_seconds((raw.get('contentDetails') or {}).get('duration'))
            # Multiply rather than round: exactly 95% and 105% remain eligible.
            if identity not in ids or not (runtime * 95 <= seconds * 100 <= runtime * 105):
                continue
            snippet = raw.get('snippet') or {}
            title = html.unescape(str(snippet.get('title') or '')).strip()
            if not title or snippet.get('liveBroadcastContent') in ('live', 'upcoming'):
                continue
            candidate_title = normalized(title)
            scores = []
            for alias in movie['titles']:
                name = normalized(alias)
                words = set(name.split())
                scores.append(1 if name and name in candidate_title else len(words & set(candidate_title.split())) / max(1, len(words)))
            additions[identity] = {'video_id': identity, 'title': title,
                'channel_title': html.unescape(str(snippet.get('channelTitle') or '')),
                'duration_seconds': seconds, 'runtime_difference': abs(seconds - runtime), 'title_score': max(scores),
                'embeddable': (raw.get('status') or {}).get('embeddable', True),
                'url': f'https://www.youtube.com/watch?v={identity}'}
        # Commit only after both requests succeed, so retries never skip a page.
        session['candidates'].update(additions)
        session['attempted'].append(query)
        session['completed_pages'].add(page)
        if page in session['pending']:
            session['pending'].remove(page)
        next_token = str(data.get('nextPageToken') or '')
        next_page = (query, next_token)
        if next_token and next_page not in session['completed_pages'] and next_page not in session['pending']:
            session['pending'].insert(0, next_page)

    def search_queries(self, search_id, queries, cancelled):
        self._check_key()
        session = self._session(search_id)
        with session['lock']:
            if (not isinstance(queries, list) or len(queries) > 3 or
                    any(not isinstance(q, str) or not q.strip() or len(q) > 240 for q in queries)):
                raise YouTubePlaylistError('GPT returned invalid search queries.')
            if session['movie']['arabic'] and any(not arabic(q) or re.search(r'[A-Za-z]', q) for q in queries):
                raise YouTubePlaylistError('GPT must use Arabic search queries for this movie.')
            pages = [(query, '') for query in dict.fromkeys(q.strip() for q in queries)
                     if (query, '') not in session['completed_pages']]
            session['pending'] = pages + [page for page in session['pending'] if page not in pages]
            for page in pages:
                if cancelled():
                    break
                self._page(session, page, cancelled)
            return self._snapshot(session)
