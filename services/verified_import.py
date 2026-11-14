"""Verified publication and recoverable source cleanup in the transfer journal."""
import hashlib
import os
from pathlib import Path
import shutil
import stat


def verified_staging_source(path, staging_root):
    """Keep the manifest path inside staging without traversing directory aliases."""
    root = Path(os.path.abspath(staging_root))
    source = Path(os.path.abspath(path))
    if root not in source.parents:
        raise ValueError('Cleanup source escaped staging')
    current = root
    for component in ('', *source.relative_to(root).parts):
        if component:
            current = current / component
        try:
            attributes = current.lstat()
        except FileNotFoundError:
            continue  # A previously checkpointed cleanup may have removed this path.
        if stat.S_ISLNK(attributes.st_mode) or getattr(attributes, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400):
            raise ValueError('Staging source traverses a symbolic link or directory junction; review required')
    return source.resolve()


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def verified_rollback_available(job):
    if not job or job.get('cleanup_started') or job.get('state') == 'rolled_back':
        return False
    plan = job.get('preserving_import_plan') or []
    try:
        return bool(plan) and all(Path(row['source']).is_file() and
            Path(row['source']).stat().st_size == row['size'] and
            Path(row['source']).stat().st_mtime_ns == row['source_modified_ns'] for row in plan)
    except (OSError, KeyError):
        return False


def import_verified_files(jobs, torrent_hash, sources, staging_root, destination, *, mode='hardlink_copy', upgrade=False, checkpoint=lambda *_: None):
    staging_root, destination = Path(staging_root).resolve(), Path(destination).resolve()
    if staging_root == destination or staging_root in destination.parents or destination in staging_root.parents:
        raise ValueError('Staging and library roots must be separate and non-nested')
    if mode not in {'hardlink_copy', 'copy', 'move'}:
        raise ValueError('Verified import requires move, hardlink/copy or copy mode')
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
        active_targets = {row['target'] for key, other in jobs.all().items() if key != torrent_hash
                          and other.get('state') not in {'imported', 'rolled_back', 'cancelled', 'seed_complete'}
                          for row in other.get('preserving_import_plan') or []}
        for source in paths:
            digest = sha256(source)
            target = destination / source.name
            number = 1
            pre_existing = False
            if mode == 'move':
                if str(target) in active_targets or str(target) in reserved:
                    raise ValueError('Destination collision with another active import')
                if target.exists():
                    if target.is_file() and target.stat().st_size == source.stat().st_size and sha256(target) == digest:
                        pre_existing = True
                    elif not upgrade:
                        raise ValueError('Destination collision; different existing content requires review')
                    else:
                        while target.exists() or str(target) in reserved or str(target) in active_targets:
                            target = destination / f'{source.stem} [upgrade {number}]{source.suffix}'
                            number += 1
            else:
                while target.exists() or str(target) in reserved:
                    target = destination / f'{source.stem} [{torrent_hash[:8]}-{number}]{source.suffix}'
                    number += 1
            reserved.add(str(target))
            temporary = target.with_name(f'.{target.name}.{torrent_hash[:12]}.partial')
            if mode == 'move' and temporary.exists():
                raise ValueError('Unexplained temporary destination collision; review required')
            plan.append({'source': str(source), 'target': str(target), 'temporary': str(temporary),
                         'size': source.stat().st_size, 'source_modified_ns': source.stat().st_mtime_ns,
                         'sha256': digest, 'state': 'published' if pre_existing else 'planned',
                         'pre_existing': pre_existing, 'method': 'reused' if pre_existing else None})
        jobs.upsert(torrent_hash, {'preserving_import_plan': plan, 'state': 'importing', 'import_mode': mode,
                                  'rollback_available': True})
        checkpoint('planned', plan)
    needed = sum(row['size'] for row in plan if row['state'] != 'published' and (mode in {'copy', 'move'} or Path(row['source']).stat().st_dev != destination.stat().st_dev))
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
    if job.get('tv_lifecycle_version') == 1 and job.get('cleanup_started'):
        raise ValueError('Rollback is unavailable after move cleanup starts; finish recovery instead')
    plan = job.get('preserving_import_plan') or []
    for row in plan:
        source, target = Path(row['source']), Path(row['target'])
        if not source.is_file() or sha256(source) != row['sha256']:
            raise ValueError('Rollback requires an intact retained source')
        if target.exists() and sha256(target) != row['sha256']:
            raise ValueError('Rollback refused: published file has changed')
    def published_by_job(row):
        return job.get('import_mode') != 'move' or row['state'] in {'verified', 'published'}
    unpublish([row['target'] for row in plan if not row.get('binding_pre_existing') and published_by_job(row)])
    for row in plan:
        for key in ('target', 'temporary'):
            if key == 'target' and (row.get('pre_existing') or not published_by_job(row)):
                continue
            path = Path(row[key])
            if path.exists():
                path.unlink()
        row['state'] = 'rolled_back'
    return jobs.upsert(torrent_hash, {'state': 'rolled_back', 'preserving_import_plan': plan, 'imported_paths': [], 'source_retained': True, 'rollback_available': False})


