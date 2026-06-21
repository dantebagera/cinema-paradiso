import threading
import time


class MetadataMigrationCoordinator:
    def __init__(
        self,
        load_state,
        save_state,
        list_paths,
        process_path,
        on_complete=None,
        batch_size=10,
        batch_delay=0.05,
    ):
        self._load_state = load_state
        self._save_state = save_state
        self._list_paths = list_paths
        self._process_path = process_path
        self._on_complete = on_complete
        self._batch_size = batch_size
        self._batch_delay = batch_delay
        self._lock = threading.RLock()
        self._thread = None
        self._recover_interrupted_state()

    def _recover_interrupted_state(self):
        state = self._load_state() or {}
        if state.get("status") != "running":
            return
        now = time.time()
        self._save_state({
            **state,
            "status": "paused",
            "current_path": "",
            "interrupted_at": now,
            "updated_at": now,
        })

    def _default_state(self):
        return {
            "status": "idle",
            "source": "",
            "target": "",
            "paths": [],
            "processed": 0,
            "matched": 0,
            "review": 0,
            "failed": 0,
            "remaining": 0,
            "total": 0,
            "current_path": "",
            "review_paths": [],
            "failed_paths": [],
            "started_at": 0,
            "updated_at": 0,
            "completed_at": 0,
        }

    def status(self):
        with self._lock:
            return {**self._default_state(), **(self._load_state() or {})}

    def preview(self, target):
        paths = list(self._list_paths() or [])
        return {
            "target": target,
            "total": len(paths),
            "paths": paths,
        }

    def start(self, target, source="", background=True):
        with self._lock:
            current = self.status()
            if current["status"] in {"running", "paused"}:
                raise RuntimeError("Metadata migration is already active")
            paths = list(self._list_paths() or [])
            now = time.time()
            state = {
                **self._default_state(),
                "status": "running",
                "source": source,
                "target": target,
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

    def pause(self):
        with self._lock:
            state = self.status()
            if state["status"] == "running":
                state["status"] = "paused"
                state["updated_at"] = time.time()
                self._save_state(state)
            return dict(state)

    def resume(self, background=True):
        with self._lock:
            state = self.status()
            if state["status"] in {"paused", "failed", "cancelled"} and state["remaining"] > 0:
                state["status"] = "running"
                state["updated_at"] = time.time()
                self._save_state(state)
        if background and self.status()["status"] == "running":
            self._ensure_thread()
        return self.status()

    def cancel(self):
        with self._lock:
            state = self.status()
            if state["status"] not in {"completed", "idle"}:
                state["status"] = "cancelled"
                state["current_path"] = ""
                state["updated_at"] = time.time()
                self._save_state(state)
            return dict(state)

    def retry_failed(self, background=True):
        with self._lock:
            state = self.status()
            retry_paths = list(state.get("failed_paths", []))
            state["paths"] = retry_paths
            state["processed"] = 0
            state["matched"] = 0
            state["review"] = 0
            state["failed"] = 0
            state["remaining"] = len(retry_paths)
            state["total"] = len(retry_paths)
            state["failed_paths"] = []
            state["review_paths"] = []
            state["current_path"] = ""
            state["status"] = "running" if retry_paths else "completed"
            state["updated_at"] = time.time()
            self._save_state(state)
        if background and retry_paths:
            self._ensure_thread()
        return self.status()

    def run_batch(self, limit=None):
        with self._lock:
            state = self.status()
            if state["status"] != "running":
                return dict(state)
            paths = state.get("paths", [])
            start_index = state["processed"]
            batch = paths[start_index:start_index + (limit or self._batch_size)]

        for path in batch:
            with self._lock:
                state = self.status()
                if state["status"] != "running":
                    return dict(state)
                state["current_path"] = path
                state["updated_at"] = time.time()
                self._save_state(state)
            try:
                outcome = self._process_path(path, state["target"])
            except Exception:
                outcome = "failed"
            if outcome not in {"matched", "review", "failed"}:
                outcome = "failed"
            with self._lock:
                state = self.status()
                state["processed"] += 1
                state[outcome] += 1
                state["remaining"] = max(0, state["total"] - state["processed"])
                state["current_path"] = ""
                state["updated_at"] = time.time()
                if outcome == "review":
                    state["review_paths"] = [*state.get("review_paths", []), path]
                elif outcome == "failed":
                    state["failed_paths"] = [*state.get("failed_paths", []), path]
                self._save_state(state)

        with self._lock:
            state = self.status()
            if state["status"] == "running" and state["processed"] >= state["total"]:
                state["status"] = "completed"
                state["completed_at"] = time.time()
                state["updated_at"] = state["completed_at"]
                self._save_state(state)
                if self._on_complete:
                    self._on_complete(dict(state))
            return dict(state)

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
