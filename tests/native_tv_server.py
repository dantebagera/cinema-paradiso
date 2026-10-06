"""Disposable TV acceptance server. Never starts a provider or media client."""
import json
import os
from pathlib import Path
import tempfile

if os.environ.get('CP_TEST_MODE') != '1':
    raise RuntimeError('This fixture server requires CP_TEST_MODE=1')
root = Path(os.environ['CP_TEST_ROOT']).resolve()
if Path(tempfile.gettempdir()).resolve() not in root.parents:
    raise RuntimeError('A unique OS-temporary root is required')
port = int(os.environ.get('CP_PORT', '5127'))
if port == 5000:
    raise RuntimeError('Production port is prohibited')

os.environ['CP_TEST_QBT_MODE'] = 'embedded'
import app
from tests.seed_iptv_e2e import catalog

fixture = json.loads((Path(__file__).parent / 'fixtures/native_tv_cases.json').read_text())
app._tv_enabled = True
app._streaming_tv_url_template = fixture['streaming_template']
app._player_manager.os_opener = lambda path: None
services = app._tv_services()
repository = services['repository']
series_id = repository.refresh({**fixture['series'], 'overview': 'A coastal town follows a mysterious radio signal.', 'seasons': [{'season_number': n} for n in (0, 1, 2)]}, fixture['episodes'], [{'tmdb_id': 123, 'name': 'Mira Stone', 'role': 'Creator'}])
media = root / 'tv'
media.mkdir(parents=True, exist_ok=True)
home = media / 'Harbor Signals'
season_home = home / 'Season 01'
season_home.mkdir(parents=True)
repository.approve_path(home, 'folder', series_id)
repository.set_import_home(series_id, home, [media])
for number, quality in ((1, '1080p'), (3, '720p')):
    path = season_home / f'Harbor.Signals.S01E{number:02d}.{quality}.mkv'
    path.write_bytes(b'SYNTHETIC TEST MEDIA - NOT FOR REAL PLAYBACK')
    episode = next(row for row in repository.episodes(series_id, 1) if row['episode_number'] == number)
    repository.bind_file(path, [episode['id']], {'probe_status': 'ok', 'quality_class': quality, 'video_codec': 'HEVC', 'audio_language': 'English'}, [media])
raw_series = {'id': 900001, 'name': 'Harbor Signals', 'original_name': 'Harbor Signals', 'first_air_date': '2020-01-01', 'last_air_date': '2021-01-03',
              'status': 'Ended', 'vote_average': 8.2, 'vote_count': 1200, 'genres': [{'id': 18, 'name': 'Drama'}, {'id': 9648, 'name': 'Mystery'}],
              'original_language': 'en', 'origin_country': ['GB'], 'episode_run_time': [45], 'number_of_episodes': 6, 'number_of_seasons': 2,
              'seasons': [{'season_number': 0, 'air_date': '2019-12-25', 'episode_count': 1},
                          {'season_number': 1, 'air_date': '2020-01-01', 'episode_count': 3},
                          {'season_number': 2, 'air_date': '2021-01-03', 'episode_count': 2}],
              'created_by': [{'id': 123, 'name': 'Mira Stone'}], 'keywords': {'results': [{'id': 55, 'name': 'Radio'}]},
              'videos': {'results': [{'site': 'YouTube', 'key': 'abc12345678', 'type': 'Trailer', 'official': True}]},
              'external_ids': {'imdb_id': 'tt1234567'}}
