"""Identify local TV series from folder, filename, year, and TMDB evidence."""
from collections import Counter
from pathlib import Path
import re
import threading
import time

from services.tv_filename_parser import title_key


def title_hint(value):
    text = str(value or '').strip()
    text = re.sub(r'^\[[^\]]+\]\s*', '', text)
    sections = re.split(r'\s+-\s+', text, maxsplit=1)
    if len(sections) == 2:
        text = sections[1] if '.com' in sections[0].casefold() else sections[0]
    text = text.replace('.', ' ').replace('_', ' ').replace('-', ' ')
    text = re.split(r'(?i)\b(?:season\s*\d+|se\d{1,3}|s\d{1,3}|complete|1080p|720p|2160p|bdrip|webrip|dvdrip|hdtv|x264|x265)\b|(?<!\d)(?:19|20)\d{2}(?!\d)|[\[\(\{]', text, maxsplit=1)[0]
    return re.sub(r'\s+', ' ', text).strip(' -._!')


def year_hint(value):
    match = re.search(r'(?<!\d)((?:19|20)\d{2})(?!\d)', str(value or ''))
    return match[1] if match else ''


def dominant_filename_title(files):
    claims = [item['claim'] for item in files if item['claim']['scope'] == 'episode' and item['claim']['series_title']]
    keyed = Counter(title_key(title_hint(claim['series_title'])) for claim in claims)
    if not keyed:
        return ''
    winner, count = keyed.most_common(1)[0]
    if not winner or count < 2 or count * 2 < len(claims):
        return ''
    return next(title_hint(claim['series_title']) for claim in claims if title_key(title_hint(claim['series_title'])) == winner)


def candidate_units(inventory):
    units = []
    for group in inventory['groups']:
        parent = Path(group['folder'])
        parent_title = title_hint(parent.name)
        files = list(group['files'])
        separated = set()
        for child in group.get('subfolders', []):
            child_path = Path(child['path'])
            child_files = [item for item in files if child_path in Path(item['path']).parents]
            if len(child_files) < 2:
                continue
            child_title = title_hint(child_path.name)
            prefix = dominant_filename_title(child_files)
            is_extra = bool(re.search(r'(?i)\b(?:movie|film|extras?|featurettes?|samples?|bonus)\b', child_path.name))
            distinct_prefix = prefix and title_key(prefix) != title_key(parent_title)
            collection_child = 'collection' in parent.name.casefold() and child_title and title_key(child_title) != title_key(parent_title)
            if not is_extra and (distinct_prefix or collection_child):
                separated.add(str(child_path))
                units.append({'path': str(child_path), 'files': child_files})
        remaining = [item for item in files if not any(Path(path) in Path(item['path']).parents for path in separated)]
        if remaining:
            units.append({'path': str(parent), 'files': remaining})
    return units


