import hashlib
import json
import os
import shutil
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from services.catalog_store import CatalogError, CatalogStore, _bool, _json_text, _number, _text
from services.canonical_catalog import CANONICAL_CARD_FIELDS, CANONICAL_CONTRACT_VERSION
from services.media_file_facts import FILE_FACTS_VERSION, QUALITY_CLASSIFIER_VERSION


CORE_DOCUMENTS = {
    "app_metadata/files.json",
    "app_metadata/tmdb_metadata.json",
    "app_metadata/plex_metadata.json",
    "app_metadata/manual_matches.json",
    "app_metadata/identity_audit_fingerprints.json",
    "user_lists.json",
    "user_collections.json",
    "followed_releases.json",
}
EXTERNAL_DOCUMENTS = {"qbittorrent/jobs.json"}
OPERATIONAL_DOCUMENTS = {"app_metadata/library_inventory.json"}
ROW_DOCUMENT_TABLES = {
    "app_metadata/files.json": ("media_files", "path_key"),
    "app_metadata/tmdb_metadata.json": ("tmdb_movies", "tmdb_id"),
    "app_metadata/plex_metadata.json": ("plex_files", "path_key"),
    "app_metadata/manual_matches.json": ("manual_matches", "path_key"),
    "app_metadata/identity_audit_fingerprints.json": (
        "identity_audit_fingerprints",
        "path_key",
    ),
}
NON_CARD_FIELDS = {
    "updated_at",
}
NON_CARD_FIELDS_BY_DOCUMENT = {
    "app_metadata/files.json": {
        "identity_revision",
        "observed_at",
        "probed_at",
        "_ingestion_retry",
    },
    "app_metadata/tmdb_metadata.json": {
        "release_years_checked_at",
    },
}


def _document_domain(name):
    name = str(name or '').replace('\\', '/')
    if name.startswith('app_metadata/'):
        return 'media'
    if name in {'user_lists.json', 'user_collections.json', 'followed_releases.json'}:
        return 'curation'
    return 'catalog'


def catalog_database_path(user_data_dir, local_app_data=None):
    user_data_dir = Path(user_data_dir).resolve()
    # Portable launchers keep authoritative state with the selected data folder.
    # Installed CP retains its existing per-data-root LocalAppData database.
    if os.environ.get("CP_PORTABLE_DATA") == "1":
        return user_data_dir / "catalog.sqlite"
    root = Path(local_app_data or os.environ.get("LOCALAPPDATA") or (Path.home() / ".cinema-paradiso"))
    key = hashlib.blake2b(str(user_data_dir).encode("utf-8", errors="surrogatepass"), digest_size=8).hexdigest()
    return (root / "Cinema Paradiso" / "Catalog" / f"catalog-read-{key}.sqlite").resolve()


