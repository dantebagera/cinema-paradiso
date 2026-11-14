"""Bounded synthetic service-only Discover comparison, one fresh process per observation.

Not the full-route Library memory protocol. Preparation/imports/fixture creation
are outside tracing; complete result serialization and release are inside it.
"""
import argparse
import gc
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tracemalloc
import weakref
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.tv_catalog_repository import TVCatalogRepository
from services.tv_read_model import TVReadModel
from services.tv_search import TVSearch
from tests.test_tv_library_read_performance import seed


def observation(version, count):
    root = Path(os.environ['CP_TEST_ROOT']) / f'{version}-{count}'
    root.mkdir()
    repo = TVCatalogRepository(root/'tv.sqlite', clock=lambda:1_600_000_000)
    seed(repo, root, count)
    owner = TVSearch
    if version == 'baseline':
        path = Path(os.environ['CP_TV_PERF_BASELINE_SOURCE'])/'services/tv_search.py'
        spec = importlib.util.spec_from_file_location('before_discover_search', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        owner = module.TVSearch
    rows = [{'id':8000+n,'tmdb_id':8000+n,'title':f'Café Series {n:02}'} for n in range(count)]
    metadata = SimpleNamespace(
        request=lambda *a, page=1, **kw:dict(results=rows[(page-1)*20:page*20],
                                           total_pages=math.ceil(count/20),total_results=count),
        normalize=lambda row:dict(row), display=lambda row, **kw:row)
    search = owner(TVReadModel(repo), metadata)
    query = dict(version=1,scope='discover',mode='simple',groups=[],sort=dict(key='auto',direction='desc'))
    refs = []
    original = repo.library_read_context
    def context():
        value=original(); refs.append(weakref.ref(value)); return value
    modules = set(sys.modules)
    with patch.object(repo,'library_read_context',context):
        tracemalloc.start(1)
        gc.collect()
        start=tracemalloc.get_traced_memory()[0]
        tracemalloc.reset_peak()
        result=search.discover(query,page_size=count)
        body=json.dumps(result,sort_keys=True).replace(str(root).replace('\\','\\\\'),'<ROOT>').encode()
        digest=hashlib.sha256(body).hexdigest()
        size=len(body)
        peak=tracemalloc.get_traced_memory()[1]-start
        del result, body
        gc.collect()
        residual=max(0,tracemalloc.get_traced_memory()[0]-start)
        tracemalloc.stop()
    record=dict(version=version,count=count,peak=peak,residual=residual,bytes=size,sha256=digest,
                contexts=len(refs),collected=all(ref() is None for ref in refs),
                late_imports=sorted(set(sys.modules)-modules))
    print(json.dumps(record))
    assert record['contexts']==1 and record['collected'] and not record['late_imports'],record


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--version',choices=['baseline','candidate'])
    parser.add_argument('--count',type=int,choices=[6,24])
    args=parser.parse_args()
    if args.version:
        observation(args.version,args.count)
    else:
        records=[]
        for count in (6,24):
            for version in ('baseline','candidate'):
                process=subprocess.run([sys.executable,__file__,'--version',version,'--count',str(count)],
                                       capture_output=True,text=True,timeout=35)
                print(process.stdout, end='')
                if process.returncode: raise RuntimeError(process.stderr)
                records.append(json.loads(process.stdout))
            before,after=records[-2:]
            assert before['sha256']==after['sha256'],(before,after)
            assert after['peak']<=before['peak']+max(1024**2,before['peak']*.1),(before,after)
            assert after['residual']<=before['residual']+256*1024,(before,after)
        Path(os.environ['CP_TV_PERF_RUN_DIR'],'discover-memory.json').write_text(json.dumps(records,indent=2))
        print('PASS: complete output parity, peak/residual bounds and request-context collection')