class TVLibraryDiscovery:
    def __init__(self, ingestion, metadata, repository, clock=time.time):
        self.ingestion, self.metadata, self.repository, self.clock = ingestion, metadata, repository, clock
        self._lock = threading.RLock()
        self._run_lock = threading.Lock()
        saved = repository.discovery_items()
        self._state = {'status': 'pending', 'items': saved, 'identified': 0,
                       'review': sum(row['state'] == 'review' for row in saved),
                       'skipped': sum(row['state'] == 'excluded' for row in saved), 'updated_at': None}

    def snapshot(self):
        with self._lock:
            return {**self._state, 'items': list(self._state['items'])}

    def _match(self, unit):
        path, files = Path(unit['path']), unit['files']
        count = len(files)
        folder = title_hint(path.name)
        filename = dominant_filename_title(files)
        if path.name.isdigit() and not filename:
            filename = next((title_hint(item['claim']['series_title']) for item in files
                             if item['claim']['scope'] == 'episode' and item['claim']['series_title']), '')
        query = filename if (not folder or folder.isdigit() or (filename and len(title_key(filename)) >= 5
                        and title_key(filename) in title_key(folder))) else folder
        year = year_hint(path.name) or year_hint(filename)
        numbered = sum(item['claim']['scope'] in {'episode', 'daily'} and not item['claim']['ignored'] for item in files)
        result = {'path': str(path), 'title_hint': query, 'year_hint': year, 'files': count,
                  'numbered': numbered, 'state': 'review', 'reason': '', 'candidates': [],
                  'sample_filenames': [item['name'] for item in files[:5]]}
        if not query or len(title_key(query)) < 3 or (numbered == 0 and re.search(r'(?i)\b(?:movie|film|extras?|featurettes?|samples?|short movies)\b', query)):
            return {**result, 'state': 'review', 'reason': 'Folder does not provide a reliable TV series title; review or exclude it'}
        try:
            if path.name.isdigit():
                raw = self.metadata.request(f'/tv/{int(path.name)}', _timeout=8, _attempts=1)
                rows = [raw] if raw.get('id') == int(path.name) else []
            else:
                rows = self.metadata.request('/search/tv', query=query, _timeout=8, _attempts=1).get('results', [])
        except (OSError, ValueError, KeyError, TimeoutError) as error:
            return {**result, 'state': 'scan_error', 'reason': f'TMDB lookup unavailable: {type(error).__name__}'}
        choices = []
        for row in rows:
            name = str(row.get('name') or '')
            original = str(row.get('original_name') or '')
            names = [title_key(name), title_key(original)]
            key = title_key(query)
            exact = key in names
            contained = len(key) >= 8 and any(key in candidate for candidate in names)
            if not (exact or contained):
                continue
            first_year = str(row.get('first_air_date') or '')[:4]
            choices.append({'tmdb_id': int(row['id']), 'title': name, 'year': first_year,
                            'match': 'exact' if exact else 'contained'})
        result['candidates'] = choices[:10]
        eligible = [row for row in choices if not year or row['year'] == year]
        exact = [row for row in eligible if row['match'] == 'exact']
        best = exact if exact else eligible
        if len(best) == 1 and (best[0]['match'] == 'exact' or count >= 3) and (numbered >= 1 or year or count >= 3):
            return {**result, 'state': 'identified', 'tmdb_id': best[0]['tmdb_id'],
                    'title': best[0]['title'], 'reason': 'Unique TMDB TV title with matching available year and episode evidence'}
        return {**result, 'reason': 'Several identities fit, the year conflicts, or episode evidence is insufficient'}

    def run(self):
        if not self._run_lock.acquire(blocking=False):
            return self.snapshot()
        try:
            with self._lock:
                self._state = {**self._state, 'status': 'running', 'items': [], 'identified': 0,
                               'review': 0, 'skipped': 0, 'updated_at': self.clock()}
            inventory = self.ingestion.inventory()
            assignments = {row['path']: row for row in inventory['assignments']}
            exclusions = {row['path']: row for row in self.repository.exclusions()}
            units = [unit for unit in candidate_units(inventory) if unit['path'] not in assignments
                     and unit['path'] not in exclusions]
            # Specific child paths win over their containing folder during file scans.
            units.sort(key=lambda unit: len(Path(unit['path']).parts), reverse=True)
            items = []
            for unit in units:
                item = self._match(unit)
                if item['state'] == 'identified':
                    try:
                        series_id = self.metadata.refresh(item['tmdb_id'])
                        self.ingestion.approve(unit['path'], 'folder', series_id)
                        item['series_id'] = series_id
                    except (OSError, ValueError, KeyError, TimeoutError, TypeError) as error:
                        item.update(state='review', reason=f'Identity found but metadata import failed: {type(error).__name__}')
                self.repository.save_discovery(item)
                items.append(item)
                with self._lock:
                    self._state = {**self._state, 'items': list(items),
                                   'identified': sum(row['state'] == 'identified' for row in items),
                                   'review': sum(row['state'] == 'review' for row in items),
                                   'skipped': sum(row['state'] == 'skipped' for row in items),
                                   'updated_at': self.clock()}
            self.repository.retire_discovery({unit['path'] for unit in units} | set(exclusions))
            with self._lock:
                self._state = {**self._state, 'status': 'complete', 'updated_at': self.clock()}
            return self.snapshot()
        except Exception:
            with self._lock:
                self._state = {**self._state, 'status': 'failed', 'updated_at': self.clock()}
            raise
        finally:
            self._run_lock.release()
