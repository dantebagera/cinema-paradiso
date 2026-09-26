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
        regular = [row for row in rows if row['season_number'] > 0 and row['released']]
        available = [row for row in rows if row['available'] and row['released']]
        unfinished = [row for row in rows if row['released'] and row['position_ms'] and not row['completed']]
        current = max(unfinished, key=lambda row: row['last_played'] or 0) if unfinished else next((row for row in regular if not row['completed']), None)
        if current is None:
            current = next((row for row in rows if row['released'] and not row['completed']), None)
        stream_target = current or next((row for row in regular), next((row for row in rows if row['released']), None))
        def target(row):
            return {'episode_id': row['id'], 'tmdb_id': series['tmdb_id'], 'season_number': row['season_number'], 'episode_number': row['episode_number'], 'title': row['title'], 'code': row['code'], 'released': row['released'] and not row['reconciliation_required']} if row else None
        qualities, languages = set(), set()
        for row in available:
            for version in row['versions']:
                if version['available']:
                    qualities.add(version['facts'].get('quality_class') or 'Unknown')
                    languages.update(audio_languages(version['facts']) or ['Unknown'])
        status = str(series.get('status') or '').lower()
        status = 'Continuing' if status in {'returning series', 'continuing', 'in production', 'planned'} else 'Ended' if status in {'ended', 'canceled', 'cancelled'} else 'Limited Series' if status == 'limited series' else 'Status Unknown'
        seasons = []
        listed = {s['season_number']: s for s in series.get('seasons', [])}
        for number in sorted({row['season_number'] for row in rows} | set(listed)):
            items = [row for row in rows if row['season_number'] == number]
            seasons.append({'number': number, 'title': 'Specials' if number == 0 else f'Season {number}', 'episodes': listed.get(number, {}).get('episode_count', len(items)), 'available': sum(row['available'] for row in items), 'completed': sum(bool(row['completed']) for row in items)})
        label = 'Resume' if unfinished else 'Play next' if any(row['completed'] for row in rows) else 'Start'
        return {**series, 'media_type': 'tv', 'year_range': year_range(series), 'status_label': status,
                'season_count': sum(s['number'] > 0 for s in seasons), 'has_specials': any(s['number'] == 0 for s in seasons),
                'episode_count': sum(row['released'] for row in rows), 'announced_count': sum(not row['released'] for row in rows),
                'available_count': len(available), 'completed_count': sum(bool(row['completed']) for row in rows),
                'quality_label': next(iter(qualities)) if len(qualities) == 1 else 'Mixed quality' if qualities else '',
                'language_label': next(iter(languages)) if len(languages) == 1 else 'Mixed languages' if languages else '',
                'seasons': seasons, 'default_season': current['season_number'] if current else next((s['number'] for s in seasons if s['available']), next((s['number'] for s in reversed(seasons) if s['number'] > 0), 0)),
                'primary_action': {'label': label, 'target': target(current), 'playable': bool(current and current['available'] and not current['reconciliation_required']), 'reason': 'Episode numbering needs review' if current and current['reconciliation_required'] else '' if current and current['available'] else 'Current episode is missing locally'},
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
