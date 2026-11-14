"""Isolated Library gates. Importing this file performs no request or app setup."""
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import date
import gc
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tracemalloc
import weakref

class ProbeGateError(AssertionError):
    def __init__(self, message, record):
        super().__init__(message)
        self.record = record


def record_memory_observation(setup, path):
    try:
        record = measure_single_request(setup)
    except ProbeGateError as error:
        with path.open('x', encoding='utf-8') as output:
            json.dump({**error.record, 'valid':False, 'error':str(error)},output,indent=2)
        raise
    with path.open('x', encoding='utf-8') as output:
        json.dump({**record,'valid':True},output,indent=2)
    return record

@dataclass
class ProbeSetup:
    client: object
    dispatch: object
    repository_context_refs: list
    flask_context_refs: list
    expected_repository_contexts: int
    setup_manifest: dict
    stack: object = None
    owners: object = None


def measure_single_request(setup):
    client, setup.client = setup.client, None
    before_modules = set(sys.modules)
    tracemalloc.start(1)
    gc.collect()
    start = tracemalloc.get_traced_memory()[0]
    tracemalloc.reset_peak()
    response = setup.dispatch(client)
    body = response.get_data()
    peak = tracemalloc.get_traced_memory()[1]-start
    status, size, encoding = response.status_code, len(body), response.headers.get('Content-Encoding', '')
    response.close()
    del body, response, client
    gc.collect()
    residual = max(0, tracemalloc.get_traced_memory()[0]-start)
    tracemalloc.stop()
    repo_count = len(setup.repository_context_refs)
    flask_count = len(setup.flask_context_refs)
    record = dict(status=status, bytes=size, encoding=encoding, peak_increment=peak,
                  residual_increment=residual, contexts=repo_count,
                  contexts_collected=all(ref() is None for ref in setup.repository_context_refs),
                  flask_contexts=flask_count,
                  flask_contexts_collected=all(ref() is None for ref in setup.flask_context_refs),
                  late_imports=sorted(set(sys.modules)-before_modules), setup=setup.setup_manifest)
    record.update({key:setup.setup_manifest[key] for key in ('version','size','endpoint') if key in setup.setup_manifest})
    checks = [(repo_count == setup.expected_repository_contexts,'Missing or unexpected repository context evidence'),
              (flask_count == 1,'Missing or unexpected Flask request context evidence'),
              (status == 200 and record['contexts_collected'] and record['flask_contexts_collected'],'Response/context release failure'),
              (not record['late_imports'],f"Late imports: {record['late_imports']}")]
    for passed, message in checks:
        if not passed: raise ProbeGateError(message,record)
    return record


