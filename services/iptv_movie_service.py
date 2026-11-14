import hashlib
import json
from contextlib import nullcontext
import os
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from .iptv_movie_classifier import (
    CLASSIFIER_VERSION,
    build_ollama_classification_payload,
    classify_playlist,
    classify_source,
    validate_ollama_classification,
)
from .iptv_movie_store import (
    ACCEPTED_STATES,
    MOVIE_SCHEMA_VERSION,
    IPTVMovieStore,
    IPTVSelectionError,
    normalize_search_text,
    source_key,
    validate_movie_key,
)
from .iptv_tmdb import (
    BULK_SEARCH_LIMIT_REASON,
    IPTVTMDBClient,
    IPTVTMDBError,
    MATCHER_VERSION,
    PARSER_VERSION,
    bounded_search_candidates,
    candidate_title_aliases,
    choose_automatic_match,
    clean_provider_title,
    collection_first_movie_id,
    collection_part_number,
    combine_provider_title_evidence,
    extract_year,
    interpreted_title_evidence,
    normalize_tmdb_movie,
    parse_provider_title,
    provider_id_matches,
    recovery_candidate_facts,
    recovery_rival_plausible,
    score_candidate,
    verify_recovery_candidate,
)
from .iptv_xtream import XtreamError
from .process_liveness import pid_alive


BULK_RECOVERY_REASONS = {
    'recovery_no_candidate': 'No usable TMDB candidates were found.',
    'recovery_search_limited': BULK_SEARCH_LIMIT_REASON,
    'recovery_primary_year_conflict': 'The provider year conflicts with the primary TMDB release year.',
    'recovery_conflicting_provider_metadata': 'The provider listing and cached film details identify different films.',
    'recovery_title_or_installment_conflict': 'The original title or installment could not be verified.',
    'recovery_runtime_conflict': 'The provider and TMDB runtimes differ materially.',
    'recovery_competing_identities': 'More than one TMDB film fits the available evidence.',
    'recovery_insufficient_identity_evidence': 'The film identity needs more supporting evidence.',
    'recovery_evidence_too_large': 'The candidate evidence exceeds the recovery request size.',
    'recovery_invalid_response': 'ChatGPT returned a missing or invalid recovery result.',
    'recovery_interrupted': 'The recovery request ended without a saved result.',
    'recovery_model_review': 'ChatGPT flagged the candidate comparison for review.',
    'recovery_source_changed': 'The source metadata or eligibility changed during recovery.',
    'recovery_tmdb_failed': 'TMDB verification failed while gathering recovery evidence.',
}


class _CachingTMDBClient:
    """One-cluster cache; never shared across providers or worker claims."""

    def __init__(self, client):
        self.client = client
        self._search = {}
        self._movies = {}
        self._normalized = {}
        self._collections = {}

    def collection(self, tmdb_id):
        key = int(tmdb_id)
        if key not in self._collections:
            self._collections[key] = self.client.collection(key) if hasattr(self.client, 'collection') else {}
        return dict(self._collections[key])

    def search_movies(self, title, year=0, page=1):
        key = (str(title or ""), int(year or 0), int(page or 1))
        if key not in self._search:
            self._search[key] = self.client.search_movies(*key)
        return [dict(row) for row in self._search[key]]

    def search_movie_page(self, title, page=1, *, primary_year=0):
        key = ('primary', title, page, primary_year)
        if key not in self._search:
            self._search[key] = self.client.search_movie_page(title, page, primary_year=primary_year)
        rows, pages = self._search[key]
        return [dict(row) for row in rows], pages

    def movie(self, tmdb_id, language=""):
        key = (int(tmdb_id), str(language or ""))
        if key not in self._movies:
            self._movies[key] = self.client.movie(*key)
        return dict(self._movies[key])

    def normalized_movie(self, tmdb_id, language=""):
        key = (int(tmdb_id), str(language or ""))
        if key not in self._normalized:
            self._normalized[key] = self.client.normalized_movie(*key)
        return dict(self._normalized[key])


class _RejectedAICandidate(ValueError):
    pass


