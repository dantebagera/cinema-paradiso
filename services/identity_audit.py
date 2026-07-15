from concurrent.futures import ThreadPoolExecutor
import threading
import time
import uuid


IDENTITY_AUDIT_SCHEMA_VERSION = 5


def _empty_outcome_counts():
    return {
        "verified": 0,
        "manual": 0,
        "tolerated": 0,
        "ambiguous": 0,
        "actionable": 0,
        "unmatched": 0,
    }


class IdentityAuditCoordinator:
    def __init__(
        self,
        load_state,
        save_state,
        list_paths,
        process_path,
        batch_size=6,
        batch_delay=0.1,
        max_workers=1,
    ):
        self._load_state = load_state
        self._save_state = save_state
        self._list_paths = list_paths
        self._process_path = process_path
        self._batch_size = batch_size
        self._batch_delay = batch_delay
        self._max_workers = max(1, int(max_workers or 1))
        self._lock = threading.RLock()
        self._thread = None
        self._recover_interrupted_state()

    def _default_state(self):
        return {
            "schema_version": IDENTITY_AUDIT_SCHEMA_VERSION,
            "id": "",
            "status": "idle",
            "paths": [],
            "processed": 0,
            "remaining": 0,
            "total": 0,
            "proposals": [],
            "automatic_fixes": [],
            "unresolved": [],
            "diagnostic_samples": {
                "ambiguous": [],
                "unmatched": [],
            },
            "outcome_counts": _empty_outcome_counts(),
            "errors": [],
            "applied": 0,
            "automatically_verified": 0,
            "recommended_count": 0,
            "review_count": 0,
            "provider": "",
            "last_checked_at": 0,
            "current_path": "",
            "started_at": 0,
            "updated_at": 0,
            "completed_at": 0,
            "interrupted_at": 0,
            "requires_refresh": False,
            "shadow_mode": True,
            "mutates_metadata": False,
        }

    def _recover_interrupted_state(self):
        raw_state = self._load_state() or {}
        if not raw_state:
            return
        now = time.time()
        changed = raw_state.get("schema_version") != IDENTITY_AUDIT_SCHEMA_VERSION
        state = {**self._default_state(), **raw_state}
        state["schema_version"] = IDENTITY_AUDIT_SCHEMA_VERSION
        if changed:
            state["requires_refresh"] = True
        if state.get("status") == "running":
            state["status"] = "paused"
            state["current_path"] = ""
            state["interrupted_at"] = now
            state["updated_at"] = now
            changed = True
        if changed:
            self._save_state(state)

    def status(self):
        with self._lock:
            raw_state = self._load_state() or {}
            return {**self._default_state(), **raw_state}

    def start(self, provider="tmdb", background=True):
        with self._lock:
            current = self.status()
            if current["status"] == "running":
                raise RuntimeError("Library identity audit is already active")
            paths = list(dict.fromkeys(self._list_paths() or []))
            now = time.time()
            state = {
                **self._default_state(),
                "id": uuid.uuid4().hex,
                "status": "running",
                "provider": provider,
                "paths": paths,
                "remaining": len(paths),
                "total": len(paths),
                "started_at": now,
                "updated_at": now,
            }
            self._save_state(state)
        if background:
            self._ensure_thread()
        return self.status()

    def cancel(self):
        with self._lock:
            state = self.status()
            if state["status"] == "running":
                state["status"] = "cancelled"
                state["current_path"] = ""
                state["updated_at"] = time.time()
                self._save_state(state)
            return state

    def pause(self):
        with self._lock:
            state = self.status()
            if state["status"] == "running":
                state["status"] = "paused"
                state["current_path"] = ""
                state["updated_at"] = time.time()
                self._save_state(state)
            return state

    def resume(self, background=True):
        with self._lock:
            state = self.status()
            if state["status"] != "paused":
                raise RuntimeError("Only a paused identity audit can be resumed")
            state["status"] = "running"
            state["interrupted_at"] = 0
            state["updated_at"] = time.time()
            self._save_state(state)
        if background:
            self._ensure_thread()
        return self.status()

    def run_batch(self, limit=None):
        with self._lock:
            state = self.status()
            if state["status"] != "running":
                return state
            start = state["processed"]
            batch = state["paths"][start:start + (limit or self._batch_size)]
            provider = state.get("provider") or "tmdb"
        if self._max_workers == 1 or len(batch) < 2:
            results = []
            for path in batch:
                with self._lock:
                    state = self.status()
                    if state["status"] != "running":
                        if results:
                            self._record_results(results)
                            return self.status()
                        return state
                results.append(self._run_path(path, provider))
            self._record_results(results)
        else:
            with self._lock:
                state = self.status()
                if state["status"] != "running":
                    return state
            with ThreadPoolExecutor(max_workers=min(self._max_workers, len(batch))) as executor:
                results = list(executor.map(
                    lambda path: self._run_path(path, provider),
                    batch,
                ))
            self._record_results(results)
        with self._lock:
            state = self.status()
            if state["status"] == "running" and state["processed"] >= state["total"]:
                state["status"] = "completed"
                state["completed_at"] = time.time()
                state["last_checked_at"] = state["completed_at"]
                state["updated_at"] = state["completed_at"]
                self._save_state(state)
            return state

    def _run_path(self, path, provider):
        try:
            return path, self._process_path(path, provider) or {}, ""
        except Exception as exc:
            return path, {}, str(exc)

    def _record_result(self, path, result, error):
        self._record_results([(path, result, error)])

    def _record_results(self, results):
        with self._lock:
            state = self.status()
            for path, result, error in results:
                state["outcome_counts"] = {
                    **_empty_outcome_counts(),
                    **dict(state.get("outcome_counts") or {}),
                }
                outcome = ""
                if not error:
                    outcome = str(result.get("outcome") or "").strip().lower()
                    outcome = {
                        "accepted": "tolerated",
                        "contradicted": "actionable",
                    }.get(outcome, outcome)
                    if outcome not in state["outcome_counts"]:
                        outcome = "ambiguous" if result else "unmatched"
                    state["outcome_counts"][outcome] += 1

                if outcome == "actionable" and result.get("candidate"):
                    proposal = dict(result)
                    proposal["outcome"] = "actionable"
                    proposal["classification"] = "actionable"
                    proposal["preselected"] = False
                    proposal.setdefault("id", uuid.uuid4().hex)
                    state["proposals"] = [*state["proposals"], proposal]
                    state["review_count"] += 1
                elif outcome in {"ambiguous", "unmatched"} and result:
                    samples = {
                        "ambiguous": [],
                        "unmatched": [],
                        **dict(state.get("diagnostic_samples") or {}),
                    }
                    if len(samples[outcome]) < 25:
                        samples[outcome] = [*samples[outcome], {"path": path, **result}]
                    state["diagnostic_samples"] = samples
                if error:
                    state["errors"] = [*state["errors"], {"path": path, "error": error}]
                state["processed"] += 1
            state["remaining"] = max(0, state["total"] - state["processed"])
            state["current_path"] = ""
            state["updated_at"] = time.time()
            self._save_state(state)

    def _ensure_thread(self):
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()

    def _run_loop(self):
        while True:
            state = self.run_batch()
            if state["status"] != "running":
                return
            time.sleep(self._batch_delay)