def prepare_probe(version, size, endpoint, *, baseline_source, run_dir):
    sys.path.insert(0, str(Path.cwd()))
    if version == 'baseline':
        import services
        for name in ('tv_catalog_repository', 'tv_read_model', 'tv_search'):
            fullname = 'services.'+name
            spec = importlib.util.spec_from_file_location(fullname, baseline_source/'services'/f'{name}.py')
            module = importlib.util.module_from_spec(spec)
            sys.modules[fullname] = module
            setattr(services, name, module)
            spec.loader.exec_module(module)
    # Explicitly finish lazy test-client and route dependencies before tracing.
    import flask.testing
    import werkzeug.test
    import flask.sessions
    import flask.json.provider
    import encodings.idna
    import stringprep
    from flask import Flask
    from unittest.mock import patch
    import app as production
    from services.tv_routes import register_tv_routes
    from services.tv_catalog_repository import TVCatalogRepository
    from services.tv_read_model import TVReadModel
    from services.tv_search import TVSearch
    from tests.test_tv_library_read_performance import seed, QUERY
    class FixedDate(date):
        @classmethod
        def today(cls): return cls(2026, 10, 23)
    root = Path(os.environ['CP_TEST_ROOT'])
    repository = TVCatalogRepository(root/'fixture.sqlite', clock=lambda: 1_600_000_000)
    seed(repository, root, size, adversarial=os.environ.get('CP_TV_PERF_MODE') == 'full')
    read = TVReadModel(repository)
    class Display:
        def display(self, row): return dict(row)
    search = TVSearch(read, Display())
    app = Flask(__name__)
    app.before_request(production._start_route_timer)
    app.after_request(production._finish_route_timer)
    register_tv_routes(app, lambda: {'repository': repository, 'read': read, 'search': search}, lambda: True, None)
    app.testing = True
    client = app.test_client()
    client.preserve_context = False
    repo_refs, flask_refs = [], []
    original_request_context = app.request_context
    def request_context(environ):
        result = original_request_context(environ)
        flask_refs.append(weakref.ref(result))
        return result
    app.request_context = request_context
    if hasattr(repository, 'library_read_context'):
        original = repository.library_read_context
        def context():
            result = original()
            repo_refs.append(weakref.ref(result))
            return result
        repository.library_read_context = context
    stack = ExitStack()
    stack.enter_context(patch('services.tv_search.date', FixedDate))
    stack.enter_context(patch('services.tv_catalog_repository.date', FixedDate))
    calls = [0]
    def dispatch(client):
        calls[0] += 1
        if endpoint == 'cards':
            return client.post('/api/tv/catalog/search', json={'scope':'library','query':QUERY,'page':1,'page_size':24}, headers={'Accept-Encoding':'gzip'})
        return client.get('/api/tv/catalog/options?scope=library', headers={'Accept-Encoding':'gzip'})
    manifest = dict(client_prepared=client is not None, tracing_at_setup=tracemalloc.is_tracing(),
                    preparation_dispatches=calls[0], version=version, size=size, endpoint=endpoint,
                    preloaded_codecs=['encodings.idna','stringprep'],
                    probe_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    assert not manifest['tracing_at_setup'] and calls[0] == 0
    return ProbeSetup(client, dispatch, repo_refs, flask_refs,
                      int(version == 'candidate' and endpoint == 'cards'), manifest, stack,
                      (repository, read, search, root))


def main():
    mode, version, size, endpoint = sys.argv[1:]
    size = int(size)
    os.environ['CP_TV_PERF_MODE'] = mode
    run_dir = Path(os.environ['CP_TV_PERF_RUN_DIR'])
    dest = run_dir/f'{mode}-{version}-{size}-{endpoint}.json'
    if dest.exists(): raise RuntimeError('Refusing to overwrite recorded observation')
    setup = prepare_probe(version, size, endpoint,
                          baseline_source=Path(os.environ['CP_TV_PERF_BASELINE_SOURCE']), run_dir=run_dir)
    try:
        if mode == 'memory':
            value = record_memory_observation(setup,dest)
            print(json.dumps(value))
            if version == 'candidate':
                baseline = json.loads((run_dir/f'memory-baseline-{size}-{endpoint}.json').read_text())
                assert (value['status'],value['bytes'],value['encoding']) == (baseline['status'],baseline['bytes'],baseline['encoding'])
                assert value['peak_increment'] <= baseline['peak_increment']+max(1048576, .1*baseline['peak_increment']), 'Peak gate failed'
                assert value['residual_increment'] <= baseline['residual_increment']+262144, 'Residual gate failed'
        elif mode == 'structure':
            from tests.test_tv_library_read_performance import counters
            repository = setup.owners[0]
            with counters(repository) as work:
                response = setup.dispatch(setup.client)
                response.get_data()
            value = dict(version=version,size=size,endpoint=endpoint,status=response.status_code,
                         selects=work['selects'],connections=work['connections'],distinct_paths=len(work['paths']),
                         max_checks_per_path=max(work['paths'].values(),default=0))
            print(json.dumps(value))
            dest.write_text(json.dumps(value, indent=2))
            assert value['status'] == 200
        else:
            repository, read, search, root = setup.owners
            response = setup.dispatch(setup.client)
            body = response.get_data()
            if response.headers.get('Content-Encoding') == 'gzip': body = gzip.decompress(body)
            value = dict(response=json.loads(body),details={str(i):read.detail(i) for i in range(1,size+1)},
                         episodes={str(i):repository.episodes(i) for i in range(1,size+1)},local_rows=search.local_rows())
            text = json.dumps(value,ensure_ascii=False,sort_keys=True).replace(str(root).replace('\\','\\\\'),'<ROOT>')
            dest.write_text(text,encoding='utf-8')
            if version == 'candidate':
                assert text == (run_dir/f'full-baseline-{size}-{endpoint}.json').read_text(encoding='utf-8'), 'Full-output mismatch'
            print(f'{version} {size} {endpoint}: complete response/detail/episode/local-row output stored; HTTP {response.status_code}')
    finally:
        setup.stack.close()

if __name__ == '__main__': main()
