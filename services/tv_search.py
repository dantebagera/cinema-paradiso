"""TV catalog queries using the shared search contract and TV-owned facts.

Local predicates run before pagination. Online pages retain their provider page
identity; filtered pages never advertise the provider's unfiltered total.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import date
import json
import math
import time
import threading
from pathlib import Path
import unicodedata

from services.advanced_search import normalize_query
from services.media_file_facts import audio_languages
from services.quality_catalog import source_claim, SOURCES

TMDB_PAGE_SIZE = 20
TV_STATUS_CHOICES = (
    ('0', 'Returning Series'), ('1', 'Planned'), ('2', 'In Production'),
    ('3', 'Ended'), ('4', 'Canceled'), ('5', 'Pilot'),
)
TV_STATUS_NAMES = dict(TV_STATUS_CHOICES)


def text_key(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(value or '')).casefold()
                   if not unicodedata.combining(c))


def bounds(value):
    operator = value.get('operator', 'between')
    if operator == 'between':
        return value['from'], value['to']
    number = value['value']
    return (number if operator != 'at_most' else None,
            number if operator != 'at_least' else None)


def runtime_bounds(value):
    return {'short': (0, 59), 'feature': (60, 149), 'long': (150, 1440)}.get(
        value['preset'], (value.get('from', 0), value.get('to', 1440)))


def within(actual, lower, upper):
    return actual is not None and (lower is None or actual >= lower) and (upper is None or actual <= upper)


def quality_rank(value):
    return {'4k': 4, '2160p': 4, '1080p': 3, '720p': 2, '480p': 1, '576p': 1}.get(str(value).lower(), 0)


def matches(row, query):
    """Evaluate normalized criteria; no caller may silently discard a group."""
    for group in query['groups']:
        kind, values = group['type'], group['values']
        checks = []
        for value in values:
            identity = str(value.get('id', ''))
            if kind == 'title':
                titles = [row.get('title'), row.get('original_title'), *row.get('alternative_titles', [])]
                match = any(text_key(value['text']) in text_key(title) for title in titles)
            elif kind == 'genre':
                match = identity in {str(x) for x in row.get('genre_ids', [])} or value['label'] in row.get('genres', [])
                if value.get('exclude'):
                    if match:
                        return False
                    continue
            elif kind == 'person':
                match = any(str(p['tmdb_id']) == identity and p.get('kind') == value['role'] for p in row.get('credits', []))
            elif kind == 'keyword':
                match = identity in {str(x['id']) for x in row.get('keywords', [])}
            elif kind in {'year', 'rating', 'runtime', 'minimum_votes'}:
                actual = row.get({'year': 'first_air_date', 'rating': 'rating', 'runtime': 'runtime', 'minimum_votes': 'votes'}[kind])
                if kind == 'year':
                    actual = int(actual[:4]) if actual and str(actual)[:4].isdigit() else None
                limits = runtime_bounds(value) if kind == 'runtime' else (value['value'], None) if kind == 'minimum_votes' else bounds(value)
                match = within(actual, *limits)
            elif kind == 'language':
                match = identity == row.get('original_language')
            elif kind == 'country':
                match = identity in row.get('origin_country', [])
            elif kind == 'tv_status':
                match = row.get('status', '').casefold() == TV_STATUS_NAMES[identity].casefold()
            elif kind == 'viewing_status':
                count = row.get('released_count', row.get('episode_count')) or 0
                watched = bool(row['series_watched']) if 'series_watched' in row else count > 0 and row.get('completed_count', 0) >= count
                if identity == 'watchlist':
                    match = bool(row.get('watchlisted'))
                elif identity == 'watched':
                    match = watched
                elif identity == 'in_progress':
                    match = row.get('last_played', 0) > 0 and row.get('completed_count', 0) < count
                else:
                    match = not watched
            elif kind == 'availability':
                owned = row.get('available_count', 0) > 0
                match = owned if identity == 'owned' else not owned
            elif kind == 'resolution':
                ranks = [quality_rank(f.get('quality_class')) for f in row.get('file_facts', [])]
                if identity == 'upgrade':
                    match = bool(row.get('upgrade_candidate'))
                elif identity == 'below-720p':
                    match = 1 in ranks
                else:
                    match = quality_rank(identity) in ranks
            elif kind == 'library_source':
                match = identity in row.get('sources', [])
            else:
                raise ValueError(f'{kind} has no TV equivalent')
            checks.append(match)
        if checks and not (all(checks) if group.get('join') == 'and' else any(checks)):
            return False
    return True


def sort_rows(rows, key, direction='desc'):
    fields = {'added': 'updated_at', 'recently_added': 'updated_at', 'rating': 'rating', 'vote_average.desc': 'rating',
              'popularity.desc': 'popularity', 'vote_count.desc': 'votes', 'year': 'first_air_date',
              'year-desc': 'first_air_date', 'year-asc': 'first_air_date', 'primary_release_date.desc': 'first_air_date',
              'recently_played': 'last_played', 'recently_aired': 'recently_aired'}
    if key in {'auto', 'provider'}:
        return rows
    rows = sorted(rows, key=lambda r: r['tmdb_id'])
    if key in {'title', 'title.asc'}:
        return sorted(rows, key=lambda r: text_key(r['title']))
    if key == 'quality':
        getter = lambda r: max((quality_rank(f.get('quality_class')) for f in r.get('file_facts', [])), default=0)
    elif key == 'progress':
        getter = lambda r: r.get('watched_percent') if r.get('watched_percent') is not None else -1
    elif key == 'missing':
        getter = lambda r: r.get('episode_count', 0) - r.get('available_count', 0)
    else:
        field = fields.get(key)
        if not field:
            raise ValueError('Unsupported TV sort')
        fallback = 0 if field in {'rating', 'popularity', 'votes', 'updated_at', 'last_played'} else ''
        getter = lambda r: (r.get(field) is not None, r.get(field) if r.get(field) is not None else fallback)
    return sorted(rows, key=getter, reverse=key != 'year-asc' and direction != 'asc')


class TVSearch:
    def __init__(self, read_model, metadata, profile=None):
        self.read = read_model
        self.repository = read_model.repository
        self.metadata = metadata
        self.profile = profile
        self._scans, self._scan_lock = {}, threading.RLock()

    @staticmethod
    def normalize(query, scope):
        query = dict(query)
        if query.pop('media_type', 'tv') != 'tv':
            raise ValueError('TV search requires a TV query')
        result = normalize_query(query, scope, media_type='tv')
        if any(g['type'] == 'movie_list' for g in result['groups']):
            raise ValueError('Movie lists cannot filter TV series')
        return result

    def local_rows(self):
        today = date.today().isoformat()
        with self.repository.store.connection() as db:
            rows = {r['id']: {**json.loads(r['metadata']), 'id': r['id'], 'tmdb_id': r['tmdb_id'], 'title': r['title'],
                             'updated_at': r['updated_at'], 'episode_count': 0, 'available_count': 0, 'completed_count': 0,
                             'last_played': 0, 'recently_aired': '', 'file_facts': [], 'episode_files': {}, 'sources': [],
                             'watchlisted': False} for r in db.execute('SELECT * FROM series')}
            for r in db.execute('SELECT * FROM series_curation'):
                if r['series_id'] in rows:
                    rows[r['series_id']]['watchlisted'] = bool(r['watchlisted'])
            for r in db.execute('SELECT e.*,p.completed,p.last_played FROM episodes e LEFT JOIN playback_progress p ON p.episode_id=e.id'):
                item = rows[r['series_id']]
                if r['air_date'] and r['air_date'] <= today:
                    item['episode_count'] += 1
                    item['completed_count'] += bool(r['completed'])
                    item['recently_aired'] = max(item['recently_aired'], r['air_date'])
                item['last_played'] = max(item['last_played'], r['last_played'] or 0)
            available = set()
            exists = {}
            for r in db.execute('SELECT e.id AS episode_id,e.series_id,e.air_date,f.* FROM episodes e JOIN episode_file_bindings b ON b.episode_id=e.id JOIN media_files f ON f.id=b.file_id'):
                path = r['path']
                if path not in exists:
                    exists[path] = Path(path).is_file()
                if not r['available'] or not exists[path]:
                    continue
                item = rows[r['series_id']]
                facts = json.loads(r['facts'])
                item['file_facts'].append(facts)
                item['episode_files'].setdefault(r['episode_id'], []).append(facts)
                item['sources'].append(source_claim(Path(path).name))
                if r['air_date'] and r['air_date'] <= today:
                    available.add((r['series_id'], r['episode_id']))
            for series_id, _ in available:
                rows[series_id]['available_count'] += 1
        for item in rows.values():
            item.update(self.read.coverage(item, self.repository.episodes(item['id'])))
        if self.profile:
            from services.acquisition_decision import below_profile_cutoff
            profile = self.profile()
            for item in rows.values():
                item['upgrade_candidate'] = any(below_profile_cutoff(files, profile) for files in item['episode_files'].values())
        return list(rows.values())

    def library(self, query, page=1, page_size=24, extras=None):
        query = self.normalize(query, 'library')
        page, page_size = max(1, int(page)), min(100, max(1, int(page_size)))
        extras = extras or {}
        with self.repository.store.connection() as db:
            assigned_ids = {row[0] for row in db.execute('SELECT DISTINCT series_id FROM tv_path_assignments')}
        rows = [r for r in self.local_rows() if (r['available_count'] > 0 or r['pending_review_count'] > 0 or r['id'] in assigned_ids)
                and matches(r, query)]
        monitored = set(extras.get('monitored_ids', []))
        if extras.get('progress') not in {None, '', 'watched', 'unwatched', 'in_progress'}:
            raise ValueError('Unsupported TV progress filter')
        def extra_match(r):
            status = str(r.get('status', '')).lower()
            status = 'Continuing' if status in {'returning series', 'continuing', 'in production', 'planned'} else 'Ended' if status in {'ended', 'canceled', 'cancelled'} else 'Limited Series' if status == 'limited series' else 'Status Unknown'
            return (not extras.get('genre') or extras['genre'] in r.get('genres', [])) and (
                not extras.get('year') or str(r.get('first_air_date', ''))[:4] == str(extras['year'])) and (
                not extras.get('minimum_rating') or float(r.get('rating') or 0) >= float(extras['minimum_rating'])) and (
                not extras.get('quality') or any(quality_rank(f.get('quality_class')) == quality_rank(extras['quality']) for f in r['file_facts'])) and (not extras.get('status') or status == extras['status']) and (
                not extras.get('monitoring') or (r['tmdb_id'] in monitored) == (extras['monitoring'] == 'monitored')) and (
                not extras.get('progress') or {'watched': r['series_watched'],
                'unwatched': not r['completed_count'], 'in_progress': r['last_played'] > 0 and r['completed_count'] < r['episode_count']}[extras['progress']]) and (
                not extras.get('availability') or (r['available_count'] > 0 if extras['availability'] == 'available' else r['available_count'] < r['episode_count'])) and (
                not extras.get('language') or any(set(audio_languages({'audio_language': extras['language']})) & set(audio_languages(f)) for f in r['file_facts']))
        rows = [r for r in rows if extra_match(r)]
        rows = sort_rows(rows, extras.get('sort') or query['sort']['key'], query['sort']['direction'])
        total = len(rows)
        selected = rows[(page-1)*page_size:page*page_size]
        items = [{**self.read.detail(r['id']), 'watchlisted': r['watchlisted']} for r in selected]
        # The legacy local adapter deliberately has no network metadata owner.
        # Persisted display fields remain usable while offline.
        if self.metadata is not None:
            items = [self.metadata.display(row) for row in items]
        return {'items': items,
                'page': page, 'page_size': page_size, 'total': total, 'total_pages': max(1, math.ceil(total/page_size)), 'complete': True}

    def options(self, scope):
        if scope not in {'library', 'discover'}:
            raise ValueError('Invalid TV scope')
        rows = self.local_rows() if scope == 'library' else []
        def choices(pairs):
            labels = {}
            for key, label in pairs:
                if key not in labels or labels[key] == key:
                    labels[key] = label
            return [{'id': key, 'label': label} for key, label in sorted(labels.items(), key=lambda x: x[1])]
        if scope == 'library':
            return {'genre': choices((str(g['id']), g['name']) for r in rows for g in (r.get('genre_records') or [{'id': name, 'name': name} for name in r.get('genres', [])])),
                    'language': choices((r['original_language'], r.get('original_language_name') or r['original_language']) for r in rows if r.get('original_language')),
                    'country': choices((c, c) for r in rows for c in r.get('origin_country', [])),
                    'library_source': choices((s, SOURCES[s]['label']) for r in rows for s in r['sources'])}
        return {'tv_status': [{'id': key, 'label': label} for key, label in TV_STATUS_CHOICES],
                'genre': choices((str(g['id']), g['name']) for g in self.metadata.request('/genre/tv/list')['genres']),
                'language': choices((r['iso_639_1'], r.get('english_name') or r['iso_639_1']) for r in self.metadata.request('/configuration/languages')),
                'country': choices((r['iso_3166_1'], r.get('english_name') or r['iso_3166_1']) for r in self.metadata.request('/configuration/countries'))}

    def identities(self, scope, kind, text):
        if scope not in {'library', 'discover'}:
            raise ValueError('Invalid TV scope')
        if kind not in {'person', 'keyword'}:
            raise ValueError('Unknown TV identity type')
        if len(text.strip()) < 2:
            return []
        if scope == 'library':
            values = {}
            for row in self.local_rows():
                for value in row.get('credits' if kind == 'person' else 'keywords', []):
                    name = value['name']
                    if text_key(text) in text_key(name):
                        identity = value.get('tmdb_id', value.get('id'))
                        values[str(identity)] = {'id': str(identity), 'label': name}
            return sorted(values.values(), key=lambda v: v['label'])[:20]
        return [{'id': str(r['id']), 'label': r['name']} for r in self.metadata.request(f'/search/{kind}', query=text)['results'][:20]]

    def discover(self, query, page=1, page_size=20):
        query = self.normalize(query, 'discover')
        deadline = time.monotonic() + 15
        page = min(500, max(1, int(page)))
        page_size = min(100, max(1, int(page_size)))
        groups = {g['type']: g for g in query['groups']}
        local = {r['tmdb_id']: r for r in self.local_rows()}
        params = {}
        mapping = {'genre': 'with_genres', 'keyword': 'with_keywords', 'language': 'with_original_language', 'country': 'with_origin_country'}
        for kind, param in mapping.items():
            if kind in groups:
                g = groups[kind]
                params[param] = (',' if g.get('join') == 'and' else '|').join(v['id'] for v in g['values'] if not v.get('exclude'))
                if kind == 'genre':
                    params['without_genres'] = ','.join(v['id'] for v in g['values'] if v.get('exclude'))
        if 'tv_status' in groups:
            params['with_status'] = groups['tv_status']['values'][0]['id']
        for kind, param in [('year', 'first_air_date'), ('rating', 'vote_average'), ('runtime', 'with_runtime'), ('minimum_votes', 'vote_count')]:
            if kind in groups:
                value = groups[kind]['values'][0]
                lo, hi = runtime_bounds(value) if kind == 'runtime' else (value['value'], None) if kind == 'minimum_votes' else bounds(value)
                if lo is not None:
                    params[param+'.gte'] = f'{lo}-01-01' if kind == 'year' else lo
                if hi is not None:
                    params[param+'.lte'] = f'{hi}-12-31' if kind == 'year' else hi
        sort = query['sort']['key']
        if sort != 'auto':
            params['sort_by'] = {'primary_release_date.desc': 'first_air_date.desc', 'title.asc': 'name.asc'}.get(sort, sort)
        feed = query.get('feed', 'trending_week')
        path = '/discover/tv'
        finite = None
        if 'person' in groups:
            candidates = {}
            for value in groups['person']['values']:
                credits = self.metadata.request(f"/person/{int(value['id'])}/tv_credits", _timeout=5, _attempts=1, _deadline=deadline)
                for row in credits.get('cast' if value['role'] == 'actor' else 'crew', []):
                    role = 'actor' if value['role'] == 'actor' else 'director' if row.get('job') == 'Director' else 'creator' if row.get('job') == 'Creator' else 'writer' if row.get('department') == 'Writing' else ''
                    if role != value['role']:
                        continue
                    candidate = candidates.setdefault(row['id'], {**self.metadata.normalize(row), 'credits': []})
                    candidate['credits'].append({'tmdb_id': int(value['id']), 'kind': role, 'name': value['label']})
            finite = list(candidates.values())
            if 'title' in groups:
                title_query = {**query, 'groups': [groups['title']]}
                finite = [r for r in finite if matches(r, title_query)]
            items = finite
            total_pages, provider_total = 1, len(finite)
        else:
            if 'title' in groups:
                path, params = '/search/tv', {'query': groups['title']['values'][0]['text']}
            elif not groups and sort == 'auto':
                path = {'trending_week': '/trending/tv/week', 'trending_today': '/trending/tv/day', 'popular': '/tv/popular',
                        'top_rated': '/tv/top_rated', 'best_all_time': '/tv/top_rated', 'now_playing': '/tv/on_the_air', 'upcoming': '/tv/airing_today'}.get(feed, path)
        post_filter = bool('title' in groups or 'person' in groups or set(groups) & {'availability', 'viewing_status'})
        needs_detail = bool(('tv_status' in groups and post_filter) or
                            (set(groups) & {'keyword', 'runtime'} and ('title' in groups or 'person' in groups)))
        def enrich(row):
            if needs_detail:
                try:
                    row = {**row, **self.metadata.preview(row['tmdb_id'], fast=True, deadline=deadline)}
                except (OSError, ValueError, KeyError):
                    row = {**row, 'metadata_notice': 'Some metadata is unavailable; retry to include missing matches.'}
            elif 'tv_status' in groups and path == '/discover/tv' and not row.get('status'):
                # TMDB discover summaries omit status even when with_status selected it.
                row = {**row, 'status': TV_STATUS_NAMES[groups['tv_status']['values'][0]['id']]}
            own = local.get(row['tmdb_id'], {})
            row = {**row, **{k: own.get(k, default) for k, default in [('id', None), ('watchlisted', False), ('available_count', 0), ('completed_count', 0), ('last_played', 0)]}, 'media_type': 'tv'}
            if own:
                detail = self.read.detail(own['id'])
                row.update({key: detail.get(key) for key in ('poster_url', 'provider_poster_url', 'poster_override',
                    'primary_action', 'episode_count', 'available_count', 'completed_count', 'offline_percent',
                    'watched_percent', 'coverage_complete', 'pending_review_count', 'series_watched',
                    'watchlisted', 'season_count', 'status_label', 'year_range', 'quality_label')})
                row['released_count'] = own.get('episode_count', 0)
            return self.metadata.display(row, deadline=deadline) if hasattr(self.metadata, 'display') else row
        if post_filter:
            # Retain unprocessed/failed detail rows so an outage cannot silently
            # turn a partial filter into a complete zero-result answer.
            local_revision = [(r['tmdb_id'], r['available_count'], r['completed_count'], r['watchlisted'], r['last_played']) for r in local.values()]
            key = json.dumps([query, local_revision], sort_keys=True)
            with self._scan_lock:
                now = time.monotonic()
                self._scans = {k:v for k,v in self._scans.items() if now-v['time'] < 300}
                state = self._scans.setdefault(key, {'time':now, 'next':1, 'items':{},
                    'pending':{r['tmdb_id']:r for r in finite or []}, 'seen':set(), 'exhausted':finite is not None})
                attempted, pages_scanned = set(), 0
                while time.monotonic() < deadline:
                    if len(state['items']) >= page*page_size and finite is None: break
                    pending = [r for identity,r in state['pending'].items() if identity not in attempted][:TMDB_PAGE_SIZE]
                    if pending:
                        attempted.update(r['tmdb_id'] for r in pending)
                        with ThreadPoolExecutor(max_workers=4) as pool:
                            enriched = list(pool.map(enrich, pending))
                        for row in enriched:
                            if row.get('metadata_notice'): continue
                            state['pending'].pop(row['tmdb_id'], None)
                            state['seen'].add(row['tmdb_id'])
                            if matches(row, query): state['items'][row['tmdb_id']] = row
                        continue
                    if state['exhausted'] or pages_scanned >= 3: break
                    provider_page = state['next']
                    try:
                        raw = self.metadata.request(path, page=provider_page, **params, _timeout=5, _attempts=1, _deadline=deadline)
                    except (OSError, ValueError, KeyError):
                        break
                    state['pending'].update((r['id'], self.metadata.normalize(r)) for r in raw.get('results', []) if r['id'] not in state['seen'])
                    state['next'] += 1
                    pages_scanned += 1
                    state['exhausted'] = provider_page >= min(500, raw.get('total_pages', 1))
                complete = state['exhausted'] and not state['pending']
                rows = list(state['items'].values())
                if complete:
                    rows = sort_rows(rows, sort if sort != 'auto' else 'popularity.desc' if finite is not None else 'provider', query['sort']['direction'])
                displayed = rows[(page-1)*page_size:page*page_size]
                return {'items': displayed, 'page': page, 'page_size': page_size,
                        'total_pages': max(1, math.ceil(len(rows)/page_size)) if complete else None,
                        'total': len(rows) if complete else None, 'complete': complete,
                        'has_next': len(rows)>page*page_size or (not complete and len(displayed)==page_size),
                        'continue_scan': not complete and len(displayed)<page_size,
                        'notice': '' if complete else 'Search is incomplete. Continue searching to retry missing metadata and find more matches; totals and ordering are partial.'}
        offset = (page - 1) * page_size
        first_provider_page = offset // TMDB_PAGE_SIZE + 1
        if first_provider_page > 500:
            raise ValueError('TV page exceeds the available TMDB results')
        raw = self.metadata.request(path, page=first_provider_page, **params, _timeout=5, _attempts=1, _deadline=deadline)
        provider_pages = min(500, max(1, int(raw.get('total_pages') or 1)))
        provider_total = min(max(0, int(raw.get('total_results') or 0)), provider_pages * TMDB_PAGE_SIZE)
        last_provider_page = min(provider_pages, (offset + page_size - 1) // TMDB_PAGE_SIZE + 1)
        raw_pages = [raw]
        remaining_pages = range(first_provider_page + 1, last_provider_page + 1)
        with ThreadPoolExecutor(max_workers=min(4, max(1, len(remaining_pages)))) as pool:
            raw_pages.extend(pool.map(
                lambda provider_page: self.metadata.request(
                    path, page=provider_page, **params, _timeout=5, _attempts=1, _deadline=deadline
                ), remaining_pages
            ))
        items = [self.metadata.normalize(row) for batch in raw_pages for row in batch.get('results', [])]
        items = items[offset % TMDB_PAGE_SIZE:offset % TMDB_PAGE_SIZE + page_size]
        with ThreadPoolExecutor(max_workers=4) as pool:
            items = list(pool.map(enrich, items))
        total_pages = max(1, math.ceil(provider_total / page_size))
        return {'items': items, 'page': page, 'page_size': page_size,
                'total_pages': total_pages, 'total': provider_total,
                'has_next': page < total_pages, 'complete': True}
