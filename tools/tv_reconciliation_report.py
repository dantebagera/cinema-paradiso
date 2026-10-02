"""Read-only accounting for every supported video in configured TV roots."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import sqlite3

from services.tv_filename_parser import VIDEO_EXTENSIONS, parse_episode_name


def table_exists(db, name):
    return db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def report(config_path, database_path):
    config = json.loads(Path(config_path).read_text(encoding='utf-8'))
    roots = [Path(root).resolve() for root in config.get('tv_roots') or []]
    uri = Path(database_path).resolve().as_uri() + '?mode=ro'
    with sqlite3.connect(uri, uri=True) as db:
        db.row_factory = sqlite3.Row
        assignments = [dict(row) for row in db.execute('SELECT a.path,a.kind,a.series_id,s.title FROM tv_path_assignments a JOIN series s ON s.id=a.series_id')]
        exclusions = [dict(row) for row in db.execute('SELECT path,kind,reason FROM tv_exclusions')] if table_exists(db, 'tv_exclusions') else []
        bindings = {}
        for row in db.execute('SELECT f.path,e.id AS episode_id,e.series_id,e.season_number,e.episode_number,s.title '
                              'FROM media_files f JOIN episode_file_bindings b ON b.file_id=f.id '
                              'JOIN episodes e ON e.id=b.episode_id JOIN series s ON s.id=e.series_id'):
            bindings.setdefault(row['path'], []).append(dict(row))
        reviews = {}
        for row in db.execute("SELECT payload,reason FROM ingestion_candidates WHERE state='needs_review'"):
            payload = json.loads(row['payload'])
            reviews.setdefault(payload.get('path'), []).append(row['reason'])
        discoveries = {}
        if table_exists(db, 'tv_discovery_units'):
            for row in db.execute('SELECT path,state,payload FROM tv_discovery_units'):
                discoveries[row['path']] = {**json.loads(row['payload']), 'state': row['state']}

    items = []
    for root in roots:
        if not root.is_dir():
            items.append({'path': str(root), 'state': 'scan_error', 'reason': 'Configured TV root is unavailable'})
            continue
        for directory, dirs, names in os.walk(root, followlinks=False):
            dirs[:] = [name for name in dirs if not (Path(directory) / name).is_symlink()]
            for name in names:
                if Path(name).suffix.casefold() not in VIDEO_EXTENSIONS:
                    continue
                path = (Path(directory) / name).resolve()
                if root not in path.parents or not path.is_file():
                    items.append({'path': str(path), 'state': 'scan_error', 'reason': 'Video path escaped the configured root or disappeared'})
                    continue
                owners = [row for row in assignments if (row['kind'] == 'file' and path == Path(row['path'])) or
                          (row['kind'] == 'folder' and Path(row['path']) in path.parents)]
                owner = max(owners, key=lambda row: len(Path(row['path']).parts), default=None)
                excluded = next((row for row in exclusions if (row['kind'] == 'file' and path == Path(row['path'])) or
                                 (row['kind'] == 'folder' and Path(row['path']) in path.parents)), None)
                claim = parse_episode_name(name)
                linked = bindings.get(str(path), [])
                reasons = reviews.get(str(path), [])
                discovery = next((value for key, value in discoveries.items() if path == Path(key) or Path(key) in path.parents), None)
                state = ('excluded' if excluded else 'linked' if linked else 'episode_review' if reasons else
                         'show_review' if discovery and discovery['state'] == 'review' else
                         'scan_error' if discovery and discovery['state'] == 'scan_error' else
                         'episode_unresolved' if owner else 'show_unresolved')
                items.append({'path': str(path), 'state': state, 'root': str(root),
                              'assignment': owner, 'show_identity': owner['series_id'] if owner else None,
                              'episode_identity': [row['episode_id'] for row in linked],
                              'binding': bool(linked), 'exclusion': excluded,
                              'review_reason': reasons or ([discovery['reason']] if discovery and discovery.get('reason') else []),
                              'claim': claim})
    counts = dict(sorted(Counter(item['state'] for item in items).items()))
    return {'roots': [str(root) for root in roots], 'total': len(items), 'states': counts, 'files': items}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default='config.json')
    parser.add_argument('--database', default='data/tv-catalog.sqlite')
    parser.add_argument('--output')
    args = parser.parse_args()
    result = report(args.config, args.database)
    if args.output:
        Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({key: result[key] for key in ('roots', 'total', 'states')}, ensure_ascii=False))