class CatalogRepository:
    """SQLite write authority with explicit JSON rollback exports."""

    def __init__(self, user_data_dir, database_path=None, export_delay=0.5, auto_export=False):
        self.user_data_dir = Path(user_data_dir).resolve()
        self.store = CatalogStore(database_path or catalog_database_path(self.user_data_dir))
        self.export_delay = float(export_delay)
        self.auto_export = bool(auto_export)
        self._lock = threading.RLock()
        self._cache = {}
        self._pending_exports = set()
        self._export_timer = None
        self._closed = False
        self.store.initialize()

    @property
    def database_path(self):
        return self.store.database_path

    @contextmanager
    def transaction(self):
        """Open one repository-owned immediate transaction for future atomic work."""
        with self._lock, self.store.transaction() as connection:
            yield connection

    def authority_enabled(self):
        connection = self.store.connect()
        try:
            row = connection.execute("SELECT value FROM catalog_meta WHERE key='write_authority'").fetchone()
            return bool(row and row[0] == "sqlite")
        finally:
            connection.close()

    def activate_from_json(self):
        with self._lock:
            if self.authority_enabled():
                return False
            documents = self._load_json_documents()
            self.store.import_documents(documents, {})
            with self.store.transaction() as connection:
                connection.execute(
                    "INSERT OR REPLACE INTO catalog_meta(key, value) VALUES('write_authority', 'sqlite')"
                )
                connection.execute(
                    "INSERT OR REPLACE INTO catalog_meta(key, value) VALUES('generation', '1')"
                )
                for domain in ('media', 'curation', 'catalog'):
                    connection.execute(
                        "INSERT OR REPLACE INTO catalog_meta(key, value) VALUES(?, '1')",
                        (f'{domain}_generation',),
                    )
                connection.execute(
                    "INSERT OR REPLACE INTO catalog_meta(key, value) VALUES('canonical_media_generation', '1')"
                )
            self._cache.clear()
            return True

    def _load_json_documents(self):
        documents = {}
        metadata_dir = self.user_data_dir / "app_metadata"
        if metadata_dir.is_dir():
            for path in metadata_dir.glob("*.json"):
                documents[f"app_metadata/{path.name}"] = self._load_bootstrap_document(path)
        for name in ("user_lists.json", "user_collections.json", "followed_releases.json"):
            path = self.user_data_dir / name
            if path.is_file():
                documents[name] = self._load_bootstrap_document(path)
        return documents

    @staticmethod
    def _load_bootstrap_document(path):
        path = Path(path)
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as current_error:
            backup = Path(f"{path}.bak")
            if backup.is_file():
                try:
                    return json.loads(backup.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    pass
            raise CatalogError(f"Cannot activate catalog from invalid JSON: {path}") from current_error

    def generation(self, domain=None):
        key = f'{domain}_generation' if domain else 'generation'
        connection = self.store.connect()
        try:
            row = connection.execute("SELECT value FROM catalog_meta WHERE key=?", (key,)).fetchone()
            return int(row[0]) if row else 0
        finally:
            connection.close()

    def catalog_meta(self, key, default=""):
        connection = self.store.connect()
        try:
            row = connection.execute("SELECT value FROM catalog_meta WHERE key=?", (str(key),)).fetchone()
            return str(row[0]) if row else str(default)
        finally:
            connection.close()

    def set_operational_meta(self, key, value):
        """Persist operational state without changing catalog generations."""
        with self._lock, self.store.transaction() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO catalog_meta(key, value) VALUES(?, ?)",
                (str(key), str(value)),
            )

    def has_document(self, name):
        connection = self.store.connect()
        try:
            return connection.execute(
                "SELECT 1 FROM source_documents WHERE name=? LIMIT 1",
                (str(name).replace("\\", "/"),),
            ).fetchone() is not None
        finally:
            connection.close()

    @staticmethod
    def _bump_generation(connection, document_names=()):
        connection.execute("""
            INSERT INTO catalog_meta(key, value) VALUES('generation', '1')
            ON CONFLICT(key) DO UPDATE SET value = CAST(value AS INTEGER) + 1
        """)
        domains = sorted({_document_domain(name) for name in document_names})
        for domain in domains:
            key = f'{domain}_generation'
            connection.execute("""
                INSERT INTO catalog_meta(key, value) VALUES(?, '1')
                ON CONFLICT(key) DO UPDATE SET value = CAST(value AS INTEGER) + 1
            """, (key,))
        if 'media' in domains:
            connection.execute("""
                INSERT OR REPLACE INTO catalog_meta(key, value)
                SELECT 'canonical_media_generation', value
                FROM catalog_meta WHERE key = 'media_generation'
            """)
        connection.execute(
            "INSERT OR REPLACE INTO catalog_meta(key, value) VALUES('export_dirty', '1')"
        )

    def read_document(self, name, fallback):
        name = str(name).replace("\\", "/")
        with self._lock:
            cached = self._cache.get(name)
            if cached is not None:
                return json.loads(json.dumps(cached))
            connection = self.store.connect()
            try:
                document = self._read_document(connection, name, fallback)
            finally:
                connection.close()
            self._cache[name] = document
            return json.loads(json.dumps(document))

    def find_plex_metadata_by_thumbs(self, thumbs):
        wanted = list(dict.fromkeys(_text(thumb) for thumb in (thumbs or []) if _text(thumb)))
        if not wanted:
            return {}
        placeholders = ",".join("?" for _ in wanted)
        with self._lock:
            connection = self.store.connect()
            try:
                rows = connection.execute(
                    "SELECT raw_json FROM plex_files "
                    f"WHERE json_extract(raw_json, '$.plex_thumb') IN ({placeholders})",
                    wanted,
                ).fetchall()
            finally:
                connection.close()
        records = {}
        for row in rows:
            try:
                record = json.loads(row[0])
            except ValueError:
                continue
            thumb = _text(record.get("plex_thumb"))
            if thumb:
                records[thumb] = record
        return records

    def owned_movie(self, *, path="", movie_key=""):
        path_key = os.path.normcase(os.path.normpath(str(path or ""))) if path else ""
        return self.store.owned_movie_candidate(path_key=path_key, movie_key=movie_key)

    def pending_final_card_paths(self):
        """Return stable accepted files still waiting for Movie View publication."""
        connection = self.store.connect()
        try:
            rows = connection.execute(
                "SELECT path FROM media_files "
                "WHERE ingest_status='stable' "
                "AND identity_status='accepted' "
                "AND metadata_accepted=1 "
                "AND json_extract(raw_json, '$.movie_view_publication')='pending' "
                "ORDER BY path_key"
            ).fetchall()
            return [str(row[0]) for row in rows if str(row[0] or "").strip()]
        finally:
            connection.close()

    def _publication_assessments(self, connection, paths):
        keys = list(dict.fromkeys(os.path.normcase(os.path.normpath(str(path))) for path in paths if str(path).strip()))
        result = {}
        for candidate in self.store._candidates_for_path_keys(connection, keys):
            raw_value = candidate.get("raw_json") or {}
            if isinstance(raw_value, str):
                try:
                    raw_value = json.loads(raw_value)
                except (TypeError, ValueError):
                    raw_value = {}
            raw = dict(raw_value) if isinstance(raw_value, dict) else {}
            card_value = candidate.get("relational_canonical") or {}
            if isinstance(card_value, str):
                try:
                    card_value = json.loads(card_value)
                except (TypeError, ValueError):
                    card_value = {}
            card = dict(card_value) if isinstance(card_value, dict) else {}
            valid_probe = (
                raw.get("probe_status") == "ok"
                and int(raw.get("probe_size") or -1) == int(raw.get("size") or -2)
                and float(raw.get("probe_modified_time") or -1) == float(raw.get("modified_time") or -2)
                and not str(raw.get("probe_error") or "")
                and int(raw.get("file_facts_version") or 0) == FILE_FACTS_VERSION
                and int(raw.get("classifier_version") or 0) == QUALITY_CLASSIFIER_VERSION
            )
            stable_probe = raw.get('ingest_status') == 'stable' and valid_probe
            identity_ready = (
                bool(raw.get("metadata_accepted"))
                and raw.get("identity_status") == "accepted"
                and bool(card.get("accepted")) and bool(card.get("movie_key"))
                and bool(card.get("title")) and bool(str(card.get("year") or ""))
                and bool(card.get("selected_provider"))
                and bool(card.get("selected_provider_snapshot"))
                and card.get("enrichment_status") == "complete"
                and not bool(card.get("fallback_active"))
                and int(card.get("metadata_contract_version") or 0) == CANONICAL_CONTRACT_VERSION
                and card.get("projection_contract") == "canonical_movie_card"
                and card.get("people_status") in {"complete", "empty"}
                and all(field in card for field in CANONICAL_CARD_FIELDS)
            )
            poster = str(card.get("poster_url") or "")
            local_poster = str(card.get("local_poster_url") or "")
            poster_ready = not poster
            if local_poster.startswith("/api/assets/"):
                checksum = local_poster.rsplit("/", 1)[-1]
                asset = connection.execute(
                    "SELECT status, checksum, local_path FROM media_assets "
                    "WHERE checksum=? AND status='ready' LIMIT 1",
                    (checksum,),
                ).fetchone()
                poster_ready = bool(
                    asset and asset[0] == "ready" and asset[1] == checksum
                    and len(checksum) == 64 and Path(asset[2]).is_file()
                )
            eligible = bool(stable_probe and identity_ready and poster_ready)
            stages = [name for name, ready in (("facts", stable_probe), ("identity", identity_ready), ("assets", poster_ready)) if not ready]
            if eligible and raw.get("movie_view_publication") != "ready":
                stages.append("publication")
            key = candidate["path_key"]
            result[key] = {
                "path": raw.get("path") or candidate.get("path") or "",
                "movie_key": card.get("movie_key") or "",
                "eligible_to_publish": eligible,
                "recoverable_prepared": bool(valid_probe and identity_ready and poster_ready and (raw.get('_ingestion_retry') or {}).get('stage') == 'assets'),
                "publication_committed": eligible and raw.get("movie_view_publication") == "ready",
                "legacy_visible": "movie_view_publication" not in raw,
                "required_stages": stages,
                "blockers": {stage: stage + "_not_ready" for stage in stages},
            }
        return result

    def publication_status(self, paths):
        with self.library_read_context() as context:
            return self._publication_assessments(context["connection"], paths)

    def final_card_publication(self, paths):
        """Only writer of strict final-card publication; status alone never publishes."""
        ready = []
        changed = False
        with self._lock, self.store.transaction() as connection:
            for key, status in self._publication_assessments(connection, paths).items():
                if not status["eligible_to_publish"]:
                    continue
                if not status["publication_committed"]:
                    connection.execute("UPDATE media_files SET raw_json=json_set(raw_json, '$.movie_view_publication','ready') WHERE path_key=?", (key,))
                    changed = True
                ready.append({"path": status["path"], "movie_key": status["movie_key"]})
            if changed:
                self._bump_generation(connection, ("app_metadata/files.json",))
                self._cache.pop("app_metadata/files.json", None)
        if changed:
            self.schedule_export("app_metadata/files.json")
        return ready

    @contextmanager
    def library_read_context(self):
        connection = self.store.connect()
        try:
            connection.execute("BEGIN")
            row = connection.execute("SELECT value FROM catalog_meta WHERE key='media_generation'").fetchone()
            yield {"connection": connection, "generation": int(row[0]) if row else 0}
        finally:
            connection.close()

    @staticmethod
    def _normalize_filter_paths(filters):
        filters = dict(filters or {})
        for field in ("upgrade_path_keys", "collection_path_keys"):
            filters[field] = [
                os.path.normcase(os.path.normpath(str(path or "")))
                for path in filters.get(field, [])
                if str(path or "").strip()
            ]
        return filters

    def library_page(self, filters=None, *, query=None, page=1, page_size=40, upgrade_path_keys=(), read_context=None):
        normalized_upgrade_paths = self._normalize_filter_paths({
            "upgrade_path_keys": upgrade_path_keys,
        })["upgrade_path_keys"]
        return self.store.library_page(
            self._normalize_filter_paths(filters),
            query=query,
            page=page,
            page_size=page_size,
            upgrade_path_keys=normalized_upgrade_paths,
            read_context=read_context,
        )

    def library_selection_paths(self, filters=None, *, query=None, upgrade_path_keys=(), read_context=None):
        normalized_upgrade_paths = self._normalize_filter_paths({
            "upgrade_path_keys": upgrade_path_keys,
        })["upgrade_path_keys"]
        return self.store.library_selection_paths(
            self._normalize_filter_paths(filters),
            query=query,
            upgrade_path_keys=normalized_upgrade_paths,
            read_context=read_context,
        )

    def library_keywords(self, query="", *, page=1, page_size=50):
        return self.store.library_keywords(query, page=page, page_size=page_size)

    def file_facts_backfill_candidates(self, limit=8, *, retry_failed=False):
        return self.store.file_facts_backfill_candidates(
            limit,
            retry_failed=retry_failed,
        )

    def file_facts_backfill_remaining(self, *, retry_failed=False):
        return self.store.file_facts_backfill_remaining(
            retry_failed=retry_failed,
        )

    def apply_file_facts_batch(self, updates):
        with self._lock, self.store.transaction() as connection:
            report = self.store.apply_file_facts_batch(connection, updates)
            if report["changed"]:
                self._bump_generation(
                    connection,
                    ("app_metadata/files.json",),
                )
                self._cache.pop("app_metadata/files.json", None)
        if report["changed"]:
            self.schedule_export("app_metadata/files.json")
        return report

    def library_candidates_for_paths(self, paths):
        path_keys = [
            os.path.normcase(os.path.normpath(str(path or "")))
            for path in paths or []
            if str(path or "").strip()
        ]
        return self.store.candidates_for_paths(path_keys)

    @staticmethod
    def _source_document(connection, name, fallback):
        row = connection.execute("SELECT payload_json FROM source_documents WHERE name = ?", (name,)).fetchone()
        if not row:
            return json.loads(json.dumps(fallback))
        try:
            value = json.loads(row[0])
        except ValueError:
            return json.loads(json.dumps(fallback))
        return value if isinstance(value, type(fallback)) else json.loads(json.dumps(fallback))

    @classmethod
    def _read_document(cls, connection, name, fallback):
        document = cls._source_document(connection, name, fallback)
        table_specs = {
            "app_metadata/files.json": ("files", "media_files", "path_key"),
            "app_metadata/tmdb_metadata.json": ("movies", "tmdb_movies", "tmdb_id"),
            "app_metadata/plex_metadata.json": ("files", "plex_files", "path_key"),
            "app_metadata/manual_matches.json": ("matches", "manual_matches", "path_key"),
            "app_metadata/identity_audit_fingerprints.json": (
                "files",
                "identity_audit_fingerprints",
                "path_key",
            ),
            "user_collections.json": ("overrides", "collection_overrides", "collection_id"),
        }
        if name in table_specs:
            root_key, table, key_column = table_specs[name]
            rows = connection.execute(f"SELECT {key_column}, raw_json FROM {table}").fetchall()
            document[root_key] = {str(row[0]): json.loads(row[1]) for row in rows}
        elif name == "user_lists.json":
            rows = connection.execute(
                "SELECT list_id, name, system_type, created_at, updated_at, raw_json "
                "FROM user_lists ORDER BY created_at, list_id"
            ).fetchall()
            lists = []
            for row in rows:
                list_row = cls._json_object(cls._row_value(row, 5, "raw_json"))
                list_row.update({
                    "id": str(cls._row_value(row, 0, "list_id")),
                    "name": str(cls._row_value(row, 1, "name") or ""),
                    "system_type": str(cls._row_value(row, 2, "system_type") or ""),
                    "created_at": float(cls._row_value(row, 3, "created_at") or 0),
                    "updated_at": float(cls._row_value(row, 4, "updated_at") or 0),
                })
                item_rows = connection.execute(
                    "SELECT position, tmdb_id, imdb_id, path, title, year, poster_url, raw_json "
                    "FROM list_items WHERE list_id = ? ORDER BY position",
                    (cls._row_value(row, 0, "list_id"),),
                ).fetchall()
                movies = []
                for item_row in item_rows:
                    movie = cls._json_object(cls._row_value(item_row, 7, "raw_json"))
                    movie.update({
                        "tmdb_id": str(cls._row_value(item_row, 1, "tmdb_id") or ""),
                        "imdb_id": str(cls._row_value(item_row, 2, "imdb_id") or ""),
                        "path": str(cls._row_value(item_row, 3, "path") or ""),
                        "title": str(cls._row_value(item_row, 4, "title") or ""),
                        "year": str(cls._row_value(item_row, 5, "year") or ""),
                        "poster_url": str(cls._row_value(item_row, 6, "poster_url") or ""),
                    })
                    movies.append(movie)
                list_row["movies"] = movies
                lists.append(list_row)
            document["lists"] = lists
        elif name == "followed_releases.json":
            rows = connection.execute(
                "SELECT tmdb_id, imdb_id, title, year, status, updated_at, raw_json "
                "FROM followed_releases ORDER BY position"
            ).fetchall()
            movies = []
            for row in rows:
                movie = cls._json_object(cls._row_value(row, 6, "raw_json"))
                movie.update({
                    "tmdb_id": str(cls._row_value(row, 0, "tmdb_id") or ""),
                    "imdb_id": str(cls._row_value(row, 1, "imdb_id") or ""),
                    "title": str(cls._row_value(row, 2, "title") or ""),
                    "year": str(cls._row_value(row, 3, "year") or ""),
                    "status": str(cls._row_value(row, 4, "status") or ""),
                    "updated_at": float(cls._row_value(row, 5, "updated_at") or 0),
                })
                movies.append(movie)
            document["movies"] = movies
        return document

    @staticmethod
    def _json_object(value):
        try:
            decoded = json.loads(value)
        except (TypeError, ValueError):
            return {}
        return decoded if isinstance(decoded, dict) else {}

    @staticmethod
    def _row_value(row, index, name):
        try:
            return row[name]
        except (IndexError, KeyError, TypeError):
            return row[index]

    def replace_document(self, name, document):
        name = str(name).replace("\\", "/")
        document = json.loads(json.dumps(document))
        with self._lock, self.store.transaction() as connection:
            if name == "app_metadata/files.json":
                latest = connection.execute("SELECT path_key, json_extract(raw_json, '$._ingestion_retry') FROM media_files WHERE json_type(raw_json, '$._ingestion_retry')='object'").fetchall()
                ledgers = {row[0]: json.loads(row[1]) for row in latest}
                for key, record in document.get("files", {}).items():
                    record.pop("_ingestion_retry", None)
                    if key in ledgers:
                        record["_ingestion_retry"] = ledgers[key]
            connection.execute(
                "INSERT OR REPLACE INTO source_documents(name, payload_json) VALUES(?, ?)",
                (name, _json_text(document)),
            )
            self._replace_normalized_document(connection, name, document)
            if name in {
                "app_metadata/files.json",
                "app_metadata/tmdb_metadata.json",
                "app_metadata/plex_metadata.json",
                "app_metadata/manual_matches.json",
            }:
                self.store.canonical.rebuild(connection)
            else:
                self.store.canonical.sync_changes(connection, name)
            if name == "app_metadata/files.json":
                connection.execute("""
                    DELETE FROM playback_history
                    WHERE path_key NOT IN (SELECT path_key FROM media_files)
                """)
            if name in {
                "app_metadata/files.json",
                "app_metadata/tmdb_metadata.json",
                "app_metadata/plex_metadata.json",
                "app_metadata/manual_matches.json",
            }:
                self._sync_playback_movie_keys(connection)
            self._bump_generation(connection, (name,))
            self._cache.pop(name, None)
        self.schedule_export(name)

    def replace_operational_document(self, name, document):
        """Persist bounded bookkeeping without advancing catalog generations."""
        name = str(name).replace("\\", "/")
        if name not in OPERATIONAL_DOCUMENTS:
            raise CatalogError(f"Unsupported operational document: {name}")
        document = json.loads(json.dumps(document))
        payload = _json_text(document)
        changed = False
        with self._lock, self.store.transaction() as connection:
            current = connection.execute(
                "SELECT payload_json FROM source_documents WHERE name=?",
                (name,),
            ).fetchone()
            if not current or current[0] != payload:
                connection.execute(
                    "INSERT OR REPLACE INTO source_documents(name, payload_json) VALUES(?, ?)",
                    (name, payload),
                )
                self._cache.pop(name, None)
                changed = True
        if changed:
            self.schedule_export(name)
        return changed

    def _replace_normalized_document(self, connection, name, document):
        if name == "app_metadata/files.json":
            connection.execute("DELETE FROM media_identity_keys")
            connection.execute("DELETE FROM media_files")
            self.store._import_media_files(connection, document)
            self.store._import_media_identity_keys(connection)
        elif name == "app_metadata/tmdb_metadata.json":
            connection.execute("DELETE FROM tmdb_movies")
            self.store._import_tmdb_movies(connection, document)
        elif name == "app_metadata/plex_metadata.json":
            connection.execute("DELETE FROM plex_files")
            self.store._import_plex_files(connection, document)
            connection.execute("DELETE FROM media_identity_keys")
            self.store._import_media_identity_keys(connection)
        elif name == "app_metadata/manual_matches.json":
            connection.execute("DELETE FROM manual_matches")
            self.store._import_manual_matches(connection, document)
            connection.execute("DELETE FROM media_identity_keys")
            self.store._import_media_identity_keys(connection)
        elif name == "app_metadata/identity_audit_fingerprints.json":
            connection.execute("DELETE FROM identity_audit_fingerprints")
            self.store._import_identity_audit_fingerprints(connection, document)
        elif name == "user_lists.json":
            connection.execute("DELETE FROM list_items")
            connection.execute("DELETE FROM user_lists")
            self.store._import_lists(connection, document)
        elif name == "user_collections.json":
            connection.execute("DELETE FROM collection_overrides")
            self.store._import_collections(connection, document)
        elif name == "followed_releases.json":
            connection.execute("DELETE FROM followed_releases")
            self.store._import_followed(connection, document)

    def upsert_record(self, name, key, record):
        return self.upsert_records(name, {str(key): record})[str(key)]

    def get_record(self, name, key, fallback=None):
        name = str(name).replace("\\", "/")
        key = str(key)
        if name not in ROW_DOCUMENT_TABLES:
            raise KeyError(f"Document does not support row reads: {name}")
        table, key_column = ROW_DOCUMENT_TABLES[name]
        connection = self.store.connect()
        try:
            row = connection.execute(
                f"SELECT raw_json FROM {table} WHERE {key_column} = ?", (key,)
            ).fetchone()
            return json.loads(row[0]) if row else json.loads(json.dumps(fallback or {}))
        finally:
            connection.close()

    def get_records(self, name, keys, *, connection=None):
        name = str(name).replace("\\", "/")
        if name not in ROW_DOCUMENT_TABLES:
            raise KeyError(f"Document does not support row reads: {name}")
        keys = list(dict.fromkeys(str(key) for key in keys))
        table, column = ROW_DOCUMENT_TABLES[name]
        owned = connection is None
        connection = connection or self.store.connect()
        try:
            result = {}
            for offset in range(0, len(keys), 200):
                rows = connection.execute(
                    f"SELECT {column}, raw_json FROM {table} WHERE {column} IN (SELECT value FROM json_each(?))",
                    (_json_text(keys[offset:offset + 200]),),
                )
                result.update((str(row[0]), json.loads(row[1])) for row in rows)
            return result
        finally:
            if owned:
                connection.close()

    def inventory_entries(self, path_keys, *, connection=None):
        keys = list(dict.fromkeys(str(key) for key in path_keys))
        owned = connection is None
        connection = connection or self.store.connect()
        try:
            result = {}
            for offset in range(0, len(keys), 200):
                rows = connection.execute("""
                    SELECT j.key, j.value FROM source_documents d,
                        json_each(d.payload_json, '$.files') j
                    WHERE d.name='app_metadata/library_inventory.json'
                      AND j.key IN (SELECT value FROM json_each(?))
                """, (_json_text(keys[offset:offset + 200]),))
                result.update((row[0], json.loads(row[1])) for row in rows)
            return result
        finally:
            if owned:
                connection.close()

    def patch_inventory(self, upserts, removed_keys):
        name = 'app_metadata/library_inventory.json'
        changed = False
        with self._lock, self.store.transaction() as connection:
            changed = bool(connection.execute("INSERT OR IGNORE INTO source_documents(name,payload_json) VALUES(?,?)", (name, '{"files":{}}')).rowcount)
            for key in removed_keys:
                path = '$.files.' + json.dumps(str(key))
                changed |= bool(connection.execute(
                    "UPDATE source_documents SET payload_json=json_remove(payload_json,?) WHERE name=? AND json_type(payload_json,?) IS NOT NULL",
                    (path, name, path),
                ).rowcount)
            for key, value in dict(upserts).items():
                path = '$.files.' + json.dumps(str(key))
                payload = _json_text(value)
                changed |= bool(connection.execute(
                    "UPDATE source_documents SET payload_json=json_set(payload_json,?,json(?)) WHERE name=? AND COALESCE(json_extract(payload_json,?), '')<>json(?)",
                    (path, payload, name, path, payload),
                ).rowcount)
            if changed:
                self._cache.pop(name, None)
                connection.execute("INSERT OR REPLACE INTO catalog_meta(key,value) VALUES('export_dirty','1')")
        if changed:
            self.schedule_export(name)
        return changed

    def patch_file_operational(self, path_key, *, expected_revision, retry_state):
        state = json.loads(_json_text(retry_state))
        if int(state.get('revision') or 0) != int(expected_revision) + 1:
            raise ValueError('Retry revision must advance exactly once')
        with self._lock, self.store.transaction() as connection:
            changed = connection.execute("""
                UPDATE media_files SET raw_json=json_set(raw_json, '$._ingestion_retry', json(?))
                WHERE path_key=? AND COALESCE(json_extract(raw_json, '$._ingestion_retry.revision'),0)=?
            """, (_json_text(state), str(path_key), int(expected_revision))).rowcount
            if changed:
                self._cache.pop('app_metadata/files.json', None)
                connection.execute("INSERT OR REPLACE INTO catalog_meta(key,value) VALUES('export_dirty','1')")
        if changed:
            self.schedule_export('app_metadata/files.json')
        return bool(changed)

    def next_retry_admission_order(self):
        """Allocate operational queue order atomically, without a media revision."""
        with self._lock, self.store.transaction() as connection:
            existing = connection.execute(
                "SELECT value FROM catalog_meta WHERE key='retry_admission_order'"
            ).fetchone()
            last = int(existing[0]) if existing is not None else 0
            order = int(last) + 1
            connection.execute(
                "INSERT OR REPLACE INTO catalog_meta(key,value) VALUES('retry_admission_order',?)",
                (str(order),),
            )
            return order

    def retry_records(self, limit=4096):
        connection = self.store.connect()
        try:
            return [json.loads(row[0]) for row in connection.execute("""
                SELECT raw_json FROM media_files
                WHERE json_extract(raw_json, '$._ingestion_retry.state') IN ('waiting','running')
                   OR (json_extract(raw_json, '$._ingestion_retry.state')='complete'
                       AND json_extract(raw_json, '$._ingestion_retry.handoff.state')='deferred'
                       AND json_array_length(raw_json, '$._ingestion_retry.source_identity.paths')>1)
                ORDER BY CASE WHEN json_extract(raw_json, '$._ingestion_retry.state')='complete' THEN 1 ELSE 0 END,
                    COALESCE(json_extract(raw_json, '$._ingestion_retry.next_due_at'),0),
                    COALESCE(json_extract(raw_json, '$._ingestion_retry.admission_order'),0),
                    COALESCE(json_extract(raw_json, '$._ingestion_retry.first_observed_at'),0), rowid
                LIMIT ?
            """, (min(max(int(limit), 1), 4096),))]
        finally:
            connection.close()

    def path_keys_under_roots(self, roots, *, inventory=False):
        roots = [os.path.normcase(os.path.normpath(str(root))).rstrip('\\/') for root in roots]
        source = "SELECT j.key AS path_key FROM source_documents d,json_each(d.payload_json,'$.files') j WHERE d.name='app_metadata/library_inventory.json'" if inventory else 'SELECT path_key FROM media_files'
        connection = self.store.connect()
        try:
            return [row[0] for row in connection.execute(f"SELECT path_key FROM ({source}) WHERE EXISTS (SELECT 1 FROM json_each(?) r WHERE path_key=r.value OR substr(path_key,1,length(r.value)+1)=r.value||?)", (_json_text(roots), os.sep))]
        finally:
            connection.close()

    def upsert_records(self, name, records):
        name = str(name).replace("\\", "/")
        records = {str(key): json.loads(json.dumps(record or {})) for key, record in dict(records or {}).items()}
        if not records:
            return {}
        if name not in ROW_DOCUMENT_TABLES:
            raise KeyError(f"Document does not support row writes: {name}")
        table, key_column = ROW_DOCUMENT_TABLES[name]
        ignored = NON_CARD_FIELDS | NON_CARD_FIELDS_BY_DOCUMENT.get(name, set())

        def card_payload(record):
            return {
                key: value
                for key, value in dict(record or {}).items()
                if key not in ignored
            }

        with self._lock, self.store.transaction() as connection:
            material_change = False
            for key, record in records.items():
                current = connection.execute(
                    f"SELECT raw_json FROM {table} WHERE {key_column} = ?",
                    (key,),
                ).fetchone()
                try:
                    current_record = json.loads(current[0]) if current else None
                except (TypeError, ValueError):
                    current_record = None
                if name == 'app_metadata/files.json':
                    record.pop('_ingestion_retry', None)
                    if current_record and '_ingestion_retry' in current_record:
                        record['_ingestion_retry'] = current_record['_ingestion_retry']
                if current_record is None or card_payload(current_record) != card_payload(record):
                    material_change = True
                self._upsert_record(connection, name, key, record)
            self.store.canonical.sync_changes(connection, name, records.keys())
            if name in {
                "app_metadata/files.json",
                "app_metadata/tmdb_metadata.json",
                "app_metadata/plex_metadata.json",
                "app_metadata/manual_matches.json",
            }:
                self._sync_playback_movie_keys(
                    connection,
                    None if name == "app_metadata/tmdb_metadata.json" else records.keys(),
                )
            if material_change:
                self._bump_generation(connection, (name,))
            else:
                connection.execute(
                    "INSERT OR REPLACE INTO catalog_meta(key, value) VALUES('export_dirty', '1')"
                )
            self._cache.pop(name, None)
        self.schedule_export(name)
        return records

    def _upsert_record(self, connection, name, key, record):
        if name == "app_metadata/files.json":
            self.store._upsert_media_file(connection, key, record)
            connection.execute("DELETE FROM media_identity_keys WHERE path_key = ?", (key,))
            self.store._import_media_identity_keys(connection, key)
        elif name == "app_metadata/tmdb_metadata.json":
            connection.execute(
                "INSERT OR REPLACE INTO tmdb_movies VALUES(?,?,?,?,?,?,?,?,?)",
                (key, _text(record.get("imdb_id")), _text(record.get("title")), _text(record.get("year")),
                 _text(record.get("poster_url")), _text(record.get("release_date")), _bool(record.get("adult")),
                 _number(record.get("updated_at")), _json_text(record)),
            )
        elif name == "app_metadata/plex_metadata.json":
            connection.execute(
                "INSERT OR REPLACE INTO plex_files VALUES(?,?,?,?,?,?,?,?,?,?)",
                (key, _text(record.get("path") or key), _text(record.get("plex_title")),
                 _text(record.get("plex_year")), _text(record.get("tmdb_id")), _text(record.get("imdb_id")),
                 _text(record.get("plex_guid")), _text(record.get("rating_key")),
                 _number(record.get("updated_at")), _json_text(record)),
            )
            connection.execute("DELETE FROM media_identity_keys WHERE path_key = ?", (key,))
            self.store._import_media_identity_keys(connection, key)
        elif name == "app_metadata/manual_matches.json":
            connection.execute(
                "INSERT OR REPLACE INTO manual_matches VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (key, _text(record.get("path") or key), _text(record.get("provider")), _text(record.get("source")),
                 _text(record.get("tmdb_id")), _text(record.get("imdb_id")),
                 _text(record.get("plex_guid") or record.get("guid")),
                 _text(record.get("title") or record.get("plex_title")),
                 _text(record.get("year") or record.get("plex_year")), _bool(record.get("accepted")),
                 _number(record.get("updated_at")), _json_text(record)),
            )
            connection.execute("DELETE FROM media_identity_keys WHERE path_key = ?", (key,))
            self.store._import_media_identity_keys(connection, key)
        elif name == "app_metadata/identity_audit_fingerprints.json":
            connection.execute(
                "INSERT OR REPLACE INTO identity_audit_fingerprints VALUES(?,?,?,?,?,?,?)",
                (
                    key,
                    _text(record.get("path") or key),
                    _text(record.get("provider")),
                    _text(record.get("provider_id")),
                    int(_number(record.get("rule_version"))),
                    _number(record.get("verified_at")),
                    _json_text(record),
                ),
            )
        else:
            raise KeyError(f"Document does not support row upserts: {name}")

    def delete_records(self, name, keys):
        name = str(name).replace("\\", "/")
        keys = [str(key) for key in keys]
        if not keys:
            return 0
        table_map = {
            "app_metadata/files.json": ("media_files", "path_key"),
            "app_metadata/plex_metadata.json": ("plex_files", "path_key"),
            "app_metadata/manual_matches.json": ("manual_matches", "path_key"),
            "app_metadata/tmdb_metadata.json": ("tmdb_movies", "tmdb_id"),
            "app_metadata/identity_audit_fingerprints.json": (
                "identity_audit_fingerprints",
                "path_key",
            ),
        }
        if name not in table_map:
            raise KeyError(f"Document does not support row deletion: {name}")
        table, key_column = table_map[name]
        placeholders = ",".join("?" for _ in keys)
        with self._lock, self.store.transaction() as connection:
            cursor = connection.execute(
                f"DELETE FROM {table} WHERE {key_column} IN ({placeholders})", keys
            )
            if name == "app_metadata/files.json":
                connection.execute(
                    f"DELETE FROM playback_history WHERE path_key IN ({placeholders})",
                    keys,
                )
            if name in {"app_metadata/plex_metadata.json", "app_metadata/manual_matches.json"}:
                for key in keys:
                    connection.execute("DELETE FROM media_identity_keys WHERE path_key = ?", (key,))
                    self.store._import_media_identity_keys(connection, key)
            self.store.canonical.sync_changes(connection, name, keys)
            if name in {
                "app_metadata/plex_metadata.json",
                "app_metadata/manual_matches.json",
                "app_metadata/tmdb_metadata.json",
            }:
                self._sync_playback_movie_keys(
                    connection,
                    None if name == "app_metadata/tmdb_metadata.json" else keys,
                )
            self._bump_generation(connection, (name,))
            self._cache.pop(name, None)
            changed = cursor.rowcount
        self.schedule_export(name)
        return changed

    def migrate_path_records(self, old_key, new_key, new_path, file_patch=None):
        old_key, new_key = str(old_key), str(new_key)
        core = (
            ("app_metadata/files.json", "media_files"),
            ("app_metadata/plex_metadata.json", "plex_files"),
            ("app_metadata/manual_matches.json", "manual_matches"),
            ("app_metadata/identity_audit_fingerprints.json", "identity_audit_fingerprints"),
        )
        generic = (
            ("app_metadata/conflicts.json", "conflicts"),
            ("app_metadata/library_inventory.json", "files"),
        )
        changed_documents = set()
        with self._lock, self.store.transaction() as connection:
            records = {}
            for name, table in core:
                row = connection.execute(
                    f"SELECT raw_json FROM {table} WHERE path_key = ?", (old_key,)
                ).fetchone()
                if row:
                    records[name] = json.loads(row[0])
            connection.execute("DELETE FROM media_files WHERE path_key = ?", (old_key,))
            connection.execute("DELETE FROM plex_files WHERE path_key = ?", (old_key,))
            connection.execute("DELETE FROM manual_matches WHERE path_key = ?", (old_key,))
            connection.execute("DELETE FROM identity_audit_fingerprints WHERE path_key = ?", (old_key,))
            for name, record in records.items():
                record = {**record, "path": str(new_path)}
                if name == "app_metadata/files.json" and file_patch:
                    record.update({key: value for key, value in file_patch.items() if key != "_ingestion_retry"})
                self._upsert_record(connection, name, new_key, record)
                changed_documents.add(name)
            for name, root_key in generic:
                document = self._source_document(connection, name, {root_key: {}})
                values = document.setdefault(root_key, {})
                if old_key not in values:
                    continue
                record = dict(values.pop(old_key) or {})
                record["path"] = str(new_path)
                values[new_key] = record
                connection.execute(
                    "INSERT OR REPLACE INTO source_documents(name, payload_json) VALUES(?, ?)",
                    (name, _json_text(document)),
                )
                changed_documents.add(name)
            self.store.canonical.rebuild(connection)
            connection.execute(
                "UPDATE playback_history SET path_key=? WHERE path_key=?",
                (new_key, old_key),
            )
            self._sync_playback_movie_keys(connection, (new_key,))
            self._bump_generation(connection, changed_documents)
            for name in changed_documents:
                self._cache.pop(name, None)
        for name in changed_documents:
            self.schedule_export(name)
        return bool(changed_documents)

    def remove_path_records(self, path_keys):
        path_keys = [str(key) for key in path_keys]
        if not path_keys:
            return 0
        placeholders = ",".join("?" for _ in path_keys)
        generic = (
            ("app_metadata/conflicts.json", "conflicts"),
            ("app_metadata/library_inventory.json", "files"),
        )
        changed_documents = {
            "app_metadata/files.json",
            "app_metadata/plex_metadata.json",
            "app_metadata/manual_matches.json",
            "app_metadata/identity_audit_fingerprints.json",
        }
        with self._lock, self.store.transaction() as connection:
            removed = connection.execute(
                f"DELETE FROM media_files WHERE path_key IN ({placeholders})", path_keys
            ).rowcount
            connection.execute(
                f"DELETE FROM playback_history WHERE path_key IN ({placeholders})",
                path_keys,
            )
            connection.execute(f"DELETE FROM plex_files WHERE path_key IN ({placeholders})", path_keys)
            connection.execute(f"DELETE FROM manual_matches WHERE path_key IN ({placeholders})", path_keys)
            connection.execute(
                f"DELETE FROM identity_audit_fingerprints WHERE path_key IN ({placeholders})",
                path_keys,
            )
            for name, root_key in generic:
                document = self._source_document(connection, name, {root_key: {}})
                values = document.setdefault(root_key, {})
                changed = False
                for key in path_keys:
                    if values.pop(key, None) is not None:
                        changed = True
                if changed:
                    connection.execute(
                        "INSERT OR REPLACE INTO source_documents(name, payload_json) VALUES(?, ?)",
                        (name, _json_text(document)),
                    )
                    changed_documents.add(name)
            self.store.canonical.sync_changes(
                connection,
                "app_metadata/files.json",
                path_keys,
            )
            self._bump_generation(connection, changed_documents)
            for name in changed_documents:
                self._cache.pop(name, None)
        for name in changed_documents:
            self.schedule_export(name)
        return removed

    @staticmethod
    def _sync_playback_movie_keys(connection, path_keys=None):
        path_keys = [str(key) for key in (path_keys or []) if str(key)]
        where = ""
        parameters = ()
        if path_keys:
            placeholders = ",".join("?" for _ in path_keys)
            where = f" WHERE path_key IN ({placeholders})"
            parameters = tuple(path_keys)
        connection.execute(
            """
            UPDATE playback_history
            SET movie_key=(
                SELECT movie_key
                FROM canonical_movie_files
                WHERE canonical_movie_files.path_key=playback_history.path_key
            )
            """ + where,
            parameters,
        )

    def schedule_export(self, name):
        if not self.auto_export:
            return
        flush_now = False
        with self._lock:
            if self._closed:
                raise CatalogError("Catalog repository is closed")
            self._pending_exports.add(str(name).replace("\\", "/"))
            if self.export_delay <= 0:
                flush_now = True
            elif self._export_timer is not None:
                self._export_timer.cancel()
            if not flush_now:
                self._export_timer = threading.Timer(self.export_delay, self.flush_exports)
                self._export_timer.daemon = True
                self._export_timer.start()
        if flush_now:
            self.flush_exports()

    def close(self, flush=True):
        if flush:
            self.flush_exports()
        with self._lock:
            self._closed = True
            if self._export_timer is not None:
                self._export_timer.cancel()
            self._export_timer = None
            if not flush:
                self._pending_exports.clear()

    def flush_exports(self):
        with self._lock:
            if self._export_timer is not None:
                self._export_timer.cancel()
            names = sorted(self._pending_exports)
            self._pending_exports.clear()
            self._export_timer = None
        for name in names:
            self._export_document(name)
        if names:
            with self.store.transaction() as connection:
                connection.execute(
                    "INSERT OR REPLACE INTO catalog_meta(key, value) VALUES('export_dirty', '0')"
                )

    def export_all(self):
        connection = self.store.connect()
        try:
            names = {
                row[0]
                for row in connection.execute("SELECT name FROM source_documents")
                if row[0] not in EXTERNAL_DOCUMENTS
            }
        finally:
            connection.close()
        names.update(CORE_DOCUMENTS)
        with self._lock:
            self._pending_exports.update(names)
        self.flush_exports()
        return sorted(names)

    def verify_exports(self, names=None):
        names = list(names or self.export_all())
        mismatches = []
        for name in names:
            path = self.user_data_dir / Path(name)
            if not path.is_file():
                mismatches.append({"name": name, "reason": "missing"})
                continue
            try:
                exported = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                mismatches.append({"name": name, "reason": "invalid_json"})
                continue
            expected = self.read_document(name, {})
            if exported != expected:
                mismatches.append({"name": name, "reason": "content_mismatch"})
        return {"passed": not mismatches, "documents": len(names), "mismatches": mismatches}

    def _export_document(self, name):
        path = self.user_data_dir / Path(name)
        document = self.read_document(name, {})
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.catalog-export.tmp")
        backup = Path(f"{path}.bak")
        if path.is_file():
            shutil.copy2(path, backup)
        text = json.dumps(document, indent=2, ensure_ascii=True)
        with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            for attempt in range(6):
                try:
                    os.replace(temporary, path)
                    break
                except PermissionError:
                    if attempt == 5:
                        raise
                    time.sleep(0.1 * (attempt + 1))
        finally:
            temporary.unlink(missing_ok=True)
