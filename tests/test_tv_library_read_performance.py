"""Bounded synthetic characterization and structural gates for Library reads."""
from contextlib import contextmanager
from datetime import date
import json
import importlib.util
import ast
import gc
import os
from pathlib import Path
import tempfile
import unittest
import sys
import threading
import weakref
from types import SimpleNamespace
from unittest.mock import patch

from services.tv_catalog_repository import TVCatalogRepository
from services.tv_read_model import TVReadModel
from services.tv_search import TVSearch


QUERY = {'version': 1, 'scope': 'library', 'mode': 'simple', 'groups': [],
         'sort': {'key': 'title', 'direction': 'asc'}}
FIXTURE_MTIME_NS = 1_600_000_000_000_000_000


def seed(repository, root, count=6, *, adversarial=False):
    """36 regulars + two Specials, 2 KiB overviews, eight reused guest people."""
    guests = [{'id': 700+n, 'name': f'Guest {n}', 'character': f'Role {n}'} for n in range(8)]
    episodes = [{'season_number': season, 'episode_number': number,
                 'title': f'Episode {season}-{number}', 'air_date': '2020-01-01',
                 'overview': 'x'*2048, 'guest_stars': guests}
                for season, total in ((0, 2), (1, 18), (2, 18)) for number in range(1, total+1)]
    ids = []
    for n in range(count):
        metadata = {'tmdb_id': 8000+n, 'title': f'Café Series {n:02}', 'status': 'Ended',
                    'first_air_date': '2020-01-01', 'original_language': 'en',
                    'original_language_name': 'English', 'origin_country': ['GB'],
                    'genres': ['Drama'], 'genre_records': [{'id': 18, 'name': 'Drama'}],
                    'rating': 8, 'seasons': [{'season_number': s, 'episode_count': t}
                                            for s, t in ((0, 2), (1, 18), (2, 18))]}
        identity = repository.refresh(metadata, list(reversed(episodes)) if adversarial and n == count-1 else episodes,
                                      [{'tmdb_id': 900, 'name': 'Creator', 'role': 'Creator'}])
        ids.append(identity)
        rows = repository.episodes(identity, 1)
        # Four tiny files per series, under 200 total at either fixture size.
        for i, row in enumerate(rows[:4]):
            path = root / f'{n:02}-S01E{i+1:02}.1080p.WEB-DL.mkv'
            path.write_bytes(b'synthetic')
            os.utime(path,ns=(FIXTURE_MTIME_NS,FIXTURE_MTIME_NS))
            repository.bind_file(path, [row['id']], {'quality_class': '1080p', 'audio_language': 'en'}, [root])
    return ids


@contextmanager
def counters(repository):
    original = repository.store.connection
    counts = {'selects': 0, 'connections': 0, 'paths': {}}
    @contextmanager
    def connection():
        counts['connections'] += 1
        with original() as db:
            def trace(sql):
                if sql.lstrip().upper().startswith('SELECT'):
                    counts['selects'] += 1
            db.set_trace_callback(trace)
            yield db
    is_file = Path.is_file
    def exists(path):
        key = str(path)
        counts['paths'][key] = counts['paths'].get(key, 0)+1
        return is_file(path)
    with patch.object(repository.store, 'connection', connection), patch.object(Path, 'is_file', exists):
        yield counts


STATE_KEYS = {'id','series_id','season_number','episode_number','title','air_date','reconciliation_required',
              'position_ms','duration_ms','completed','last_played','selected_file_id','versions','available','released','code'}


