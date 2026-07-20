import json
import re
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path


KINDS = {"live", "movie", "series"}
TRAILING_YEAR_RE = re.compile(r"\(\s*(19\d{2}|20\d{2}|21\d{2})\s*\)\s*$")


def _text(value):
    return str(value or "").strip()


def _integer(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class IPTVStore:
    def __init__(self, database_path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self):
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @contextmanager
    def _connection(self):
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self):
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS categories (
                    kind TEXT NOT NULL,
                    category_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    item_count INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (kind, category_id)
                );
                CREATE TABLE IF NOT EXISTS items (
                    kind TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    category_id TEXT NOT NULL DEFAULT '',
                    name TEXT NOT NULL,
                    sort_name TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    channel_num INTEGER,
                    image_url TEXT NOT NULL DEFAULT '',
                    backdrop_url TEXT NOT NULL DEFAULT '',
                    container_extension TEXT NOT NULL DEFAULT '',
                    tmdb_id TEXT NOT NULL DEFAULT '',
                    year TEXT NOT NULL DEFAULT '',
                    rating REAL,
                    plot TEXT NOT NULL DEFAULT '',
                    cast_names TEXT NOT NULL DEFAULT '',
                    director TEXT NOT NULL DEFAULT '',
                    genre TEXT NOT NULL DEFAULT '',
                    duration TEXT NOT NULL DEFAULT '',
                    epg_channel_id TEXT NOT NULL DEFAULT '',
                    added TEXT NOT NULL DEFAULT '',
                    raw_json TEXT NOT NULL DEFAULT '{}',
                    PRIMARY KEY (kind, item_id)
                );
                CREATE INDEX IF NOT EXISTS idx_iptv_items_category ON items(kind, category_id, position);
                CREATE INDEX IF NOT EXISTS idx_iptv_items_name ON items(kind, sort_name);
                CREATE TABLE IF NOT EXISTS details (
                    kind TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    fetched_at REAL NOT NULL,
                    PRIMARY KEY (kind, item_id)
                );
                CREATE TABLE IF NOT EXISTS iptv_lists (
                    list_id TEXT PRIMARY KEY,
                    provider_key TEXT NOT NULL,
                    name TEXT NOT NULL,
                    system_type TEXT NOT NULL DEFAULT '',
                    position INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_iptv_lists_provider ON iptv_lists(provider_key, position, created_at);
                CREATE UNIQUE INDEX IF NOT EXISTS idx_iptv_lists_system
                    ON iptv_lists(provider_key, system_type) WHERE system_type <> '';
                CREATE TABLE IF NOT EXISTS iptv_list_items (
                    list_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    added_at REAL NOT NULL,
                    snapshot_json TEXT NOT NULL DEFAULT '{}',
                    PRIMARY KEY (list_id, kind, item_id),
                    FOREIGN KEY (list_id) REFERENCES iptv_lists(list_id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_iptv_list_items_order ON iptv_list_items(list_id, position);
                CREATE TABLE IF NOT EXISTS watch_history (
                    kind TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    position_seconds REAL NOT NULL DEFAULT 0,
                    duration_seconds REAL NOT NULL DEFAULT 0,
                    completed INTEGER NOT NULL DEFAULT 0,
                    last_watched REAL NOT NULL,
                    PRIMARY KEY (kind, item_id)
                );
                CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "favorites" in tables and "legacy_favorites" not in tables:
                connection.execute("ALTER TABLE favorites RENAME TO legacy_favorites")

    @staticmethod
    def _category_rows(kind, rows):
        result = []
        for position, row in enumerate(rows or []):
            if not isinstance(row, dict):
                continue
            category_id = _text(row.get("category_id"))
            if category_id:
                result.append((kind, category_id, _text(row.get("category_name")) or "Untitled", position, 0))
        return result

    @staticmethod
    def _item_row(kind, row, position):
        if not isinstance(row, dict):
            return None
        item_key = "series_id" if kind == "series" else "stream_id"
        item_id = _text(row.get(item_key))
        if not item_id:
            return None
        name = _text(row.get("name")) or "Untitled"
        year = _text(row.get("year") or row.get("releaseDate") or row.get("release_date"))[:4]
        if not year:
            year_match = TRAILING_YEAR_RE.search(name)
            year = year_match.group(1) if year_match else ""
        image_url = _text(row.get("cover" if kind == "series" else "stream_icon"))
        backdrops = row.get("backdrop_path") or row.get("backdrop") or []
        if isinstance(backdrops, list):
            backdrop_url = _text(backdrops[0] if backdrops else "")
        else:
            backdrop_url = _text(backdrops)
        return (
            kind,
            item_id,
            _text(row.get("category_id")),
            name,
            name.casefold(),
            position,
            _integer(row.get("num")),
            image_url,
            backdrop_url,
            _text(row.get("container_extension")),
            _text(row.get("tmdb") or row.get("tmdb_id")),
            year,
            _number(row.get("rating") or row.get("rating_5based")),
            _text(row.get("plot")),
            _text(row.get("cast")),
            _text(row.get("director")),
            _text(row.get("genre")),
            _text(row.get("duration")),
            _text(row.get("epg_channel_id")),
            _text(row.get("added") or row.get("last_modified")),
            json.dumps(row, ensure_ascii=False, separators=(",", ":")),
        )

    def replace_catalog(self, catalog):
        category_rows = []
        item_rows = []
        for kind in KINDS:
            category_rows.extend(self._category_rows(kind, catalog.get(kind, {}).get("categories", [])))
            for position, row in enumerate(catalog.get(kind, {}).get("items", [])):
                item = self._item_row(kind, row, position)
                if item:
                    item_rows.append(item)
        with self._lock, self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("DELETE FROM categories")
            connection.execute("DELETE FROM items")
            connection.executemany(
                "INSERT INTO categories(kind, category_id, name, position, item_count) VALUES (?, ?, ?, ?, ?)",
                category_rows,
            )
            connection.executemany(
                """INSERT INTO items(
                    kind, item_id, category_id, name, sort_name, position, channel_num,
                    image_url, backdrop_url, container_extension, tmdb_id, year, rating,
                    plot, cast_names, director, genre, duration, epg_channel_id, added, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                item_rows,
            )
            connection.execute(
                """UPDATE categories SET item_count = (
                    SELECT COUNT(*) FROM items
                    WHERE items.kind = categories.kind AND items.category_id = categories.category_id
                )"""
            )
            connection.execute("DELETE FROM details")
            now = str(time.time())
            connection.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('last_sync', ?)", (now,))
            connection.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('generation', COALESCE((SELECT CAST(value AS INTEGER) + 1 FROM meta WHERE key='generation'), 1))")
        return self.counts()

    def counts(self):
        with self._connection() as connection:
            rows = connection.execute("SELECT kind, COUNT(*) AS count FROM items GROUP BY kind").fetchall()
            result = {kind: 0 for kind in KINDS}
            result.update({row["kind"]: row["count"] for row in rows})
            return result

    def status(self):
        with self._connection() as connection:
            meta = {row["key"]: row["value"] for row in connection.execute("SELECT key, value FROM meta")}
        return {"counts": self.counts(), "last_sync": float(meta.get("last_sync", 0) or 0), "generation": int(meta.get("generation", 0) or 0)}

    def categories(self, kind):
        if kind not in KINDS:
            raise ValueError("Unsupported IPTV category kind")
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT category_id, name, position, item_count FROM categories WHERE kind=? ORDER BY position",
                (kind,),
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _provider_key(value):
        return _text(value) or "default"

    @staticmethod
    def _snapshot(row, kind="", item_id=""):
        source = dict(row) if row is not None else {}
        keys = (
            "kind", "item_id", "category_id", "name", "channel_num", "image_url", "backdrop_url",
            "container_extension", "tmdb_id", "year", "rating", "plot", "cast_names", "director",
            "genre", "duration", "epg_channel_id", "added",
        )
        snapshot = {key: source.get(key) for key in keys if source.get(key) not in (None, "")}
        snapshot["kind"] = _text(snapshot.get("kind") or kind)
        snapshot["item_id"] = _text(snapshot.get("item_id") or item_id)
        snapshot["name"] = _text(snapshot.get("name")) or "Untitled"
        return snapshot

    def _ensure_favorites_list(self, connection, provider_key):
        provider_key = self._provider_key(provider_key)
        row = connection.execute(
            "SELECT list_id FROM iptv_lists WHERE provider_key=? AND system_type='favorites'",
            (provider_key,),
        ).fetchone()
        if row:
            list_id = row["list_id"]
        else:
            list_id = uuid.uuid4().hex
            now = time.time()
            connection.execute(
                "INSERT INTO iptv_lists(list_id, provider_key, name, system_type, position, created_at, updated_at) VALUES (?, ?, 'Favorites', 'favorites', 0, ?, ?)",
                (list_id, provider_key, now, now),
            )
        legacy_exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='legacy_favorites'"
        ).fetchone()
        if legacy_exists:
            legacy_rows = connection.execute(
                "SELECT kind, item_id, created_at FROM legacy_favorites ORDER BY created_at DESC"
            ).fetchall()
            for position, legacy in enumerate(legacy_rows):
                item = connection.execute(
                    "SELECT * FROM items WHERE kind=? AND item_id=?",
                    (legacy["kind"], legacy["item_id"]),
                ).fetchone()
                snapshot = self._snapshot(item, legacy["kind"], legacy["item_id"])
                connection.execute(
                    """INSERT OR IGNORE INTO iptv_list_items(list_id, kind, item_id, position, added_at, snapshot_json)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (list_id, legacy["kind"], legacy["item_id"], position, legacy["created_at"], json.dumps(snapshot, ensure_ascii=False)),
                )
            connection.execute("DROP TABLE legacy_favorites")
        return list_id

    def list_items(self, kind, category_id="", query="", page=1, page_size=30, favorites_only=False, provider_key="default"):
        if kind not in KINDS:
            raise ValueError("Unsupported IPTV item kind")
        page = max(1, int(page or 1))
        page_size = min(100, max(1, int(page_size or 30)))
        clauses = ["i.kind=?"]
        params = [kind]
        if category_id:
            clauses.append("i.category_id=?")
            params.append(str(category_id))
        if query:
            clauses.append("i.sort_name LIKE ?")
            params.append(f"%{str(query).strip().casefold()}%")
        where = " AND ".join(clauses)
        order = "COALESCE(i.channel_num, 2147483647), i.position" if kind == "live" else "i.position"
        with self._connection() as connection:
            favorites_id = self._ensure_favorites_list(connection, provider_key)
            favorite_clause = " AND EXISTS(SELECT 1 FROM iptv_list_items fi WHERE fi.list_id=? AND fi.kind=i.kind AND fi.item_id=i.item_id)" if favorites_only else ""
            total_params = [*params, favorites_id] if favorites_only else params
            total = connection.execute(f"SELECT COUNT(*) FROM items i WHERE {where}{favorite_clause}", total_params).fetchone()[0]
            rows = connection.execute(
                f"""SELECT i.*, EXISTS(SELECT 1 FROM iptv_list_items fi WHERE fi.list_id=? AND fi.kind=i.kind AND fi.item_id=i.item_id) AS favorite
                    FROM items i WHERE {where}{favorite_clause} ORDER BY {order} LIMIT ? OFFSET ?""",
                [favorites_id, *params, *([favorites_id] if favorites_only else []), page_size, (page - 1) * page_size],
            ).fetchall()
        return {"items": [self._public_item(row) for row in rows], "page": page, "page_size": page_size, "total": total}

    def list_favorites(self, kind="", query="", page=1, page_size=60, provider_key="default"):
        with self._connection() as connection:
            list_id = self._ensure_favorites_list(connection, provider_key)
        result = self.list_entries(provider_key, list_id, kind=kind, query=query, page=page, page_size=page_size)
        for item in result["items"]:
            item["favorite"] = True
        return result

    def get_item(self, kind, item_id, provider_key="default"):
        with self._connection() as connection:
            favorites_id = self._ensure_favorites_list(connection, provider_key)
            row = connection.execute(
                """SELECT i.*, EXISTS(SELECT 1 FROM iptv_list_items fi WHERE fi.list_id=? AND fi.kind=i.kind AND fi.item_id=i.item_id) AS favorite
                   FROM items i WHERE i.kind=? AND i.item_id=?""",
                (favorites_id, kind, str(item_id)),
            ).fetchone()
        return self._public_item(row) if row else None

    @staticmethod
    def _public_item(row):
        data = dict(row)
        data.pop("raw_json", None)
        data.pop("sort_name", None)
        data["favorite"] = bool(data.get("favorite"))
        return data

    def image_url(self, kind, item_id, backdrop=False):
        column = "backdrop_url" if backdrop else "image_url"
        with self._connection() as connection:
            row = connection.execute(f"SELECT {column} FROM items WHERE kind=? AND item_id=?", (kind, str(item_id))).fetchone()
        return _text(row[0]) if row else ""

    def get_cached_detail(self, kind, item_id, max_age=86400):
        with self._connection() as connection:
            row = connection.execute("SELECT payload_json, fetched_at FROM details WHERE kind=? AND item_id=?", (kind, str(item_id))).fetchone()
        if not row or time.time() - row["fetched_at"] > max_age:
            return None
        try:
            return json.loads(row["payload_json"])
        except json.JSONDecodeError:
            return None

    def cache_detail(self, kind, item_id, payload):
        with self._connection() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO details(kind, item_id, payload_json, fetched_at) VALUES (?, ?, ?, ?)",
                (kind, str(item_id), json.dumps(payload, ensure_ascii=False), time.time()),
            )

    @staticmethod
    def _public_list(row):
        data = dict(row)
        for key in ("item_count", "live_count", "movie_count", "series_count"):
            data[key] = int(data.get(key) or 0)
        data["system"] = bool(data.get("system_type"))
        data["included"] = bool(data.get("included"))
        return data

    def lists(self, provider_key="default", kind="", item_id="", include_system=False):
        provider_key = self._provider_key(provider_key)
        if kind and kind not in KINDS:
            raise ValueError("Unsupported IPTV list item kind")
        with self._connection() as connection:
            self._ensure_favorites_list(connection, provider_key)
            system_clause = "" if include_system else " AND l.system_type=''"
            rows = connection.execute(
                f"""SELECT l.*,
                           COUNT(li.item_id) AS item_count,
                           SUM(CASE WHEN li.kind='live' THEN 1 ELSE 0 END) AS live_count,
                           SUM(CASE WHEN li.kind='movie' THEN 1 ELSE 0 END) AS movie_count,
                           SUM(CASE WHEN li.kind='series' THEN 1 ELSE 0 END) AS series_count,
                           EXISTS(SELECT 1 FROM iptv_list_items member
                                  WHERE member.list_id=l.list_id AND member.kind=? AND member.item_id=?) AS included
                    FROM iptv_lists l LEFT JOIN iptv_list_items li ON li.list_id=l.list_id
                    WHERE l.provider_key=?{system_clause}
                    GROUP BY l.list_id
                    ORDER BY CASE WHEN l.system_type='favorites' THEN -1 ELSE l.position END, l.created_at""",
                (kind, str(item_id or ""), provider_key),
            ).fetchall()
        return [self._public_list(row) for row in rows]

    def _owned_list(self, connection, provider_key, list_id):
        row = connection.execute(
            "SELECT * FROM iptv_lists WHERE provider_key=? AND list_id=?",
            (self._provider_key(provider_key), str(list_id)),
        ).fetchone()
        if row is None:
            raise KeyError("IPTV list was not found")
        return row

    def create_list(self, provider_key, name):
        provider_key = self._provider_key(provider_key)
        clean_name = re.sub(r"\s+", " ", _text(name))
        if not clean_name:
            raise ValueError("List name is required")
        if len(clean_name) > 80:
            raise ValueError("List name must be 80 characters or fewer")
        with self._connection() as connection:
            self._ensure_favorites_list(connection, provider_key)
            duplicate = connection.execute(
                "SELECT 1 FROM iptv_lists WHERE provider_key=? AND lower(name)=lower(?)",
                (provider_key, clean_name),
            ).fetchone()
            if duplicate:
                raise ValueError("An IPTV list with that name already exists")
            list_id = uuid.uuid4().hex
            position = connection.execute(
                "SELECT COALESCE(MAX(position), -1) + 1 FROM iptv_lists WHERE provider_key=? AND system_type=''",
                (provider_key,),
            ).fetchone()[0]
            now = time.time()
            connection.execute(
                "INSERT INTO iptv_lists(list_id, provider_key, name, system_type, position, created_at, updated_at) VALUES (?, ?, ?, '', ?, ?, ?)",
                (list_id, provider_key, clean_name, position, now, now),
            )
        return next(item for item in self.lists(provider_key) if item["list_id"] == list_id)

    def rename_list(self, provider_key, list_id, name):
        clean_name = re.sub(r"\s+", " ", _text(name))
        if not clean_name:
            raise ValueError("List name is required")
        if len(clean_name) > 80:
            raise ValueError("List name must be 80 characters or fewer")
        with self._connection() as connection:
            target = self._owned_list(connection, provider_key, list_id)
            if target["system_type"]:
                raise ValueError("System lists cannot be renamed")
            duplicate = connection.execute(
                "SELECT 1 FROM iptv_lists WHERE provider_key=? AND list_id<>? AND lower(name)=lower(?)",
                (self._provider_key(provider_key), str(list_id), clean_name),
            ).fetchone()
            if duplicate:
                raise ValueError("An IPTV list with that name already exists")
            connection.execute(
                "UPDATE iptv_lists SET name=?, updated_at=? WHERE list_id=?",
                (clean_name, time.time(), str(list_id)),
            )
        return next(item for item in self.lists(provider_key) if item["list_id"] == str(list_id))

    def delete_list(self, provider_key, list_id):
        with self._connection() as connection:
            target = self._owned_list(connection, provider_key, list_id)
            if target["system_type"]:
                raise ValueError("System lists cannot be deleted")
            connection.execute("DELETE FROM iptv_lists WHERE list_id=?", (str(list_id),))
        return True

    def add_list_item(self, provider_key, list_id, kind, item_id, prepend=False):
        if kind not in KINDS:
            raise ValueError("Unsupported IPTV list item kind")
        item_id = str(item_id)
        with self._connection() as connection:
            target = self._owned_list(connection, provider_key, list_id)
            item = connection.execute("SELECT * FROM items WHERE kind=? AND item_id=?", (kind, item_id)).fetchone()
            if item is None:
                raise KeyError("IPTV item was not found")
            existing = connection.execute(
                "SELECT 1 FROM iptv_list_items WHERE list_id=? AND kind=? AND item_id=?",
                (str(list_id), kind, item_id),
            ).fetchone()
            if existing:
                return False
            if prepend:
                connection.execute("UPDATE iptv_list_items SET position=position+1 WHERE list_id=?", (str(list_id),))
                position = 0
            else:
                position = connection.execute(
                    "SELECT COALESCE(MAX(position), -1) + 1 FROM iptv_list_items WHERE list_id=?",
                    (str(list_id),),
                ).fetchone()[0]
            now = time.time()
            snapshot = self._snapshot(item, kind, item_id)
            connection.execute(
                "INSERT INTO iptv_list_items(list_id, kind, item_id, position, added_at, snapshot_json) VALUES (?, ?, ?, ?, ?, ?)",
                (str(list_id), kind, item_id, position, now, json.dumps(snapshot, ensure_ascii=False)),
            )
            connection.execute("UPDATE iptv_lists SET updated_at=? WHERE list_id=?", (now, target["list_id"]))
        return True

    def remove_list_item(self, provider_key, list_id, kind, item_id):
        with self._connection() as connection:
            target = self._owned_list(connection, provider_key, list_id)
            cursor = connection.execute(
                "DELETE FROM iptv_list_items WHERE list_id=? AND kind=? AND item_id=?",
                (str(list_id), kind, str(item_id)),
            )
            connection.execute("UPDATE iptv_lists SET updated_at=? WHERE list_id=?", (time.time(), target["list_id"]))
        return cursor.rowcount > 0

    def move_list_item(self, provider_key, list_id, kind, item_id, direction):
        direction = int(direction or 0)
        if direction not in {-1, 1}:
            raise ValueError("List move direction must be -1 or 1")
        with self._connection() as connection:
            target = self._owned_list(connection, provider_key, list_id)
            if target["system_type"]:
                raise ValueError("System list order cannot be changed")
            current = connection.execute(
                "SELECT position FROM iptv_list_items WHERE list_id=? AND kind=? AND item_id=?",
                (str(list_id), kind, str(item_id)),
            ).fetchone()
            if current is None:
                raise KeyError("IPTV list item was not found")
            operator = "<" if direction < 0 else ">"
            order = "DESC" if direction < 0 else "ASC"
            neighbor = connection.execute(
                f"SELECT kind, item_id, position FROM iptv_list_items WHERE list_id=? AND position{operator}? ORDER BY position {order} LIMIT 1",
                (str(list_id), current["position"]),
            ).fetchone()
            if neighbor is None:
                return False
            connection.execute(
                "UPDATE iptv_list_items SET position=? WHERE list_id=? AND kind=? AND item_id=?",
                (neighbor["position"], str(list_id), kind, str(item_id)),
            )
            connection.execute(
                "UPDATE iptv_list_items SET position=? WHERE list_id=? AND kind=? AND item_id=?",
                (current["position"], str(list_id), neighbor["kind"], neighbor["item_id"]),
            )
            connection.execute("UPDATE iptv_lists SET updated_at=? WHERE list_id=?", (time.time(), str(list_id)))
        return True

    def list_entries(self, provider_key, list_id, kind="", query="", page=1, page_size=60):
        if kind and kind not in KINDS:
            raise ValueError("Unsupported IPTV list item kind")
        page = max(1, int(page or 1))
        page_size = min(100, max(1, int(page_size or 60)))
        with self._connection() as connection:
            target = self._owned_list(connection, provider_key, list_id)
            favorites_id = self._ensure_favorites_list(connection, provider_key)
            rows = connection.execute(
                """SELECT i.*, li.kind AS saved_kind, li.item_id AS saved_item_id,
                          li.position AS list_position, li.added_at AS list_added_at, li.snapshot_json,
                          EXISTS(SELECT 1 FROM iptv_list_items fi
                                 WHERE fi.list_id=? AND fi.kind=li.kind AND fi.item_id=li.item_id) AS favorite
                   FROM iptv_list_items li
                   LEFT JOIN items i ON i.kind=li.kind AND i.item_id=li.item_id
                   WHERE li.list_id=? ORDER BY li.position""",
                (favorites_id, str(list_id)),
            ).fetchall()
        items = []
        for row in rows:
            data = dict(row)
            snapshot_json = data.pop("snapshot_json", "{}")
            saved_kind = data.pop("saved_kind")
            saved_item_id = data.pop("saved_item_id")
            list_position = data.pop("list_position")
            list_added_at = data.pop("list_added_at")
            available = bool(data.get("kind") and data.get("item_id"))
            if available:
                item = self._public_item(data)
            else:
                try:
                    item = json.loads(snapshot_json)
                except json.JSONDecodeError:
                    item = {}
                item.update({"kind": saved_kind, "item_id": saved_item_id, "favorite": bool(data.get("favorite"))})
            item.update({"available": available, "list_position": list_position, "list_added_at": list_added_at})
            items.append(item)
        if kind:
            items = [item for item in items if item.get("kind") == kind]
        if query:
            needle = str(query).strip().casefold()
            items = [item for item in items if needle in str(item.get("name") or "").casefold()]
        total = len(items)
        offset = (page - 1) * page_size
        return {
            "list": self._public_list(target),
            "items": items[offset:offset + page_size],
            "page": page,
            "page_size": page_size,
            "total": total,
        }

    def set_favorite(self, kind, item_id, favorite, provider_key="default"):
        with self._connection() as connection:
            favorites_id = self._ensure_favorites_list(connection, provider_key)
        if favorite:
            self.add_list_item(provider_key, favorites_id, kind, item_id, prepend=True)
        else:
            self.remove_list_item(provider_key, favorites_id, kind, item_id)
        return bool(favorite)

    def update_history(self, kind, item_id, position_seconds=0, duration_seconds=0, completed=False):
        with self._connection() as connection:
            if not connection.execute("SELECT 1 FROM items WHERE kind=? AND item_id=?", (kind, str(item_id))).fetchone():
                raise KeyError("IPTV item was not found")
            connection.execute(
                """INSERT OR REPLACE INTO watch_history(
                    kind, item_id, position_seconds, duration_seconds, completed, last_watched
                ) VALUES (?, ?, ?, ?, ?, ?)""",
                (kind, str(item_id), max(0, float(position_seconds or 0)), max(0, float(duration_seconds or 0)), int(bool(completed)), time.time()),
            )

    def recent(self, limit=12, provider_key="default"):
        with self._connection() as connection:
            favorites_id = self._ensure_favorites_list(connection, provider_key)
            rows = connection.execute(
                """SELECT i.*,
                          EXISTS(SELECT 1 FROM iptv_list_items fi WHERE fi.list_id=? AND fi.kind=i.kind AND fi.item_id=i.item_id) AS favorite,
                          h.position_seconds, h.duration_seconds, h.completed, h.last_watched
                   FROM watch_history h JOIN items i ON i.kind=h.kind AND i.item_id=h.item_id
                   ORDER BY h.last_watched DESC LIMIT ?""",
                (favorites_id, min(50, max(1, int(limit)))),
            ).fetchall()
        return [self._public_item(row) for row in rows]
