"""One bounded owner-level profile using production facts through SQLite mode=ro.

No app import, constructor/migration, catalog write or real media client. Uses the
existing TV owners; only the connection factory is replaced for read-only safety.
"""
import argparse
import contextlib
import cProfile
import io
import json
import hashlib
import importlib.util
import math
import os
from pathlib import Path
import pstats
import sqlite3
import sys
import threading
import time
import urllib.request
from types import SimpleNamespace
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.tv_catalog_repository import TVCatalogRepository
from services.tv_metadata import TVMetadata
from services.tv_read_model import TVReadModel
from services.tv_search import TVSearch


class ReadOnlyStore:
    def __init__(self, path):
        self.path = Path(path)

    @contextlib.contextmanager
    def connection(self):
        db = sqlite3.connect(self.path.resolve().as_uri()+'?mode=ro', uri=True)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA query_only=ON')
        try:
            yield db
        finally:
            db.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('scope', choices=['library','discover','owned-compare'])
    args = parser.parse_args()
    cfg = json.loads(Path('config.json').read_text(encoding='utf8'))
    root = Path(cfg.get('user_data_dir') or Path.cwd()/'data')
    repo = object.__new__(TVCatalogRepository)
    repo.store, repo.clock = ReadOnlyStore(root/'tv-catalog.sqlite'), time.time
    if args.scope == 'owned-compare':
        # Fixed provider summaries isolate local fact work on real read-only
        # data. This is not a live route or a provider latency comparison.
        from tests.test_tv_library_read_performance import counters
        with repo.store.connection() as db:
            rows = [dict(row) for row in db.execute('SELECT tmdb_id AS id,tmdb_id,title FROM series ORDER BY id LIMIT 40')]
        metadata = SimpleNamespace(
            request=lambda *a,page=1,**kw:dict(results=rows[(page-1)*20:page*20],total_pages=math.ceil(len(rows)/20),total_results=len(rows)),
            normalize=lambda row:dict(row),display=lambda row,**kw:row)
        path=Path(os.environ['CP_TV_PERF_BASELINE_SOURCE'])/'services/tv_search.py'
        spec=importlib.util.spec_from_file_location('before_owned_search',path)
        module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        records=[]
        query=dict(version=1,scope='discover',mode='simple',groups=[],sort=dict(key='auto',direction='desc'))
        for version,owner in [('baseline',module.TVSearch),('candidate',TVSearch)]:
            search=owner(TVReadModel(repo),metadata)
            with counters(repo) as work:
                start=time.perf_counter()
                result=search.discover(query,page_size=40)
                elapsed=(time.perf_counter()-start)*1000
            digest=hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest()
            records.append(dict(version=version,ms=elapsed,items=len(result['items']),connections=work['connections'],
                                selects=work['selects'],distinct_paths=len(work['paths']),max_checks=max(work['paths'].values()),sha256=digest))
        print(json.dumps(records))
        assert records[0]['sha256']==records[1]['sha256'],records
        assert records[1]['connections']==1 and records[1]['max_checks']==1,records
        return
    with ReadOnlyStore(root/'acquisition.sqlite').connection() as db:
        profile = json.loads(db.execute("SELECT payload FROM profiles WHERE id='safe-hd'").fetchone()[0])
    events, lock = [], threading.Lock()
    def record(**event):
        with lock:
            events.append(event)
    def opener(url, **kwargs):
        start = time.perf_counter()
        try:
            return urllib.request.urlopen(url, **kwargs)
        finally:
            record(stage='provider_headers',path=urlsplit(url).path,ms=(time.perf_counter()-start)*1000)
    metadata = TVMetadata(repo, lambda:cfg.get('tmdb_key',''), opener=opener)
    read = TVReadModel(repo)
    original_detail = read.detail
    def detail(*a, **kw):
        start = time.perf_counter()
        try:
            return original_detail(*a, **kw)
        finally:
            record(stage='detail',ms=(time.perf_counter()-start)*1000)
    read.detail = detail
    search = TVSearch(read,metadata,profile=lambda:profile)
    original_rows = search.local_rows
    def rows(*a, **kw):
        start=time.perf_counter()
        try:
            return original_rows(*a, **kw)
        finally:
            record(stage='local_rows',ms=(time.perf_counter()-start)*1000)
    search.local_rows=rows
    query={'version':1,'scope':args.scope,'media_type':'tv','mode':'simple','groups':[],
           'sort':{'key':'added' if args.scope=='library' else 'auto','direction':'desc'}}
    profiler=cProfile.Profile()
    profiler.enable()
    start=time.perf_counter()
    result=(search.library(query,page_size=39) if args.scope=='library' else search.discover(query,page_size=40))
    elapsed=(time.perf_counter()-start)*1000
    profiler.disable()
    print(json.dumps({'scope':args.scope,'total_ms':elapsed,'items':len(result['items']),'events':events}))
    out=io.StringIO()
    pstats.Stats(profiler,stream=out).sort_stats('cumulative').print_stats(18)
    print(out.getvalue())


if __name__=='__main__':
    main()
