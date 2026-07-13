import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from services.movie_identity import normalize_movie_title, ownership_keys
from services.smart_match import parse_release_filename


CATALOG_SCHEMA_VERSION = 2


class CatalogError(RuntimeError):
    pass


def _json_text(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _text(value):
    return str(value or "").strip()


def _bool(value):
    return 1 if bool(value) else 0


def _number(value, default=0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _identity_key(movie):
    movie = movie or {}
    if _text(movie.get("tmdb_id")):
        return f"tmdb:{_text(movie.get('tmdb_id'))}"
    if _text(movie.get("imdb_id")):
        return f"imdb:{_text(movie.get('imdb_id')).lower()}"
    if _text(movie.get("plex_guid")):
        return f"plex:{_text(movie.get('plex_guid')).lower()}"
    if _text(movie.get("path")):
        return f"path:{_text(movie.get('path')).lower()}"
    title = normalize_movie_title(movie.get("title"))
    year = _text(movie.get("year"))
    return f"title:{title}|{year}" if title and year else ""


class CatalogStore:
    def __init__(self, database_path):
        self.database_path = Path(database_path).resolve()

    def connect(self):
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = FULL")
        return connection

    @contextmanager
    def transaction(self):
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self):
        with self.transaction() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS catalog_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS source_documents (
                    name TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS media_files (
                    path_key TEXT PRIMARY KEY,
                    path TEXT NOT NULL,
                    filename TEXT NOT NULL DEFAULT '',
                    library_root TEXT NOT NULL DEFAULT '',
                    size INTEGER NOT NULL DEFAULT 0,
                    added_time REAL NOT NULL DEFAULT 0,
                    modified_time REAL NOT NULL DEFAULT 0,
                    resolution TEXT NOT NULL DEFAULT '',
                    rip_source TEXT NOT NULL DEFAULT '',
                    parsed_title TEXT NOT NULL DEFAULT '',
                    parsed_year TEXT NOT NULL DEFAULT '',
                    identity_status TEXT NOT NULL DEFAULT '',
                    identity_title TEXT NOT NULL DEFAULT '',
                    identity_year TEXT NOT NULL DEFAULT '',
                    identity_source TEXT NOT NULL DEFAULT '',
                    identity_revision INTEGER NOT NULL DEFAULT 0,
                    identity_decision_version INTEGER NOT NULL DEFAULT 0,
                    identity_evidence_fingerprint TEXT NOT NULL DEFAULT '',
                    tmdb_id TEXT NOT NULL DEFAULT '',
                    imdb_id TEXT NOT NULL DEFAULT '',
                    plex_guid TEXT NOT NULL DEFAULT '',
                    plex_rating_key TEXT NOT NULL DEFAULT '',
                    display_provider TEXT NOT NULL DEFAULT '',
                    metadata_status TEXT NOT NULL DEFAULT '',
                    metadata_source TEXT NOT NULL DEFAULT '',
                    metadata_accepted INTEGER NOT NULL DEFAULT 0,
                    enrichment_status TEXT NOT NULL DEFAULT '',
                    ingest_status TEXT NOT NULL DEFAULT '',
                    manual_lock INTEGER NOT NULL DEFAULT 0,
                    manual_locked INTEGER NOT NULL DEFAULT 0,
                    raw_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS media_identity_keys (
                    path_key TEXT NOT NULL,
                    identity_key TEXT NOT NULL,
                    key_source TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY (path_key, identity_key),
                    FOREIGN KEY (path_key) REFERENCES media_files(path_key) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS tmdb_movies (
                    tmdb_id TEXT PRIMARY KEY,
                    imdb_id TEXT NOT NULL DEFAULT '',
                    title TEXT NOT NULL DEFAULT '',
                    year TEXT NOT NULL DEFAULT '',
                    poster_url TEXT NOT NULL DEFAULT '',
                    release_date TEXT NOT NULL DEFAULT '',
                    adult INTEGER NOT NULL DEFAULT 0,
                    updated_at REAL NOT NULL DEFAULT 0,
                    raw_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS plex_files (
                    path_key TEXT PRIMARY KEY,
                    path TEXT NOT NULL DEFAULT '',
                    plex_title TEXT NOT NULL DEFAULT '',
                    plex_year TEXT NOT NULL DEFAULT '',
                    tmdb_id TEXT NOT NULL DEFAULT '',
                    imdb_id TEXT NOT NULL DEFAULT '',
                    plex_guid TEXT NOT NULL DEFAULT '',
                    rating_key TEXT NOT NULL DEFAULT '',
                    updated_at REAL NOT NULL DEFAULT 0,
                    raw_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS manual_matches (
                    path_key TEXT PRIMARY KEY,
                    path TEXT NOT NULL DEFAULT '',
                    provider TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL DEFAULT '',
                    tmdb_id TEXT NOT NULL DEFAULT '',
                    imdb_id TEXT NOT NULL DEFAULT '',
                    plex_guid TEXT NOT NULL DEFAULT '',
                    title TEXT NOT NULL DEFAULT '',
                    year TEXT NOT NULL DEFAULT '',
                    accepted INTEGER NOT NULL DEFAULT 0,
                    updated_at REAL NOT NULL DEFAULT 0,
                    raw_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS user_lists (
                    list_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL DEFAULT '',
                    system_type TEXT NOT NULL DEFAULT '',
                    created_at REAL NOT NULL DEFAULT 0,
                    updated_at REAL NOT NULL DEFAULT 0,
                    raw_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS list_items (
                    list_id TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    identity_key TEXT NOT NULL DEFAULT '',
                    tmdb_id TEXT NOT NULL DEFAULT '',
                    imdb_id TEXT NOT NULL DEFAULT '',
                    path TEXT NOT NULL DEFAULT '',
                    title TEXT NOT NULL DEFAULT '',
                    year TEXT NOT NULL DEFAULT '',
                    poster_url TEXT NOT NULL DEFAULT '',
                    raw_json TEXT NOT NULL,
                    PRIMARY KEY (list_id, position),
                    FOREIGN KEY (list_id) REFERENCES user_lists(list_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS collection_overrides (
                    collection_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL DEFAULT '',
                    updated_at REAL NOT NULL DEFAULT 0,
                    raw_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS followed_releases (
                    position INTEGER PRIMARY KEY,
                    identity_key TEXT NOT NULL DEFAULT '',
                    tmdb_id TEXT NOT NULL DEFAULT '',
                    imdb_id TEXT NOT NULL DEFAULT '',
                    title TEXT NOT NULL DEFAULT '',
                    year TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT '',
                    updated_at REAL NOT NULL DEFAULT 0,
                    raw_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS download_jobs (
                    torrent_hash TEXT PRIMARY KEY,
                    state TEXT NOT NULL DEFAULT '',
                    title TEXT NOT NULL DEFAULT '',
                    year TEXT NOT NULL DEFAULT '',
                    destination TEXT NOT NULL DEFAULT '',
                    updated_at REAL NOT NULL DEFAULT 0,
                    raw_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_media_files_tmdb_id ON media_files(tmdb_id);
                CREATE INDEX IF NOT EXISTS idx_media_files_imdb_id ON media_files(imdb_id);
                CREATE INDEX IF NOT EXISTS idx_media_files_plex_guid ON media_files(plex_guid);
                CREATE INDEX IF NOT EXISTS idx_media_files_title_year ON media_files(identity_title, identity_year);
                CREATE INDEX IF NOT EXISTS idx_media_files_status ON media_files(identity_status, metadata_status);
                CREATE INDEX IF NOT EXISTS idx_media_files_quality ON media_files(resolution, rip_source);
                CREATE INDEX IF NOT EXISTS idx_media_files_added ON media_files(added_time DESC);
                CREATE INDEX IF NOT EXISTS idx_media_identity_key ON media_identity_keys(identity_key);
                CREATE INDEX IF NOT EXISTS idx_list_items_identity ON list_items(identity_key);
                CREATE INDEX IF NOT EXISTS idx_list_items_tmdb ON list_items(tmdb_id);
                CREATE INDEX IF NOT EXISTS idx_followed_identity ON followed_releases(identity_key);
            """)
            connection.execute(
                "INSERT OR REPLACE INTO catalog_meta(key, value) VALUES('schema_version', ?)",
                (str(CATALOG_SCHEMA_VERSION),),
            )

    def import_documents(self, documents, backup_manifest):
        self.initialize()
        documents = dict(documents or {})
        with self.transaction() as connection:
            for table in (
                "source_documents", "list_items", "user_lists", "collection_overrides",
                "followed_releases", "download_jobs", "manual_matches", "plex_files",
                "tmdb_movies", "media_identity_keys", "media_files",
            ):
                connection.execute(f"DELETE FROM {table}")

            for name, document in sorted(documents.items()):
                connection.execute(
                    "INSERT INTO source_documents(name, payload_json) VALUES(?, ?)",
                    (name, _json_text(document)),
                )

            self._import_media_files(connection, documents.get("app_metadata/files.json", {}))
            self._import_tmdb_movies(connection, documents.get("app_metadata/tmdb_metadata.json", {}))
            self._import_plex_files(connection, documents.get("app_metadata/plex_metadata.json", {}))
            self._import_manual_matches(connection, documents.get("app_metadata/manual_matches.json", {}))
            self._import_lists(connection, documents.get("user_lists.json", {}))
            self._import_collections(connection, documents.get("user_collections.json", {}))
            self._import_followed(connection, documents.get("followed_releases.json", {}))
            self._import_download_jobs(connection, documents.get("qbittorrent/jobs.json", {}))
            self._import_media_identity_keys(connection)

            connection.execute(
                "INSERT OR REPLACE INTO catalog_meta(key, value) VALUES('backup_manifest', ?)",
                (_json_text(backup_manifest or {}),),
            )
            connection.execute(
                "INSERT OR REPLACE INTO catalog_meta(key, value) VALUES('imported_at', ?)",
                (datetime.now(timezone.utc).isoformat(),),
            )

    @staticmethod
    def _import_media_files(connection, document):
        records = document.get("files", {}) if isinstance(document, dict) else {}
        for path_key, record in records.items():
            record = record if isinstance(record, dict) else {}
            values = (
                _text(path_key), _text(record.get("path") or path_key), _text(record.get("filename")),
                _text(record.get("library_root")), int(_number(record.get("size"))),
                _number(record.get("added_time")), _number(record.get("modified_time")),
                _text(record.get("resolution")), _text(record.get("rip_source")),
                _text(record.get("parsed_title")), _text(record.get("parsed_year")),
                _text(record.get("identity_status")), _text(record.get("identity_title") or record.get("accepted_title")),
                _text(record.get("identity_year") or record.get("accepted_year")), _text(record.get("identity_source")),
                int(_number(record.get("identity_revision"))), int(_number(record.get("identity_decision_version"))),
                _text(record.get("identity_evidence_fingerprint")), _text(record.get("tmdb_id")),
                _text(record.get("imdb_id")), _text(record.get("plex_guid")), _text(record.get("plex_rating_key") or record.get("rating_key")),
                _text(record.get("display_provider")), _text(record.get("metadata_status")),
                _text(record.get("metadata_source")), _bool(record.get("metadata_accepted")),
                _text(record.get("enrichment_status")), _text(record.get("ingest_status")),
                _bool(record.get("manual_lock")), _bool(record.get("manual_locked")), _json_text(record),
            )
            placeholders = ",".join("?" for _ in values)
            connection.execute(f"INSERT INTO media_files VALUES ({placeholders})", values)

    @staticmethod
    def _import_tmdb_movies(connection, document):
        records = document.get("movies", {}) if isinstance(document, dict) else {}
        for tmdb_id, record in records.items():
            record = record if isinstance(record, dict) else {}
            connection.execute(
                "INSERT INTO tmdb_movies VALUES(?,?,?,?,?,?,?,?,?)",
                (_text(tmdb_id), _text(record.get("imdb_id")), _text(record.get("title")),
                 _text(record.get("year")), _text(record.get("poster_url")), _text(record.get("release_date")),
                 _bool(record.get("adult")), _number(record.get("updated_at")), _json_text(record)),
            )

    @staticmethod
    def _import_plex_files(connection, document):
        records = document.get("files", {}) if isinstance(document, dict) else {}
        for path_key, record in records.items():
            record = record if isinstance(record, dict) else {}
            connection.execute(
                "INSERT INTO plex_files VALUES(?,?,?,?,?,?,?,?,?,?)",
                (_text(path_key), _text(record.get("path") or path_key), _text(record.get("plex_title")),
                 _text(record.get("plex_year")), _text(record.get("tmdb_id")), _text(record.get("imdb_id")),
                 _text(record.get("plex_guid")), _text(record.get("rating_key")),
                 _number(record.get("updated_at")), _json_text(record)),
            )

    @staticmethod
    def _import_manual_matches(connection, document):
        records = document.get("matches", {}) if isinstance(document, dict) else {}
        for path_key, record in records.items():
            record = record if isinstance(record, dict) else {}
            connection.execute(
                "INSERT INTO manual_matches VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (_text(path_key), _text(record.get("path") or path_key), _text(record.get("provider")),
                 _text(record.get("source")), _text(record.get("tmdb_id")), _text(record.get("imdb_id")),
                 _text(record.get("plex_guid") or record.get("guid")), _text(record.get("title") or record.get("plex_title")),
                 _text(record.get("year") or record.get("plex_year")), _bool(record.get("accepted")),
                 _number(record.get("updated_at")), _json_text(record)),
            )

    @staticmethod
    def _import_lists(connection, document):
        lists = document.get("lists", []) if isinstance(document, dict) else []
        for list_row in lists if isinstance(lists, list) else []:
            if not isinstance(list_row, dict) or not _text(list_row.get("id")):
                continue
            list_id = _text(list_row.get("id"))
            connection.execute(
                "INSERT INTO user_lists VALUES(?,?,?,?,?,?)",
                (list_id, _text(list_row.get("name")), _text(list_row.get("system_type")),
                 _number(list_row.get("created_at")), _number(list_row.get("updated_at")), _json_text(list_row)),
            )
            movies = list_row.get("movies", [])
            for position, movie in enumerate(movies if isinstance(movies, list) else []):
                movie = movie if isinstance(movie, dict) else {}
                connection.execute(
                    "INSERT INTO list_items VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (list_id, position, _identity_key(movie), _text(movie.get("tmdb_id")),
                     _text(movie.get("imdb_id")), _text(movie.get("path")), _text(movie.get("title")),
                     _text(movie.get("year")), _text(movie.get("poster_url")), _json_text(movie)),
                )

    @staticmethod
    def _import_collections(connection, document):
        records = document.get("overrides", {}) if isinstance(document, dict) else {}
        for collection_id, record in records.items():
            record = record if isinstance(record, dict) else {}
            connection.execute(
                "INSERT INTO collection_overrides VALUES(?,?,?,?)",
                (_text(collection_id), _text(record.get("name")), _number(record.get("updated_at")), _json_text(record)),
            )

    @staticmethod
    def _import_followed(connection, document):
        movies = document.get("movies", []) if isinstance(document, dict) else []
        for position, movie in enumerate(movies if isinstance(movies, list) else []):
            movie = movie if isinstance(movie, dict) else {}
            connection.execute(
                "INSERT INTO followed_releases VALUES(?,?,?,?,?,?,?,?,?)",
                (position, _identity_key(movie), _text(movie.get("tmdb_id")), _text(movie.get("imdb_id")),
                 _text(movie.get("title")), _text(movie.get("year")), _text(movie.get("status")),
                 _number(movie.get("updated_at")), _json_text(movie)),
            )

    @staticmethod
    def _import_download_jobs(connection, document):
        jobs = document.get("jobs", {}) if isinstance(document, dict) else {}
        for torrent_hash, job in jobs.items():
            job = job if isinstance(job, dict) else {}
            connection.execute(
                "INSERT INTO download_jobs VALUES(?,?,?,?,?,?,?)",
                (_text(torrent_hash).lower(), _text(job.get("state")), _text(job.get("title")),
                 _text(job.get("year")), _text(job.get("destination")),
                 _number(job.get("updated_at")), _json_text(job)),
            )

    @staticmethod
    def _import_media_identity_keys(connection):
        rows = connection.execute("""
            SELECT mf.path_key, mf.raw_json AS file_json,
                   pf.raw_json AS plex_json, mm.raw_json AS manual_json
            FROM media_files mf
            LEFT JOIN plex_files pf ON pf.path_key = mf.path_key
            LEFT JOIN manual_matches mm ON mm.path_key = mf.path_key
        """).fetchall()
        for row in rows:
            file_record = json.loads(row["file_json"])
            authoritative = {
                **file_record,
                "title": file_record.get("identity_title") or file_record.get("accepted_title") or "",
                "year": file_record.get("identity_year") or file_record.get("accepted_year") or "",
            }
            candidates = [(authoritative, "authoritative")]
            if row["plex_json"]:
                candidates.append((json.loads(row["plex_json"]), "plex_snapshot"))
            if row["manual_json"]:
                candidates.append((json.loads(row["manual_json"]), "manual_match"))
            parsed_fallback = parse_release_filename(
                file_record.get("filename") or Path(file_record.get("path") or row["path_key"]).name
            )
            parsed = {
                "title": file_record.get("parsed_title") or parsed_fallback.get("title", ""),
                "year": file_record.get("parsed_year") or parsed_fallback.get("year", ""),
            }
            candidates.append((parsed, "parsed_filename"))
            for candidate, source in candidates:
                for identity_key in ownership_keys(candidate):
                    connection.execute(
                        "INSERT OR IGNORE INTO media_identity_keys(path_key, identity_key, key_source) VALUES(?, ?, ?)",
                        (row["path_key"], identity_key, source),
                    )

    def ownership_candidates(self, identity_keys):
        keys = list(dict.fromkeys(_text(key) for key in identity_keys if _text(key)))
        if not keys:
            return []
        placeholders = ",".join("?" for _ in keys)
        connection = self.connect()
        try:
            rows = connection.execute(f"""
                SELECT DISTINCT mf.*, pf.raw_json AS plex_json,
                       mm.raw_json AS manual_json, tm.raw_json AS tmdb_json
                FROM media_identity_keys mik
                JOIN media_files mf ON mf.path_key = mik.path_key
                LEFT JOIN plex_files pf ON pf.path_key = mf.path_key
                LEFT JOIN manual_matches mm ON mm.path_key = mf.path_key
                LEFT JOIN tmdb_movies tm ON tm.tmdb_id = mf.tmdb_id
                WHERE mik.identity_key IN ({placeholders})
                  AND (mf.identity_status = 'accepted' OR mf.metadata_accepted = 1)
                ORDER BY mf.added_time DESC
            """, keys).fetchall()
            return self._decode_media_rows(connection, rows, include_identity_keys=True)
        finally:
            connection.close()

    def library_candidates(self):
        connection = self.connect()
        try:
            rows = connection.execute("""
                SELECT mf.*, pf.raw_json AS plex_json,
                       mm.raw_json AS manual_json, tm.raw_json AS tmdb_json
                FROM media_files mf
                LEFT JOIN plex_files pf ON pf.path_key = mf.path_key
                LEFT JOIN manual_matches mm ON mm.path_key = mf.path_key
                LEFT JOIN tmdb_movies tm ON tm.tmdb_id = mf.tmdb_id
                ORDER BY mf.added_time DESC, mf.identity_title COLLATE NOCASE
            """).fetchall()
            return self._decode_media_rows(connection, rows, include_identity_keys=False)
        finally:
            connection.close()

    @staticmethod
    def _decode_media_rows(connection, rows, include_identity_keys):
        result = []
        for row in rows:
            item = dict(row)
            for column in ("raw_json", "plex_json", "manual_json", "tmdb_json"):
                item[column] = json.loads(item[column]) if item.get(column) else {}
            if include_identity_keys:
                item["identity_keys"] = [
                    key_row[0]
                    for key_row in connection.execute(
                        "SELECT identity_key FROM media_identity_keys WHERE path_key = ?",
                        (item["path_key"],),
                    ).fetchall()
                ]
            result.append(item)
        return result

    def parity_report(self, expected_counts):
        table_map = {
            "file_records": "media_files",
            "tmdb_movies": "tmdb_movies",
            "plex_files": "plex_files",
            "manual_matches": "manual_matches",
            "user_lists": "user_lists",
            "list_movies": "list_items",
            "collection_overrides": "collection_overrides",
            "followed_releases": "followed_releases",
            "qbittorrent_jobs": "download_jobs",
        }
        connection = self.connect()
        try:
            counts = {
                name: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                for name, table in table_map.items()
            }
            integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
            foreign_keys = [dict(row) for row in connection.execute("PRAGMA foreign_key_check").fetchall()]
            schema_version = int(connection.execute(
                "SELECT value FROM catalog_meta WHERE key='schema_version'"
            ).fetchone()[0])
            mismatches = {
                name: {"expected": int(expected_counts.get(name, 0)), "actual": counts[name]}
                for name in table_map
                if counts[name] != int(expected_counts.get(name, 0))
            }
            return {
                "passed": integrity == "ok" and not foreign_keys and not mismatches and schema_version == CATALOG_SCHEMA_VERSION,
                "schema_version": schema_version,
                "integrity": integrity,
                "foreign_key_errors": foreign_keys,
                "counts": counts,
                "mismatches": mismatches,
            }
        finally:
            connection.close()
