"""Finite synthetic API comparison. Never opens a production data root."""
import argparse
import ctypes
import importlib.util
import json
import os
from pathlib import Path
import statistics
import sys
import tempfile
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--variant', choices=['baseline', 'candidate'], required=True)
    parser.add_argument('--remaining-cpu', type=float, default=30)
    args = parser.parse_args()
    root = Path(os.environ['CP_TEST_ROOT']).resolve()
    if os.environ.get('CP_TEST_MODE') != '1' or os.environ.get('CP_TEST_QBT_MODE') != 'embedded' or Path(tempfile.gettempdir()).resolve() not in root.parents:
        raise RuntimeError('Isolated temporary embedded test mode required')
    project = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project))
    started = time.perf_counter()
    cpu_start = time.process_time()

    def budget():
        if time.process_time() - cpu_start > args.remaining_cpu or time.perf_counter() - started > 180:
            raise RuntimeError('Finite capture budget exhausted; no extension')

    if args.variant == 'baseline':
        for name, relative in [('services.catalog_store', 'services/catalog_store.py'), ('services.catalog_repository', 'services/catalog_repository.py'), ('app', 'app.py')]:
            spec = importlib.util.spec_from_file_location(name, root / 'baseline' / relative)
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
    import app
    import services.catalog_store as module
    from tests.test_catalog_store import CatalogStoreTest

    app._user_data_dir = str(root / 'performance' / 'data')
    repository = app._catalog_repository()
    connection = repository.store.connect()
    try:
        empty = connection.execute('SELECT COUNT(*) FROM media_files').fetchone()[0] == 0
    finally:
        connection.close()
    if empty:
        documents = CatalogStoreTest()._paging_documents(4000)
        files = documents['app_metadata/files.json']['files']
        movies = documents['app_metadata/tmdb_metadata.json']['movies']
        plex = documents['app_metadata/plex_metadata.json']['files']
        for index, (key, record) in enumerate(files.items()):
            movie = movies[record['tmdb_id']]
            movie['title'] = record['identity_title'] = f'Synthetic Movie {index:04d}'
            movie['plot'] = ('A winter expedition crosses distant valleys with a changing ensemble. ' * 12) + ('Christmas gathering.' if index % 53 == 0 else 'Quiet evening.')
            movie['keywords'] += ['winter expedition', 'ensemble voyage']
            plex[key] = {'path': record['path'], 'tmdb_id': record['tmdb_id'], 'plex_title': movie['title'], 'plex_year': movie['year'], 'summary': movie['plot'], 'genres': movie['genres']}
        repository.store.import_documents(documents, {})
    budget()
    client = app.app.test_client()
    normalize = module._catalog_search_key
    normalization_calls = [0]
    def counted(value):
        normalization_calls[0] += 1
        return normalize(value)
    module._catalog_search_key = counted
    misses = [0]
    if hasattr(module, '_uncached_catalog_search_key'):
        compute = module._uncached_catalog_search_key
        def computed(value):
            misses[0] += 1
            return compute(value)
        module._uncached_catalog_search_key = computed
    results = {}
    core = lambda: int(ctypes.windll.kernel32.GetCurrentProcessorNumber())
    for text in ['christmas', 'm', 'no-synthetic-match-xyz']:
        samples = []
        if hasattr(module, '_SEARCH_NORMALIZATION_CACHE'):
            module._SEARCH_NORMALIZATION_CACHE.clear()
        for sample in range(4):
            budget()
            count_before, misses_before = normalization_calls[0], misses[0]
            wall, cpu, processor = time.perf_counter(), time.process_time(), core()
            response = client.post('/api/library/search/advanced', json={'query': {'version': 1, 'scope': 'library', 'mode': 'advanced', 'groups': [{'type': 'title', 'values': [{'text': text}]}], 'sort': {'key': 'added', 'direction': 'desc'}}, 'page': 1, 'page_size': 40})
            elapsed, cpu_elapsed = time.perf_counter() - wall, time.process_time() - cpu
            if response.status_code != 200:
                raise RuntimeError(response.get_data(as_text=True))
            data = response.get_json()
            samples.append({'wall_ms': round(elapsed * 1000, 3), 'cpu_ms': round(cpu_elapsed * 1000, 3), 'normalization_calls': normalization_calls[0] - count_before, 'normalization_misses': misses[0] - misses_before if args.variant == 'candidate' else normalization_calls[0] - count_before, 'processor_start': processor, 'processor_end': core()})
            budget()
        results[text] = {'samples': samples, 'warm_median_ms': statistics.median(item['wall_ms'] for item in samples[1:]), 'response': data}
    report = {'variant': args.variant, 'results': results, 'cpu_seconds': time.process_time() - cpu_start, 'wall_seconds': time.perf_counter() - started, 'cache': module._SEARCH_NORMALIZATION_CACHE.info() if hasattr(module, '_SEARCH_NORMALIZATION_CACHE') else None, 'core_history': 'Only boundary processor numbers sampled; intervening scheduling and core-class equivalence are unproved.'}
    target = root / ('performance-' + args.variant + '.json')
    target.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({key: value for key, value in report.items() if key != 'results'}))
    print(json.dumps({text: {key: value for key, value in result.items() if key != 'response'} for text, result in results.items()}, indent=2))


if __name__ == '__main__':
    main()
