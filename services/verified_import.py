"""Seeding-preserving file operations using QBittorrentJobStore's journal only."""
import hashlib
import os
from pathlib import Path
import shutil


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def import_verified_files(jobs, torrent_hash, sources, staging_root, destination, *, mode='hardlink_copy', checkpoint=lambda *_: None):
    staging_root, destination = Path(staging_root).resolve(), Path(destination).resolve()
    if staging_root == destination or staging_root in destination.parents or destination in staging_root.parents:
        raise ValueError('Staging and library roots must be separate and non-nested')
    if mode not in {'hardlink_copy', 'copy'}:
        raise ValueError('Preserving import requires hardlink/copy or copy mode')
    job = jobs.get(torrent_hash)
    if not job:
        raise ValueError('Transfer job not found')
    paths = [Path(path).resolve() for path in sources]
    if not paths or len(paths) != len(set(paths)):
        raise ValueError('A unique nonempty file list is required')
    for path in paths:
        if staging_root not in path.parents or not path.is_file():
            raise ValueError('Import source escaped staging or is missing')
    destination.mkdir(parents=True, exist_ok=True)
    plan = job.get('preserving_import_plan') or []
    if plan and {row['source'] for row in plan} != {str(path) for path in paths}:
        raise ValueError('Import source list changed after journaling')
    if not plan:
        reserved = set()
        for source in paths:
            digest = sha256(source)
            target = destination / source.name
            number = 1
            while target.exists() or str(target) in reserved:
                target = destination / f'{source.stem} [{torrent_hash[:8]}-{number}]{source.suffix}'
                number += 1
            reserved.add(str(target))
            plan.append({'source': str(source), 'target': str(target), 'temporary': str(target.with_name(f'.{target.name}.{torrent_hash[:12]}.partial')),
                         'size': source.stat().st_size, 'sha256': digest, 'state': 'planned', 'method': None})
        jobs.upsert(torrent_hash, {'preserving_import_plan': plan, 'state': 'importing', 'import_mode': mode})
        checkpoint('planned', plan)
    needed = sum(row['size'] for row in plan if row['state'] != 'published' and (mode == 'copy' or Path(row['source']).stat().st_dev != destination.stat().st_dev))
    if shutil.disk_usage(destination).free < needed:
        raise OSError('Insufficient destination space for verified import')
    for row in plan:
        source, target, temporary = (Path(row[key]) for key in ('source', 'target', 'temporary'))
        if target.parent.resolve() != destination or temporary.parent.resolve() != destination:
            raise ValueError('Journal destination escaped the configured library')
        if source.stat().st_size != row['size'] or sha256(source) != row['sha256']:
            raise ValueError('Source changed after import was journaled')
        if target.exists():
            if row['state'] not in {'verified', 'published'} or sha256(target) != row['sha256']:
                raise ValueError('Destination collision; existing file will not be overwritten')
        else:
            if temporary.exists():
                if sha256(temporary) != row['sha256']:
                    # This exact partial path was created by this journal, not library data.
                    temporary.unlink()
            if not temporary.exists():
                row['state'] = 'copying'
                jobs.upsert(torrent_hash, {'preserving_import_plan': plan})
                if mode == 'hardlink_copy':
                    try:
                        os.link(source, temporary)
                        row['method'] = 'hardlink'
                    except OSError:
                        row['method'] = 'copy'
                else:
                    row['method'] = 'copy'
                if row['method'] == 'copy':
                    if shutil.disk_usage(destination).free < row['size']:
                        raise OSError('Insufficient copy fallback space')
                    with open(source, 'rb') as input_stream, open(temporary, 'xb') as output_stream:
                        shutil.copyfileobj(input_stream, output_stream, length=1024*1024)
                        output_stream.flush()
                        os.fsync(output_stream.fileno())
            if temporary.stat().st_size != row['size'] or sha256(temporary) != row['sha256'] or sha256(source) != row['sha256']:
                raise ValueError('Copied media verification failed')
            row['state'] = 'verified'
            jobs.upsert(torrent_hash, {'preserving_import_plan': plan})
            checkpoint('verified', row)
            # Exclusive publication: never replace an existing library file.
            if os.name == 'nt':
                os.rename(temporary, target)
            else:
                os.link(temporary, target)
                temporary.unlink()
            checkpoint('published_before_journal', row)
        row['state'] = 'published'
        jobs.upsert(torrent_hash, {'preserving_import_plan': plan, 'imported_paths': [item['target'] for item in plan if item['state'] == 'published']})
        checkpoint('published', row)
    return jobs.upsert(torrent_hash, {'state': 'payload_imported', 'last_error': '', 'payload_paths': [str(path) for path in paths], 'source_retained': True})


def rollback_verified_files(jobs, torrent_hash, *, unpublish):
    job = jobs.get(torrent_hash)
    if not job:
        raise ValueError('Transfer job not found')
    plan = job.get('preserving_import_plan') or []
    for row in plan:
        source, target = Path(row['source']), Path(row['target'])
        if not source.is_file() or sha256(source) != row['sha256']:
            raise ValueError('Rollback requires an intact retained source')
        if target.exists() and sha256(target) != row['sha256']:
            raise ValueError('Rollback refused: published file has changed')
    unpublish([row['target'] for row in plan])
    for row in plan:
        for key in ('target', 'temporary'):
            path = Path(row[key])
            if path.exists():
                path.unlink()
        row['state'] = 'rolled_back'
    return jobs.upsert(torrent_hash, {'state': 'rolled_back', 'preserving_import_plan': plan, 'imported_paths': [], 'source_retained': True})
