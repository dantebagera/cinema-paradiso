import json
import os
import threading
from pathlib import Path

from services.catalog_store import CATALOG_SCHEMA_VERSION, CatalogStore


class CatalogReadModel:
    """Temporary JSON-to-SQL bridge used until the catalog owns writes."""

    def __init__(self, database_path):
        self.database_path = Path(database_path).resolve()
        self._lock = threading.RLock()

    @staticmethod
    def _revision_text(revision):
        return json.dumps(revision, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

    def is_current(self, revision):
        if not self.database_path.is_file():
            return False
        store = CatalogStore(self.database_path)
        connection = None
        try:
            connection = store.connect()
            values = dict(connection.execute(
                "SELECT key, value FROM catalog_meta WHERE key IN ('schema_version', 'source_revision')"
            ).fetchall())
            return (
                int(values.get("schema_version", 0)) == CATALOG_SCHEMA_VERSION
                and values.get("source_revision") == self._revision_text(revision)
            )
        except Exception:
            return False
        finally:
            if connection is not None:
                connection.close()

    def ensure_current(self, revision, documents_loader):
        if self.is_current(revision):
            return CatalogStore(self.database_path)
        with self._lock:
            if self.is_current(revision):
                return CatalogStore(self.database_path)
            documents = documents_loader()
            temporary = self.database_path.with_name(f".{self.database_path.name}.building")
            for candidate in (temporary, Path(f"{temporary}-wal"), Path(f"{temporary}-shm")):
                candidate.unlink(missing_ok=True)
            store = CatalogStore(temporary)
            try:
                store.import_documents(documents, {})
                with store.transaction() as connection:
                    connection.execute(
                        "INSERT OR REPLACE INTO catalog_meta(key, value) VALUES('source_revision', ?)",
                        (self._revision_text(revision),),
                    )
                connection = store.connect()
                try:
                    connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                finally:
                    connection.close()
                self.database_path.parent.mkdir(parents=True, exist_ok=True)
                os.replace(temporary, self.database_path)
            finally:
                for suffix in ("-wal", "-shm"):
                    Path(f"{temporary}{suffix}").unlink(missing_ok=True)
                temporary.unlink(missing_ok=True)
            return CatalogStore(self.database_path)
