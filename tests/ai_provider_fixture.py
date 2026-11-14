"""Synthetic external boundaries for the compiled AI desktop tests.

The real Flask routes, provider selection, SSE decoder, jobs, catalogue traversal,
identity ranker, reviews and persistence stay in use. No runtime manager starts.
"""
import json
import re
import threading
import time
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from flask import jsonify, request


def movie(identity):
    identity = int(identity)
    return {'id': identity, 'title': 'Fixture Movie ' + str(identity),
            'original_title': 'Fixture Movie ' + str(identity), 'runtime': 95,
            'release_date': '2001-01-01', 'genres': [{'id': 878, 'name': 'Science Fiction'}],
            'genre_ids': [878], 'overview': 'Synthetic catalogue evidence.', 'vote_count': 100,
            'vote_average': 7.5, 'original_language': 'en', 'poster_path': '', 'backdrop_path': '',
            'production_companies': [{'id': 77, 'name': 'Fixture Studio', 'origin_country': 'US'}],
            'keywords': {'keywords': []}, 'credits': {'cast': [], 'crew': []}}


def query():
    return {'version': 1, 'scope': 'discover', 'mode': 'advanced', 'feed': 'catalog',
            'sort': {'key': 'auto', 'direction': 'desc'}, 'groups': []}


class FixtureAuth:
    def __init__(self, owner):
        self.owner = owner
        self.rows = []
        self.credentials = SimpleNamespace(profiles=lambda: [dict(row) for row in self.rows])

    def start(self, account_id=None):
        identity = account_id or 'fixture-account-' + str(len(self.rows) + 1)
        existing = next((row for row in self.rows if row['account_id'] == identity), None)
        if existing:
            existing.update(connected=True, plan_enabled=True)
        else:
            self.rows.append({'account_id': identity, 'label': 'Synthetic account ' + str(len(self.rows) + 1),
                              'connected': True, 'plan_enabled': True})
        return {'attempt_id': identity, 'expires_at': time.time() + 600}

    def status(self, identity):
        return {'state': 'complete', 'account_id': identity, 'plan_enabled': True}

    def cancel(self, identity):
        pass

    def access_token(self, identity):
        if not any(row['account_id'] == identity and row['connected'] for row in self.rows):
            from services.chatgpt_transport import ChatGPTError
            raise ChatGPTError('account_disconnected')
        return 'synthetic-token-never-a-real-credential'

    def sign_out(self, identity):
        next(row for row in self.rows if row['account_id'] == identity)['connected'] = False
        self.owner._on_chatgpt_disconnect(identity)
        return {'account_id': identity, 'remote_revocation_confirmed': True}