metadata = services['metadata']
repository.refresh({**metadata.normalize(raw_series), 'overview': 'A coastal town follows a mysterious radio signal.'}, fixture['episodes'], metadata.credits(raw_series))
provider_examples = json.loads((Path(__file__).parent/'fixtures/tv_provider_parity.json').read_text(encoding='utf-8'))
def tmdb_fixture(path, **params):
    pieces=path.split('/')
    if len(pieces)>2 and pieces[1]=='tv' and pieces[2] in provider_examples:
        return provider_examples[pieces[2]]['season' if 'season' in pieces else 'detail']
    if path == '/genre/tv/list': return {'genres': raw_series['genres']}
    if path == '/configuration/languages': return [{'iso_639_1': 'en', 'english_name': 'English'}]
    if path == '/configuration/countries': return [{'iso_3166_1': 'GB', 'english_name': 'United Kingdom'}]
    if path == '/search/person': return {'results': [{'id': 123, 'name': 'Mira Stone'}]}
    if path == '/search/keyword': return {'results': [{'id': 55, 'name': 'Radio'}]}
    if path == '/person/123/tv_credits': return {'cast': [], 'crew': [{**raw_series, 'job': 'Creator'}]}
    if path.startswith('/tv/') and '/season/' in path:
        season = int(path.rsplit('/', 1)[1])
        return {'episodes': [{**ep, 'id': index + 1, 'name': ep['title']} for index, ep in enumerate(fixture['episodes']) if ep['season_number'] == season]}
    if path in {'/tv/900001', '/tv/900002'}:
        if params.get('language') == 'ar-SA':
            return {**raw_series, 'id': int(path.rsplit('/', 1)[1]), 'name': 'إشارات الميناء',
                    'overview': 'بلدة ساحلية تتبع إشارة غامضة.',
                    'genres': [{'id': 18, 'name': 'دراما'}, {'id': 9648, 'name': 'غموض'}]}
        return {**raw_series, 'id': int(path.rsplit('/', 1)[1]), 'name': 'Open Water' if path.endswith('900002') else 'Harbor Signals'}
    if path in {'/discover/tv', '/search/tv', '/trending/tv/week', '/tv/popular', '/tv/on_the_air', '/tv/airing_today', '/tv/top_rated'}:
        results = [raw_series, {**raw_series, 'id': 900002, 'name': 'Open Water', 'original_name': 'Open Water'}]
        if path == '/discover/tv' and params.get('with_status') is not None:
            status_name = {'0': 'Returning Series', '1': 'Planned', '2': 'In Production',
                           '3': 'Ended', '4': 'Canceled', '5': 'Pilot'}[str(params['with_status'])]
            results = [row for row in results if row['status'] == status_name]
        if params.get('query'): results = [r for r in [*results, *[v['detail'] for v in provider_examples.values()]] if str(params['query']).lower() in r['name'].lower()]
        return {'results': results, 'page': params.get('page', 1), 'total_pages': 1, 'total_results': len(results)}
    raise ValueError('Unconfigured fixture endpoint')
metadata.request = tmdb_fixture

from types import SimpleNamespace
from unittest.mock import Mock
owner = app._tv_acquisition()
owner.roots = lambda: [media]
owner.prowlarr = lambda: SimpleNamespace(base_url='http://fixture.invalid', search_tv=lambda **kw: [
    {'title': f"Harbor.Signals.S{kw.get('season') or 1:02d}E{kw.get('episode') or 2:02d}.1080p.WEB-DL", 'tmdbId': 900001, 'infoHash': 'a'*40, 'magnetUrl': 'magnet:?xt=urn:btih:'+'a'*40, 'indexerId': 7, 'seeders': 12, 'size': 1000},
    {'title': 'Harbor.Signals.S01E02.1080p.HDCAM', 'tmdbId': 900001, 'infoHash': 'b'*40, 'magnetUrl': 'magnet:?xt=urn:btih:'+'b'*40, 'indexerId': 7, 'seeders': 10, 'size': 1000}])
original_provider = owner.prowlarr

def parity_provider():
    old=original_provider()
    def search(**kw):
        identity=str(kw.get('tmdb_tv_id'))
        if identity not in provider_examples: return old.search_tv(**kw)
        title=provider_examples[identity]['detail']['name'].replace(' ','.')
        return [{'title':f'{title}.S01E{number:02d}.1080p.WEB-DL','downloadUrl':f'http://fixture.invalid/7/download?episode={number}','indexerId':7,'indexer':'Fixture TV','size':100000,'seeders':10} for number in [1,2,3]]
    return SimpleNamespace(base_url='http://fixture.invalid',search_tv=search)
owner.prowlarr=parity_provider
import hashlib
owner.resolve_candidate=lambda candidate: {'info_hash':hashlib.sha1(candidate['title'].encode()).hexdigest(),'magnet_url':'magnet:?xt=urn:btih:'+hashlib.sha1(candidate['title'].encode()).hexdigest(),'download_url':'','transport_verified':True}
owner.trusted_indexers = lambda: [7]
manager = app._get_qbittorrent_manager()
manager.ensure_running = Mock(return_value=True)
manager.client = Mock()
manager.client.torrents.return_value = []
manager.client.files.return_value = []
manager.proxy = Mock(side_effect=lambda path, **_: (
    (200, {'Content-Type':'image/svg+xml'}, (Path(__file__).parents[1]/'static'/'logo.svg').read_bytes())
    if str(path).endswith('.png') else
    (200, {'Content-Type':'text/html'}, b'<html><body><p>Fixture qBittorrent</p></body></html>')
))
owner.submit_candidate = lambda manager, candidate, metadata: manager.submit_magnet(candidate['magnet_url'], metadata)

