import unittest

from services.metadata_migration import MetadataMigrationCoordinator


class MemoryStateStore:
    def __init__(self):
        self.state = {}

    def load(self):
        return dict(self.state)

    def save(self, state):
        self.state = dict(state)


class MetadataMigrationCoordinatorTest(unittest.TestCase):
    def test_batches_persist_progress_and_complete(self):
        store = MemoryStateStore()
        outcomes = {
            "one": "matched",
            "two": "review",
            "three": "failed",
        }
        completed = []
        coordinator = MetadataMigrationCoordinator(
            load_state=store.load,
            save_state=store.save,
            list_paths=lambda: list(outcomes),
            process_path=lambda path, target: outcomes[path],
            on_complete=lambda state: completed.append(dict(state)),
        )

        started = coordinator.start("tmdb", background=False)
        self.assertEqual(started["status"], "running")
        self.assertEqual(started["total"], 3)

        coordinator.run_batch(limit=2)
        progress = coordinator.status()
        self.assertEqual(progress["processed"], 2)
        self.assertEqual(progress["matched"], 1)
        self.assertEqual(progress["review"], 1)
        self.assertEqual(progress["remaining"], 1)

        coordinator.run_batch(limit=2)
        finished = coordinator.status()
        self.assertEqual(finished["status"], "completed")
        self.assertEqual(finished["failed"], 1)
        self.assertEqual(finished["remaining"], 0)
        self.assertEqual(len(completed), 1)

    def test_pause_resume_and_cancel_are_persisted(self):
        store = MemoryStateStore()
        coordinator = MetadataMigrationCoordinator(
            load_state=store.load,
            save_state=store.save,
            list_paths=lambda: ["one", "two"],
            process_path=lambda path, target: "matched",
        )

        coordinator.start("tmdb", background=False)
        self.assertEqual(coordinator.pause()["status"], "paused")
        self.assertEqual(coordinator.run_batch()["processed"], 0)
        self.assertEqual(coordinator.resume(background=False)["status"], "running")
        self.assertEqual(coordinator.cancel()["status"], "cancelled")
        self.assertEqual(store.state["status"], "cancelled")

    def test_restart_continues_from_persisted_processed_index(self):
        store = MemoryStateStore()
        processed = []
        first = MetadataMigrationCoordinator(
            load_state=store.load,
            save_state=store.save,
            list_paths=lambda: ["one", "two", "three"],
            process_path=lambda path, target: processed.append(path) or "matched",
        )
        first.start("tmdb", background=False)
        first.run_batch(limit=1)

        restarted = MetadataMigrationCoordinator(
            load_state=store.load,
            save_state=store.save,
            list_paths=lambda: ["ignored-new-scan"],
            process_path=lambda path, target: processed.append(path) or "matched",
        )
        self.assertEqual(restarted.resume(background=False)["status"], "running")
        restarted.run_batch(limit=10)

        self.assertEqual(processed, ["one", "two", "three"])
        self.assertEqual(restarted.status()["status"], "completed")
        self.assertEqual(restarted.status()["processed"], 3)

    def test_retry_processes_only_failed_paths(self):
        store = MemoryStateStore()
        attempts = []
        outcomes = {"one": "matched", "two": "failed", "three": "review"}
        coordinator = MetadataMigrationCoordinator(
            load_state=store.load,
            save_state=store.save,
            list_paths=lambda: list(outcomes),
            process_path=lambda path, target: attempts.append(path) or outcomes[path],
        )
        coordinator.start("tmdb", background=False)
        coordinator.run_batch(limit=10)
        outcomes["two"] = "matched"

        retried = coordinator.retry_failed(background=False)
        self.assertEqual(retried["paths"], ["two"])
        coordinator.run_batch(limit=10)

        self.assertEqual(attempts, ["one", "two", "three", "two"])
        self.assertEqual(coordinator.status()["status"], "completed")
        self.assertEqual(coordinator.status()["matched"], 1)
        self.assertEqual(coordinator.status()["failed"], 0)

    def test_cancelled_migration_does_not_process_remaining_paths(self):
        store = MemoryStateStore()
        processed = []
        coordinator = MetadataMigrationCoordinator(
            load_state=store.load,
            save_state=store.save,
            list_paths=lambda: ["one", "two", "three"],
            process_path=lambda path, target: processed.append(path) or "matched",
        )
        coordinator.start("tmdb", background=False)
        coordinator.run_batch(limit=1)
        coordinator.cancel()
        coordinator.run_batch(limit=10)

        self.assertEqual(processed, ["one"])
        self.assertEqual(coordinator.status()["status"], "cancelled")
        self.assertEqual(coordinator.status()["processed"], 1)
        self.assertEqual(coordinator.status()["remaining"], 2)

    def test_start_rejects_second_active_migration_without_losing_progress(self):
        store = MemoryStateStore()
        coordinator = MetadataMigrationCoordinator(
            load_state=store.load,
            save_state=store.save,
            list_paths=lambda: ["one", "two"],
            process_path=lambda path, target: "matched",
        )
        coordinator.start("tmdb", background=False)
        coordinator.run_batch(limit=1)
        before = coordinator.status()

        with self.assertRaisesRegex(RuntimeError, "already active"):
            coordinator.start("plex", background=False)

        after = coordinator.status()
        self.assertEqual(after["target"], "tmdb")
        self.assertEqual(after["processed"], before["processed"])
        self.assertEqual(after["remaining"], before["remaining"])


if __name__ == "__main__":
    unittest.main()
