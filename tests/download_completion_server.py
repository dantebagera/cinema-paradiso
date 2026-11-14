"""OS-temp-only fixture exercising real import, catalog, SSE and Following routes."""
import os
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import Mock, patch

if os.environ.get('CP_TEST_MODE') != '1':
    raise RuntimeError('Completion fixture requires CP_TEST_MODE')
root = Path(os.environ['CP_TEST_ROOT']).resolve()
if Path(tempfile.gettempdir()).resolve() not in root.parents:
    raise RuntimeError('OS-temporary test root required')
port = int(os.environ.get('CP_PORT', '5121'))
if port == 5000:
    raise RuntimeError('Production port prohibited')

import app
from services.catalog_events import CatalogEventBroker
from tests.test_sql_migration_parity import SqlMigrationParityTest

fixture = SqlMigrationParityTest()
fixture.setUp()
search_seeded = False
metadata = {'tmdb_id': '801', 'imdb_id': 'tt0000801', 'title': 'Automatic Refresh',
            'year': '2026', 'release_date': '2026-01-01', 'plot': 'Automatic completion fixture.'}
store = app._curation_store()
store.follow_movie({**metadata, 'status': 'available'})
scan_gate = threading.Event()
scan_gate.set()  # Other desktop tests must not leave an armed scan behind.
scan_started = threading.Event()
ownership_requests = 0
downloaded_path = None
original_ownership = app._reconcile_followed_release_ownership

def slow_scan():
    old_movies = store.followed_all()
    scan_started.set()
    if not scan_gate.wait(180):
        raise RuntimeError('Fixture scan gate timed out')
    return {'movies': old_movies, 'newly_available': [], 'removed_owned': []}

def ownership():
    global ownership_requests
    ownership_requests += 1
    return original_ownership()

app._check_followed_releases = slow_scan
app._reconcile_followed_release_ownership = ownership
app._catalog_event_broker = CatalogEventBroker()

@app.app.route('/api/test/completion/arm', methods=['POST'])
def arm():
    global downloaded_path
    if not app._followed_release_scan_lock.acquire(timeout=5):
        return app.jsonify({'error': 'Previous fixture scan still running'}), 409
    try:
        scan_gate.clear()
        scan_started.clear()
        if downloaded_path:
            fixture.store.catalog.remove_path_records([app._norm(downloaded_path)])
        downloaded_path = None
        store.save_followed_all([])
        store.follow_movie(metadata)
        app._library_cache = {}
        old_broker = app._catalog_event_broker
        app._catalog_event_broker = CatalogEventBroker()
        old_broker.shutdown()
        return app.jsonify({'armed': True})
    finally:
        app._followed_release_scan_lock.release()

@app.app.route('/api/test/completion/import', methods=['POST'])
def complete():
    global downloaded_path
    downloaded = fixture._movie_path('Automatic.Refresh.2026.1080p.mkv')
    downloaded_path = str(downloaded)
    stable_time = time.time() - app._FILE_STABILITY_SECONDS - 1
    os.utime(downloaded, (stable_time, stable_time))
    job = {'hash': 'completion-fixture', 'state': 'imported', 'library_scan_pending': True,
           'imported_paths': [str(downloaded)], **metadata}
    manager = Mock()
    # Seed the final card through the real handler/coordinator, then simulate
    # restart recovery's already-publishable branch with a fresh broker.
    with patch('app.probe_media_file', return_value=fixture._successful_probe(downloaded)), \
            patch('app._fetch_tmdb_metadata_by_id', return_value=metadata), \
            patch('app._catalog_event_broker', CatalogEventBroker()):
        fixture._complete_imports(manager, [job])
    app._handle_completed_qbittorrent_imports(manager, [job])
    return app.jsonify({'pending': manager.jobs.upsert.call_args.args[1]['library_scan_pending'],
                        'events': app._catalog_event_broker.status()['retained'],
                        'ownership_requests': ownership_requests})

@app.app.route('/api/test/completion/reconnect', methods=['POST'])
def reconnect():
    # Refollow in disposable data to prove a missed ready event is recovered
    # through actual EventSource reconnect and the broker's catalog-sync.
    store.follow_movie(metadata)
    # A genuine missed media revision makes Last-Event-ID older than the
    # committed catalog. Reconnecting with no media change needs no sync.
    fixture.store.update_file_record(downloaded_path, {'added_time': time.time()})
    old_broker = app._catalog_event_broker
    app._catalog_event_broker = CatalogEventBroker()
    old_broker.shutdown()
    return app.jsonify({'ok': True})

@app.app.route('/api/test/completion/release-scan', methods=['POST'])
def release_scan():
    scan_gate.set()
    return app.jsonify({'ok': True})

@app.app.route('/api/test/completion/status')
def status():
    return app.jsonify({'ownership_requests': ownership_requests, 'scan_started': scan_started.is_set(),
                        'followed_count': len(store.followed_all())})


@app.app.route('/api/test/search/seed', methods=['POST'])
def seed_search():
    global search_seeded
    if not search_seeded:
        for index in range(85):
            fixture._accepted_movie(f'Search.Fixture.{index:03d}.2002.mkv', {
                'tmdb_id': str(710000 + index), 'title': f'Search Fixture {index:03d}',
                'year': '2002', 'plot': 'Synthetic library search fixture.', 'genres': ['Drama'],
                'cast': [], 'directors': [], 'writers': [], 'certification': '', 'keywords': [],
            })
        search_seeded = True
    return app.jsonify({'count': 85})

app.app.run(host='127.0.0.1', port=port, threaded=True, use_reloader=False)
