"""TV adapters for the existing PlayerManager and progress event policy."""
import re
from pathlib import Path

from services.player_catalog import PlayerMediaError
from services.playback_history import PlaybackHistoryService


def parse_tv_key(key):
    match = re.fullmatch(r'tv:episode:(\d+):file:(\d+)', str(key))
    if not match:
        raise PlayerMediaError('Invalid TV playback identity')
    return tuple(map(int, match.groups()))


class TVPlayback:
    def __init__(self, repository, roots):
        self.repository, self.roots = repository, roots

    def target(self, episode_id, file_id=None):
        episode = self.repository.episode(episode_id)
        row = next(item for item in self.repository.episodes(episode['series_id'], episode['season_number']) if item['id'] == episode_id)
        return self._target_from_row(row, file_id)

    @staticmethod
    def _target_from_row(row, file_id=None):
        if not row['released'] or row['reconciliation_required']:
            raise PlayerMediaError('Episode is unreleased or needs metadata reconciliation')
        versions = [v for v in row['versions'] if v['available'] and (file_id is None or v['file_id'] == int(file_id))]
        if not versions:
            raise PlayerMediaError('Episode file is missing')
        selected = next((v for v in versions if v['file_id'] == row['selected_file_id']), versions[0])
        return f"tv:episode:{row['id']}:file:{selected['file_id']}"

    def queue(self, media):
        episode = self.repository.episode(media['episode_id'])
        series = self.repository.series(episode['series_id'])
        rows = sorted(self.repository.episodes(episode['series_id']),
                      key=lambda row: (row['season_number'], row['episode_number']))
        items = []
        for row in rows:
            if (row['season_number'] == 0) != (episode['season_number'] == 0):
                continue
            reason = ('Episode numbering needs review' if row['reconciliation_required'] else
                      'Episode has not aired' if not row['released'] else '')
            try:
                key = self._target_from_row(row) if not reason else ''
                if row['id'] == episode['id']:
                    key = media['path_key']
            except PlayerMediaError:
                key = ''
            if not key and not reason:
                reason = 'Episode is missing locally'
            items.append({'path_key': key or f"missing:tv:{row['id']}",
                          'title': f"S{row['season_number']:02d}E{row['episode_number']:02d} · {row['title']}",
                          'section': 'Specials' if row['season_number'] == 0 else f"Season {row['season_number']}",
                          'available': bool(key) and not reason, 'reason': reason})
        return {'title': series['title'], 'items': items}

    def resolve(self, key):
        episode_id, file_id = parse_tv_key(key)
        self.target(episode_id, file_id)
        with self.repository.store.connection() as db:
            row = db.execute('SELECT f.*,b.segment_start_ms,b.segment_end_ms FROM media_files f JOIN episode_file_bindings b ON b.file_id=f.id WHERE b.episode_id=? AND f.id=?', (episode_id, file_id)).fetchone()
            count = db.execute('SELECT COUNT(*) FROM episode_file_bindings WHERE file_id=?', (file_id,)).fetchone()[0]
        path = Path(row['path']).resolve()
        if not any(Path(root).resolve() in path.parents for root in self.roots()):
            raise PlayerMediaError('Episode file is outside configured TV roots')
        if not path.is_file():
            raise PlayerMediaError('Episode file is missing')
        episode = self.repository.episode(episode_id)
        series = self.repository.series(episode['series_id'])
        return {'media_type': 'tv', 'path_key': key, 'path': str(path), 'filename': path.name,
                'title': f"{series['title']} · S{episode['season_number']:02d}E{episode['episode_number']:02d} · {episode['title']}",
                'file_size': row['size'], 'movie_key': '', 'tmdb_id': '', 'imdb_id': '',
                'poster_reference': series.get('poster_url', ''), 'year': '',
                'episode_id': episode_id, 'file_id': file_id, 'shared_without_segments': count > 1}


class TVHistoryStore:
    def __init__(self, repository):
        self.repository = repository

    def _row(self, episode_id):
        with self.repository.store.connection() as db:
            row = db.execute('SELECT * FROM playback_progress WHERE episode_id=?', (episode_id,)).fetchone()
        return {**dict(row), 'completed_at': row['last_played'] if row['completed'] else None} if row else {'position_ms': 0, 'duration_ms': 0, 'revision': 0, 'completed_at': None}

    def begin_session(self, key, _movie_key=None, restart=False):
        episode_id, file_id = parse_tv_key(key)
        old = self._row(episode_id)
        switched = old.get('file_id') is not None and old.get('file_id') != file_id
        self.repository.save_progress(episode_id, file_id, position_ms=0 if switched else old['position_ms'], duration_ms=0 if switched else old['duration_ms'], completed=old['completed_at'] is not None and not switched, restart=restart or switched, player_activity=True)
        return self._row(episode_id)

    def restart_session(self, key, revision):
        episode_id, file_id = parse_tv_key(key)
        # Keep the current session revision; only a newly opened rewatch invalidates old sessions.
        return self.repository.save_progress(episode_id, file_id, expected_revision=revision)

    def save(self, key, revision, *, position_ms, duration_ms, completion_threshold, force_complete=False, **_preferences):
        episode_id, file_id = parse_tv_key(key)
        with self.repository.store.connection() as db:
            shared = db.execute('SELECT COUNT(*) FROM episode_file_bindings WHERE file_id=?', (file_id,)).fetchone()[0] > 1
        completed = not shared and (force_complete or (duration_ms > 0 and position_ms / duration_ms >= completion_threshold))
        result = self.repository.save_progress(episode_id, file_id, position_ms=min(position_ms, duration_ms) if duration_ms else position_ms, duration_ms=duration_ms, completed=completed, expected_revision=revision)
        return {**result, 'row': self._row(episode_id)}


class TVPlaybackHistory(PlaybackHistoryService):
    def __init__(self, repository, config):
        super().__init__(TVHistoryStore(repository), config, lambda: None)

    def _mark_completed(self, media):
        # TVHistoryStore has already persisted episode completion; never write movie curation.
        return None


class TypedPlaybackHistory:
    def __init__(self, movies, tv_provider):
        self.movies, self.tv_provider = movies, tv_provider

    def begin_session(self, media, **options):
        owner = self.tv_provider() if media.get('media_type') == 'tv' else self.movies
        return owner.begin_session(media, **options)

    def handle_event(self, session, message):
        media = (getattr(session, 'playback_context', None) or {}).get('media', {})
        owner = self.tv_provider() if media.get('media_type') == 'tv' else self.movies
        return owner.handle_event(session, message)

    def flush_session(self, session):
        media = (getattr(session, 'playback_context', None) or {}).get('media', {})
        owner = self.tv_provider() if media.get('media_type') == 'tv' else self.movies
        return owner.flush_session(session)
