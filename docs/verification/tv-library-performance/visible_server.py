"""Isolated CP shell with canonical TV routes and strictly read-only real TV facts.

No normal app startup threads, migrations on real stores, clients or actions.
Movie results are empty fixture responses: compare TV stages, not Movie speed.
"""
import cProfile
import io
import importlib.util
import json
import os
from pathlib import Path
import pstats
import shutil
import sys
import threading
import time
import urllib.request
from urllib.parse import urlsplit
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
if os.environ.get('CP_TEST_MODE') != '1':
    raise RuntimeError('Explicit isolated test mode required')
root = Path(os.environ['CP_TEST_ROOT']).resolve()
port = int(os.environ.get('CP_PORT','5130'))
if port == 5000:
    raise RuntimeError('Production port prohibited')
cfg = json.loads(Path('config.json').read_text(encoding='utf8'))
data_root = Path(cfg.get('user_data_dir') or Path.cwd()/'data')
network_opener = urllib.request.urlopen
import app
from flask import jsonify, request
from tools.tv_readonly_profile import ReadOnlyStore
from tools.tv_tab_timeline import PROBE
from services.tv_catalog_repository import TVCatalogRepository
from services.tv_read_model import TVReadModel
from services.tv_metadata import TVMetadata
from services.tv_search import TVSearch

if os.environ.get('CP_TV_DIAG_BASELINE_SOURCE'):
    source=Path(os.environ['CP_TV_DIAG_BASELINE_SOURCE'])/'services/tv_search.py'
    spec=importlib.util.spec_from_file_location('diagnostic_baseline_search',source)
    baseline=importlib.util.module_from_spec(spec);spec.loader.exec_module(baseline)
    TVSearch=baseline.TVSearch

output_lock = threading.Lock()
def event(stage, **data):
    with output_lock:
        print('CP_TV_DIAG '+json.dumps(dict(stage=stage,t=time.perf_counter()*1000,**data)),flush=True)

repo = object.__new__(TVCatalogRepository)
repo.store, repo.clock = ReadOnlyStore(data_root/'tv-catalog.sqlite'), time.time
acq = ReadOnlyStore(data_root/'acquisition.sqlite')
def profile(identity):
    with acq.connection() as db:
        return json.loads(db.execute('SELECT payload FROM profiles WHERE id=?',(identity,)).fetchone()[0])
def monitored():
    with acq.connection() as db:
        return {row[0] for row in db.execute("SELECT DISTINCT tmdb_id FROM tv_tasks WHERE state IN ('running','waiting','waiting_season_end','needs_review')")}
def opener(url, **kwargs):
    if urlsplit(url).hostname != 'api.themoviedb.org':
        raise RuntimeError('Only normal TMDB reads allowed')
    start=time.perf_counter()
    try:
        return network_opener(url,**kwargs)
    finally:
        event('provider_headers',path=urlsplit(url).path,ms=(time.perf_counter()-start)*1000)
metadata=TVMetadata(repo,lambda:cfg.get('tmdb_key',''),opener=opener)
read=TVReadModel(repo)
search=TVSearch(read,metadata)
for owner,name in [(repo,'library_read_context'),(search,'local_rows'),(read,'maintenance'),(read,'tv_lists')]:
    original=getattr(owner,name)
    def measured(*args,_original=original,_name=name,**kwargs):
        start=time.perf_counter()
        try:return _original(*args,**kwargs)
        finally:event(_name,ms=(time.perf_counter()-start)*1000)
    setattr(owner,name,measured)
app._tv_enabled=True
owners=dict(repository=repo,read=read,metadata=metadata,search=search,
            acquisition=SimpleNamespace(acquisition=SimpleNamespace(profile=profile)),
            monitoring=SimpleNamespace(monitored_tmdb_ids=monitored))
app._tv_services._instances[Path(app._user_data_dir).resolve()/'tv-catalog.sqlite']=owners
app._player_manager.os_opener=lambda *a,**kw: (_ for _ in ()).throw(RuntimeError('Player blocked'))

@app.app.before_request
def diagnostic_guard():
    path=request.path
    if path=='/__cp_tab_probe.js':return app.Response(PROBE,mimetype='application/javascript')
    if path=='/__cp_probe_evidence' and request.method=='POST':
        records=request.get_json()
        if not isinstance(records,list) or len(records)>2000:return jsonify(error='Invalid capture'),400
        with (root/'browser-events.json').open('x',encoding='utf8') as output:json.dump(records,output,indent=2)
        return jsonify(saved=True,events=len(records))
    if path=='/api/tmdb/discover/advanced':return jsonify(results=[],page=1,total_pages=1,total_results=0)
    if path=='/api/library/search/advanced':return jsonify(items=[],page=1,page_size=40,total=0,total_pages=1,complete=True)
    if request.method not in {'GET','HEAD'} and path not in {'/api/tv/catalog/search','/api/tv/catalog/enrich'}:
        return jsonify(error='Diagnostic actions are disabled'),405
    if path.startswith('/api/tv/') and request.method=='GET' and not (
        path in {'/api/tv/capabilities','/api/tv/catalog/options','/api/tv/lists','/api/tv/maintenance'} or
        path.endswith('/poster')):
        return jsonify(error='Diagnostic permits catalog reads only'),405

@app.app.after_request
def inject_probe(response):
    if response.mimetype=='text/html':
        response.direct_passthrough=False
        response.set_data(response.get_data().replace(b'<head>',b'<head><script src="/__cp_tab_probe.js" data-capture="true"></script>',1))
    return response

original_wsgi=app.app.wsgi_app
def profiled_wsgi(environ,start_response):
    path=environ.get('PATH_INFO','')
    profiler=cProfile.Profile() if path=='/api/tv/catalog/search' and os.environ.get('CP_TV_DIAG_PROFILE')=='1' else None
    start=time.perf_counter()
    if profiler:profiler.enable()
    try:return original_wsgi(environ,start_response)
    finally:
        if profiler:
            profiler.disable()
            stream=io.StringIO()
            pstats.Stats(profiler,stream=stream).sort_stats('cumulative').print_stats(22)
            event('route_profile',ms=(time.perf_counter()-start)*1000,profile=stream.getvalue())
app.app.wsgi_app=profiled_wsgi

if __name__=='__main__':
    dist=Path(os.environ['CP_TEST_DIST_DIR'])
    if not dist.is_relative_to(root):raise RuntimeError('Dist must remain isolated')
    if not (dist/'index.html').is_file():shutil.copytree(Path.cwd()/'dist',dist)
    event('ready',port=port,data_mode='ro/query_only',movie_results='empty fixture',startup_threads=False)
    app.app.run(host='127.0.0.1',port=port,debug=False,threaded=True,use_reloader=False)