class IPTVMovieService:
    """Provider-local orchestration for raw IPTV movies and enriched metadata."""

    _process_lock = threading.RLock()
    _processes = {}
    _instances = {}
    GLOBAL_WORKER_LIMIT = 1
    PROJECTION_BATCH_SIZE = 500
    WORKER_BATCH_LIMIT = 100
    WORKER_PREPARATION_BATCH_SIZE = 100
    WORKER_GRACEFUL_STOP_SECONDS = 0.75
    WORKER_FORCED_STOP_SECONDS = 0.35
    def __init__(self, provider_root, provider_id, raw_service, metadata_settings, *, tmdb_client_factory=None, process_factory=None, ollama_runner=None):
        self.provider_id = str(provider_id or "")
        self.root = Path(provider_root).resolve()
        self.raw_service = raw_service
        self.metadata_settings = metadata_settings
        self.tmdb_client_factory = tmdb_client_factory or (lambda: IPTVTMDBClient(self.metadata_settings))
        self.process_factory = process_factory or subprocess.Popen
        self.ollama_runner = ollama_runner or self._run_ollama
        self._store = None
        self._store_lock = threading.RLock()
        self._projection_lock = threading.RLock()
        self._projection_thread = None
        self._closing = False
        self._latest_job_references = {"match": None, "rebuild": None}
        with self._process_lock:
            self._instances[self.provider_id] = self

    def _run_ollama(self, evidence):
        settings = self.metadata_settings.public()
        if not settings.get("ollama_enabled"):
            raise RuntimeError("IPTV Ollama assistance is disabled")
        endpoint = str(settings.get("ollama_url") or "").rstrip("/") + "/api/generate"
        prompt = (
            "Return only strict JSON. Use only the supplied IPTV evidence and allowed categories or candidate IDs. "
            "Never invent a TMDB ID. Evidence: " + json.dumps(evidence, ensure_ascii=False, separators=(",", ":"))
        )
        request = urllib.request.Request(
            endpoint,
            data=json.dumps({
                "model": settings.get("ollama_model"), "prompt": prompt,
                "stream": False, "format": "json", "options": {"temperature": 0},
            }, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                raw = response.read(64 * 1024 + 1)
        except (OSError, urllib.error.URLError) as error:
            raise RuntimeError("IPTV Ollama is unavailable or timed out") from error
        if len(raw) > 64 * 1024:
            raise ValueError("IPTV Ollama response exceeded the safe limit")
        try:
            envelope = json.loads(raw.decode("utf-8"))
            result = envelope.get("response") if isinstance(envelope, dict) else None
            return json.loads(result) if isinstance(result, str) else result
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError) as error:
            raise ValueError("IPTV Ollama returned invalid JSON") from error

    @property
    def database_path(self):
        return self.root / "movies.sqlite"

    @property
    def store(self):
        with self._store_lock:
            if self._store is None:
                version = IPTVMovieStore.inspect_schema_version(self.database_path)
                if version not in {0, MOVIE_SCHEMA_VERSION}:
                    raise RuntimeError("This provider's IPTV Movies database requires an approved schema migration")
                self._store = IPTVMovieStore(self.root, self.provider_id)
            return self._store

    def _ready_store(self):
        if not self.database_path.is_file():
            return None
        if IPTVMovieStore.inspect_schema_version(self.database_path) != MOVIE_SCHEMA_VERSION:
            return None
        return self.store

    def _raw_connection(self):
        database_path = Path(self.raw_service.store.database_path).resolve()
        connection = sqlite3.connect(f"file:{database_path.as_posix()}?mode=ro", uri=True, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        return connection

    def _raw_state(self, connection=None):
        owned = connection is None
        connection = connection or self._raw_connection()
        try:
            meta = {row["key"]: row["value"] for row in connection.execute("SELECT key,value FROM meta")}
            favorite = connection.execute(
                "SELECT list_id FROM iptv_lists WHERE provider_key=? AND system_type='favorites' ORDER BY created_at LIMIT 1",
                (self.raw_service.provider_key(),),
            ).fetchone()
            return {
                "generation": int(float(meta.get("generation", 0) or 0)),
                "favorite_list_id": str(favorite[0]) if favorite else "",
            }
        finally:
            if owned:
                connection.close()

    @staticmethod
    def _batch_placeholders(values):
        return ",".join("?" for _ in values)

    def _project_raw_movies(self, connection, generation, total, lease_token):
        cursor = connection.execute(
            """SELECT i.*,COALESCE(c.name,'') playlist_name
               FROM items i LEFT JOIN categories c ON c.kind='movie' AND c.category_id=i.category_id
               WHERE i.kind='movie' ORDER BY i.position,i.item_id"""
        )
        while True:
            raw_rows = cursor.fetchmany(self.PROJECTION_BATCH_SIZE)
            if not raw_rows:
                break
            rows = []
            source_ids = []
            for row in raw_rows:
                item = dict(row)
                raw_json = item.pop("raw_json", "{}")
                try:
                    item["raw"] = json.loads(raw_json)
                except json.JSONDecodeError:
                    item["raw"] = {}
                rows.append(item)
                source_ids.append(str(item["item_id"]))
            placeholders = self._batch_placeholders(source_ids)
            history = {
                str(row["item_id"]): dict(row)
                for row in connection.execute(
                    f"SELECT * FROM watch_history WHERE kind='movie' AND item_id IN ({placeholders})",
                    source_ids,
                )
            }
            memberships = []
            for membership_row in connection.execute(
                f"""SELECT li.list_id,li.item_id source_id,li.position,li.added_at,li.snapshot_json
                    FROM iptv_list_items li JOIN iptv_lists l ON l.list_id=li.list_id
                    WHERE li.kind='movie' AND li.item_id IN ({placeholders})
                    ORDER BY l.position,li.position,li.item_id""",
                source_ids,
            ):
                membership = dict(membership_row)
                try:
                    membership["snapshot"] = json.loads(membership.pop("snapshot_json") or "{}")
                except json.JSONDecodeError:
                    membership["snapshot"] = {}
                memberships.append(membership)
            self.store.project_source_batch(
                rows, generation, memberships=memberships, history=history, lease_token=lease_token
            )
        self.store.finish_projection(generation, lease_token=lease_token)

    def _projection_worker(self, generation, total, lease_token):
        connection = self._raw_connection()
        try:
            self._project_raw_movies(connection, generation, total, lease_token)
        except Exception as error:
            self.store.projection_failed(lease_token, str(error))
        finally:
            connection.close()

    def start_projection(self, *, wait=False):
        with self._projection_lock:
            connection = self._raw_connection()
            try:
                state = self._raw_state(connection)
                total = connection.execute("SELECT COUNT(*) FROM items WHERE kind='movie'").fetchone()[0]
            finally:
                connection.close()
            store = self.store
            if store.source_generation() == state["generation"]:
                return store.projection_status()
            active = self._projection_thread
            if active is not None and active.is_alive():
                return store.projection_status()
            token = store.begin_projection(state["generation"], total)
            if not token:
                return store.projection_status()
            thread = threading.Thread(
                target=self._projection_worker,
                args=(state["generation"], int(total), token),
                name=f"cp-iptv-movie-projection-{self.provider_id[:8]}",
                daemon=True,
            )
            self._projection_thread = thread
            thread.start()
        if wait:
            thread.join()
        return store.projection_status()

    def ensure_projected(self):
        self.start_projection(wait=True)
        connection = self._raw_connection()
        try:
            return self._raw_state(connection)
        finally:
            connection.close()

    def projection_status(self):
        store = self._ready_store()
        if store is None:
            return {
                "state": "migration-required" if self.database_path.is_file() else "not-started",
                "phase": "", "source_generation": 0, "previous_generation": 0,
                "total": 0, "processed": 0, "published": 0, "error": "",
            }
        return store.projection_status()

    def bulk_catalog_continuation(self, keys, filters, apply_id, receipt_keys):
        raw_generation = self._raw_state()['generation']
        store = self._ready_store()
        if not store or self.raw_service.sync_status()['state'] == 'running':
            raise IPTVSelectionError('iptv_projection_in_progress', 'Finish preparing provider movies in IPTV Metadata before resuming.')
        generation, eligible = store.bulk_catalog_continuation(keys, filters, raw_generation)
        if self.raw_service.sync_status()['state'] == 'running' or self._raw_state()['generation'] != raw_generation:
            raise IPTVSelectionError('iptv_projection_in_progress', 'Finish preparing provider movies in IPTV Metadata before resuming.')
        if not apply_id:
            return generation, eligible, set()
        with store.bulk_match_receipts(receipt_keys, apply_id) as receipts:
            return generation, eligible, receipts

    def retry_projection(self):
        return self.start_projection(wait=False)

    @staticmethod
    def _store_category(value):
        value = str(value or "").strip()
        return value.casefold() if value else "unclassified"

    def _ollama_classification_decision(self, playlist_name, titles):
        result = validate_ollama_classification(
            self.ollama_runner(build_ollama_classification_payload(playlist_name, titles))
        )
        category = self._store_category(result.get("category"))
        confidence = float(result.get("confidence") or 0)
        high_confidence = result.get("status") == "classified" and confidence >= 0.9
        return {
            "category": category.title() if high_confidence else "unclassified",
            "confidence": confidence,
            "method": "ollama",
            "status": "classified" if high_confidence else "review",
            "mixed": bool(result.get("mixed")),
            "evidence": {
                "ollama_category": category,
                "evidence_summary": result.get("evidence_summary") or "",
                "input_title_count": len(list(titles or [])[:25]),
            },
            "review_reason": "" if high_confidence else "ollama-low-confidence-or-uncertain",
            "classifier_version": CLASSIFIER_VERSION,
        }

    def classify_catalog(self, *, only_pending=True, use_ollama=False):
        """Classify provider Movies in bounded local pages before TMDB work."""
        store = self._ready_store()
        if store is None:
            raise RuntimeError("Provider movies are still being prepared")
        playlist_samples = {}
        offset = 0
        while True:
            rows = store.classification_rows(only_pending=False, limit=1000, offset=offset)
            if not rows:
                break
            for row in rows:
                bucket = playlist_samples.setdefault(
                    row.get("playlist_id") or "", {"name": row.get("playlist_name") or "", "titles": []}
                )
                if len(bucket["titles"]) < 25:
                    bucket["titles"].append(row.get("provider_title") or "")
            offset += len(rows)
        playlist_decisions = {}
        for playlist_id, bucket in playlist_samples.items():
            decision = classify_playlist(bucket["name"], bucket["titles"])
            if decision.get("category") == "unclassified" and use_ollama and self.ollama_runner:
                decision = self._ollama_classification_decision(bucket["name"], bucket["titles"])
            store.save_playlist_classification(playlist_id, bucket["name"], decision)
            playlist_decisions[playlist_id] = decision

        totals = {"classified": 0, "review": 0, "locked": 0, "categories": {}}
        offset = 0
        while True:
            rows = store.classification_rows(only_pending=only_pending, limit=500, offset=offset)
            if not rows:
                break
            decisions = []
            for row in rows:
                if row.get("classification_manual_lock"):
                    totals["locked"] += 1
                    continue
                decision = classify_source(
                    row.get("provider_title") or "",
                    row.get("playlist_name") or "",
                    playlist_decision=playlist_decisions.get(row.get("playlist_id") or ""),
                )
                if decision.get("category") == "unclassified" and use_ollama and self.ollama_runner:
                    decision = self._ollama_classification_decision(
                        row.get("playlist_name") or "", [row.get("provider_title") or ""]
                    )
                decisions.append({"source_key": row["source_key"], **decision})
                category = self._store_category(decision.get("category"))
                totals["categories"][category] = totals["categories"].get(category, 0) + 1
                totals["review" if category == "unclassified" else "classified"] += 1
            store.apply_classification_decisions(decisions)
            if only_pending:
                # Classified rows disappear. Review rows remain and must be skipped
                # on the next bounded page so an unclear catalog cannot loop forever.
                offset += sum(
                    1 for decision in decisions
                    if self._store_category(decision.get("category")) == "unclassified"
                )
            else:
                offset += len(rows)
        return totals

    def classify_catalog_batch(self, *, limit=WORKER_PREPARATION_BATCH_SIZE):
        """Apply one deterministic classification page on the worker process.

        Ollama is intentionally excluded here. Automatic enrichment must not
        turn a control action into an unbounded series of model calls; unclear
        sources remain review for the explicit proposal flow.
        """
        store = self._ready_store()
        if store is None:
            raise RuntimeError("Provider movies are still being prepared")
        rows = store.classification_rows(
            only_pending=True,
            limit=min(self.WORKER_PREPARATION_BATCH_SIZE, max(1, int(limit or 1))),
        )
        if not rows:
            return {"processed": 0, "classified": 0, "review": 0, "locked": 0}
        playlist_decisions = {}
        decisions = []
        totals = {"processed": 0, "classified": 0, "review": 0, "locked": 0}
        for row in rows:
            if row.get("classification_manual_lock"):
                totals["locked"] += 1
                continue
            playlist_id = row.get("playlist_id") or ""
            playlist_decision = playlist_decisions.get(playlist_id)
            if playlist_decision is None:
                playlist_decision = store.playlist_classification(playlist_id)
                if (not playlist_decision or int(playlist_decision.get("classifier_version") or 0) != CLASSIFIER_VERSION
                        or playlist_decision.get("playlist_name") != (row.get("playlist_name") or "")):
                    playlist_decision = classify_playlist(
                        row.get("playlist_name") or "", [row.get("provider_title") or ""]
                    )
                    store.save_playlist_classification(
                        playlist_id, row.get("playlist_name") or "", playlist_decision
                    )
                playlist_decisions[playlist_id] = playlist_decision
            decision = classify_source(
                row.get("provider_title") or "",
                row.get("playlist_name") or "",
                playlist_decision=playlist_decision,
            )
            decisions.append({"source_key": row["source_key"], "source_generation": row["source_generation"], **decision})
            totals["processed"] += 1
            bucket = "review" if self._store_category(decision.get("category")) == "unclassified" else "classified"
            totals[bucket] += 1
        store.apply_classification_decisions(decisions)
        return totals

    def classification_preview(self, payload=None, *, ai_classifier=None, ai_provenance=None, selection_snapshot=None):
        payload = payload if isinstance(payload, dict) else {}
        selection = selection_snapshot or self.store.resolve_selection(
            mode=payload.get("selection_mode") or "explicit",
            selected_keys=payload.get("selected_keys") or [],
            filters=payload.get("filters") or {}, page=payload.get("page", 1),
            page_size=payload.get("page_size", 50),
        )
        if selection_snapshot and selection['catalog_generation'] != self.store.source_generation():
            raise ValueError('The provider catalog changed; create a new classification preview')
        rows_by_key = {key: self.store.source(key) for key in selection['source_keys']}
        proposals = []
        forced = self._store_category(payload.get("category")) if payload.get("category") else ""
        if forced and forced == "unclassified":
            raise ValueError("Choose Film, Sports, Plays, Music, or Misc")
        if forced and ai_classifier:
            raise ValueError('AI classification cannot also force a manual category')
        decisions = {}
        groups = {}
        playlist_decisions = {}
        for key, row in rows_by_key.items():
            if not row:
                continue
            if ai_classifier and row.get('classification_manual_lock'):
                decisions[key] = {'category': row.get('category') or 'unclassified',
                    'confidence': row.get('classification_confidence') or 0,
                    'method': 'manual-locked', 'evidence': {}, 'review_reason': 'Manual classification lock is preserved'}
                continue
            decision = ({'category': forced.title(), 'confidence': 1, 'method': 'manual-preview',
                         'evidence': {'requested_category': forced}, 'status': 'classified', 'review_reason': ''}
                        if forced else classify_source(row['provider_title'], row.get('playlist_name') or ''))
            decisions[key] = decision
            playlist_id = row.get('playlist_id')
            if ai_classifier and playlist_id and playlist_id not in playlist_decisions:
                playlist_decisions[playlist_id] = self.store.playlist_classification(playlist_id) or {}
            playlist_mixed = playlist_decisions.get(playlist_id, {}).get('mixed')
            needs_title_review = decision.get('method') == 'playlist-default' and (
                row.get('category') == 'unclassified' or playlist_mixed or
                self._store_category(decision.get('category')) != row.get('category'))
            if ai_classifier and (self._store_category(decision.get('category')) == 'unclassified' or needs_title_review):
                groups.setdefault(row.get('playlist_name') or '', []).append(key)
        for playlist, keys in groups.items():
            for offset in range(0, len(keys), 25):
                batch = keys[offset:offset+25]
                titles = [rows_by_key[key]['provider_title'] for key in batch]
                result = ai_classifier(playlist, titles)
                for key in batch:
                    title = rows_by_key[key]['provider_title']
                    exception = next((row for row in result.get('title_exceptions', []) if row['title'] == title), None)
                    chosen = exception or result
                    confident = float(chosen.get('confidence') or 0) >= .9 and (exception is not None or
                        not result.get('mixed') and not result.get('uncertain') and result.get('status') == 'classified')
                    category = self._store_category(chosen.get('category')) if confident else 'unclassified'
                    decisions[key] = {'category': category, 'confidence': chosen.get('confidence') or 0,
                        'method': 'chatgpt', 'evidence': {'category': chosen.get('category'),
                            'evidence_summary': chosen.get('evidence_summary') or '', 'input_title_count': len(titles),
                            'ai_provenance': dict(ai_provenance or {})},
                        'review_reason': '' if category != 'unclassified' else 'chatgpt-low-confidence-or-uncertain'}
        for key in selection["source_keys"]:
            row = rows_by_key.get(key)
            if not row:
                continue
            decision = decisions[key]
            proposals.append({
                "proposal_id": uuid.uuid4().hex, "source_key": key,
                "provider_title": row["provider_title"], "provider_year": row["provider_year"],
                "previous_category": row.get("category") or "unclassified",
                "category": self._store_category(decision.get("category")),
                "confidence": decision.get("confidence", 0), "method": decision.get("method", ""),
                "evidence": decision.get("evidence") or {}, "review_reason": decision.get("review_reason") or "",
                "locked": bool(row.get("classification_manual_lock")),
            })
        return {"provider_id": self.provider_id, "catalog_generation": selection["catalog_generation"], "selection_mode": selection["mode"], "proposals": proposals}

    def classification_apply(self, payload=None, *, preserve_manual_locks=False):
        payload = payload if isinstance(payload, dict) else {}
        expected_generation = int(payload.get("catalog_generation") or -1)
        if expected_generation != self.store.source_generation():
            raise ValueError("The provider catalog changed; preview the classification again")
        proposals = [row for row in payload.get("proposals") or [] if isinstance(row, dict) and row.get("selected", True)]
        unresolved = [row.get('source_key') for row in proposals if self._store_category(row.get('category')) == 'unclassified']
        decisions = [{
            "source_key": row.get("source_key"), "category": row.get("category"),
            "confidence": row.get("confidence", 1), "method": "manual-bulk",
            "evidence": row.get("evidence") or {}, "manual_lock": True,
        } for row in proposals if self._store_category(row.get('category')) != 'unclassified']
        result = self.store.apply_classification_decisions(decisions, manual=True, preserve_manual_locks=preserve_manual_locks,
                                                           expected_generation=expected_generation)
        return {**result, 'skipped': unresolved}

    def list_movies(self, filters=None, page=1, page_size=30):
        store = self._ready_store()
        if store is None:
            return {"items": [], "page": max(1, int(page or 1)), "page_size": min(100, max(1, int(page_size or 30))), "total": 0, "generation": 0, "projection": self.projection_status()}
        snapshot = self._raw_state()
        result = store.list_movies(
            filters,
            page=page,
            page_size=page_size,
            favorite_list_id=snapshot["favorite_list_id"],
        )
        result["projection"] = store.projection_status()
        return result

    def facets(self):
        store = self._ready_store()
        result = store.facets() if store else {"playlists": [], "genres": [], "languages": [], "countries": [], "qualities": []}
        result["lists"] = self._raw_lists_readonly()
        result["projection"] = self.projection_status()
        return result

    def _raw_lists_readonly(self, *, include_system=False):
        connection = self._raw_connection()
        try:
            system_clause = "" if include_system else " AND l.system_type=''"
            rows = connection.execute(
                f"""SELECT l.*,
                           COUNT(li.item_id) AS item_count,
                           SUM(CASE WHEN li.kind='live' THEN 1 ELSE 0 END) AS live_count,
                           SUM(CASE WHEN li.kind='movie' THEN 1 ELSE 0 END) AS movie_count,
                           SUM(CASE WHEN li.kind='series' THEN 1 ELSE 0 END) AS series_count,
                           0 AS included
                    FROM iptv_lists l LEFT JOIN iptv_list_items li ON li.list_id=l.list_id
                    WHERE l.provider_key=?{system_clause}
                    GROUP BY l.list_id
                    ORDER BY CASE WHEN l.system_type='favorites' THEN -1 ELSE l.position END,l.created_at""",
                (self.raw_service.provider_key(),),
            ).fetchall()
            result = []
            for row in rows:
                item = dict(row)
                for key in ("item_count", "live_count", "movie_count", "series_count"):
                    item[key] = int(item.get(key) or 0)
                item["system"] = bool(item.get("system_type"))
                item["included"] = False
                result.append(item)
            return result
        finally:
            connection.close()

    def movie(self, movie_key):
        store = self._ready_store()
        if store is None:
            raise RuntimeError("Provider movies are still being prepared")
        snapshot = self._raw_state()
        return store.movie(validate_movie_key(movie_key), snapshot["favorite_list_id"])

    def sources(self, movie_key):
        store = self._ready_store()
        if store is None:
            raise RuntimeError("Provider movies are still being prepared")
        return store.sources(validate_movie_key(movie_key))

    def _raw_list(self, list_id):
        lists = self.raw_service.lists(include_system=True)
        target = next((row for row in lists if row["list_id"] == str(list_id)), None)
        if target is None:
            raise KeyError("IPTV list was not found")
        return target

    def set_favorite(self, movie_key, favorite):
        movie_key = validate_movie_key(movie_key)
        store = self._ready_store()
        if store is None:
            raise RuntimeError("Provider movies are still being prepared")
        sources = store.sources(movie_key)
        available = [source for source in sources if source.get("available")]
        if not available:
            raise ValueError("This IPTV movie has no available source")
        if favorite:
            self.raw_service.set_favorite("movie", available[0]["item_id"], True)
        else:
            for source in sources:
                self.raw_service.set_favorite("movie", source["item_id"], False)
        favorite_list = next(
            (row for row in self.raw_service.lists(include_system=True) if row.get("system_type") == "favorites"),
            None,
        )
        if not favorite_list:
            raise RuntimeError("The provider Favorites list is unavailable")
        store.set_list_membership(
            favorite_list["list_id"], movie_key, bool(favorite), snapshot=available[0]
        )
        return bool(favorite)

    def set_list_membership(self, movie_key, list_id, included):
        movie_key = validate_movie_key(movie_key)
        target = self._raw_list(list_id)
        if target.get("system_type"):
            raise ValueError("Use the Favorite action for the provider Favorites list")
        store = self._ready_store()
        if store is None:
            raise RuntimeError("Provider movies are still being prepared")
        sources = store.sources(movie_key)
        available = [source for source in sources if source.get("available")]
        if included and not available:
            raise ValueError("This IPTV movie has no available source")
        if included:
            self.raw_service.set_list_item(list_id, "movie", available[0]["item_id"], True)
        else:
            for source in sources:
                self.raw_service.set_list_item(list_id, "movie", source["item_id"], False)
        store.set_list_membership(
            list_id, movie_key, bool(included), snapshot=(available or sources or [{}])[0]
        )
        return bool(included)

    def manual_search(self, movie_key, query="", year=0, tmdb_id=None):
        catalog_generation = self.store.source_generation()
        movie = self.movie(movie_key)
        if movie.get('category') in {'sports', 'music'}:
            raise ValueError('This source classification only supports provider metadata')
        raw_title = str(query or movie.get("provider_title") or movie.get("name") or "").strip()
        target_year = (
            extract_year(year)
            or extract_year(raw_title)
            or extract_year(movie.get("provider_year") or movie.get("year") or 0)
        )
        provider_title = movie.get("provider_title") or movie.get("name") or ""
        parsed = (
            parse_provider_title(raw_title, target_year)
            if query and raw_title != provider_title else combine_provider_title_evidence(
                movie.get("provider_title"), extract_year(year) or movie.get("provider_year"),
                movie.get("detail_title"), movie.get("detail_year"),
                playlist_name=movie.get("playlist_name"),
            )
        )
        target_year = parsed['year']
        client = self.tmdb_client_factory()
        if tmdb_id is not None:
            if movie.get('category') != 'plays' or not str(tmdb_id).isascii() or not str(tmdb_id).isdigit() or not 0 < int(tmdb_id) <= 2147483647:
                raise ValueError('Enter a valid TMDB movie ID for this Play')
            candidate = client.movie(int(tmdb_id))
            if candidate.get('id') != int(tmdb_id):
                raise ValueError('TMDB returned a different identity')
            candidates, attempts = [candidate], []
        else:
            candidates, attempts = bounded_search_candidates(client, parsed)
        items = []
        for row in candidates:
            score = score_candidate(parsed, target_year, row)
            candidate_year = extract_year(row.get("release_date") or row.get("year"))
            year_agreement = not target_year or not candidate_year or abs(target_year - candidate_year) <= 1
            result_class = "validated" if score >= 94 and year_agreement else "plausible" if score >= 78 and year_agreement else "low-relevance"
            items.append({
                "tmdb_id": int(row.get("id") or 0),
                "title": str(row.get("title") or row.get("original_title") or "Untitled"),
                "original_title": str(row.get("original_title") or ""),
                "year": str(row.get("release_date") or "")[:4],
                "plot": str(row.get("overview") or ""),
                "poster_url": f"https://image.tmdb.org/t/p/w342/{str(row.get('poster_path')).lstrip('/')}" if row.get("poster_path") else "",
                "score": score, "result_class": result_class,
                "matching_alias": row.get("search_alias") or parsed.get("primary_alias"),
                "year_agreement": year_agreement,
                "warnings": [] if year_agreement else ["Release year conflicts with the provider source"],
            })
        items.sort(key=lambda row: ({"validated": 0, "plausible": 1, "low-relevance": 2}[row["result_class"]], -row["score"], row["tmdb_id"]))
        return {
            "query": parsed.get("primary_alias") or raw_title,
            "year": target_year,
            "parsed": parsed,
            "attempts": attempts,
            "items": items,
            "catalog_generation": catalog_generation,
        }

    def manual_match(self, movie_key, tmdb_id, *, expected_category=None, expected_generation=None):
        movie_key = validate_movie_key(movie_key)
        store = self._ready_store()
        if store is None:
            raise RuntimeError("Provider movies are still being prepared")
        category = store.movie(movie_key).get('category')
        generation = store.source_generation() if expected_generation is None else int(expected_generation)
        if store.source_generation() != generation:
            raise ValueError('The provider catalog changed. Search again before applying.')
        if expected_category is not None and category != expected_category:
            raise ValueError('The source classification changed. Search again before applying.')
        if category in {'sports', 'music'}:
            raise ValueError('This source classification only supports provider metadata')
        client = self.tmdb_client_factory()
        snapshot = client.normalized_movie(tmdb_id)
        if int(snapshot.get('tmdb_id') or 0) != int(tmdb_id):
            raise ValueError('TMDB returned a different identity')
        play_localization = None
        if category == 'plays' and snapshot.get('original_language') == 'ar':
            try:
                play_localization = client.normalized_movie(tmdb_id, language='ar-SA')
            except IPTVTMDBError:
                pass  # The verified base snapshot still supplies metadata.
        next_key = store.apply_match(
            movie_key,
            snapshot,
            manual=True,
            method="manual",
            confidence=100,
            evidence={"tmdb_id": int(tmdb_id)},
            expected_category=category,
            expected_generation=generation,
        )
        if play_localization:
            store.save_localization(tmdb_id, 'ar-SA', play_localization)
        elif category != 'plays' and snapshot.get("original_language") == "ar":
            store.save_localization(tmdb_id, "ar-SA", client.normalized_movie(tmdb_id, language="ar-SA"))
        return next_key

    def fusion_preview(self, *, limit=500):
        """Preview bounded, independently validated same-provider fusion repairs."""
        store = self._ready_store()
        if store is None:
            raise RuntimeError("Provider movies are still being prepared")
        candidates = store.fusion_candidate_rows(limit=limit)
        proposals = []
        conflicts = []
        for row in candidates["classification"]:
            locked = bool(row.get("manual_lock")) and row.get("category") != "film"
            item = {
                "proposal_id": f"classification:{row['source_key']}",
                "type": "classification", "source_key": row["source_key"],
                "provider_title": row.get("provider_title"),
                "provider_year": int(row.get("provider_year") or 0),
                "playlist_name": row.get("playlist_name"),
                "quality_claim": row.get("quality_claim"),
                "tmdb_id": int(row.get("tmdb_id") or 0),
                "current_category": row.get("category"),
                "reason": "Accepted manual TMDB movie identity requires Film classification",
                "safe": not locked, "locked": locked,
            }
            (proposals if item["safe"] else conflicts).append(item)
        for row in candidates["siblings"]:
            snapshot = store.stored_tmdb_snapshot(row.get("tmdb_id"))
            parsed = combine_provider_title_evidence(
                row.get("provider_title"), row.get("provider_year"),
                row.get("detail_title"), row.get("detail_year"),
            )
            valid, confidence = provider_id_matches(parsed, parsed.get("year"), snapshot or {})
            has_durable_snapshot = bool(
                snapshot
                and int(((snapshot.get("raw") or {}).get("id") or 0)) == int(row.get("tmdb_id") or 0)
            )
            item = {
                "proposal_id": f"sibling:{row['source_key']}:{int(row.get('tmdb_id') or 0)}",
                "type": "sibling", "source_key": row["source_key"],
                "provider_title": row.get("provider_title"),
                "provider_year": int(row.get("provider_year") or 0),
                "playlist_name": row.get("playlist_name"),
                "quality_claim": row.get("quality_claim"),
                "tmdb_id": int(row.get("tmdb_id") or 0),
                "accepted_sibling_count": int(row.get("accepted_count") or 0),
                "match_state": row.get("match_state"),
                "confidence": float(confidence or 0),
                "reason": (
                    "Strict title/year validation agrees with the stored accepted sibling identity"
                    if valid and has_durable_snapshot
                    else "Sibling identity is not independently safe from stored title/year evidence"
                ),
                "safe": bool(valid and has_durable_snapshot), "locked": False,
            }
            (proposals if item["safe"] else conflicts).append(item)
        return {
            "provider_id": self.provider_id,
            "catalog_generation": store.source_generation(),
            "proposals": proposals,
            "conflicts": conflicts,
            "counts": {
                "safe": len(proposals), "conflicts": len(conflicts),
                "classification_repairs": sum(item["type"] == "classification" for item in proposals),
                "validated_siblings": sum(item["type"] == "sibling" for item in proposals),
            },
            "preview_only": True,
        }

    def fusion_apply(self, payload):
        payload = payload if isinstance(payload, dict) else {}
        store = self._ready_store()
        if store is None:
            raise RuntimeError("Provider movies are still being prepared")
        expected_generation = int(payload.get("catalog_generation") or -1)
        if expected_generation != store.source_generation():
            raise ValueError("The provider catalog changed; create a new fusion preview")
        selected = {
            str(value or "").strip() for value in (payload.get("proposal_ids") or [])
            if str(value or "").strip()
        }
        current = self.fusion_preview(limit=max(500, len(selected) * 4))
        available = {item["proposal_id"]: item for item in current["proposals"]}
        applied = []
        rejected = []
        for proposal_id in sorted(selected):
            item = available.get(proposal_id)
            if not item:
                rejected.append({"proposal_id": proposal_id, "reason": "stale-or-unsafe"})
                continue
            if item["type"] == "classification":
                store.apply_classification(
                    [item["source_key"]], "film", method="fusion-repair-manual-match",
                    confidence=1, evidence={"tmdb_id": item["tmdb_id"], "preview": proposal_id},
                    manual=True,
                )
            else:
                snapshot = store.stored_tmdb_snapshot(item["tmdb_id"])
                if not snapshot:
                    rejected.append({"proposal_id": proposal_id, "reason": "snapshot-missing"})
                    continue
                store.apply_match(
                    f"source:{item['source_key']}", snapshot, manual=False,
                    method="validated-sibling-repair", confidence=item.get("confidence", 0),
                    evidence={"sibling_validation": item},
                )
            applied.append(proposal_id)
        return {
            "provider_id": self.provider_id,
            "catalog_generation": store.source_generation(),
            "applied": applied, "rejected": rejected,
            "status": store.worker_control_status(),
        }

    def remove_match(self, movie_key, reprocess=False):
        store = self._ready_store()
        if store is None:
            raise RuntimeError("Provider movies are still being prepared")
        return store.remove_match(validate_movie_key(movie_key), reprocess=bool(reprocess))

    def enrich_source(self, source_key_value, *, tmdb_client=None, claimed_at=None):
        store = self._ready_store()
        if store is None:
            raise RuntimeError("Provider movies are still being prepared")
        source = store.source(source_key_value)
        if not source:
            raise KeyError("IPTV movie source was not found")
        if not source.get("available"):
            return "unmatched"
        if source.get("category") != "film" or source.get("classification_status") != "classified":
            return "classified-non-film" if source.get("category") in {"sports", "plays", "music", "misc"} else "classification-review"
        with store.connection() as connection:
            match = connection.execute(
                "SELECT * FROM source_matches WHERE source_key=?", (source_key_value,)
            ).fetchone()
        if match and match["manual_lock"]:
            return match["state"]
        parsed = combine_provider_title_evidence(
            source.get("provider_title"), source.get("provider_year"),
            source.get("detail_title"), source.get("detail_year"),
            playlist_name=source.get("playlist_name"),
        )
        sibling = store.accepted_sibling_candidate(source_key_value)
        if sibling.get("state") == "candidate":
            snapshot = store.stored_tmdb_snapshot(sibling.get("tmdb_id"))
            valid, confidence = provider_id_matches(parsed, parsed["year"], snapshot or {})
            if valid and snapshot and int((snapshot.get("raw") or {}).get("id") or 0) == int(sibling["tmdb_id"]):
                store.apply_match(
                    f"source:{source_key_value}", snapshot, manual=False,
                    method="validated-sibling", confidence=confidence,
                    evidence={
                        "sibling_validation": {
                            "tmdb_id": int(sibling["tmdb_id"]),
                            "sibling_count": int(sibling.get("sibling_count") or 0),
                            "work_title": sibling.get("work_title"),
                            "work_year": sibling.get("work_year"),
                            "score": confidence,
                            "parsed": parsed,
                        }
                    },
                    claimed_at=claimed_at,
                )
                return "matched-auto"
        client = tmdb_client or self.tmdb_client_factory()
        store.set_match_state([source_key_value], "provider-id-pending", method="provider-detail", claimed_at=claimed_at)
        detail = self.raw_service.enrichment_movie_detail(source["source_id"])
        store.update_provider_detail(source_key_value, detail, claimed_at=claimed_at)
        source = store.source(source_key_value) or source
        parsed = combine_provider_title_evidence(
            source.get("provider_title"), source.get("provider_year"),
            source.get("detail_title") or detail.get("name"),
            source.get("detail_year") or detail.get("year"),
            playlist_name=source.get("playlist_name"),
        )
        provider_tmdb_id = source.get("provider_tmdb_id") or 0
        provider_evidence = {"provider_tmdb_id": provider_tmdb_id, "validated": False, "parsed": parsed}
        if provider_tmdb_id > 0:
            payload = _tmdb_record_if_found(client.movie, provider_tmdb_id)
            if payload is None:
                provider_evidence["lookup"] = "not-found"
        else:
            payload = None
        if payload is not None:
            valid, confidence = provider_id_matches(
                parsed,
                parsed["year"],
                payload,
            )
            if valid:
                key = f"source:{source_key_value}"
                snapshot = normalize_tmdb_movie(payload)
                store.apply_match(
                    key,
                    snapshot,
                    manual=False,
                    method="provider-tmdb-id",
                    confidence=confidence,
                    evidence={"provider_id_validation": {"provider_tmdb_id": provider_tmdb_id, "validated": True, "score": confidence, "parsed": parsed}},
                    claimed_at=claimed_at,
                )
                if snapshot.get("original_language") == "ar":
                    localized = _tmdb_record_if_found(client.normalized_movie, provider_tmdb_id, language="ar-SA")
                    if localized is not None:
                        store.save_localization(provider_tmdb_id, "ar-SA", localized)
                return "matched-auto"
        store.set_match_state([source_key_value], "search-pending", method="title-year-search",
                              evidence={"provider_id_validation": provider_evidence}, claimed_at=claimed_at)
        candidates, attempts = bounded_search_candidates(client, parsed, skip_missing_details=True)
        decision = choose_automatic_match(parsed, parsed["year"], candidates)
        accepted = decision["accepted"]
        snapshot = _tmdb_record_if_found(client.normalized_movie, accepted["id"]) if accepted else None
        if snapshot is not None:
            store.apply_match(
                f"source:{source_key_value}",
                snapshot,
                manual=False,
                method="strict-title-year",
                confidence=accepted["match_score"],
                evidence={
                    "provider_id_validation": provider_evidence,
                    "fallback_search": {"parsed": parsed, "attempts": attempts, "candidate_count": len(decision["candidates"])},
                },
                claimed_at=claimed_at,
            )
            if snapshot.get("original_language") == "ar":
                localized = _tmdb_record_if_found(client.normalized_movie, accepted["id"], language="ar-SA")
                if localized is not None:
                    store.save_localization(accepted["id"], "ar-SA", localized)
            return "matched-auto"
        evidence = {
            "provider_id_validation": provider_evidence,
            "fallback_search": {
                "parsed": parsed, "attempts": attempts,
                "candidates": [{"tmdb_id": int(row.get("id") or 0), "score": row.get("match_score", 0), "alias": row.get("search_alias"), "phase": row.get("search_phase")} for row in decision["candidates"][:5]],
            },
        }
        state = decision["state"]
        if accepted:
            state = "unmatched"
            evidence["fallback_search"]["missing_candidate_tmdb_id"] = accepted["id"]
        store.set_match_state(
            [source_key_value], state, method="strict-title-year", evidence=evidence, claimed_at=claimed_at
        )
        return state

    def enrich_work_cluster(self, source_keys, *, tmdb_client=None, should_continue=None, claimed_at=None):
        client = _CachingTMDBClient(tmdb_client or self.tmdb_client_factory())
        outcomes = []
        for key in list(dict.fromkeys(str(value or "").strip() for value in source_keys if str(value or "").strip())):
            if should_continue is not None and not should_continue():
                break
            try:
                state = self.enrich_source(key, tmdb_client=client, claimed_at=claimed_at)
                outcomes.append({"source_key": key, "state": state})
            except Exception as error:
                outcomes.append({"source_key": key, "state": "error", "error": str(error)[:300], "_error": error})
        return outcomes

    def localization(self, movie_key, locale):
        movie = self.movie(movie_key)
        tmdb_id = int(movie.get("tmdb_id") or 0)
        if not tmdb_id:
            raise ValueError("Unmatched provider movies do not have TMDB localization")
        locale = str(locale or "")
        stored = self.store.localization(tmdb_id, locale)
        if stored:
            return self.store.merge_localization_display(movie, stored, locale)
        if locale != "ar-SA":
            raise ValueError("Unsupported IPTV movie localization")
        # Non-Arabic movies fetch Arabic only after an explicit user switch and
        # do not persist that transient presentation choice.
        localized = self.tmdb_client_factory().normalized_movie(tmdb_id, language=locale)
        return {**self.store.merge_localization_display(movie, localized, locale), "transient": True}

    def repair_missing_arabic_localizations(self, *, limit=100, tmdb_client=None):
        """Backfill display-only Arabic snapshots without changing accepted identities."""
        store = self._ready_store()
        if store is None:
            raise RuntimeError("Provider movies are still being prepared")
        tmdb_ids = store.missing_arabic_localizations(limit=limit)
        client = tmdb_client or self.tmdb_client_factory()
        saved = []
        failed = []
        for tmdb_id in tmdb_ids:
            try:
                store.save_localization(tmdb_id, "ar-SA", client.normalized_movie(tmdb_id, language="ar-SA"))
                saved.append(tmdb_id)
            except Exception as error:
                failed.append({"tmdb_id": tmdb_id, "error": str(error)[:300]})
        return {"requested": len(tmdb_ids), "saved": saved, "failed": failed}

    @property
    def _scheduler_path(self):
        return self.metadata_settings.root / "metadata-worker-scheduler.json"

    def _claim_global_capacity(self, token):
        path = self._scheduler_path
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"provider_id": self.provider_id, "token": token, "pid": os.getpid()})
        for _attempt in range(2):
            try:
                descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                    stream.write(payload)
                return True
            except FileExistsError:
                try:
                    current = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    current = {}
                if pid_alive(current.get("pid")):
                    return False
                try:
                    path.unlink()
                except FileNotFoundError:
                    pass
        return False

    def _update_global_capacity_pid(self, token, pid):
        try:
            current = json.loads(self._scheduler_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if current.get("provider_id") == self.provider_id and current.get("token") == token:
            temporary = self._scheduler_path.with_suffix(f".{uuid.uuid4().hex}.tmp")
            temporary.write_text(json.dumps({**current, "pid": int(pid)}), encoding="utf-8")
            os.replace(temporary, self._scheduler_path)

    def _release_global_capacity(self, token):
        try:
            current = json.loads(self._scheduler_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if current.get("provider_id") == self.provider_id and current.get("token") == token:
            try:
                self._scheduler_path.unlink()
            except OSError:
                pass

    def _monitor_worker(self, process, token):
        try:
            exit_code = process.wait()
        except Exception:
            while process.poll() is None:
                time.sleep(0.25)
            exit_code = process.poll()
        try:
            if not self._closing:
                self.store.worker_finished(
                    "crashed", f"IPTV metadata worker exited before finishing (exit code {exit_code})",
                    token=token, only_active=True,
                )
        finally:
            self._release_global_capacity(token)
            with self._process_lock:
                if self._processes.get(self.provider_id) is process:
                    self._processes.pop(self.provider_id, None)
                waiting = [service for service in self._instances.values() if service.provider_id != self.provider_id]
        if self._closing:
            return
        for service in waiting:
            try:
                if service.enrichment_status().get("state") == "waiting-capacity":
                    service._launch_enrichment(resume=True, queued=True)
                    break
            except Exception:
                continue

    def _existing_local_worker_start(self):
        """Keep repeated start/resume requests from replacing a live lease.

        A worker can record its terminal database state just before its OS
        process exits. During that short window, issuing Start again must not
        mint a new token for a process that was launched with the old token.
        """
        with self._process_lock:
            process = self._processes.get(self.provider_id)
            if process is None:
                return None
            if process.poll() is not None:
                self._processes.pop(self.provider_id, None)
                return None
        status = self.store.worker_control_status()
        if status.get("command") == "run" and status.get("state") in {
            "starting", "running", "waiting-capacity",
        }:
            return status
        raise RuntimeError(
            "The previous IPTV metadata worker is still shutting down; try again in a moment"
        )

    def _spawn_worker(self, token, *, diagnostic_limit=0):
        with self._process_lock:
            active = {
                provider_id: process
                for provider_id, process in self._processes.items()
                if process.poll() is None
            }
            self._processes.clear()
            self._processes.update(active)
            current = active.get(self.provider_id)
            if current is not None:
                return current
            process = None
            try:
                if len(active) >= self.GLOBAL_WORKER_LIMIT or not self._claim_global_capacity(token):
                    self.store.worker_waiting_for_capacity(token)
                    return None
                environment = os.environ.copy()
                environment.update({
                    "CP_IPTV_WORKER_PROVIDER_ID": self.provider_id,
                    "CP_IPTV_WORKER_PROVIDER_ROOT": str(self.root),
                    "CP_IPTV_WORKER_USER_DATA_DIR": str(self.metadata_settings.root.parent),
                    "CP_IPTV_WORKER_LEASE_TOKEN": token,
                    "CP_IPTV_WORKER_MAX_JOBS": str(max(0, int(diagnostic_limit or 0))),
                    "CP_IPTV_WORKER_SCHEDULER_PATH": str(self._scheduler_path),
                })
                process = self.process_factory(
                    [sys.executable, "-m", "services.iptv_enrichment_worker"],
                    cwd=str(Path(__file__).resolve().parents[1]), env=environment,
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                self._update_global_capacity_pid(token, process.pid)
                self._processes[self.provider_id] = process
                # The child owns the durable running transition.
                threading.Thread(target=self._monitor_worker, args=(process, token),
                                 name=f"cp-iptv-worker-monitor-{self.provider_id[:8]}", daemon=True).start()
            except Exception as error:
                reason = f"Could not start the IPTV metadata worker: {self.metadata_settings.redact(error)}"
                try:
                    self.store.worker_finished("crashed", reason, token=token, only_active=True)
                finally:
                    self._processes.pop(self.provider_id, None)
                    if process is not None and process.poll() is None:
                        try:
                            process.terminate()
                        except OSError:
                            pass
                    self._release_global_capacity(token)
                raise RuntimeError(reason) from error
            return process

    def start_enrichment(self, *, consent=False, diagnostic=False):
        return self._launch_enrichment(consent=consent, diagnostic=diagnostic)

    def _launch_enrichment(self, *, resume=False, consent=False, diagnostic=False, continue_after_restart=False,
                           queued=False):
        if not queued:
            store = self._ready_store()
            if (store is None or self.raw_service.sync_status()["state"] == "running"
                    or store.projection_status()["state"] != "complete"
                    or store.source_generation() != self._raw_state()["generation"]):
                raise RuntimeError("Finish preparing provider movies before starting metadata enrichment")
        with self._process_lock:
            existing = self._existing_local_worker_start()
            if existing is not None:
                return self._merge_control_status(existing)
            self.metadata_settings.credential()
            if resume:
                token = self.store.resume_worker(continue_after_restart=bool(continue_after_restart))
                limit = self.store.worker_control_status()["diagnostic_limit"]
            else:
                limit = self.WORKER_BATCH_LIMIT if diagnostic else 0
                token = self.store.schedule_enrichment(consent=bool(consent), diagnostic_limit=limit)
            self._spawn_worker(token, diagnostic_limit=limit)
        return self._merge_control_status(self.store.worker_control_status())

    def pause_enrichment(self):
        return self._merge_control_status(self.store.worker_command("pause"))

    def resume_enrichment(self, *, continue_after_restart=False):
        return self._launch_enrichment(resume=True, continue_after_restart=continue_after_restart)

    def cancel_enrichment(self):
        with self._process_lock:
            process = self._processes.get(self.provider_id)
            if process is not None and process.poll() is not None:
                self._processes.pop(self.provider_id, None)
                process = None
        if process is None:
            self.store.cancel_enrichment()
        else:
            self.store.worker_command("cancel")
        return self._merge_control_status(self.store.worker_control_status())

    def _merge_control_status(self, control, *, status_stale=False):
        """Publish the exact provider-local transactional summary."""
        merged = self._public_worker_status(control)
        merged["summary_available"] = True
        merged["status_stale"] = bool(status_stale)
        return merged

    @staticmethod
    def _public_worker_status(status):
        """Keep durable worker diagnostics out of the API error envelope."""
        public = dict(status or {})
        public["worker_error"] = public.pop("error", "")
        return public

    def enrichment_status(self):
        if not self.database_path.is_file():
            return {
                "state": "idle", "command": "idle", "pid": 0, "worker_error": "",
                "started_at": 0, "finished_at": 0, "generation": 0,
                "source_generation": 0, "sources": 0, "queue": {}, "matches": {},
                "batch_limit": self.WORKER_BATCH_LIMIT,
            }
        try:
            status = self._public_worker_status({
                **self.store.worker_control_status(include_projection=True),
                "batch_limit": self.WORKER_BATCH_LIMIT,
                "summary_available": True,
                "status_stale": False,
            })
        except sqlite3.Error:
            raise RuntimeError("IPTV Movies status is temporarily busy")
        return status

    def metadata_status(self, *, control_only=False):
        status = self.enrichment_status()
        if (
            not control_only
            and status.get("state") not in {"starting", "running", "pausing", "cancelling", "waiting-capacity"}
            and self.database_path.is_file()
            and self._ready_store() is not None
        ):
            try:
                self._latest_job_references = self.store.latest_job_references()
            except sqlite3.Error:
                status["status_stale"] = True
        status["latest_jobs"] = self._latest_job_references
        return status

    def metadata_review(self, view="needs-review", page=1, page_size=50, filters=None):
        store = self._ready_store()
        if store is None:
            return {"view": view, "items": [], "page": page, "page_size": page_size, "total": 0}
        return store.review_queue(view, page=page, page_size=page_size, filters=filters)

    def prioritize_movies(self, movie_keys):
        store = self._ready_store()
        if store is None:
            return 0
        source_keys = []
        for movie_key in list(movie_keys or [])[:100]:
            source_keys.extend(store.source_keys_for_movie(validate_movie_key(movie_key)))
        return store.prioritize_sources(source_keys)

    def retry_failures(self):
        count = self.store.retry_failures()
        return {**self.enrichment_status(), "retried": count}

    def re_evaluate_stale(self):
        self.store.mark_stale_automatic_results()
        count = self.store.re_evaluate_stale()
        return {**self.enrichment_status(), "requeued": count}

    @staticmethod
    def _source_title_evidence(source):
        return combine_provider_title_evidence(
            source.get("provider_title"), source.get("provider_year"),
            source.get("detail_title"), source.get("detail_year"),
            playlist_name=source.get("playlist_name"),
        )

    def bulk_tmdb_client(self):
        return _CachingTMDBClient(self.tmdb_client_factory())

    def recheck_bulk_search(self, source, saved, client):
        """Use saved title hints only when the current listing still supports them."""
        if (not source or source.get('match_state') in ACCEPTED_STATES or source.get('classification_manual_lock')
                or not self.bulk_inference_eligible(source)):
            return None
        prior, interpretation = saved['evidence']['identity'], saved['evidence']['interpretation']
        current = interpreted_title_evidence(self._source_title_evidence(source), interpretation)['bulk_identity']
        if current != prior:
            return None
        return self.bulk_source_proposal(source, client, interpretation=interpretation, interpreted=True, automatic=True)

    @staticmethod
    def _bulk_provider_facts(source):
        from .chatgpt_tools import model_safe

        try:
            detail = json.loads(source.get('detail_json') or '{}')
        except (TypeError, ValueError):
            detail = {}
        if not isinstance(detail, dict):
            detail = {}
        def value(column, *names):
            return next((detail[name] for name in names if isinstance(detail.get(name), str) and detail[name].strip()),
                        source.get(column) or '')
        cast = value('provider_cast', 'cast_names', 'cast').split(',')
        return model_safe({'title': source['provider_title'], 'year': source['provider_year'],
                           'playlist': source.get('playlist_name') or '',
                           'detail_title': value('detail_title', 'name', 'title'),
                           'detail_year': extract_year(source.get('detail_year')) or extract_year(detail.get('year')),
                           'duration': value('provider_duration', 'duration'),
                           'cast': ', '.join(name.strip() for name in cast[:8]),
                           'director': value('provider_director', 'director'),
                           'plot': value('provider_plot', 'plot', 'description')})

    @staticmethod
    def _bulk_candidate_fingerprint(movie):
        facts = recovery_candidate_facts(movie, localized=False)
        facts['collection'] = (movie.get('belongs_to_collection') or {}).get('id')
        return hashlib.sha256(json.dumps(facts, ensure_ascii=False, sort_keys=True).encode()).hexdigest()

    @staticmethod
    def _bulk_candidate_proof(movie):
        return {key: movie[key] for key in ('localized_titles', 'collection_first_movie_id', 'collection_part_number')
                if movie.get(key)}

    @staticmethod
    def _bulk_proof_current(client, movie, proof):
        collection = (movie.get('belongs_to_collection') or {}).get('id')
        if proof.get('collection_first_movie_id') and proof['collection_first_movie_id'] != collection_first_movie_id(client, collection):
            return False
        if proof.get('collection_part_number') and proof['collection_part_number'] != collection_part_number(client, collection, movie['id']):
            return False
        if proof.get('localized_titles'):
            localized = client.movie(movie['id'], language='ar-SA')
            current = {str(localized.get(key) or '').strip() for key in ('title', 'original_title')} - {''}
            return current == set(proof['localized_titles'])
        return True

    def _bulk_recovery_evidence(self, source, parsed, candidates):
        ordered = sorted(candidates, key=lambda row: (
            -score_candidate(parsed, parsed['year'], row), int(row['id'])))
        hydrated = [row for row in ordered if row.get('candidate_hydrated')]
        selected = hydrated[:8]
        selected_ids = {row['id'] for row in selected}
        limited = (any(row.get('bulk_search_limited') for row in ordered) or
                   any(row['id'] not in selected_ids and recovery_rival_plausible(parsed, row)
                       for row in ordered))
        return {'provider': self._bulk_provider_facts(source), 'search_limit_reached': limited,
                'candidates': [recovery_candidate_facts(row) for row in selected],
                'candidate_fingerprints': {str(row['id']): self._bulk_candidate_fingerprint(row) for row in selected},
                'candidate_proofs': {str(row['id']): self._bulk_candidate_proof(row) for row in selected}}

    @staticmethod
    def compact_bulk_recovery(evidence):
        from .chatgpt_tools import model_safe

        provider = dict(evidence['provider'])
        provider['plot'] = provider['plot'][:360]
        targets = set(combine_provider_title_evidence(provider['title'], provider['year'],
            provider['detail_title'], provider['detail_year'], playlist_name=provider['playlist'])['aliases'])
        target_words = set(' '.join(targets).split())
        candidates = []
        for candidate in evidence['candidates']:
            names = {clean_provider_title(candidate[key]) for key in ('title', 'original_title')}
            aliases = sorted((alias for alias in candidate['aliases'] if alias not in names),
                             key=lambda alias: (alias not in targets, not bool(set(alias.split()) & target_words)))
            compact = dict(candidate, aliases=aliases[:4], overview=candidate['overview'][:240])
            candidates.append(compact)
        return model_safe({'provider': provider, 'candidates': candidates,
                           'search_limit_reached': evidence['search_limit_reached']})

    def prepare_bulk_recovery(self, source, prior, client):
        parsed = self._source_title_evidence(source)
        interpretation = prior['evidence'].get('interpretation') or {}
        parsed = interpreted_title_evidence(parsed, {**interpretation, 'year': ''})
        # Prefer raw/detail aliases before model suggestions when a query bound is reached.
        aliases = list(dict.fromkeys([*parsed['bulk_identity']['provider_aliases'], *parsed['aliases']]))
        candidates, attempts = bounded_search_candidates(client, parsed, search_aliases=aliases, strict_bounds=True)
        return dict(self._bulk_recovery_evidence(source, parsed, candidates), search_attempts=attempts)

    @staticmethod
    def bulk_inference_eligible(source):
        return (not source['match_manual_lock'] and
                (source.get('match_state') not in ACCEPTED_STATES or source.get('match_stale')) and
                source['category'] in {'film', 'unclassified'} and
                (not source['classification_manual_lock'] or source['category'] == 'film'))

    @classmethod
    def bulk_recovery_eligible(cls, source, proposal):
        unresolved = proposal['outcome'] in {'review', 'unmatched'} or proposal['evidence'].get('first_pass_invalid_response')
        if not unresolved or not cls.bulk_inference_eligible(source):
            return False
        interpretation = proposal['evidence'].get('interpretation') or {}
        if interpretation.get('category') not in (None, 'Film'):
            return False
        local = classify_source(source['provider_title'], source.get('playlist_name') or '')
        return (proposal['category'] == 'film' or source['category'] == 'film' or
                local['category'] == 'Film' or bool(cls._bulk_provider_facts(source)['duration']))

    @classmethod
    def finish_bulk_recovery(cls, prior, entry, decision=None, reason=''):
        from .chatgpt_tools import model_safe

        evidence = entry.get('evidence')
        recovery = {key: entry[key] for key in ('evidence_hash', 'candidate_ids', 'protocol_hash', 'attempts') if key in entry}
        recovery['first_pass'] = {'outcome': prior['outcome'], 'reason': prior.get('review_reason', '')}
        if evidence:
            recovery['input'] = entry.get('submitted_input') or cls.compact_bulk_recovery(evidence)
            recovery['search_attempts'] = model_safe(evidence['search_attempts'])
        if decision is not None:
            recovery['decision'] = decision
            candidate_id = decision['candidate_id']
            facts = verify_recovery_candidate(evidence['provider'], evidence['candidates'], candidate_id,
                                               search_limited=evidence['search_limit_reached'])
            recovery['verification'] = facts
            if not reason:
                reason = facts['reason']
                if decision['decision'] == 'review' and (not reason or candidate_id is None):
                    reason = 'recovery_model_review'
        message = BULK_RECOVERY_REASONS.get(reason, '')
        recovery['reason'] = reason
        if entry.get('tmdb_error'):
            recovery['tmdb_error'] = entry['tmdb_error']
        result = {**prior, 'evidence': {**prior['evidence'], 'recovery': recovery},
                  'review_reason': message, 'warnings': [message] if message else []}
        if not reason:
            candidate = next(row for row in evidence['candidates'] if row['candidate_id'] == candidate_id)
            result.update(category='film', classification_confidence=.9, confidence=100,
                          outcome='verified', recommendation='recommended', candidate_tmdb_id=candidate_id,
                          bulk_automatic=True, source_revision=entry['source_revision'],
                          match_revision=entry['match_revision'],
                          candidate_fingerprint=evidence['candidate_fingerprints'][str(candidate_id)],
                          tmdb_proof=evidence['candidate_proofs'][str(candidate_id)])
            result['evidence']['candidate'] = {'tmdb_id': candidate_id, 'title': candidate['title'],
                                                'year': extract_year(candidate['release_date'])}
        else:
            result.update(recommendation='review',
                          outcome='unmatched' if reason == 'recovery_no_candidate' else
                          'failed' if reason in {'recovery_tmdb_failed', 'recovery_invalid_response',
                                                 'recovery_interrupted'} else 'review')
        return result

    def bulk_source_proposal(self, source, client, *, interpretation=None, interpreted=False, automatic=False,
                             focused_search=True):
        """Prepare one review row, or return None when interpretation is still needed."""
        current = source['category']
        classification_locked = bool(source['classification_manual_lock'])
        match_locked = bool(source['match_manual_lock'])
        row = {'source_key': source['source_key'], 'proposal_id': source['source_key'],
               'provider_title': source['provider_title'], 'provider_year': source['provider_year'],
               'previous_category': current, 'category': current, 'candidate_tmdb_id': 0,
               'classification_confidence': source['classification_confidence'], 'confidence': 0,
               'method': 'chatgpt-bulk', 'evidence': {}, 'locked': classification_locked,
               'match_manual_lock': match_locked, 'recommendation': 'review', 'warnings': []}

        def outcome(kind, reason=''):
            return {**row, 'outcome': kind, 'review_reason': reason,
                    'warnings': [reason] if reason else []}

        if match_locked:
            return outcome('review', 'Manual match lock preserved.')
        if automatic and source.get('match_state') in ACCEPTED_STATES and not source.get('match_stale'):
            return outcome('review', 'This source already has a verified film match.')
        local = classify_source(source['provider_title'], source.get('playlist_name') or '')
        local_category = self._store_category(local.get('category'))
        if classification_locked or current in {'sports', 'music', 'plays'} or (automatic and current == 'misc'):
            category, confidence = current, source['classification_confidence']
        elif local_category != 'unclassified' and local['confidence'] >= .9 and local['method'] != 'playlist-default':
            category, confidence = local_category, local['confidence']
        elif current == 'film' and source['classification_confidence'] >= .9:
            category, confidence = current, source['classification_confidence']
        else:
            category, confidence = 'unclassified', 0
        if category not in {'film', 'unclassified'}:
            row.update(category=category, classification_confidence=confidence)
            return outcome('categorized')

        if automatic and classification_locked and category != 'film':
            return outcome('review', 'Manual classification lock preserved.')

        parsed = self._source_title_evidence(source)
        hints = []
        if interpreted:
            if interpretation is None:
                if automatic:
                    row['evidence']['first_pass_invalid_response'] = True
                return outcome('failed', 'ChatGPT did not return a valid row after repair.')
            row['evidence']['interpretation'] = dict(interpretation)
            if interpretation['uncertain'] or interpretation['confidence'] < .9:
                return outcome('review', 'ChatGPT could not classify this source confidently.')
            if category == 'unclassified':
                category = self._store_category(interpretation['category'])
                confidence = interpretation['confidence']
            hints = list(dict.fromkeys(filter(None, (
                clean_provider_title(title, parsed['year']) for title in
                [interpretation['title'], *interpretation['aliases']]))))
            row['evidence']['search_hints'] = hints
            row['evidence']['suggested_year'] = extract_year(interpretation['year'])
            parsed = interpreted_title_evidence(parsed, interpretation)
            row['evidence']['identity'] = parsed['bulk_identity']
        row.update(category=category, classification_confidence=confidence)
        if category not in {'film', 'unclassified'}:
            return outcome('categorized')
        if classification_locked and category != 'film':
            return outcome('review', 'Manual classification lock preserved.')
        candidate = None
        candidates = []
        score = 0
        try:
            provider_id = int(source['provider_tmdb_id'] or 0)
            if provider_id and not interpreted:
                try:
                    supplied = client.movie(provider_id)
                except IPTVTMDBError as error:
                    if error.status != 404:
                        raise
                    supplied = {}
                valid, score = provider_id_matches(parsed, parsed['year'], supplied)
                if valid and supplied.get('id') == provider_id:
                    candidate = supplied
                    row['evidence']['provider_id_validated'] = True
            if (not candidate and category == 'film') or (automatic and candidate):
                if automatic and not parsed.get('bulk_identity'):
                    parsed = interpreted_title_evidence(parsed, {})
                aliases = list(dict.fromkeys([*parsed['aliases'], *hints]))
                candidates, attempts = bounded_search_candidates(client, parsed, search_aliases=aliases,
                    **({'strict_bounds': True, 'focused': focused_search} if automatic else {}))
                decision = choose_automatic_match(parsed, parsed['year'], candidates)
                row['evidence']['search_attempts'] = attempts
                row['evidence']['candidates'] = [
                    {'tmdb_id': item['id'], 'title': item.get('title') or '',
                     'year': extract_year(item.get('release_date')), 'score': item['match_score'],
                     'identity_conflict': item.get('identity_conflict', ''),
                     'rival_score': item.get('rival_score', item['match_score'])}
                    for item in decision['candidates']]
                candidate = decision['accepted'] or (candidate if not candidates else None)
                if candidate:
                    score = candidate.get('match_score', score)
                elif interpreted:
                    row['recommendation'] = 'no-match'
                    if decision.get('reason') == BULK_SEARCH_LIMIT_REASON:
                        row['evidence']['review_code'] = 'recovery_search_limited'
                    return (outcome('review', decision.get('reason') or 'TMDB candidates could not be independently verified.')
                            if decision['state'] == 'ambiguous' else outcome('unmatched', 'No verified TMDB candidate.'))
        except IPTVTMDBError as error:
            row['evidence']['verification_error'] = {
                'message': str(error), 'status': error.status,
                'retryable': error.retryable, 'retry_after': error.retry_after}
            return outcome('failed', 'TMDB verification failed for this source.')
        if candidate and automatic:
            recovery = self._bulk_recovery_evidence(source, parsed, candidates)
            if not any(item['candidate_id'] == candidate['id'] for item in recovery['candidates']):
                recovery['candidates'].append(recovery_candidate_facts(candidate))
            facts = verify_recovery_candidate(recovery['provider'], recovery['candidates'], candidate['id'],
                search_limited=recovery['search_limit_reached'], require_support=False)
            if not facts['verified']:
                row['evidence']['first_pass_verification'] = facts
                row['evidence']['review_code'] = facts['reason']
                return outcome('review', BULK_RECOVERY_REASONS[facts['reason']]) if interpreted else None
            row['bulk_automatic'] = True
            row['source_revision'] = source['source_revision']
            row['match_revision'] = source['match_revision']
            row['candidate_fingerprint'] = self._bulk_candidate_fingerprint(candidate)
            row['tmdb_proof'] = self._bulk_candidate_proof(candidate)
        if candidate:
            row.update(category='film', classification_confidence=max(.9, confidence),
                       candidate_tmdb_id=candidate['id'], confidence=score, recommendation='recommended')
            row['evidence']['candidate'] = {'tmdb_id': candidate['id'], 'title': candidate.get('title') or '',
                                            'year': extract_year(candidate.get('release_date') or candidate.get('year'))}
            return outcome('verified')
        if interpreted:
            return outcome('unmatched', 'No verified TMDB candidate.')
        return None

    def apply_bulk_proposals(self, proposals, kind, generation, *, operation_id=None, stop_requested=None):
        if not operation_id and not self.store.bulk_selection_current(generation):
            raise ValueError('The provider catalog changed. Start a new review.')
        report = {'applied': [], 'skipped': [], 'failed': [], 'locked': []}
        if kind == 'classification':
            decisions = []
            for row in proposals:
                key = row['source_key']
                if (row.get('catalog_stale') or row['outcome'] not in {'categorized', 'unmatched', 'review'} or
                        row['category'] in {'unclassified', row['previous_category']} or
                        row['classification_confidence'] < .9 or row['locked'] or row['match_manual_lock']
                        or row.get('apply_state') == 'applied'):
                    report['skipped'].append(key)
                    continue
                decisions.append({'source_key': key, 'category': row['category'], 'method': 'chatgpt-bulk',
                                  'confidence': row['classification_confidence'], 'evidence': row['evidence'],
                                  'expected_category': row['previous_category']})
            result = self.store.apply_classification_decisions(decisions, manual=True, preserve_manual_locks=True,
                expected_generation=generation, preserve_match_locks=True, stable_projection=True)
            return {**report, 'applied': result['applied'], 'locked': result['locked'],
                    'skipped': [*report['skipped'], *result['missing']]}
        receipts = (self.store.bulk_match_receipts([row['source_key'] for row in proposals], operation_id)
                    if operation_id else nullcontext(set()))
        with receipts as applied:
            return self._apply_bulk_matches(proposals, generation, report, applied, operation_id, stop_requested)

    def _apply_bulk_matches(self, proposals, generation, report, applied, operation_id, stop_requested):
        client = None
        outcomes = []
        halted = ''
        for row in proposals:
            key = row['source_key']
            if (row.get('catalog_stale') or row['outcome'] != 'verified' or row['category'] != 'film' or row.get('match_manual_lock')
                    or type(row.get('candidate_tmdb_id')) is not int or row['candidate_tmdb_id'] < 1
                    or row.get('apply_state') == 'applied'):
                report['skipped'].append(key)
                continue
            if key in applied:
                outcomes.append((row, 'applied', '', False))
                report['applied'].append(key)
                continue
            if halted or (stop_requested and stop_requested()):
                halted = halted or 'bulk_apply_stopped'
                continue
            message, retryable = '', False
            try:
                tmdb_id = row['candidate_tmdb_id']
                if client is None:
                    client = self.bulk_tmdb_client()
                automatic = row.get('bulk_automatic', False)
                if automatic:
                    current = client.movie(tmdb_id)
                    if (self._bulk_candidate_fingerprint(current) != row['candidate_fingerprint'] or
                            not self._bulk_proof_current(client, current, row.get('tmdb_proof', {}))):
                        raise IPTVSelectionError('skipped', 'TMDB evidence changed after verification.')
                    movie = normalize_tmdb_movie(current)
                else:
                    movie = client.normalized_movie(tmdb_id)
                if movie.get('tmdb_id') != tmdb_id:
                    raise ValueError('TMDB returned a different identity.')
                self.store.apply_match(f'source:{key}', movie, manual=not automatic, method='chatgpt-bulk',
                    confidence=row['confidence'], evidence=row['evidence'], expected_category=row['previous_category'],
                    expected_generation=generation, preserve_match_lock=True, preserve_classification_lock=True,
                    stable_projection=True, bulk_operation_id=operation_id, stop_requested=stop_requested,
                    expected_source_revision=row.get('source_revision'), expected_match_revision=row.get('match_revision'),
                    bulk_automatic=automatic)
                outcome = 'applied'
            except IPTVSelectionError as error:
                if operation_id and error.code in ('iptv_selection_changed', 'bulk_apply_stopped'):
                    halted = error.code
                    continue
                outcome, message = error.code if operation_id else 'failed', self.metadata_settings.redact(error)
            except KeyError:
                outcome, message = 'skipped', 'The source is no longer available.'
            except (ValueError, IPTVTMDBError, sqlite3.OperationalError) as error:
                outcome, message = 'failed', self.metadata_settings.redact(error)
                retryable = isinstance(error, sqlite3.OperationalError) or (
                    isinstance(error, IPTVTMDBError) and (error.retryable or error.status in (408, 429, 500, 502, 503, 504)))
            outcomes.append((row, outcome, message, retryable))
            report[outcome].append({'source_key': key, 'error': message} if outcome == 'failed' else key)
        if operation_id:
            report.update(outcomes=outcomes, halted=halted)
        return report

    def _proposal_for_source(self, source_key_value, client, *, method="tmdb", ai_ranker=None, ai_title_hints=None):
        source = self.store.source(source_key_value)
        if not source:
            raise KeyError("IPTV movie source was not found")
        if source.get("category") != "film":
            return {"candidate_tmdb_id": 0, "recommendation": "skipped", "confidence": 0,
                    "evidence": {"classification": source.get("category")},
                    "warnings": ["Only Film sources can be matched to TMDB"]}
        with self.store.connection() as connection:
            match = connection.execute("SELECT * FROM source_matches WHERE source_key=?", (source_key_value,)).fetchone()
        if match and match["manual_lock"]:
            return {"candidate_tmdb_id": 0, "recommendation": "locked", "confidence": 0,
                    "evidence": {}, "warnings": ["Manual match lock is preserved"]}
        parsed = self._source_title_evidence(source)
        candidates, attempts = bounded_search_candidates(client, parsed)
        decision = choose_automatic_match(parsed, parsed.get("year"), candidates)
        scored = decision.get("candidates") or []
        chosen = decision.get("accepted") or (scored[0] if scored and float(scored[0].get("match_score") or 0) >= 78 else None)
        warnings = []
        search_hints = []

        def eligible(rows):
            year = parsed.get('year') or 0
            return [row for row in rows if row['match_score'] >= 78 and
                    (not year or not (release := extract_year(row.get('release_date') or row.get('year'))) or abs(release - year) <= 1)]

        if ai_ranker:
            shortlist = eligible(scored)
            if not shortlist and ai_title_hints:
                search_hints = ai_title_hints(source_key_value, {
                    'title': str(source.get('provider_title') or '')[:240],
                    'year': parsed.get('year') or 0, 'aliases': parsed.get('aliases', [])[:6],
                })
                previous_aliases = set(parsed.get('aliases') or [])
                queries = list(dict.fromkeys(clean_provider_title(hint, parsed.get('year')) for hint in search_hints))
                queries = [query for query in queries if query and query not in previous_aliases]
                if queries:
                    extra_candidates, extra_attempts = bounded_search_candidates(client, parsed, search_aliases=queries)
                    attempts += extra_attempts
                    candidates = list({row['id']: row for row in [*candidates, *extra_candidates]}.values())
                    decision = choose_automatic_match(parsed, parsed.get('year'), candidates)
                    scored = decision['candidates']
                    shortlist = eligible(scored)
            candidates_for_ai = shortlist
            chosen = None
        else:
            candidates_for_ai = candidates
        if method == "ai" and candidates_for_ai:
            if not ai_ranker and not self.ollama_runner:
                raise RuntimeError("IPTV Ollama matching is unavailable")
            bounded = [{
                "tmdb_id": int(row.get("id") or 0), "title": str(row.get("title") or "")[:240],
                "original_title": str(row.get("original_title") or "")[:240],
                "year": extract_year(row.get("release_date") or row.get("year")),
                "deterministic_score": score_candidate(parsed, parsed.get("year"), row),
                **({'aliases': [alias[:240] for alias in candidate_title_aliases(row)[:6]]} if ai_ranker else {}),
            } for row in candidates_for_ai[:8]]
            response = (ai_ranker or self.ollama_runner)({
                "mode": "rank-real-tmdb-candidates", "title": str(source.get("provider_title") or "")[:240],
                "year": int((parsed.get('year') if ai_ranker else source.get('provider_year')) or 0),
                "aliases": [alias[:240] for alias in (parsed.get('aliases') or [])[:6]],
                "candidates": bounded,
            })
            if isinstance(response, str):
                response = json.loads(response)
            if not isinstance(response, dict):
                raise ValueError("Ollama match output must be structured JSON")
            ai_id = int(response.get("tmdb_id") or 0)
            if ai_ranker and ai_id == 0:
                return {'candidate_tmdb_id': 0, 'recommendation': 'no-match', 'confidence': 0,
                    'evidence': {'parsed': parsed, 'attempts': attempts, 'candidate_count': len(bounded), 'method': 'chatgpt', 'search_hints': search_hints},
                    'warnings': ['AI ranking declined an identity; explicit review remains available']}
            allowed_ids = {row['tmdb_id'] for row in bounded} if ai_ranker else None
            allowed = {int(row.get("id") or 0): row for row in candidates if allowed_ids is None or int(row.get('id') or 0) in allowed_ids}
            if ai_id not in allowed:
                raise _RejectedAICandidate('ChatGPT proposed an identity outside the actually supplied candidate set' if ai_ranker else
                                 "Ollama proposed an identity outside the validated TMDB candidate set")
            candidate = next((row for row in scored if int(row.get("id") or 0) == ai_id), None)
            if not candidate or float(candidate.get("match_score") or 0) < 78:
                raise _RejectedAICandidate('ChatGPT proposed a candidate rejected by deterministic validation' if ai_ranker else
                                 "Ollama proposed a candidate rejected by deterministic validation")
            chosen = candidate
            warnings.append("AI ranking is advisory; explicit apply is still required")
        if not chosen:
            result = ('candidate-rejected' if candidates else 'no-candidates') if ai_ranker else 'no-match'
            return {"candidate_tmdb_id": 0, "recommendation": result, "confidence": 0,
                    "evidence": {"parsed": parsed, "attempts": attempts, "candidate_count": len(candidates), "search_hints": search_hints},
                    "warnings": warnings}
        confidence = float(chosen.get("match_score") or score_candidate(parsed, parsed.get("year"), chosen))
        recommendation = "recommended" if decision.get("accepted") and int(decision["accepted"].get("id") or 0) == int(chosen.get("id") or 0) else "review"
        return {
            "candidate_tmdb_id": int(chosen.get("id") or 0), "recommendation": recommendation,
            "confidence": confidence, "warnings": warnings,
            "evidence": {
                "parsed": parsed, "attempts": attempts,
                "candidate": {"tmdb_id": int(chosen.get("id") or 0), "title": chosen.get("title") or chosen.get("original_title") or "", "year": extract_year(chosen.get("release_date") or chosen.get("year"))},
                "runner_up_gap": confidence - float(scored[1].get("match_score") or 0) if len(scored) > 1 else None,
                "method": method,
                "search_hints": search_hints,
            },
        }

    def create_match_job(self, payload=None, *, ai_ranker=None, ai_title_hints=None, selection_snapshot=None, resume_job_id=None,
                         on_created=lambda job_id: None, on_progress=None, ai_provenance=None):
        payload = payload if isinstance(payload, dict) else {}
        method = str(payload.get("method") or "tmdb").strip().lower()
        if method not in {"tmdb", "ai"}:
            raise ValueError("IPTV movie matching method must be tmdb or ai")
        selection = selection_snapshot or self.store.resolve_selection(
            mode=payload.get("selection_mode") or "explicit",
            selected_keys=payload.get("selected_keys") or [], filters=payload.get("filters") or {},
            page=payload.get("page", 1), page_size=payload.get("page_size", 50),
        )
        if selection_snapshot and selection['catalog_generation'] != self.store.source_generation():
            raise ValueError('The provider catalog changed; create a new match preview')
        if resume_job_id:
            previous = self.store.resume_proposal_job(resume_job_id, selection)
            completed = {row['source_key'] for row in previous['proposals']}
            job_id = resume_job_id
        else:
            job_id = self.store.create_proposal_job(method=method, selection=selection)
            completed = set()
        on_created(job_id)
        client = None
        processed = len(completed)
        try:
            for key in selection["source_keys"]:
                if key in completed:
                    continue
                source = self.store.source(key)
                if source and source.get("category") == "film" and client is None:
                    client = _CachingTMDBClient(self.tmdb_client_factory())
                try:
                    proposal = self._proposal_for_source(key, client, method=method, ai_ranker=ai_ranker,
                                                         ai_title_hints=ai_title_hints)
                except Exception as error:
                    if not ai_ranker or not (isinstance(error, _RejectedAICandidate) or
                                             getattr(error, 'code', None) == 'invalid_iptv_result'):
                        raise
                    proposal = {'candidate_tmdb_id': 0, 'recommendation': 'candidate-rejected', 'confidence': 0,
                                'warnings': ['ChatGPT did not return an eligible result for this source.']}
                if ai_ranker:
                    proposal['evidence'] = {**proposal.get('evidence', {}), 'ai_provenance': dict(ai_provenance or {})}
                self.store.save_proposal(job_id, key, **proposal)
                processed += 1
                if on_progress:
                    on_progress(processed)
            return self.store.finish_proposal_job(job_id, state="ready")
        except Exception as error:
            if ai_ranker and getattr(error, 'code', None) in ('paused_budget', 'job_not_running', 'cancelled'):
                raise  # Existing proposals stay unapplyable until explicit continuation completes them.
            self.store.finish_proposal_job(job_id, state="failed", error=self.metadata_settings.redact(error))
            raise

    def match_job(self, job_id):
        return self.store.proposal_job(job_id)

    def cancel_match_job(self, job_id):
        return self.store.finish_proposal_job(job_id, state="cancelled")

    def apply_match_job(self, job_id, payload=None):
        payload = payload if isinstance(payload, dict) else {}
        job = self.store.proposal_job(job_id)
        if job["state"] != "ready":
            raise ValueError("This IPTV movie proposal job is not ready to apply")
        if int(job["catalog_generation"]) != self.store.source_generation():
            raise ValueError("The provider catalog changed; create a new proposal preview")
        selected = set(str(value or "") for value in payload.get("proposal_ids") or [])
        if not selected:
            raise ValueError("Select at least one IPTV movie proposal to apply")
        client = self.tmdb_client_factory()
        report = {"applied": [], "skipped": [], "locked": [], "failed": []}
        for proposal in job["proposals"]:
            proposal_id = proposal["proposal_id"]
            if proposal_id not in selected:
                report["skipped"].append(proposal_id)
                continue
            if proposal.get("match_manual_lock") or proposal.get("category") != "film":
                self.store.mark_proposal_apply(proposal_id, "locked", "Manual lock or non-Film classification")
                report["locked"].append(proposal_id)
                continue
            tmdb_id = int(proposal.get("candidate_tmdb_id") or 0)
            if tmdb_id <= 0:
                self.store.mark_proposal_apply(proposal_id, "rejected", "No credible TMDB candidate")
                report["skipped"].append(proposal_id)
                continue
            try:
                snapshot = client.normalized_movie(tmdb_id)
                if int(snapshot.get('tmdb_id') or 0) != tmdb_id:
                    raise ValueError('TMDB returned a different identity')
                self.store.apply_match(
                    f"source:{proposal['source_key']}", snapshot, manual=True,
                    method=f"bulk-{job['method']}", confidence=proposal.get("confidence") or 100,
                    evidence={"proposal_id": proposal_id, "job_id": job_id},
                    expected_category='film', preserve_match_lock=True,
                    expected_generation=int(job['catalog_generation']),
                )
                self.store.mark_proposal_apply(proposal_id, "applied", f"TMDB {tmdb_id}")
                report["applied"].append(proposal_id)
            except Exception as error:
                message = self.metadata_settings.redact(error)
                self.store.mark_proposal_apply(proposal_id, "failed", message)
                report["failed"].append({"proposal_id": proposal_id, "error": message})
        self.store.finish_proposal_job(job_id, state="complete")
        return {**report, "job": self.store.proposal_job(job_id)}

    def rebuild_preview(self, payload=None):
        payload = payload if isinstance(payload, dict) else {}
        playlist_samples = {}
        all_rows = []
        offset = 0
        while True:
            rows = self.store.classification_rows(only_pending=False, limit=1000, offset=offset)
            if not rows:
                break
            all_rows.extend(rows)
            for row in rows:
                bucket = playlist_samples.setdefault(
                    row.get("playlist_id") or "", {"name": row.get("playlist_name") or "", "titles": []}
                )
                if len(bucket["titles"]) < 25:
                    bucket["titles"].append(row.get("provider_title") or "")
            offset += len(rows)
        playlist_decisions = {
            key: classify_playlist(value["name"], value["titles"])
            for key, value in playlist_samples.items()
        }
        items = []
        transition_names = (
            "old-automatic-accepted-still-accepted",
            "old-automatic-accepted-now-non-film",
            "old-automatic-accepted-now-review-or-unmatched",
            "old-unmatched-or-review-newly-accepted",
            "classification-changed",
            "parser-or-evidence-changed",
            "unchanged-unresolved",
            "technical-failure",
            "manual-lock-preserved",
        )
        transitions = {name: [] for name in transition_names}
        classification_counts = {category: 0 for category in ("film", "sports", "plays", "music", "misc", "unclassified")}
        with self.store.connection() as connection:
            matches = {
                row["source_key"]: dict(row)
                for row in connection.execute("SELECT * FROM source_matches")
            }
            cached_movies = {}
            for snapshot_row in connection.execute(
                "SELECT tmdb_id,title,original_title,year,release_date,raw_json FROM tmdb_movies"
            ):
                row = dict(snapshot_row)
                try:
                    payload_row = json.loads(row.get("raw_json") or "{}")
                except json.JSONDecodeError:
                    payload_row = {}
                if not isinstance(payload_row, dict):
                    payload_row = {}
                payload_row.setdefault("id", row["tmdb_id"])
                payload_row.setdefault("title", row["title"])
                payload_row.setdefault("original_title", row["original_title"])
                payload_row.setdefault("release_date", row["release_date"] or (str(row["year"]) if row["year"] else ""))
                cached_movies[int(row["tmdb_id"])] = payload_row
            cached_aliases = {}
            for alias_row in connection.execute(
                """SELECT normalized_text,tmdb_id FROM movie_search_aliases
                   WHERE source_key='' AND tmdb_id>0 ORDER BY tmdb_id"""
            ):
                cached_aliases.setdefault(alias_row["normalized_text"], []).append(int(alias_row["tmdb_id"]))
        for row in all_rows:
            match = matches.get(row["source_key"]) or {}
            try:
                decision = classify_source(
                    row.get("provider_title") or "", row.get("playlist_name") or "",
                    playlist_decision=playlist_decisions.get(row.get("playlist_id") or ""),
                    manual_category=(row.get("category") or "").title(),
                    manual_lock=bool(row.get("classification_manual_lock")),
                )
                proposed_category = self._store_category(decision.get("category"))
                previous_category = self._store_category(row.get("category"))
                previous_state = str(match.get("state") or "unprocessed")
                parsed = combine_provider_title_evidence(
                    row.get("provider_title"), row.get("provider_year"),
                    row.get("detail_title"), row.get("detail_year"),
                )
                shadow = {"state": "not-applicable", "candidate_tmdb_id": 0, "candidate_count": 0}
                if row.get("classification_manual_lock") or match.get("manual_lock"):
                    transition = "manual-lock-preserved"
                    proposed_category = previous_category
                    proposed_state = previous_state
                elif previous_state == "matched-auto" and proposed_category != "film":
                    transition = "old-automatic-accepted-now-non-film"
                    proposed_state = "unprocessed"
                elif previous_state == "matched-auto" and proposed_category == "film":
                    current_id = int(match.get("tmdb_id") or 0)
                    candidate = cached_movies.get(current_id)
                    shadow_decision = choose_automatic_match(parsed, parsed.get("year"), [candidate] if candidate else [])
                    accepted = shadow_decision.get("accepted") or {}
                    if int(accepted.get("id") or 0) == current_id:
                        transition = "old-automatic-accepted-still-accepted"
                        shadow = {"state": "accepted", "candidate_tmdb_id": current_id, "candidate_count": 1}
                    else:
                        transition = "old-automatic-accepted-now-review-or-unmatched"
                        shadow = {"state": shadow_decision.get("state") or "unmatched", "candidate_tmdb_id": 0, "candidate_count": int(bool(candidate))}
                    proposed_state = "unprocessed"
                elif proposed_category == "film":
                    candidate_ids = []
                    for alias in parsed.get("aliases") or []:
                        for tmdb_id in cached_aliases.get(normalize_search_text(alias), []):
                            if tmdb_id not in candidate_ids:
                                candidate_ids.append(tmdb_id)
                            if len(candidate_ids) >= 20:
                                break
                        if len(candidate_ids) >= 20:
                            break
                    candidates = [cached_movies[tmdb_id] for tmdb_id in candidate_ids if tmdb_id in cached_movies]
                    shadow_decision = choose_automatic_match(parsed, parsed.get("year"), candidates)
                    accepted = shadow_decision.get("accepted") or {}
                    if int(accepted.get("id") or 0):
                        transition = "old-unmatched-or-review-newly-accepted"
                        shadow = {"state": "accepted", "candidate_tmdb_id": int(accepted["id"]), "candidate_count": len(candidates)}
                    else:
                        transition = "unchanged-unresolved"
                        shadow = {"state": shadow_decision.get("state") or "unmatched", "candidate_tmdb_id": 0, "candidate_count": len(candidates)}
                    proposed_state = "unprocessed"
                else:
                    transition = "unchanged-unresolved"
                    proposed_state = "unprocessed"
                transitions[transition].append(row["source_key"])
                if proposed_category != previous_category:
                    transitions["classification-changed"].append(row["source_key"])
                if (
                    int(match.get("parser_version") or 0) != PARSER_VERSION
                    or int(match.get("matcher_version") or 0) != MATCHER_VERSION
                    or int(match.get("classifier_version") or 0) != CLASSIFIER_VERSION
                ):
                    transitions["parser-or-evidence-changed"].append(row["source_key"])
            except Exception as error:
                previous_category = self._store_category(row.get("category"))
                proposed_category = previous_category
                previous_state = str(match.get("state") or "unprocessed")
                proposed_state = previous_state
                transition = "technical-failure"
                transitions[transition].append(row["source_key"])
                decision = {"evidence": {}, "review_reason": self.metadata_settings.redact(error)}
                shadow = {"state": "failed", "candidate_tmdb_id": 0, "candidate_count": 0}
            classification_counts[proposed_category] = classification_counts.get(proposed_category, 0) + 1
            items.append({
                "source_key": row["source_key"], "previous_classification": previous_category,
                "proposed_classification": proposed_category, "previous_match_state": previous_state,
                "proposed_match_state": proposed_state, "transition": transition,
                "evidence": {
                    "classification": decision.get("evidence") or {},
                    "classification_review_reason": decision.get("review_reason") or "",
                    "shadow_match": shadow,
                    "parser_version": PARSER_VERSION,
                    "matcher_version": MATCHER_VERSION,
                    "classifier_version": CLASSIFIER_VERSION,
                },
            })
        report = {
            "source_total": len(items),
            "classification_counts": classification_counts,
            "transition_counts": {key: len(values) for key, values in transitions.items()},
            "transition_keys": transitions,
            "manual_locks_preserved": len(transitions.get("manual-lock-preserved", [])),
            "note": "Preview only. No accepted identity, classification, queue, list, favorite, history, playback, or raw provider state changed.",
        }
        return self.store.create_rebuild_job(items, report, scope=payload.get("scope") or {"automatic": True})

    def rebuild_job(self, job_id):
        return self.store.rebuild_job(job_id)

    def cancel_rebuild(self, job_id):
        return self.store.set_rebuild_state(job_id, "cancelled")

    def apply_rebuild(self, job_id, payload=None):
        payload = payload if isinstance(payload, dict) else {}
        if str(os.environ.get("CP_TEST_MODE") or "") != "1":
            raise RuntimeError("Live IPTV Movies rebuild apply requires separate Gate 9 approval")
        declared_root = Path(os.environ.get("CP_TEST_ROOT") or "").resolve()
        try:
            self.root.relative_to(declared_root)
        except (ValueError, OSError):
            raise RuntimeError("Disposable rebuild apply must stay inside CP_TEST_ROOT")
        job = self.store.rebuild_job(job_id)
        if job["state"] not in {"ready", "applying"}:
            raise ValueError("This IPTV Movies rebuild is not ready to apply")
        if int(job["catalog_generation"]) != self.store.source_generation():
            raise ValueError("The provider catalog changed; create a new rebuild preview")
        if str(payload.get("confirm_provider_id") or "") != self.provider_id:
            raise ValueError("Confirm the selected provider before applying its rebuild")
        self.store.set_rebuild_state(job_id, "applying")
        report = {"applied": 0, "locked": 0, "failed": []}
        while True:
            pending = self.store.rebuild_pending_items(job_id, limit=500)
            if not pending:
                break
            for source_key_value in pending:
                try:
                    state = self.store.apply_rebuild_item(job_id, source_key_value)
                    report[state] = report.get(state, 0) + 1
                except Exception as error:
                    report["failed"].append({"source_key": source_key_value, "error": self.metadata_settings.redact(error)})
                    break
            if report["failed"]:
                break
        state = "failed" if report["failed"] else "complete"
        return {**report, "job": self.store.set_rebuild_state(job_id, state, error=report["failed"][0]["error"] if report["failed"] else "")}

    def close(self):
        self._closing = True
        with self._process_lock:
            process = self._processes.pop(self.provider_id, None)
        if process is not None and process.poll() is None:
            if self.database_path.is_file():
                try:
                    self.store.worker_command("pause")
                except (RuntimeError, sqlite3.Error):
                    pass
            deadline = time.monotonic() + self.WORKER_GRACEFUL_STOP_SECONDS
            while process.poll() is None and time.monotonic() < deadline:
                time.sleep(0.05)
            if process.poll() is None:
                process.terminate()
                deadline = time.monotonic() + self.WORKER_FORCED_STOP_SECONDS
                while process.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.05)
            if process.poll() is None and hasattr(process, "kill"):
                process.kill()
            if self.database_path.is_file():
                try:
                    self.store.checkpoint_paused_after_stop(
                        "Stopped safely during Cinema Paradiso shutdown"
                    )
                except (RuntimeError, sqlite3.Error):
                    pass
        with self._process_lock:
            self._instances.pop(self.provider_id, None)


def _tmdb_record_if_found(fetch, tmdb_id, **options):
    try:
        return fetch(tmdb_id, **options)
    except IPTVTMDBError as error:
        if error.status != 404:
            raise
        return None


def classify_enrichment_error(error):
    if isinstance(error, IPTVTMDBError):
        if error.status == 401:
            return "error-terminal", "authentication", False, 0
        if error.status == 429:
            return "error-retryable", "rate-limit", True, max(1, error.retry_after)
        return (
            "error-retryable" if error.retryable else "error-terminal",
            "tmdb",
            bool(error.retryable),
            30 if error.retryable else 0,
        )
    if isinstance(error, (XtreamError, TimeoutError, OSError)):
        return "error-retryable", "provider", True, 30
    return "error-terminal", "unexpected", False, 0
