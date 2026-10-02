"""Exact selected-show TV file actions; curation and episode history stay in TV catalog."""
import hashlib
import json
from pathlib import Path

from send2trash import send2trash
from services.tv_filename_parser import VIDEO_EXTENSIONS


class TVBulkActions:
    SIDECARS = {'.srt', '.ass', '.ssa', '.vtt', '.jpg', '.jpeg', '.png', '.webp'}
    ACTIVE_TRANSFER_STATES = {'selected', 'submitted', 'downloading', 'validating', 'importing',
                              'import_pending', 'retry_wait', 'needs_review', 'partial_import'}

    def __init__(self, repository, roots, jobs, active_media_path, trash_file=send2trash):
        self.repository, self.roots, self.jobs = repository, roots, jobs
        self.active_media_path, self.trash_file = active_media_path, trash_file

    def _selection(self, series_ids):
        ids = sorted(set(int(value) for value in series_ids))
        if not ids or len(ids) > 100:
            raise ValueError('Select 1 to 100 TV shows')
        for series_id in ids:
            self.repository.series(series_id)
        return ids

    def _inside_root(self, path):
        target = Path(path).resolve()
        return any(Path(root).resolve() in target.parents for root in self.roots())

    def preview_delete(self, series_ids):
        ids = self._selection(series_ids)
        placeholders = ','.join('?' for _ in ids)
        with self.repository.store.connection() as db:
            shows = {row['id']: dict(row) for row in db.execute(
                f'SELECT id,tmdb_id,title FROM series WHERE id IN ({placeholders})', ids)}
            rows = [dict(row) for row in db.execute(
                f'''SELECT DISTINCT f.id,f.path,f.size,f.modified_ns,e.series_id
                    FROM media_files f JOIN episode_file_bindings b ON b.file_id=f.id
                    JOIN episodes e ON e.id=b.episode_id
                    WHERE f.available=1 AND e.series_id IN ({placeholders})''', ids)]
            bound = {row['id']: {item[0] for item in db.execute(
                'SELECT DISTINCT e.series_id FROM episode_file_bindings b JOIN episodes e ON e.id=b.episode_id WHERE b.file_id=?', (row['id'],))}
                for row in rows}
        active_jobs = list(self.jobs().values())
        playing = self.active_media_path()
        result, blockers = {}, {}
        for series_id in ids:
            show = shows[series_id]
            reasons = []
            for job in active_jobs:
                request = job.get('tv_request') or {}
                if job.get('state') in self.ACTIVE_TRANSFER_STATES and (
                    request.get('series_id') == series_id or request.get('tmdb_id') == show['tmdb_id']):
                    reasons.append(f"Active transfer {job.get('expected_info_hash') or job.get('title') or 'unknown'}")
            files = []
            for row in rows:
                if row['series_id'] != series_id:
                    continue
                path = Path(row['path']).resolve()
                if not path.is_file():
                    continue
                if not self._inside_root(path):
                    reasons.append(f'Outside TV root: {path}')
                    continue
                if bound[row['id']] - set(ids):
                    reasons.append(f'Shared with an unselected show: {path}')
                    continue
                if playing and path == Path(playing).resolve():
                    reasons.append(f'Currently playing: {path}')
                    continue
                stat = path.stat()
                files.append({'path': str(path), 'size': stat.st_size, 'modified_ns': stat.st_mtime_ns,
                              'kind': 'video', 'file_id': row['id']})
                same_stem_videos = [candidate for candidate in path.parent.glob(path.stem + '.*')
                                    if candidate.is_file() and candidate.suffix.lower() in VIDEO_EXTENSIONS]
                if len(bound[row['id']]) == 1 and len(same_stem_videos) == 1:
                    for extension in self.SIDECARS:
                        sidecar = path.with_suffix(extension)
                        if sidecar.is_file() and self._inside_root(sidecar):
                            side_stat = sidecar.stat()
                            files.append({'path': str(sidecar), 'size': side_stat.st_size,
                                          'modified_ns': side_stat.st_mtime_ns, 'kind': 'sidecar',
                                          'file_id': row['id']})
            result[series_id] = {'series_id': series_id, 'title': show['title'], 'files': files,
                                 'blocked': bool(reasons), 'reasons': sorted(set(reasons))}
            if reasons:
                blockers[series_id] = result[series_id]['reasons']
        unique = {item['path']: item for show in result.values() for item in show['files']}
        files = sorted(unique.values(), key=lambda item: item['path'].casefold())
        fingerprint = hashlib.sha256(json.dumps({'ids': ids, 'files': files, 'blockers': blockers},
                                                 sort_keys=True).encode()).hexdigest()
        return {'series_ids': ids, 'shows': list(result.values()), 'files': files,
                'blocked': bool(blockers), 'token': fingerprint,
                'video_count': sum(item['kind'] == 'video' for item in files),
                'sidecar_count': sum(item['kind'] == 'sidecar' for item in files)}

    def delete(self, series_ids, token):
        preview = self.preview_delete(series_ids)
        if preview['blocked']:
            raise ValueError('Resolve blocked TV shows before deleting any selected files')
        if token != preview['token']:
            raise ValueError('TV files changed after preview; review the exact paths again')
        removed, failed = [], []
        for item in preview['files']:
            path = Path(item['path'])
            try:
                if not self._inside_root(path) or not path.is_file():
                    raise ValueError('File is missing or outside the TV root')
                stat = path.stat()
                if (stat.st_size, stat.st_mtime_ns) != (item['size'], item['modified_ns']):
                    raise ValueError('File changed since preview')
                if self.active_media_path() and path.resolve() == Path(self.active_media_path()).resolve():
                    raise ValueError('File is playing')
                self.trash_file(str(path))
                removed.append(item)
                if item['kind'] == 'video':
                    with self.repository.store.transaction() as db:
                        db.execute('UPDATE media_files SET available=0 WHERE id=? AND path=?',
                                   (item['file_id'], item['path']))
            except (OSError, ValueError) as error:
                failed.append({'path': item['path'], 'reason': str(error)})
        with self.repository.store.transaction() as db:
            db.execute('INSERT INTO tv_bulk_actions(action,series_ids,paths,outcome,created_at) VALUES(?,?,?,?,?)',
                       ('delete', json.dumps(preview['series_ids']), json.dumps(preview['files']),
                        json.dumps({'removed': removed, 'failed': failed}), self.repository.clock()))
        return {'removed': removed, 'failed': failed, 'series_ids': preview['series_ids']}

    def history(self, page=1, page_size=50):
        page = max(1, int(page)); page_size = min(100, max(1, int(page_size)))
        with self.repository.store.connection() as db:
            rows = [dict(row) for row in db.execute('SELECT * FROM tv_bulk_actions ORDER BY id DESC LIMIT ? OFFSET ?',
                                                     (page_size, (page-1)*page_size))]
        for row in rows:
            for field in ('series_ids', 'paths', 'outcome'):
                row[field] = json.loads(row[field])
        return {'items': rows, 'page': page}
