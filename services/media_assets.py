"""Checksum-addressed local artwork registry for owned and curated movies."""

import hashlib
import io
import json
import os
import shutil
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PIL import Image, UnidentifiedImageError


MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
VALID_ASSET_TYPES = {"poster", "portrait", "discover_poster"}
MIME_EXTENSIONS = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}
FORMAT_MIMES = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp", "GIF": "image/gif"}


class MediaAssetError(RuntimeError):
    pass


def normalize_asset_url(value):
    raw = str(value or "").strip()
    parsed = urllib.parse.urlsplit(raw)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        raise MediaAssetError("Artwork URL must use HTTP or HTTPS")
    return urllib.parse.urlunsplit((
        parsed.scheme.lower(), parsed.netloc.lower(), parsed.path or "/", parsed.query, ""
    ))


def _asset_key(asset_type, provider, source_url):
    seed = f"{asset_type}|{provider}|{source_url}".encode("utf-8")
    return hashlib.sha256(seed).hexdigest()


class MediaAssetService:
    def __init__(self, repository, metadata_root=None, *, open_url=None, soft_limit_bytes=10 * 1024**3):
        self.repository = repository
        default_root = Path(os.environ.get("LOCALAPPDATA") or repository.user_data_dir) / "Cinema Paradiso" / "Metadata"
        self.root = Path(metadata_root or default_root).resolve()
        self.assets_root = self.root / "assets"
        self.temporary_root = self.root / ".tmp"
        self.soft_limit_bytes = int(soft_limit_bytes)
        self.open_url = open_url or urllib.request.urlopen
        self._lock = threading.RLock()
        self._run_lock = threading.Lock()
        self._state = {"status": "idle", "queued": 0, "completed": 0, "failed": 0, "started_at": 0, "updated_at": 0}
        self.assets_root.mkdir(parents=True, exist_ok=True)
        self.temporary_root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _bump_generation(connection):
        connection.execute("""
            INSERT INTO catalog_meta(key, value) VALUES('asset_generation', '1')
            ON CONFLICT(key) DO UPDATE SET value=CAST(value AS INTEGER)+1
        """)

    @staticmethod
    def _ensure_asset(connection, asset_type, provider, source_url, retention_class):
        asset_type = str(asset_type or "").strip()
        if asset_type not in VALID_ASSET_TYPES:
            raise MediaAssetError(f"Unsupported asset type: {asset_type}")
        provider = str(provider or "").strip().lower()
        source_url = normalize_asset_url(source_url)
        key = _asset_key(asset_type, provider, source_url)
        now = time.time()
        connection.execute("""
            INSERT INTO media_assets(
                asset_key, asset_type, provider, source_url, status, retention_class, created_at, updated_at
            ) VALUES(?,?,?,?,?,?,?,?)
            ON CONFLICT(asset_type, provider, source_url) DO UPDATE SET
                retention_class=CASE
                    WHEN media_assets.retention_class='custom' THEN 'custom'
                    WHEN media_assets.retention_class='owned' THEN 'owned'
                    WHEN excluded.retention_class='owned' THEN 'owned'
                    WHEN media_assets.retention_class='saved' THEN 'saved'
                    WHEN excluded.retention_class='saved' THEN 'saved'
                    ELSE media_assets.retention_class
                END,
                updated_at=MAX(media_assets.updated_at, excluded.updated_at)
        """, (key, asset_type, provider, source_url, "queued", retention_class, now, now))
        row = connection.execute(
            "SELECT asset_key FROM media_assets WHERE asset_type=? AND provider=? AND source_url=?",
            (asset_type, provider, source_url),
        ).fetchone()
        return row[0]

    @staticmethod
    def _bind_movie(connection, movie_key, asset_type, asset_key, selected=True):
        current = connection.execute("""
            SELECT ma.asset_key, a.retention_class FROM movie_assets ma
            JOIN media_assets a ON a.asset_key=ma.asset_key
            WHERE ma.movie_key=? AND ma.asset_type=? AND ma.selected=1
        """, (movie_key, asset_type)).fetchone()
        if current and current[1] == "custom" and current[0] != asset_key:
            selected = False
        changed = not current or (selected and current[0] != asset_key)
        if selected:
            connection.execute(
                "UPDATE movie_assets SET selected=0 WHERE movie_key=? AND asset_type=?",
                (movie_key, asset_type),
            )
        connection.execute("""
            INSERT INTO movie_assets(movie_key, asset_type, asset_key, selected) VALUES(?,?,?,?)
            ON CONFLICT(movie_key, asset_type, asset_key) DO UPDATE SET selected=excluded.selected
        """, (movie_key, asset_type, asset_key, 1 if selected else 0))
        return changed

    @staticmethod
    def _bind_person(connection, person_key, asset_type, asset_key, selected=True):
        current = connection.execute(
            "SELECT asset_key FROM person_assets WHERE person_key=? AND asset_type=? AND selected=1",
            (person_key, asset_type),
        ).fetchone()
        changed = not current or (selected and current[0] != asset_key)
        if selected:
            connection.execute(
                "UPDATE person_assets SET selected=0 WHERE person_key=? AND asset_type=?",
                (person_key, asset_type),
            )
        connection.execute("""
            INSERT INTO person_assets(person_key, asset_type, asset_key, selected) VALUES(?,?,?,?)
            ON CONFLICT(person_key, asset_type, asset_key) DO UPDATE SET selected=excluded.selected
        """, (person_key, asset_type, asset_key, 1 if selected else 0))
        return changed

    def queue_movie(self, movie_key, asset_type, provider, source_url, *, retention_class="owned", selected=True):
        with self._lock, self.repository.store.transaction() as connection:
            key = self._ensure_asset(connection, asset_type, provider, source_url, retention_class)
            if self._bind_movie(connection, movie_key, asset_type, key, selected=selected):
                self._bump_generation(connection)
            return key

    def queue_person(self, person_key, provider, source_url, *, retention_class="owned", selected=True):
        with self._lock, self.repository.store.transaction() as connection:
            key = self._ensure_asset(connection, "portrait", provider, source_url, retention_class)
            if self._bind_person(connection, person_key, "portrait", key, selected=selected):
                self._bump_generation(connection)
            return key

    def queue_curated(self, identity_key, source_url, *, provider="tmdb", retention_class="saved"):
        with self._lock, self.repository.store.transaction() as connection:
            key = self._ensure_asset(connection, "poster", provider, source_url, retention_class)
            before = connection.total_changes
            connection.execute(
                "INSERT OR IGNORE INTO curated_asset_refs(curated_identity_key,asset_type,asset_key) VALUES(?,?,?)",
                (str(identity_key), "poster", key),
            )
            if connection.total_changes != before:
                self._bump_generation(connection)
            return key

    @staticmethod
    def _validate_image(payload, content_type=""):
        if not payload or len(payload) > MAX_IMAGE_BYTES:
            raise MediaAssetError("Artwork payload is empty or larger than 20 MB")
        try:
            with Image.open(io.BytesIO(payload)) as image:
                image.verify()
            with Image.open(io.BytesIO(payload)) as image:
                width, height = image.size
                image_format = str(image.format or "").upper()
                image.load()
        except (UnidentifiedImageError, OSError, ValueError) as error:
            raise MediaAssetError("Artwork payload is not a complete decodable image") from error
        if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
            raise MediaAssetError("Artwork dimensions are invalid or too large")
        mime_type = FORMAT_MIMES.get(image_format, "")
        declared = str(content_type or "").split(";", 1)[0].strip().lower()
        if not mime_type or declared and (not declared.startswith("image/") or declared != mime_type):
            raise MediaAssetError("Artwork MIME type does not match decoded image")
        return mime_type, int(width), int(height)

    def _final_path(self, checksum, mime_type):
        extension = MIME_EXTENSIONS[mime_type]
        return self.assets_root / checksum[:2] / f"{checksum}{extension}"

    def _mark_failed(self, asset_key, error):
        with self.repository.store.transaction() as connection:
            connection.execute("""
                UPDATE media_assets SET status='failed', last_error=?, updated_at=? WHERE asset_key=?
            """, (str(error)[:1000], time.time(), asset_key))

    def download(self, asset_key):
        connection = self.repository.store.connect()
        try:
            row = connection.execute("SELECT * FROM media_assets WHERE asset_key=?", (asset_key,)).fetchone()
        finally:
            connection.close()
        if not row:
            raise MediaAssetError("Unknown artwork asset")
        asset = dict(row)
        if asset["status"] == "ready" and asset["local_path"] and Path(asset["local_path"]).is_file():
            return asset
        with self.repository.store.transaction() as connection:
            connection.execute("""
                UPDATE media_assets SET status='downloading', attempt_count=attempt_count+1,
                    last_error='', updated_at=? WHERE asset_key=?
            """, (time.time(), asset_key))
        temporary = None
        try:
            request = urllib.request.Request(asset["source_url"], headers={"Accept": "image/*", "User-Agent": "Cinema-Paradiso/1"})
            with self.open_url(request, timeout=20) as response:
                content_type = response.headers.get("Content-Type", "")
                payload = response.read(MAX_IMAGE_BYTES + 1)
            mime_type, width, height = self._validate_image(payload, content_type)
            checksum = hashlib.sha256(payload).hexdigest()
            final_path = self._final_path(checksum, mime_type)
            final_path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary_name = tempfile.mkstemp(prefix="asset-", suffix=".part", dir=self.temporary_root)
            temporary = Path(temporary_name)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            if final_path.exists():
                temporary.unlink()
            else:
                os.replace(temporary, final_path)
            now = time.time()
            with self.repository.store.transaction() as connection:
                selected = connection.execute("""
                    SELECT 1 FROM movie_assets WHERE asset_key=? AND selected=1
                    UNION ALL SELECT 1 FROM person_assets WHERE asset_key=? AND selected=1 LIMIT 1
                """, (asset_key, asset_key)).fetchone()
                connection.execute("""
                    UPDATE media_assets SET local_path=?, checksum=?, mime_type=?, byte_size=?,
                        width=?, height=?, status='ready', last_error='', downloaded_at=?,
                        last_verified_at=?, last_accessed_at=?, updated_at=? WHERE asset_key=?
                """, (str(final_path), checksum, mime_type, len(payload), width, height,
                      now, now, now, now, asset_key))
                if selected:
                    self._bump_generation(connection)
            return self.lookup(asset_key=asset_key)
        except Exception as error:
            if temporary and temporary.exists():
                temporary.unlink()
            self._mark_failed(asset_key, error)
            if isinstance(error, MediaAssetError):
                raise
            raise MediaAssetError(str(error)) from error

    def lookup(self, *, asset_key="", checksum=""):
        connection = self.repository.store.connect()
        try:
            row = connection.execute(
                "SELECT * FROM media_assets WHERE asset_key=?" if asset_key else
                "SELECT * FROM media_assets WHERE checksum=? AND status='ready' ORDER BY retention_class='custom' DESC LIMIT 1",
                (asset_key or checksum,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            connection.close()

    def queue_owned_artwork(self, batch_size=500):
        connection = self.repository.store.connect()
        try:
            movie_rows = [dict(row) for row in connection.execute(
                "SELECT cmf.path_key, cm.movie_key FROM canonical_movie_files cmf "
                "JOIN canonical_movies cm ON cm.movie_key=cmf.movie_key ORDER BY cmf.path_key"
            ).fetchall()]
            people_rows = [dict(row) for row in connection.execute(
                "SELECT person_key, provider, profile_url FROM people WHERE profile_url<>'' ORDER BY person_key"
            ).fetchall()]
            curated_rows = [dict(row) for row in connection.execute("""
                SELECT COALESCE(NULLIF(identity_key,''),
                           CASE WHEN tmdb_id<>'' THEN 'tmdb:'||tmdb_id
                                WHEN imdb_id<>'' THEN 'imdb:'||LOWER(imdb_id)
                                WHEN path<>'' THEN 'path:'||LOWER(path)
                                ELSE 'list:'||list_id||':'||position END) AS identity_key,
                       poster_url
                FROM list_items WHERE poster_url<>'' ORDER BY list_id, position
            """).fetchall()]
            projections = {}
            for offset in range(0, len(movie_rows), batch_size):
                keys = [row["path_key"] for row in movie_rows[offset:offset + batch_size]]
                projections.update(self.repository.store.canonical.project_paths(connection, keys, include_details=False))
        finally:
            connection.close()
        queued = 0
        movie_by_path = {row["path_key"]: row["movie_key"] for row in movie_rows}
        operations = []
        for path_key, projection in projections.items():
            url = str(projection.get("poster_url") or "")
            if url.startswith("http://") or url.startswith("https://"):
                operations.append(("movie", movie_by_path[path_key], projection.get("selected_provider") or "provider", url, "owned"))
        operations.extend(("person", row["person_key"], row["provider"] or "provider", row["profile_url"], "owned") for row in people_rows)
        operations.extend(("curated", row["identity_key"], "tmdb", row["poster_url"], "saved") for row in curated_rows)
        for offset in range(0, len(operations), batch_size):
            changed = False
            with self._lock, self.repository.store.transaction() as connection:
                for kind, owner_key, provider, url, retention_class in operations[offset:offset + batch_size]:
                    try:
                        key = self._ensure_asset(
                            connection, "poster" if kind in {"movie", "curated"} else "portrait",
                            provider, url, retention_class,
                        )
                    except MediaAssetError:
                        continue
                    if kind == "movie":
                        changed = self._bind_movie(connection, owner_key, "poster", key, selected=True) or changed
                    elif kind == "person":
                        changed = self._bind_person(connection, owner_key, "portrait", key, selected=True) or changed
                    else:
                        before = connection.total_changes
                        connection.execute(
                            "INSERT OR IGNORE INTO curated_asset_refs(curated_identity_key,asset_type,asset_key) VALUES(?,?,?)",
                            (owner_key, "poster", key),
                        )
                        changed = connection.total_changes != before or changed
                    queued += 1
                if changed:
                    self._bump_generation(connection)
        return queued

    def run_backfill(self, *, limit=100, workers=4, max_attempts=4):
        if not self._run_lock.acquire(blocking=False):
            return self.status()
        try:
            connection = self.repository.store.connect()
            try:
                rows = connection.execute("""
                    SELECT asset_key FROM media_assets
                    WHERE attempt_count<? AND (
                        status='queued' OR (
                            status='failed' AND updated_at <= ? - CASE attempt_count
                                WHEN 1 THEN 30 WHEN 2 THEN 120 ELSE 600 END
                        )
                    )
                    ORDER BY CASE retention_class WHEN 'custom' THEN 0 WHEN 'owned' THEN 1 WHEN 'saved' THEN 2 ELSE 3 END,
                             updated_at, asset_key LIMIT ?
                """, (int(max_attempts), time.time(), max(1, int(limit)))).fetchall()
            finally:
                connection.close()
            keys = [row[0] for row in rows]
            self._state.update({"status": "running", "queued": len(keys), "completed": 0, "failed": 0,
                                "started_at": time.time(), "updated_at": time.time()})
            with ThreadPoolExecutor(max_workers=max(1, min(int(workers), 8))) as executor:
                futures = {executor.submit(self.download, key): key for key in keys}
                for future in as_completed(futures):
                    try:
                        future.result()
                        self._state["completed"] += 1
                    except Exception:
                        self._state["failed"] += 1
                    self._state["updated_at"] = time.time()
            self._state["status"] = "completed"
            return self.status()
        finally:
            self._run_lock.release()

    def status(self):
        connection = self.repository.store.connect()
        try:
            counts = {row[0]: int(row[1]) for row in connection.execute(
                "SELECT status, COUNT(*) FROM media_assets GROUP BY status"
            ).fetchall()}
            row = connection.execute("""
                SELECT COUNT(*), COUNT(DISTINCT checksum), COALESCE(SUM(byte_size),0),
                       SUM(CASE WHEN retention_class='custom' THEN 1 ELSE 0 END)
                FROM media_assets WHERE status='ready'
            """).fetchone()
            generation = int(connection.execute(
                "SELECT value FROM catalog_meta WHERE key='asset_generation'"
            ).fetchone()[0])
            logical_references = int(connection.execute("""
                SELECT (SELECT COUNT(*) FROM movie_assets)
                     + (SELECT COUNT(*) FROM person_assets)
                     + (SELECT COUNT(*) FROM curated_asset_refs)
            """).fetchone()[0])
            referenced_assets = int(connection.execute("""
                SELECT COUNT(DISTINCT asset_key) FROM (
                    SELECT asset_key FROM movie_assets
                    UNION ALL SELECT asset_key FROM person_assets
                    UNION ALL SELECT asset_key FROM curated_asset_refs
                )
            """).fetchone()[0])
        finally:
            connection.close()
        return {
            **self._state, "counts": counts, "asset_generation": generation,
            "ready_assets": int(row[0]), "unique_checksums": int(row[1]),
            "logical_bytes": int(row[2]), "custom_assets": int(row[3] or 0),
            "logical_references": logical_references,
            "referenced_assets": referenced_assets,
            "relationship_deduplications": max(0, logical_references - referenced_assets),
            "checksum_deduplications": max(0, int(row[0]) - int(row[1])),
            "physical_bytes": sum(path.stat().st_size for path in self.assets_root.rglob("*") if path.is_file()),
        }

    def cleanup_temporary(self, *, grace_seconds=7 * 86400):
        cutoff = time.time() - max(0, int(grace_seconds))
        removed = []
        with self._lock, self.repository.store.transaction() as connection:
            rows = connection.execute("""
                SELECT a.* FROM media_assets a
                WHERE a.retention_class='temporary' AND a.status='ready' AND a.updated_at<?
                  AND NOT EXISTS(SELECT 1 FROM movie_assets ma WHERE ma.asset_key=a.asset_key)
                  AND NOT EXISTS(SELECT 1 FROM person_assets pa WHERE pa.asset_key=a.asset_key)
                  AND NOT EXISTS(SELECT 1 FROM curated_asset_refs cr WHERE cr.asset_key=a.asset_key)
                ORDER BY a.last_accessed_at, a.updated_at
            """, (cutoff,)).fetchall()
            physical = sum(path.stat().st_size for path in self.assets_root.rglob("*") if path.is_file())
            for row in rows:
                if physical <= self.soft_limit_bytes:
                    break
                path = Path(row["local_path"])
                shared = connection.execute(
                    "SELECT 1 FROM media_assets WHERE local_path=? AND asset_key<>? AND status='ready' LIMIT 1",
                    (str(path), row["asset_key"]),
                ).fetchone()
                connection.execute("DELETE FROM media_assets WHERE asset_key=?", (row["asset_key"],))
                if not shared and path.is_file():
                    size = path.stat().st_size
                    path.unlink()
                    physical -= size
                removed.append(row["asset_key"])
            if removed:
                self._bump_generation(connection)
        return {"removed": len(removed), "asset_keys": removed}

    def ingest_custom_file(self, movie_key, source_path, *, source_name="custom"):
        source_path = Path(source_path).resolve()
        payload = source_path.read_bytes()
        mime_type, width, height = self._validate_image(payload)
        checksum = hashlib.sha256(payload).hexdigest()
        final_path = self._final_path(checksum, mime_type)
        final_path.parent.mkdir(parents=True, exist_ok=True)
        if not final_path.exists():
            temporary = self.temporary_root / f"custom-{checksum}.part"
            temporary.write_bytes(payload)
            os.replace(temporary, final_path)
        source_url = f"https://local.invalid/custom/{urllib.parse.quote(source_name)}/{checksum}"
        key = _asset_key("poster", "custom", source_url)
        now = time.time()
        with self._lock, self.repository.store.transaction() as connection:
            existing = connection.execute("""
                SELECT a.* FROM media_assets a
                JOIN movie_assets ma ON ma.asset_key=a.asset_key
                WHERE a.asset_key=? AND ma.movie_key=? AND ma.asset_type='poster'
                  AND ma.selected=1 AND a.status='ready' AND a.checksum=?
            """, (key, movie_key, checksum)).fetchone()
            if existing and Path(existing["local_path"]).is_file():
                return dict(existing)
            connection.execute("""
                INSERT OR REPLACE INTO media_assets(
                    asset_key,asset_type,provider,source_url,local_path,checksum,mime_type,byte_size,
                    width,height,status,attempt_count,last_error,downloaded_at,last_verified_at,last_accessed_at,
                    retention_class,created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (key, "poster", "custom", source_url, str(final_path), checksum, mime_type, len(payload),
                  width, height, "ready", 1, "", now, now, now, "custom", now, now))
            self._bind_movie(connection, movie_key, "poster", key, selected=True)
            self._bump_generation(connection)
        return self.lookup(asset_key=key)

    def migrate_custom_posters(self, legacy_directory):
        legacy_directory = Path(legacy_directory).resolve()
        if not legacy_directory.is_dir():
            return {"found": 0, "migrated": 0, "failed": 0}
        connection = self.repository.store.connect()
        try:
            rows = [dict(row) for row in connection.execute("""
                SELECT mo.override_id, mo.poster_url, mk.identity_key
                FROM movie_overrides mo
                JOIN movie_override_identity_keys mk ON mk.override_id=mo.override_id
                WHERE mo.override_type='poster' AND mo.poster_url<>''
                ORDER BY mo.override_id
            """).fetchall()]
            movies = [dict(row) for row in connection.execute(
                "SELECT movie_key,tmdb_id,imdb_id,plex_guid FROM canonical_movies"
            ).fetchall()]
            path_movies = {row[0]: row[1] for row in connection.execute("""
                SELECT mik.identity_key, cmf.movie_key FROM media_identity_keys mik
                JOIN canonical_movie_files cmf ON cmf.path_key=mik.path_key
            """).fetchall()}
        finally:
            connection.close()
        movies_by_identity = {}
        for movie in movies:
            movies_by_identity[movie["movie_key"]] = movie["movie_key"]
            if movie["tmdb_id"]: movies_by_identity[f"tmdb:{movie['tmdb_id']}"] = movie["movie_key"]
            if movie["imdb_id"]: movies_by_identity[f"imdb:{movie['imdb_id'].lower()}"] = movie["movie_key"]
            if movie["plex_guid"]: movies_by_identity[f"plex:{movie['plex_guid'].lower()}"] = movie["movie_key"]
        movies_by_identity.update(path_movies)
        grouped = {}
        for row in rows:
            grouped.setdefault((row["override_id"], row["poster_url"]), []).append(row["identity_key"])
        result = {"found": len(grouped), "migrated": 0, "failed": 0}
        for (override_id, poster_url), keys in grouped.items():
            movie_key = next((movies_by_identity.get(key) for key in keys if movies_by_identity.get(key)), "")
            filename = Path(urllib.parse.unquote(urllib.parse.urlsplit(poster_url).path)).name
            source_path = (legacy_directory / filename).resolve()
            try:
                source_path.relative_to(legacy_directory)
                if not movie_key or not source_path.is_file():
                    raise MediaAssetError("Custom poster owner or file is missing")
                self.ingest_custom_file(movie_key, source_path, source_name=override_id)
                result["migrated"] += 1
            except (OSError, ValueError, MediaAssetError):
                result["failed"] += 1
        return result

    def reset_custom_poster(self, movie_key):
        with self._lock, self.repository.store.transaction() as connection:
            custom = connection.execute("""
                SELECT ma.asset_key FROM movie_assets ma JOIN media_assets a ON a.asset_key=ma.asset_key
                WHERE ma.movie_key=? AND ma.asset_type='poster' AND ma.selected=1
                  AND a.retention_class='custom'
            """, (movie_key,)).fetchone()
            if not custom:
                return False
            connection.execute(
                "UPDATE movie_assets SET selected=0 WHERE movie_key=? AND asset_type='poster'",
                (movie_key,),
            )
            fallback = connection.execute("""
                SELECT ma.asset_key FROM movie_assets ma JOIN media_assets a ON a.asset_key=ma.asset_key
                WHERE ma.movie_key=? AND ma.asset_type='poster' AND a.retention_class<>'custom'
                ORDER BY a.status='ready' DESC, a.updated_at DESC LIMIT 1
            """, (movie_key,)).fetchone()
            if fallback:
                connection.execute(
                    "UPDATE movie_assets SET selected=1 WHERE movie_key=? AND asset_type='poster' AND asset_key=?",
                    (movie_key, fallback[0]),
                )
            self._bump_generation(connection)
            return True