class TVLibraryProbeContractTests(unittest.TestCase):
    def load_probe(self):
        path = Path('docs/verification/tv-library-performance/probe.py')
        spec = importlib.util.spec_from_file_location('tv_library_probe_contract', path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    def test_probe_setup_is_explicitly_separated(self):
        path = Path(os.environ.get('CP_TV_PROBE_INSPECT', 'docs/verification/tv-library-performance/probe.py'))
        names = {n.name for n in ast.parse(path.read_text(encoding='utf-8-sig')).body if isinstance(n, ast.FunctionDef)}
        self.assertTrue({'prepare_probe','measure_single_request'}.issubset(names), names)

    def fake_measure(self, module, setup, events, *, missing=False):
        class Context: pass
        refs = setup.flask_context_refs
        class Response:
            status_code, headers = 200, {}
            def get_data(self): events.append('consume'); return b'ok'
            def close(self): events.append('response-close')
            def __del__(self): events.append('response-release')
        class Client:
            def __del__(self): events.append('client-release')
        def dispatch(client):
            events.append('dispatch')
            context = Context(); refs.append(weakref.ref(context))
            return Response()
        setup.client, setup.dispatch = Client(), dispatch
        setup.expected_repository_contexts = int(missing)
        active = [False]
        tracer = SimpleNamespace(is_tracing=lambda: active[0],
            start=lambda _: (events.append('trace-start'), active.__setitem__(0, True)),
            reset_peak=lambda: events.append('reset'), get_traced_memory=lambda: (100,200),
            stop=lambda: (events.append('trace-stop'), active.__setitem__(0,False)))
        original_gc = module.gc.collect
        def collect(): events.append('collect'); return original_gc()
        with patch.object(module,'tracemalloc',tracer), patch.object(module.gc,'collect',collect):
            return module.measure_single_request(setup)

    def test_setup_precedes_tracing_without_warmup(self):
        module = self.load_probe()
        from flask import Flask
        events = []
        class Client: pass
        def factory(*a, **kw):
            self.assertFalse(module.tracemalloc.is_tracing()); events.append('client-setup'); return Client()
        with patch.object(Flask,'test_client',side_effect=factory), patch(__name__+'.seed'):
            setup = module.prepare_probe('candidate',6,'cards',baseline_source=Path('.'),run_dir=Path(os.environ['CP_TEST_ROOT']))
        try:
            self.assertEqual(setup.setup_manifest['preparation_dispatches'],0)
            self.assertFalse(setup.setup_manifest['tracing_at_setup'])
            result = self.fake_measure(module,setup,events)
            self.assertLess(events.index('client-setup'),events.index('trace-start'))
            self.assertLess(events.index('reset'),events.index('dispatch'))
            self.assertLess(events.index('consume'),events.index('response-close'))
            self.assertLess(events.index('response-release'),len(events)-1)
            self.assertLess(events.index('client-release'),len(events)-1)
            self.assertEqual(events.count('dispatch'),1)
            self.assertEqual(events[-2:],['collect','trace-stop'])
            self.assertTrue(result['flask_contexts_collected'])
        finally: setup.stack.close()

    def test_probe_rejects_missing_context_evidence(self):
        module = self.load_probe()
        setup = module.ProbeSetup(None,None,[],[],1,{})
        with self.assertRaisesRegex(AssertionError,'Missing or unexpected repository context'):
            self.fake_measure(module,setup,[],missing=True)

    def test_url_codecs_are_preloaded_without_endpoint_dispatch(self):
        module = self.load_probe()
        from flask import Flask
        with patch.object(Flask,'test_client',return_value=SimpleNamespace()), patch(__name__+'.seed'):
            setup = module.prepare_probe('candidate',6,'cards',baseline_source=Path('.'),run_dir=Path(os.environ['CP_TEST_ROOT']))
        try:
            self.assertEqual(setup.setup_manifest.get('preloaded_codecs'),['encodings.idna','stringprep'])
            self.assertEqual(setup.setup_manifest['preparation_dispatches'],0)
            self.assertFalse(setup.setup_manifest['tracing_at_setup'])
        finally: setup.stack.close()

    def test_invalid_observation_preserves_evidence(self):
        module = self.load_probe()
        self.assertTrue(hasattr(module,'record_memory_observation'))
        destination = Path(os.environ['CP_TEST_ROOT'])/'invalid-record.json'
        record = {'peak_increment':123,'residual_increment':45,'late_imports':['fixture.codec']}
        with patch.object(module,'measure_single_request',side_effect=module.ProbeGateError('invalid setup',record)):
            with self.assertRaisesRegex(module.ProbeGateError,'invalid setup'):
                module.record_memory_observation(None,destination)
        self.assertEqual(json.loads(destination.read_text()),{**record,'valid':False,'error':'invalid setup'})


class TVLibraryReadPerformanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT'])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = TVCatalogRepository(self.root/'tv.sqlite', clock=lambda: 1_600_000_000)
        self.ids = seed(self.repo, self.root)
        self.read = TVReadModel(self.repo)
        self.search = TVSearch(self.read, None)

    def test_synthetic_file_timestamps_are_fixed_and_truthful(self):
        for row in self.repo.episodes(self.ids[0],1)[:4]:
            version = row['versions'][0]
            self.assertEqual(Path(version['path']).stat().st_mtime_ns,FIXTURE_MTIME_NS)
            self.assertEqual(version['modified_ns'],FIXTURE_MTIME_NS)

    def test_discover_reuses_one_snapshot_for_exact_owned_card_details(self):
        raw = [{'id':8000+n,'tmdb_id':8000+n,'title':f'Café Series {n:02}'} for n in range(6)]
        metadata = SimpleNamespace(request=lambda *a, **kw: {'results':raw,'total_pages':1,'total_results':6},
                                   normalize=lambda row:dict(row), display=lambda row, **kw:row)
        search = TVSearch(self.read,metadata)
        fields = ('primary_action','episode_count','available_count','completed_count','offline_percent',
                  'watched_percent','coverage_complete','pending_review_count','series_watched',
                  'season_count','status_label','year_range','quality_label')
        details = [self.read.detail(identity) for identity in self.ids]
        expected = [{key:detail.get(key) for key in fields} for detail in details]
        refs = []
        original = self.repo.library_read_context
        def context():
            value=original(); refs.append(weakref.ref(value)); return value
        query={'version':1,'scope':'discover','mode':'simple','groups':[],'sort':{'key':'auto','direction':'desc'}}
        with patch.object(self.repo,'library_read_context',context), counters(self.repo) as work:
            result=search.discover(query,page_size=20)
        self.assertEqual([{key:row.get(key) for key in fields} for row in result['items']],expected)
        self.assertEqual([row['id'] for row in result['items']],self.ids)
        self.assertEqual((result['total'],result['total_pages']), (6,1))
        self.assertEqual(work['connections'],1,work)
        self.assertLessEqual(work['selects'],14,work)
        self.assertEqual(max(work['paths'].values()),1,work)
        self.assertEqual(len(refs),1)
        self.assertIsNone(refs[0]())
        # A retained filtered scan must never retain the request snapshot, and
        # the next request must observe a file that disappeared meanwhile.
        next(self.root.glob('00-*.mkv')).unlink()
        filtered = {**query,'groups':[{'type':'availability','values':[{'id':'owned','label':'Owned'}]}]}
        with patch.object(self.repo,'library_read_context',context):
            refreshed = search.discover(filtered,page_size=20)
        self.assertEqual(refreshed['items'][0]['available_count'],3)
        self.assertEqual(len(search._scans),1)
        self.assertEqual(len(refs),2)
        self.assertTrue(all(ref() is None for ref in refs))

    def test_discover_starts_provider_while_independent_snapshot_is_preparing(self):
        provider_started = threading.Event()
        original = self.repo.library_read_context
        def context():
            self.assertTrue(provider_started.wait(1),'Provider waited for the complete local snapshot')
            return original()
        def request(*args,**kwargs):
            provider_started.set()
            return {'results':[{'id':8000,'tmdb_id':8000,'title':'Café Series 00'}],
                    'total_pages':1,'total_results':1}
        metadata=SimpleNamespace(request=request,normalize=lambda row:dict(row),display=lambda row,**kw:row)
        query={'version':1,'scope':'discover','mode':'simple','groups':[],'sort':{'key':'auto','direction':'desc'}}
        with patch.object(self.repo,'library_read_context',context):
            result=TVSearch(self.read,metadata).discover(query)
        self.assertEqual([row['id'] for row in result['items']],[self.ids[0]])

    def test_discover_preserves_snapshot_failure_before_simultaneous_provider_failure(self):
        def fail_provider(*args,**kwargs):raise OSError('provider unavailable')
        metadata=SimpleNamespace(request=fail_provider)
        query={'version':1,'scope':'discover','mode':'simple','groups':[],'sort':{'key':'auto','direction':'desc'}}
        with patch.object(self.repo,'library_read_context',side_effect=ValueError('invalid episode metadata')):
            with self.assertRaisesRegex(ValueError,'invalid episode metadata'):
                TVSearch(self.read,metadata).discover(query)

    def test_discover_preserves_local_projection_failure_before_provider_failure(self):
        def fail_provider(*args,**kwargs):raise OSError('provider unavailable')
        search=TVSearch(self.read,SimpleNamespace(request=fail_provider))
        query={'version':1,'scope':'discover','mode':'simple','groups':[],'sort':{'key':'auto','direction':'desc'}}
        refs=[];original=self.repo.library_read_context
        def snapshot():
            value=original();refs.append(weakref.ref(value));return value
        with patch.object(self.repo,'library_read_context',snapshot),patch.object(search,'local_rows',side_effect=ValueError('invalid local facts')):
            try:
                search.discover(query)
            except ValueError as error:
                self.assertEqual(str(error),'invalid local facts')
            else:self.fail('Local projection failure was hidden')
        gc.collect()
        self.assertEqual(len(refs),1)
        self.assertTrue(all(ref() is None for ref in refs))

    def test_exact_membership_full_fields_and_options(self):
        invisible = self.repo.refresh({'tmdb_id': 9991, 'title': 'Invisible', 'genres': ['Comedy'],
                                       'original_language': 'fr', 'origin_country': ['FR']}, [])
        pending = self.repo.refresh({'tmdb_id': 9992, 'title': 'Pending'}, [])
        assigned = self.repo.refresh({'tmdb_id': 9993, 'title': 'Assigned'}, [])
        folder = self.root/'assigned'; folder.mkdir()
        self.repo.approve_path(folder, 'folder', assigned)
        self.repo.review({'series_id': str(pending), 'path': str(self.root/'pending.mkv')}, 'Synthetic review')
        result = self.search.library(QUERY, page_size=100)
        self.assertEqual([row['id'] for row in result['items']], [assigned, *self.ids, pending])
        self.assertNotIn(invisible, [row['id'] for row in result['items']])
        self.assertEqual((result['total'], result['total_pages'], result['complete']), (8, 1, True))
        for row in result['items']:
            self.assertEqual(row, self.read.detail(row['id']))
        row = result['items'][1]
        self.assertEqual((row['episode_count'], row['available_count'], row['specials_count']), (36, 4, 2))
        self.assertEqual(row['cast'], [{'tmdb_id': 900, 'name': 'Creator', 'role': 'Creator'}])
        self.assertEqual(row['primary_action']['target']['code'], 'S01E01')
        self.assertTrue(row['primary_action']['playable'])
        options = self.search.options('library')
        self.assertEqual(options['language'], [{'id': 'en', 'label': 'English'}, {'id': 'fr', 'label': 'fr'}])
        self.assertEqual(options['country'], [{'id': 'FR', 'label': 'FR'}, {'id': 'GB', 'label': 'GB'}])
        self.assertEqual(options['genre'], [{'id': 'Comedy', 'label': 'Comedy'}, {'id': '18', 'label': 'Drama'}])

    def test_search_structural_bound_and_fresh_availability(self):
        with counters(self.repo) as work:
            result = self.search.library(QUERY)
        self.assertLessEqual(work['selects'], 14, work)
        self.assertEqual(max(work['paths'].values()), 1, work)
        self.assertEqual(result['total'], 6)
        path = next(self.root.glob('00-*.mkv')); path.unlink()
        self.assertEqual(self.search.library(QUERY)['items'][0]['available_count'], 3)
        path.write_bytes(b'synthetic')
        self.assertEqual(self.search.library(QUERY)['items'][0]['available_count'], 4)

    def test_options_structural_bound_and_no_detail_work(self):
        with counters(self.repo) as work:
            options = self.search.options('library')
        self.assertLessEqual(work['selects'], 2, work)
        self.assertEqual(max(work['paths'].values()), 1, work)
        self.assertTrue(options['library_source'])

    def test_full_episode_payload_and_library_state_share_rules(self):
        self.assertTrue(hasattr(self.repo, 'library_read_context'))
        context = self.repo.library_read_context()
        for identity in self.ids:
            full = self.repo.episodes(identity, today=context.today)
            self.assertEqual([{k:r[k] for k in STATE_KEYS} for r in full],
                             self.repo.library_episode_rows(identity, read_context=context))
            self.assertEqual(full[0]['overview'],'x'*2048)
            self.assertEqual(len(full[0]['guest_stars']),8)
            self.assertIn('metadata',full[0])
            self.assertEqual(self.read.detail(identity), self.read.detail(identity, read_context=context))
            self.assertEqual([{k:r[k] for k in STATE_KEYS} for r in self.repo.episodes(identity,1,limit=2,offset=1)],
                             self.repo.library_episode_rows(identity,1,limit=2,offset=1,read_context=context))
        with counters(self.repo) as work:
            self.read.detail(self.ids[0])
        self.assertLess(work['selects'], 14)

    def test_library_context_retains_only_episode_state(self):
        self.assertTrue(hasattr(self.repo,'library_read_context'))
        context = self.repo.library_read_context()
        for rows in context.episode_rows.values():
            for row in rows: self.assertEqual(set(row),STATE_KEYS)
        for name in ('episode_records','episode_credits','assembled_episodes'):
            self.assertFalse(hasattr(context,name))
        self.assertNotIn('x'*2048,repr(context))
        self.assertNotIn('Guest 0',repr(context))

    def test_episode_metadata_error_is_not_hidden_by_compact_projection(self):
        self.assertTrue(hasattr(self.repo,'library_read_context'))
        with self.repo.store.transaction() as db:
            db.execute("UPDATE episodes SET metadata='broken' WHERE id=(SELECT MAX(id) FROM episodes)")
        with self.assertRaises(ValueError): self.repo.library_read_context()
        with self.assertRaises(ValueError): self.repo.episodes(self.ids[-1])
        with self.repo.store.transaction() as db: db.execute("UPDATE episodes SET metadata='[]'")
        with self.assertRaises(AttributeError): self.repo.library_read_context()
        with self.assertRaises(AttributeError): self.repo.episodes(self.ids[0])

    def test_snapshot_survives_coordinated_write_and_refreshes_next_request(self):
        self.assertTrue(hasattr(self.repo,'library_read_context'))
        snapshot = self.repo.library_read_context()
        episode = self.repo.library_episode_rows(self.ids[0],1,read_context=snapshot)[0]
        ready, done = threading.Event(), threading.Event()
        errors = []
        def writer():
            try:
                ready.wait(2)
                self.repo.save_progress(episode['id'],position_ms=1234,player_activity=True)
            except BaseException as error: errors.append(error)
            finally: done.set()
        worker = threading.Thread(target=writer); worker.start(); ready.set()
        self.assertTrue(done.wait(3)); worker.join(1); self.assertFalse(errors)
        self.assertIsNone(episode['position_ms'])
        current = self.repo.library_read_context()
        self.assertEqual(self.repo.library_episode_rows(self.ids[0],1,read_context=current)[0]['position_ms'],1234)
        self.assertIsNot(snapshot.path_exists,current.path_exists)

    def test_concurrent_requests_do_not_share_contexts(self):
        contexts = []
        original = self.repo.library_read_context
        barrier = threading.Barrier(2)
        def context():
            value = original(); contexts.append(value); barrier.wait(3); return value
        results, errors = [], []
        def request():
            try: results.append(self.search.library(QUERY))
            except BaseException as error: errors.append(error)
        with patch.object(self.repo,'library_read_context',context):
            workers = [threading.Thread(target=request) for _ in range(2)]
            for worker in workers: worker.start()
            for worker in workers: worker.join(5)
        self.assertFalse(errors); self.assertEqual(len(results),2)
        self.assertEqual(results[0],results[1]); self.assertIsNot(contexts[0],contexts[1])
        self.assertIsNot(contexts[0].path_exists,contexts[1].path_exists)

    def test_local_rows_preserve_binding_encounter_order(self):
        root = self.root/'order'; root.mkdir()
        repo = TVCatalogRepository(root/'tv.sqlite',clock=lambda:1_600_000_000)
        seed(repo,root,1,adversarial=True)
        source = Path(os.environ['CP_TV_PERF_BASELINE_SOURCE'])/'services'
        owners = []
        for name in ('tv_catalog_repository','tv_read_model','tv_search'):
            spec=importlib.util.spec_from_file_location('before_'+name,source/(name+'.py'))
            module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); owners.append(module)
        before_repo=owners[0].TVCatalogRepository(root/'tv.sqlite')
        baseline=owners[2].TVSearch(owners[1].TVReadModel(before_repo),None).local_rows()
        self.assertEqual(TVSearch(TVReadModel(repo),None).local_rows(),baseline)

    def test_pagination_errors_and_empty_results(self):
        self.assertEqual(self.search.library(QUERY, page=999)['items'], [])
        self.assertEqual(self.search.library(QUERY, page=0, page_size=0)['page_size'], 1)
        self.assertEqual(self.search.library(QUERY, page_size=101)['page_size'], 100)
        absent = {**QUERY, 'groups': [{'type': 'title', 'values': [{'text': 'absent'}]}]}
        self.assertEqual((self.search.library(absent)['total'], self.search.library(absent)['total_pages']), (0, 1))
        with self.assertRaises(ValueError): self.search.options('invalid')
        with self.assertRaises(ValueError): self.search.library(QUERY, extras={'progress': 'invalid'})
