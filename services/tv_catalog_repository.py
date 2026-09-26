"""Canonical TV identities, local versions and episode-only progress."""
from datetime import date
from contextlib import nullcontext
import hashlib
import json
from pathlib import Path
import time

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
        return series_id

    def series(self, series_id):
        with self.store.connection() as db:
            row = db.execute('SELECT * FROM series WHERE id=?', (series_id,)).fetchone()
            if not row:
                raise LookupError('Series not found')
            result = {**json.loads(row['metadata']), 'id': row['id'], 'tmdb_id': row['tmdb_id'], 'title': row['title']}
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

    def episodes(self, series_id, season=None, *, limit=None, offset=0):
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
                row['released'] = released(row['air_date'])
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

    def save_progress(self, episode_id, file_id=None, *, position_ms=0, duration_ms=0, completed=False, restart=False, expected_revision=None):
        position, duration = int(position_ms), int(duration_ms)
        if position < 0 or duration < 0 or (duration and position > duration):
            raise ValueError('Invalid episode progress')
        with self.store.transaction() as db:
            if not db.execute('SELECT 1 FROM episodes WHERE id=?', (episode_id,)).fetchone():
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
            return {'accepted': True, 'revision': revision}

    def review(self, payload, reason):
        fingerprint = hashlib.sha256(encode(payload).encode()).hexdigest()
        with self.store.transaction() as db:
            db.execute('INSERT OR IGNORE INTO ingestion_candidates(fingerprint,payload,state,reason,created_at) VALUES(?,?,?,?,?)', (fingerprint, encode(payload), 'needs_review', reason, self.clock()))
            return db.execute('SELECT id FROM ingestion_candidates WHERE fingerprint=?', (fingerprint,)).fetchone()[0]
