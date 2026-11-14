"""Ordered, catalog-owned native playlists; never accepts paths from the player."""
import json
import sqlite3

from services.identity_decision import normalize_movie_title, resolve_collection_membership


def collection_queue(collection, owned, *, current):
    by_path = {}
    records = []
    for row in [*owned, current]:
        if not row.get('path_key'):
            continue
        path = str(row.get('path') or row['path_key'])
        # Current selection supplies the exact version, not a duplicate movie entry.
        previous = by_path.get(path) or {}
        record = {**previous, **row, 'path': path}
        by_path[path] = record
    records = list(by_path.values())
    items, seen = [], set()
    parts = sorted(collection.get('parts') or [], key=lambda row: (
        str(row.get('release_date') or (str(row['year']) + '-00-00' if row.get('year') else '9999')),
        str(row.get('title') or '').casefold(), str(row.get('tmdb_id') or row.get('id') or '')))
    for index, part in enumerate(parts):
        part = {**part, 'tmdb_id': str(part.get('tmdb_id') or part.get('id') or '')}
        identity = (('tmdb:' + part['tmdb_id']) if part['tmdb_id'] else
                    ('imdb:' + str(part['imdb_id']).lower()) if part.get('imdb_id') else
                    str(part.get('path') or ('title:' + normalize_movie_title(part.get('title')) + ':' + str(part.get('year') or ''))))
        if identity in seen:
            continue
        seen.add(identity)
        resolution = resolve_collection_membership({'parts': [part]}, records)
        paths = resolution['owned_paths'] or [path for conflict in resolution['conflicts'] for path in conflict['paths']]
        current_path = str(current.get('path') or current.get('path_key') or '')
        selected = current_path if current_path in paths else next(iter(paths), '')
        local = by_path.get(selected) or {}
        key = str(local.get('path_key') or '')
        items.append({'path_key': key or 'missing:movie:' + identity,
                      'title': str(part.get('title') or part.get('name') or 'Movie'),
                      'section': str(part.get('year') or str(part.get('release_date') or '')[:4]),
                      'available': bool(key),
                      'reason': '' if key else 'Movie is not available locally'})
    return {'title': collection.get('name') or 'Collection', 'items': items}


class PlayerQueue:
    def __init__(self, provider):
        self.provider = provider

    def snapshot(self, media):
        single = {'title': str(media.get('title') or 'Playlist')[:512], 'current_index': 0,
                  'items': [{'path_key': media['path_key'], 'title': str(media.get('title') or 'File')[:512],
                             'section': '', 'available': True, 'reason': ''}], 'error': ''}
        try:
            raw = self.provider(media) or {}
            rows = raw.get('items') or []
            if not rows:
                return single
            if len(rows) > 2000:
                raise ValueError('Playlist is too large to display safely')
            items, seen = [], set()
            for row in rows:
                key = str(row.get('path_key') or '')
                if not key or len(key) > 4096 or key in seen:
                    continue
                seen.add(key)
                items.append({'path_key': key, 'title': str(row.get('title') or 'File')[:512],
                              'section': str(row.get('section') or '')[:128],
                              'available': bool(row.get('available')),
                              'reason': str(row.get('reason') or '')[:512]})
            current = next((i for i, row in enumerate(items) if row['path_key'] == media['path_key']), None)
            if current is None:
                raise LookupError('Current file is not in the playlist')
            result = {'title': str(raw.get('title') or single['title'])[:512],
                      'items': items, 'current_index': current, 'error': str(raw.get('error') or '')[:1024],
                      'autoplay_blocked_reason': str(raw.get('autoplay_blocked_reason') or '')[:512]}
            # Reserve space for the media envelope and preferences in the 256 KiB protocol.
            if len(json.dumps(result, ensure_ascii=False).encode('utf-8')) > 180 * 1024:
                raise ValueError('Playlist is too large to display safely')
            return result
        except (LookupError, ValueError, TypeError, OSError, RuntimeError, sqlite3.Error):
            single['error'] = 'Playlist unavailable or too large. Reopen the file to retry.'
            return single
