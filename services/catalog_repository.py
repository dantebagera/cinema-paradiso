import hashlib
import json
import os
import shutil
import threading
import time
import uuid
from pathlib import Path

from services.catalog_store import CatalogError, CatalogStore, _bool, _json_text, _number, _text


CORE_DOCUMENTS = {
    "app_metadata/files.json",
    "app_metadata/tmdb_metadata.json",
    "app_metadata/plex_metadata.json",
    "app_metadata/manual_matches.json",
    "user_lists.json",
    "user_collections.json",
    "followed_releases.json",
}
EXTERNAL_DOCUMENTS = {"qbittorrent/jobs.json"}


def catalog_database_path(user_data_dir, local_app_data=None):
    user_data_dir = Path(user_data_dir).resolve()
    root = Path(local_app_data or os.environ.get("LOCALAPPDATA") or (Path.home() / ".cinema-paradiso"))
    key = hashlib.blake2b(str(user_data_dir).encode("utf-8", errors="surrogatepass"), digest_size=8).hexdigest()
    return (root / "Cinema Paradiso" / "Catalog" / f"catalog-read-{key}.sqlite").resolve()


class CatalogRepository:
    """SQLite write authority with JSON files maintained as compatibility exports."""

    def __init__(self, user_data_dir, database_path=None, export_delay=0.5):
        self.user_data_dir = Path(user_data_dir).resolve()
        self.store = CatalogStore(database_path or catalog_database_path(self.user_data_dir))
        self.export_delay = float(export_delay)
        self._lock = threading.RLock()
        self._cache = {}
        self._pending_exports = set()
        self._export_timer = None
        self.store.initialize()

    @property
    def database_path(self):
        return self.store.database_path

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
        jobs = self.user_data_dir / "qbittorrent" / "jobs.json"
        if jobs.is_file():
            documents["qbittorrent/jobs.json"] = self._load_bootstrap_document(jobs)
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

    def generation(self):
        connection = self.store.connect()
        try:
            row = connection.execute("SELECT value FROM catalog_meta WHERE key='generation'").fetchone()
            return int(row[0]) if row else 0
        finally:
            connection.close()

    @staticmethod
    def _bump_generation(connection):
        connection.execute("""
            INSERT INTO catalog_meta(key, value) VALUES('generation', '1')
            ON CONFLICT(key) DO UPDATE SET value = CAST(value AS INTEGER) + 1
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
            "user_collections.json": ("overrides", "collection_overrides", "collection_id"),
            "qbittorrent/jobs.json": ("jobs", "download_jobs", "torrent_hash"),
        }
        if name in table_specs:
            root_key, table, key_column = table_specs[name]
            rows = connection.execute(f"SELECT {key_column}, raw_json FROM {table}").fetchall()
            document[root_key] = {str(row[0]): json.loads(row[1]) for row in rows}
        elif name == "user_lists.json":
            rows = connection.execute("SELECT raw_json FROM user_lists ORDER BY created_at, list_id").fetchall()
            document["lists"] = [json.loads(row[0]) for row in rows]
        elif name == "followed_releases.json":
            rows = connection.execute("SELECT raw_json FROM followed_releases ORDER BY position").fetchall()
            document["movies"] = [json.loads(row[0]) for row in rows]
        return document

    def replace_document(self, name, document):
        name = str(name).replace("\\", "/")
        document = json.loads(json.dumps(document))
        with self._lock, self.store.transaction() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO source_documents(name, payload_json) VALUES(?, ?)",
                (name, _json_text(document)),
            )
            self._replace_normalized_document(connection, name, document)
            self._bump_generation(connection)
            self._cache.pop(name, None)
        self.schedule_export(name)

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
        elif name == "qbittorrent/jobs.json":
            connection.execute("DELETE FROM download_jobs")
            self.store._import_download_jobs(connection, document)

    def upsert_record(self, name, key, record):
        return self.upsert_records(name, {str(key): record})[str(key)]

    def get_record(self, name, key, fallback=None):
        name = str(name).replace("\\", "/")
        key = str(key)
        table_map = {
            "app_metadata/files.json": ("media_files", "path_key"),
            "app_metadata/tmdb_metadata.json": ("tmdb_movies", "tmdb_id"),
            "app_metadata/plex_metadata.json": ("plex_files", "path_key"),
            "app_metadata/manual_matches.json": ("manual_matches", "path_key"),
        }
        if name not in table_map:
            raise KeyError(f"Document does not support row reads: {name}")
        table, key_column = table_map[name]
        connection = self.store.connect()
        try:
            row = connection.execute(
                f"SELECT raw_json FROM {table} WHERE {key_column} = ?", (key,)
            ).fetchone()
            return json.loads(row[0]) if row else json.loads(json.dumps(fallback or {}))
        finally:
            connection.close()

    def upsert_records(self, name, records):
        name = str(name).replace("\\", "/")
        records = {str(key): json.loads(json.dumps(record or {})) for key, record in dict(records or {}).items()}
        if not records:
            return {}
        with self._lock, self.store.transaction() as connection:
            for key, record in records.items():
                self._upsert_record(connection, name, key, record)
            self._bump_generation(connection)
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
        }
        if name not in table_map:
            raise KeyError(f"Document does not support row deletion: {name}")
        table, key_column = table_map[name]
        placeholders = ",".join("?" for _ in keys)
        with self._lock, self.store.transaction() as connection:
            cursor = connection.execute(
                f"DELETE FROM {table} WHERE {key_column} IN ({placeholders})", keys
            )
            if name in {"app_metadata/plex_metadata.json", "app_metadata/manual_matches.json"}:
                for key in keys:
                    connection.execute("DELETE FROM media_identity_keys WHERE path_key = ?", (key,))
                    self.store._import_media_identity_keys(connection, key)
            self._bump_generation(connection)
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
        )
        generic = (
            ("app_metadata/conflicts.json", "conflicts"),
            ("app_metadata/library_inventory.json", "files"),
            ("app_metadata/identity_audit_fingerprints.json", "files"),
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
            for name, record in records.items():
                record = {**record, "path": str(new_path)}
                if name == "app_metadata/files.json" and file_patch:
                    record.update(file_patch)
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
            self._bump_generation(connection)
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
            ("app_metadata/identity_audit_fingerprints.json", "files"),
        )
        changed_documents = {
            "app_metadata/files.json",
            "app_metadata/plex_metadata.json",
            "app_metadata/manual_matches.json",
        }
        with self._lock, self.store.transaction() as connection:
            removed = connection.execute(
                f"DELETE FROM media_files WHERE path_key IN ({placeholders})", path_keys
            ).rowcount
            connection.execute(f"DELETE FROM plex_files WHERE path_key IN ({placeholders})", path_keys)
            connection.execute(f"DELETE FROM manual_matches WHERE path_key IN ({placeholders})", path_keys)
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
            self._bump_generation(connection)
            for name in changed_documents:
                self._cache.pop(name, None)
        for name in changed_documents:
            self.schedule_export(name)
        return removed

    def schedule_export(self, name):
        flush_now = False
        with self._lock:
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
