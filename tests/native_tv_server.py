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
provider_examples['910003'] = {
    'detail': {**raw_series, 'id':910003, 'name':'Louie Fixture', 'original_name':'Louie Fixture', 'first_air_date':'2010-06-29',
               'number_of_seasons':1, 'number_of_episodes':3, 'seasons':[{'season_number':1,'air_date':'2010-06-29','episode_count':3}],
               'external_ids':{'imdb_id':'tt9100030'}},
    'season': {'episodes':[{'id':9100030+n,'season_number':1,'episode_number':n,'name':f'Fixture {n}','air_date':'2010-06-29'} for n in (1,2,3)]}}
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
app._prowlarr_url, app._prowlarr_key = 'http://fixture.invalid', 'fixture'
app._fetch_enabled_prowlarr_indexers = lambda: [{'id': 2, 'name': 'YTS'}, {'id': 7, 'name': 'LimeTorrents'}, {'id': 9, 'name': '1337x'}]
app._download_trusted_indexers, app._download_trusted_indexers_configured = ['2'], True
app._tv_download_trusted_indexers, app._tv_download_trusted_indexers_configured = ['7', '9'], True
owner.prowlarr = lambda: SimpleNamespace(base_url='http://fixture.invalid', search_tv=lambda **kw: [
    {'title': f"Harbor.Signals.S{kw.get('season') or 1:02d}E{kw.get('episode') or (1 if kw.get('season') == 2 else 2):02d}.1080p.WEB-DL", 'tmdbId': 900001, 'infoHash': ('d' if kw.get('season') == 2 else 'a')*40, 'magnetUrl': 'magnet:?xt=urn:btih:'+('d' if kw.get('season') == 2 else 'a')*40, 'indexerId': 7, 'seeders': 12, 'size': 1000},
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
owner.trusted_indexers = app._effective_tv_download_trusted_indexer_ids
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

@app.app.post('/__tv_fixture/new-home/begin')
def fixture_new_begin():
    repository.store.backup(root / 'before-new-home.sqlite')
    return {'tmdb_id':910003}

@app.app.get('/__tv_fixture/new-home/state')
def fixture_new_state():
    with repository.store.connection() as db:
        tracked = db.execute('SELECT id FROM series WHERE tmdb_id=910003').fetchone()
    return {'tracked':bool(tracked),'home_exists':(media / 'Louie Fixture (2010)').exists()}

@app.app.post('/__tv_fixture/source-policy')
def fixture_source_policy():
    original = owner.prowlarr
    provider, calls = original(), []
    def search(**kwargs):
        calls.append(kwargs.get('indexer_ids'))
        return provider.search_tv(**kwargs)
    owner.prowlarr = lambda: SimpleNamespace(base_url=provider.base_url, search_tv=search)
    try:
        owner.search(series_id, 1, 2, manual=False)
        automatic = calls[-1]
        owner.search(series_id, 1, 2, manual=True)
        return {'automatic_indexers':automatic,'manual_indexers':calls[-1]}
    finally: owner.prowlarr = original

@app.app.post('/__tv_fixture/new-home/complete')
def fixture_new_complete():
    digest = hashlib.sha1(b'Louie.Fixture.S01E01.1080p.WEB-DL').hexdigest()
    job = manager.jobs.get(digest)
    if not job: raise ValueError('Use the desktop Download action first')
    path = manager.staging_dir / 'Louie.Fixture.S01E01.1080p.WEB-DL.mkv'
    path.write_bytes(b'x'*100000)
    files = [{'name':path.name, 'size':path.stat().st_size}]
    torrent = {'hash':digest,'name':path.name,'progress':1,'save_path':str(manager.staging_dir)}
    original_probe, original_files = owner.probe, manager.client.files.side_effect
    owner.probe = lambda _: {'probe_status':'ok','quality_class':'1080p'}
    manager.client.files.side_effect = lambda _: files
    try:
        with manager._completion_lock:
            validated = manager._process_pending_magnet_validation(digest, job, torrent)
            result = owner.process_completed(manager, digest, validated, torrent)
        episode = repository.episodes(job['tv_request']['series_id'], 1)[0]
        return {'job':result,'source_exists':path.exists(),'binding_paths':[v['path'] for v in episode['versions']]}
    finally:
        owner.probe, manager.client.files.side_effect = original_probe, original_files

@app.app.post('/__tv_fixture/new-home/flat')
def fixture_new_flat():
    identity = metadata.refresh(910003)
    folder = media / 'Flat fixture'; folder.mkdir(exist_ok=True)
    path = folder / 'Louie.Fixture.S01E01.mkv'; path.write_bytes(b'flat fixture')
    repository.approve_path(folder, 'folder', identity)
    repository.bind_file(path, [repository.episodes(identity, 1)[0]['id']], {}, [media])
    return {'series_id':identity,'path':str(path)}

@app.app.post('/__tv_fixture/new-home/reset')
def fixture_new_reset():
    digest = hashlib.sha1(b'Louie.Fixture.S01E01.1080p.WEB-DL').hexdigest()
    job = manager.jobs.get(digest)
    if job:
        for value in job.get('imported_paths', []):
            path = Path(value).resolve()
            if media not in path.parents: raise ValueError('Fixture cleanup escaped temporary media')
            path.unlink(missing_ok=True)
        owner.acquisition.event(job['acquisition_id'], 'cancel', state='cancelled')
        manager.jobs.upsert(digest, {'state':'cancelled'})
    repository.store.restore(root / 'before-new-home.sqlite')
    flat = media / 'Flat fixture' / 'Louie.Fixture.S01E01.mkv'
    flat.unlink(missing_ok=True)
    return {'reset':True}
# Season-pack acceptance uses a separate synthetic show and real storage/transfer owners.
pack_cases = {}
pack_provider, pack_metadata, pack_resolver = owner.prowlarr, metadata.request, owner.resolve_candidate
def season_pack_provider():
    original = pack_provider()
    def report(**kwargs):
        case = pack_cases.get(str(kwargs.get('tmdb_tv_id')))
        if not case: return {'items':original.search_tv(**kwargs)}
        case['queries'].append({'season':kwargs.get('season'),'episode':kwargs.get('episode')})
        prefix = case['title'].replace(' ','.')
        common = {'indexerId':7,'indexer':'Fixture TV','size':300000,'seeders':20}
        items = [
            {**common,'title':f"{case['title']} (2010) Season 2 S02 (1080p BluRay x265 HEVC 10bit AAC 5.1 Garshasp)", 'infoHash':case['hash'],'magnetUrl':'magnet:?xt=urn:btih:'+case['hash']},
            {**common,'title':f'{prefix}.S02.1080p.BluRay.x264-FGT [CK] [S02 Two Complete]','infoHash':case['review_hash'],'magnetUrl':'http://fixture.invalid/7/download'},
            {**common,'title':f'{prefix}.2010.S01.1080p.BluRay.x265','infoHash':case['wrong_hash'],'magnetUrl':'magnet:?xt=urn:btih:'+case['wrong_hash']}]
        if case['mode']=='review': items = items[1:]
        return {'items':items,'partial':True,'sources':[{'id':7,'name':'Fixture TV','state':'complete','count':len(items)}, {'id':9,'name':'Fixture timeout','state':'timeout','count':0}]}
    return SimpleNamespace(base_url='http://fixture.invalid',search_tv_report=report,search_tv=lambda **kwargs:report(**kwargs)['items'])
def season_pack_metadata(path, **kwargs):
    parts = path.split('/')
    case = pack_cases.get(parts[2]) if len(parts)>2 and parts[1]=='tv' else None
    if case:
        episodes = [{'id':case['tmdb_id']*10+n,'season_number':2,'episode_number':n,'name':f'Episode {n}','air_date':'2011-06-23'} for n in (1,2,3)]
        if 'season' in parts: return {'episodes':episodes}
        return {**raw_series,'id':case['tmdb_id'],'name':case['title'],'original_name':case['title'], 'first_air_date':'2010-06-29',
                'seasons':[{'season_number':2,'episode_count':3}],'external_ids':{}}
    if path=='/search/tv':
        case = next((case for case in pack_cases.values() if case['title']==kwargs.get('query')),None)
        if case: return {'results':[{'id':case['tmdb_id'],'name':case['title'],'first_air_date':'2010-06-29'}, {'id':999999,'name':case['title'],'first_air_date':'2006-01-01'}]}
    return pack_metadata(path,**kwargs)
def season_pack_resolver(candidate):
    if candidate.get('download_url')=='http://fixture.invalid/7/download' and candidate.get('info_hash'):
        digest = candidate['info_hash']
        return {'info_hash':digest,'magnet_url':'magnet:?xt=urn:btih:'+digest,'download_url':'','transport_verified':True}
    return pack_resolver(candidate)
owner.prowlarr, metadata.request, owner.resolve_candidate = season_pack_provider, season_pack_metadata, season_pack_resolver

@app.app.post('/__tv_fixture/season-pack/begin')
def fixture_pack_begin():
    mode = app.request.get_json().get('mode','pack')
    number = len(pack_cases)+1
    tmdb_id = 920000+number
    title = f'Louie Pack Fixture {number}'
    digest = hashlib.sha1(f'pack-{number}'.encode()).hexdigest()
    case = {'tmdb_id':tmdb_id,'title':title,'hash':digest,'review_hash':hashlib.sha1(f'review-{number}'.encode()).hexdigest(),
            'wrong_hash':hashlib.sha1(f'wrong-{number}'.encode()).hexdigest(),'mode':mode,'queries':[]}
    identity = repository.refresh({'tmdb_id':tmdb_id,'title':title,'first_air_date':'2010-06-29','status':'Ended','seasons':[{'season_number':2,'episode_count':3}]},
        [{'provider_id':str(tmdb_id*10+n),'season_number':2,'episode_number':n,'title':f'Episode {n}','air_date':'2011-06-23'} for n in (1,2,3)])
    folder = media / f'{title} (2010)'
    (folder / 'Season 02').mkdir(parents=True,exist_ok=True)
    repository.approve_path(folder,'folder',identity)
    repository.set_import_home(identity,folder,[media])
    case['series_id'] = identity
    pack_cases[str(tmdb_id)] = case
    return case

@app.app.post('/__tv_fixture/season-pack/run/<int:identity>')
def fixture_pack_run(identity):
    monitoring = app._tv_monitoring()
    monitoring.run_once(limit=5,submit=True)
    case = next(case for case in pack_cases.values() if case['series_id']==identity)
    return {'tasks':monitoring.list_tasks(identity)['items'],'queries':case['queries']}

@app.app.post('/__tv_fixture/season-pack/complete/<int:identity>')
def fixture_pack_complete(identity):
    case = next(case for case in pack_cases.values() if case['series_id']==identity)
    digest = case['hash'] if manager.jobs.get(case['hash']) else case['review_hash']
    job = manager.jobs.get(digest)
    if not job: raise ValueError('Queue the pack first')
    files, paths = [],[]
    for n in (1,2,3):
        path = manager.staging_dir / f"{case['title'].replace(' ','.')}.2010.S02E{n:02d}.1080p.BluRay.mkv"
        path.write_bytes(b'x'*100000)
        paths.append(path)
        files.append({'index':n-1,'name':path.name,'size':path.stat().st_size})
    torrent = {'hash':digest,'progress':1,'save_path':str(manager.staging_dir)}
    original_probe, original_files = owner.probe, manager.client.files.side_effect
    owner.probe = lambda _: {'probe_status':'ok','quality_class':'1080p','video_codec':'HEVC'}
    manager.client.files.side_effect = lambda _: files
    try:
        with manager._completion_lock:
            validated = manager._process_pending_magnet_validation(digest,job,torrent)
            result = owner.process_completed(manager,digest,validated,torrent)
        monitoring = app._tv_monitoring()
        # The fixture supplies the next worker tick after synthetic completion.
        # Production polling keeps its ordinary schedule.
        with monitoring.store.transaction() as db:
            db.execute('UPDATE tv_tasks SET next_due=0 WHERE series_id=?', (identity,))
        monitoring.run_once(submit=True)
        return {'job':result,'source_exists':any(path.exists() for path in paths),'episodes':repository.episodes(identity,2)}
    finally: owner.probe, manager.client.files.side_effect = original_probe, original_files

# Use the real metadata refresh owner against fixture transport, including scoped preview persistence.
performance_fixture = {}

def prohibit_player_launch(*args, **kwargs):
    raise AssertionError('A real player launch is prohibited in this fixture')

app._player_manager.os_opener = prohibit_player_launch
app._player_manager.process_launcher = prohibit_player_launch

@app.app.post('/__tv_fixture/library-performance/begin')
def performance_begin():
    if performance_fixture:
        raise ValueError('Performance fixture already active')
    repository.store.backup(root/'library-performance-before.sqlite')
    episode = repository.episodes(series_id,1)[0]
    path = season_home/'Harbor.Signals.S01E01.720p.alternate.mkv'
    path.write_bytes(b'SYNTHETIC SECOND VERSION')
    identity = repository.bind_file(path,[episode['id']],{'quality_class':'720p','audio_language':'English'},[media])
    repository.save_progress(episode['id'],restart=True)
    original_play, original_roots = app._player_manager.play, services['playback'].roots
    performance_fixture.update(original_play=original_play,original_roots=original_roots,path=path,keys=[])
    services['playback'].roots = lambda: [media]
    def record_play(path_key, *, restart=False):
        resolved = services['playback'].resolve(path_key)
        services['history'].begin_session(resolved,restart=restart)
        performance_fixture['keys'].append(path_key)
        return {'ok':True,'mode':'built_in','fallback':False}
    app._player_manager.play = record_play
    return {'episode_id':episode['id'],'file_id':identity,'expected_key':f'tv:episode:{episode["id"]}:file:{identity}'}

@app.app.get('/__tv_fixture/library-performance/state')
def performance_state():
    return {'keys':performance_fixture.get('keys',[])}

@app.app.post('/__tv_fixture/library-performance/end')
def performance_end():
    if performance_fixture:
        app._player_manager.play = performance_fixture['original_play']
        services['playback'].roots = performance_fixture['original_roots']
        repository.store.restore(root/'library-performance-before.sqlite')
        path = performance_fixture['path'].resolve()
        if media.resolve() not in path.parents:
            raise ValueError('Fixture cleanup escaped temporary media')
        path.unlink(missing_ok=True)
        performance_fixture.clear()
    return {'restored':True}

print(f'TV fixture series_id={series_id}, root={root}', flush=True)
app.app.run(host='127.0.0.1', port=port, use_reloader=False, debug=False)