class FixtureHTTP:
    lock = threading.Lock()
    calls = []
    failure = None
    delay = 0
    series_id = None
    provider_id = None
    phase_gates = {}

    @classmethod
    def wait_phase(cls, phase, cancel=None):
        gate = cls.phase_gates.get(phase)
        if gate is None:
            return
        deadline = time.monotonic() + 20
        while not gate.wait(.05):
            if cancel is not None and cancel.is_set():
                from services.chatgpt_transport import ChatGPTError
                raise ChatGPTError('cancelled')
            if time.monotonic() > deadline:
                raise AssertionError('Desktop fixture phase was not released: ' + phase)

    def json(self, method, url, **kwargs):
        if not url.endswith('/models'):
            raise AssertionError('Unexpected fixture JSON endpoint')
        return {'models': [{'slug': name, 'display_name': name, 'visibility': 'list'}
                           for name in ('fixture-model-a', 'fixture-model-b')]}

    @staticmethod
    def call(name, args):
        namespace, short = name.split('.')
        return {'type': 'function_call', 'name': short, 'namespace': namespace, 'status': 'completed',
                'call_id': 'call-' + uuid.uuid4().hex, 'arguments': json.dumps(args)}

    def stream(self, url, *, payload, token, cancel):
        from services.chatgpt_transport import ChatGPTError
        with self.lock:
            self.calls.append({'model': payload['model'], 'input': payload['input']})
            failure = self.failure
        if cancel.wait(self.delay):
            raise ChatGPTError('cancelled')
        if failure:
            raise ChatGPTError(failure, status=429 if failure == 'rate_limit_exceeded' else 403)
        self.wait_phase('connecting', cancel)
        yield b'data: {"type":"response.created"}\n\n'
        self.wait_phase('retrieving', cancel)
        inputs = payload['input']
        namespaces = {row['name'] for row in payload.get('tools', [])}
        try:
            evidence = json.loads(next(row['content'] for row in inputs if row.get('role') == 'user'))
        except (ValueError, StopIteration):
            evidence = {}
        text, output = '', []
        bulk = 'rows' in evidence and not namespaces
        if bulk:
            if any('candidates' in row for row in evidence['rows']):
                raise AssertionError('A new bulk fixture job reached candidate recovery.')
            text = json.dumps({'rows': [{'id': row['id'], 'title': row['title'],
                'category': 'Film' if any(title in row['title'] for title in
                                          ('Fixture Movie', 'Crystal River', 'Missing Story')) else 'Music',
                'year': '2024', 'confidence': .99, 'uncertain': 'Missing Story' in row['title'],
                'aliases': []} for row in evidence['rows']]})
        elif not namespaces and 'batch_target' not in evidence:
            text = 'CP_CONNECTION_OK'
        elif 'batch_target' in evidence:
            if 'all films' in evidence.get('request', '').lower():
                output = [self.call('cp_control.open', {})]
            else:
                start = int(evidence['accepted_count']) + 1
                stop = start + int(evidence['batch_target'])
                if evidence.get('request') == 'Synthetic large batch':
                    # Force a real 24-attempt pause independently of the normal
                    # per-response capacity; Continue must retain 480/500.
                    stop = min(stop, start + 20)
                if 'shortfall' in evidence.get('request', '').lower():
                    stop = min(stop, 12)
                result = {'recommendations': [
                              {'title': 'Fixture Movie ' + str(i), 'year': '2001'}
                              for i in range(start, max(start, stop))]}
                if not evidence.get('scope_is_fixed'):
                    result['scope'] = {'query': query(), 'subjective_requirements': [], 'requested_count': None}
                text = json.dumps(result)
        elif namespaces == {'cp_result'}:
            if 'files' in evidence:
                result = {'matches': [{'id': row['id'], 'title': 'Fixture Movie 1', 'year': '2001', 'alternatives': []}
                                      for row in evidence['files']]}
            elif 'candidates' in evidence:
                result = {'tmdb_id': evidence['candidates'][0]['tmdb_id'] if evidence['candidates'] else 0}
            elif evidence.get('mode') == 'suggest-search-aliases':
                result = {'aliases': ['Fixture Movie Alternate'] if FixtureHTTP.iptv_title_hints else []}
            else:
                result = {'category': 'Film', 'confidence': .95, 'mixed': False, 'uncertain': False,
                          'title_exceptions': [], 'evidence_summary': 'Synthetic classification evidence.'}
            output = [self.call('cp_result.submit', result)]
        else:
            last_user = max((i for i, row in enumerate(inputs) if row.get('role') == 'user'), default=0)
            prompt = str(inputs[last_user].get('content', '')).lower()
            results = [json.loads(row['output']) for row in inputs[last_user + 1:] if row.get('type') == 'function_call_output']
            if 'classification then matching' in prompt:
                from services.chatgpt_tools import IPTV_FILTERS
                from services.iptv_movie_store import source_key
                filters = {key: None for key in IPTV_FILTERS['properties']}
                filters['view'] = 'provider'
                selected = {'mode': 'explicit', 'keys': ['source:' + source_key('12')], 'filters': filters}
                if len(results) < 2:
                    output = [self.call('cp_iptv.prepare_iptv_classification' if not results else 'cp_iptv.prepare_iptv_match',
                        {'provider_id': self.provider_id, 'selection': selected,
                         'depends_on': [] if not results else [results[0]['action_id']]})]
                else:
                    text = 'Confirm classification, then prepare the next saved matching run. Matches need a separate Apply.'
            elif 'tv list' in prompt:
                if not results:
                    output = [self.call('cp_tv.prepare_tv_list', {'action': 'create', 'list_id': None,
                        'name': 'Synthetic TV list', 'series': [{'domain': 'tv', 'series_id': self.series_id, 'episode_id': None}], 'depends_on': []})]
                else:
                    text = 'Review the native TV series card before saving this TV list.'
            elif 'suggest' in prompt:
                if not results:
                    output = [self.call('cp_movie.suggest_movies', {'prompt': 'Synthetic suggestions', 'count': '3'})]
                elif len(results) == 1 and 'list' in prompt:
                    output = [self.call('cp_movie.prepare_movie_list', {'action': 'create', 'name': 'Nested suggestions',
                        'list_id': None, 'result_set': results[-1]['result_set'], 'depends_on': []})]
                else:
                    text = 'The verified suggestions are ready for review.'
            elif 'playback' in prompt:
                if not results:
                    output = [self.call('cp_runtime.playback_status', {})]
                else:
                    text = 'Playback is stopped in this synthetic fixture.'
            elif 'open iptv' in prompt:
                if not results:
                    output = [self.call('cp_runtime.open_review', {'surface': 'iptv', 'target_ref': None})]
                else:
                    text = 'Open the existing IPTV review.'
            elif not results:
                output = [self.call('cp_movie.resolve_companies', {'text': 'Fixture Studio', 'page': 1})]
            elif len(results) == 1:
                controlled = query()
                controlled['groups'] = [{'type': 'company', 'join': 'or', 'values': [
                    {'id': '77', 'label': 'Fixture Studio', 'country': 'US', 'exclude': False}]}]
                output = [self.call('cp_movie.search_movies', {'query': controlled, 'count': None,
                    'scope': {'include_shorts': False, 'include_upcoming': False, 'include_documentaries': True}})]
            elif len(results) == 2 and 'list' in prompt:
                output = [self.call('cp_movie.prepare_movie_list', {'action': 'create', 'name': 'Desktop fixture studio',
                    'list_id': None, 'result_set': results[-1]['result_set'], 'depends_on': []})]
            else:
                text = 'All 120 released feature films were verified. Review the selection before saving.'
        if text:
            if not bulk:
                output.append({'type': 'message', 'role': 'assistant', 'content': [{'type': 'output_text', 'text': text}]})
            for offset in range(0, len(text), 61):
                delta = {'type': 'response.output_text.delta', 'delta': text[offset:offset+61]}
                yield ('data: ' + json.dumps(delta) + '\n\n').encode()
        event = {'type': 'response.completed', 'response': {'id': 'resp_synthetic_' + str(len(self.calls)),
                  'status': 'completed', 'output': output}}
        yield ('data: ' + json.dumps(event) + '\n\n').encode()


