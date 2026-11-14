"""Persistent disposable backend for crash boundaries and compiled desktop checks."""
import argparse
from dataclasses import replace
import json
import os
from pathlib import Path
import tempfile
import threading
import time
from types import SimpleNamespace
from unittest.mock import patch


def configure(root, *, fail_poster=False, boundary=''):
    root = Path(root).resolve()
    declared = Path(os.environ['CP_TEST_ROOT']).resolve()
    if (os.environ.get('CP_TEST_MODE') != '1' or os.environ.get('CP_TEST_QBT_MODE') != 'embedded'
            or declared not in root.parents or Path(tempfile.gettempdir()).resolve() not in root.parents):
        raise RuntimeError('Temporary embedded test descendants only')
    root.mkdir(parents=True, exist_ok=True)
    import app
    from services.catalog_events import CatalogEventBroker
    from services.media_file_facts import MediaFileFacts
    from tests.test_media_assets import _png, _Response
    app._user_data_dir = str(root / 'data')
    media = root / 'media'
    media.mkdir(exist_ok=True)
    app._movies_dirs = [str(media)]
    app._movies_dir = str(media)
    app._library_ingestion_coordinator_instance = None
    app._library_cache = {}
    app._stats_cache = {}
    app._catalog_event_broker = CatalogEventBroker()
    app.LibraryIngestionCoordinator._ensure_dispatcher_locked = lambda self: None
    store = app.AppMetadataStore(root / 'data')
    store.save_authority_state({'active_provider': 'tmdb'})
    metadata = {'tmdb_id': '810001', 'title': 'Qualification Import', 'year': '2026',
                'plot': 'Persistent isolated poster retry and publication fixture.',
                'poster_url': 'https://fixture.invalid/poster.png', 'genres': ['Drama'],
                'cast': [], 'directors': [], 'writers': [], 'certification': '', 'keywords': []}
    path = media / 'Qualification.Import.2026.1080p.mkv'
    job_file = root / 'job.json'
    if not job_file.exists():
        path.write_bytes(b'isolated movie')
        stable = time.time() - 60
        os.utime(path, (stable, stable))
        job_file.write_text(json.dumps({'hash': 'qualification-import', 'state': 'imported',
            'library_scan_pending': True, 'imported_paths': [str(path)], **metadata}))
        app._curation_store().follow_movie({**metadata, 'status': 'available'})
    clock = [time.time()]
    calls_file = root / 'poster-calls.json'
    def checkpoint(label):
        with (root / 'checkpoint.json').open('w') as output:
            json.dump({'pid': os.getpid(), 'boundary': label}, output)
            output.flush()
            os.fsync(output.fileno())
        threading.Event().wait(120)
        raise RuntimeError('Parent did not terminate fixture worker')
    def log(name, data):
        with (root / (name + '.jsonl')).open('a') as output:
            output.write(json.dumps(data) + '\n')
    def upsert(_hash, changes):
        job = json.loads(job_file.read_text())
        job.update(changes)
        job_file.write_text(json.dumps(job))
        log('journal', changes)
        if boundary == 'after-ack' and changes.get('library_scan_pending') is False:
            checkpoint(boundary)
        return job
    manager = SimpleNamespace(jobs=SimpleNamespace(upsert=upsert))
    def probe(value, **kwargs):
        measured = Path(value).stat()
        return MediaFileFacts(probe_status='ok', probe_size=measured.st_size,
            probe_modified_time=measured.st_mtime, quality_class='1080p', quality_source='measured')
    patch('app.probe_media_file', side_effect=probe).start()
    def fetch(identity, **kwargs):
        return metadata if str(identity) == metadata['tmdb_id'] else store.get_tmdb_metadata(str(identity))
    patch('app._fetch_tmdb_metadata_by_id', side_effect=fetch).start()
    # No external service is used by this fixture, including Home's source scan.
    app._check_followed_releases = lambda *args, **kwargs: {
        'movies': app._curation_store().followed_all(), 'newly_available': [], 'removed_owned': []}
    service = app._media_asset_service()
    def open_poster(request, **kwargs):
        count = json.loads(calls_file.read_text()) if calls_file.exists() else 0
        calls_file.write_text(json.dumps(count + 1))
        if fail_poster and count == 0:
            raise TimeoutError('controlled first poster transport failure')
        return _Response(_png())
    service.open_url = open_poster
    coordinator = app._library_ingestion_coordinator()
    original_commit = coordinator.dependencies.final_card_publication
    original_event = coordinator.dependencies.publish_catalog_event
    def commit(paths):
        publications = original_commit(paths)
        if publications:
            log('publication', publications)
            if boundary == 'after-commit-before-event':
                checkpoint(boundary)
        return publications
    def event(**value):
        result = original_event(**value)
        log('events', value)
        if boundary == 'after-event-before-ack':
            checkpoint(boundary)
        return result
    coordinator.dependencies = replace(coordinator.dependencies, wall_time=lambda: clock[0],
        final_card_publication=commit, publish_catalog_event=event)
    def status():
        row = store.catalog.get_record('app_metadata/files.json', store._key(path), {})
        publication = store.catalog.publication_status([str(path)]).get(store._key(path), {})
        return {'pid': os.getpid(), 'job': json.loads(job_file.read_text()),
                'ledger': row.get('_ingestion_retry', {}), 'publication': publication,
                'poster_calls': json.loads(calls_file.read_text()) if calls_file.exists() else 0,
                'events': app._catalog_event_broker.status()['retained'],
                'generation': store.catalog.generation('media'),
                'followed_count': len(app._curation_store().followed_all())}
    def drive():
        job = json.loads(job_file.read_text())
        app._handle_completed_qbittorrent_imports(manager, [job])
        coordinator.recover_pending()
        pending = list(coordinator._pending.values())
        coordinator._pending.clear()
        for item in pending:
            coordinator._run_path_episode(item)
        app._handle_completed_qbittorrent_imports(manager, [json.loads(job_file.read_text())])
        return status()
    return SimpleNamespace(app=app, root=root, store=store, media=media, path=path,
                           clock=clock, status=status, drive=drive, metadata=metadata)


