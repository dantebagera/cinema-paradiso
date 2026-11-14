"""Authoritative reconciliation coordinator.

This module owns work normalization, bounded submission, stability, targeted
traversal, full inventory reconciliation, and retry-loop ordering. Domain
identity and metadata decisions remain injected from their established owners.
"""

import collections
import hashlib
import json
import os
import threading
import time
import uuid
from dataclasses import dataclass
from contextlib import nullcontext


class StaleReconciliationResult(RuntimeError):
    pass


class RetryRevisionChanged(RuntimeError):
    pass


def file_is_readable(path):
    try:
        with open(path, "rb") as stream:
            stream.read(1)
        return True
    except (OSError, PermissionError):
        return False


def file_copy_is_stable(
    file_facts,
    previous=None,
    now=None,
    *,
    stability_seconds=15.0,
    wall_time=time.time,
):
    previous = previous or {}
    now = wall_time() if now is None else float(now)
    size = int(file_facts.get("size") or 0)
    modified_time = float(file_facts.get("modified_time") or 0)
    if modified_time and now - modified_time >= stability_seconds:
        return True
    same_observation = (
        int(previous.get("observed_size") or -1) == size
        and float(previous.get("observed_modified_time") or -1) == modified_time
    )
    observed_at = float(previous.get("observed_at") or 0)
    return bool(
        same_observation
        and observed_at
        and now - observed_at >= stability_seconds
    )


@dataclass(frozen=True)
class LibraryIngestionDependencies:
    store: object
    roots: object
    iter_video_files: object
    metadata_file_facts: object
    stability_check: object
    reconcile_path: object
    active_metadata_provider: object
    migrate_metadata_path: object
    resolve_authoritative_identity: object
    record_has_unresolved_identity: object
    record_needs_metadata_enrichment: object
    accepted_identity_evidence_changed: object
    identity_evidence_fingerprint: object
    record_needs_identity_decision_refresh: object
    plex_data: object
    plex_rescan: object
    auto_sync_plex: object
    inventory_bootstrap_cutoff: object
    clear_library_cache: object
    run_detail_backfill: object
    run_file_facts_backfill: object
    read_state: object
    write_state: object
    mark_complete: object
    identity_decision_version: int
    video_extensions: frozenset
    stability_seconds: float = 15.0
    sleep: object = time.sleep
    wall_time: object = time.time
    monotonic: object = time.monotonic
    readable_check: object = file_is_readable
    final_card_publication: object = lambda paths: []
    publish_catalog_event: object = lambda **kwargs: False
    apply_identity_hint: object = lambda path, identity, facts, store=None: False
    prepare_final_card_assets: object = lambda paths: None
    retry_repository: object = lambda: None
    resolve_source_identity: object = lambda source: {"state": "deferred", "paths": []}


