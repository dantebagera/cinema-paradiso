"""Independent native-TV database. No movie/IPTV imports or attached stores."""
from contextlib import closing, contextmanager
import os
from pathlib import Path
import sqlite3
import tempfile
import threading


TV_SCHEMA_VERSION = 2
SCHEMA = """
CREATE TABLE IF NOT EXISTS tv_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS series(
 id INTEGER PRIMARY KEY, tmdb_id INTEGER NOT NULL UNIQUE CHECK(tmdb_id>0),
 title TEXT NOT NULL, metadata TEXT NOT NULL DEFAULT '{}', updated_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS series_curation(
 series_id INTEGER PRIMARY KEY REFERENCES series(id), watchlisted INTEGER NOT NULL DEFAULT 0 CHECK(watchlisted IN (0,1)));
CREATE TABLE IF NOT EXISTS series_external_ids(
 series_id INTEGER NOT NULL REFERENCES series(id), provider TEXT NOT NULL,
 value TEXT NOT NULL, UNIQUE(provider,value), PRIMARY KEY(series_id,provider));
CREATE TABLE IF NOT EXISTS seasons(
 series_id INTEGER NOT NULL REFERENCES series(id), number INTEGER NOT NULL CHECK(number>=0),
 metadata TEXT NOT NULL DEFAULT '{}', PRIMARY KEY(series_id,number));
CREATE TABLE IF NOT EXISTS episodes(
 id INTEGER PRIMARY KEY, series_id INTEGER NOT NULL REFERENCES series(id),
 season_number INTEGER NOT NULL CHECK(season_number>=0), episode_number INTEGER NOT NULL CHECK(episode_number>0),
 provider_id TEXT, title TEXT NOT NULL, air_date TEXT, runtime INTEGER,
 metadata TEXT NOT NULL DEFAULT '{}', reconciliation_required INTEGER NOT NULL DEFAULT 0,
 UNIQUE(series_id,season_number,episode_number), UNIQUE(series_id,provider_id),
 FOREIGN KEY(series_id,season_number) REFERENCES seasons(series_id,number));
CREATE TABLE IF NOT EXISTS people(id INTEGER PRIMARY KEY, tmdb_id INTEGER NOT NULL UNIQUE, name TEXT NOT NULL, metadata TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS series_credits(series_id INTEGER REFERENCES series(id), person_id INTEGER REFERENCES people(id), role TEXT NOT NULL, PRIMARY KEY(series_id,person_id,role));
CREATE TABLE IF NOT EXISTS episode_credits(episode_id INTEGER REFERENCES episodes(id), person_id INTEGER REFERENCES people(id), role TEXT NOT NULL, PRIMARY KEY(episode_id,person_id,role));
CREATE TABLE IF NOT EXISTS media_files(
 id INTEGER PRIMARY KEY, path TEXT NOT NULL UNIQUE, size INTEGER NOT NULL CHECK(size>=0),
 modified_ns INTEGER NOT NULL, facts TEXT NOT NULL, available INTEGER NOT NULL DEFAULT 1, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS episode_file_bindings(
 episode_id INTEGER NOT NULL REFERENCES episodes(id), file_id INTEGER NOT NULL REFERENCES media_files(id),
 segment_start_ms INTEGER, segment_end_ms INTEGER, PRIMARY KEY(episode_id,file_id));
CREATE TABLE IF NOT EXISTS playback_progress(
 episode_id INTEGER PRIMARY KEY REFERENCES episodes(id), file_id INTEGER REFERENCES media_files(id),
 position_ms INTEGER NOT NULL DEFAULT 0 CHECK(position_ms>=0), duration_ms INTEGER NOT NULL DEFAULT 0 CHECK(duration_ms>=0),
 completed INTEGER NOT NULL DEFAULT 0, revision INTEGER NOT NULL DEFAULT 0,
 last_played REAL NOT NULL, hidden INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS watch_events(id INTEGER PRIMARY KEY, episode_id INTEGER REFERENCES episodes(id), event TEXT NOT NULL, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS ingestion_candidates(
 id INTEGER PRIMARY KEY, fingerprint TEXT NOT NULL UNIQUE, payload TEXT NOT NULL, state TEXT NOT NULL, reason TEXT NOT NULL, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS metadata_events(id INTEGER PRIMARY KEY, series_id INTEGER REFERENCES series(id), event TEXT NOT NULL, payload TEXT NOT NULL, created_at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS tv_episode_series ON episodes(series_id,season_number,episode_number);
CREATE INDEX IF NOT EXISTS tv_binding_file ON episode_file_bindings(file_id);
"""


