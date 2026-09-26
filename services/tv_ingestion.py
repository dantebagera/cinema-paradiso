from dataclasses import asdict, is_dataclass
from pathlib import Path

from services.media_file_facts import probe_media_file
from services.tv_catalog_store import guarded_path
from services.tv_filename_parser import VIDEO_EXTENSIONS, parse_episode_name, resolve_episode_claim


class TVIngestion:
    def __init__(self, repository, roots, probe=probe_media_file):
        self.repository, self.roots, self.probe = repository, roots, probe

    def ingest(self, series_id, path, *, provider_episode_id=None):
        self.repository.series(series_id)
        path = guarded_path(path)
        roots = [guarded_path(root) for root in self.roots()]
        if not path.is_file() or not any(root in path.parents for root in roots):
            raise ValueError('File must be within a configured TV root')
        if path.suffix.lower() not in VIDEO_EXTENSIONS:
            return {'state': 'ignored', 'reason': 'Not a supported video file'}
        claim = parse_episode_name(path.name)
        result = resolve_episode_claim(claim, self.repository.episodes(series_id), provider_episode_id=provider_episode_id)
        if result['state'] == 'accepted':
            before = path.stat()
            facts = self.probe(str(path))
            facts = asdict(facts) if is_dataclass(facts) else dict(facts)
            after = path.stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or facts.get('probe_status') != 'ok':
                result = {'state': 'needs_review', 'reason': 'File changed or measured media facts are unavailable'}
            else:
                result['file_id'] = self.repository.bind_file(path, result['episode_ids'], facts, roots)
        if result['state'] == 'needs_review':
            result['review_id'] = self.repository.review({'series_id': series_id, 'path': str(path), 'claim': claim}, result['reason'])
        return result

    def scan(self, series_id, folder, *, limit=500):
        folder = guarded_path(folder)
        roots = [guarded_path(root) for root in self.roots()]
        if not any(folder == root or root in folder.parents for root in roots):
            raise ValueError('Scan must remain inside a TV root')
        paths = []
        for path in folder.rglob('*'):
            if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS:
                paths.append(path)
                if len(paths) > min(5000, max(1, int(limit))):
                    raise ValueError('Scan exceeds the requested bound; select a season folder')
        return [self.ingest(series_id, path) for path in sorted(paths)]

    def ingest_plex(self, series_id, entries):
        # Caller must select a TV series identity; Plex titles alone never bind.
        results = []
        for item in entries:
            provider_id = item.get('tmdb_episode_id')
            if not provider_id and item.get('season_number') is not None and item.get('episode_number') is not None:
                matches = [row for row in self.repository.episodes(series_id, item['season_number'])
                           if row['episode_number'] == int(item['episode_number'])]
                provider_id = matches[0]['provider_id'] if len(matches) == 1 else None
            results.append(self.ingest(series_id, item['path'], provider_episode_id=provider_id))
        return results

    def apply_review(self, review_id, data):
        import json
        with self.repository.store.connection() as db:
            row = db.execute('SELECT * FROM ingestion_candidates WHERE id=?', (review_id,)).fetchone()
        if not row:
            raise LookupError('Review not found')
        if row['state'] == 'applied':
            return {'state': 'applied'}
        payload = json.loads(row['payload'])
        ids = [int(value) for value in data['episode_ids']]
        if any(self.repository.episode(value)['series_id'] != payload['series_id'] for value in ids):
            raise ValueError('Review cannot bind a different series')
        path = guarded_path(payload['path'])
        facts = self.probe(str(path))
        facts = asdict(facts) if is_dataclass(facts) else dict(facts)
        if facts.get('probe_status') != 'ok':
            raise ValueError('File must have verified playable media facts')
        file_id = self.repository.bind_file(path, ids, facts, self.roots())
        with self.repository.store.transaction() as db:
            db.execute("UPDATE ingestion_candidates SET state='applied' WHERE id=?", (review_id,))
        return {'state': 'applied', 'file_id': file_id}