class LibraryIngestionCoordinator:
    QUEUE_CAPACITY = 4096
    COALESCE_SECONDS = 0.5
    MAX_STABILITY_SECONDS = 24 * 60 * 60
    RETRY_DELAYS = (1, 2, 4, 8, 15)
    ASSET_RETRY_DELAYS = (2, 10, 30)

    def __init__(self, dependencies):
        self.dependencies = dependencies
        self._run_lock = threading.RLock()
        self._queue_condition = threading.Condition(threading.RLock())
        self._pending = collections.OrderedDict()
        self._dirty_roots = set()
        self._accepting = True
        self._dispatcher = None
        self._active = None
        self._last_result = {}
        self._last_error = ""
        self._identity_hints = {}
        self._volatile_episodes = {}
        self._admission_order = 0
        self._episode_local = threading.local()
        self._startup_waiting = False
        self._running_paths = set()
        self._followup_paths = {}

    @staticmethod
    def normalize_path(path):
        return os.path.normcase(os.path.normpath(os.path.abspath(str(path or ""))))

    def _root_for_path(self, path):
        normalized = self.normalize_path(path)
        for configured in self.dependencies.roots():
            root = self.normalize_path(configured)
            try:
                if os.path.commonpath((normalized, root)) == root:
                    return os.path.abspath(str(configured))
            except ValueError:
                continue
        return ""

    def _validate_path(self, path, *, require_directory=False):
        absolute = os.path.abspath(str(path or ""))
        root = self._root_for_path(absolute)
        if not root:
            raise ValueError(f"Path is outside configured library roots: {absolute}")
        if require_directory:
            if not os.path.isdir(absolute):
                raise ValueError(f"Library directory is unavailable: {absolute}")
        elif os.path.splitext(absolute)[1].lower() not in self.dependencies.video_extensions:
            raise ValueError(f"Path is not a supported video file: {absolute}")
        return absolute, root

    @classmethod
    def _contains_path(cls, parent, child):
        parent = cls.normalize_path(parent)
        child = cls.normalize_path(child)
        try:
            return os.path.commonpath((parent, child)) == parent
        except ValueError:
            return False

    def file_copy_is_stable(self, file_facts, previous=None, now=None):
        return self.dependencies.stability_check(file_facts, previous, now)

    def reconcile_path_now(self, path, provider=None, store=None, previous=None):
        store = store or self.dependencies.store()
        previous = previous or {}
        provider = provider or self.dependencies.active_metadata_provider(store)
        observation = self.dependencies.metadata_file_facts(path, probe=False)
        publication_pending = bool(previous.get('_require_publication')) or not (
            previous.get("identity_status") == "accepted"
            or bool(previous.get("metadata_accepted"))
        )
        if publication_pending:
            observation["movie_view_publication"] = (
                previous.get("movie_view_publication") or "pending"
            )
        if not self.file_copy_is_stable(observation, previous):
            pending_patch = {
                **observation,
                "ingest_status": "pending",
                "observed_size": observation.get("size", 0),
                "observed_modified_time": observation.get("modified_time", 0),
                "observed_at": self.dependencies.wall_time(),
            }
            if not self.dependencies.resolve_authoritative_identity(previous).get("accepted"):
                pending_patch.update({
                    "metadata_status": "pending",
                    "metadata_accepted": False,
                })
            store.update_file_record(path, pending_patch)
            return "pending"

        if not self.dependencies.readable_check(path):
            store.update_file_record(path, {
                **observation,
                "ingest_status": "pending",
                "observed_size": observation.get("size", 0),
                "observed_modified_time": observation.get("modified_time", 0),
                "observed_at": self.dependencies.wall_time(),
                "probe_error": "file_not_readable",
            })
            return "pending"

        reusable = (
            previous.get('probe_status') == 'ok'
            and previous.get('probe_size') == observation.get('size')
            and previous.get('probe_modified_time') == observation.get('modified_time')
            and not previous.get('probe_error')
        )
        from services.media_file_facts import FILE_FACTS_VERSION, QUALITY_CLASSIFIER_VERSION, MediaFileFacts
        reusable = reusable and previous.get('file_facts_version') == FILE_FACTS_VERSION and previous.get('classifier_version') == QUALITY_CLASSIFIER_VERSION
        measured = {key: previous[key] for key in MediaFileFacts().as_record() if key in previous}
        facts = {**measured, **observation} if reusable else self.dependencies.metadata_file_facts(path, probe=True)
        facts.update({
            "ingest_status": "stable",
            "observed_size": facts.get("size", 0),
            "observed_modified_time": facts.get("modified_time", 0),
            "observed_at": self.dependencies.wall_time(),
        })
        if publication_pending:
            facts["movie_view_publication"] = (
                previous.get("movie_view_publication") or "pending"
            )
        probe_status = str(facts.get("probe_status") or "unprobed")
        if probe_status != "ok":
            retryable = probe_status in {"unprobed", "inaccessible", "file_changed"}
            store.update_file_record(path, {
                **facts,
                "ingest_status": "pending" if retryable else "failed",
                "metadata_status": "pending" if retryable else "failed",
                "metadata_accepted": False,
            })
            return "pending" if retryable else "failed"
        path_key = self.normalize_path(path)
        identity_hint = self._identity_hints.get(path_key)
        if identity_hint:
            try:
                if hasattr(store, '_check_reconciliation_guard'):
                    current = store.catalog.get_record('app_metadata/files.json', store._key(path), {})
                    store._check_reconciliation_guard(path, current)
                if self.dependencies.apply_identity_hint(path, identity_hint, facts, store=store):
                    self._identity_hints.pop(path_key, None)
                    return "matched"
            except StaleReconciliationResult:
                raise
        if self.dependencies.resolve_authoritative_identity(previous).get('accepted') and not previous.get('_revalidate_identity'):
            context = store.snapshot_for_paths([path])
            if not self.dependencies.record_needs_metadata_enrichment(previous, store._key(path), context):
                store.update_file_record(path, facts)
                return 'matched'
            if provider == 'filename' and previous.get('display_provider') in {'tmdb', 'plex'}:
                provider = previous['display_provider']
        if provider == "filename":
            store.update_file_record(path, {
                **facts,
                "display_provider": "filename",
                "metadata_status": "unmatched",
                "metadata_source": "filename",
                "metadata_accepted": False,
                "ingest_status": "stable",
                "identity_decision_version": self.dependencies.identity_decision_version,
                "observed_size": facts.get("size", 0),
                "observed_modified_time": facts.get("modified_time", 0),
                "observed_at": self.dependencies.wall_time(),
            })
            return "review"

        outcome = self.dependencies.migrate_metadata_path(
            path,
            provider,
            store=store,
            revalidate_accepted=bool(previous.get("_revalidate_identity")),
            facts=facts,
        )
        patch = {
            **facts,
            "ingest_status": "stable",
            "observed_size": facts.get("size", 0),
            "observed_modified_time": facts.get("modified_time", 0),
            "observed_at": self.dependencies.wall_time(),
        }
        if outcome == "review":
            post_migration = store.catalog.get_record("app_metadata/files.json", store._key(path), {})
            post_status = str(post_migration.get("identity_status") or "")
            if post_status == "conflict":
                patch.update({
                    "identity_status": "conflict",
                    "metadata_status": "conflict",
                    "metadata_accepted": False,
                    "identity_decision_version": self.dependencies.identity_decision_version,
                })
            elif post_status == "unmatched":
                patch.update({
                    "metadata_status": "unmatched",
                    "metadata_accepted": False,
                    "identity_decision_version": self.dependencies.identity_decision_version,
                })
            else:
                patch.update({
                    "identity_status": "review",
                    "metadata_status": "needs_review",
                    "metadata_accepted": False,
                    "identity_decision_version": self.dependencies.identity_decision_version,
                })
        elif outcome == "failed":
            patch.update({
                "metadata_status": "unmatched",
                "metadata_accepted": False,
                "identity_decision_version": self.dependencies.identity_decision_version,
            })
        store.update_file_record(path, patch)
        return outcome

    @staticmethod
    def _result(provider, removed=0):
        return {
            "checked": 0,
            "matched": 0,
            "review": 0,
            "pending": 0,
            "failed": 0,
            "removed": int(removed),
            "facts_refreshed": 0,
            "provider": provider,
        }

    def _candidate_for_path(
        self,
        path,
        filename,
        fingerprint,
        record,
        snapshot,
        provider,
        *,
        force_unresolved=False,
        enrich_accepted=True,
        inventory_exists=True,
        previous_inventory=None,
        bootstrap_cutoff=0,
    ):
        key = self.dependencies.store()._key(path)
        if record.get("metadata_accepted") or record.get("metadata_status") == "accepted":
            facts_changed = (
                int(record.get("size") or -1) != fingerprint["size"]
                or float(record.get("modified_time") or -1) != fingerprint["modified_time"]
                or (bool(record.get("filename")) and record.get("filename") != filename)
            )
            facts = record
            if facts_changed:
                facts = self.dependencies.metadata_file_facts(path, probe=False)
            plex_data = self.dependencies.plex_data(key, filename, snapshot)
            if provider in {"tmdb", "plex"} and self.dependencies.accepted_identity_evidence_changed(
                path, record, facts, plex_data
            ):
                return {**record, "_revalidate_identity": True}
            if facts_changed:
                return {**record, "_refresh_file_facts": True}
            if enrich_accepted and provider in {"tmdb", "plex"} and self.dependencies.record_needs_metadata_enrichment(
                facts, key, snapshot
            ):
                return facts
            return None
        if force_unresolved and self.dependencies.record_has_unresolved_identity(record):
            return record
        current_identity_fingerprint = ""
        if self.dependencies.record_has_unresolved_identity(record):
            file_facts = self.dependencies.metadata_file_facts(path, probe=False)
            current_identity_fingerprint = self.dependencies.identity_evidence_fingerprint(
                path,
                file_facts,
                self.dependencies.plex_data(key, file_facts.get("filename", filename), snapshot),
            )
        if self.dependencies.record_needs_identity_decision_refresh(
            record, current_identity_fingerprint
        ):
            return record
        if not record or record.get("metadata_status") == "pending":
            return record
        if not inventory_exists:
            changed = (
                bool(record)
                and (
                int(record.get("size") or -1) != fingerprint["size"]
                or float(record.get("modified_time") or -1) != fingerprint["modified_time"]
                )
            )
            try:
                newly_added = os.path.getctime(path) > bootstrap_cutoff
            except OSError:
                newly_added = False
            return record if changed or (not record and newly_added) else None
        previous = (previous_inventory or {}).get(key, {})
        changed = (
            not previous
            or int(previous.get("size") or -1) != fingerprint["size"]
            or float(previous.get("modified_time") or -1) != fingerprint["modified_time"]
        )
        return record if changed else None

    def _prepare_provider(self, provider, candidates):
        if provider == "plex" and candidates:
            self.dependencies.plex_rescan()
            self.dependencies.sleep(1)
            self.dependencies.auto_sync_plex(force=True)

    @staticmethod
    def _inventory_exists(store):
        owner = getattr(store, "has_library_inventory", None)
        if callable(owner):
            return bool(owner())
        return bool(store.library_inventory_file.exists())

    def _process_candidates(self, candidates, provider, store, result):
        matched_paths = []
        for path, previous in candidates:
            if self.dependencies.retry_repository() is not None and not getattr(self._episode_local, 'reserved', False):
                item = {'type': 'path', 'value': str(path), 'reason': 'reconcile', 'correlation_id': str(uuid.uuid4()), 'require_publication': bool(previous.get('_require_publication') or previous.get('movie_view_publication') == 'pending')}
                nested, due = self._run_path_episode(item)
                for field in ('checked', 'matched', 'review', 'pending', 'failed', 'removed', 'facts_refreshed'):
                    result[field] += int(nested.get(field) or 0)
                if due:
                    self._submit('path', [path], item['reason'], item['correlation_id'], require_publication=item['require_publication'])
                continue
            if previous.get("_refresh_file_facts"):
                guard = getattr(store, 'reconciliation_guard', None)
                try:
                    with guard(path, previous) if callable(guard) else nullcontext():
                        observation = self.dependencies.metadata_file_facts(path, probe=False)
                        if not self.file_copy_is_stable(observation, previous):
                            store.update_file_record(path, {
                                **observation,
                                "ingest_status": "pending",
                                "observed_size": observation.get("size", 0),
                                "observed_modified_time": observation.get("modified_time", 0),
                                "observed_at": self.dependencies.wall_time(),
                            })
                            result["pending"] += 1
                            continue
                        refreshed = self.dependencies.metadata_file_facts(path, probe=True)
                        store.update_file_record(path, {
                            **refreshed,
                            "ingest_status": "stable",
                            "observed_size": refreshed.get("size", 0),
                            "observed_modified_time": refreshed.get("modified_time", 0),
                            "observed_at": self.dependencies.wall_time(),
                        })
                        result["facts_refreshed"] += 1
                        continue
                except StaleReconciliationResult:
                    result['_obsolete'] = True
                    result['pending'] += 1
                    continue
            result["checked"] += 1
            try:
                guard = getattr(store, 'reconciliation_guard', None)
                with guard(path, previous) if callable(guard) else nullcontext():
                    outcome = self.dependencies.reconcile_path(path, provider, store=store, previous=previous)
            except StaleReconciliationResult:
                result['_obsolete'] = True
                outcome = 'pending'
            except Exception as error:
                result['_failure'] = f'{type(error).__name__}: {error}'
                outcome = "failed"
            result[outcome if outcome in result else "failed"] += 1
            if outcome == "matched":
                matched_paths.append(path)
        if result["checked"] or result["removed"]:
            self.dependencies.clear_library_cache()
        result["_matched_paths"] = matched_paths
        return result

    def reconcile_all_now(self, force_unresolved=False, *, enrich_accepted=True, retry_blocked=False):
        with self._run_lock:
            store = self.dependencies.store()
            snapshot = store.snapshot()
            records = snapshot.get("files", {})
            inventory_exists = self._inventory_exists(store)
            previous_inventory = store.get_library_inventory()
            bootstrap_cutoff = (
                self.dependencies.inventory_bootstrap_cutoff(store)
                if not inventory_exists
                else 0
            )
            provider = self.dependencies.active_metadata_provider(store)
            candidates = []
            current_inventory = {}
            for _, _, filename, path in self.dependencies.iter_video_files():
                try:
                    stat_result = os.stat(path)
                except OSError:
                    continue
                key = store._key(path)
                fingerprint = {
                    "path": path,
                    "size": int(stat_result.st_size),
                    "modified_time": float(stat_result.st_mtime),
                }
                current_inventory[key] = fingerprint
                previous = self._candidate_for_path(
                    path,
                    filename,
                    fingerprint,
                    records.get(key, {}),
                    snapshot,
                    provider,
                    force_unresolved=force_unresolved,
                    enrich_accepted=enrich_accepted,
                    inventory_exists=inventory_exists,
                    previous_inventory=previous_inventory,
                    bootstrap_cutoff=bootstrap_cutoff,
                )
                ledger = records.get(key, {}).get('_ingestion_retry') or {}
                if retry_blocked and (ledger.get('state') == 'blocked' or records.get(key, {}).get('ingest_status') == 'failed'):
                    self._rearm_path(path)
                    previous = records.get(key, {})
                if previous is not None:
                    candidates.append((path, previous))

            removed = 0
            roots = [root for root in self.dependencies.roots() if root]
            if roots and all(os.path.isdir(root) for root in roots):
                removed = store.prune_missing_path_records(current_inventory.keys())
            store.save_library_inventory(current_inventory)
            self._prepare_provider(provider, candidates)
            return self._process_candidates(
                candidates, provider, store, self._result(provider, removed)
            )

    def reconcile_paths_now(
        self,
        paths,
        *,
        force_unresolved=False,
        identity_hints=None,
        enrich_accepted=True,
        require_publication=False,
        source_identity=None,
    ):
        with self._run_lock:
            for path, identity in dict(identity_hints or {}).items():
                self._identity_hints[self.normalize_path(path)] = dict(identity or {})
            validated = []
            for path in paths or ():
                absolute, _root = self._validate_path(path)
                if absolute not in validated:
                    validated.append(absolute)
            store = self.dependencies.store()
            snapshot = store.snapshot_for_paths(validated, identity_hints=identity_hints)
            records = snapshot.get("files", {})
            inventory_exists = snapshot.inventory_exists
            inventory = snapshot["inventory"]
            removed_inventory = []
            bootstrap_cutoff = (
                self.dependencies.inventory_bootstrap_cutoff(store)
                if not inventory_exists
                else 0
            )
            provider = self.dependencies.active_metadata_provider(store)
            candidates = []
            removed = 0
            for path in validated:
                key = store._key(path)
                try:
                    stat_result = os.stat(path)
                except OSError:
                    if os.path.isdir(self._root_for_path(path)):
                        if key in records:
                            store.remove_path_records(path)
                            removed += 1
                        inventory.pop(key, None)
                        removed_inventory.append(key)
                    continue
                fingerprint = {
                    "path": path,
                    "size": int(stat_result.st_size),
                    "modified_time": float(stat_result.st_mtime),
                }
                previous = self._candidate_for_path(
                    path,
                    os.path.basename(path),
                    fingerprint,
                    records.get(key, {}),
                    snapshot,
                    provider,
                    force_unresolved=force_unresolved,
                    enrich_accepted=enrich_accepted,
                    inventory_exists=inventory_exists,
                    previous_inventory=inventory,
                    bootstrap_cutoff=bootstrap_cutoff,
                )
                record = records.get(key, {})
                publication_required = require_publication or record.get('movie_view_publication') == 'pending'
                if publication_required:
                    status = store.catalog.publication_status([path]).get(key, {})
                    if not status.get('publication_committed'):
                        previous = {**record, '_require_publication': True}
                inventory[key] = fingerprint
                if previous is not None:
                    candidates.append((path, previous))
            store.catalog.patch_inventory(inventory, removed_inventory)
            self._prepare_provider(provider, candidates)
            return self._process_candidates(
                candidates, provider, store, self._result(provider, removed)
            )

    def reconcile_directories_now(
        self,
        directories,
        *,
        force_unresolved=False,
        enrich_accepted=True,
    ):
        validated = []
        paths = []
        for directory in directories or ():
            absolute, _root = self._validate_path(directory, require_directory=True)
            if absolute not in validated:
                validated.append(absolute)
            for current, _dirs, files in os.walk(absolute):
                for filename in files:
                    if os.path.splitext(filename)[1].lower() in self.dependencies.video_extensions:
                        paths.append(os.path.join(current, filename))
        result = self.reconcile_paths_now(
            paths,
            force_unresolved=force_unresolved,
            enrich_accepted=enrich_accepted,
        )
        if not validated:
            return result
        store = self.dependencies.store()
        current_keys = {store._key(path) for path in paths}
        inventory_keys = store.catalog.path_keys_under_roots(validated, inventory=True)
        store.catalog.patch_inventory({}, [key for key in inventory_keys if key not in current_keys])
        removed = store.prune_missing_path_records(current_keys, roots=validated)
        if removed:
            result["removed"] += removed
            self.dependencies.clear_library_cache()
        return result

    def run_reconcile_loop(
        self,
        run_inventory=True,
        run_detail_backfill=False,
        run_file_facts=False,
    ):
        detail_backfill = (
            self.dependencies.run_detail_backfill()
            if run_detail_backfill
            else dict(self.dependencies.read_state().get("detail_backfill") or {})
        )
        if not run_inventory:
            file_facts = (
                self.dependencies.run_file_facts_backfill()
                if run_file_facts
                else dict(self.dependencies.read_state().get("file_facts_backfill") or {})
            )
            self.dependencies.write_state({
                **self.dependencies.read_state(),
                "status": "completed",
                "detail_backfill": detail_backfill,
                "file_facts_backfill": file_facts,
                "updated_at": self.dependencies.wall_time(),
            })
            self.dependencies.mark_complete()
            return
        result = self.reconcile_all_now()
        state = self.dependencies.read_state()
        finalization = self.finalize_matched_paths(
            result.get("_matched_paths") or [],
            reason=str(state.get("reason") or "startup"),
            correlation_id=str(state.get("correlation_id") or f"startup:{uuid.uuid4()}"),
        )
        if finalization["failures"] and self._accepting:
            self.reconcile_paths(list(finalization["failures"]), reason="startup:asset-retry",
                                 correlation_id=str(state.get("correlation_id") or ""), require_publication=True)
        file_facts = self.dependencies.run_file_facts_backfill() if run_file_facts else dict(state.get("file_facts_backfill") or {})
        # Retry named paths through the dispatcher, without another inventory walk.
        with self._queue_condition:
            self._startup_waiting = bool(self._pending or self._active)
            self.dependencies.write_state({
                **result, "detail_backfill": detail_backfill, "file_facts_backfill": file_facts,
                "status": "running" if self._startup_waiting else "completed",
                "updated_at": self.dependencies.wall_time(),
            })
            if not self._startup_waiting:
                self.dependencies.mark_complete()

    def finalize_matched_paths(self, paths, *, reason, correlation_id):
        """Prepare and publish each completed card without cross-path blocking."""
        repository = self.dependencies.retry_repository()
        if repository is not None and not getattr(self._episode_local, 'finalizing', False):
            publications, failures = [], {}
            for path in dict.fromkeys(str(path) for path in paths if str(path)):
                item = {'type': 'path', 'value': path, 'reason': reason, 'correlation_id': correlation_id, 'require_publication': True}
                _result, due = self._run_path_episode(item)
                status = repository.publication_status([path]).get(self.normalize_path(path), {})
                if status.get('publication_committed'):
                    publications.append({'path': path, 'movie_key': status['movie_key']})
                else:
                    failures[path] = self._read_episode(path).get('last_error') or 'strict_publication_not_ready'
                if due:
                    self.reconcile_paths([path], reason=reason, correlation_id=correlation_id, require_publication=True)
            return {'publications': publications, 'failures': failures}
        publications = []
        failures = {}
        for path in dict.fromkeys(str(path or "") for path in paths or () if str(path or "")):
            try:
                source = self._read_episode(path).get('source_identity') or {}
                before = self._episode_signature(path, source)
                self.dependencies.prepare_final_card_assets([path])
                if before != self._episode_signature(path, source):
                    raise StaleReconciliationResult('inputs changed during artwork preparation')
                publications.extend(self.dependencies.final_card_publication([path]))
            except Exception as error:
                failures[path] = f"{type(error).__name__}: {error}"
        if publications:
            self.dependencies.publish_catalog_event(
                reason=str(reason or "manual").split(":", 1)[0],
                movie_keys=[publication["movie_key"] for publication in publications],
                changed_count=len(publications),
                correlation_id=str(correlation_id or ""),
            )
        return {"publications": publications, "failures": failures}

    def _submit(self, work_type, values, reason, correlation_id, *, require_publication=False, source_identity=None):
        correlation_id = str(correlation_id or uuid.uuid4())
        entries = []
        if work_type == "all":
            entries = [("all", ())]
        else:
            for value in values or ():
                absolute, root = self._validate_path(
                    value, require_directory=work_type == "directory"
                )
                entries.append((f"{work_type}:{self.normalize_path(absolute)}", (absolute, root)))
        accepted = 0
        coalesced = 0
        rejected = 0
        now = self.dependencies.monotonic()
        with self._queue_condition:
            if not self._accepting:
                rejected = len(entries)
            else:
                for key, payload in entries:
                    first_observed_at = now
                    if self._active and self._active.get('type') == work_type and self._active.get('value') == (payload[0] if payload else ''):
                        # A real observer event may require one revalidation after
                        # the current side effect. Polling is not new evidence.
                        if str(reason or '').startswith('observer:'):
                            self._active['follow_up'] = True
                        if source_identity and source_identity != self._active.get('source_identity'):
                            self._active['follow_up'] = True
                            self._active['source_identity'] = dict(source_identity)
                        if require_publication and not self._active.get('require_publication'):
                            self._active['follow_up'] = True
                            self._active['require_publication'] = True
                        coalesced += 1
                        continue
                    if work_type == "directory":
                        absolute = payload[0]
                        ancestor = None
                        descendants = []
                        for pending_key, pending_item in self._pending.items():
                            if pending_item.get("type") != "directory":
                                continue
                            pending_path = pending_item.get("value") or ""
                            if self._contains_path(pending_path, absolute):
                                ancestor = pending_item
                                break
                            if self._contains_path(absolute, pending_path):
                                descendants.append(pending_key)
                        if ancestor is not None:
                            ancestor["reason"] = str(reason or ancestor["reason"])
                            ancestor["correlation_id"] = correlation_id
                            ancestor["not_before"] = now + self.COALESCE_SECONDS
                            coalesced += 1
                            continue
                        if descendants:
                            first_observed_at = min(
                                [now]
                                + [
                                    float(self._pending[item].get("first_observed_at") or now)
                                    for item in descendants
                                ]
                            )
                            for descendant in descendants:
                                self._pending.pop(descendant, None)
                            coalesced += len(descendants)
                    existing = self._pending.get(key)
                    if existing:
                        existing["reason"] = str(reason or existing["reason"])
                        existing["correlation_id"] = correlation_id
                        if not existing.get('retry_count') and str(reason or '').startswith('observer:'):
                            existing["not_before"] = now + self.COALESCE_SECONDS
                        existing['require_publication'] = existing.get('require_publication', False) or require_publication
                        if source_identity and not existing.get('source_identity'):
                            existing['source_identity'] = dict(source_identity)
                        coalesced += 1
                        continue
                    if len(self._pending) >= self.QUEUE_CAPACITY:
                        rejected += 1
                        root = payload[1] if payload else ""
                        if root:
                            self._dirty_roots.add(self.normalize_path(root))
                        continue
                    self._admission_order += 1
                    repository = self.dependencies.retry_repository() if work_type == 'path' else None
                    admission_order = repository.next_retry_admission_order() if repository is not None else self._admission_order
                    self._pending[key] = {
                        "type": work_type,
                        "value": payload[0] if payload else "",
                        "reason": str(reason or "manual"),
                        "correlation_id": correlation_id,
                        "not_before": now + self.COALESCE_SECONDS,
                        "first_observed_at": first_observed_at,
                        "retry_count": 0,
                        "order": self._admission_order,
                        "admission_order": admission_order,
                        "require_publication": bool(require_publication),
                        "source_identity": dict(source_identity or {}),
                    }
                    accepted += 1
                self._ensure_dispatcher_locked()
                self._queue_condition.notify_all()
            queue_depth = len(self._pending)
        return {
            "correlation_id": correlation_id,
            "accepted": accepted,
            "coalesced": coalesced,
            "rejected": rejected,
            "queue_depth": queue_depth,
        }

    def reconcile_paths(self, paths, reason, correlation_id=None, identity_hints=None, *, require_publication=False, source_identity=None):
        with self._queue_condition:
            for path, identity in dict(identity_hints or {}).items():
                self._identity_hints[self.normalize_path(path)] = dict(identity or {})
        return self._submit("path", paths, reason, correlation_id, require_publication=require_publication, source_identity=source_identity)

    def reconcile_directories(self, directories, reason, correlation_id=None):
        return self._submit("directory", directories, reason, correlation_id)

    def reconcile_all(self, reason, correlation_id=None):
        return self._submit("all", (), reason, correlation_id)

    def _ensure_dispatcher_locked(self):
        if self._dispatcher and self._dispatcher.is_alive():
            return
        self._dispatcher = threading.Thread(
            target=self._dispatch,
            name="cinema-library-ingestion",
            daemon=True,
        )
        self._dispatcher.start()

    def _read_episode(self, path):
        repository = self.dependencies.retry_repository()
        if repository is None:
            return dict(self._volatile_episodes.get(self.normalize_path(path), {}))
        return repository.get_record('app_metadata/files.json', self.normalize_path(path), {}).get('_ingestion_retry', {})

    def recover_pending(self):
        repository = self.dependencies.retry_repository()
        if repository is None:
            return
        for record in repository.retry_records(self.QUEUE_CAPACITY):
            state = record.get('_ingestion_retry') or {}
            if state.get('state') == 'blocked':
                continue
            path = record.get('path')
            if not path or not self._root_for_path(path):
                continue
            self.reconcile_paths([path], reason=state.get('reason') or 'startup:retry', correlation_id=state.get('correlation_id'), require_publication=state.get('require_publication', False), source_identity=state.get('source_identity'))

    def _write_episode(self, path, state):
        previous_revision = int(state.get('revision') or 0)
        repository = self.dependencies.retry_repository()
        if not state.get('admission_order'):
            state['admission_order'] = repository.next_retry_admission_order() if repository is not None else self._admission_order
        next_state = {**state, 'revision': previous_revision + 1}
        if repository is None:
            self._volatile_episodes[self.normalize_path(path)] = next_state
        elif not repository.patch_file_operational(self.normalize_path(path), expected_revision=previous_revision, retry_state=next_state):
            raise RetryRevisionChanged('retry ledger revision changed')
        state.update(next_state)
        return True

    def _episode_signature(self, path, source):
        repository = self.dependencies.retry_repository()
        if repository is None:
            return self.normalize_path(path)
        store = self.dependencies.store()
        context = store.snapshot_for_paths([path])
        record = context['files'].get(store._key(path), {})
        observed = self.dependencies.metadata_file_facts(path, probe=False)
        identity_fields = ('tmdb_id', 'imdb_id', 'plex_guid', 'identity_title', 'identity_year', 'manual_lock', 'manual_locked', 'decision_origin')
        identity = {key: record.get(key) for key in identity_fields}
        # Provider content matters; clocks and attempt-generated status do not.
        def semantic(value):
            if isinstance(value, dict):
                return {key: semantic(item) for key, item in value.items() if not key.endswith('_at') and key not in {'status', 'error', 'probe_error', 'enrichment_status'}}
            if isinstance(value, list):
                return [semantic(item) for item in value]
            return value
        from services.media_file_facts import FILE_FACTS_VERSION, QUALITY_CLASSIFIER_VERSION
        payload = [self.normalize_path(path), observed.get('size'), observed.get('modified_time'), FILE_FACTS_VERSION, QUALITY_CLASSIFIER_VERSION, self.dependencies.identity_decision_version, identity, context.get('manual_matches'), semantic(context.get('tmdb_movies')), semantic(context.get('plex_files')), semantic(context.get('poster_overrides')), semantic(context.get('metadata_overrides')), source]
        return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()

    def _external_revision(self, path):
        repository = self.dependencies.retry_repository()
        if repository is None:
            return None
        record = repository.get_record('app_metadata/files.json', self.normalize_path(path), {})
        manual = repository.get_record('app_metadata/manual_matches.json', self.normalize_path(path), {})
        observed = self.dependencies.metadata_file_facts(path, probe=False)
        return (observed.get('size'), observed.get('modified_time'), {key: record.get(key) for key in ('tmdb_id', 'imdb_id', 'plex_guid', 'manual_lock', 'manual_locked', 'identity_source', 'decision_origin')}, manual)

    def _reservation_guard(self, path):
        repository = self.dependencies.retry_repository()
        if repository is None:
            return None
        revision = self._external_revision(path)
        record = revision[2]
        protected = bool(record.get('manual_lock') or record.get('manual_locked') or record.get('decision_origin') == 'user_manual' or str(record.get('identity_source') or '').startswith('manual_'))
        context = self.dependencies.store().snapshot_for_paths([path])
        # Automatic identity/provider outputs can be written immediately before a
        # crash. They do not become a new external observation on restart.
        value = [revision[0], revision[1], record if protected else {}, revision[3], context.get('poster_overrides'), context.get('metadata_overrides')]
        return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()

    def _rearm_path(self, path):
        state = self._read_episode(path)
        if not state or state.get('state') == 'blocked':
            if not state:
                state = {'version': 1, 'revision': 0, 'evidence_signature': self._episode_signature(path, {}), 'source_identity': {}}
            state.update(state='waiting', attempts={}, next_due_at=0, first_observed_at=self.dependencies.wall_time(), legacy_failure=False)
            self._write_episode(path, state)

    def _reserve(self, path, state, stage):
        attempts = dict(state.get('attempts') or {})
        count = int(attempts.get(stage) or 0)
        if (stage == 'assets' and count >= len(self.ASSET_RETRY_DELAYS) + 1) or self.dependencies.wall_time() - state['first_observed_at'] >= self.MAX_STABILITY_SECONDS:
            state.update(state='blocked', stage=stage, last_error=state.get('last_error') or stage + '_budget_exhausted')
            self._write_episode(path, state)
            self._identity_hints.pop(self.normalize_path(path), None)
            return False
        attempts[stage] = count + 1
        state.update(state='running', stage=stage, attempts=attempts, next_due_at=0, reservation_guard=self._reservation_guard(path))
        return self._write_episode(path, state)

    def _defer_episode(self, path, state, stage, error, *, terminal=False):
        count = int(state.get('attempts', {}).get(stage) or 1)
        delays = self.ASSET_RETRY_DELAYS if stage == 'assets' else self.RETRY_DELAYS
        exhausted = (stage == 'assets' and count > len(delays)) or self.dependencies.wall_time() - state['first_observed_at'] >= self.MAX_STABILITY_SECONDS
        state.update(state='blocked' if terminal or exhausted else 'waiting', stage=stage, last_error=str(error)[:1024])
        state['next_due_at'] = 0 if state['state'] == 'blocked' else self.dependencies.wall_time() + delays[min(count - 1, len(delays) - 1)]
        if not self._write_episode(path, state):
            return None
        self._last_error = state['last_error']
        if state['state'] == 'blocked':
            self._identity_hints.pop(self.normalize_path(path), None)
        return state['next_due_at'] or None

    def _commit_prepared(self, path, state, item):
        repository = self.dependencies.retry_repository()
        if repository is None or not state.get('require_publication'):
            return False
        status = repository.publication_status([path]).get(self.normalize_path(path), {})
        if status.get('publication_committed'):
            state.update(state='complete', next_due_at=0, last_error='')
            self._write_episode(path, state)
            self._identity_hints.pop(self.normalize_path(path), None)
            return True
        if state.get('legacy_failure'):
            return False
        if not (status.get('eligible_to_publish') or status.get('recoverable_prepared')):
            return False
        record = repository.get_record('app_metadata/files.json', self.normalize_path(path), {})
        observed = self.dependencies.metadata_file_facts(path, probe=False)
        if (observed.get('size'), observed.get('modified_time')) != (record.get('probe_size'), record.get('probe_modified_time')) or not self.dependencies.readable_check(path) or not self.file_copy_is_stable(observed, record):
            return False
        if not status.get('eligible_to_publish'):
            store = self.dependencies.store()
            with store.reconciliation_guard(path, record):
                store.update_file_record(path, {'ingest_status': 'stable'})
        # A completed asset can satisfy an exhausted episode; no external retry
        # is granted. Publication still reserves and commits through its owner.
        stage_attempts = dict(state.get('attempts') or {})
        stage_attempts['publication'] = int(stage_attempts.get('publication') or 0) + 1
        state.update(state='running', stage='publication', attempts=stage_attempts)
        if not self._write_episode(path, state):
            return True
        try:
            publications = self.dependencies.final_card_publication([path])
        except Exception as error:
            self._defer_episode(path, state, 'publication', f'{type(error).__name__}: {error}', terminal=True)
            return True
        if not publications:
            self._defer_episode(path, state, 'publication', 'publication_inputs_changed', terminal=True)
            return True
        self.dependencies.publish_catalog_event(reason=str(item.get('reason') or 'manual').split(':', 1)[0], movie_keys=[entry['movie_key'] for entry in publications], changed_count=len(publications), correlation_id=item.get('correlation_id') or '')
        state.update(state='complete', next_due_at=0, last_error='')
        self._write_episode(path, state)
        self._identity_hints.pop(self.normalize_path(path), None)
        return True

    def _resume_source_targets(self, path, state, item):
        source = state.get('source_identity') or {}
        handoff = state.get('handoff') or {}
        targets = handoff.get('paths') or source.get('paths') or []
        if handoff.get('state') not in {'ready', 'deferred'}:
            return
        repository = self.dependencies.retry_repository()
        for target in targets:
            if self.normalize_path(target) == self.normalize_path(path):
                continue
            if repository is not None:
                row = repository.get_record('app_metadata/files.json', self.normalize_path(target), {})
                child = row.get('_ingestion_retry') or {}
                if child.get('state') == 'blocked':
                    continue
                if child.get('state') == 'complete' and repository.publication_status([target]).get(self.normalize_path(target), {}).get('publication_committed'):
                    continue
            self.reconcile_paths([target], reason=item['reason'], correlation_id=item['correlation_id'], require_publication=bool(state.get('require_publication')))

    def _run_path_episode(self, item):
        key = self.normalize_path(item['value'])
        with self._queue_condition:
            if key in self._running_paths:
                previous = self._followup_paths.get(key) or {}
                self._followup_paths[key] = {**item, 'require_publication': bool(item.get('require_publication') or previous.get('require_publication'))}
                return {'pending': 1}, None
            self._running_paths.add(key)
        try:
            with self._run_lock:
                return self._execute_path_episode(item)
        except RetryRevisionChanged:
            # One bounded reread/reschedule; never overwrite the winning ledger.
            self._read_episode(item['value'])
            item['cas_retries'] = int(item.get('cas_retries') or 0) + 1
            self._last_error = 'retry_revision_conflict'
            if item['cas_retries'] <= 1:
                return {'pending': 1}, self.dependencies.wall_time() + self.COALESCE_SECONDS
            with self._queue_condition:
                root = self._root_for_path(item['value'])
                if root:
                    self._dirty_roots.add(self.normalize_path(root))
            return {'failed': 1}, None
        finally:
            with self._queue_condition:
                self._running_paths.discard(key)
                followup = self._followup_paths.pop(key, None)
                if followup:
                    if self._active and self.normalize_path(self._active.get('value') or '') == key:
                        self._active['follow_up'] = True
                        self._active['require_publication'] = bool(self._active.get('require_publication') or followup.get('require_publication'))
                        if followup.get('source_identity'):
                            self._active['source_identity'] = followup['source_identity']
                    elif self._accepting:
                        self._submit('path', [item['value']], followup.get('reason'), followup.get('correlation_id'), require_publication=followup.get('require_publication', False), source_identity=followup.get('source_identity'))

    def _execute_path_episode(self, item):
        path = item['value']
        repository = self.dependencies.retry_repository()
        source = dict(item.get('source_identity') or {})
        state = self._read_episode(path)
        source = source or dict(state.get('source_identity') or {})
        required = bool(item.get('require_publication') or state.get('require_publication'))
        if repository is not None:
            if not os.path.isfile(path):
                return self.reconcile_paths_now([path]), None
            store = self.dependencies.store()
            record = repository.get_record('app_metadata/files.json', self.normalize_path(path), {})
            required = required or record.get('movie_view_publication') == 'pending'
            if not record:
                store.update_file_record(path, {**self.dependencies.metadata_file_facts(path, probe=False), 'movie_view_publication': 'pending', 'ingest_status': 'pending'})
                required = True
        signature = self._episode_signature(path, source)
        if state.get('state') == 'running' and state.get('stage') in {'facts', 'provider'} and state.get('reservation_guard') == self._reservation_guard(path) and state.get('source_identity', {}) == source:
            state['evidence_signature'] = signature
        if not state or state.get('evidence_signature') != signature:
            legacy_failed = not state and repository is not None and record.get('ingest_status') == 'failed' and record.get('probe_status') not in {'unprobed', 'inaccessible', 'file_changed'}
            state = {'version': 1, 'revision': int(state.get('revision') or 0), 'evidence_signature': signature, 'state': 'waiting', 'stage': 'facts', 'attempts': {}, 'first_observed_at': self.dependencies.wall_time(), 'next_due_at': 0, 'require_publication': required, 'source_identity': source, 'correlation_id': item.get('correlation_id', ''), 'reason': item.get('reason', '')}
            state['admission_order'] = item.get('admission_order') or (repository.next_retry_admission_order() if repository is not None else self._admission_order)
            if legacy_failed:
                state.update(state='blocked', legacy_failure=True, last_error=record.get('probe_error') or record.get('poster_error') or 'existing_failed_ingestion_requires_manual_retry')
            if not self._write_episode(path, state):
                return {}, None
        if required and not state.get('require_publication'):
            state['require_publication'] = True
            if not self._write_episode(path, state):
                return {}, None
        self._resume_source_targets(path, state, item)
        if (not source or (state.get('handoff') or {}).get('state') in {'ready', 'deferred'}) and self._commit_prepared(path, state, item):
            return {}, None
        if state.get('state') in {'blocked', 'complete'}:
            return {}, None
        now = self.dependencies.wall_time()
        if state.get('state') == 'running':
            # A crash consumes its reserved attempt and resumes at backoff.
            due = self._defer_episode(path, state, state.get('stage', 'facts'), 'interrupted_attempt')
            return {}, due
        if float(state.get('next_due_at') or 0) > now:
            delays = self.ASSET_RETRY_DELAYS if state.get('stage') == 'assets' else self.RETRY_DELAYS
            count = int(state.get('attempts', {}).get(state.get('stage')) or 1)
            clamped = min(state['next_due_at'], now + delays[min(count - 1, len(delays) - 1)])
            if clamped != state['next_due_at']:
                state['next_due_at'] = clamped
                self._write_episode(path, state)
            return {}, clamped
        if source and not state.get('handoff'):
            if not self._reserve(path, state, 'provider'):
                return {}, None
            try:
                revision = self._external_revision(path)
                handoff = self.dependencies.resolve_source_identity(source)
                if revision != self._external_revision(path):
                    return {}, self._defer_episode(path, state, 'provider', 'inputs_changed_during_provider_lookup')
                state['handoff'] = {key: value for key, value in handoff.items() if key != 'metadata'}
                if handoff.get('metadata'):
                    self._identity_hints[self.normalize_path(path)] = dict(handoff['metadata'])
                state.update(state='waiting', evidence_signature=self._episode_signature(path, source))
                signature = state['evidence_signature']
                if not self._write_episode(path, state):
                    return {}, None
                targets = handoff.get('paths') or source.get('paths') or [path]
                if handoff.get('state') == 'failed':
                    return {}, self._defer_episode(path, state, 'provider', handoff.get('reason', 'provider_failed'), terminal=True)
                self._resume_source_targets(path, state, item)
            except Exception as error:
                transient = isinstance(error, (OSError, TimeoutError, ConnectionError))
                code = int(getattr(error, 'code', 0) or 0)
                if 400 <= code < 500 and code not in {408, 429}:
                    transient = False
                return {}, self._defer_episode(path, state, 'provider', str(error), terminal=not transient)
        if self._commit_prepared(path, state, item):
            return {}, None
        if state.get('handoff', {}).get('state') == 'ready' and self.normalize_path(path) not in self._identity_hints and repository is not None:
            metadata = self.dependencies.store().get_tmdb_metadata(state['handoff'].get('tmdb_id'))
            if metadata:
                self._identity_hints[self.normalize_path(path)] = metadata
        if state.get('stage') != 'assets':
            if not self._reserve(path, state, 'facts'):
                return {}, None
            try:
                self._episode_local.reserved = True
                result = self.reconcile_paths_now([path], require_publication=required)
            except Exception as error:
                return {}, self._defer_episode(path, state, 'facts', f'{type(error).__name__}: {error}', terminal=True)
            finally:
                self._episode_local.reserved = False
            if result.get('_obsolete'):
                return result, self._defer_episode(path, state, 'facts', 'inputs_changed_during_work')
            state['evidence_signature'] = self._episode_signature(path, source)
            if result.get('pending'):
                return result, self._defer_episode(path, state, 'facts', 'file_not_stable_or_readable')
            if result.get('failed') or result.get('review'):
                record = repository.get_record('app_metadata/files.json', self.normalize_path(path), {}) if repository is not None else {}
                failure = result.get('_failure') or record.get('probe_error') or '; '.join(record.get('identity_decision_reasons') or []) or 'identity_or_media_requires_review'
                return result, self._defer_episode(path, state, 'facts', failure, terminal=True)
        else:
            result = {}
        matched = result.get('_matched_paths') or ([path] if state.get('stage') == 'assets' or required else [])
        if matched:
            if not self._reserve(path, state, 'assets'):
                return result, None
            try:
                self._episode_local.finalizing = True
                finalization = self.finalize_matched_paths(matched, reason=item['reason'], correlation_id=item['correlation_id'])
            finally:
                self._episode_local.finalizing = False
            failures = finalization['failures']
            if failures:
                due = self._defer_episode(path, state, 'assets', next(iter(failures.values())))
                if not due:
                    self.dependencies.store().update_file_record(path, {'ingest_status': 'failed', 'poster_error': state['last_error']})
                return result, due
            if required and not finalization['publications']:
                return result, self._defer_episode(path, state, 'assets', 'strict_publication_not_ready', terminal=True)
        state.update(state='complete', next_due_at=0, last_error='', evidence_signature=self._episode_signature(path, source))
        self._write_episode(path, state)
        self._identity_hints.pop(self.normalize_path(path), None)
        return result, None

    def _dispatch(self):
        while True:
            with self._queue_condition:
                while not self._pending and self._accepting:
                    self._queue_condition.wait()
                if not self._pending and not self._accepting:
                    return
                now = self.dependencies.monotonic()
                wall_now = self.dependencies.wall_time()
                def deadline(work):
                    # Compare durable due times against one shared clock pair.
                    # Per-item conversions introduce jitter that can reverse FIFO.
                    if 'retry_due_at' in work:
                        return now + (work['retry_due_at'] - wall_now)
                    return work['not_before']
                key, item = min(self._pending.items(), key=lambda pair: (deadline(pair[1]), pair[1].get('order', 0)))
                delay = deadline(item) - now
                if delay > 0:
                    self._queue_condition.wait(timeout=delay)
                    continue
                self._pending.pop(key, None)
                self._active = item
            try:
                if item["type"] == "path":
                    result, due = self._run_path_episode(item)
                    self._last_result = {**{name: value for name, value in result.items() if not name.startswith('_')}, 'reason': item['reason'], 'correlation_id': item['correlation_id']}
                    if due and self._accepting:
                        retry = {**item, 'retry_count': int(item.get('retry_count') or 0) + 1, 'retry_due_at': due}
                        with self._queue_condition:
                            self._pending[key] = retry
                            self._queue_condition.notify_all()
                    elif item.get('follow_up') and self._accepting:
                        with self._queue_condition:
                            followup = {**item, 'follow_up': False, 'not_before': self.dependencies.monotonic() + self.COALESCE_SECONDS}
                            followup.pop('retry_due_at', None)
                            self._pending[key] = followup
                            self._queue_condition.notify_all()
                    continue
                elif item["type"] == "directory":
                    result = self.reconcile_directories_now((item["value"],))
                else:
                    result = self.reconcile_all_now()
                self._last_result = {
                    **{key: value for key, value in result.items() if not key.startswith("_")},
                    "reason": item["reason"],
                    "correlation_id": item["correlation_id"],
                }
                self._last_error = ""
            except Exception as error:
                self._last_error = f"{type(error).__name__}: {error}"
            finally:
                with self._queue_condition:
                    self._active = None
                    self._queue_condition.notify_all()
                    if self._startup_waiting and not self._pending:
                        self._startup_waiting = False
                        self.dependencies.write_state({**self.dependencies.read_state(), "status": "completed", "pending": 0, "updated_at": self.dependencies.wall_time()})
                        self.dependencies.mark_complete()

    def status(self):
        with self._queue_condition:
            active = dict(self._active) if self._active else None
            if active:
                active.pop('source_identity', None)
            if active and active.get("value"):
                active["path_id"] = hashlib.blake2b(
                    self.normalize_path(active.pop("value")).encode(
                        "utf-8", errors="surrogatepass"
                    ),
                    digest_size=8,
                ).hexdigest()
            return {
                "accepting": self._accepting,
                "queue_depth": len(self._pending),
                "queue_capacity": self.QUEUE_CAPACITY,
                "active": active,
                "dirty_root_ids": [
                    hashlib.blake2b(
                        root.encode("utf-8", errors="surrogatepass"),
                        digest_size=8,
                    ).hexdigest()
                    for root in sorted(self._dirty_roots)
                ],
                "last_result": dict(self._last_result),
                "last_error": self._last_error,
            }

    def checkpoint_for_shutdown(self, timeout_seconds=30):
        """Stop new ingestion while leaving queued work recoverable at startup.

        A queued retry has already written its current file state to the catalog.
        Waiting for every retry would make a safe shutdown wait for hours. Mark
        affected roots dirty, discard only those in-memory retries, and let the
        active reconciliation finish before exit.
        """
        deadline = time.monotonic() + max(0, float(timeout_seconds))
        with self._queue_condition:
            self._accepting = False
            for item in self._pending.values():
                value = item.get("value")
                if not value or item.get("type") == "all":
                    self._dirty_roots.update(
                        self.normalize_path(root) for root in self.dependencies.roots()
                    )
                    continue
                root = self._root_for_path(value)
                if root:
                    self._dirty_roots.add(self.normalize_path(root))
            self._pending.clear()
            self._queue_condition.notify_all()
            dispatcher = self._dispatcher
        if dispatcher:
            dispatcher.join(timeout=max(0, deadline - time.monotonic()))
        if dispatcher and dispatcher.is_alive():
            return False
        remaining = max(0, deadline - time.monotonic())
        acquired = self._run_lock.acquire(timeout=remaining)
        if not acquired:
            return False
        self._run_lock.release()
        return True

    def resume_after_shutdown_failure(self):
        """Resume background ingestion when an OS power command was rejected."""
        with self._queue_condition:
            self._accepting = True
            self._ensure_dispatcher_locked()
            self._queue_condition.notify_all()

    def shutdown(self, timeout_seconds=10):
        with self._queue_condition:
            self._accepting = False
            self._queue_condition.notify_all()
            dispatcher = self._dispatcher
        if dispatcher:
            dispatcher.join(timeout=max(0, float(timeout_seconds)))
        return not (dispatcher and dispatcher.is_alive())
