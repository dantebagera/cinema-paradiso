from dataclasses import asdict, is_dataclass
from pathlib import Path
import os
import re

from services.media_file_facts import probe_media_file
from services.tv_catalog_store import guarded_path
from services.tv_filename_parser import VIDEO_EXTENSIONS, parse_episode_name, resolve_episode_claim, series_identity, title_key


class TVIngestion:
    def __init__(self, repository, roots, probe=probe_media_file):
        self.repository, self.roots, self.probe = repository, roots, probe

    def _season_hint(self, path, roots):
        directories = next((path.relative_to(root).parts[:-1] for root in roots if root in path.parents), ())
        seasons = set()
        for directory in directories:
            if re.search(r'(?i)(?:^|[^a-z0-9])(?:season|se|s)[ ._-]*\d{1,3}\s*[-–]\s*\d{1,3}', directory):
                return None
            seasons.update(int(value) for value in re.findall(r'(?i)(?:^|[^a-z0-9])(?:season|se|s)[ ._-]*(\d{1,3})(?!\d)', directory))
        return next(iter(seasons)) if len(seasons) == 1 else None

    def ingest(self, series_id, path, *, provider_episode_id=None, verify_title=False, identity_folder=None):
        series = self.repository.series(series_id)
        path = guarded_path(path)
        roots = [guarded_path(root) for root in self.roots()]
        if not path.is_file() or not any(root in path.parents for root in roots):
            raise ValueError('File must be within a configured TV root')
        if path.suffix.lower() not in VIDEO_EXTENSIONS:
            return {'state': 'ignored', 'reason': 'Not a supported video file'}
        claim = parse_episode_name(path.name)
        result = resolve_episode_claim(claim, self.repository.episodes(series_id), provider_episode_id=provider_episode_id, season_hint=self._season_hint(path, roots))
        if verify_title and not provider_episode_id and not claim['ignored'] and claim['series_title']:
            identity = series_identity({'title': claim['series_title'], 'folder_title': Path(identity_folder).name if identity_folder else ''}, series)
            if identity['state'] != 'matched':
                result = {'state': 'needs_review', 'episode_ids': [], 'reason': 'Filename series title or year conflicts with the approved series'}
        if result['state'] == 'accepted':
            before = path.stat()
            facts = self.probe(str(path))
            facts = asdict(facts) if is_dataclass(facts) else dict(facts)
            after = path.stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or facts.get('probe_status') != 'ok':
                result = {'state': 'needs_review', 'reason': 'File changed or measured media facts are unavailable'}
            else:
                result['file_id'] = self.repository.bind_file(path, result['episode_ids'], facts, roots)
                self.repository.close_reviews(series_id, path, state='applied')
        if result['state'] == 'needs_review':
            result['review_id'] = self.repository.review({'series_id': series_id, 'path': str(path), 'claim': claim}, result['reason'])
        return result

    def _roots(self):
        return [guarded_path(root) for root in self.roots()]

    def inventory(self, *, limit=10000):
        """Read-only inventory. Each file remains visible, including mixed and unknown names."""
        limit = min(20000, max(1, int(limit)))
        assignments = self.repository.path_assignments()
        groups, total = [], 0
        for root in self._roots():
            if not root.is_dir():
                continue
            by_folder = {}
            for directory, dirs, names in os.walk(root, followlinks=False):
                dirs[:] = [name for name in dirs if not (Path(directory) / name).is_symlink()]
                for name in names:
                    if Path(name).suffix.lower() not in VIDEO_EXTENSIONS:
                        continue
                    path = guarded_path(Path(directory) / name)
                    if root not in path.parents or not path.is_file():
                        continue
                    total += 1
                    if total > limit:
                        raise ValueError('TV inventory exceeds its file bound; select a smaller root')
                    folder = root if path.parent == root else root / path.relative_to(root).parts[0]
                    group = by_folder.setdefault(str(folder), {'root': str(root), 'folder': str(folder), 'files': [], 'subfolders': {}})
                    claim = parse_episode_name(name)
                    group['files'].append({'path': str(path), 'name': name, 'claim': claim})
                    relative = path.relative_to(folder)
                    if len(relative.parts) > 1:
                        child = str(folder / relative.parts[0])
                        group['subfolders'][child] = group['subfolders'].get(child, 0) + 1
            for group in by_folder.values():
                group['files'].sort(key=lambda item: item['path'].casefold())
                group['count'] = len(group['files'])
                group['subfolders'] = [{'path': path, 'count': count} for path, count in sorted(group['subfolders'].items())]
                groups.append(group)
        groups.sort(key=lambda item: item['folder'].casefold())
        return {'groups': groups, 'total': total, 'assignments': assignments}

    def approve(self, path, kind, series_id):
        path = guarded_path(path)
        if kind not in {'folder', 'file'} or not any(path == root or root in path.parents for root in self._roots()):
            raise ValueError('Assignment must be an existing folder or file inside a TV root')
        if kind == 'file' and path.suffix.lower() not in VIDEO_EXTENSIONS:
            raise ValueError('A file assignment needs a supported video')
        return self.repository.approve_path(path, kind, int(series_id))

    def scan_approved(self, *, limit=10000):
        counts = {'accepted': 0, 'unchanged': 0, 'needs_review': 0, 'ignored': 0, 'unassigned': 0}
        inventory = self.inventory(limit=limit)
        assignments = inventory['assignments']
        exclusions = self.repository.exclusions()
        for group in inventory['groups']:
            for item in group['files']:
                path = Path(item['path'])
                if any((row['kind'] == 'file' and path == Path(row['path'])) or
                       (row['kind'] == 'folder' and Path(row['path']) in path.parents)
                       for row in exclusions):
                    counts['ignored'] += 1
                    continue
                owners = [row for row in assignments if (row['kind'] == 'file' and path == Path(row['path']))
                          or (row['kind'] == 'folder' and (path == Path(row['path']) or Path(row['path']) in path.parents))]
                if not owners:
                    counts['unassigned'] += 1
                    continue
                owner = max(owners, key=lambda row: len(Path(row['path']).parts))
                if owner['kind'] == 'folder':
                    assigned = Path(owner['path'])
                    series = self.repository.series(owner['series_id'])
                    parents = list(path.parent.parents)
                    nested = [directory for directory in [path.parent, *parents] if assigned in directory.parents]
                    if any(re.search(r'(?i)^(?:extras?|featurettes?|samples?|trailers?|movies?|nc(?:op|ed)?|subs|subtitles)(?:$|[ ._(-])', directory.name) for directory in nested):
                        self.repository.exclude_path(path, 'file', 'Extra or non-episode folder under an assigned TV show')
                        self.repository.close_reviews(owner['series_id'], path, state='ignored')
                        counts['ignored'] += 1
                        continue
                    series_key = title_key(series['title'])
                    conflict = next((directory for directory in nested if not re.match(
                        r'(?i)^(?:season[ ._-]*\d+|s\d{1,3}|specials)(?:$|[ ._(-])', directory.name)
                        and not (series_key and title_key(directory.name).startswith(series_key)
                                 and title_key(directory.name)[len(series_key):] in {'complete', 'miniseries'})
                        and series_identity({'title': directory.name}, series)['state'] != 'matched'), None)
                    if conflict:
                        self.repository.review({'series_id': owner['series_id'], 'path': str(path), 'claim': item['claim']},
                                               'Nested folder title conflicts with the approved series; approve this folder or file explicitly')
                        counts['needs_review'] += 1
                        continue
                previous = self.repository.file_binding(path)
                stat = path.stat()
                if previous and previous['series_ids'] == {owner['series_id']} and (previous['size'], previous['modified_ns']) == (stat.st_size, stat.st_mtime_ns):
                    counts['unchanged'] += 1
                    continue
                try:
                    result = self.ingest(owner['series_id'], path, verify_title=owner['kind'] != 'file', identity_folder=owner['path'])
                    counts[result['state']] += 1
                except (ValueError, OSError, TimeoutError) as error:
                    self.repository.review({'series_id': owner['series_id'], 'path': str(path), 'claim': item['claim']},
                                           f'File could not be linked: {error}')
                    counts['needs_review'] += 1
        return {**counts, 'total': inventory['total']}

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
        return [self.ingest(series_id, path, verify_title=True) for path in sorted(paths)]

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