def finalize_verified_move(jobs, torrent_hash, staging_root):
    """Unlink only journal-owned sources after durable catalog and transfer checkpoints."""
    job = jobs.get(torrent_hash)
    if not job or job.get('tv_publication', {}).get('state') != 'committed' or not job.get('torrent_removed'):
        raise ValueError('Move cleanup requires committed TV publication and torrent removal')
    staging_root = Path(staging_root).resolve()
    recorded_path = Path(job['tv_staging_root'])
    recorded_root = (verified_staging_source(recorded_path, staging_root)
                     if recorded_path != staging_root else staging_root)
    if recorded_root != staging_root and staging_root not in recorded_root.parents:
        raise ValueError('Recorded cleanup directory escaped staging')
    plan = job['preserving_import_plan']
    declared = {row['source'] for row in job['tv_selected_files']}
    if {row['source'] for row in plan} != declared:
        raise ValueError('Move cleanup does not match the validated selected manifest')
    auxiliary = job.get('tv_auxiliary_files') or []
    skipped = ((job.get('validated_manifest') or {}).get('domain') or {}).get('skipped_files') or []
    source_paths = {row['source']: recorded_root / row['name'] if row.get('name') else Path(row['source'])
                    for row in job['tv_selected_files']}
    for row in auxiliary:
        if row.get('name') not in skipped:
            raise ValueError('Auxiliary cleanup does not match the validated skipped manifest')
        path = recorded_root / row['name']
        if str(verified_staging_source(path, staging_root)) != row['source']:
            raise ValueError('Auxiliary cleanup path changed; review required')
        source_paths[row['source']] = path
    auxiliary_sources = {row['source'] for row in auxiliary}
    if auxiliary_sources & declared or len(auxiliary_sources) != len(auxiliary):
        raise ValueError('Auxiliary cleanup does not match the validated skipped manifest')
    declared |= auxiliary_sources
    cleanup_sources = plan + auxiliary
    for row in cleanup_sources:
        source = verified_staging_source(source_paths[row['source']], staging_root)
        if str(source) != row['source']:
            raise ValueError('Cleanup source path changed; review required')
        if staging_root not in source.parents or (recorded_root != source.parent and recorded_root not in source.parents):
            raise ValueError('Cleanup source escaped its recorded staging directory')
        if 'target' in row:
            target = Path(row['target']).resolve()
            if not target.is_file() or target.stat().st_size != row['size'] or sha256(target) != row['sha256']:
                raise ValueError('Published destination changed; cleanup requires review')
        if source.exists():
            if not source.is_file() or source.stat().st_size != row['size'] or sha256(source) != row['sha256']:
                raise ValueError('Source changed; cleanup requires review')
        elif row.get('cleanup_state') not in {'unlinking', 'removed'}:
            raise ValueError('Source missing without a journaled cleanup checkpoint')
        for key, other in jobs.all().items():
            if key == torrent_hash:
                continue
            if other.get('state') == 'imported' and not other.get('source_retained'):
                continue
            references = list(other.get('payload_paths') or [])
            references += [entry['source'] for entry in other.get('preserving_import_plan') or []]
            references += [entry['source'] for entry in other.get('tv_selected_files') or []]
            references += [entry['source'] for entry in other.get('tv_auxiliary_files') or []]
            other_root = Path(other.get('tv_staging_root') or other.get('tv_download_staging_root') or staging_root)
            references += [str(other_root / entry['name']) for entry in
                ((other.get('validated_manifest') or {}).get('domain') or {}).get('mappings', [])]
            references += [str(other_root / name) for name in
                ((other.get('validated_manifest') or {}).get('domain') or {}).get('skipped_files', [])]
            if any(Path(path).resolve() == source for path in references):
                raise ValueError('Source is referenced by another active job; cleanup requires review')
    # A dedicated payload directory belongs to this job only when its contents are known.
    # The shared staging root itself may contain other jobs and is never traversed/deleted.
    cleanup_dirs = {Path(row['source']).parent for row in cleanup_sources if Path(row['source']).parent != staging_root}
    if recorded_root != staging_root:
        cleanup_dirs.add(recorded_root)
    for folder in cleanup_dirs:
        if folder.exists() and any(path.is_file() and str(path.resolve()) not in declared for path in folder.rglob('*')):
            raise ValueError('Unknown staging contents; cleanup requires review')
    jobs.upsert(torrent_hash, {'cleanup_started': True, 'rollback_available': False})
    for row in cleanup_sources:
        source = verified_staging_source(source_paths[row['source']], staging_root)
        if str(source) != row['source']:
            raise ValueError('Cleanup source path changed; review required')
        if source.exists():
            row['cleanup_state'] = 'unlinking'
            jobs.upsert(torrent_hash, {'preserving_import_plan': plan, 'tv_auxiliary_files': auxiliary})
            source.unlink()
        row['cleanup_state'] = 'removed'
        jobs.upsert(torrent_hash, {'preserving_import_plan': plan, 'tv_auxiliary_files': auxiliary})
    for folder in sorted(cleanup_dirs, key=lambda path: len(path.parts), reverse=True):
        while folder != staging_root and staging_root in folder.resolve().parents and folder.is_dir():
            if any(folder.iterdir()):
                break
            folder.rmdir()
            folder = folder.parent
    return jobs.upsert(torrent_hash, {'state': 'imported', 'source_retained': False, 'rollback_available': False,
        'cleanup_complete': True, 'library_scan_pending': False, 'identity_handoff': {'state': 'tv_published'}, 'last_error': ''})
