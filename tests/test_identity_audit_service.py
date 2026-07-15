import threading
import time
import unittest

from services.identity_audit import IDENTITY_AUDIT_SCHEMA_VERSION, IdentityAuditCoordinator


class MemoryState:
    def __init__(self, state=None):
        self.state = dict(state or {})
        self.save_count = 0

    def load(self):
        return dict(self.state)

    def save(self, state):
        self.save_count += 1
        self.state = dict(state)


class IdentityAuditCoordinatorTest(unittest.TestCase):
    def test_restarted_running_job_becomes_paused_without_processing(self):
        store = MemoryState({
            "schema_version": IDENTITY_AUDIT_SCHEMA_VERSION,
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
                "classification": "actionable",
                "outcome": "actionable",
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

    def test_verified_outcome_is_counted_without_creating_a_fix_record(self):
        store = MemoryState()
        coordinator = IdentityAuditCoordinator(
            load_state=store.load,
            save_state=store.save,
            list_paths=lambda: ["Elle.2016.mkv"],
            process_path=lambda path, provider: {
                "outcome": "verified",
                "path": path,
            },
        )
        coordinator.start(provider="tmdb", background=False)

        state = coordinator.run_batch()

        self.assertEqual(state["outcome_counts"]["verified"], 1)
        self.assertEqual(state["automatically_verified"], 0)
        self.assertEqual(state["automatic_fixes"], [])

    def test_ambiguous_outcome_is_counted_but_not_added_to_review(self):
        store = MemoryState()
        coordinator = IdentityAuditCoordinator(
            load_state=store.load,
            save_state=store.save,
            list_paths=lambda: ["Love.2011.mkv"],
            process_path=lambda path, provider: {
                "outcome": "ambiguous",
                "path": path,
                "candidate": {"tmdb_id": "222"},
            },
        )
        coordinator.start(provider="tmdb", background=False)

        state = coordinator.run_batch()

        self.assertEqual(state["outcome_counts"]["ambiguous"], 1)
        self.assertEqual(state["proposals"], [])
        self.assertEqual(len(state["diagnostic_samples"]["ambiguous"]), 1)

    def test_provider_checks_can_run_concurrently_while_state_updates_stay_serial(self):
        store = MemoryState()
        active = 0
        max_active = 0
        activity_lock = threading.Lock()

        def process(path, provider):
            nonlocal active, max_active
            with activity_lock:
                active += 1
                max_active = max(max_active, active)
            time.sleep(0.03)
            with activity_lock:
                active -= 1
            return {}

        coordinator = IdentityAuditCoordinator(
            load_state=store.load,
            save_state=store.save,
            list_paths=lambda: ["a.mkv", "b.mkv", "c.mkv"],
            process_path=process,
            batch_size=3,
            max_workers=3,
        )
        coordinator.start(provider="tmdb", background=False)

        state = coordinator.run_batch()

        self.assertEqual(state["status"], "completed")
        self.assertEqual(state["processed"], 3)
        self.assertGreaterEqual(max_active, 2)

    def test_batch_results_are_persisted_once_instead_of_once_per_file(self):
        store = MemoryState()
        coordinator = IdentityAuditCoordinator(
            load_state=store.load,
            save_state=store.save,
            list_paths=lambda: [f"{index}.mkv" for index in range(6)],
            process_path=lambda path, provider: {"outcome": "verified", "path": path},
            batch_size=6,
            max_workers=3,
        )
        coordinator.start(provider="tmdb", background=False)

        state = coordinator.run_batch()

        self.assertEqual(state["status"], "completed")
        self.assertEqual(state["outcome_counts"]["verified"], 6)
        self.assertEqual(store.save_count, 3)


if __name__ == "__main__":
    unittest.main()