def guarded_path(path):
    path = Path(path).resolve()
    if os.environ.get('CP_TEST_MODE') == '1':
        declared = Path(os.environ['CP_TEST_ROOT']).resolve()
        temporary = Path(tempfile.gettempdir()).resolve()
        if temporary not in declared.parents or temporary not in path.parents:
            raise ValueError('TV test storage must remain in OS-temporary storage')
    return path


class TVCatalogStore:
    def __init__(self, path):
        self.path = guarded_path(path)
        self._lock = threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as connection:
            version = connection.execute('PRAGMA user_version').fetchone()[0]
            if version > TV_SCHEMA_VERSION:
                raise ValueError('TV database is newer than this application')
            connection.executescript('BEGIN IMMEDIATE;\n' + SCHEMA +
                                     f'\nPRAGMA user_version={TV_SCHEMA_VERSION};\nCOMMIT;')

    @contextmanager
    def connection(self):
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('PRAGMA journal_mode=WAL')
        connection.execute('PRAGMA synchronous=FULL')
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def transaction(self):
        with self._lock, self.connection() as connection:
            connection.execute('BEGIN IMMEDIATE')
            try:
                yield connection
                connection.commit()
            except BaseException:
                connection.rollback()
                raise

    def audit(self):
        with self.connection() as connection:
            counts = {
                'episodes': connection.execute('SELECT COUNT(*) FROM episodes e LEFT JOIN series s ON s.id=e.series_id LEFT JOIN seasons z ON z.series_id=e.series_id AND z.number=e.season_number WHERE s.id IS NULL OR z.series_id IS NULL').fetchone()[0],
                'files': connection.execute('SELECT COUNT(*) FROM media_files f LEFT JOIN episode_file_bindings b ON b.file_id=f.id WHERE b.file_id IS NULL').fetchone()[0],
                'bindings': connection.execute('SELECT COUNT(*) FROM episode_file_bindings b LEFT JOIN episodes e ON e.id=b.episode_id LEFT JOIN media_files f ON f.id=b.file_id WHERE e.id IS NULL OR f.id IS NULL').fetchone()[0],
                'identities': connection.execute('SELECT COUNT(*) FROM series_external_ids x LEFT JOIN series s ON s.id=x.series_id WHERE s.id IS NULL').fetchone()[0],
                'progress': connection.execute('SELECT COUNT(*) FROM playback_progress p LEFT JOIN episodes e ON e.id=p.episode_id LEFT JOIN media_files f ON f.id=p.file_id WHERE e.id IS NULL OR (p.file_id IS NOT NULL AND f.id IS NULL)').fetchone()[0],
            }
            return {'integrity': connection.execute('PRAGMA integrity_check').fetchone()[0],
                    'foreign_keys': [tuple(row) for row in connection.execute('PRAGMA foreign_key_check')],
                    'schema_version': connection.execute('PRAGMA user_version').fetchone()[0],
                    'orphans': counts}

    def backup(self, destination):
        destination = guarded_path(destination)
        if destination == self.path:
            raise ValueError('Backup must have a separate path')
        destination.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, self.connection() as source, closing(sqlite3.connect(destination)) as target:
            source.backup(target)
        return str(destination)

    def restore(self, source):
        source = guarded_path(source)
        if source == self.path or not source.is_file():
            raise ValueError('A separate existing backup is required')
        with self._lock, closing(sqlite3.connect(f'{source.as_uri()}?mode=ro', uri=True)) as backup:
            if backup.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('Backup integrity failed')
            if backup.execute('PRAGMA user_version').fetchone()[0] not in {1, TV_SCHEMA_VERSION}:
                raise ValueError('Backup schema mismatch')
            if backup.execute('PRAGMA foreign_key_check').fetchall():
                raise ValueError('Backup relationships are invalid')
            if not backup.execute("SELECT 1 FROM sqlite_master WHERE name='tv_meta'").fetchone():
                raise ValueError('Not a TV backup')
            with self.connection() as destination:
                backup.backup(destination)
                destination.executescript('BEGIN IMMEDIATE;\n' + SCHEMA +
                                          f'\nPRAGMA user_version={TV_SCHEMA_VERSION};\nCOMMIT;')