def install(owner, guard):
    from services.iptv_movie_store import source_key
    from services.iptv_metadata_settings import IPTVMetadataSettings
    from tests.iptv_movie_fixtures import provider_catalog, FakeTMDBClient, tmdb_payload
    from services.iptv_provider_manager import IPTVProviderManager
    owner._tmdb_key = 'synthetic-no-network'
    owner._ai_provider_config.clear()
    owner._cfg.update(ai_provider='ollama', chatgpt={}, ai_config_generation=0)
    owner._plex_token = ''
    owner._tmdb_genres = {878: 'Science Fiction', 27: 'Horror'}
    owner._ai_scope_context = lambda: {'genre': [{'id': '878', 'label': 'Science Fiction'}, {'id': '27', 'label': 'Horror'}]}
    owner._load_tmdb_filter_options = lambda: {'languages': [], 'countries': []}
    auth = FixtureAuth(owner)
    owner._chatgpt_auth_owner = auth
    owner._chatgpt_auth_root = Path(owner._user_data_dir).resolve() / 'ai/chatgpt'
    guard.enter_context(patch('services.chatgpt_transport.PublicOpenAIHTTP', FixtureHTTP))
    owner._ai_movie_details = lambda identity: movie(identity)
    def search_movie(title, year=''):
        FixtureHTTP.wait_phase('matching')
        return [movie(int(re.search(r'(\d+)$', title).group(1)))]
    owner._smart_match_tmdb_search = search_movie
    owner._smart_match_tmdb_alternative_titles = lambda identity: []
    def provider_get(endpoint, params):
        if endpoint == '/search/company':
            return {'results': [{'id': 77, 'name': 'Fixture Studio', 'origin_country': 'US'}], 'total_pages': 1, 'total_results': 1}
        if endpoint.startswith('/movie/'):
            return movie(endpoint.rsplit('/', 1)[-1])
        page = int(params.get('page', 1))
        return {'page': page, 'total_pages': 6, 'total_results': 120,
                'results': [movie(i) for i in range((page - 1) * 20 + 1, page * 20 + 1)]}
    owner._ai_tmdb_provider_get = provider_get
    owner._ai_tool_availability = lambda definition, context: None
    manager = IPTVProviderManager(owner._user_data_dir, migrate_legacy=False)
    provider = manager.create_provider('Synthetic provider', 'https://fixture.invalid', 'synthetic-user', 'synthetic-password', False)
    FixtureHTTP.provider_id = provider['provider_id']
    raw = manager.service(provider['provider_id'])
    raw.store.replace_catalog(provider_catalog(movie_rows=[
        {'stream_id': '10', 'name': 'Opaque object', 'category_id': 'movies-a'},
        {'stream_id': '11', 'name': 'Fixture Movie (2024)', 'category_id': 'movies-b'},
        {'stream_id': '12', 'name': 'Fixture Movie (2024)', 'category_id': 'movies-b'},
        {'stream_id': '13', 'name': 'مسرحية الاختبار (1980)', 'category_id': 'movies-a'}]))
    movies = manager.movie_service(provider['provider_id'])
    FixtureHTTP.iptv_title_hints = False
    class IPTVTmdbFixture(FakeTMDBClient):
        def search_movies(self, title, year=0, page=1):
            if FixtureHTTP.iptv_title_hints and title != 'fixture movie alternate':
                return []
            return super().search_movies(title, year, page)

    movies.tmdb_client_factory = lambda: IPTVTmdbFixture(movies={550: tmdb_payload(),
        781869: tmdb_payload(781869, 'مسرحية الاختبار الموثقة', 1980)})
    movies.start_projection(wait=True)
    movies.store.apply_classification_decisions([{'source_key': source_key('11'), 'category': 'film', 'confidence': 1}])
    movies.store.apply_classification_decisions([{'source_key': source_key('13'), 'category': 'plays', 'confidence': 1}], manual=True)
    IPTVMetadataSettings(owner._user_data_dir).save('synthetic-no-network', credential_type='api_key')
    owner._get_iptv_provider_manager = lambda: manager
    # Registered routes retain this factory's original function reference.
    owner._iptv_provider_manager = manager
    owner._iptv_provider_manager_root = Path(owner._user_data_dir).resolve()
    owner._player_manager.os_opener = lambda path: (_ for _ in ()).throw(AssertionError('No fixture playback'))
    owner._tv_enabled = True
    tv_case = json.loads((Path(__file__).parent / 'fixtures/native_tv_cases.json').read_text())
    FixtureHTTP.series_id = owner._tv_services()['repository'].refresh(tv_case['series'], tv_case['episodes'], [])
    owner._tv_services()['metadata'].preview = lambda *args, **kwargs: {
        'runtime': 45, 'original_language': 'en', 'original_language_name': 'English', 'origin_country': ['GB'],
        'cast': [], 'trailer_url': ''}
    library = Path(owner._user_data_dir).parent / 'synthetic-library'
    library.mkdir(exist_ok=True)
    file = library / 'Fixture.Movie.1.2001.mkv'
    file.write_bytes(b'SYNTHETIC NON-PLAYABLE FIXTURE')
    owner._movies_dirs, owner._movies_dir = [str(library)], str(library)
    owner.AppMetadataStore(Path(owner._user_data_dir)).update_file_record(str(file), {
        'filename': file.name, 'library_root': str(library), 'size': file.stat().st_size,
        'identity_status': 'unmatched', 'metadata_status': 'unmatched', 'identity_revision': 1,
        'parsed_title': 'Fixture Movie 1', 'parsed_year': '2001', 'exists': True})
    owner._smart_match_candidates_for_queries = lambda *args, **kwargs: [
        {'tmdb_id': '1', 'title': 'Fixture Movie 1', 'year': '2001'}]

    @owner.app.post('/api/test/ai-fixture')
    def fixture_control():
        data = request.get_json()
        FixtureHTTP.iptv_title_hints = bool(data.get('iptv_unmatched'))
        if data.get('iptv_unmatched'):
            movies.store.set_match_state([source_key('11')], 'unmatched')
            with movies.store.connection(immediate=True) as connection:
                movies.store._set_meta(connection, 'parser_version', '3')
        FixtureHTTP.failure = data.get('failure')
        FixtureHTTP.delay = min(2, max(0, float(data.get('delay', 0))))
        return jsonify(provider_id=provider['provider_id'], source_keys=['source:' + source_key('10'), 'source:' + source_key('11')],
                       calls=len(FixtureHTTP.calls), user_data_root=str(owner._user_data_dir),
                       synthetic_movie_path=str(file), series_id=FixtureHTTP.series_id,
                       movie_record=owner._catalog_repository().get_record('app_metadata/files.json', owner._norm(str(file)), {}))

    @owner.app.post('/api/test/ai-phases')
    def fixture_phases():
        data = request.get_json()
        if 'hold' in data:
            for gate in FixtureHTTP.phase_gates.values():
                gate.set()
            FixtureHTTP.phase_gates = {phase: threading.Event() for phase in data['hold']}
        if data.get('release') == 'all':
            for gate in FixtureHTTP.phase_gates.values():
                gate.set()
        elif data.get('release') in FixtureHTTP.phase_gates:
            FixtureHTTP.phase_gates[data['release']].set()
        return jsonify(ok=True)

    @owner.app.post('/api/test/iptv-bulk-fixture')
    def bulk_fixture():
        data = request.get_json()
        count = int(data['count'])
        if count not in (3, 6413) or (count == 3 and data.get('saved')):
            raise ValueError('Unsupported desktop fixture size')
        suffix = 'saved' if data.get('saved') else 'launch'
        record = manager.create_provider(f'Bulk fixture {suffix}', 'https://bulk-fixture.invalid',
                                         f'{suffix}-{uuid.uuid4().hex}', 'synthetic', False)
        identity = record['provider_id']
        bulk_raw = manager.service(identity)
        bulk_titles = ['Fixture Movie (2024)', 'Crystal River (2024)', 'Missing Story (2024)']
        bulk_raw.store.replace_catalog(provider_catalog(movie_rows=[
            {'stream_id': str(i), 'name': bulk_titles[i] if count == 3 else
                'Fixture Movie (2024)' if i == 0 else f'Bulk specimen {i}',
             'category_id': 'movies-a'} for i in range(count)]))
        bulk_movies = manager.movie_service(identity)
        bulk_movies.tmdb_client_factory = FakeTMDBClient
        bulk_movies.start_projection(wait=True)
        if count == 3:
            from tests.iptv_movie_fixtures import tmdb_payload
            films = {550: tmdb_payload(), 551: tmdb_payload(551, 'Crystal River')}
            class BulkFixtureTMDB(FakeTMDBClient):
                def search_movies(self, title, year=0, page=1):
                    return [row for row in films.values() if row['title'].casefold() == title]
            bulk_movies.tmdb_client_factory = lambda: BulkFixtureTMDB(movies=films)
            for key in ('1', '2'):
                bulk_movies.store.update_provider_detail(source_key(key), {
                    'duration': '01:41:00', 'cast_names': 'Actor One', 'director': 'Director One'})
            if data.get('fail_write'):
                import sqlite3
                original_apply = bulk_movies.store.apply_match
                failed = False
                def apply_match(key, *args, **kwargs):
                    nonlocal failed
                    if key == 'source:' + source_key('1') and not failed:
                        failed = True
                        raise sqlite3.OperationalError('Fixture catalogue write failed')
                    return original_apply(key, *args, **kwargs)
                bulk_movies.store.apply_match = apply_match
        bulk_movies.store.set_match_state([source_key(str(i)) for i in range(count)], 'unmatched')
        if data.get('mixed_unmatched') and count == 3:
            uncertain, unknown = source_key('1'), source_key('2')
            bulk_movies.store.apply_classification([uncertain], 'film', method='fixture', confidence=1)
            bulk_movies.store.set_match_state([uncertain], 'ambiguous')
            bulk_movies.store.apply_classification([unknown], 'unclassified', method='fixture', confidence=0)
            bulk_movies.store.set_match_state([unknown], 'unprocessed')
        with bulk_movies.store.connection(immediate=True) as connection:
            connection.execute('UPDATE source_matches SET updated_at=0')
        manager.set_selection(identity)
        result = dict(provider_id=identity, other_provider_id=provider['provider_id'], count=count)
        if data.get('stale_bulk') or data.get('search_recheck'):
            from services.chatgpt_skills import IPTV_BULK_PROTOCOL_HASH
            from services.iptv_tmdb import interpreted_title_evidence
            selected = owner._ai_provider_service.snapshot('F5', domain_id=identity)
            store = owner._get_ai_job_service().store
            keys = [source_key(str(i)) for i in range(count)]
            generation = bulk_movies.store.source_generation()
            job = store.create('F5', selected, {'bulk_call_budget': 10, 'titles_per_request': 2,
                'bulk_auto_apply': True, 'bulk_protocol_hash': IPTV_BULK_PROTOCOL_HASH,
                'selection_snapshot': {'source_keys': keys, 'catalog_generation': generation, 'mode': 'all-filtered',
                    'filters': {'review_scope': 'leftovers', 'review_view': 'unmatched'}}}, 'stale-bulk')
            store.start_run(job['id'], job['revision'])
            store.reserve_inference(job['id'])
            if data.get('search_recheck'):
                source = bulk_movies.store.bulk_sources(keys[:1], generation)[keys[0]]
                hint = {'id': '0', 'category': 'Film', 'title': 'Fixture Movie', 'year': '2024',
                        'aliases': [], 'confidence': 1, 'uncertain': False}
                identity = interpreted_title_evidence(bulk_movies._source_title_evidence(source), hint)['bulk_identity']
                store.add_results(job['id'], [{'domain': 'iptv', 'identity': key, 'card': {
                    'source_key': key, 'proposal_id': key, 'outcome': 'review', 'category': 'film',
                    'provider_title': bulk_titles[i], 'review_reason': 'Candidate search limit reached before competing identities could be ruled out.',
                    'evidence': {'interpretation': hint, 'identity': identity} if i == 0 else {}}}
                    for i, key in enumerate(keys)], bulk_work={
                    'offset': count, 'pending': [], 'answers': {}, 'throttles': 0})
                store.finish(job['id'], 'completed', coverage='complete')
                bulk_raw.store.replace_catalog(provider_catalog(movie_rows=[
                    {'stream_id': str(i), 'name': title, 'category_id': 'movies-a'} for i, title in enumerate(bulk_titles)]))
                bulk_movies.start_projection(wait=True)
                return jsonify(result | {'job_id': job['id']})
            store.add_results(job['id'], [{'domain': 'iptv', 'identity': keys[0], 'card': {
                'source_key': keys[0], 'proposal_id': keys[0], 'outcome': 'review', 'category': 'unclassified',
                'provider_title': bulk_titles[0]}}], bulk_work={
                    'offset': 2, 'window_end': 2, 'pending': [], 'answers': {'1': None}, 'throttles': 0})
            store.finish(job['id'], 'failed', message='The provider catalog changed. Start a new review.')
            bulk_raw.store.replace_catalog(provider_catalog(movie_rows=[
                {'stream_id': str(i), 'name': title, 'category_id': 'movies-a'} for i, title in enumerate(bulk_titles)]))
            bulk_movies.start_projection(wait=True)
            result.update(job_id=job['id'])
        if data.get('saved'):
            from services.ai_provider import AISelection
            from services.chatgpt_skills import IPTV_BULK_PROTOCOL_HASH, load
            account = owner._ai_provider_config['chatgpt']['active_account_id']
            selected = AISelection('chatgpt', 1, account, 'fixture-model-a', 'iptv-matching',
                                   '1', load('F5')['hash'], 'F5', identity)
            store = owner._get_ai_job_service().store
            keys = [source_key(str(i)) for i in range(count)]
            generation = bulk_movies.store.source_generation()
            job = store.create('F5', selected, {'bulk_call_budget': 100,
                'bulk_protocol_hash': IPTV_BULK_PROTOCOL_HASH,
                'selection_snapshot': {'source_keys': keys, 'catalog_generation': generation}}, 'legacy')
            store.start_run(job['id'], job['revision'])
            for _ in range(39):
                store.reserve_inference(job['id'])
            processed, verified = (count if data.get('completed') else 3741), 2301
            rows = []
            for i, key in enumerate(keys[:processed]):
                outcome = 'verified' if i < verified else 'review' if i % 2 else 'unmatched'
                rows.append({'domain': 'iptv', 'identity': key, 'card': {
                    'source_key': key, 'proposal_id': key, 'provider_title': f'Saved source {i}',
                    'previous_category': 'unclassified', 'category': 'film', 'outcome': outcome,
                    'candidate_tmdb_id': 550 if outcome == 'verified' else 0, 'confidence': 100,
                    'evidence': {'candidate': {'title': 'Fixture Movie', 'year': 2024}},
                    'recommendation': 'recommended', 'match_manual_lock': False}})
            store.add_results(job['id'], rows, bulk_work={'offset': processed, 'pending': [], 'answers': {}, 'throttles': 0})
            report = bulk_movies.apply_bulk_proposals(store.bulk_proposals(job['id'], keys[:20]), 'match', generation)
            assert set(report['applied']) == set(keys[:20]), report
            store.mark_bulk_applied(job['id'], report['applied'])
            store.finish(job['id'], 'completed' if data.get('completed') else 'paused',
                         coverage='complete' if data.get('completed') else 'partial',
                         message='' if data.get('completed') else 'Paused by request.')
            result.update(job_id=job['id'], last_verified_source=keys[verified - 1])
        return jsonify(result)

    return SimpleNamespace(auth=auth, manager=manager, provider=provider)


