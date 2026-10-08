"""Explicit, offline repair of already-published TV files; no automatic naming rule."""
import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import tempfile
import time
import uuid
import urllib.request

from services.qbittorrent import QBittorrentJobStore, _atomic_json_write
from services.tv_catalog_repository import TVCatalogRepository
from services.tv_filename_parser import parse_episode_name, series_identity
from services.verified_import import sha256


def require_offline():
    try:
        with socket.create_connection(('127.0.0.1', 5000), timeout=1):
            pass
    except OSError:
        return
    raise ValueError('CP is running; stop it before applying the repair')


def preview(repository, jobs, roots, homes, manifest_path):
    roots = [Path(root).resolve() for root in roots]
    plan = {'id': uuid.uuid4().hex, 'state': 'preview', 'created_at': time.time(),
            'catalog': str(repository.store.path), 'roots': list(map(str, roots)), 'folders': [], 'moves': []}
    records = jobs.all()
    targets = set()
    with repository.store.connection() as db:
        for old_text, home_text in homes.items():
            old, home = Path(old_text).resolve(), Path(home_text).resolve()
            assignment = db.execute("SELECT * FROM tv_path_assignments WHERE path=? AND kind='folder'", (str(old),)).fetchone()
            if not assignment or not old.name.isdigit() or old.parent not in roots:
                raise ValueError('Repair requires an approved numeric folder directly inside a TV root')
            series_id = assignment['series_id']
            series = repository.series(series_id)
            if int(old.name) != series['tmdb_id']:
                raise ValueError('Numeric folder and approved series identity disagree')
            if home == old or home.parent not in roots or home.name.isdigit() or not repository._import_path_allowed(home, series_id, roots, show_home=True):
                raise ValueError('Explicit show home is unsafe or belongs to another series')
            home_assignment = db.execute('SELECT series_id FROM tv_path_assignments WHERE path=?', (str(home),)).fetchone()
            if home.exists() and (not home_assignment or home_assignment[0] != series_id):
                raise ValueError('An existing show home must already be approved for this series')
            rows = [dict(r) for r in db.execute('SELECT * FROM media_files WHERE path LIKE ?', (str(old) + '\\%',))]
            # Path.parts also makes the utility's disposable tests portable.
            if os.name != 'nt':
                rows = [dict(r) for r in db.execute('SELECT * FROM media_files') if old in Path(r['path']).parents]
            physical = {str(p.resolve()) for p in old.rglob('*') if p.is_file()}
            if physical != {row['path'] for row in rows} or not rows:
                raise ValueError('Unknown or unbound numeric-folder contents require review')
            folder = {'old': str(old), 'home': str(home), 'series_id': series_id, 'title': series['title'], 'seasons': []}
            for row in rows:
                source = Path(row['path']).resolve()
                bindings = [dict(r) for r in db.execute('SELECT b.*,e.series_id,e.season_number,e.episode_number,e.reconciliation_required '
                    'FROM episode_file_bindings b JOIN episodes e ON e.id=b.episode_id WHERE b.file_id=?', (row['id'],))]
                seasons = {r['season_number'] for r in bindings}
                if not bindings or any(r['series_id'] != series_id or r['reconciliation_required'] for r in bindings) or len(seasons) != 1:
                    raise ValueError('File has ambiguous show/season bindings')
                season = next(iter(seasons))
                claim = parse_episode_name(source.name)
                if claim['ignored'] or claim['season_number'] != season or set(claim['episode_numbers']) != {r['episode_number'] for r in bindings} or series_identity({'title': source.name}, series)['state'] != 'matched':
                    raise ValueError('Filename and catalog episode identity disagree')
                if home.exists():
                    destination = repository.resolve_import_destination(series_id, season, roots)
                    # An approved empty home with an explicit Season NN is also a
                    # concrete migration destination, not a new acquisition fallback.
                    matches = [p for p in home.iterdir() if p.is_dir() and p.name.casefold() == f'season {season:02d}']
                    if destination['state'] == 'ready' and destination['show_home'] == str(home):
                        season_path = Path(destination['path'])
                    elif len(matches) == 1:
                        season_path = matches[0]
                    else:
                        raise ValueError('Existing home has no proved or explicit season destination')
                else:
                    if season <= 0:
                        raise ValueError('Specials require an explicit existing destination')
                    season_path = home / f'Season {season:02d}'
                target = season_path / source.name
                if not repository._import_path_allowed(target, series_id, roots):
                    raise ValueError('Destination is excluded or has conflicting ownership')
                if target.exists() or str(target) in targets or db.execute('SELECT 1 FROM media_files WHERE path=?', (str(target),)).fetchone():
                    raise ValueError('Destination collision requires review; no overwrite')
                ancestor = target.parent
                while not ancestor.exists():
                    ancestor = ancestor.parent
                if source.stat().st_dev != ancestor.stat().st_dev:
                    raise ValueError('This repair requires same-volume moves')
                stat = source.stat()
                if not row['available'] or stat.st_size != row['size'] or stat.st_mtime_ns != row['modified_ns']:
                    raise ValueError('Catalog file fingerprint changed')
                digest = sha256(source)
                references = [(key, item) for key, job in records.items() for item in job.get('preserving_import_plan', [])
                              if Path(item['target']).resolve() == source]
                if not references or any(item['sha256'] != digest or item['state'] != 'published' for _, item in references):
                    raise ValueError('Published job hash or publication state does not agree')
                targets.add(str(target))
                folder['seasons'].append(str(season_path))
                plan['moves'].append({'source': str(source), 'target': str(target), 'file_id': row['id'], 'series_id': series_id,
                    'size': stat.st_size, 'modified_ns': stat.st_mtime_ns, 'sha256': digest, 'bindings': bindings,
                    'jobs': sorted({key for key, _ in references}), 'move_state': 'pending'})
            folder['seasons'] = sorted(set(folder['seasons']))
            plan['folders'].append(folder)
    _atomic_json_write(manifest_path, plan)
    return plan