def seed_bulk(fixture):
    from tests.test_catalog_store import CatalogStoreTest
    connection = fixture.store.catalog.store.connect()
    try:
        count = connection.execute('SELECT COUNT(*) FROM media_files').fetchone()[0]
        seeded = connection.execute("SELECT title FROM tmdb_movies WHERE tmdb_id='1000'").fetchone()
    finally:
        connection.close()
    if count == 4000 and seeded and seeded[0] == 'Search Fixture 0000':
        return  # Reuse the approved read-bound fixture without another bulk import.
    documents = CatalogStoreTest()._paging_documents(4000)
    files = {}
    for index, old in enumerate(documents['app_metadata/files.json']['files'].values()):
        path = fixture.media / f'Search.Fixture.{index:04d}.mkv'
        path.write_bytes(b'movie')
        row = {**old, 'path': str(path), 'filename': path.name, 'library_root': str(fixture.media),
               'identity_title': f'Search Fixture {index:04d}'}
        files[fixture.store._key(path)] = row
        movie = documents['app_metadata/tmdb_metadata.json']['movies'][row['tmdb_id']]
        movie.update(title=row['identity_title'], poster_url='', plot=('Synthetic dense plot. ' * 10))
    documents['app_metadata/files.json']['files'] = files
    documents['app_metadata/poster_overrides.json'] = {'overrides': []}
    documents['followed_releases.json'] = fixture.store.catalog.read_document('followed_releases.json', {'movies': []})
    fixture.store.catalog.store.import_documents(documents, {})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['crash', 'resume', 'server'])
    parser.add_argument('root')
    parser.add_argument('--boundary', default='')
    args = parser.parse_args()
    fixture = configure(args.root, fail_poster=args.mode == 'server', boundary=args.boundary)
    if args.mode in {'crash', 'resume'}:
        fixture.drive()
        report = fixture.drive()
        if args.mode == 'resume':
            response = fixture.app.app.test_client().get('/api/library?view=cards')
            report['library_api_status'] = response.status_code
            report['library_api'] = response.get_json()
            fixture.app._reconcile_followed_release_ownership()
            report['followed_count_after_ownership'] = len(fixture.app._curation_store().followed_all())
            broker = fixture.app._catalog_event_broker
            client = broker.subscribe(last_event_id=0, current_generation=report['generation'])
            try:
                report['reconnect_event'] = client.get_nowait()
            finally:
                broker.unsubscribe(client)
        (fixture.root / 'backend-result.json').write_text(json.dumps(report, indent=2))
        if args.mode == 'crash':
            raise RuntimeError('Backend crash checkpoint was not reached')
        return
    seed_bulk(fixture)
    app = fixture.app
    @app.app.route('/api/test/qualification/status')
    def status():
        return app.jsonify(fixture.status())
    @app.app.route('/api/test/qualification/drive', methods=['POST'])
    def drive():
        return app.jsonify(fixture.drive())
    @app.app.route('/api/test/qualification/advance', methods=['POST'])
    def advance():
        fixture.clock[0] += 2.1
        return app.jsonify({'advanced_seconds': 2.1})
    port = int(os.environ['CP_PORT'])
    if port == 5000:
        raise RuntimeError('Production port prohibited')
    app.app.run(host='127.0.0.1', port=port, threaded=True, use_reloader=False)


if __name__ == '__main__':
    main()
