import unittest

from services.identity_audit import IdentityAuditCoordinator


class MemoryState:
    def __init__(self, state=None):
        self.state = dict(state or {})

    def load(self):
        return dict(self.state)

    def save(self, state):
        self.state = dict(state)


class IdentityAuditCoordinatorTest(unittest.TestCase):
    def test_restarted_running_job_becomes_paused_without_processing(self):
        store = MemoryState({
            "schema_version": 4,
            "id": "job-1",
            "status": "running",
            "paths": ["a.mkv", "b.mkv"],
            "processed": 1,
            "remaining": 1,
            "total": 2,
            "proposals": [{"id": "proposal-1"}],
            "automatic_fixes": [{"id": "automatic-1"}],
        })
        processed = []

        coordinator = IdentityAuditCoordinator(
            load_state=store.load,
            save_state=store.save,
            list_paths=lambda: [],
            process_path=lambda path, provider: processed.append(path),
        )

        state = coordinator.status()

        self.assertEqual(state["status"], "paused")
        self.assertEqual(state["interrupted_at"], state["updated_at"])
        self.assertEqual(state["processed"], 1)
        self.assertEqual(state["proposals"], [{"id": "proposal-1"}])
        self.assertEqual(state["automatic_fixes"], [{"id": "automatic-1"}])
        self.assertEqual(processed, [])

    def test_pause_persists_partial_results_and_resume_continues_without_duplicates(self):
        store = MemoryState()
        coordinator = None
        processed = []

        def process(path, provider):
            processed.append(path)
            if path == "a.mkv":
                coordinator.pause()
            return {
                "path": path,
                "candidate": {"tmdb_id": path},
                "classification": "review",
            }

        coordinator = IdentityAuditCoordinator(
            load_state=store.load,
            save_state=store.save,
            list_paths=lambda: ["a.mkv", "b.mkv"],
            process_path=process,
            batch_size=2,
        )
        coordinator.start(provider="tmdb", background=False)

        paused = coordinator.run_batch()
        resumed = coordinator.resume(background=False)
        completed = coordinator.run_batch()

        self.assertEqual(paused["status"], "paused")
        self.assertEqual(paused["processed"], 1)
        self.assertEqual(len(paused["proposals"]), 1)
        self.assertEqual(resumed["status"], "running")
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(processed, ["a.mkv", "b.mkv"])
        self.assertEqual(len(completed["proposals"]), 2)

    def test_new_start_clears_previous_job_results(self):
        store = MemoryState({
            "schema_version": 4,
            "id": "old-job",
            "status": "completed",
            "paths": ["old.mkv"],
            "processed": 1,
            "remaining": 0,
            "total": 1,
            "proposals": [{"id": "proposal-1"}],
            "automatic_fixes": [{"id": "automatic-1"}],
            "errors": [{"path": "old.mkv", "error": "old"}],
        })
        coordinator = IdentityAuditCoordinator(
            load_state=store.load,
            save_state=store.save,
            list_paths=lambda: ["new.mkv"],
            process_path=lambda path, provider: {},
        )

        state = coordinator.start(provider="tmdb", background=False)

        self.assertNotEqual(state["id"], "old-job")
        self.assertEqual(state["paths"], ["new.mkv"])
        self.assertEqual(state["proposals"], [])
        self.assertEqual(state["automatic_fixes"], [])
        self.assertEqual(state["errors"], [])

    def test_automatic_fix_record_is_saved_with_partial_results(self):
        store = MemoryState()
        coordinator = IdentityAuditCoordinator(
            load_state=store.load,
            save_state=store.save,
            list_paths=lambda: ["Elle.2016.mkv"],
            process_path=lambda path, provider: {
                "automatically_verified": True,
                "automatic_fix": {
                    "id": "auto-elle",
                    "path": path,
                    "filename": path,
                    "current": {"title": "Elle", "year": "2016"},
                    "candidate": {"tmdb_id": "337674", "title": "Elle", "year": "2016"},
                    "evidence_score": 100,
                    "runner_up_gap": 20,
                    "reasons": ["exact title or alias", "release year matches"],
                },
            },
        )
        coordinator.start(provider="tmdb", background=False)

        state = coordinator.run_batch()

        self.assertEqual(state["automatically_verified"], 1)
        self.assertEqual(len(state["automatic_fixes"]), 1)
        self.assertEqual(state["automatic_fixes"][0]["candidate"]["tmdb_id"], "337674")


if __name__ == "__main__":
    unittest.main()