def _matching(path, row):
    return path.is_file() and path.stat().st_size == row['size'] and sha256(path) == row['sha256']


def apply(repository, jobs, roots, manifest_path, *, offline_check=require_offline, checkpoint=lambda *_: None,
          backup_dir=None, extra_backups=()):
    offline_check()
    manifest_path = Path(manifest_path)
    plan = json.loads(manifest_path.read_text(encoding='utf-8'))
    if Path(plan['catalog']).resolve() != repository.store.path.resolve():
        raise ValueError('Catalog owner changed after preview')
    if sorted(plan['roots']) != sorted(str(Path(r).resolve()) for r in roots):
        raise ValueError('Configured roots changed after preview')
    moves = plan['moves']
    for folder in plan['folders']:
        old = Path(folder['old'])
        expected = {move['source'] for move in moves if move['series_id'] == folder['series_id']}
        if old.exists() and any(str(path.resolve()) not in expected for path in old.rglob('*') if path.is_file()):
            raise ValueError('Unknown numeric-folder contents appeared after preview')
    with repository.store.connection() as db:
        actual = [db.execute('SELECT path FROM media_files WHERE id=?', (r['file_id'],)).fetchone() for r in moves]
        committed = all(row and row[0] == move['target'] for row, move in zip(actual, moves))
        if not committed and any(not row or row[0] != move['source'] for row, move in zip(actual, moves)):
            raise ValueError('Catalog paths changed after preview')
        for move in moves:
            bindings = [dict(r) for r in db.execute('SELECT b.*,e.series_id,e.season_number,e.episode_number,e.reconciliation_required '
                'FROM episode_file_bindings b JOIN episodes e ON e.id=b.episode_id WHERE b.file_id=?', (move['file_id'],))]
            if bindings != move['bindings']:
                raise ValueError('Episode bindings changed after preview')
    for move in moves:
        source, target = Path(move['source']), Path(move['target'])
        if committed or (not source.exists() and move['move_state'] in {'renaming', 'moved'}):
            if source.exists() or not _matching(target, move):
                raise ValueError('Repair destination changed or source unexpectedly reappeared')
        elif not _matching(source, move) or source.stat().st_mtime_ns != move['modified_ns']:
            raise ValueError('Repair source changed after preview')
        elif target.exists():
            raise ValueError('Destination collision appeared after preview')
        if not repository._import_path_allowed(target, move['series_id'], roots):
            raise ValueError('Destination ownership/exclusion changed after preview')
        for key in move['jobs']:
            job = jobs.get(key)
            candidates = [item for item in (job or {}).get('preserving_import_plan', [])
                          if item['target'] in ({move['source'], move['target']} if committed else {move['source']})]
            if not job or job.get('media_type') != 'tv' or len(candidates) != 1 or candidates[0]['sha256'] != move['sha256'] or candidates[0]['state'] != 'published':
                raise ValueError('Transfer publication references changed after preview')
    if not plan.get('backup_dir'):
        backup = Path(backup_dir or manifest_path.parent / 'backups' / plan['id'])
        backup.mkdir(parents=True, exist_ok=False)
        repository.store.backup(backup / 'tv-catalog.sqlite')
        shutil.copy2(jobs.path, backup / 'jobs.json')
        for source in extra_backups:
            source = Path(source)
            if source.suffix == '.sqlite':
                with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as original, closing(sqlite3.connect(backup / source.name)) as output:
                    original.backup(output)
            else:
                shutil.copy2(source, backup / source.name)
        plan['backup_dir'] = str(backup)
        plan['backup_hashes'] = {path.name: sha256(path) for path in backup.iterdir() if path.is_file()}
        _atomic_json_write(manifest_path, plan)
    try:
        if not committed:
            for move in moves:
                source, target = Path(move['source']), Path(move['target'])
                if source.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    move['move_state'] = 'renaming'
                    _atomic_json_write(manifest_path, plan)
                    os.rename(source, target)
                move['move_state'] = 'moved'
                _atomic_json_write(manifest_path, plan)
                if not _matching(target, move):
                    raise ValueError('Moved file verification failed')
            with repository.store.transaction() as db:
                for move in moves:
                    result = db.execute('UPDATE media_files SET path=?,size=?,modified_ns=? WHERE id=? AND path=?',
                        (move['target'], move['size'], Path(move['target']).stat().st_mtime_ns, move['file_id'], move['source']))
                    if result.rowcount != 1:
                        raise ValueError('Catalog changed while moving files')
                for folder in plan['folders']:
                    db.execute("INSERT INTO tv_path_assignments VALUES(?,'folder',?,?) ON CONFLICT(path) DO NOTHING",
                               (folder['home'], folder['series_id'], time.time()))
                    db.execute("INSERT INTO tv_import_homes(series_id,path,origin) VALUES(?,?,'existing') ON CONFLICT(series_id) DO UPDATE SET path=excluded.path,origin='existing'",
                               (folder['series_id'], folder['home']))
                    db.execute('DELETE FROM tv_path_assignments WHERE path=? AND series_id=?', (folder['old'], folder['series_id']))
                    db.execute("UPDATE tv_discovery_units SET state='resolved',updated_at=? WHERE path=?", (time.time(), folder['old']))
            committed = True
            plan['state'] = 'catalog_committed'
            _atomic_json_write(manifest_path, plan)
            checkpoint('catalog_committed')
        for key in sorted({key for move in moves for key in move['jobs']}):
            job = jobs.get(key)
            if not job:
                raise ValueError('Affected transfer journal entry is missing')
            mapping = {move['source']: move['target'] for move in moves if key in move['jobs']}
            import_plan = job['preserving_import_plan']
            for item in import_plan:
                old = item['target']
                if old in mapping:
                    new = Path(mapping[old])
                    item['target'] = str(new)
                    item['temporary'] = str(new.parent / Path(item['temporary']).name)
            destinations = {str(Path(p).parent) for p in mapping.values()}
            if len(destinations) != 1:
                raise ValueError('An affected job spans multiple destinations; review its bookkeeping')
            audit = job.get('tv_storage_repair') or {'id': plan['id'], 'original_destination': job['destination']}
            jobs.upsert(key, {'destination': next(iter(destinations)), 'preserving_import_plan': import_plan,
                'imported_paths': [mapping.get(path, path) for path in job.get('imported_paths', [])], 'tv_storage_repair': audit})
        for folder in plan['folders']:
            old = Path(folder['old'])
            if old.is_dir():
                # Only empty, explicitly inventoried numeric directories are removed.
                for child in sorted((p for p in old.rglob('*') if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
                    if old not in child.resolve().parents:
                        raise ValueError('Numeric directory cleanup escaped its approved folder')
                    child.rmdir()
                old.rmdir()
        plan['state'] = 'complete'
        _atomic_json_write(manifest_path, plan)
        return plan
    except Exception:
        if not committed:
            for move in reversed(moves):
                source, target = Path(move['source']), Path(move['target'])
                if not source.exists() and move['move_state'] in {'renaming', 'moved'} and _matching(target, move):
                    os.rename(target, source)
                move['move_state'] = 'pending'
            plan['state'] = 'preview'
            _atomic_json_write(manifest_path, plan)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['preview', 'apply'])
    parser.add_argument('--project-root', type=Path, default=Path.cwd())
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--homes-json', type=Path)
    args = parser.parse_args()
    project = args.project_root.resolve()
    config = json.loads((project / 'config.json').read_text(encoding='utf-8-sig'))
    data = Path(config['user_data_dir']).resolve()
    jobs = QBittorrentJobStore(data / 'qbittorrent/jobs.json')
    if args.command == 'preview':
        # Never initialize/migrate the production database just to inspect it.
        with tempfile.TemporaryDirectory(prefix='cp-tv-repair-preview-') as directory:
            copied = Path(directory) / 'tv.sqlite'
            with closing(sqlite3.connect((data / 'tv-catalog.sqlite').as_uri() + '?mode=ro', uri=True)) as source, closing(sqlite3.connect(copied)) as target:
                source.backup(target)
            result = preview(TVCatalogRepository(copied), jobs, config['tv_roots'],
                             json.loads(args.homes_json.read_text()), args.manifest)
            result['catalog'] = str(data / 'tv-catalog.sqlite')
            _atomic_json_write(args.manifest, result)
    else:
        require_offline()
        with urllib.request.urlopen(f"http://127.0.0.1:{config.get('qbt_webui_port', 8686)}/api/v2/torrents/info", timeout=8) as response:
            if json.load(response):
                raise ValueError('qBittorrent has active transfers; review them before applying this offline repair')
        repository = TVCatalogRepository(data / 'tv-catalog.sqlite')
        result = apply(repository, jobs, config['tv_roots'], args.manifest,
                       backup_dir=data / 'backups' / ('tv-numeric-repair-' + json.loads(args.manifest.read_text())['id']),
                       extra_backups=[data / 'acquisition.sqlite', project / 'config.json'])
    print(json.dumps({'state': result['state'], 'files': len(result['moves']), 'manifest': str(args.manifest.resolve()),
                      'destinations': [r['seasons'] for r in result['folders']]}, indent=2))


if __name__ == '__main__':
    main()
