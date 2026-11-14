"""A real disposable coordinator process; parent terminates it at durable boundaries."""
import argparse
from dataclasses import replace
import json
import os
from pathlib import Path
import tempfile
import threading
from unittest.mock import Mock

from services.catalog_repository import CatalogRepository
from services.library_ingestion import LibraryIngestionCoordinator
from tests.test_library_ingestion_queue import _dependencies


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode')
    parser.add_argument('root')
    parser.add_argument('--boundary', default='')
    parser.add_argument('--clock', type=float, default=1000.0)
    args = parser.parse_args()
    root = Path(args.root).resolve()
    declared = Path(os.environ['CP_TEST_ROOT']).resolve()
    if os.environ.get('CP_TEST_MODE') != '1' or declared not in root.parents or Path(tempfile.gettempdir()).resolve() not in root.parents:
        raise RuntimeError('Disposable test descendants only')
    root.mkdir(parents=True, exist_ok=True)
    repository = CatalogRepository(root / 'data', root / 'catalog.sqlite')
    repository.activate_from_json()
    path = root / 'Example.mkv'
    key = os.path.normcase(str(path))
    if not path.exists():
        path.write_bytes(b'fixture')
        repository.upsert_record('app_metadata/files.json', key, {'path': str(path), 'size': 7})
    store = Mock()
    store.catalog = repository
    store._key.side_effect = lambda value: os.path.normcase(str(value))
    store.snapshot_for_paths.side_effect = lambda paths: {
        'files': {store._key(p): repository.get_record('app_metadata/files.json', store._key(p)) for p in paths},
        'manual_matches': {}, 'tmdb_movies': {}, 'plex_files': {}, 'poster_overrides': [], 'metadata_overrides': []}
    def update(value, patch):
        target = store._key(value)
        repository.upsert_record('app_metadata/files.json', target, {**repository.get_record('app_metadata/files.json', target), **patch})
    store.update_file_record.side_effect = update
    facts = lambda p, probe=False: {'path': str(p), 'size': Path(p).stat().st_size, 'modified_time': Path(p).stat().st_mtime}
    deps = replace(_dependencies(root), store=lambda: store, retry_repository=lambda: repository,
                   wall_time=lambda: args.clock, monotonic=lambda: args.clock, metadata_file_facts=facts)
    coordinator = LibraryIngestionCoordinator(deps)
    coordinator._ensure_dispatcher_locked = lambda: None
    item = {'type': 'path', 'value': str(path), 'reason': 'qbittorrent', 'correlation_id': 'process-fixture', 'require_publication': True}
    def checkpoint(label):
        with (root / 'checkpoint.json').open('w') as output:
            json.dump({'pid': os.getpid(), 'boundary': label}, output)
            output.flush()
            os.fsync(output.fileno())
        threading.Event().wait(120)
        raise RuntimeError('Parent failed to terminate checkpoint worker')
    def calls(label):
        with (root / 'external-calls.jsonl').open('a') as output:
            output.write(json.dumps({'stage': label, 'pid': os.getpid()}) + '\n')
    coordinator.reconcile_paths_now = lambda paths, **kwargs: {'checked': 1, 'review': 1}
    if args.mode == 'crash':
        reserve = coordinator._reserve
        def reserved(p, state, stage):
            if args.boundary == 'before-reservation' and stage == 'facts':
                checkpoint(args.boundary)
            result = reserve(p, state, stage)
            if args.boundary == 'after-reservation' and stage == 'facts':
                checkpoint(args.boundary)
            return result
        coordinator._reserve = reserved
        if args.boundary == 'during-facts':
            def reconcile(paths, **kwargs):
                calls('facts')
                update(path, {'observed_at': 1234, 'probe_status': 'ok'})
                checkpoint(args.boundary)
            coordinator.reconcile_paths_now = reconcile
        if args.boundary == 'provider-after-own-write':
            source = {'tmdb_id': '745678', 'paths': [str(path)]}
            item['source_identity'] = source
            def resolve(source):
                calls('provider')
                update(path, {'tmdb_id': '745678', 'identity_status': 'accepted', 'identity_source': 'download_submission'})
                checkpoint(args.boundary)
            coordinator.dependencies = replace(deps, resolve_source_identity=resolve)
        if args.boundary == 'last-asset-attempt':
            state = {'version': 1, 'revision': 0, 'state': 'waiting', 'stage': 'assets', 'attempts': {'assets': 3},
                     'first_observed_at': 1000.0, 'require_publication': True, 'source_identity': {},
                     'evidence_signature': coordinator._episode_signature(path, {})}
            coordinator._write_episode(path, state)
            def prepare(paths):
                calls('assets')
                checkpoint(args.boundary)
            coordinator.dependencies = replace(deps, prepare_final_card_assets=prepare)
        if args.boundary == 'persisted-handoff-before-sibling':
            sibling = root / 'Sibling.mkv'
            sibling.write_bytes(b'sibling')
            item['source_identity'] = {'paths': [str(path), str(sibling)]}
            coordinator.dependencies = replace(deps, resolve_source_identity=lambda source: {'state': 'deferred', 'paths': []})
            resume = coordinator._resume_source_targets
            def admit(p, state, work):
                if state.get('handoff'):
                    checkpoint(args.boundary)
                return resume(p, state, work)
            coordinator._resume_source_targets = admit
        coordinator._run_path_episode(item)
        raise RuntimeError('Crash boundary was not reached')
    elif args.mode == 'resume':
        coordinator.recover_pending()
        recovered = [dict(work) for work in coordinator._pending.values()]
        coordinator._pending.clear()
        for work in recovered:
            coordinator._run_path_episode(work)
        report = {'ledger': coordinator._read_episode(path), 'recovered': recovered,
                  'pending': [dict(work) for work in coordinator._pending.values()],
                  'record': repository.get_record('app_metadata/files.json', key)}
        (root / 'resumed.json').write_text(json.dumps(report, indent=2))
    elif args.mode == 'order-seed':
        # File discovery order deliberately differs from retry admission order.
        for name in ['C', 'B', 'A']:
            target = root / (name + '.mkv')
            target.write_bytes(b'fixture')
            repository.upsert_record('app_metadata/files.json', store._key(target), {'path': str(target), 'size': 7})
        for name in ['A', 'B', 'C']:
            target = root / (name + '.mkv')
            state = {'version': 1, 'revision': 0, 'state': 'waiting', 'stage': 'facts', 'attempts': {'facts': 1},
                     'first_observed_at': 1000.0, 'next_due_at': 1002.0, 'require_publication': True,
                     'source_identity': {}, 'evidence_signature': coordinator._episode_signature(target, {})}
            coordinator._write_episode(target, state)
        checkpoint('order-seeded')
    elif args.mode == 'order-recover':
        coordinator.COALESCE_SECONDS = 0
        coordinator.recover_pending()
        actual = []
        execute = coordinator._run_path_episode
        def observed(work):
            actual.append(Path(work['value']).stem)
            return execute(work)
        coordinator._run_path_episode = observed
        coordinator._accepting = False
        coordinator._dispatch()
        (root / 'order.json').write_text(json.dumps(actual))
    repository.close(flush=False)


if __name__ == '__main__':
    main()