# Explicit test-only setup for provider shows whose download tests need approved homes.
@app.app.post('/__tv_fixture/approved-home/<int:tmdb_id>')
def fixture_home(tmdb_id):
    identity = metadata.refresh(tmdb_id, season_scope={1})
    folder = media / f'Approved fixture {tmdb_id}'
    (folder / 'Season 01').mkdir(parents=True, exist_ok=True)
    repository.approve_path(folder, 'folder', identity)
    repository.set_import_home(identity, folder, [media])
    return {'series_id': identity, 'path': str(folder)}

@app.app.post('/__tv_fixture/complete-normal')
def fixture_complete_normal():
    """Run the real submission, manifest validation, publication and cleanup owners."""
    digest = 'c' * 40
    original_provider, original_probe = owner.prowlarr, owner.probe
    name = 'Harbor.Signals.S02E01.1080p.WEB-DL.mkv'
    payload = manager.staging_dir / 'normal-fixture'
    payload.mkdir(parents=True, exist_ok=True)
    source = payload / name
    source.write_bytes(b'SYNTHETIC VERIFIED TV STORAGE FIXTURE')
    files = [{'name': name, 'size': source.stat().st_size}]
    torrent = {'hash': digest, 'name': name, 'progress': 1, 'save_path': str(payload)}
    owner.prowlarr = lambda: SimpleNamespace(base_url='http://fixture.invalid', search_tv=lambda **_: [
        {'title': name, 'tmdbId': 900001, 'infoHash': digest, 'magnetUrl': 'magnet:?xt=urn:btih:'+digest,
         'size': source.stat().st_size, 'seeders': 20, 'indexerId': 7}])
    owner.probe = lambda _: {'probe_status': 'ok', 'quality_class': '1080p'}
    original_files = manager.client.files.side_effect
    manager.client.files.side_effect = lambda _: files
    try:
        with manager._completion_lock:
            review = owner.search(series_id, 2, 1)
            submitted = owner.submit(review['decisions'][0]['decision_token'], 'normal-fixture-completion')
            job = manager._process_pending_magnet_validation(digest, submitted['job'], torrent)
            result = owner.process_completed(manager, digest, job, torrent)
        return {'job': result, 'intent_id': submitted['intent']['id'], 'source_exists': source.exists(),
                'binding_paths': [row['path'] for row in repository.episodes(series_id, 2)[0]['versions']]}
    finally:
        owner.prowlarr, owner.probe = original_provider, original_probe
        manager.client.files.side_effect = original_files

@app.app.post('/__tv_fixture/reset-normal')
def fixture_reset_normal():
    job = manager.jobs.get('c' * 40)
    if job:
        for path in job.get('imported_paths') or []:
            with repository.store.transaction() as db:
                file_row = db.execute('SELECT id FROM media_files WHERE path=?', (path,)).fetchone()
                if file_row:
                    db.execute('DELETE FROM episode_file_bindings WHERE file_id=?', (file_row[0],))
                    db.execute('DELETE FROM media_files WHERE id=?', (file_row[0],))
            Path(path).unlink(missing_ok=True)
    return {'reset': True}

@app.app.post('/__tv_fixture/ambiguous-home')
def fixture_ambiguous_home():
    repository.store.backup(root / 'before-home-choice.sqlite')
    second = media / ('Second approved collection with a long folder name ' + 'x' * 65)
    season = second / 'Season 01'
    season.mkdir(parents=True, exist_ok=True)
    path = season / 'owned.mkv'
    path.write_bytes(b'SYNTHETIC OWNED EPISODE')
    repository.approve_path(second, 'folder', series_id)
    episode = repository.episodes(series_id, 1)[0]
    repository.bind_file(path, [episode['id']], {}, [media])
    with repository.store.transaction() as db:
        db.execute('DELETE FROM tv_import_homes WHERE series_id=?', (series_id,))
    return {'home': str(second), 'destination': str(second / 'Season 02')}

@app.app.post('/__tv_fixture/reset-home')
def fixture_reset_home():
    repository.store.restore(root / 'before-home-choice.sqlite')
    return {'reset': True}
# Use the real metadata refresh owner against fixture transport, including scoped preview persistence.
print(f'TV fixture series_id={series_id}, root={root}', flush=True)
app.app.run(host='127.0.0.1', port=port, use_reloader=False, debug=False)
