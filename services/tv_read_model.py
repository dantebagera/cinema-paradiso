import json
from pathlib import Path

from services.tv_catalog_repository import released
from services.media_file_facts import audio_languages


def year_range(metadata):
    start = str(metadata.get('first_air_date') or '')[:4]
    end = str(metadata.get('last_air_date') or '')[:4]
    if not start:
        return ''
    status = str(metadata.get('status') or '').lower()
    if status in {'returning series', 'continuing', 'in production', 'planned'}:
        return f'{start}–Present'
    if status in {'ended', 'canceled', 'cancelled', 'limited series'} and end:
        return start if start == end else f'{start}–{end}'
    return f'{start}–'


class TVReadModel:
    def __init__(self, repository):
        self.repository = repository

    def coverage(self, series, rows):
        """The only TV episode-count policy used by cards, detail and search."""
        regular = [row for row in rows if row['season_number'] > 0]
        released_regular = [row for row in regular if row['released']]
        specials = [row for row in rows if row['season_number'] == 0]
        future = [row for row in regular if row['air_date'] and not row['released']]
        unknown = [row for row in regular if not row['air_date']]
        hydration = self.repository.hydration(series['id'])
        listed = {int(season['season_number']): int(season.get('episode_count') or 0)
                  for season in series.get('seasons', []) if int(season['season_number']) > 0}
        loaded = {number: sum(row['season_number'] == number for row in regular) for number in listed}
        complete = (hydration['status'] == 'complete' and bool(listed)
                    and all(loaded[number] == expected for number, expected in listed.items())
                    and {row['season_number'] for row in regular}.issubset(set(listed))
                    and not any(row['reconciliation_required'] for row in rows))
        offline = sum(row['available'] for row in released_regular)
        watched = sum(bool(row['completed']) for row in released_regular)
        total = len(released_regular)
        with self.repository.store.connection() as db:
            pending = db.execute("SELECT COUNT(*) FROM ingestion_candidates WHERE state='needs_review' "
                                 "AND CAST(json_extract(payload,'$.series_id') AS INTEGER)=?", (series['id'],)).fetchone()[0]
            show_action = db.execute('SELECT 1 FROM series_watched_actions WHERE series_id=?', (series['id'],)).fetchone() is not None
        percent = lambda count: min(100, max(0, int(100 * count / total + 0.5))) if complete and total else None
        return {'episode_count': total, 'available_count': offline, 'completed_count': watched,
                'offline_percent': percent(offline), 'watched_percent': percent(watched),
                'coverage_complete': complete, 'hydration_status': hydration['status'],
                'hydration_error': hydration.get('error', ''), 'pending_review_count': pending,
                'specials_count': len(specials), 'specials_offline_count': sum(row['available'] for row in specials),
                'specials_watched_count': sum(bool(row['completed']) for row in specials),
                'future_count': len(future), 'unknown_date_count': len(unknown),
                'series_watched': bool(complete and total and watched == total
                                       and str(series.get('status') or '').casefold() == 'ended'),
                'series_watched_action_active': show_action}

    def maintenance(self, *, query='', page=1, page_size=50):
        """Paginated TV-only review and exclusion projection for Maintenance."""
        page = max(1, int(page))
        page_size = min(100, max(1, int(page_size)))
        items = []
        with self.repository.store.connection() as db:
            for row in db.execute("SELECT path,state,payload FROM tv_discovery_units WHERE state IN ('review','scan_error')"):
                payload = json.loads(row['payload'])
                items.append({'kind': 'show_folder', 'state': row['state'], **payload})
            for row in db.execute("SELECT c.id,c.payload,c.reason,s.title AS series_title FROM ingestion_candidates c "
                                  "LEFT JOIN series s ON s.id=CAST(json_extract(c.payload,'$.series_id') AS INTEGER) "
                                  "WHERE c.state='needs_review' ORDER BY c.id"):
                payload = json.loads(row['payload'])
                reason = row['reason']
                items.append({'kind': 'episode_file', 'state': 'conflict' if 'conflict' in reason.casefold() or
                              'collision' in reason.casefold() else 'review', 'review_id': row['id'],
                              'path': payload.get('path'), 'series_id': payload.get('series_id'),
                              'series_title': row['series_title'], 'claim': payload.get('claim'),
                              'files': 1, 'sample_filenames': [Path(payload.get('path') or '').name], 'reason': reason})
            for row in db.execute('SELECT path,kind,reason FROM tv_exclusions'):
                items.append({'kind': 'exclusion', 'state': 'excluded', 'path': row['path'],
                              'files': 1 if row['kind'] == 'file' else None, 'reason': row['reason']})
        needle = str(query or '').casefold().strip()
        if needle:
            items = [item for item in items if needle in ' '.join(str(item.get(key) or '') for key in
                     ('path', 'series_title', 'title_hint', 'reason')).casefold()]
        counts = {'unidentified_folders': sum(item['kind'] == 'show_folder' and item['state'] == 'review' for item in items),
                  'unresolved_episode_files': sum(item['kind'] == 'episode_file' and item['state'] == 'review' for item in items),
                  'conflicts': sum(item['state'] == 'conflict' for item in items),
                  'scan_errors': sum(item['state'] == 'scan_error' for item in items),
                  'exclusions': sum(item['state'] == 'excluded' for item in items)}
        items.sort(key=lambda item: (item['kind'], str(item.get('series_title') or item.get('title_hint') or '').casefold(), item['path'] or ''))
        total = len(items)
        return {'items': items[(page-1)*page_size:page*page_size], 'counts': counts,
                'total': total, 'page': page, 'page_size': page_size,
                'total_pages': max(1, (total+page_size-1)//page_size)}

    def tv_lists(self, *, list_id=None, query='', page=1, page_size=40, status='all'):
        custom = self.repository.tv_lists()
        with self.repository.store.connection() as db:
            watchlisted = {row[0] for row in db.execute('SELECT series_id FROM series_curation WHERE watchlisted=1')}
            played = {row[0] for row in db.execute('SELECT DISTINCT e.series_id FROM episodes e '
                'JOIN playback_progress p ON p.episode_id=e.id WHERE p.completed=1')}
        watched = {series_id for series_id in played if self.detail(series_id)['series_watched']}
        lists = [{'id': 'watched', 'name': 'Watched', 'count': len(watched), 'system': True},
                 {'id': 'watchlist', 'name': 'Watchlist', 'count': len(watchlisted), 'system': True}]
        lists += [{'id': item['id'], 'name': item['name'], 'count': len(item['series_ids']), 'system': False}
                  for item in custom]
        if list_id is None:
            return {'lists': lists}
        if list_id == 'watched':
            ids = watched
        elif list_id == 'watchlist':
            ids = watchlisted
        else:
            match = next((item for item in custom if item['id'] == list_id), None)
            if not match:
                raise LookupError('TV list not found')
            ids = set(match['series_ids'])
        needle = str(query or '').casefold().strip()
        items = [self.detail(series_id) for series_id in ids]
        if needle:
            items = [item for item in items if needle in item['title'].casefold()]
        if status not in {'all', 'offline', 'missing', 'watched'}:
            raise ValueError('Unknown TV list filter')
        if status == 'offline':
            items = [item for item in items if item['available_count'] > 0]
        elif status == 'missing':
            items = [item for item in items if item['coverage_complete'] and item['available_count'] < item['episode_count']]
        elif status == 'watched':
            items = [item for item in items if item['series_watched']]
        items.sort(key=lambda row: row['title'].casefold())
        page = max(1, int(page))
        page_size = min(100, max(1, int(page_size)))
        total = len(items)
        return {'lists': lists, 'items': items[(page-1)*page_size:page*page_size],
                'total': total, 'page': page, 'page_size': page_size,
                'total_pages': max(1, (total+page_size-1)//page_size)}

    def files(self, *, query='', page=1, page_size=50):
        """Read TV-owned physical files without consulting the Movie catalog."""
        page = max(1, int(page))
        page_size = min(100, max(1, int(page_size)))
        needle = str(query or '').strip().lower()
        pattern = f'%{needle}%'
        predicate = '''(? = '' OR lower(f.path) LIKE ? OR EXISTS (
            SELECT 1 FROM episode_file_bindings match_binding
            JOIN episodes match_episode ON match_episode.id=match_binding.episode_id
            JOIN series match_series ON match_series.id=match_episode.series_id
            WHERE match_binding.file_id=f.id AND
              (lower(match_series.title) LIKE ? OR lower(match_episode.title) LIKE ?)
        ))'''
        args = (needle, pattern, pattern, pattern)
        with self.repository.store.connection() as db:
            total = db.execute(f'SELECT COUNT(*) FROM media_files f WHERE {predicate}', args).fetchone()[0]
            rows = db.execute(
                f'SELECT f.* FROM media_files f WHERE {predicate} ORDER BY f.created_at DESC,f.id DESC LIMIT ? OFFSET ?',
                (*args, page_size, (page - 1) * page_size)
            ).fetchall()
            items = []
            for row in rows:
                bindings = [dict(bound) for bound in db.execute('''
                    SELECT e.id AS episode_id,e.series_id,e.season_number,e.episode_number,e.title AS episode_title,
                           s.title AS series_title,s.tmdb_id
                    FROM episode_file_bindings b JOIN episodes e ON e.id=b.episode_id
                    JOIN series s ON s.id=e.series_id WHERE b.file_id=?
                    ORDER BY s.title,e.season_number,e.episode_number
                ''', (row['id'],))]
                items.append({
                    'file_id': row['id'], 'path': row['path'], 'filename': Path(row['path']).name,
                    'size': row['size'], 'modified_ns': row['modified_ns'], 'available': bool(row['available']),
                    'facts': json.loads(row['facts'] or '{}'), 'episodes': bindings
                })
        return {'items': items, 'total': total, 'page': page, 'page_size': page_size,
                'total_pages': max(1, (total + page_size - 1) // page_size)}

    def detail(self, series_id):
        series = self.repository.series(series_id)
        rows = self.repository.episodes(series_id)
        coverage = self.coverage(series, rows)
        regular = [row for row in rows if row['season_number'] > 0]
        released_regular = [row for row in regular if row['released']]
        available = [row for row in rows if row['available'] and row['released']]
        cursor = self.repository.viewing_cursor(series_id)
        played = next((row for row in regular if cursor and row['id'] == cursor['episode_id']), None)
        if played and not played['completed']:
            current, label = played, 'Resume'
        elif played:
            current = next((row for row in regular if (row['season_number'], row['episode_number']) >
                            (played['season_number'], played['episode_number'])), None)
            label = 'Play next'
        else:
            current = released_regular[0] if released_regular else None
            label = 'Start'
        stream_target = current
        def target(row):
            return {'episode_id': row['id'], 'tmdb_id': series['tmdb_id'], 'season_number': row['season_number'], 'episode_number': row['episode_number'], 'title': row['title'], 'code': row['code'], 'released': row['released'] and not row['reconciliation_required']} if row else None
        qualities, languages = set(), set()
        for row in available:
            for version in row['versions']:
                if version['available']:
                    qualities.add(version['facts'].get('quality_class') or 'Unknown')
                    languages.update(audio_languages(version['facts']) or ['Unknown'])
        status = str(series.get('status') or '').lower()
        status = 'Continuing' if status in {'returning series', 'continuing', 'in production', 'planned'} else 'Ended' if status == 'ended' else 'Canceled' if status in {'canceled', 'cancelled'} else 'Limited Series' if status == 'limited series' else 'Status Unknown'
        seasons = []
        listed = {s['season_number']: s for s in series.get('seasons', [])}
        for number in sorted({row['season_number'] for row in rows} | set(listed)):
            items = [row for row in rows if row['season_number'] == number]
            seasons.append({'number': number, 'title': 'Specials' if number == 0 else f'Season {number}', 'episodes': listed.get(number, {}).get('episode_count', len(items)), 'available': sum(row['available'] for row in items), 'completed': sum(bool(row['completed']) for row in items)})
        action_reason = ('Episode numbering needs review' if current and current['reconciliation_required'] else
                         'Next episode has not aired' if current and not current['released'] else
                         'Current episode is missing locally' if current and not current['available'] else
                         'Caught up' if played and coverage['coverage_complete'] and current is None else
                         'Next episode is unknown until metadata is complete' if played and current is None else '')
        return {**series, 'media_type': 'tv', 'year_range': year_range(series), 'status_label': status,
                'season_count': sum(s['number'] > 0 for s in seasons), 'has_specials': any(s['number'] == 0 for s in seasons),
                **coverage, 'announced_count': coverage['future_count'],
                'quality_label': next(iter(qualities)) if len(qualities) == 1 else 'Mixed quality' if qualities else '',
                'language_label': next(iter(languages)) if len(languages) == 1 else 'Mixed languages' if languages else '',
                'seasons': seasons, 'default_season': current['season_number'] if current else next((s['number'] for s in seasons if s['available']), next((s['number'] for s in reversed(seasons) if s['number'] > 0), 0)),
                'primary_action': {'label': label, 'target': target(current), 'playable': bool(current and current['released'] and current['available'] and not current['reconciliation_required']), 'reason': action_reason,
                                   'position_ms': int(current['position_ms'] or 0) if current and label == 'Resume' else 0},
                'stream_target': target(stream_target), 'last_played': max((row['last_played'] or 0 for row in rows), default=0)}

    def library(self, *, query='', page=1, page_size=24, status='', sort='title', availability='', genre='', year='', minimum_rating=0, progress='', quality='', language='', monitoring='', monitored_ids=None):
        # Legacy parameter adapter. TVSearch is the single catalog-query owner.
        from services.tv_search import TVSearch
        payload = {'version': 1, 'scope': 'library', 'mode': 'simple', 'groups': [], 'sort': {'key': 'title', 'direction': 'asc'}}
        if query:
            payload['groups'].append({'type': 'title', 'values': [{'text': query}]})
        extras = dict(status=status, sort=sort, availability=availability, genre=genre, year=year,
                      minimum_rating=minimum_rating, progress=progress, quality=quality, language=language,
                      monitoring=monitoring, monitored_ids=monitored_ids or set())
        return TVSearch(self, None).library(payload, page, page_size, extras)

    def continue_watching(self):
        with self.repository.store.connection() as db:
            ids = [row[0] for row in db.execute('SELECT DISTINCT e.series_id FROM episodes e JOIN playback_progress p ON p.episode_id=e.id WHERE p.hidden=0 ORDER BY p.last_played DESC LIMIT 50')]
        return [{**item, 'path_key': f"tv:series:{item['id']}"} for item in (self.detail(value) for value in ids) if item['primary_action']['target']]
