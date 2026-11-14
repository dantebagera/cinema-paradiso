"""Optional RT observations. Never creates or joins CP's canonical catalog."""
import json
import sqlite3
import threading
from pathlib import Path
from contextlib import contextmanager


@contextmanager
def _connection(path, **kwargs):
    db = sqlite3.connect(path, timeout=.05, **kwargs)
    try:
        with db:
            yield db
    finally:
        db.close()


class RatingsIdentityConflict(ValueError):
    pass


class MovieRatingsStore:
    def __init__(self, path):
        self.path = Path(path)
        self.epoch = 0
        self._write_lock = threading.RLock()

    def read_many(self, keys):
        keys = list(dict.fromkeys(keys))
        if not keys or not self.path.is_file():
            return {}
        with _connection(self.path.resolve().as_uri() + '?mode=ro', uri=True) as db:
            if db.execute('PRAGMA user_version').fetchone()[0] != 1:
                raise ValueError('unsupported_ratings_schema')
            rows = db.execute('''SELECT a.alias,o.source,o.payload FROM aliases a
                JOIN observations o ON o.key=a.key AND o.source=a.source
                WHERE a.alias IN (SELECT value FROM json_each(?))''', (json.dumps(keys),)).fetchall()
        result = {}
        for alias, source, payload in rows:
            result.setdefault(alias, {})[source] = json.loads(payload)
        return result

    def publish(self, records, expected_epoch=None):
        records = list(records)
        if not records:
            return True
        with self._write_lock:
            if expected_epoch is not None and self.epoch != expected_epoch:
                return False
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with _connection(self.path) as db:
                db.execute('PRAGMA journal_mode=WAL')
                version = db.execute('PRAGMA user_version').fetchone()[0]
                if version not in (0, 1):
                    raise ValueError('unsupported_ratings_schema')
                db.executescript('''CREATE TABLE IF NOT EXISTS observations (
                    key TEXT NOT NULL, source TEXT NOT NULL, sequence REAL NOT NULL, payload TEXT NOT NULL,
                    PRIMARY KEY(key,source));
                    CREATE TABLE IF NOT EXISTS aliases (
                    alias TEXT NOT NULL, source TEXT NOT NULL, key TEXT NOT NULL, PRIMARY KEY(alias,source));
                    PRAGMA user_version=1;''')
                db.execute('BEGIN IMMEDIATE')
                for record in records:
                    key, source = record['key'], record['source']
                    aliases = list(dict.fromkeys([key, *record.get('aliases', [])]))
                    old = db.execute('SELECT sequence,payload FROM observations WHERE key=? AND source=?', (key, source)).fetchone()
                    if old and old[0] > record['sequence']:
                        continue
                    for alias in aliases:
                        conflict = db.execute('SELECT key FROM aliases WHERE alias=? AND source=?', (alias, source)).fetchone()
                        if conflict and conflict[0] != key:
                            raise RatingsIdentityConflict('conflicting_movie_alias')
                    previous = json.loads(old[1]) if old else {}
                    retained = previous.get('aliases', [])
                    prior_identity = previous.get('identity', {})
                    current_identity = record.get('identity', {})
                    for field in ('tmdb_id', 'imdb_id', 'plex_guid'):
                        if prior_identity.get(field) and current_identity.get(field) and prior_identity[field] != current_identity[field]:
                            raise RatingsIdentityConflict('conflicting_movie_identity')
                    saved = {**previous, **record, 'identity': {**prior_identity, **current_identity},
                             'aliases': list(dict.fromkeys([*retained, *aliases]))}
                    if all(record.get(f) is None for f in ('critics', 'audience')) and any(previous.get(f) is not None for f in ('critics', 'audience')):
                        for field in ('critics', 'audience', 'raw', 'retrieved_at', 'expires_at'):
                            if field in previous: saved[field] = previous[field]
                    db.execute('INSERT OR REPLACE INTO observations VALUES(?,?,?,?)',
                               (key, source, record['sequence'], json.dumps(saved, allow_nan=False)))
                    db.executemany('INSERT OR REPLACE INTO aliases VALUES(?,?,?)', [(a, source, key) for a in aliases])
        return True

    def read_state(self):
        return {'schema_version': 1, 'exists': self.path.is_file()}

    def invalidate(self):
        with self._write_lock:
            self.epoch += 1

