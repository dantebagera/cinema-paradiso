"""Coordinated offline recovery points; never includes movie or IPTV stores.

The application must be stopped before restore. Backup takes all supplied owner
locks and holds write reservations on both databases while copying jobs.json.
"""
from contextlib import ExitStack, closing
import hashlib
import json
from pathlib import Path
import sqlite3
from services.tv_catalog_store import guarded_path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def checkpoint(tv, acquisition, manager, destination, *, acquisition_lock):
    destination = guarded_path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    with acquisition_lock, manager._completion_lock, tv.store._lock, manager.jobs._lock, ExitStack() as stack:
        connections = [stack.enter_context(owner.connection()) for owner in (tv.store, acquisition)]
        for db in connections:
            db.execute('BEGIN IMMEDIATE')
        for owner, name in ((tv.store, 'tv-catalog.sqlite'), (acquisition, 'acquisition.sqlite')):
            with owner.connection() as source, closing(sqlite3.connect(destination/name)) as target:
                source.backup(target)
        (destination/'jobs.json').write_text(json.dumps(manager.jobs._read()), encoding='utf-8')
    names = ['tv-catalog.sqlite', 'acquisition.sqlite', 'jobs.json']
    manifest = {'version': 1, 'files': {name: digest(destination/name) for name in names}}
    (destination/'checkpoint.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return manifest


def restore_offline(snapshot, tv_path, acquisition_path, jobs_path, *, application_stopped=False):
    if application_stopped is not True:
        raise ValueError('Coordinated restore requires the application to be stopped')
    snapshot = guarded_path(snapshot)
    manifest = json.loads((snapshot/'checkpoint.json').read_text(encoding='utf-8'))
    names = ['tv-catalog.sqlite', 'acquisition.sqlite', 'jobs.json']
    if manifest.get('version') != 1 or set(manifest.get('files', {})) != set(names):
        raise ValueError('Invalid checkpoint manifest')
    for name in names:
        if digest(snapshot/name) != manifest['files'][name]:
            raise ValueError('Checkpoint checksum mismatch')
    for name, marker in [('tv-catalog.sqlite', 'episodes'), ('acquisition.sqlite', 'intents')]:
        with closing(sqlite3.connect(snapshot/name)) as db:
            if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or db.execute('PRAGMA foreign_key_check').fetchall() or not db.execute("SELECT 1 FROM sqlite_master WHERE name=?", (marker,)).fetchone():
                raise ValueError('Invalid checkpoint database')
    jobs = json.loads((snapshot/'jobs.json').read_text(encoding='utf-8'))
    if not isinstance(jobs, dict) or not isinstance(jobs.get('jobs'), dict):
        raise ValueError('Invalid checkpoint jobs')
    paths = [guarded_path(value) for value in (tv_path, acquisition_path, jobs_path)]
    if len(set(paths)) != 3 or any(path in [snapshot/name for name in names] for path in paths):
        raise ValueError('Recovery destinations must be distinct from checkpoint sources')
    # A checkpoint remains intact throughout restore so interrupted restores can repeat.
    for name, path in zip(names[:2], paths[:2]):
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(snapshot/name)) as source, closing(sqlite3.connect(path)) as target:
            source.backup(target)
    paths[2].parent.mkdir(parents=True, exist_ok=True)
    temporary = paths[2].with_suffix('.restore.tmp')
    temporary.write_text(json.dumps(jobs), encoding='utf-8')
    temporary.replace(paths[2])
    return {'restored': names}
