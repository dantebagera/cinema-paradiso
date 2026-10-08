"""Canonical TV identities, local versions and episode-only progress."""
from datetime import date
from contextlib import nullcontext
import hashlib
import json
import re
from pathlib import Path
import time
import uuid

from services.tv_catalog_store import TVCatalogStore, guarded_path


def encode(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def released(value, today=None):
    try:
        return date.fromisoformat(str(value)[:10]) <= (today or date.today())
    except (TypeError, ValueError):
        return False


class TVCatalogRepository:
    def __init__(self, path, clock=time.time):
        self.store = TVCatalogStore(path)
        self.clock = clock

    def path_assignments(self):
        with self.store.connection() as db:
            return [dict(row) for row in db.execute(
                'SELECT a.path,a.kind,a.series_id,s.tmdb_id,s.title FROM tv_path_assignments a '
                'JOIN series s ON s.id=a.series_id ORDER BY a.path')]

    def _import_path_allowed(self, path, series_id, roots, *, show_home=False):
        path = guarded_path(path)
        roots = [Path(root).resolve() for root in roots if Path(root).is_dir()]
        if not any(root in path.parents for root in roots):
            return False
        for item in self.exclusions():
            excluded = Path(item['path']).resolve()
            # Excluded extras do not disqualify their whole show home. Actual
            # season destinations remain conservative about excluded contents.
            if path == excluded or excluded in path.parents or (not show_home and path in excluded.parents):
                return False
        for item in self.path_assignments():
            assigned = Path(item['path']).resolve()
            if item['series_id'] != int(series_id) and (path == assigned or assigned in path.parents or path in assigned.parents):
                return False
        return True

    def set_import_home(self, series_id, path, roots):
        self.series(series_id)
        path = guarded_path(path)
        if not path.is_dir() or not self._import_path_allowed(path, series_id, roots, show_home=True):
            raise ValueError('Choose an approved TV show folder inside the configured TV roots')
        with self.store.transaction() as db:
            assignment = db.execute("SELECT 1 FROM tv_path_assignments WHERE path=? AND kind='folder' AND series_id=?",
                                    (str(path), int(series_id))).fetchone()
            if not assignment:
                raise ValueError('Choose an approved TV show folder belonging to this series')
            db.execute("INSERT INTO tv_import_homes(series_id,path,origin) VALUES(?,?,'existing') ON CONFLICT(series_id) DO UPDATE SET path=excluded.path,origin='existing'",
                       (int(series_id), str(path)))
        return {'series_id': int(series_id), 'show_home': str(path)}

    def resolve_import_destination(self, series_id, season, roots, *, metadata=None, publication=None):
        result = {'state': 'needs_home', 'show_home': None, 'season': season, 'path': None,
                  'origin': 'existing', 'requires_creation': False,
                  'candidates': [], 'reason': 'Choose an approved TV show folder before downloading'}
        if season is None:
            return result
        if series_id:
            metadata = self.series(series_id)
        season = int(season)
        if season < 0:
            raise ValueError('Choose a valid TV season')
        with self.store.connection() as db:
            preferred = db.execute('SELECT path,origin FROM tv_import_homes WHERE series_id=?', (int(series_id or 0),)).fetchone()
            bindings = [(Path(row['path']).resolve(), row['season_number']) for row in db.execute(
                'SELECT DISTINCT f.path,e.season_number FROM media_files f JOIN episode_file_bindings b ON b.file_id=f.id '
                'JOIN episodes e ON e.id=b.episode_id WHERE e.series_id=?', (int(series_id or 0),))]
        if preferred and preferred['origin'] == 'metadata':
            return self._metadata_destination(result, series_id, season, roots, metadata, home=Path(preferred['path']), bindings=bindings, publication=publication)
        approved = [Path(row['path']).resolve() for row in self.path_assignments()
                    if row['series_id'] == int(series_id or 0) and row['kind'] == 'folder'
                    and Path(row['path']).is_dir() and self._import_path_allowed(row['path'], series_id, roots, show_home=True)]

        def season_number(folder):
            match = re.fullmatch(r'(Season )(\d+)', folder.name, re.IGNORECASE)
            return int(match[2]) if match else 0 if folder.name.casefold() == 'specials' else None

        credible = [home for home in approved if any(path.parent.parent == home and
                    season_number(path.parent) == number for path, number in bindings)]
        result['candidates'] = sorted(str(path) for path in credible)
        if preferred:
            home = Path(preferred[0]).resolve()
            if home not in approved:
                return {**result, 'reason': 'The chosen TV show folder is no longer approved or safe; review its destination'}
        elif len(credible) == 1:
            home = credible[0]
        elif len(credible) > 1:
            return {**result, 'state': 'needs_choice', 'reason': 'Choose between the approved TV show folders'}
        else:
            assignments = [row for row in self.path_assignments() if row['series_id'] == series_id]
            if bindings or assignments:
                return {**result, 'reason': 'Existing flat or unresolved TV collection requires destination review'}
            return self._metadata_destination(result, series_id, season, roots, metadata)
        result['show_home'] = str(home)
        associated = {path.parent for path, number in bindings if number == season and
                      path.parent.parent == home and season_number(path.parent) == season}
        directories = [folder for folder in home.iterdir() if folder.is_dir() and season_number(folder) is not None]
        matching = {folder.resolve() for folder in directories if season_number(folder) == season}
        choices = associated or matching
        if len(choices) == 1:
            destination = next(iter(choices))
        elif choices:
            return {**result, 'state': 'needs_choice', 'reason': 'Multiple season folders require destination review'}
        else:
            # A leading zero proves padding; an unpadded small number proves no padding.
            # Two-digit seasons alone do not contradict a padded convention.
            styles = set()
            prefixes = set()
            for folder in directories:
                match = re.fullmatch(r'(Season )(\d+)', folder.name, re.IGNORECASE)
                if not match or int(match[2]) == 0:
                    continue
                prefixes.add(match[1])
                if match[2].startswith('0'):
                    styles.add(len(match[2]))
                elif len(match[2]) == 1:
                    styles.add(1)
            if season == 0 or len(prefixes) != 1 or len(styles) > 1 or not directories:
                return {**result, 'state': 'needs_choice', 'reason': 'Season folder convention requires destination review'}
            width = next(iter(styles), 1)
            destination = home / f'{next(iter(prefixes))}{season:0{width}d}'
        if not self._import_path_allowed(destination, series_id, roots):
            return {**result, 'reason': 'The season destination is excluded, outside TV roots, or belongs to another series'}
        return {**result, 'state': 'ready', 'season': season, 'path': str(destination), 'requires_creation': not destination.exists(), 'reason': ''}

    @staticmethod
    def _path_key(path):
        return str(Path(path).resolve()).casefold()

    def _metadata_destination(self, result, series_id, season, roots, metadata, *, home=None, bindings=(), publication=None):
        result = {**result, 'origin': 'metadata'}
        def blocked(reason): return {**result, 'reason': reason}
        if season <= 0: return blocked('New TV collections require a regular season; Specials need destination review')
        roots = list(dict.fromkeys(Path(root).resolve() for root in roots))
        if home is None:
            if len(roots) != 1 or not roots[0].is_dir(): return blocked('Choose one existing TV library root before creating a collection')
            title = str((metadata or {}).get('canonical_title') or (metadata or {}).get('title') or '')
            first_air = str((metadata or {}).get('first_air_date') or '')
            try: year = date.fromisoformat(first_air).year
            except ValueError: return blocked('Canonical show title and full first-air date are required for a new TV collection')
            if not title or title != title.strip() or title.endswith('.') or re.search(r'[<>:"/\\|?*\x00-\x1f]', title) or re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', title, re.I):
                return blocked('The canonical show name is unsafe on Windows; destination review is required')
            home = roots[0] / f'{title} ({year:04d})'
        home = home.resolve()
        destination = home / f'Season {season:02d}'
        result.update(show_home=str(home), path=str(destination), requires_creation=not destination.exists())
        if not self._import_path_allowed(home, series_id or 0, roots, show_home=True) or not self._import_path_allowed(destination, series_id or 0, roots):
            return blocked('Destination is excluded, outside TV roots, or belongs to another series')
        owned = any(home in path.parents for path, _ in bindings)
        published_home = (publication or {}).get('tv_created_home') == str(home)
        # A reservation establishes database ownership, never ownership of an externally created directory.
        if home.parent.is_dir():
            collisions = [child for child in home.parent.iterdir() if child.name.casefold() == home.name.casefold()]
            if collisions and (not owned and not published_home or any(child.resolve() != home for child in collisions)):
                return blocked('An unowned or externally created show folder collides with this destination; review required')
        if home.exists() and not home.is_dir(): return blocked('The show destination is not a directory')
        if home.is_dir():
            collisions = [child for child in home.iterdir() if child.name.casefold() == destination.name.casefold()]
            created_seasons = (publication or {}).get('tv_created_seasons', [])
            season_owned = any(path.parent == destination and number == season for path, number in bindings)
            if collisions and (not season_owned and str(destination) not in created_seasons or any(child.resolve() != destination for child in collisions)):
                return blocked('An unowned season folder collides with this destination; review required')
        return {**result, 'state': 'ready', 'reason': ''}

    def reserve_import_home(self, series_id, destination, roots):
        self.series(series_id)
        if destination.get('origin') != 'metadata':
            return self.set_import_home(series_id, destination['show_home'], roots)
        with self.store.transaction() as db:
            current = self.resolve_import_destination(series_id, destination['season'], roots)
            if current['state'] != 'ready' or any(current[key] != destination[key] for key in ('show_home', 'path')):
                raise ValueError(current['reason'] or 'Destination changed; review again')
            home = current['show_home']
            existing = db.execute('SELECT path FROM tv_import_homes WHERE series_id=?', (series_id,)).fetchone()
            if existing and self._path_key(existing['path']) != self._path_key(home):
                raise ValueError('A different show home is already reserved')
            for row in db.execute('SELECT path,series_id FROM tv_path_assignments'):
                if self._path_key(row['path']) == self._path_key(home) and row['series_id'] != series_id:
                    raise ValueError('This show home belongs to another series')
            db.execute("INSERT OR IGNORE INTO tv_path_assignments VALUES(?,'folder',?,?)", (home, series_id, self.clock()))
            db.execute("INSERT OR IGNORE INTO tv_import_homes(series_id,path,origin) VALUES(?,?,'metadata')", (series_id, home))
        return current

    def exclusions(self):
        with self.store.connection() as db:
            return [dict(row) for row in db.execute('SELECT * FROM tv_exclusions ORDER BY path')]

    def exclude_path(self, path, kind, reason):
        path = guarded_path(path)
        if kind not in {'folder', 'file'} or not (path.is_dir() if kind == 'folder' else path.is_file()):
            raise ValueError('Exclude an existing TV folder or video file')
        if not str(reason or '').strip():
            raise ValueError('An exclusion reason is required')
        with self.store.transaction() as db:
            db.execute('INSERT INTO tv_exclusions VALUES(?,?,?,?) ON CONFLICT(path) DO UPDATE SET kind=excluded.kind,reason=excluded.reason',
                       (str(path), kind, str(reason).strip(), self.clock()))
            db.execute("UPDATE tv_discovery_units SET state='excluded' WHERE path=?", (str(path),))
        return {'path': str(path), 'kind': kind, 'state': 'excluded'}

    def remove_exclusion(self, path):
        with self.store.transaction() as db:
            result = db.execute('DELETE FROM tv_exclusions WHERE path=?', (str(path),))
        return {'removed': bool(result.rowcount)}

    def save_discovery(self, item):
        with self.store.transaction() as db:
            db.execute('INSERT INTO tv_discovery_units VALUES(?,?,?,?) '
                       'ON CONFLICT(path) DO UPDATE SET state=excluded.state,payload=excluded.payload,updated_at=excluded.updated_at',
                       (item['path'], item['state'], encode(item), self.clock()))

    def discovery_items(self):
        with self.store.connection() as db:
            return [json.loads(row['payload']) for row in db.execute('SELECT payload FROM tv_discovery_units ORDER BY path')]

    def retire_discovery(self, paths):
        paths = set(paths)
        with self.store.transaction() as db:
            for row in db.execute('SELECT path FROM tv_discovery_units WHERE state NOT IN ("resolved","excluded")'):
                if row['path'] not in paths:
                    db.execute("UPDATE tv_discovery_units SET state='resolved',updated_at=? WHERE path=?", (self.clock(), row['path']))

    def file_binding(self, path):
        with self.store.connection() as db:
            row = db.execute('SELECT id,size,modified_ns FROM media_files WHERE path=?', (str(path),)).fetchone()
            if not row:
                return None
            return {**dict(row), 'series_ids': {item[0] for item in db.execute(
                'SELECT DISTINCT e.series_id FROM episode_file_bindings b '
                'JOIN episodes e ON e.id=b.episode_id WHERE b.file_id=?', (row['id'],))}}

    def binding_episode_ids(self, path):
        with self.store.connection() as db:
            return {row[0] for row in db.execute('SELECT b.episode_id FROM episode_file_bindings b '
                'JOIN media_files f ON f.id=b.file_id WHERE f.path=? AND f.available=1', (str(path),))}

    def approve_path(self, path, kind, series_id):
        path = guarded_path(path)
        if kind not in {'folder', 'file'} or not (path.is_dir() if kind == 'folder' else path.is_file()):
            raise ValueError('Approve an existing TV folder or video file')
        self.series(series_id)
        with self.store.transaction() as db:
            db.execute('INSERT INTO tv_path_assignments(path,kind,series_id,approved_at) VALUES(?,?,?,?) '
                       'ON CONFLICT(path) DO UPDATE SET kind=excluded.kind,series_id=excluded.series_id,approved_at=excluded.approved_at',
                       (str(path), kind, int(series_id), self.clock()))
        return {'path': str(path), 'kind': kind, 'series_id': int(series_id)}

    def refresh(self, metadata, episodes, credits=(), *, season_scope=None):
        tmdb_id = int(metadata['tmdb_id'])
        title = str(metadata.get('title') or '').strip()
        if tmdb_id <= 0 or not title:
            raise ValueError('A typed TMDB TV identity and title are required')
        seen = set()
        for episode in episodes:
            key = (int(episode['season_number']), int(episode['episode_number']))
            if key in seen or key[0] < 0 or key[1] <= 0:
                raise ValueError('Duplicate or invalid episode numbering')
            seen.add(key)
        with self.store.transaction() as db:
            db.execute('INSERT INTO series(tmdb_id,title,metadata,updated_at) VALUES(?,?,?,?) '
                       'ON CONFLICT(tmdb_id) DO UPDATE SET title=excluded.title,metadata=excluded.metadata,updated_at=excluded.updated_at',
                       (tmdb_id, title, encode(metadata), self.clock()))
            series_id = db.execute('SELECT id FROM series WHERE tmdb_id=?', (tmdb_id,)).fetchone()[0]
            db.execute('INSERT OR IGNORE INTO series_external_ids VALUES(?,?,?)', (series_id, 'tmdb:tv', str(tmdb_id)))
            for provider, value in metadata.get('external_ids', {}).items():
                if value:
                    db.execute('INSERT INTO series_external_ids VALUES(?,?,?) ON CONFLICT(series_id,provider) DO UPDATE SET value=excluded.value',
                               (series_id, provider, str(value)))
            for season in metadata.get('seasons', []):
                db.execute('INSERT INTO seasons VALUES(?,?,?) ON CONFLICT(series_id,number) DO UPDATE SET metadata=excluded.metadata',
                           (series_id, int(season['season_number']), encode(season)))
            observed = set()
            for episode in episodes:
                season, number = int(episode['season_number']), int(episode['episode_number'])
                provider_id = str(episode.get('provider_id') or '') or None
                previous = db.execute('SELECT * FROM episodes WHERE series_id=? AND provider_id=?', (series_id, provider_id)).fetchone() if provider_id else None
                occupied = db.execute('SELECT * FROM episodes WHERE series_id=? AND season_number=? AND episode_number=?', (series_id, season, number)).fetchone()
                conflict = (previous and (previous['season_number'], previous['episode_number']) != (season, number)) or (occupied and occupied['provider_id'] and provider_id and occupied['provider_id'] != provider_id)
                if conflict:
                    for row in (previous, occupied):
                        if row:
                            observed.add(row['id'])
                            db.execute('UPDATE episodes SET reconciliation_required=1 WHERE id=?', (row['id'],))
                    db.execute('INSERT INTO metadata_events(series_id,event,payload,created_at) VALUES(?,?,?,?)', (series_id, 'numbering_conflict', encode(episode), self.clock()))
                    continue
                db.execute("INSERT OR IGNORE INTO seasons VALUES(?,?,'{}')", (series_id, season))
                db.execute('INSERT INTO episodes(series_id,season_number,episode_number,provider_id,title,air_date,runtime,metadata) VALUES(?,?,?,?,?,?,?,?) '
                           'ON CONFLICT(series_id,season_number,episode_number) DO UPDATE SET provider_id=COALESCE(excluded.provider_id,episodes.provider_id),title=excluded.title,air_date=excluded.air_date,runtime=excluded.runtime,metadata=excluded.metadata',
                           (series_id, season, number, provider_id, str(episode.get('title') or f'Episode {number}'), episode.get('air_date'), episode.get('runtime'), encode(episode)))
                episode_id = db.execute('SELECT id FROM episodes WHERE series_id=? AND season_number=? AND episode_number=?', (series_id, season, number)).fetchone()[0]
                observed.add(episode_id)
                if 'guest_stars' in episode:
                    db.execute('DELETE FROM episode_credits WHERE episode_id=?', (episode_id,))
                    for person in episode['guest_stars']:
                        db.execute('INSERT INTO people(tmdb_id,name,metadata) VALUES(?,?,?) ON CONFLICT(tmdb_id) DO UPDATE SET name=excluded.name,metadata=excluded.metadata', (int(person['id']), person['name'], encode(person)))
                        person_id = db.execute('SELECT id FROM people WHERE tmdb_id=?', (int(person['id']),)).fetchone()[0]
                        db.execute('INSERT OR IGNORE INTO episode_credits VALUES(?,?,?)', (episode_id, person_id, person.get('character') or 'Guest'))
            for row in db.execute('SELECT id,season_number FROM episodes WHERE series_id=?', (series_id,)):
                if row[0] not in observed and (season_scope is None or row[1] in season_scope):
                    db.execute('UPDATE episodes SET reconciliation_required=1 WHERE id=?', (row[0],))
            db.execute('DELETE FROM series_credits WHERE series_id=?', (series_id,))
            for person in credits:
                db.execute('INSERT INTO people(tmdb_id,name,metadata) VALUES(?,?,?) ON CONFLICT(tmdb_id) DO UPDATE SET name=excluded.name,metadata=excluded.metadata',
                           (int(person['tmdb_id']), str(person['name']), encode(person)))
                person_id = db.execute('SELECT id FROM people WHERE tmdb_id=?', (int(person['tmdb_id']),)).fetchone()[0]
                db.execute('INSERT OR IGNORE INTO series_credits VALUES(?,?,?)', (series_id, person_id, person.get('role', 'Cast')))
            db.execute('INSERT INTO metadata_events(series_id,event,payload,created_at) VALUES(?,?,?,?)', (series_id, 'refresh', encode({'episodes': len(observed)}), self.clock()))
            if season_scope is None:
                regular_seasons = [s for s in metadata.get('seasons', []) if int(s['season_number']) > 0]
                complete = bool(regular_seasons) and all(
                    len([e for e in episodes if int(e['season_number']) == int(season['season_number'])])
                    == int(season.get('episode_count') or 0)
                    for season in regular_seasons
                ) and {int(e['season_number']) for e in episodes if int(e['season_number']) > 0}.issubset(
                    {int(s['season_number']) for s in regular_seasons}
                ) and not db.execute('SELECT 1 FROM episodes WHERE series_id=? AND reconciliation_required=1 LIMIT 1', (series_id,)).fetchone()
                db.execute('INSERT INTO series_hydration(series_id,status,season_count,episode_count,updated_at,error) VALUES(?,?,?,?,?,?) '
                           'ON CONFLICT(series_id) DO UPDATE SET status=excluded.status,season_count=excluded.season_count,episode_count=excluded.episode_count,updated_at=excluded.updated_at,error=excluded.error',
                           (series_id, 'complete' if complete else 'incomplete', len(regular_seasons),
                            sum(int(e['season_number']) > 0 for e in episodes), self.clock(),
                            '' if complete else 'Season counts or episode identities require reconciliation'))
        return series_id

    def hydration(self, series_id):
        with self.store.connection() as db:
            row = db.execute('SELECT * FROM series_hydration WHERE series_id=?', (series_id,)).fetchone()
        return dict(row) if row else {'series_id': series_id, 'status': 'unknown', 'error': 'Complete season metadata has not been loaded'}

    def poster_override(self, series_id):
        with self.store.connection() as db:
            row = db.execute('SELECT image,mime,updated_at FROM series_poster_overrides WHERE series_id=?', (series_id,)).fetchone()
        return dict(row) if row else None

    def save_poster_override(self, series_id, image, mime):
        self.series(series_id)
        if mime not in {'image/jpeg', 'image/png', 'image/webp'} or not image or len(image) > 5_000_000:
            raise ValueError('Choose a JPEG, PNG or WebP image under 5 MB')
        from io import BytesIO
        from PIL import Image
        try:
            with Image.open(BytesIO(image)) as poster:
                poster.verify()
        except (OSError, ValueError) as error:
            raise ValueError('The poster image could not be verified') from error
        with self.store.transaction() as db:
            db.execute('INSERT INTO series_poster_overrides VALUES(?,?,?,?) '
                       'ON CONFLICT(series_id) DO UPDATE SET image=excluded.image,mime=excluded.mime,updated_at=excluded.updated_at',
                       (series_id, image, mime, self.clock()))
        return {'poster_url': f'/api/tv/series/{series_id}/poster?v={int(self.clock())}'}

    def reset_poster_override(self, series_id):
        with self.store.transaction() as db:
            result = db.execute('DELETE FROM series_poster_overrides WHERE series_id=?', (series_id,))
        return {'reset': bool(result.rowcount)}

    def tv_lists(self):
        with self.store.connection() as db:
            return [{**dict(row), 'series_ids': [member[0] for member in db.execute(
                'SELECT series_id FROM tv_custom_list_members WHERE list_id=? ORDER BY added_at', (row['id'],))]}
                for row in db.execute('SELECT * FROM tv_custom_lists ORDER BY lower(name),id')]

    def create_tv_list(self, name):
        name = str(name or '').strip()
        if not name or len(name) > 80:
            raise ValueError('TV list name must have 1 to 80 characters')
        identity = uuid.uuid4().hex
        with self.store.transaction() as db:
            db.execute('INSERT INTO tv_custom_lists VALUES(?,?,?)', (identity, name, self.clock()))
        return {'id': identity, 'name': name, 'series_ids': []}

    def rename_tv_list(self, list_id, name):
        name = str(name or '').strip()
        if not name or len(name) > 80:
            raise ValueError('TV list name must have 1 to 80 characters')
        with self.store.transaction() as db:
            result = db.execute('UPDATE tv_custom_lists SET name=? WHERE id=?', (name, list_id))
            if not result.rowcount:
                raise LookupError('TV list not found')
        return {'id': list_id, 'name': name}

    def delete_tv_list(self, list_id):
        with self.store.transaction() as db:
            result = db.execute('DELETE FROM tv_custom_lists WHERE id=?', (list_id,))
            if not result.rowcount:
                raise LookupError('TV list not found')
        return {'deleted': True}

    def set_tv_list_members(self, list_id, series_ids, present):
        ids = sorted(set(int(value) for value in series_ids))
        if not ids or len(ids) > 100:
            raise ValueError('Select 1 to 100 TV shows')
        with self.store.transaction() as db:
            if not db.execute('SELECT 1 FROM tv_custom_lists WHERE id=?', (list_id,)).fetchone():
                raise LookupError('TV list not found')
            for series_id in ids:
                if not db.execute('SELECT 1 FROM series WHERE id=?', (series_id,)).fetchone():
                    raise LookupError('TV show not found')
            for series_id in ids:
                if present:
                    db.execute('INSERT OR IGNORE INTO tv_custom_list_members VALUES(?,?,?)', (list_id, series_id, self.clock()))
                else:
                    db.execute('DELETE FROM tv_custom_list_members WHERE list_id=? AND series_id=?', (list_id, series_id))
        return {'list_id': list_id, 'series_ids': ids, 'present': bool(present)}

    def record_hydration_failure(self, series_id, error):
        with self.store.transaction() as db:
            db.execute('INSERT INTO series_hydration(series_id,status,updated_at,error) VALUES(?,?,?,?) '
                       'ON CONFLICT(series_id) DO UPDATE SET status=CASE WHEN series_hydration.status="complete" THEN "complete" ELSE "retry" END,updated_at=excluded.updated_at,error=excluded.error',
                       (series_id, 'retry', self.clock(), str(error)[:500]))

    def viewing_cursor(self, series_id):
        with self.store.connection() as db:
            row = db.execute('SELECT episode_id,played_at FROM series_viewing_cursor WHERE series_id=?', (series_id,)).fetchone()
            if row:
                return dict(row)
            # Older player sessions stored a file ID; manual watched edits did not.
            legacy = db.execute('SELECT p.episode_id,p.last_played AS played_at FROM playback_progress p '
                                'JOIN episodes e ON e.id=p.episode_id WHERE e.series_id=? AND p.file_id IS NOT NULL '
                                'ORDER BY p.last_played DESC LIMIT 1', (series_id,)).fetchone()
            return dict(legacy) if legacy else None

    def set_series_watched(self, series_id, watched):
        series = self.series(series_id)
        if str(series.get('status') or '').casefold() != 'ended' or self.hydration(series_id)['status'] != 'complete':
            raise ValueError('A confirmed ended show with complete episode metadata is required')
        with self.store.transaction() as db:
            rows = db.execute('SELECT e.id,p.completed,p.revision FROM episodes e LEFT JOIN playback_progress p ON p.episode_id=e.id '
                              'WHERE e.series_id=? AND e.season_number>0 AND e.reconciliation_required=0', (series_id,)).fetchall()
            if not rows:
                raise ValueError('No regular episodes are known')
            active = db.execute('SELECT action_id FROM series_watched_actions WHERE series_id=?', (series_id,)).fetchone()
            if watched:
                if active:
                    return {'watched': True, 'changed': 0}
                action_id = uuid.uuid4().hex
                db.execute('INSERT INTO series_watched_actions VALUES(?,?,?)', (series_id, action_id, self.clock()))
                changed = 0
                for row in rows:
                    if row['completed']:
                        continue
                    revision = (row['revision'] or 0) + 1
                    db.execute('INSERT INTO playback_progress(episode_id,position_ms,duration_ms,completed,revision,last_played) VALUES(?,?,?,?,?,?) '
                               'ON CONFLICT(episode_id) DO UPDATE SET completed=1,revision=excluded.revision,hidden=0',
                               (row['id'], 0, 0, 1, revision, self.clock()))
                    db.execute('INSERT INTO series_watched_action_marks VALUES(?,?,?)', (series_id, row['id'], revision))
                    db.execute('INSERT INTO watch_events(episode_id,event,created_at) VALUES(?,?,?)', (row['id'], 'completed_by_series_action', self.clock()))
                    changed += 1
            else:
                if not active:
                    return {'watched': False, 'changed': 0}
                marks = db.execute('SELECT episode_id,revision FROM series_watched_action_marks WHERE series_id=?', (series_id,)).fetchall()
                changed = 0
                for mark in marks:
                    result = db.execute('UPDATE playback_progress SET completed=0,revision=revision+1 '
                                        'WHERE episode_id=? AND completed=1 AND revision=?', (mark['episode_id'], mark['revision']))
                    if result.rowcount:
                        db.execute('INSERT INTO watch_events(episode_id,event,created_at) VALUES(?,?,?)', (mark['episode_id'], 'undone_series_action', self.clock()))
                        changed += 1
                db.execute('DELETE FROM series_watched_action_marks WHERE series_id=?', (series_id,))
                db.execute('DELETE FROM series_watched_actions WHERE series_id=?', (series_id,))
        return {'watched': bool(watched), 'changed': changed}

    def series(self, series_id):
        with self.store.connection() as db:
            row = db.execute('SELECT * FROM series WHERE id=?', (series_id,)).fetchone()
            if not row:
                raise LookupError('Series not found')
            result = {**json.loads(row['metadata']), 'id': row['id'], 'tmdb_id': row['tmdb_id'], 'title': row['title']}
            poster = db.execute('SELECT updated_at FROM series_poster_overrides WHERE series_id=?', (series_id,)).fetchone()
            if poster:
                result['provider_poster_url'] = result.get('poster_url', '')
                result['poster_url'] = f'/api/tv/series/{series_id}/poster?v={int(poster[0])}'
                result['poster_override'] = True
            curated = db.execute('SELECT watchlisted FROM series_curation WHERE series_id=?', (series_id,)).fetchone()
            result['watchlisted'] = bool(curated and curated[0])
            result['cast'] = result.get('credits') if 'credits' in result else [dict(p) for p in db.execute('SELECT p.tmdb_id,p.name,c.role FROM people p JOIN series_credits c ON c.person_id=p.id WHERE c.series_id=? ORDER BY p.id LIMIT 30', (series_id,))]
            return result

    def episode(self, episode_id):
        with self.store.connection() as db:
            row = db.execute('SELECT * FROM episodes WHERE id=?', (episode_id,)).fetchone()
            if not row:
                raise LookupError('Episode not found')
            return dict(row)

    def episodes(self, series_id, season=None, *, limit=None, offset=0, today=None):
        query, args = 'SELECT e.*,p.position_ms,p.duration_ms,p.completed,p.last_played,p.file_id AS selected_file_id FROM episodes e LEFT JOIN playback_progress p ON p.episode_id=e.id WHERE e.series_id=?', [series_id]
        if season is not None:
            query += ' AND e.season_number=?'
            args.append(int(season))
        query += ' ORDER BY e.season_number,e.episode_number'
        if limit is not None:
            query += ' LIMIT ? OFFSET ?'
            args += [min(100, max(1, int(limit))), max(0, int(offset))]
        with self.store.connection() as db:
            rows = [dict(r) for r in db.execute(query, args)]
            versions = {}
            credits = {}
            for person in db.execute('SELECT c.episode_id,p.tmdb_id,p.name,c.role FROM people p JOIN episode_credits c ON c.person_id=p.id JOIN episodes e ON e.id=c.episode_id WHERE e.series_id=? ORDER BY p.id', (series_id,)):
                credits.setdefault(person['episode_id'], []).append(dict(person))
            for r in db.execute('SELECT b.*,f.* FROM episode_file_bindings b JOIN media_files f ON f.id=b.file_id JOIN episodes e ON e.id=b.episode_id WHERE e.series_id=?', (series_id,)):
                value = dict(r)
                value['facts'] = json.loads(value['facts'])
                value['available'] = bool(value['available'] and Path(value['path']).is_file())
                versions.setdefault(r['episode_id'], []).append(value)
            for row in rows:
                row['guest_stars'] = credits.get(row['id'], [])[:30]
                row['overview'] = json.loads(row['metadata']).get('overview', '')
                row['versions'] = versions.get(row['id'], [])
                row['available'] = any(v['available'] for v in row['versions'])
                row['released'] = released(row['air_date'], today)
                row['code'] = f"S{row['season_number']:02d}E{row['episode_number']:02d}"
            return rows

    def bind_file(self, path, episode_ids, facts, roots, segments=None, *, _connection=None):
        path = guarded_path(path)
        roots = [guarded_path(root) for root in roots]
        ids = sorted(set(int(value) for value in episode_ids))
        if not ids or not path.is_file() or not any(root in path.parents for root in roots):
            raise ValueError('An existing file inside a configured TV root and episode identities are required')
        stat = path.stat()
        with (nullcontext(_connection) if _connection is not None else self.store.transaction()) as db:
            rows = [db.execute('SELECT * FROM episodes WHERE id=?', (value,)).fetchone() for value in ids]
            if any(not row or row['reconciliation_required'] for row in rows) or len({row['series_id'] for row in rows}) != 1:
                raise ValueError('Bindings require unambiguous episodes from one series')
            old = db.execute('SELECT id FROM media_files WHERE path=?', (str(path),)).fetchone()
            if old:
                existing = {r[0] for r in db.execute('SELECT episode_id FROM episode_file_bindings WHERE file_id=?', (old[0],))}
                if existing != set(ids):
                    raise ValueError('Existing file bindings require manual reconciliation')
            db.execute('INSERT INTO media_files(path,size,modified_ns,facts,created_at) VALUES(?,?,?,?,?) ON CONFLICT(path) DO UPDATE SET size=excluded.size,modified_ns=excluded.modified_ns,facts=excluded.facts,available=1',
                       (str(path), stat.st_size, stat.st_mtime_ns, encode(facts), self.clock()))
            file_id = db.execute('SELECT id FROM media_files WHERE path=?', (str(path),)).fetchone()[0]
            for episode_id in ids:
                segment = (segments or {}).get(episode_id, (None, None))
                db.execute('INSERT OR IGNORE INTO episode_file_bindings VALUES(?,?,?,?)', (episode_id, file_id, *segment))
            return file_id

    def bind_files(self, entries, roots):
        # Publish a verified pack as one catalog transaction; retries remain idempotent.
        with self.store.transaction() as db:
            return [self.bind_file(row['path'], row['episode_ids'], row['facts'], roots, _connection=db) for row in entries]

    def save_progress(self, episode_id, file_id=None, *, position_ms=0, duration_ms=0, completed=False, restart=False, expected_revision=None, player_activity=False):
        position, duration = int(position_ms), int(duration_ms)
        if position < 0 or duration < 0 or (duration and position > duration):
            raise ValueError('Invalid episode progress')
        with self.store.transaction() as db:
            episode = db.execute('SELECT series_id FROM episodes WHERE id=?', (episode_id,)).fetchone()
            if not episode:
                raise LookupError('Episode not found')
            if file_id is not None and not db.execute('SELECT 1 FROM episode_file_bindings WHERE episode_id=? AND file_id=?', (episode_id, file_id)).fetchone():
                raise ValueError('Version does not belong to this episode')
            old = db.execute('SELECT * FROM playback_progress WHERE episode_id=?', (episode_id,)).fetchone()
            revision = old['revision'] if old else 0
            if expected_revision is not None and revision != expected_revision:
                return {'accepted': False, 'revision': revision}
            if old and expected_revision is None and not restart:
                revision += 1
            if restart:
                position, completed, revision = 0, False, revision + 1
            db.execute('INSERT INTO playback_progress(episode_id,file_id,position_ms,duration_ms,completed,revision,last_played) VALUES(?,?,?,?,?,?,?) '
                       'ON CONFLICT(episode_id) DO UPDATE SET file_id=excluded.file_id,position_ms=excluded.position_ms,duration_ms=excluded.duration_ms,completed=excluded.completed,revision=excluded.revision,last_played=excluded.last_played,hidden=0',
                       (episode_id, file_id, position, duration, bool(completed), revision, self.clock()))
            if bool(old['completed'] if old else False) != bool(completed):
                db.execute('INSERT INTO watch_events(episode_id,event,created_at) VALUES(?,?,?)', (episode_id, 'completed' if completed else 'uncompleted', self.clock()))
            if player_activity:
                db.execute('INSERT INTO series_viewing_cursor VALUES(?,?,?) '
                           'ON CONFLICT(series_id) DO UPDATE SET episode_id=excluded.episode_id,played_at=excluded.played_at',
                           (episode['series_id'], episode_id, self.clock()))
            return {'accepted': True, 'revision': revision}

    def review(self, payload, reason):
        fingerprint = hashlib.sha256(encode(payload).encode()).hexdigest()
        with self.store.transaction() as db:
            existing = db.execute("SELECT id FROM ingestion_candidates WHERE state='needs_review' AND json_extract(payload,'$.series_id')=? AND json_extract(payload,'$.path')=? ORDER BY id", (payload['series_id'], payload['path'])).fetchall()
            if existing:
                db.execute('UPDATE ingestion_candidates SET payload=?,reason=? WHERE id=?', (encode(payload), reason, existing[0]['id']))
                db.executemany("UPDATE ingestion_candidates SET state='superseded' WHERE id=?", [(row['id'],) for row in existing[1:]])
                return existing[0]['id']
            db.execute("INSERT INTO ingestion_candidates(fingerprint,payload,state,reason,created_at) VALUES(?,?,?,?,?) ON CONFLICT(fingerprint) DO UPDATE SET state='needs_review',reason=excluded.reason", (fingerprint, encode(payload), 'needs_review', reason, self.clock()))
            return db.execute('SELECT id FROM ingestion_candidates WHERE fingerprint=?', (fingerprint,)).fetchone()[0]

    def close_reviews(self, series_id, path, *, state):
        if state not in {'applied', 'ignored'}:
            raise ValueError('Invalid review state')
        with self.store.transaction() as db:
            rows = db.execute("SELECT id,payload FROM ingestion_candidates WHERE state='needs_review'").fetchall()
            ids = [row['id'] for row in rows if (payload := json.loads(row['payload'])).get('series_id') == series_id and payload.get('path') == str(path)]
            db.executemany('UPDATE ingestion_candidates SET state=? WHERE id=?', [(state, review_id) for review_id in ids])