def verify_matrix(owner):
    from services.chatgpt_tools import ToolContext
    from services.iptv_movie_store import source_key
    client = owner.app.test_client()
    account = client.post('/api/ai/auth/start', json={}).json['attempt_id']
    configured = client.put('/api/ai/config', json={'expected_generation': 0, 'provider': 'chatgpt',
        'active_account_id': account, 'chatgpt_model': 'fixture-model-a',
        'allow_movie_identity_hints': True, 'allow_iptv_titles': True})
    assert configured.status_code == 200, configured.json
    service = owner._get_ai_job_service()
    def wait(response):
        assert response.status_code == 202, response.json
        deadline = time.monotonic() + 12
        while True:
            operation = client.get('/api/ai/jobs/' + response.json['id']).json
            if operation['state'] not in ('queued', 'running'):
                return operation
            assert time.monotonic() < deadline, operation
            time.sleep(.02)
    try:
        manifest = service.domain_tools.registry.manifest(ToolContext(owner._ai_provider_service.snapshot('F2'), 'fixture', 'fixture'))
        assert all(row['status'] == 'callable' for row in manifest), manifest
        f1 = wait(client.post('/api/ai/recommendations', json={'prompt': 'Synthetic', 'count': '120', 'request_key': 'matrix-F1'}))
        assert f1['state'] == 'completed' and f1['accepted_count'] == 120, f1
        shortfall = wait(client.post('/api/ai/recommendations', json={'prompt': 'Synthetic shortfall',
            'count': '50', 'request_key': 'matrix-F1-shortfall'}))
        assert shortfall['state'] == 'partial' and shortfall['accepted_count'] == 11, shortfall
        handoff_prompt = 'All films produced by Fixture Studio'
        handoff = wait(client.post('/api/ai/recommendations', json={'prompt': handoff_prompt,
            'count': '50', 'request_key': 'matrix-F1-handoff'}))
        assert handoff['state'] == 'awaiting_clarification' and handoff['accepted_count'] == 0, handoff
        assert handoff['output'] == {'handoff': 'ai-control', 'prompt': handoff_prompt}, handoff
        f2 = wait(client.post('/api/ai/control/turns', json={'prompt': 'Suggest and list three movies', 'request_key': 'matrix-F2'}))
        assert f2['state'] == 'awaiting_confirmation' and f2['accepted_count'] == 3 and f2['run_calls'] == 4, f2
        review = next(view for view in f2['output']['views'] if view['kind'] == 'action-plan')
        receipt = client.post('/api/ai/control/plans/' + review['action']['action_id'] + '/confirm', json={
            'revision': review['action']['revision'], 'selected_keys': ['item-2'], 'confirmation_phrase': '', 'request_key': 'save-nested'})
        assert receipt.status_code == 200 and receipt.json['state'] == 'completed', receipt.json
        saved = next(row for row in client.get('/api/user/lists').json['lists'] if row['name'] == 'Nested suggestions')
        assert [str(row['tmdb_id']) for row in saved['movies']] == ['2'], saved
        followup = wait(client.post('/api/ai/control/turns', json={'prompt': 'Playback status',
            'session_id': f2['session_id'], 'request_key': 'matrix-follow-up'}))
        assert followup['state'] == 'completed', followup
        fixture = client.post('/api/test/ai-fixture', json={}).json
        start = client.post('/api/metadata/smart-match', json={'paths': [fixture['synthetic_movie_path']],
            'provider': 'tmdb', 'method': 'ai', 'background': False, 'request_key': 'matrix-F3'})
        assert start.status_code == 202, start.json
        f3 = service.handlers['F3'](start.json['ai_job_id'])
        assert f3['state'] == 'completed' and f3['run_calls'] == 1, f3
        native = client.get('/api/metadata/smart-match').json
        assert native['proposals'][0]['candidate']['tmdb_id'] == '1', native
        assert client.post('/api/test/ai-fixture', json={}).json['movie_record']['identity_status'] == 'unmatched'
        applied = client.post('/api/metadata/smart-match/' + native['id'] + '/apply',
                              json={'proposal_ids': [native['proposals'][0]['id']]})
        assert applied.json['applied'] == 1, applied.json
        provider = owner._ai_desktop_fixture.provider['provider_id']
        movie_owner = owner._ai_desktop_fixture.manager.movie_service(provider)
        for feature, suffix, stream in [('F4', 'classification-jobs', '10'), ('F5', 'match-jobs', '11')]:
            operation = wait(client.post('/api/iptv/providers/' + provider + '/movies/ai/' + suffix,
                json={'selected_keys': ['source:' + source_key(stream)], 'request_key': 'matrix-' + feature}))
            assert operation['state'] == 'completed' and operation['run_calls'] == 1, operation
            review = operation['output']['prepared_review']
            if feature == 'F4':
                assert movie_owner.store.source(source_key(stream))['category'] == 'unclassified'
            confirmed = client.post('/api/ai/control/plans/' + review['action']['action_id'] + '/confirm', json={
                'revision': review['action']['revision'], 'selected_keys': ['item-1'],
                'confirmation_phrase': '', 'request_key': 'confirm-' + feature})
            assert confirmed.status_code == 200 and confirmed.json['state'] == 'completed', confirmed.json
            if feature == 'F4':
                assert movie_owner.store.source(source_key(stream))['category'] == 'film'
            else:
                with movie_owner.store.connection() as connection:
                    assert connection.execute('SELECT tmdb_id FROM source_matches WHERE source_key=?',
                                              (source_key(stream),)).fetchone()['tmdb_id'] == 550
        return {'features': ['F1', 'F2', 'F3', 'F4', 'F5'], 'callable_tools': len(manifest),
                'nested_parent_requests': f2['run_calls'], 'saved_subset': [2], 'external_network': 'blocked'}
    finally:
        service.close()
